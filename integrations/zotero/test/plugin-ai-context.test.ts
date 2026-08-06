// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/ai-context-zotero", async () => {
  const actual = await vi.importActual<typeof import("../src/ai-context-zotero")>(
    "../src/ai-context-zotero",
  );
  return {
    ...actual,
    normalizeAIContextTargets: vi.fn(),
    resolveAIContextAttachment: vi.fn(),
  };
});
vi.mock("../src/ai-context-open-handler", async () => {
  const actual = await vi.importActual<typeof import("../src/ai-context-open-handler")>(
    "../src/ai-context-open-handler",
  );
  return { ...actual, installAIContextOpenHandler: vi.fn() };
});

import {
  parseAIContextDocument,
  renderNewAIContextDocument,
  type AIContextDocument,
  type AIContextMessage,
  type AIContextPaper,
  type AIContextProjectionResult,
} from "../src/ai-context";
import {
  normalizeAIContextTargets,
  resolveAIContextAttachment,
} from "../src/ai-context-zotero";
import {
  installAIContextOpenHandler,
  type AIContextOpenHandler,
} from "../src/ai-context-open-handler";
import {
  AI_CONTEXT_MENU_IDS,
  ZoteroChatPlugin,
  isCreateReadingContextCommand,
} from "../src/plugin";

const normalizeTargetsMock = vi.mocked(normalizeAIContextTargets);
const resolveAttachmentMock = vi.mocked(resolveAIContextAttachment);
const installOpenHandlerMock = vi.mocked(installAIContextOpenHandler);
let installedOpenCallbacks: {
  isCandidate(item: unknown): boolean;
  openAIContext(item: unknown): unknown;
} | null = null;

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  installedOpenCallbacks = null;
});

const userEntry = (id: string, text: string) => ({ id, kind: "user" as const, text });
const assistantEntry = (id: string, text: string) => ({ id, kind: "assistant" as const, text });
const paperItem = (key: string, libraryID = 1) => ({
  id: key === "P1" ? 11 : key === "P2" ? 12 : 13,
  key,
  libraryID,
  itemType: "journalArticle",
  isRegularItem: () => true,
  isEditable: () => true,
  getField: (name: string) => name === "title" ? "Title " + key : "",
  getCreators: () => [],
  getAttachments: () => [],
});
const secondaryPaper = (itemKey: string) => ({
  id: "1-A-" + itemKey,
  libraryID: "1",
  attachmentKey: "A-" + itemKey,
  itemKey,
  title: "Title " + itemKey,
  mode: "retrieval" as const,
});

function emptyProjection(): AIContextProjectionResult {
  return { created: [], reused: [], missing: [] };
}

function documentFixture(
  id: string,
  kind: "conversation" | "reading" = "conversation",
  options: {
    capturedEntryIds?: string[];
    memoryMarkdown?: string;
    messages?: AIContextMessage[];
    papers?: AIContextPaper[];
  } = {},
): AIContextDocument {
  const messages = options.messages ?? [];
  const papers = options.papers ?? [{ libraryID: "1", itemKey: "P1", title: "Title P1" }];
  const manifest = {
    schemaVersion: 1 as const,
    id,
    contextKey: (kind === "reading" ? "reading:" : "conversation:") + id,
    kind,
    sourceThreadId: kind === "conversation" ? id : null,
    createdAt: "2026-07-31T00:00:00.000Z",
    updatedAt: "2026-07-31T00:00:00.000Z",
    status: "active" as const,
    papers,
    projection: {
      mode: "attached" as const,
      targets: papers.map(({ libraryID, itemKey }) => ({ libraryID, itemKey })),
    },
    capturedEntryIds: options.capturedEntryIds ?? messages.map(({ id: entryID }) => entryID),
  };
  const synthesis = {
    title: "Decoding",
    description: "Resumable context.",
    category: "codes" as const,
    status: "active" as const,
    memoryMarkdown: options.memoryMarkdown ?? "memory",
    progressMarkdown: "not started",
    nextStepMarkdown: "read P1",
    readingPlan: kind === "reading"
      ? papers.map(({ itemKey }) => ({ itemKey, rationale: "first", guidance: "read all" }))
      : [],
  };
  const relativePath = "drafts/ai-contexts/" + id + ".qmd";
  return parseAIContextDocument(
    relativePath,
    renderNewAIContextDocument({ manifest, synthesis, messages }),
  );
}

function readerContextFor(item: ReturnType<typeof paperItem>) {
  const title = item.getField("title");
  return {
    schemaVersion: 1,
    capturedAt: "2026-07-31T00:00:00.000Z",
    attachment: {
      id: 21, key: "A-" + item.key, libraryID: 1, title, creators: [], tags: [],
    },
    parent: {
      id: item.id, key: item.key, libraryID: item.libraryID,
      title, creators: [], tags: [],
    },
    pdfPath: "/papers/" + item.key + ".pdf",
    page: {
      pageIndex: 0, pageNumber: 1, pageCount: 1, pageLabel: "1",
      text: "", source: "none", warnings: [],
    },
    selection: null,
    fullText: { source: "none", characters: 0 },
    workspace: {
      root: "/repo", context: "/repo/.research-loop/context.json",
      currentPage: "", currentSelection: "", pdfText: "", agents: "/repo/AGENTS.md",
    },
    warnings: [],
  };
}

function normalizeFixture(items: unknown[]): AIContextPaper[] {
  const parents = items.map((item: any) => item.isPDFAttachment?.()
    ? paperItem(String(item.parentKey))
    : item);
  return [...new Map(parents.map((item: any) => [
    String(item.libraryID) + ":" + String(item.key),
    {
      libraryID: String(item.libraryID),
      itemKey: String(item.key),
      title: String(item.getField("title")),
    },
  ])).values()];
}

function aiContextPluginHarness(input: {
  activeThreadId?: string;
  entries?: Array<ReturnType<typeof userEntry> | ReturnType<typeof assistantEntry>>;
  activePrimary?: ReturnType<typeof paperItem> | null;
  uiPrimary?: ReturnType<typeof paperItem> | null;
  secondary?: Array<ReturnType<typeof secondaryPaper>>;
  selected?: unknown[];
  normalizedPapers?: AIContextPaper[];
  normalizeError?: Error;
  saveError?: Error;
  pendingRepairs?: Array<{ document: AIContextDocument; status: AIContextProjectionResult }>;
  resolvedDocument?: AIContextDocument;
  stubActivation?: boolean;
  openSupported?: boolean;
  connected?: boolean;
} = {}) {
  const selected = input.selected ?? [];
  (window as any).ZoteroPane = { getSelectedItems: vi.fn(() => selected) };
  const debug = vi.fn();
  vi.stubGlobal("Zotero", {
    getMainWindow: () => window,
    getMainWindows: () => [window],
    Libraries: { userLibraryID: 1 },
    FileHandlers: {},
    debug,
  });

  normalizeTargetsMock.mockReset();
  normalizeTargetsMock.mockImplementation(async (_runtime, items) => {
    if (input.normalizeError) throw input.normalizeError;
    return input.normalizedPapers ?? normalizeFixture(items);
  });
  const resolvedDocument = input.resolvedDocument ?? documentFixture("open-1");
  resolveAttachmentMock.mockReset();
  resolveAttachmentMock.mockResolvedValue({
    item: { key: "A1" },
    relativePath: resolvedDocument.relativePath,
    document: resolvedDocument,
  });
  installOpenHandlerMock.mockReset();
  installOpenHandlerMock.mockImplementation((_handlers, callbacks) => {
    installedOpenCallbacks = callbacks;
    return {
      supported: input.openSupported !== false,
      dispose: vi.fn(),
    } satisfies AIContextOpenHandler;
  });

  const plugin = new ZoteroChatPlugin() as any;
  plugin.settings = { qlabRoot: "/repo" };
  plugin.selectedModel = "test-model";
  plugin.selectedEffort = "medium";
  plugin.pendingScreenshots = [];
  plugin.context = input.uiPrimary ? readerContextFor(input.uiPrimary) : null;
  const activeReader = input.activePrimary === undefined
    ? plugin.context
    : input.activePrimary ? readerContextFor(input.activePrimary) : null;
  const state = {
    activeThreadId: input.activeThreadId ?? "thread-1",
    running: false,
    connected: input.connected ?? true,
    models: [],
    mode: "agent" as const,
  };
  plugin.codex = {
    state,
    getChatEntries: vi.fn(() => input.entries ?? []),
    getActiveDiffs: vi.fn(() => []),
    getActiveReaderContext: vi.fn(() => activeReader),
    openWorkspaceObjectConversation: vi.fn(async (object: { key: string }) => {
      state.activeThreadId = "dedicated-" + object.key.slice("ai-context:".length);
    }),
    setInteractionContext: vi.fn(),
    setActiveDocument: vi.fn(),
    setReaderContextSelection: vi.fn(),
    send: vi.fn(async () => undefined),
    isSignedIn: vi.fn(() => true),
    stop: vi.fn(),
  };
  plugin.ensureChatSession = vi.fn(async () => { state.connected = true; });
  plugin.conversationPapers = {
    list: vi.fn((_threadID: string) => input.secondary ?? []),
  };
  plugin.aiContexts = {
    save: input.saveError
      ? vi.fn(async () => { throw input.saveError; })
      : vi.fn(async () => ({
          document: documentFixture("ctx-1"),
          projection: emptyProjection(),
        })),
    open: vi.fn(async () => documentFixture("ctx-1")),
    pendingRepairs: vi.fn(async () => input.pendingRepairs ?? []),
    repair: vi.fn(async () => emptyProjection()),
  };
  plugin.aiContextRuntime = { canonical: vi.fn((path: string) => path) };
  plugin.generator = { generate: vi.fn(async () => JSON.stringify({})) };
  plugin.aiContextHost = {
    preflight: vi.fn(async () => undefined),
    compareAndSwap: vi.fn(async () => true),
    project: vi.fn(async () => emptyProjection()),
    projectionStatus: vi.fn(async () => emptyProjection()),
  };
  plugin.openWorkbenchTab = vi.fn(async () => undefined);
  plugin.selectedWorkbenchEntry = vi.fn(() => ({ view: {} }));
  plugin.openQmdDocument = vi.fn(async () => true);
  plugin.renderChatViews = vi.fn();
  plugin.chooseQLabRoot = vi.fn(async () => null);
  if (input.stubActivation !== false) {
    plugin.activateAIContext = vi.fn(async (contextDocument: AIContextDocument) => {
      plugin.activeAIContextPath = contextDocument.relativePath;
      plugin.activeAIContext = contextDocument;
      plugin.activeAIContextThreadId = state.activeThreadId;
      plugin.activeAIContextRoot = plugin.settings.qlabRoot;
    });
  }
  return { plugin, debug };
}

function expectNoPublishedAIContext(plugin: any): void {
  const interaction = plugin.codex.setInteractionContext.mock.calls.at(-1)![0];
  expect(interaction).not.toHaveProperty("AI Context record");
  expect(interaction).not.toHaveProperty("AI Context memory and plan");
}

async function settleWorkspace(): Promise<void> {
  for (let index = 0; index < 4; index += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

async function mountAIContextEditWorkspace(id: string) {
  const contextDocument = documentFixture(id);
  const { plugin } = aiContextPluginHarness({
    resolvedDocument: contextDocument,
    stubActivation: false,
  });
  const host = document.createElement("div");
  document.body.appendChild(host);
  let workspace: any;
  const sidebar = {
    openEditorTab: () => {
      workspace ??= plugin.createWorkspaceView(host);
      workspace.show();
      return workspace;
    },
    workspace: () => workspace ?? null,
  };
  vi.stubGlobal("PathUtils", {
    join: (...parts: string[]) => parts.join("/").replace(/\/+/gu, "/"),
  });
  vi.stubGlobal("Components", {
    interfaces: { nsIFile: {} },
    classes: {
      "@mozilla.org/file/local;1": {
        createInstance: () => {
          let path = "";
          return {
            initWithPath(value: string) { path = value; },
            exists: () => true,
            isSymlink: () => false,
            isDirectory: () => !path.endsWith(".qmd"),
            normalize: () => {},
            get path() { return path; },
          };
        },
      },
    },
  });
  vi.stubGlobal("IOUtils", {
    getChildren: vi.fn(async () => []),
    stat: vi.fn(),
  });
  plugin.selectedWorkbenchEntry.mockReturnValue({ view: sidebar });
  delete plugin.openQmdDocument;
  plugin.qmdRender = {
    open: vi.fn(async () => "http://127.0.0.1:44100/ai-context.html"),
    stop: vi.fn(),
    diagnostic: vi.fn(() => null),
    checkDraft: vi.fn(async () => ({ ok: true, diagnostics: [] })),
  };
  plugin.qmdChangeRender = {
    open: vi.fn(async () => "http://127.0.0.1:44200/ai-context.html"),
    stop: vi.fn(),
    diagnostic: vi.fn(() => null),
  };
  plugin.availableEditors = vi.fn(async () => []);
  plugin.pendingQmdChanges = vi.fn(async () => new Set());
  plugin.reviewDraftForKnowledge = vi.fn(async () => undefined);
  plugin.keepQmdChange = vi.fn(async () => undefined);
  plugin.readQmdSource = vi.fn(async () => ({
    source: "# Draft\n\n[todo: complete this passage]\n",
    revision: "private-copy-r1",
  }));
  plugin.saveQmdSource = vi.fn(async (_path: string, _revision: string, source: string) => ({
    source,
    revision: "private-copy-restored",
  }));
  const changePath = `work/qlab-zotero/draft-changes/${"a".repeat(64)}/draft.qmd`;
  plugin.qmdChangePaths = vi.fn(() => ({
    changePath,
    previewPath: contextDocument.relativePath.replace(/\.qmd$/u, ".preview.qmd"),
    manifestPath: "/profile/draft-changes/ai-context-edit.json",
  }));
  plugin.prepareQmdChange = vi.fn(async () => ({
    changePath,
    previewPath: contextDocument.relativePath.replace(/\.qmd$/u, ".preview.qmd"),
    changed: false,
    revision: "private-copy-r1",
  }));
  plugin.refreshQmdChangePreview = vi.fn(async () => undefined);

  await plugin.activateAIContext(contextDocument, window);
  await settleWorkspace();

  return {
    plugin,
    contextDocument,
    changePath,
    host,
    workspace,
    editButton: host.querySelector<HTMLButtonElement>(".zc-qmd-enable-ai-editing")!,
    status: host.querySelector<HTMLElement>(".zc-qmd-status")!,
  };
}

describe("AI Context plugin integration", () => {
  it("derives captured IDs from fixture messages", () => {
    const document = documentFixture("captured", "conversation", {
      messages: [
        { id: "u1", role: "user", text: "question" },
        { id: "a1", role: "assistant", text: "answer" },
      ],
    });
    expect(document.manifest.capturedEntryIds).toEqual(["u1", "a1"]);
  });

  it("orders reading normalization and preflight before connection, login, and save", async () => {
    const events: string[] = [];
    const normalized = [{ libraryID: "1", itemKey: "P1", title: "Title P1" }];
    const { plugin } = aiContextPluginHarness({
      connected: false,
      selected: [paperItem("P1")],
      normalizedPapers: normalized,
    });
    normalizeTargetsMock.mockImplementation(async () => { events.push("normalize"); return normalized; });
    plugin.aiContextHost.preflight.mockImplementation(async () => { events.push("preflight"); });
    plugin.ensureChatSession.mockImplementation(async () => { events.push("connect"); plugin.codex.state.connected = true; });
    plugin.codex.isSignedIn.mockImplementation(() => { events.push("login"); return true; });
    plugin.aiContexts.save.mockImplementation(async () => {
      events.push("save");
      return { document: documentFixture("reading-1", "reading"), projection: emptyProjection() };
    });

    await plugin.createReadingContext(window);

    expect(events).toEqual(["normalize", "preflight", "connect", "login", "save"]);
  });

  it.each([
    ["zero items", [], new Error("Select 1 to 50 local-library regular items")],
    ["51 items", Array.from({ length: 51 }, (_, index) => paperItem("P" + index)), new Error("Select 1 to 50 local-library regular items")],
    ["group library", [paperItem("P1", 2)], new Error("Only the local user library is supported")],
    ["non-regular item", [{ ...paperItem("P1"), isRegularItem: () => false }], new Error("Select regular Zotero items")],
  ])("stops on %s normalization before connection or persistence", async (_label, selected, error) => {
    const { plugin } = aiContextPluginHarness({
      connected: false,
      selected,
      normalizeError: error,
    });
    await expect(plugin.createReadingContext(window)).rejects.toThrow(error.message);
    expect(normalizeTargetsMock).toHaveBeenCalledOnce();
    expect(plugin.aiContextHost.preflight).not.toHaveBeenCalled();
    expect(plugin.ensureChatSession).not.toHaveBeenCalled();
    expect(plugin.codex.isSignedIn).not.toHaveBeenCalled();
    expect(plugin.aiContexts.save).not.toHaveBeenCalled();
    expect(plugin.generator.generate).not.toHaveBeenCalled();
  });

  it("routes only text === 'create a reading context' and delegates variants unchanged", async () => {
    expect(isCreateReadingContextCommand("create a reading context")).toBe(true);
    const variants = [
      " create a reading context",
      "create a reading context ",
      "Create a reading context",
      "please create a reading context",
      "create a reading context now",
    ];
    for (const text of variants) expect(isCreateReadingContextCommand(text)).toBe(false);

    const exact = aiContextPluginHarness({
      selected: [paperItem("P1")],
      normalizedPapers: [{ libraryID: "1", itemKey: "P1", title: "Title P1" }],
    }).plugin;
    await exact.sendChat("create a reading context");
    expect(exact.codex.send).not.toHaveBeenCalled();

    for (const text of variants) {
      const delegated = aiContextPluginHarness().plugin;
      await delegated.sendChat(text);
      expect(delegated.codex.send).toHaveBeenCalledWith(
        text, expect.anything(), expect.anything(), expect.any(Array), expect.any(Object),
      );
    }
  });

  it.each([
    ["reading", (plugin: any) => plugin.createReadingContext(window)],
    ["standalone", (plugin: any) => plugin.createStandaloneAIContext(window)],
    ["open", (plugin: any) => plugin.openAIContextAttachment({ key: "A1" }, window)],
    ["repair", (plugin: any) => plugin.repairAIContextAttachments(window)],
  ])("cancels root choice before %s can read or write state", async (_label, run) => {
    const { plugin } = aiContextPluginHarness({
      entries: [userEntry("u1", "question"), assistantEntry("a1", "answer")],
    });
    plugin.settings.qlabRoot = "";
    await run(plugin);
    expect(plugin.aiContexts.save).not.toHaveBeenCalled();
    expect(plugin.aiContexts.open).not.toHaveBeenCalled();
    expect(plugin.aiContexts.repair).not.toHaveBeenCalled();
    expect(resolveAttachmentMock).not.toHaveBeenCalled();
    expect(plugin.generator.generate).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.preflight).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.compareAndSwap).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.project).not.toHaveBeenCalled();
  });

  it("creates a standalone linked projection from the visible live transcript", async () => {
    const { plugin } = aiContextPluginHarness({
      entries: [userEntry("u1", "question"), assistantEntry("a1", "answer")],
    });
    await plugin.createStandaloneAIContext(window);
    expect(plugin.aiContexts.save).toHaveBeenCalledWith(expect.objectContaining({
      kind: "conversation",
      contextKey: null,
      sourceThreadId: "thread-1",
      papers: [],
      projection: { mode: "standalone", targets: [] },
    }));
  });

  it("rejects the Tools standalone command during a running turn without saving", async () => {
    const { plugin } = aiContextPluginHarness({
      entries: [assistantEntry("old-a", "completed before the current turn")],
    });
    plugin.codex.state.running = true;
    plugin.reportError = vi.fn();
    let command: () => void = () => { throw new Error("command was not bound"); };
    const item = {
      id: "",
      setAttribute: vi.fn(),
      addEventListener: vi.fn((name: string, callback: () => void) => {
        if (name === "command") command = callback;
      }),
    };
    const popup = {
      ownerDocument: { createXULElement: vi.fn(() => item) },
      append: vi.fn(),
    };
    plugin.appendAIContextMenuItem(
      popup,
      "qlab-zotero-create-standalone-ai-context",
      "Create Standalone AI Context",
      () => plugin.createStandaloneAIContext(window),
    );

    command();
    await vi.waitFor(() => expect(plugin.reportError).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringMatching(/current response/i) }),
    ));
    expect(plugin.aiContexts.save).not.toHaveBeenCalled();
    expect(plugin.generator.generate).not.toHaveBeenCalled();
  });

  it("publishes active fields atomically after QMD open and binds the dedicated thread", async () => {
    const contextDocument = documentFixture("atomic-1");
    const { plugin } = aiContextPluginHarness({ stubActivation: false });
    plugin.openQmdDocument.mockImplementation(async () => {
      expect(plugin.activeAIContextPath).toBeNull();
      expect(plugin.activeAIContextThreadId).toBeNull();
      expect(plugin.activeAIContextRoot).toBeNull();
      return true;
    });

    await plugin.activateAIContext(contextDocument, window);

    expect(plugin.activeAIContextPath).toBe(contextDocument.relativePath);
    expect(plugin.activeAIContext).toBe(contextDocument);
    expect(plugin.activeAIContextThreadId).toBe("dedicated-atomic-1");
    expect(plugin.activeAIContextRoot).toBe("/repo");
  });

  it("starts one dedicated edit turn from the real on-demand workspace with only its private directory writable", async () => {
    const mounted = await mountAIContextEditWorkspace("edit-turn");
    const { plugin, contextDocument, changePath, workspace, editButton, host } = mounted;

    expect((workspace as any).options.onEditWithAI).toEqual(expect.any(Function));
    expect(editButton.hidden).toBe(false);
    editButton.click();
    await settleWorkspace();

    expect(plugin.codex.send).toHaveBeenCalledOnce();
    const [instruction, model, effort, screenshots, options] = plugin.codex.send.mock.calls[0]!;
    expect(model).toBe("test-model");
    expect(effort).toBe("medium");
    expect(screenshots).toEqual([]);
    expect(options).toEqual({
      expectedThreadId: "dedicated-edit-turn",
      writableRoots: [`/repo/${changePath.split("/").slice(0, -1).join("/")}`],
      transientContext: {
        "Complete TODOs Action": {
          kind: "application",
          value: expect.any(String),
        },
      },
    });
    expect(instruction).toBe("Complete all [todo: ...] placeholders in the current Draft.");
    const actionContext = options.transientContext["Complete TODOs Action"].value;
    const normalizedInstruction = String(actionContext).replace(/\s+/gu, " ").toLowerCase();
    for (const rule of [
      "action: complete-todos",
      "mode: todo-only",
      "use skills/complete-gaps/skill.md as the authoritative workflow",
      "find every literal [todo: ...] placeholder",
      "replace only each exact placeholder span",
      "preserve every byte outside the placeholder spans",
      "use the full current dedicated conversation",
      "write only the private working-copy path supplied in qmd editor context",
      "do not edit the original draft, trusted knowledge, literature, or any other file",
      "leave that exact placeholder unchanged",
      "do not ask for another approval",
      "publish concise commentary progress",
      "never expose hidden chain-of-thought",
    ]) {
      expect(normalizedInstruction).toContain(rule);
    }
    expect(plugin.codex.setActiveDocument).toHaveBeenLastCalledWith({
      relativePath: contextDocument.relativePath,
      editablePath: changePath,
    });
    expect(plugin.aiContexts.save).not.toHaveBeenCalled();
    expect(plugin.generator.generate).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.compareAndSwap).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.project).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.projectionStatus).not.toHaveBeenCalled();
    expect(plugin.aiContexts.repair).not.toHaveBeenCalled();
    expect(plugin.reviewDraftForKnowledge).not.toHaveBeenCalled();
    expect(plugin.keepQmdChange).not.toHaveBeenCalled();
    expect(plugin.saveQmdSource).not.toHaveBeenCalled();

    workspace.destroy();
    host.remove();
  });

  it("feeds a TODO guard failure back to the Agent as hidden turn context", async () => {
    const { plugin, contextDocument, changePath, workspace, host } =
      await mountAIContextEditWorkspace("guard-retry");
    const reason = "Content outside a [todo: ...] placeholder changed";

    await (workspace as any).options.onTodoGuardRejected(
      contextDocument.relativePath,
      changePath,
      reason,
    );

    expect(plugin.codex.send).toHaveBeenCalledOnce();
    const [instruction, _model, _effort, _screenshots, options] = plugin.codex.send.mock.calls[0]!;
    expect(instruction).toBe("Continue completing TODOs from the restored private working copy.");
    expect(String(instruction)).not.toContain(reason);
    expect(options).toEqual({
      expectedThreadId: "dedicated-guard-retry",
      writableRoots: [`/repo/${changePath.split("/").slice(0, -1).join("/")}`],
      transientContext: {
        "TODO-only host guard": {
          kind: "application",
          value: expect.stringContaining(reason),
        },
      },
    });

    workspace.destroy();
    host.remove();
  });

  it.each([
    ["active path", (plugin: any) => { plugin.activeAIContextPath = "drafts/ai-contexts/other.qmd"; }],
    ["canonical repository root", (plugin: any) => { plugin.activeAIContextRoot = "/other-repo"; }],
    ["dedicated thread", (plugin: any) => { plugin.codex.state.activeThreadId = "another-thread"; }],
  ])("refuses the toolbar edit after the %s no longer matches", async (_label, drift) => {
    const { plugin, workspace, editButton, status, host } = await mountAIContextEditWorkspace("authority-turn");
    drift(plugin);

    editButton.click();
    await settleWorkspace();

    expect(plugin.codex.send).not.toHaveBeenCalled();
    expect(status.textContent).toMatch(/active AI Context|dedicated AI Context|repository/i);
    expect(editButton.disabled).toBe(false);
    workspace.destroy();
    host.remove();
  });

  it("refuses a private working-copy path that does not belong to the opened AI Context", async () => {
    const { plugin, workspace, editButton, status, host } = await mountAIContextEditWorkspace("copy-turn");
    plugin.prepareQmdChange.mockResolvedValue({
      changePath: `work/qlab-zotero/draft-changes/${"b".repeat(64)}/draft.qmd`,
      previewPath: "drafts/ai-contexts/copy-turn.preview.qmd",
      changed: false,
      revision: "wrong-private-copy",
    });

    editButton.click();
    await settleWorkspace();

    expect(plugin.codex.send).not.toHaveBeenCalled();
    expect(status.textContent).toMatch(/private AI Context working copy/i);
    expect(editButton.disabled).toBe(false);
    workspace.destroy();
    host.remove();
  });

  it.each([
    ["disconnected", (plugin: any) => { plugin.codex.state.connected = false; }],
    ["signed out", (plugin: any) => { plugin.codex.isSignedIn.mockReturnValue(false); }],
    ["already running", (plugin: any) => { plugin.codex.state.running = true; }],
  ])("refuses the toolbar edit while Codex is %s", async (_label, block) => {
    const { plugin, workspace, editButton, status, host } = await mountAIContextEditWorkspace("connection-turn");
    block(plugin);

    editButton.click();
    await settleWorkspace();

    expect(plugin.codex.send).not.toHaveBeenCalled();
    expect(status.textContent).toMatch(/connect|sign in|current response/i);
    expect(editButton.disabled).toBe(false);
    workspace.destroy();
    host.remove();
  });

  it("surfaces a rejected dedicated turn and lets the workspace button retry", async () => {
    const { plugin, workspace, editButton, status, host } = await mountAIContextEditWorkspace("retry-turn");
    plugin.codex.send
      .mockRejectedValueOnce(new Error("private edit turn rejected"))
      .mockResolvedValueOnce(undefined);

    editButton.click();
    await settleWorkspace();
    expect(status.textContent).toContain("private edit turn rejected");
    expect(editButton.disabled).toBe(false);

    editButton.click();
    await settleWorkspace();
    expect(plugin.codex.send).toHaveBeenCalledTimes(2);
    workspace.destroy();
    host.remove();
  });

  it("clears A authority before a failed A-to-B activation", async () => {
    const first = documentFixture("context-a");
    const second = documentFixture("context-b");
    const { plugin } = aiContextPluginHarness({ stubActivation: false });
    await plugin.activateAIContext(first, window);
    expect(plugin.activeAIContextPath).toBe(first.relativePath);

    plugin.openQmdDocument.mockRejectedValueOnce(new Error("B QMD failed to open"));
    await expect(plugin.activateAIContext(second, window)).rejects.toThrow(/B QMD failed/);

    expect(plugin.activeAIContextPath).toBeNull();
    expect(plugin.activeAIContext).toBeNull();
    expect(plugin.activeAIContextThreadId).toBeNull();
    expect(plugin.activeAIContextRoot).toBeNull();
    expect(plugin.activatingAIContext).toBe(false);
    expectNoPublishedAIContext(plugin);
    expect(plugin.aiContexts.open).not.toHaveBeenCalled();
    expect(plugin.aiContexts.save).not.toHaveBeenCalled();
  });

  it("does not bind a new thread when the real QMD workspace cannot render the requested record", async () => {
    const first = documentFixture("workspace-a");
    const second = documentFixture("workspace-b");
    const { plugin } = aiContextPluginHarness({ stubActivation: false });
    const host = document.createElement("div");
    document.body.appendChild(host);
    let workspace: any;
    const sidebar = {
      openEditorTab: () => {
        workspace ??= plugin.createWorkspaceView(host);
        workspace.show();
        return workspace;
      },
      workspace: () => workspace ?? null,
    };
    plugin.selectedWorkbenchEntry.mockReturnValue({ view: sidebar });
    delete plugin.openQmdDocument;
    plugin.qmdRender = {
      open: vi.fn(async () => { throw new Error("render failed"); }),
      stop: vi.fn(),
      diagnostic: vi.fn(() => null),
      checkDraft: vi.fn(async () => ({ ok: true, diagnostics: [] })),
    };
    plugin.qmdChangeRender = { stop: vi.fn() };
    plugin.availableEditors = vi.fn(async () => []);
    plugin.prepareQmdChange = vi.fn(async () => ({
      changePath: "work/qlab-zotero/draft-changes/b.qmd",
      previewPath: "drafts/ai-contexts/workspace-b.preview.qmd",
      changed: false,
      revision: "r1",
    }));
    plugin.activeAIContextPath = first.relativePath;
    plugin.activeAIContext = first;
    plugin.activeAIContextThreadId = "thread-1";
    plugin.activeAIContextRoot = "/repo";

    await expect(plugin.activateAIContext(second, window)).rejects.toThrow(/QMD.*open/i);

    expect(plugin.codex.openWorkspaceObjectConversation).not.toHaveBeenCalled();
    expect(plugin.codex.setActiveDocument).toHaveBeenCalledWith(null);
    expect(plugin.activeAIContextPath).toBeNull();
    expect(plugin.activeAIContext).toBeNull();
    expect(plugin.activeAIContextThreadId).toBeNull();
    expect(plugin.activeAIContextRoot).toBeNull();
    workspace?.destroy();
    host.remove();
  });

  it("reopens a valid AI Context through a cached real QMD workspace without creating an Agent copy", async () => {
    const contextDocument = documentFixture("readonly-reopen", "conversation", {
      messages: [
        { id: "u1", role: "user", text: "What changed?" },
        { id: "a1", role: "assistant", text: "The model was updated." },
      ],
    });
    const { plugin } = aiContextPluginHarness({
      resolvedDocument: contextDocument,
      stubActivation: false,
    });
    const host = document.createElement("div");
    document.body.appendChild(host);
    let workspace: any;
    let workspaceBuilds = 0;
    const sidebar = {
      openEditorTab: () => {
        if (!workspace) {
          workspaceBuilds += 1;
          workspace = plugin.createWorkspaceView(host);
        }
        workspace.show();
        return workspace;
      },
      workspace: () => workspace ?? null,
    };
    const writeUTF8 = vi.fn(async () => undefined);
    const makeDirectory = vi.fn(async () => undefined);
    vi.stubGlobal("IOUtils", {
      getChildren: vi.fn(async () => []),
      stat: vi.fn(),
      writeUTF8,
      makeDirectory,
    });
    const prepareQmdChange = vi.fn(async () => ({
      changePath: "work/qlab-zotero/draft-changes/readonly/draft.qmd",
      previewPath: "drafts/ai-contexts/readonly-reopen.preview.qmd",
      changed: true,
      revision: "agent-copy-r1",
    }));
    const changeRender = {
      open: vi.fn(async () => "http://127.0.0.1:44200/readonly.html"),
      stop: vi.fn(),
      diagnostic: vi.fn(() => null),
    };
    plugin.selectedWorkbenchEntry.mockReturnValue({ view: sidebar });
    delete plugin.openQmdDocument;
    plugin.qmdRender = {
      open: vi.fn(async () => "http://127.0.0.1:44100/readonly.html"),
      stop: vi.fn(),
      diagnostic: vi.fn(() => null),
      checkDraft: vi.fn(async () => ({ ok: true, diagnostics: [] })),
    };
    plugin.qmdChangeRender = changeRender;
    plugin.availableEditors = vi.fn(async () => []);
    plugin.pendingQmdChanges = vi.fn(async () => new Set());
    plugin.prepareQmdChange = prepareQmdChange;
    plugin.refreshQmdChangePreview = vi.fn(async () => {});
    plugin.codex.getActiveDiffs.mockReturnValue([{
      turnId: "dedicated-readonly-turn",
      diff: "diff --git a/work/qlab-zotero/draft-changes/readonly/draft.qmd b/work/qlab-zotero/draft-changes/readonly/draft.qmd\n-old\n+new",
    }]);

    await plugin.openAIContextAttachment({ key: "A1" }, window);
    await settleWorkspace();
    await plugin.openAIContextAttachment({ key: "A1" }, window);
    await settleWorkspace();

    expect(workspaceBuilds).toBe(1);
    expect(plugin.qmdRender.open).toHaveBeenCalledTimes(2);
    expect(plugin.codex.getActiveDiffs).toHaveBeenCalledTimes(2);
    expect(prepareQmdChange).not.toHaveBeenCalled();
    expect(changeRender.open).not.toHaveBeenCalled();
    expect(writeUTF8).not.toHaveBeenCalled();
    expect(makeDirectory).not.toHaveBeenCalled();
    expect(plugin.codex.setActiveDocument).toHaveBeenLastCalledWith({
      relativePath: contextDocument.relativePath,
      editablePath: null,
    });
    expect(plugin.codex.openWorkspaceObjectConversation).toHaveBeenCalledTimes(2);
    expect(plugin.aiContexts.save).not.toHaveBeenCalled();
    expect(plugin.generator.generate).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.compareAndSwap).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.project).not.toHaveBeenCalled();
    workspace?.destroy();
    host.remove();
  });

  it("clears active update authority after switching to an ordinary paper thread", async () => {
    const contextDocument = documentFixture("bound-1");
    const { plugin } = aiContextPluginHarness({ stubActivation: false });
    await plugin.activateAIContext(contextDocument, window);
    plugin.codex.state.activeThreadId = "paper-thread";

    plugin.reconcileActiveAIContextThread();

    expect(plugin.activeAIContextPath).toBeNull();
    expect(plugin.activeAIContext).toBeNull();
    expect(plugin.activeAIContextThreadId).toBeNull();
    expect(plugin.activeAIContextRoot).toBeNull();
    expectNoPublishedAIContext(plugin);
  });

  it("clears and republishes interaction context when the visible QMD switches", async () => {
    const contextDocument = documentFixture("qmd-switch");
    const { plugin } = aiContextPluginHarness({ stubActivation: false });
    await plugin.activateAIContext(contextDocument, window);

    plugin.handleAIContextDocumentChange("drafts/another.qmd");

    expect(plugin.activeAIContextPath).toBeNull();
    expect(plugin.activeAIContext).toBeNull();
    expect(plugin.activeAIContextThreadId).toBeNull();
    expect(plugin.activeAIContextRoot).toBeNull();
    expectNoPublishedAIContext(plugin);
  });

  it("clears an old same-relative-path authority after choosing another root", async () => {
    const old = documentFixture("same-relative-path");
    const { plugin } = aiContextPluginHarness({ entries: [] });
    plugin.activeAIContextPath = old.relativePath;
    plugin.activeAIContext = old;
    plugin.activeAIContextThreadId = "thread-1";
    plugin.activeAIContextRoot = "/repo-a";
    plugin.settings.qlabRoot = "";
    plugin.chooseQLabRoot.mockResolvedValue("/repo-b");

    await plugin.requireAIContextRoot(window);

    expect(plugin.settings.qlabRoot).toBe("/repo-b");
    expect(plugin.activeAIContextPath).toBeNull();
    expect(plugin.activeAIContextRoot).toBeNull();
    expect(plugin.aiContexts.open).not.toHaveBeenCalled();
    expectNoPublishedAIContext(plugin);
    expect(plugin.codex.setInteractionContext.mock.calls.at(-1)![0]["QLab repository"].value)
      .toContain("/repo-b");
  });

  it("opens through the resolver with zero save, generator, CAS, or project calls", async () => {
    const contextDocument = documentFixture("open-1");
    const { plugin } = aiContextPluginHarness({
      resolvedDocument: contextDocument,
      stubActivation: false,
    });
    const item = { key: "A1" };
    await plugin.openAIContextAttachment(item, window);
    expect(resolveAttachmentMock).toHaveBeenCalledWith(plugin.aiContextRuntime, item);
    expect(plugin.codex.openWorkspaceObjectConversation).toHaveBeenCalledWith(
      expect.objectContaining({ key: "ai-context:open-1", title: contextDocument.title }),
    );
    expect(plugin.aiContexts.save).not.toHaveBeenCalled();
    expect(plugin.generator.generate).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.compareAndSwap).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.project).not.toHaveBeenCalled();
  });

  it("routes an installed candidate and diagnoses unsupported open interception", async () => {
    const supported = aiContextPluginHarness({
      resolvedDocument: documentFixture("handler-open"),
      stubActivation: false,
    });
    supported.plugin.installAIContextOpener();
    await installedOpenCallbacks!.openAIContext({ key: "A1" });
    expect(resolveAttachmentMock).toHaveBeenCalled();

    const unsupported = aiContextPluginHarness({ openSupported: false });
    unsupported.plugin.installAIContextOpener();
    expect(unsupported.debug).toHaveBeenCalledWith(
      expect.stringMatching(/FileHandlers\.open.*unsupported/i),
    );
    expect(AI_CONTEXT_MENU_IDS).toContain("qlab-zotero-open-ai-context");
  });

  it("deduplicates exact visible entries but preserves conflicting IDs for service resolution", () => {
    const { plugin } = aiContextPluginHarness({
      entries: [
        userEntry("u2", "same"), userEntry("u2", "same"),
        assistantEntry("a2", "one"), assistantEntry("a2", "two"),
      ],
    });
    expect(plugin.visibleAIContextMessages()).toEqual([
      { id: "u2", role: "user", text: "same" },
      { id: "a2", role: "assistant", text: "one" },
      { id: "a2", role: "assistant", text: "two" },
    ]);
  });

  it("injects bounded untrusted memory without raw transcript", async () => {
    const active = documentFixture("active-1", "reading", {
      memoryMarkdown: "m".repeat(40_000),
      messages: [{ id: "secret", role: "user", text: "RAW TRANSCRIPT SECRET" }],
    });
    const { plugin } = aiContextPluginHarness({ stubActivation: false, entries: [] });
    plugin.activeAIContextPath = active.relativePath;
    plugin.activeAIContext = active;
    plugin.activeAIContextThreadId = "thread-1";
    plugin.activeAIContextRoot = "/repo";
    plugin.updateInteractionContext();
    const interaction = plugin.codex.setInteractionContext.mock.calls.at(-1)![0];
    expect(interaction["AI Context record"]).toEqual({
      kind: "application",
      value: [
        "Repository root: /repo",
        "Draft path: drafts/ai-contexts/active-1.qmd",
        "Record ID: active-1",
        "Write rules: explicit Save/Update only; drafts is untrusted; never write knowledge",
      ].join("\n"),
    });
    expect(interaction["AI Context memory and plan"].value).toHaveLength(32_000);
    expect(interaction["AI Context memory and plan"].value).not.toContain(
      "RAW TRANSCRIPT SECRET",
    );
  });

  it("cancels a two-record repair chooser with zero mutations", async () => {
    const first = documentFixture("repair-1");
    const second = documentFixture("repair-2");
    const pending = [first, second].map((contextDocument) => ({
      document: contextDocument,
      status: {
        created: [], reused: [],
        missing: [{ mode: "attached" as const, libraryID: "1", itemKey: "P1" }],
      },
    }));
    const { plugin } = aiContextPluginHarness({ pendingRepairs: pending });
    plugin.choosePendingAIContext = vi.fn(() => null);
    await plugin.repairAIContextAttachments(window);
    expect(plugin.aiContexts.repair).not.toHaveBeenCalled();
    expect(plugin.aiContexts.open).not.toHaveBeenCalled();
    expect(plugin.aiContextHost.project).not.toHaveBeenCalled();
  });

  it("repairs, reopens, and activates the only pending record", async () => {
    const contextDocument = documentFixture("repair-one");
    const { plugin } = aiContextPluginHarness({
      pendingRepairs: [{
        document: contextDocument,
        status: {
          created: [], reused: [],
          missing: [{ mode: "attached", libraryID: "1", itemKey: "P1" }],
        },
      }],
    });
    plugin.aiContexts.open.mockResolvedValue(contextDocument);
    await plugin.repairAIContextAttachments(window);
    expect(plugin.aiContexts.repair).toHaveBeenCalledWith(contextDocument.relativePath);
    expect(plugin.aiContexts.open).toHaveBeenCalledWith(contextDocument.relativePath);
    expect(plugin.activateAIContext).toHaveBeenCalledWith(contextDocument, window);
  });

  it("disposes before Codex.stop and removes all four menus from every main window", async () => {
    const { plugin } = aiContextPluginHarness();
    const firstWindow = { name: "first" } as unknown as Window;
    const secondWindow = { name: "second" } as unknown as Window;
    vi.spyOn(Zotero, "getMainWindows").mockReturnValue([firstWindow, secondWindow]);
    const order: string[] = [];
    plugin.aiContextOpenHandler = {
      supported: true,
      dispose: vi.fn(() => order.push("dispose")),
    };
    plugin.codex.stop = vi.fn(() => order.push("codex-stop"));
    plugin.removeQLabMenu = vi.fn();
    plugin.removeWindowAssets = vi.fn();
    await plugin.shutdown();
    expect(order.indexOf("dispose")).toBeLessThan(order.indexOf("codex-stop"));
    expect(plugin.removeQLabMenu.mock.calls).toEqual([
      [firstWindow],
      [secondWindow],
    ]);
    expect(AI_CONTEXT_MENU_IDS).toEqual([
      "qlab-zotero-create-reading-context",
      "qlab-zotero-create-standalone-ai-context",
      "qlab-zotero-open-ai-context",
      "qlab-zotero-repair-ai-context",
    ]);
  });
});
