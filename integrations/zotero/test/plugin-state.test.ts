// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import * as pluginModule from "../src/plugin";

import {
  MAX_SELECTION_PROMPT_CHARACTERS,
  ZoteroChatPlugin,
  buildSelectionPrompt,
  clampFloatOpacity,
  clampFloatSize,
  draftChangeRebaseAction,
  formatPendingApprovalDescription,
  pdfDirectory,
  pdfSourceMatchesConversationPaper,
  pdfSourceMatchesReaderContext,
  prepareRepositoryTargetStartup,
} from "../src/plugin";
import type { ReaderContext } from "../src/reader-context";
import {
  capabilitiesFor,
  type LocalRepositoryInspection,
  type RepositoryTargetSnapshot,
  type ResolvedLocalRepositoryTarget,
  type StoredTargetPreferences,
} from "../src/repository-target";
const EMPTY_TARGET_PREFERENCES: StoredTargetPreferences = {
  version: 2,
  active: null,
  pendingCandidate: null,
  legacyUnassigned: [],
  migratedLegacy: false,
};

function startupTarget(
  root = "/legacy",
  overrides: Partial<ResolvedLocalRepositoryTarget> = {},
): ResolvedLocalRepositoryTarget {
  return {
    kind: "local" as const,
    root,
    canonicalRoot: root,
    repositoryId: "a".repeat(64),
    targetId: "b".repeat(64),
    ...overrides,
  };
}

function startupSnapshot(
  target: ResolvedLocalRepositoryTarget = startupTarget(),
  targetEpoch = 1,
): RepositoryTargetSnapshot {
  return { target, targetEpoch, capabilities: capabilitiesFor(target) };
}

function startupPreferences(
  active: ResolvedLocalRepositoryTarget | null,
  migratedLegacy = true,
): StoredTargetPreferences {
  return {
    ...EMPTY_TARGET_PREFERENCES,
    active,
    migratedLegacy,
  };
}

function startupSettings(repositoryTargets: StoredTargetPreferences) {
  return {
    libraryRoot: "/library",
    qlabRoot: "",
    repositoryTargets,
    defaultModel: "",
    reasoningEffort: "medium" as const,
    approvalPolicy: "never",
    terminalHeight: 420,
    showReasoning: false,
    storageRoot: "/profile",
  };
}

function targetStartupHarness(options: {
  preferences?: StoredTargetPreferences;
  rawLegacyRoot?: string;
  inspect?: (root: string, callIndex: number) => LocalRepositoryInspection | Promise<LocalRepositoryInspection>;
  sessionFailure?: Error | null;
  preferenceFailure?: Error | null;
} = {}) {
  const calls: string[] = [];
  let preferences: StoredTargetPreferences = options.preferences ?? EMPTY_TARGET_PREFERENCES;
  let records = [{
    threadId: "legacy-thread",
    title: "Legacy",
    workspace: "/legacy/drafts",
    recordedCwd: "/legacy/drafts",
    updatedAt: "2026-07-31",
    extensionField: { keep: true },
  }];
  let inspectCallIndex = 0;
  let preferenceFailure = options.preferenceFailure ?? null;
  const inspect = vi.fn(async (root: string) => {
    calls.push(`inspect:${root}`);
    const callIndex = inspectCallIndex++;
    return options.inspect
      ? options.inspect(root, callIndex)
      : startupTarget(root);
  });
  const deps = {
    readRawTargetMigrationInput: () => {
      calls.push("raw");
      return {
        legacyQLabRoot: options.rawLegacyRoot ?? "/legacy",
        repositoryTargetsRaw: JSON.stringify(preferences),
      };
    },
    readSessionRecords: async () => {
      calls.push("sessions");
      if (options.sessionFailure) throw options.sessionFailure;
      return {
        file: { version: 1 as const, papers: {} },
        locations: records.map((_record, index) => ({ kind: "history" as const, paperKey: "paper", index })),
        records: structuredClone(records),
        activeThreadId: null,
      };
    },
    loadSettings: async () => {
      calls.push("settings");
      return startupSettings(preferences);
    },
    createResolver: () => {
      calls.push("resolver");
      return {
        inspect,
        canonicalize: vi.fn(async (path: string) => path),
      };
    },
    saveSessionRecords: async (_snapshot: unknown, next: readonly (typeof records)[number][]) => {
      calls.push("saveSessionRecords");
      records = structuredClone([...next]);
    },
    saveRepositoryTargets: (next: StoredTargetPreferences) => {
      calls.push("saveRepositoryTargets");
      if (preferenceFailure) throw preferenceFailure;
      preferences = structuredClone(next);
    },
    publish: (snapshot: RepositoryTargetSnapshot) => {
      calls.push("publish");
      published.push(snapshot);
      return undefined;
    },
  };
  const published: RepositoryTargetSnapshot[] = [];
  const factorySnapshots: Array<RepositoryTargetSnapshot | null> = [];
  const construct = async () => {
    const start = (pluginModule as Record<string, unknown>)
      .startRepositoryTargetBoundServices;
    if (typeof start !== "function") {
      throw new Error("Production repository-target startup factory is missing");
    }
    return (start as Function)(deps, async () => {
      calls.push("factory");
      return {
        createMainSite: (snapshot: RepositoryTargetSnapshot | null) => {
          calls.push("mainSite");
          factorySnapshots.push(snapshot);
          return { kind: "mainSite" };
        },
        createTerminal: (snapshot: RepositoryTargetSnapshot | null) => {
          calls.push("terminal");
          factorySnapshots.push(snapshot);
          return { kind: "terminal" };
        },
        createCodex: (snapshot: RepositoryTargetSnapshot | null) => {
          calls.push("codex");
          factorySnapshots.push(snapshot);
          return { kind: "codex", snapshot };
        },
      };
    });
  };
  return {
    calls,
    deps,
    inspect,
    published,
    factorySnapshots,
    construct,
    records: () => structuredClone(records),
    preferences: () => structuredClone(preferences),
    clearCalls: () => { calls.length = 0; },
    setPreferenceFailure: (error: Error | null) => { preferenceFailure = error; },
  };
}

describe("repository target startup", () => {
  it("freshly resolves a migrated target before publishing it", async () => {
    const h = targetStartupHarness();

    const prepared = await prepareRepositoryTargetStartup(h.deps);

    expect(h.calls).toEqual([
      "raw",
      "sessions",
      "settings",
      "resolver",
      "inspect:/legacy",
      "saveSessionRecords",
      "saveRepositoryTargets",
      "inspect:/legacy",
      "publish",
    ]);
    expect(prepared.activeSnapshot).toEqual(startupSnapshot());
    expect(prepared.settings.repositoryTargets.migratedLegacy).toBe(true);
    expect(h.records()[0]).toMatchObject({
      threadId: "legacy-thread",
      targetId: "b".repeat(64),
      extensionField: { keep: true },
    });

    h.clearCalls();
    const persisted = { preferences: h.preferences(), records: h.records() };
    await prepareRepositoryTargetStartup(h.deps);
    expect(h.calls).toEqual([
      "raw", "sessions", "settings", "resolver", "inspect:/legacy", "publish",
    ]);
    expect(h.inspect).toHaveBeenCalledTimes(3);
    expect({ preferences: h.preferences(), records: h.records() }).toEqual(persisted);
  });

  it("publishes a newly chosen ready repository into Codex and persisted settings", async () => {
    const originalServices = (globalThis as any).Services;
    const setStringPref = vi.fn();
    (globalThis as any).Services = { prefs: { setStringPref } };
    const plugin = new ZoteroChatPlugin() as any;
    const target = startupTarget("/chosen");
    const staged = { snapshot: null, binding: null, activeDocument: null };
    plugin.settings = startupSettings(EMPTY_TARGET_PREFERENCES);
    plugin.codex = {
      repositoryTargetBlockers: vi.fn(() => []),
      stageRepositoryTarget: vi.fn(async () => staged),
      commitRepositoryTarget: vi.fn(),
      disposeStagedRepositoryTarget: vi.fn(async () => {}),
    };
    plugin.repositoryTargetResolver = { inspect: vi.fn(async () => target) };
    plugin.updateInteractionContext = vi.fn();
    plugin.renderChatViews = vi.fn();
    plugin.repositoryTargetController = plugin.createRepositoryTargetController(null);

    try {
      await expect(plugin.activateRepositoryTarget("/chosen")).resolves.toBe("/chosen");
      expect(plugin.codex.stageRepositoryTarget).toHaveBeenCalledWith(
        startupSnapshot(target),
        expect.any(AbortSignal),
      );
      expect(plugin.codex.commitRepositoryTarget).toHaveBeenCalledWith(staged);
      expect(plugin.settings.qlabRoot).toBe("/chosen");
      expect(plugin.settings.repositoryTargets.active).toEqual(target);
      expect(plugin.activeRepositoryTarget).toEqual(startupSnapshot(target));
      expect(setStringPref).toHaveBeenCalledWith(
        "extensions.zotkit.qlabRoot",
        "/chosen",
      );
      expect(setStringPref).toHaveBeenCalledWith(
        "extensions.zotkit.repositoryTargets",
        expect.stringContaining(`\"targetId\":\"${target.targetId}\"`),
      );
    }
    finally {
      (globalThis as any).Services = originalServices;
    }
  });

  it("retries a failed preference save with byte-stable migrated record fields", async () => {
    const diskFull = new Error("disk full");
    const h = targetStartupHarness({ preferenceFailure: diskFull });

    await expect(prepareRepositoryTargetStartup(h.deps)).rejects.toBe(diskFull);
    expect(h.calls).toEqual([
      "raw", "sessions", "settings", "resolver", "inspect:/legacy",
      "saveSessionRecords", "saveRepositoryTargets",
    ]);
    expect(h.preferences().migratedLegacy).toBe(false);
    const firstSavedRecords = h.records();
    expect(firstSavedRecords[0]).toMatchObject({
      targetId: "b".repeat(64),
      extensionField: { keep: true },
    });

    h.clearCalls();
    h.setPreferenceFailure(null);
    await prepareRepositoryTargetStartup(h.deps);
    expect(h.calls).toEqual([
      "raw", "sessions", "settings", "resolver", "inspect:/legacy", "saveSessionRecords",
      "saveRepositoryTargets", "inspect:/legacy", "publish",
    ]);
    expect(h.records()).toEqual(firstSavedRecords);
    expect(h.preferences().migratedLegacy).toBe(true);
  });

  it("uses a raw missing root even though display-safe settings contain no qlab root", async () => {
    const h = targetStartupHarness({
      inspect: () => ({ kind: "unavailable", reason: "missing" }),
    });

    const prepared = await prepareRepositoryTargetStartup(h.deps);

    expect(h.inspect).toHaveBeenCalledWith("/legacy");
    expect(prepared.settings.qlabRoot).toBe("");
    expect(prepared.settings.repositoryTargets).toMatchObject({
      active: null,
      pendingCandidate: null,
      legacyUnassigned: [{ threadId: "legacy-thread", reason: "missing" }],
      migratedLegacy: true,
    });
    expect(h.calls.at(-1)).toBe("saveRepositoryTargets");
    expect(h.calls).not.toContain("publish");
  });

  it("freshly resolves an already-migrated active target before publishing", async () => {
    const active = startupTarget();
    const h = targetStartupHarness({ preferences: startupPreferences(active) });

    const started = await h.construct();

    expect(h.calls).toEqual([
      "raw", "sessions", "settings", "resolver", "inspect:/legacy", "publish",
      "factory", "mainSite", "terminal", "codex",
    ]);
    expect(started.prepared.activeSnapshot).toEqual(startupSnapshot(active));
    expect(started.codex.snapshot).toBe(h.published[0]);
    expect(h.published).toEqual([startupSnapshot(active)]);
  });

  it("keeps targetless startup targetless without consulting a resolver", async () => {
    const h = targetStartupHarness({
      preferences: startupPreferences(null),
      rawLegacyRoot: "",
    });

    const prepared = await prepareRepositoryTargetStartup(h.deps);

    expect(prepared.activeSnapshot).toBeNull();
    expect(h.calls).toEqual(["raw", "sessions", "settings"]);
    expect(h.inspect).not.toHaveBeenCalled();
    expect(h.published).toEqual([]);
  });

  it("recovers a previously selected repository after transient identity failure", async () => {
    const legacyUnassigned = [{
      threadId: "legacy-thread",
      recordedCwd: null,
      reason: "identity-unavailable" as const,
    }];
    const h = targetStartupHarness({
      preferences: {
        ...startupPreferences(null),
        legacyUnassigned,
      },
      rawLegacyRoot: "/chosen",
      inspect: (root) => startupTarget(root),
    });

    const prepared = await prepareRepositoryTargetStartup(h.deps);

    expect(h.calls).toEqual([
      "raw", "sessions", "settings", "resolver", "inspect:/chosen",
      "saveRepositoryTargets", "inspect:/chosen", "publish",
    ]);
    expect(prepared.activeSnapshot).toEqual(startupSnapshot(startupTarget("/chosen")));
    expect(prepared.settings.qlabRoot).toBe("/chosen");
    expect(prepared.settings.repositoryTargets).toMatchObject({
      active: startupTarget("/chosen"),
      pendingCandidate: null,
      legacyUnassigned,
      migratedLegacy: true,
    });
    expect(h.calls).not.toContain("saveSessionRecords");
  });

  it("does not replace an explicit pending repository candidate during recovery", async () => {
    const h = targetStartupHarness({
      preferences: {
        ...startupPreferences(null),
        pendingCandidate: {
          kind: "candidate",
          canonicalRoot: "/empty",
          state: "empty",
          eligibleLegacyThreads: [],
        },
      },
      rawLegacyRoot: "/empty",
    });

    const prepared = await prepareRepositoryTargetStartup(h.deps);

    expect(prepared.activeSnapshot).toBeNull();
    expect(prepared.settings.repositoryTargets.pendingCandidate?.canonicalRoot).toBe("/empty");
    expect(h.calls).toEqual(["raw", "sessions", "settings"]);
    expect(h.inspect).not.toHaveBeenCalled();
  });

  it.each([
    ["non-local inspection", { kind: "candidate", canonicalRoot: "/legacy", state: "partial" }],
    ["unavailable inspection", { kind: "unavailable", reason: "missing" }],
    ["root mismatch", startupTarget("/legacy", { root: "/different-spelling" })],
    ["canonical-root mismatch", startupTarget("/legacy", { canonicalRoot: "/replacement" })],
    ["repository identity mismatch", startupTarget("/legacy", { repositoryId: "c".repeat(64) })],
    ["target identity mismatch", startupTarget("/legacy", { targetId: "d".repeat(64) })],
  ] as const)("rejects a stored active target on %s before publication", async (_name, inspection) => {
    const h = targetStartupHarness({
      preferences: startupPreferences(startupTarget()),
      inspect: () => inspection as LocalRepositoryInspection,
    });

    await expect(prepareRepositoryTargetStartup(h.deps))
      .rejects.toThrow("Stored active repository no longer matches its persisted identity");
    expect(h.published).toEqual([]);
  });

  it("rejects a repository replacement at the same path before constructing target services", async () => {
    const replacement = startupTarget("/legacy", {
      repositoryId: "c".repeat(64),
      targetId: "d".repeat(64),
    });
    const h = targetStartupHarness({
      preferences: startupPreferences(startupTarget()),
      inspect: () => replacement,
    });

    await expect(h.construct())
      .rejects.toThrow("Stored active repository no longer matches its persisted identity");
    expect(h.calls).not.toContain("publish");
    expect(h.calls).not.toContain("factory");
    expect(h.calls).not.toContain("codex");
  });

  it("uses the production gate for ordered target-service construction and exact Codex binding", async () => {
    const h = targetStartupHarness();

    const started = await h.construct();

    const snapshot = startupSnapshot();
    expect(h.calls).toEqual([
      "raw", "sessions", "settings", "resolver", "inspect:/legacy", "saveSessionRecords",
      "saveRepositoryTargets", "inspect:/legacy", "publish", "factory", "mainSite", "terminal", "codex",
    ]);
    expect(h.factorySnapshots).toEqual([snapshot, snapshot, snapshot]);
    expect(started.codex).toEqual({ kind: "codex", snapshot });
    expect(h.factorySnapshots.every((value) => value === h.published[0])).toBe(true);
    expect(started.codex.snapshot).toBe(h.published[0]);
  });

  it("constructs target-bound services with null only after a targetless startup is prepared", async () => {
    const h = targetStartupHarness({
      preferences: startupPreferences(null),
      rawLegacyRoot: "",
    });

    await h.construct();

    expect(h.calls).toEqual([
      "raw", "sessions", "settings", "factory", "mainSite", "terminal", "codex",
    ]);
    expect(h.factorySnapshots).toEqual([null, null, null]);
  });

  it.each([
    ["malformed sessions", { sessionFailure: new Error("malformed sessions") }],
    ["failed preference save", { preferenceFailure: new Error("disk full") }],
  ] as Array<[string, { sessionFailure?: Error; preferenceFailure?: Error }]>)
  ("does not construct services after %s", async (_name, options) => {
    const h = targetStartupHarness(options);

    await expect(h.construct()).rejects.toThrow(options.sessionFailure?.message ?? options.preferenceFailure?.message);
    expect(h.calls).not.toContain("publish");
    expect(h.calls).not.toContain("factory");
    expect(h.calls).not.toContain("mainSite");
    expect(h.calls).not.toContain("terminal");
    expect(h.calls).not.toContain("codex");
  });
});

describe("Zotkit Reader terminal state", () => {
  it("matches only PDF links that identify the conversation paper", () => {
    const context = {
      parent: { url: "https://arxiv.org/abs/2306.13123v2" },
      attachment: {},
    } as ReaderContext;

    expect(pdfSourceMatchesReaderContext(
      "https://arxiv.org/pdf/2306.13123v2.pdf#page=6",
      context,
    )).toBe(true);
    expect(pdfSourceMatchesReaderContext(
      "https://example.org/another-paper.pdf#page=6",
      context,
    )).toBe(false);
  });

  it("matches page links to an explicitly attached secondary paper", () => {
    expect(pdfSourceMatchesConversationPaper(
      "https://arxiv.org/pdf/2401.01234.pdf#page=9",
      { sourceUrls: ["https://arxiv.org/abs/2401.01234"], dois: [] },
    )).toBe(true);
    expect(pdfSourceMatchesConversationPaper(
      "https://example.org/unrelated.pdf#page=9",
      { sourceUrls: ["https://arxiv.org/abs/2401.01234"], dois: [] },
    )).toBe(false);
  });

  it("treats a Cursor save as the new Draft baseline without discarding a real AI version", () => {
    expect(draftChangeRebaseAction("old-original", "cursor-save", "ai-version"))
      .toBe("preserve-ai-version");
  });

  it("moves an untouched AI working copy forward when Cursor saves the original Draft", () => {
    expect(draftChangeRebaseAction("old-original", "cursor-save", "old-original"))
      .toBe("refresh-working-copy");
    expect(draftChangeRebaseAction("same", "same", "ai-version"))
      .toBe("already-current");
  });

  it("creates every legal Draft staging parent without rejecting intermediate work directories", async () => {
    const originalComponents = (globalThis as any).Components;
    const originalIOUtils = (globalThis as any).IOUtils;
    const originalPathUtils = (globalThis as any).PathUtils;
    const directories = new Set(["/repo"]);
    const makeDirectory = vi.fn(async (path: string) => {
      const parent = path.slice(0, path.lastIndexOf("/")) || "/";
      if (!directories.has(parent)) throw new Error(`missing parent ${parent}`);
      directories.add(path);
    });
    (globalThis as any).PathUtils = { join: (...parts: string[]) => parts.join("/").replace(/\/{2,}/g, "/") };
    (globalThis as any).IOUtils = {
      exists: async (path: string) => directories.has(path),
      makeDirectory,
    };
    (globalThis as any).Components = {
      interfaces: { nsIFile: {} },
      classes: {
        "@mozilla.org/file/local;1": {
          createInstance: () => {
            let path = "";
            return {
              initWithPath(value: string) { path = value; },
              exists: () => directories.has(path),
              isSymlink: () => false,
              isDirectory: () => directories.has(path),
              normalize: () => {},
              get path() { return path; },
            };
          },
        },
      },
    };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.settings = { qlabRoot: "/repo" };

    try {
      await plugin.ensureSafeChangeDirectory(
        `work/qlab-zotero/draft-changes/${"a".repeat(64)}`,
      );
      expect([...directories]).toEqual([
        "/repo",
        "/repo/work",
        "/repo/work/qlab-zotero",
        "/repo/work/qlab-zotero/draft-changes",
        `/repo/work/qlab-zotero/draft-changes/${"a".repeat(64)}`,
      ]);
      expect(makeDirectory).toHaveBeenCalledTimes(4);
    }
    finally {
      (globalThis as any).Components = originalComponents;
      (globalThis as any).IOUtils = originalIOUtils;
      (globalThis as any).PathUtils = originalPathUtils;
    }
  });

  it("toggles the current-paper and current-page chips and the model context together", () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = {
      attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
      parent: { title: "Paper", creators: [], tags: [] },
      page: { pageNumber: 5, pageLabel: "5" },
    };
    plugin.codex = {
      setReaderContextSelection: vi.fn(),
      setInteractionContext: vi.fn(),
    };
    plugin.renderChatViews = vi.fn();

    plugin.removeInteractionContext("active-paper");
    expect(plugin.contextChips().map((chip: { id: string }) => chip.id)).toEqual(["current-page"]);
    expect(plugin.contextSuggestions().find((item: { id: string }) => item.id === "active-paper").disabled).toBe(false);
    expect(plugin.codex.setReaderContextSelection).toHaveBeenLastCalledWith({
      paper: false,
      page: true,
      selection: false,
    });

    plugin.removeInteractionContext("current-page");
    expect(plugin.contextChips()).toEqual([]);
    expect(plugin.codex.setReaderContextSelection).toHaveBeenLastCalledWith({
      paper: false,
      page: false,
      selection: false,
    });

    plugin.addInteractionContext({ id: "active-paper", kind: "paper", label: "Current Paper" });
    expect(plugin.contextChips().map((chip: { id: string }) => chip.id)).toEqual(["active-paper"]);
    expect(plugin.codex.setReaderContextSelection).toHaveBeenLastCalledWith({
      paper: true,
      page: false,
      selection: false,
    });
  });

  it("waits for a new Zotero window's native tab deck before migrating Workbench", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const source = { closed: false } as Window;
    const targetDocument = document.implementation.createHTMLDocument("Dedicated QLab");
    const target = { closed: false, document: targetDocument } as unknown as Window & { Zotero_Tabs?: any };
    let windows: Window[] = [source];
    (globalThis as any).Zotero = {
      getMainWindows: () => windows,
      openMainWindow: () => { windows = [source, target]; },
    };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.shortcutWindows = new Set([target]);
    let settled = false;

    try {
      const pending = plugin.openWorkbenchWindow(source).then((value: Window) => {
        settled = true;
        return value;
      });
      await new Promise((resolve) => setTimeout(resolve, 70));
      expect(settled).toBe(false);
      target.Zotero_Tabs = {
        add: vi.fn(),
        close: vi.fn(),
        tabHooks: {},
        _tabs: [
          { id: "zotero-pane", type: "library" },
          { id: "restored-reader", type: "reader" },
        ],
      };
      await expect(pending).resolves.toBe(target);
      expect(targetDocument.documentElement.getAttribute("data-qlab-workbench-window")).toBe("true");
      expect(target.Zotero_Tabs.close).toHaveBeenCalledWith(["restored-reader"]);
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("opens the standalone Workbench through Gecko when the current surface cannot open dialogs", async () => {
    const previousServices = (globalThis as any).Services;
    const previousZotero = (globalThis as any).Zotero;
    const popupDocument = document.implementation.createHTMLDocument("Standalone QLab");
    const host = popupDocument.createElement("div");
    host.id = "qlab-standalone-workbench-host";
    popupDocument.body.appendChild(host);
    const popup = {
      document: popupDocument,
      closed: false,
      close: vi.fn(),
    } as unknown as Window;
    const openWindow = vi.fn(() => popup);
    const source = {
      openDialog: vi.fn(() => { throw new Error("openDialog is unavailable"); }),
    } as unknown as Window;
    const plugin = new ZoteroChatPlugin() as any;
    plugin.injectWindowAssets = vi.fn();
    (globalThis as any).Services = { ww: { openWindow } };
    (globalThis as any).Zotero = {
      UIProperties: { registerRoot: vi.fn() },
    };

    try {
      await expect(plugin.openStandaloneWorkbenchWindow(source)).resolves.toBe(popup);
      expect(openWindow).toHaveBeenCalledWith(
        source,
        "chrome://zotkit/content/standalone-workbench.xhtml",
        "qlab-standalone-workbench",
        expect.stringContaining("dependent=no"),
        null,
      );
      expect(plugin.injectWindowAssets).toHaveBeenCalledWith(popup);
    }
    finally {
      (globalThis as any).Services = previousServices;
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("opens the paper bound to the QLab tab as a normal Zotero PDF tab", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const open = vi.fn(async () => ({}));
    (globalThis as any).Zotero = { Reader: { open } };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.readerContextItem = vi.fn(() => ({ id: 42 }));

    try {
      await plugin.openContextPDF();
      expect(open).toHaveBeenCalledWith(42, null, {
        allowDuplicate: false,
        openInBackground: false,
        preventJumpback: false,
      });
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("opens a QLab-only window's paper in a standalone Reader window", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const open = vi.fn(async () => ({}));
    (globalThis as any).Zotero = { Reader: { open } };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.readerContextItem = vi.fn(() => ({ id: 42 }));

    try {
      await plugin.openContextPDF(true);
      expect(open).toHaveBeenCalledWith(42, null, {
        allowDuplicate: false,
        openInBackground: false,
        preventJumpback: false,
        openInWindow: true,
      });
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("keeps Change Paper from adding a PDF tab to a QLab-only window", async () => {
    const originalZotero = (globalThis as any).Zotero;
    let resolveSelection!: () => void;
    const deferred = {
      promise: new Promise<void>((resolve) => { resolveSelection = resolve; }),
      resolve: () => resolveSelection(),
    };
    const attachment = {
      id: 42,
      key: "PAPER",
      libraryID: 1,
      title: "Dedicated Paper",
      creators: [],
      isPDFAttachment: () => true,
    };
    const reader = { itemID: 42 };
    const open = vi.fn(async () => reader);
    (globalThis as any).Zotero = {
      Promise: { defer: () => deferred },
      Items: { getAsync: vi.fn(async () => attachment) },
      Reader: { open },
      Session: { debounceSave: vi.fn() },
    };
    const targetDocument = document.implementation.createHTMLDocument("Dedicated QLab");
    targetDocument.documentElement.setAttribute("data-qlab-workbench-window", "true");
    const target = {
      document: targetDocument,
      setTimeout,
      openDialog: vi.fn((_url: string, _name: string, _features: string, io: any) => {
        io.dataOut = [42];
        io.deferred.resolve();
      }),
    } as unknown as Window;
    const accepted = { attachment, parent: { title: "Dedicated Paper", creators: [] } };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.readerContext = { acceptReaderHook: vi.fn(async () => accepted) };
    plugin.addedContextIDs = new Set();
    plugin.contextRequestSequence = 0;
    plugin.applyContext = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();
    plugin.workbenchTabs = {
      update: vi.fn(),
      entries: vi.fn(() => []),
    };

    try {
      await plugin.chooseWorkbenchPaper(target, "qlab-tab");
      expect(open).toHaveBeenCalledWith(42, null, {
        allowDuplicate: false,
        openInBackground: true,
        preventJumpback: true,
        openInWindow: true,
      });
      expect(plugin.applyContext).toHaveBeenCalledWith(accepted, 1);
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("opens page citations in the selected conversation PDF without changing or interrupting chat state", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const open = vi.fn(async () => ({}));
    const conversationAttachment = { id: 42, key: "PAPER-A" };
    const focusedAttachment = { id: 84, key: "PAPER-B" };
    const getByLibraryAndKey = vi.fn((_libraryID: number, key: string) => (
      key === "PAPER-A" ? conversationAttachment : focusedAttachment
    ));
    (globalThis as any).Zotero = { Reader: { open }, Items: { getByLibraryAndKey } };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = { attachment: { id: 84, libraryID: 1, key: "PAPER-B" } };
    plugin.codex = {
      getActiveReaderContext: vi.fn(() => ({
        attachment: { id: 42, libraryID: 1, key: "PAPER-A" },
      })),
      interrupt: vi.fn(),
    };

    try {
      await plugin.openConversationPDFPage(6, true);
      expect(getByLibraryAndKey).toHaveBeenCalledWith(1, "PAPER-A");
      expect(open).toHaveBeenCalledWith(42, { pageIndex: 5 }, {
        allowDuplicate: false,
        openInBackground: false,
        preventJumpback: false,
        openInWindow: true,
      });
      expect(plugin.codex.interrupt).not.toHaveBeenCalled();
      expect(plugin.context.attachment.key).toBe("PAPER-B");
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("starts an empty Workbench terminal at the configured QLab root", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const host = document.createElement("div");
    plugin.settings = { qlabRoot: "/research/quarto-lab" };
    plugin.context = null;
    plugin.readerContext = {
      getCachedZotkitLibrarySnapshotReference: vi.fn(() => null),
      ensureCurrentPdfTextReference: vi.fn(),
    };

    const options = await plugin.terminalOptions(host);

    expect(options).toMatchObject({
      host,
      paperTitle: "QLab Repository",
      workspace: "/research/quarto-lab",
      workingDirectory: "/research/quarto-lab",
      pdfPath: null,
      agent: "shell",
    });
    expect(plugin.readerContext.ensureCurrentPdfTextReference).not.toHaveBeenCalled();
  });

  it("shows exact requested permissions in the approval description", () => {
    const description = formatPendingApprovalDescription({
      description: "Stage a generated PDF",
      cwd: "/profile/papers/1-ATTACH",
      requestedPermissions: {
        network: { enabled: true },
        fileSystem: {
          entries: [{
            access: "write",
            path: { type: "path", path: "/profile/papers/1-ATTACH/staging" },
          }],
        },
      },
    });

    expect(description).toContain("Stage a generated PDF");
    expect(description).toContain('"network":{"enabled":true}');
    expect(description).toContain("/profile/papers/1-ATTACH/staging");
  });

  it("matches Cursor's Reader shortcuts while leaving editable controls alone", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.openWorkbenchTab = vi.fn(async () => {});
    plugin.openChatWithSelection = vi.fn(async () => {});
    plugin.openWorkbenchTerminal = vi.fn(async () => {});
    plugin.installShortcutHandler(window);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "i", metaKey: true, bubbles: true }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "l", metaKey: true, bubbles: true }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "L", metaKey: true, shiftKey: true, bubbles: true }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "j", metaKey: true, shiftKey: true, bubbles: true }));
    await Promise.resolve();

    expect(plugin.openWorkbenchTab).toHaveBeenCalledWith(window);
    expect(plugin.openChatWithSelection).toHaveBeenNthCalledWith(1, true);
    expect(plugin.openChatWithSelection).toHaveBeenNthCalledWith(2, false);
    expect(plugin.openWorkbenchTerminal).toHaveBeenCalledWith(window);

    const input = document.createElement("input");
    document.body.appendChild(input);
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "i", metaKey: true, bubbles: true }));
    expect(plugin.openWorkbenchTab).toHaveBeenCalledOnce();
    plugin.removeShortcutHandler(window);
    input.remove();
  });

  it("adds ⌘K to the Reader shortcuts and leaves editable controls alone", () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.toggleFloatPanel = vi.fn(async () => {});
    plugin.installShortcutHandler(window);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
    expect(plugin.toggleFloatPanel).toHaveBeenCalledOnce();

    const input = document.createElement("input");
    document.body.appendChild(input);
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
    expect(plugin.toggleFloatPanel).toHaveBeenCalledOnce();
    plugin.removeShortcutHandler(window);
    input.remove();
  });

  it("toggleFloatPanel opens with the cached selection attached, then closes and restores focus", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const focusTarget = document.createElement("button");
    document.body.appendChild(focusTarget);
    focusTarget.focus();
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = { setInteractionContext: vi.fn(), state: { connected: false } };
    plugin.context = {
      selection: { text: "chosen theorem", pageNumber: 3 },
      page: { pageNumber: 3 },
    };
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();
    plugin.reportError = vi.fn();

    await plugin.toggleFloatPanel();
    const root = document.querySelector<HTMLElement>(".zc-float")!;
    expect(root.hidden).toBe(false);
    expect(plugin.addedContextIDs.has("current-selection")).toBe(true);
    expect(plugin.ensureChatSession).toHaveBeenCalledOnce();
    expect(plugin.renderChatViews).toHaveBeenCalled();

    await plugin.toggleFloatPanel();
    expect(root.hidden).toBe(true);
    expect(document.activeElement).toBe(focusTarget);

    plugin.floatPanels.get(window)?.view.destroy();
    plugin.floatPanels.get(window)?.host.remove();
    focusTarget.remove();
    (globalThis as any).Zotero = previousZotero;
  });

  it("toggleFloatPanel opens without a chip when nothing is selected", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = { setInteractionContext: vi.fn(), state: { connected: false } };
    plugin.context = null;
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    await plugin.toggleFloatPanel();
    expect(document.querySelector<HTMLElement>(".zc-float")!.hidden).toBe(false);
    expect(plugin.addedContextIDs.has("current-selection")).toBe(false);

    plugin.hideFloatPanel(window);
    plugin.floatPanels.get(window)?.view.destroy();
    plugin.floatPanels.get(window)?.host.remove();
    (globalThis as any).Zotero = previousZotero;
  });

  it("renderFloatPanels keeps the floating chat compact by showing only the latest exchange", () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = {
      setInteractionContext: vi.fn(),
      state: {
        running: true,
        fallbackReason: null,
        models: [{ id: "gpt-5", label: "GPT-5" }, { id: "gpt-5-codex", label: "GPT-5 Codex" }],
        capabilities: { supportsAgentMode: true, supportsLogin: true },
      },
      getChatEntries: () => [
        { id: "u1", kind: "user", text: "old question" },
        { id: "a1", kind: "assistant", text: "old answer" },
        { id: "u2", kind: "user", text: "latest question" },
        { id: "a2", kind: "assistant", text: "latest answer" },
      ],
    };
    plugin.selectedModel = "gpt-5-codex";
    plugin.context = {
      selection: { text: "chosen theorem", pageNumber: 3 },
      page: { pageNumber: 3 },
      attachment: { title: "A Test Paper", creators: [] },
    };
    plugin.addedContextIDs.add("current-selection");
    plugin.chatPhase = "ready";
    const entry = plugin.mountFloatPanel(window);
    entry.view.show();

    plugin.renderFloatPanels();

    const root = document.querySelector<HTMLElement>(".zc-float")!;
    expect(root.textContent).toContain("latest question");
    expect(root.textContent).not.toContain("old question");
    expect(root.textContent).toContain("Selected 14 characters");
    expect(root.querySelector<HTMLElement>(".zc-float-stop")!.hidden).toBe(false);
    expect(root.querySelector(".zc-float-title")?.textContent).toBe("QLab · A Test Paper");
    const modelSelect = root.querySelector<HTMLSelectElement>(".zc-float-model")!;
    expect(modelSelect.hidden).toBe(false);
    expect(modelSelect.value).toBe("gpt-5-codex");

    entry.view.destroy();
    entry.host.remove();
    plugin.floatPanels.clear();
    (globalThis as any).Zotero = previousZotero;
  });

  describe("float panel size persistence", () => {
    afterEach(() => {
      vi.unstubAllGlobals();
      vi.useRealTimers();
      // Defensive: a mid-assertion failure would otherwise skip the inline
      // `entry.host.remove()` cleanup below and leave a stale `.zc-float`
      // node in `document`, corrupting the next test's querySelector.
      document.querySelectorAll(".zc-float-host").forEach((node) => node.remove());
    });

    it("restores the persisted floatSize onto the panel as an inline style when mounting", () => {
      vi.stubGlobal("Services", {
        prefs: {
          getStringPref: (key: string, fallback: string) =>
            key === "extensions.zotkit.floatSize" ? "540x480" : fallback,
          setStringPref: () => {},
        },
      });

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const root = document.querySelector<HTMLElement>(".zc-float")!;

      expect(root.style.width).toBe("540px");
      expect(root.style.height).toBe("480px");

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });

    it("ignores an unparsable persisted floatSize", () => {
      vi.stubGlobal("Services", {
        prefs: {
          getStringPref: (key: string, fallback: string) =>
            key === "extensions.zotkit.floatSize" ? "not-a-size" : fallback,
          setStringPref: () => {},
        },
      });

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const root = document.querySelector<HTMLElement>(".zc-float")!;

      expect(root.style.width).toBe("");
      expect(root.style.height).toBe("");

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });

    function stubFakeResizeObserver(setStringPref = vi.fn(), getStringPref?: (key: string, fallback: string) => string): {
      setStringPref: ReturnType<typeof vi.fn>;
      getObservedCallback: () => ResizeObserverCallback;
    } {
      vi.stubGlobal("Services", {
        prefs: {
          getStringPref: getStringPref ?? ((_key: string, fallback: string) => fallback),
          setStringPref,
        },
      });
      let observedCallback: ResizeObserverCallback | null = null;
      class FakeResizeObserver {
        constructor(callback: ResizeObserverCallback) {
          observedCallback = callback;
        }
        observe(): void {}
        disconnect(): void {}
      }
      vi.stubGlobal("ResizeObserver", FakeResizeObserver);
      return { setStringPref, getObservedCallback: () => observedCallback! };
    }

    it("persists a grip-driven resize: the observer fires after the native `resize: both` grip writes inline style", () => {
      vi.useFakeTimers();
      const { setStringPref, getObservedCallback } = stubFakeResizeObserver();

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const root = document.querySelector<HTMLElement>(".zc-float")!;
      const observedCallback = getObservedCallback();
      expect(observedCallback).not.toBeUndefined();

      // The initial notification reflects the panel's starting size (no
      // inline style change yet) and must not be persisted.
      observedCallback([{ contentRect: { width: 620, height: 400 } } as ResizeObserverEntry], {} as ResizeObserver);
      expect(setStringPref).not.toHaveBeenCalled();

      // Gecko's native `resize: both` grip writes inline style.width/height
      // directly on the element -- simulate the grip drag, then the
      // observer notification it triggers.
      root.style.width = "700px";
      root.style.height = "500px";
      observedCallback([{ contentRect: { width: 700, height: 500 } } as ResizeObserverEntry], {} as ResizeObserver);
      expect(setStringPref).not.toHaveBeenCalled();
      vi.advanceTimersByTime(499);
      expect(setStringPref).not.toHaveBeenCalled();
      vi.advanceTimersByTime(1);
      expect(setStringPref).toHaveBeenCalledWith("extensions.zotkit.floatSize", "700x500");

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });

    it("does not persist a window-driven reflow that never touches the inline style", () => {
      vi.useFakeTimers();
      const { setStringPref, getObservedCallback } = stubFakeResizeObserver();

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const observedCallback = getObservedCallback();
      expect(observedCallback).not.toBeUndefined();

      observedCallback([{ contentRect: { width: 620, height: 400 } } as ResizeObserverEntry], {} as ResizeObserver);
      // A responsive reflow (e.g. the window shrinking so the CSS
      // `min(620px, 100vw - 48px)` bound recomputes) changes the observed
      // content box without ever writing to `style.width`/`style.height`.
      observedCallback([{ contentRect: { width: 500, height: 400 } } as ResizeObserverEntry], {} as ResizeObserver);
      vi.advanceTimersByTime(1000);
      expect(setStringPref).not.toHaveBeenCalled();

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });

    it("does not mistake clearing the inline height for an empty transcript as a user resize", () => {
      vi.useFakeTimers();
      const { setStringPref, getObservedCallback } = stubFakeResizeObserver(
        vi.fn(),
        (key, fallback) => (key === "extensions.zotkit.floatSize" ? "620x480" : fallback),
      );

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const root = document.querySelector<HTMLElement>(".zc-float")!;
      expect(root.style.height).toBe("480px");
      const observedCallback = getObservedCallback();

      observedCallback([{ contentRect: { width: 620, height: 480 } } as ResizeObserverEntry], {} as ResizeObserver);

      entry.view.setState({ phase: "ready", entries: [] });
      expect(root.style.height).toBe("");

      // happy-dom never actually fires ResizeObserver callbacks, but a real
      // browser would notify it of the resulting content-box change; that
      // notification must not be mistaken for a user resize.
      observedCallback([{ contentRect: { width: 620, height: 220 } } as ResizeObserverEntry], {} as ResizeObserver);
      vi.advanceTimersByTime(1000);
      expect(setStringPref).not.toHaveBeenCalled();

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });

    it("clamps outlier resized dimensions before persisting them", () => {
      vi.useFakeTimers();
      const { setStringPref, getObservedCallback } = stubFakeResizeObserver();

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const root = document.querySelector<HTMLElement>(".zc-float")!;
      const observedCallback = getObservedCallback();

      observedCallback([{ contentRect: { width: 620, height: 400 } } as ResizeObserverEntry], {} as ResizeObserver);

      root.style.width = "50px";
      root.style.height = "5000px";
      observedCallback([{ contentRect: { width: 50, height: 5000 } } as ResizeObserverEntry], {} as ResizeObserver);
      vi.advanceTimersByTime(500);
      expect(setStringPref).toHaveBeenCalledWith("extensions.zotkit.floatSize", "380x2000");

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });
  });

  it("records turn duration keyed by the opening user entry when running flips off", () => {
    vi.useFakeTimers();
    try {
      const plugin = new ZoteroChatPlugin() as any;
      plugin.codex = {
        setInteractionContext: vi.fn(),
        state: {
          activeThreadId: "th1",
          running: true,
          fallbackReason: null,
          models: [],
          mode: "agent",
        },
        getChatEntries: () => [
          { id: "u1", kind: "user", text: "问" },
          { id: "a1", kind: "assistant", text: "答" },
        ],
        getActivePlan: () => null,
        getActiveDiffs: () => [],
        getPendingApprovals: () => [],
        getCheckpoints: () => [],
        getThreadOptions: () => [],
        isSignedIn: () => false,
      };

      vi.setSystemTime(new Date("2026-07-23T10:00:00Z"));
      plugin.renderChatViews();

      vi.setSystemTime(new Date("2026-07-23T10:00:28Z"));
      plugin.codex.state.running = false;
      plugin.renderChatViews();

      expect(plugin.turnDurationsForActiveThread()).toEqual({ u1: 28_000 });
    }
    finally {
      vi.useRealTimers();
    }
  });

  it("keeps a background thread timer alive across tab switches and completes it on return", () => {
    vi.useFakeTimers();
    try {
      const plugin = new ZoteroChatPlugin() as any;
      plugin.onTurnCompleted = vi.fn();
      plugin.codex = {
        setInteractionContext: vi.fn(),
        state: {
          activeThreadId: "A",
          running: true,
          fallbackReason: null,
          models: [],
          mode: "agent",
        },
        getChatEntries: () => [
          { id: "u1", kind: "user", text: "问 A" },
        ],
        getActivePlan: () => null,
        getActiveDiffs: () => [],
        getPendingApprovals: () => [],
        getCheckpoints: () => [],
        getThreadOptions: () => [],
        isSignedIn: () => false,
      };

      vi.setSystemTime(new Date("2026-07-23T10:00:00Z"));
      plugin.renderChatViews(); // Thread A starts running.

      // The user switches to idle thread B mid-turn; A continues in the background.
      vi.setSystemTime(new Date("2026-07-23T10:05:00Z"));
      plugin.codex.state.activeThreadId = "B";
      plugin.codex.state.running = false;
      plugin.codex.getChatEntries = () => [];
      plugin.renderChatViews();

      expect(plugin.turnDurationsForActiveThread()).toEqual({});
      expect(plugin.onTurnCompleted).not.toHaveBeenCalled();

      // Reopening A while it is still running resumes the same visible clock.
      plugin.codex.state.activeThreadId = "A";
      plugin.codex.state.running = true;
      plugin.codex.getChatEntries = () => [
        { id: "u1", kind: "user", text: "问 A" },
      ];
      plugin.renderChatViews();

      expect(plugin.turnDurationsForActiveThread()).toEqual({});
      expect(plugin.onTurnCompleted).not.toHaveBeenCalled();

      vi.setSystemTime(new Date("2026-07-23T10:06:00Z"));
      plugin.codex.state.running = false;
      plugin.renderChatViews();
      expect(plugin.turnDurationsForActiveThread()).toEqual({ u1: 360_000 });
    }
    finally {
      vi.useRealTimers();
    }
  });

  it("onMainWindowUnload destroys the window's float panel", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = { setInteractionContext: vi.fn(), state: { connected: false } };
    plugin.context = null;
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    await plugin.toggleFloatPanel();
    expect(document.querySelector(".zc-float")).not.toBeNull();

    await plugin.onMainWindowUnload(window);
    expect(document.querySelector(".zc-float")).toBeNull();
    expect(plugin.floatPanels.size).toBe(0);

    (globalThis as any).Zotero = previousZotero;
  });

  it("Escape closes the float panel from anywhere and restores focus", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = { setInteractionContext: vi.fn(), state: { connected: false } };
    plugin.context = null;
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    await plugin.toggleFloatPanel();
    const root = document.querySelector<HTMLElement>(".zc-float")!;
    expect(root.hidden).toBe(false);

    plugin.installShortcutHandler(window);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(root.hidden).toBe(true);

    plugin.removeShortcutHandler(window);
    plugin.floatPanels.get(window)?.view.destroy();
    plugin.floatPanels.get(window)?.host.remove();
    plugin.floatPanels.clear();
    (globalThis as any).Zotero = previousZotero;
  });

  it("coalesces concurrent first expansion into one lazy terminal startup", async () => {
    let release!: () => void;
    const startup = new Promise<void>((resolve) => { release = resolve; });
    const plugin = new ZoteroChatPlugin() as any;
    plugin.openTerminalInternal = vi.fn(() => startup);

    const first = plugin.openTerminal();
    const second = plugin.openTerminal();
    expect(plugin.openTerminalInternal).toHaveBeenCalledOnce();

    release();
    await Promise.all([first, second]);
    expect(plugin.terminalOpenPromise).toBeNull();
  });

  it("clears a failed lazy startup without creating an unhandled finally rejection", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.openTerminalInternal = vi.fn(async () => { throw new Error("startup failed"); });

    await expect(plugin.openTerminal()).rejects.toThrow("startup failed");
    await Promise.resolve();

    expect(plugin.terminalOpenPromise).toBeNull();
  });

  it("captures context before the first terminal open can start the helper", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const host = document.createElement("div");
    const calls: string[] = [];
    plugin.terminal = {
      mount: vi.fn(() => calls.push("mount")),
      open: vi.fn(async () => { calls.push("open"); }),
    };
    plugin.refreshContext = vi.fn(async () => { calls.push("context"); });
    plugin.readerContext = {
      ensureZotkitLibrarySnapshot: vi.fn(async () => { calls.push("snapshot"); }),
    };
    plugin.terminalOptions = vi.fn(async () => {
      calls.push("options");
      return { host };
    });

    await plugin.openTerminalInternal(host);

    expect(calls).toEqual(["mount", "context", "snapshot", "options", "open"]);
  });

  it("invalidates Reader text caches and reloads every matching Reader after a PDF mutation", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const matchingA = { itemID: 7, reload: vi.fn(async () => {}) };
    const matchingB = { itemID: 7, reload: vi.fn(async () => {}) };
    const unrelated = { itemID: 8, reload: vi.fn(async () => {}) };
    (globalThis as any).Zotero = {
      Reader: {
        _readers: [matchingA, unrelated, matchingB],
        getByTabID: vi.fn(() => matchingA),
      },
    };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.readerContext = {
      invalidateAttachmentCaches: vi.fn(async () => {}),
      ensureZotkitLibrarySnapshot: vi.fn(async () => null),
    };
    plugin.selectedTabID = vi.fn(() => "reader-a");
    plugin.refreshContext = vi.fn(async () => {});
    plugin.refreshMutationCheckpoints = vi.fn(async () => {});

    try {
      await plugin.refreshAfterMutation({
        decision: "accepted",
        effects: {
          attachmentID: 7,
          attachmentKey: "ATTACH",
          attachmentLibraryID: 1,
          attachmentContentChanged: true,
          attachmentRelinked: false,
          pdfReplaced: true,
        },
      });

      expect(plugin.readerContext.invalidateAttachmentCaches).toHaveBeenCalledWith({
        key: "ATTACH",
        libraryID: 1,
      });
      expect(matchingA.reload).toHaveBeenCalledOnce();
      expect(matchingB.reload).toHaveBeenCalledOnce();
      expect(unrelated.reload).not.toHaveBeenCalled();
      expect(plugin.refreshContext).toHaveBeenCalledOnce();
    }
    finally {
      if (originalZotero === undefined) delete (globalThis as any).Zotero;
      else (globalThis as any).Zotero = originalZotero;
    }
  });

  it("mounts and switches the terminal on the selected Reader body across A to B to A", async () => {
    const originalZotero = (globalThis as any).Zotero;
    let selectedID = "reader-a";
    (globalThis as any).Zotero = {
      getMainWindow: () => ({ Zotero_Tabs: { selectedID } }),
    };

    const createReaderBody = (tabID: string): HTMLElement => {
      const details = document.createElement("item-details");
      details.setAttribute("data-tab-id", tabID);
      const section = document.createElement("collapsible-section");
      section.setAttribute("open", "");
      const body = document.createElement("div");
      section.append(body);
      details.append(section);
      document.body.append(details);
      return body;
    };

    const bodyA = createReaderBody("reader-a");
    const bodyB = createReaderBody("reader-b");
    const plugin = new ZoteroChatPlugin() as any;
    plugin.paneMode = "terminal";
    plugin.views = new Set([bodyB, bodyA]);
    plugin.context = { workspace: { root: "/profile/zotkit/a" } };
    plugin.terminal = {
      isOpen: true,
      hasLiveSessions: true,
      mount: vi.fn(),
      setVisible: vi.fn(),
      switchPaper: vi.fn(async () => {}),
    };
    plugin.terminalOptions = vi.fn(async (host: HTMLElement) => ({ host }));
    plugin.refreshContext = vi.fn(async (_pageChange: boolean, host: HTMLElement) => {
      await plugin.switchTerminalToContext(false, host);
    });

    try {
      for (const [tabID, body] of [
        ["reader-a", bodyA],
        ["reader-b", bodyB],
        ["reader-a", bodyA],
      ] as const) {
        selectedID = tabID;
        expect(plugin.activeSidebarBody()).toBe(body);
        await plugin.refreshSelectedReaderTab(tabID);
      }

      expect(plugin.terminal.mount.mock.calls.map(([host]: [HTMLElement]) => host))
        .toEqual([bodyA, bodyB, bodyA]);
      expect(plugin.terminal.switchPaper.mock.calls.map(([options]: [{ host: HTMLElement }]) => options.host))
        .toEqual([bodyA, bodyB, bodyA]);
    }
    finally {
      bodyA.closest("item-details")?.remove();
      bodyB.closest("item-details")?.remove();
      if (originalZotero === undefined) delete (globalThis as any).Zotero;
      else (globalThis as any).Zotero = originalZotero;
    }
  });

  it("restores a live Reader terminal after visiting the library tab", async () => {
    const originalZotero = (globalThis as any).Zotero;
    let selectedID = "reader-a";
    (globalThis as any).Zotero = {
      getMainWindow: () => ({ Zotero_Tabs: { selectedID } }),
    };
    const details = document.createElement("item-details");
    details.setAttribute("data-tab-id", "reader-a");
    const section = document.createElement("collapsible-section");
    section.setAttribute("open", "");
    const body = document.createElement("div");
    section.append(body);
    details.append(section);
    document.body.append(details);

    const plugin = new ZoteroChatPlugin() as any;
    plugin.paneMode = "terminal";
    plugin.views = new Set([body]);
    plugin.terminal = {
      isOpen: false,
      hasLiveSessions: true,
      mount: vi.fn(),
      setVisible: vi.fn(),
    };
    plugin.refreshContext = vi.fn(async () => {});

    try {
      selectedID = "zotero-pane";
      await plugin.refreshSelectedReaderTab("zotero-pane", false);
      expect(plugin.terminal.setVisible).toHaveBeenCalledWith(false);

      selectedID = "reader-a";
      await plugin.refreshSelectedReaderTab("reader-a", true);
      expect(plugin.terminal.mount).toHaveBeenCalledWith(body);
      expect(plugin.refreshContext).toHaveBeenCalledWith(false, body);
    }
    finally {
      details.remove();
      if (originalZotero === undefined) delete (globalThis as any).Zotero;
      else (globalThis as any).Zotero = originalZotero;
    }
  });

  it("drops an older tab switch when terminal options finish after a newer switch", async () => {
    const originalZotero = (globalThis as any).Zotero;
    let selectedID = "reader-b";
    (globalThis as any).Zotero = {
      getMainWindow: () => ({ Zotero_Tabs: { selectedID } }),
    };
    const makeBody = (tabID: string): HTMLElement => {
      const details = document.createElement("item-details");
      details.setAttribute("data-tab-id", tabID);
      const body = document.createElement("div");
      details.append(body);
      document.body.append(details);
      return body;
    };
    const bodyA = makeBody("reader-a");
    const bodyB = makeBody("reader-b");
    let releaseB!: (options: { host: HTMLElement; paperKey: string }) => void;
    const optionsB = new Promise<{ host: HTMLElement; paperKey: string }>((resolve) => {
      releaseB = resolve;
    });
    const plugin = new ZoteroChatPlugin() as any;
    plugin.destroyed = false;
    plugin.context = { workspace: { root: "/profile/zotkit" } };
    plugin.terminal = {
      hasLiveSessions: true,
      switchPaper: vi.fn(async () => {}),
    };
    plugin.readerContext = { ensureZotkitLibrarySnapshot: vi.fn(async () => {}) };
    plugin.terminalOptions = vi.fn((host: HTMLElement) => (
      host === bodyB ? optionsB : Promise.resolve({ host, paperKey: "A" })
    ));

    try {
      plugin.contextRequestSequence = 1;
      const stale = plugin.switchTerminalToContext(false, bodyB, 1);
      await Promise.resolve();

      selectedID = "reader-a";
      plugin.contextRequestSequence = 2;
      await plugin.switchTerminalToContext(false, bodyA, 2);
      releaseB({ host: bodyB, paperKey: "B" });
      await stale;

      expect(plugin.terminal.switchPaper).toHaveBeenCalledOnce();
      expect(plugin.terminal.switchPaper).toHaveBeenCalledWith(
        expect.objectContaining({ host: bodyA, paperKey: "A" }),
      );
    }
    finally {
      bodyA.closest("item-details")?.remove();
      bodyB.closest("item-details")?.remove();
      if (originalZotero === undefined) delete (globalThis as any).Zotero;
      else (globalThis as any).Zotero = originalZotero;
    }
  });

  it("does not let an older page refresh overwrite a newer Reader tab context", async () => {
    const originalZotero = (globalThis as any).Zotero;
    let selectedID = "reader-a";
    (globalThis as any).Zotero = {
      getMainWindow: () => ({ Zotero_Tabs: { selectedID } }),
    };
    const contextA = {
      attachment: { key: "A", libraryID: 1 },
      workspace: { root: "/profile/a" },
    };
    const contextB = {
      attachment: { key: "B", libraryID: 1 },
      workspace: { root: "/profile/b" },
    };
    let releasePageA!: (context: typeof contextA) => void;
    const pageA = new Promise<typeof contextA>((resolve) => { releasePageA = resolve; });
    const plugin = new ZoteroChatPlugin() as any;
    plugin.destroyed = false;
    plugin.terminal = { hasLiveSessions: false };
    plugin.readerContext = {
      refreshForPageChange: vi.fn(() => pageA),
      refresh: vi.fn(async () => contextB),
    };

    try {
      const stalePageRefresh = plugin.refreshContext(true);
      await Promise.resolve();
      selectedID = "reader-b";
      await plugin.refreshContext(false);
      releasePageA(contextA);
      await stalePageRefresh;

      expect(plugin.context).toBe(contextB);
      expect(plugin.context.attachment.key).toBe("B");
    }
    finally {
      if (originalZotero === undefined) delete (globalThis as any).Zotero;
      else (globalThis as any).Zotero = originalZotero;
    }
  });

});

describe("Reader context copied into the terminal", () => {
  it("uses the original PDF directory when the path is absolute", () => {
    expect(pdfDirectory("/workspace/fixtures/papers/example.pdf")).toBe("/workspace/fixtures/papers");
    expect(pdfDirectory("relative/example.pdf")).toBeNull();
    expect(pdfDirectory(null)).toBeNull();
  });

  it("inserts metadata, page, path, and literal selection without submitting", () => {
    const context = {
      schemaVersion: 1,
      attachment: {
        id: 2,
        key: "PDFKEY",
        title: "Attachment",
        creators: [],
        tags: [],
      },
      parent: {
        id: 1,
        key: "ITEMKEY",
        title: "Quantum Control",
        creators: [{ firstName: "Ada", lastName: "Lovelace" }],
        year: "2026",
        doi: "10.1/example",
        tags: [],
      },
      pdfPath: "/workspace/fixtures/papers/quantum.pdf",
      page: {
        pageIndex: 6,
        pageNumber: 7,
        text: "page",
        source: "pdfjs",
        warnings: [],
      },
      selection: {
        text: "first line\nsecond line\u001b[31m",
        pageNumber: 7,
        capturedAt: "2026-07-22T00:00:00Z",
      },
      fullText: { source: "deferred", characters: 0 },
      capturedAt: "2026-07-22T00:00:00Z",
      warnings: [],
    } as ReaderContext;

    const prompt = buildSelectionPrompt(context);
    expect(prompt).toContain("Quantum Control");
    expect(prompt).toContain("Ada Lovelace");
    expect(prompt).toContain("10.1/example");
    expect(prompt).toContain("/workspace/fixtures/papers/quantum.pdf");
    expect(prompt).toContain("PDF page: 7");
    expect(prompt).toContain("first line second line [31m");
    expect(prompt).toMatch(/Question: $/);
    expect(prompt).not.toMatch(/[\r\n\u001b]/);
  });

  it("bounds a pasted selection while leaving the complete live MCP copy available", () => {
    const context = {
      schemaVersion: 1,
      attachment: { id: 2, key: "PDFKEY", creators: [], tags: [] },
      parent: null,
      pdfPath: "/papers/long.pdf",
      page: { pageIndex: 0, pageNumber: 1, text: "", source: "none", warnings: [] },
      selection: {
        text: "x".repeat(MAX_SELECTION_PROMPT_CHARACTERS + 500),
        pageNumber: 1,
        capturedAt: "2026-07-22T00:00:00Z",
      },
      fullText: { source: "deferred", characters: 0 },
      capturedAt: "2026-07-22T00:00:00Z",
      warnings: [],
    } as ReaderContext;

    const prompt = buildSelectionPrompt(context);
    expect(prompt).toContain("full text remains available through zotero_reader");
    expect(prompt.length).toBeLessThan(MAX_SELECTION_PROMPT_CHARACTERS + 500);
  });
});

describe("clampFloatOpacity", () => {
  it("clamps parsed values to the 60-100 slider range", () => {
    expect(clampFloatOpacity("100")).toBe(100);
    expect(clampFloatOpacity("85")).toBe(85);
    expect(clampFloatOpacity("40")).toBe(60);
    expect(clampFloatOpacity("250")).toBe(100);
  });

  it("clamps a valid-but-falsy 0 to the 60 floor instead of the old `|| 100` trap promoting it to 100", () => {
    // `Number("0")` is a legitimate (if out-of-range) 0, not NaN -- the old
    // `Number(pref) || 100` fallback silently turned it into 100 by treating
    // falsy-but-valid 0 the same as "missing". It should now simply clamp to
    // the 60 floor like any other too-low value.
    expect(clampFloatOpacity("0")).toBe(60);
  });

  it("falls back to 100 only for genuinely unparsable (NaN) values, not merely falsy/empty ones", () => {
    expect(clampFloatOpacity("not-a-number")).toBe(100);
    // `Number("")` is 0, not NaN, so this clamps like any other 0 -- it must
    // not be confused with the NaN fallback case.
    expect(clampFloatOpacity("")).toBe(60);
  });
});

describe("paper-trail wiring", () => {
  it("begins a pending anchor on sendChat only when the selection chip is attached", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = { selection: { text: "s", position: { pageIndex: 1, rects: [[0, 0, 1, 1]] }, pageNumber: 2 }, attachment: { key: "A", libraryID: 1 } };
    plugin.codex = {
      state: { connected: true, activeThreadId: "th1" },
      isSignedIn: () => true,
      send: vi.fn(async () => {}),
      getChatEntries: () => [],
    };
    plugin.paperTrail = { beginPendingAnchor: vi.fn() };
    plugin.addedContextIDs = new Set(["current-selection"]);
    await plugin.sendChat("为什么?");
    expect(plugin.paperTrail.beginPendingAnchor).toHaveBeenCalledWith(plugin.context, "为什么?", "th1");
    plugin.addedContextIDs = new Set();
    await plugin.sendChat("再问");
    expect(plugin.paperTrail.beginPendingAnchor).toHaveBeenCalledTimes(1);
  });

  it("model tool registry stays write-free (static guarantee)", async () => {
    const { ZOTERO_MUTATION_TOOL } = await import("../src/zotero-mutations");
    expect(ZOTERO_MUTATION_TOOL).toBe("zotero_propose_changes");
    const source = readFileSync(join(__dirname, "../src/paper-trail.ts"), "utf8");
    expect(source).not.toMatch(/tools\s*[:=]/);   // paper-trail 永不注册Model工具
  });

  it("jumpToAnchor opens the reader at the annotation", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const open = vi.fn(async () => {});
    (globalThis as any).Zotero = { Items: { getByLibraryAndKey: () => ({ id: 42 }) }, Reader: { open } };
    const plugin = new ZoteroChatPlugin() as any;
    await plugin.jumpToAnchor({ libraryID: 1, attachmentKey: "A", annotationKey: "ANN1", anchorId: "a1" });
    expect(open).toHaveBeenCalledWith(42, { annotationID: "ANN1" }, { allowDuplicate: false });
    (globalThis as any).Zotero = previousZotero;
  });

  it("resumeAnchorChat switches to the anchor's thread and opens the panel when it wasn't already open", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = { attachment: { key: "A", libraryID: 1 } };
    plugin.codex = {
      state: { connected: false, activeThreadId: "th-old" },
      getAnchors: () => [{ anchorId: "a1", annotationKey: "ANN1", threadId: "th-new" }],
      switchThread: vi.fn(async () => {}),
    };
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    await plugin.resumeAnchorChat("ANN1");

    expect(plugin.codex.switchThread).toHaveBeenCalledWith("th-new");
    const root = document.querySelector<HTMLElement>(".zc-float")!;
    expect(root.hidden).toBe(false);

    plugin.floatPanels.get(window)?.view.destroy();
    plugin.floatPanels.get(window)?.host.remove();
    (globalThis as any).Zotero = previousZotero;
  });

  it("resumeAnchorChat keeps an already-open panel open (does not toggle it closed), and no-ops the thread switch when the annotation has no matching anchor", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = { attachment: { key: "A", libraryID: 1 } };
    plugin.codex = {
      state: { connected: false, activeThreadId: "th1" },
      getAnchors: () => [],
      switchThread: vi.fn(async () => {}),
    };
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    // Simulate the user already having the panel open before "继续对话" is clicked.
    await plugin.toggleFloatPanel();
    const root = document.querySelector<HTMLElement>(".zc-float")!;
    expect(root.hidden).toBe(false);

    const hideSpy = vi.spyOn(plugin, "hideFloatPanel");
    await plugin.resumeAnchorChat("ANN-missing");

    expect(hideSpy).not.toHaveBeenCalled();
    expect(root.hidden).toBe(false);
    expect(plugin.codex.switchThread).not.toHaveBeenCalled();

    plugin.floatPanels.get(window)?.view.destroy();
    plugin.floatPanels.get(window)?.host.remove();
    (globalThis as any).Zotero = previousZotero;
  });
});

describe("clampFloatSize", () => {
  it("clamps width to [380, 760] and height to [220, 2000]", () => {
    expect(clampFloatSize(620, 480)).toEqual({ width: 620, height: 480 });
    expect(clampFloatSize(50, 5000)).toEqual({ width: 380, height: 2000 });
    expect(clampFloatSize(10_000, 10)).toEqual({ width: 760, height: 220 });
  });
});

describe("Region screenshots (Design 3)", () => {
  const paperContext = () => ({
    attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
    parent: { title: "Paper", creators: [], tags: [] },
    page: { pageNumber: 5, pageLabel: "5" },
  });

  it("offers Screenshot Region in the Add-Context menu only while a reader is active", () => {
    const plugin = new ZoteroChatPlugin() as any;

    const withoutReader = plugin.contextSuggestions()
      .find((item: { id: string }) => item.id === "capture-region");
    expect(withoutReader).toMatchObject({
      label: "Screenshot Region",
      kind: "selection",
      disabled: true,
    });

    plugin.context = paperContext();
    const withReader = plugin.contextSuggestions()
      .find((item: { id: string }) => item.id === "capture-region");
    expect(withReader?.disabled).toBe(false);

    plugin.pendingScreenshots = Array.from({ length: 10 }, (_, index) => ({
      image: `data:image/png;base64,${index}`,
      kind: "page" as const,
    }));
    expect(plugin.contextSuggestions()
      .find((item: { id: string }) => item.id === "capture-region")?.disabled).toBe(true);
  });

  it("starts the region flow from the Add-Context menu entry", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const target = { reader: { id: "reader-b" }, pageIndex: 8, context: paperContext() };
    plugin.readerContext = { getActiveCaptureTarget: vi.fn(async () => target) };
    plugin.startRegionScreenshot = vi.fn(async () => {});
    plugin.updateInteractionContext = vi.fn();
    plugin.renderChatViews = vi.fn();

    plugin.addInteractionContext({ id: "capture-region", kind: "selection", label: "Screenshot Region" });

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(plugin.readerContext.getActiveCaptureTarget).toHaveBeenCalledOnce();
    expect(plugin.startRegionScreenshot).toHaveBeenCalledWith(target);
    expect(plugin.updateInteractionContext).not.toHaveBeenCalled();
  });

  it("labels pending page and region screenshots independently", () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = paperContext();
    plugin.pendingScreenshots = [
      { image: "data:image/png;base64,a", kind: "page" },
      { image: "data:image/png;base64,b", kind: "region" },
      { image: "data:image/png;base64,c", kind: "page" },
    ];

    const labels = plugin.contextChips().map((chip: { label: string }) => chip.label);

    expect(labels).toContain("PDF Screenshot 1");
    expect(labels).toContain("Region Screenshot 1");
    expect(labels).toContain("PDF Screenshot 2");
    expect(plugin.contextChips().map((chip: { id: string }) => chip.id))
      .toEqual(expect.arrayContaining(["screenshot:0", "screenshot:1", "screenshot:2"]));
    expect(plugin.contextChips().filter((chip: { id: string }) => chip.id.startsWith("screenshot:")))
      .toEqual(expect.arrayContaining([
        expect.objectContaining({ kind: "screenshot" }),
      ]));
  });

  it("sends pending screenshots as bare data URIs and clears them after the send", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const send = vi.fn(async () => {});
    plugin.codex = {
      state: { connected: true, activeThreadId: null },
      isSignedIn: () => true,
      send,
      getActiveReaderContext: () => null,
    };
    plugin.pendingScreenshots = [
      { image: "data:image/png;base64,a", kind: "page" },
      {
        image: "data:image/png;base64,b",
        kind: "region",
        source: {
          paperKey: "1-READER-B",
          paperTitle: "Paper B",
          pageIndex: 8,
          pageNumber: 9,
          pageLabel: "9",
        },
      },
    ];

    await plugin.sendChat("what is in this figure?");

    expect(send).toHaveBeenCalledWith(
      "what is in this figure?",
      "",
      "medium",
      ["data:image/png;base64,a", "data:image/png;base64,b"],
      {},
    );
    expect(plugin.pendingScreenshots).toEqual([]);
  });

  it("applies an accepted capture target without switching the selected conversation", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = {
      getMainWindows: () => [],
      getMainWindow: () => null,
    };
    const context = paperContext();
    const target = { reader: { id: "reader-b" }, pageIndex: 8, context };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.contextRequestSequence = 40;
    plugin.readerContext = { captureTargetFromHook: vi.fn(async () => target) };
    plugin.codex = {
      state: { connected: true, activeThreadId: "thread-a" },
      isSignedIn: () => true,
      setPaper: vi.fn(async () => {}),
    };
    plugin.updateInteractionContext = vi.fn();
    plugin.renderChatViews = vi.fn();
    const applyContext = vi.spyOn(plugin, "applyContext");

    try {
      await expect(plugin.acceptReaderCaptureTarget({
        reader: target.reader,
        item: { id: 17 },
        params: {},
      })).resolves.toBe(target);

      expect(applyContext).toHaveBeenCalledWith(context, 41);
      expect(plugin.codex.setPaper).toHaveBeenCalledWith(context);
      expect(plugin.codex.state.activeThreadId).toBe("thread-a");
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("injects a Reader-bound region-capture button beside the workbench button", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const listeners = new Map<string, (event: any) => void>();
    (globalThis as any).Zotero = {
      Reader: {
        registerEventListener: vi.fn((type: string, handler: (event: any) => void) => {
          listeners.set(type, handler);
        }),
      },
    };
    try {
      const plugin = new ZoteroChatPlugin() as any;
      const target = {
        reader: { id: "reader-b" },
        pageIndex: 8,
        context: paperContext(),
      };
      plugin.installShortcutHandler = vi.fn();
      plugin.acceptReaderCaptureTarget = vi.fn(async () => target);
      plugin.startRegionScreenshot = vi.fn(async () => {});
      plugin.registerReaderHooks();

      const appended: HTMLElement[] = [];
      listeners.get("renderToolbar")!({
        doc: document,
        append: (element: HTMLElement) => appended.push(element),
        reader: { id: "reader-1" },
      });

      expect(appended).toHaveLength(2);
      const regionButton = appended[1] as HTMLButtonElement;
      expect(regionButton.title).toBe("Capture Region Screenshot (QLab)");
      expect(regionButton.getAttribute("aria-label")).toBe("Capture Region Screenshot (QLab)");
      expect(regionButton.querySelector("img")?.alt).toBe("");
      expect(regionButton.textContent).not.toBe("⬚");
      regionButton.click();
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(plugin.acceptReaderCaptureTarget).toHaveBeenCalledOnce();
      expect(plugin.startRegionScreenshot).toHaveBeenCalledWith(target);
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("keeps only one region-selection overlay", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const pageElement = document.createElement("div");
    document.body.appendChild(pageElement);
    const target = { reader: { id: "reader-b" }, pageIndex: 8, context: paperContext() };
    plugin.readerContext = {
      getCaptureTargetPageViewElement: vi.fn(async () => pageElement),
    };

    await plugin.startRegionScreenshot(target);
    const first = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;
    await plugin.startRegionScreenshot(target);
    const second = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;

    expect(first.isConnected).toBe(false);
    expect(second).not.toBe(first);
    expect(pageElement.querySelectorAll(".zc-region-overlay")).toHaveLength(1);
    pageElement.remove();
  });

  it("removes the active overlay before another capture waits for its page", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const pageElement = document.createElement("div");
    document.body.appendChild(pageElement);
    const target = { reader: { id: "reader-b" }, pageIndex: 8, context: paperContext() };
    let resolvePage!: (page: HTMLElement) => void;
    const delayedPage = new Promise<HTMLElement>((resolve) => { resolvePage = resolve; });
    plugin.readerContext = {
      getCaptureTargetPageViewElement: vi.fn()
        .mockResolvedValueOnce(pageElement)
        .mockReturnValueOnce(delayedPage),
    };

    await plugin.startRegionScreenshot(target);
    const first = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;
    const secondStart = plugin.startRegionScreenshot(target);
    await Promise.resolve();

    expect(first.isConnected).toBe(false);
    resolvePage(pageElement);
    await secondStart;
    pageElement.remove();
  });

  it("keeps only the newest overlay when pending page lookups resolve out of order", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const olderPage = document.createElement("div");
    const newerPage = document.createElement("div");
    document.body.append(olderPage, newerPage);
    const target = { reader: { id: "reader-b" }, pageIndex: 8, context: paperContext() };
    let resolveOlder!: (page: HTMLElement) => void;
    let resolveNewer!: (page: HTMLElement) => void;
    const olderLookup = new Promise<HTMLElement>((resolve) => { resolveOlder = resolve; });
    const newerLookup = new Promise<HTMLElement>((resolve) => { resolveNewer = resolve; });
    plugin.readerContext = {
      getCaptureTargetPageViewElement: vi.fn()
        .mockReturnValueOnce(olderLookup)
        .mockReturnValueOnce(newerLookup),
    };

    try {
      const olderStart = plugin.startRegionScreenshot(target);
      const newerStart = plugin.startRegionScreenshot(target);
      resolveNewer(newerPage);
      await newerStart;
      resolveOlder(olderPage);
      await olderStart;

      expect(olderPage.querySelector(".zc-region-overlay")).toBeNull();
      const newest = newerPage.querySelector<HTMLElement>(".zc-region-overlay")!;
      expect(newest).not.toBeNull();
      expect(document.querySelectorAll(".zc-region-overlay")).toHaveLength(1);

      plugin.regionCaptureDispose?.();
      expect(newest.isConnected).toBe(false);
    }
    finally {
      olderPage.remove();
      newerPage.remove();
    }
  });

  it("ignores a stale page-lookup rejection after a newer capture takes ownership", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const newerPage = document.createElement("div");
    document.body.appendChild(newerPage);
    const target = { reader: { id: "reader-b" }, pageIndex: 8, context: paperContext() };
    let rejectOlder!: (error: Error) => void;
    let resolveNewer!: (page: HTMLElement) => void;
    const olderLookup = new Promise<HTMLElement>((_resolve, reject) => { rejectOlder = reject; });
    const newerLookup = new Promise<HTMLElement>((resolve) => { resolveNewer = resolve; });
    plugin.readerContext = {
      getCaptureTargetPageViewElement: vi.fn()
        .mockReturnValueOnce(olderLookup)
        .mockReturnValueOnce(newerLookup),
    };

    try {
      const olderStart = plugin.startRegionScreenshot(target);
      const newerStart = plugin.startRegionScreenshot(target);
      resolveNewer(newerPage);
      await newerStart;
      rejectOlder(new Error("stale Reader lookup failed"));

      await expect(olderStart).resolves.toBeUndefined();
      expect(newerPage.querySelectorAll(".zc-region-overlay")).toHaveLength(1);
    }
    finally {
      plugin.regionCaptureDispose?.();
      newerPage.remove();
    }
  });

  it("does not install an overlay when shutdown wins a pending page lookup", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = {
      debug: vi.fn(),
      getMainWindows: () => [],
    };
    const plugin = new ZoteroChatPlugin() as any;
    const pageElement = document.createElement("div");
    document.body.appendChild(pageElement);
    const target = { reader: { id: "reader-b" }, pageIndex: 8, context: paperContext() };
    let resolvePage!: (page: HTMLElement) => void;
    const pendingPage = new Promise<HTMLElement>((resolve) => { resolvePage = resolve; });
    plugin.readerContext = {
      getCaptureTargetPageViewElement: vi.fn(() => pendingPage),
    };

    try {
      const start = plugin.startRegionScreenshot(target);
      await plugin.shutdown();
      resolvePage(pageElement);
      await start;

      expect(pageElement.querySelector(".zc-region-overlay")).toBeNull();
      expect(plugin.regionCaptureDispose).toBeNull();
    }
    finally {
      pageElement.remove();
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it.each([
    ["resolves", "resolve"],
    ["rejects", "reject"],
  ] as const)("keeps shutdown terminal when a pending region image render %s", async (_label, outcome) => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = {
      debug: vi.fn(),
      getMainWindows: () => [],
      logError: vi.fn(),
    };
    const plugin = new ZoteroChatPlugin() as any;
    const pageElement = document.createElement("div");
    document.body.appendChild(pageElement);
    pageElement.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 400, height: 600,
      right: 400, bottom: 600, x: 0, y: 0,
      toJSON: () => ({}),
    }) as DOMRect;
    const target = { reader: { id: "reader-b" }, pageIndex: 8, context: paperContext() };
    let resolveImage!: (image: string) => void;
    let rejectImage!: (error: Error) => void;
    const pendingImage = new Promise<string>((resolve, reject) => {
      resolveImage = resolve;
      rejectImage = reject;
    });
    plugin.readerContext = {
      getCaptureTargetPageViewElement: vi.fn(async () => pageElement),
      captureTargetRegionImage: vi.fn(() => pendingImage),
    };
    const focusComposer = vi.fn();
    plugin.visibleChatSurface = vi.fn(() => ({ kind: "workbench", focusComposer }));
    plugin.openResearchChat = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();
    plugin.chatError = "existing message";

    try {
      await plugin.startRegionScreenshot(target);
      const overlay = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;
      overlay.dispatchEvent(new MouseEvent("mousedown", {
        button: 0,
        clientX: 40,
        clientY: 60,
        bubbles: true,
      }));
      document.dispatchEvent(new MouseEvent("mouseup", {
        clientX: 140,
        clientY: 160,
        bubbles: true,
      }));
      expect(plugin.readerContext.captureTargetRegionImage).toHaveBeenCalledOnce();

      await plugin.shutdown();
      if (outcome === "resolve") resolveImage("data:image/png;base64,late-region");
      else rejectImage(new Error("late region render failed"));
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(plugin.pendingScreenshots).toEqual([]);
      expect(plugin.openResearchChat).not.toHaveBeenCalled();
      expect(plugin.renderChatViews).not.toHaveBeenCalled();
      expect(plugin.visibleChatSurface).not.toHaveBeenCalled();
      expect(focusComposer).not.toHaveBeenCalled();
      expect(plugin.chatError).toBe("existing message");
      expect((globalThis as any).Zotero.logError).not.toHaveBeenCalled();
    }
    finally {
      pageElement.remove();
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("retains Reader capture provenance on the completed region chip", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const plugin = new ZoteroChatPlugin() as any;
    const pageElement = document.createElement("div");
    document.body.appendChild(pageElement);
    pageElement.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 400, height: 600,
      right: 400, bottom: 600, x: 0, y: 0,
      toJSON: () => ({}),
    }) as DOMRect;
    const target = {
      reader: { id: "reader-b" },
      pageIndex: 8,
      context: {
        attachment: { key: "READER-B", libraryID: 1, title: "Paper B", creators: [] },
        parent: { title: "Paper B", creators: [], tags: [] },
        page: { pageIndex: 8, pageNumber: 9, pageLabel: "9" },
      },
    };
    plugin.context = {
      attachment: { key: "PLUGIN", libraryID: 2, title: "Plugin Paper", creators: [] },
      parent: { title: "Plugin Paper", creators: [], tags: [] },
      page: { pageIndex: 2, pageNumber: 3, pageLabel: "iii" },
    };
    plugin.codex = {
      state: { activeThreadId: null },
      getActiveReaderContext: () => ({
        attachment: { key: "CODEX", libraryID: 3, title: "Codex Paper", creators: [] },
        parent: { title: "Codex Paper", creators: [], tags: [] },
        page: { pageIndex: 20, pageNumber: 21, pageLabel: "A-21" },
      }),
    };
    plugin.readerContext = {
      getCaptureTargetPageViewElement: vi.fn(async () => pageElement),
      captureTargetRegionImage: vi.fn(async () => "data:image/png;base64,region"),
    };
    const workbenchHost = document.createElement("div");
    document.body.appendChild(workbenchHost);
    const main = {
      closed: false,
      document,
      Zotero_Tabs: { selectedID: "reader-b", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = { getMainWindow: () => main, logError: vi.fn() };
    plugin.workbenchTabs = {
      entries: vi.fn(() => [{ id: "workbench-1", host: workbenchHost, view: { focusComposer: vi.fn() } }]),
    };
    plugin.openResearchChat = vi.fn(async () => { main.Zotero_Tabs.selectedID = "workbench-1"; });
    plugin.renderChatViews = vi.fn();

    try {
      await plugin.startRegionScreenshot(target);
      const overlay = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;
      expect(overlay).not.toBeNull();
      overlay.dispatchEvent(new MouseEvent("mousedown", { button: 0, clientX: 40, clientY: 60, bubbles: true }));
      document.dispatchEvent(new MouseEvent("mouseup", { clientX: 140, clientY: 160, bubbles: true }));
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(plugin.readerContext.captureTargetRegionImage).toHaveBeenCalledWith(
        target,
        { rect: { x: 40, y: 60, width: 100, height: 100 }, view: { width: 400, height: 600 } },
      );
      expect(plugin.pendingScreenshots).toEqual([
        {
          image: "data:image/png;base64,region",
          kind: "region",
          source: {
            paperKey: "1-READER-B",
            paperTitle: "Paper B",
            pageIndex: 8,
            pageNumber: 9,
            pageLabel: "9",
          },
        },
      ]);
      expect(plugin.contextChips()).toEqual(expect.arrayContaining([
        expect.objectContaining({
          label: "Region · Paper B · p. 9",
          detail: "Captured from Paper B, PDF page 9",
        }),
      ]));
      expect(plugin.openResearchChat).toHaveBeenCalledWith(undefined, false);
    }
    finally {
      workbenchHost.remove();
      pageElement.remove();
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("opens the running-turn float when only a retained Workbench exists", () => {
    const previousZotero = (globalThis as any).Zotero;
    const mainDocument = document.implementation.createHTMLDocument("QLab running turn");
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: { selectedID: "reader-1", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = { getMainWindow: () => main };
    const plugin = new ZoteroChatPlugin() as any;
    const retainedHost = mainDocument.createElement("div");
    mainDocument.body.appendChild(retainedHost);
    plugin.codex = { state: { running: true } };
    plugin.workbenchTabs = { entries: vi.fn(() => [{ id: "workbench-1", host: retainedHost, view: {} }]) };
    plugin.standaloneWorkbench = { isActive: vi.fn(() => false) };
    plugin.currentTurnId = "turn-1";
    plugin.ensureFloatPanelOpen = vi.fn(async () => {});

    try {
      plugin.maybeAutoOpenFloatForRunningTurn();
      expect(plugin.ensureFloatPanelOpen).toHaveBeenCalledOnce();
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("opens the running-turn float for hidden standalone and non-visible sidebar hosts", () => {
    const previousZotero = (globalThis as any).Zotero;
    const mainDocument = document.implementation.createHTMLDocument("QLab running visibility");
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: { selectedID: "reader-1", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = { getMainWindow: () => main };
    const plugin = new ZoteroChatPlugin() as any;
    const standaloneDocument = document.implementation.createHTMLDocument("QLab hidden standalone");
    Object.defineProperty(standaloneDocument, "hidden", { configurable: true, value: true });
    const standaloneHost = standaloneDocument.createElement("div");
    standaloneHost.id = "qlab-standalone-workbench-host";
    standaloneDocument.body.appendChild(standaloneHost);
    const standalone = {
      closed: false,
      document: standaloneDocument,
      windowState: 0,
      STATE_MINIMIZED: 1,
    } as unknown as Window & { windowState: number; STATE_MINIMIZED: number };
    plugin.codex = { state: { running: true } };
    plugin.workbenchTabs = { entries: vi.fn(() => []) };
    plugin.standaloneWorkbench = {
      isActive: vi.fn(() => true),
      window: vi.fn(() => standalone),
      currentView: vi.fn(() => ({ focusComposer: vi.fn() })),
    };
    plugin.currentTurnId = "turn-1";
    plugin.ensureFloatPanelOpen = vi.fn(async () => {});
    const attempt = () => {
      plugin.autoOpenedFloatTurnId = null;
      plugin.floatDismissedTurnId = null;
      plugin.ensureFloatPanelOpen.mockClear();
      plugin.maybeAutoOpenFloatForRunningTurn();
      expect(plugin.ensureFloatPanelOpen).toHaveBeenCalledOnce();
    };

    try {
      attempt();

      Object.defineProperty(standaloneDocument, "hidden", { configurable: true, value: false });
      standalone.windowState = standalone.STATE_MINIMIZED;
      attempt();

      plugin.standaloneWorkbench.isActive.mockReturnValue(false);
      const details = mainDocument.createElement("item-details");
      details.setAttribute("data-tab-id", "reader-1");
      const section = mainDocument.createElement("collapsible-section");
      const body = mainDocument.createElement("div");
      section.appendChild(body);
      details.appendChild(section);
      mainDocument.body.appendChild(details);
      plugin.chatViews.set(body, { focusComposer: vi.fn() });
      attempt();

      section.setAttribute("open", "");
      main.Zotero_Tabs.selectedID = "reader-2";
      attempt();
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("keeps cancelled region selections out of crop and chat reveal paths", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const pageElement = document.createElement("div");
    document.body.appendChild(pageElement);
    pageElement.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 400, height: 600,
      right: 400, bottom: 600, x: 0, y: 0,
      toJSON: () => ({}),
    }) as DOMRect;
    const target = {
      reader: { id: "reader-b" }, pageIndex: 8,
      context: {
        attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
        parent: { title: "Paper", creators: [], tags: [] },
        page: { pageIndex: 8, pageNumber: 9, pageLabel: "9" },
      },
    };
    plugin.readerContext = {
      getCaptureTargetPageViewElement: vi.fn(async () => pageElement),
      captureTargetRegionImage: vi.fn(),
    };
    plugin.openResearchChat = vi.fn();
    plugin.renderChatViews = vi.fn();
    plugin.reportChatError = vi.fn();

    try {
      await plugin.startRegionScreenshot(target);
      let overlay = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));

      await plugin.startRegionScreenshot(target);
      overlay = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;
      overlay.dispatchEvent(new MouseEvent("mousedown", { button: 0, clientX: 40, clientY: 60, bubbles: true }));
      document.dispatchEvent(new MouseEvent("mouseup", { clientX: 44, clientY: 64, bubbles: true }));

      expect(plugin.readerContext.captureTargetRegionImage).not.toHaveBeenCalled();
      expect(plugin.openResearchChat).not.toHaveBeenCalled();
      expect(plugin.renderChatViews).not.toHaveBeenCalled();
      expect(plugin.reportChatError).not.toHaveBeenCalled();
    }
    finally {
      plugin.regionCaptureDispose?.();
      pageElement.remove();
    }
  });

  it("replaces a disconnected float when a running turn needs a visible surface", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const mainDocument = document.implementation.createHTMLDocument("QLab stale float");
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: { selectedID: "reader-1", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = { getMainWindow: () => main };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = { state: { running: true } };
    plugin.workbenchTabs = { entries: vi.fn(() => []) };
    plugin.standaloneWorkbench = { isActive: vi.fn(() => false) };
    plugin.currentTurnId = "turn-1";
    const staleHost = mainDocument.createElement("div");
    const destroy = vi.fn();
    plugin.floatPanels.set(main, {
      host: staleHost,
      view: { destroy, isVisible: vi.fn(() => true) },
      focusReturn: null,
    });
    const replacementHost = mainDocument.createElement("div");
    mainDocument.body.appendChild(replacementHost);
    plugin.openFloatPanel = vi.fn(async () => {
      plugin.floatPanels.set(main, {
        host: replacementHost,
        view: { isVisible: vi.fn(() => true) },
        focusReturn: null,
      });
    });

    try {
      plugin.maybeAutoOpenFloatForRunningTurn();
      await vi.waitFor(() => expect(plugin.openFloatPanel).toHaveBeenCalledWith(main));
      expect(destroy).toHaveBeenCalledOnce();
      expect(plugin.floatPanels.get(main).host).toBe(replacementHost);
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("refreshes page context only while a chat surface is visible", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const mainDocument = document.implementation.createHTMLDocument("QLab page observer");
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: { selectedID: "reader-1", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    let observer: any;
    (globalThis as any).Zotero = {
      getMainWindow: () => main,
      Notifier: {
        registerObserver: vi.fn((next: any) => { observer = next; return "observer-1"; }),
      },
    };
    const plugin = new ZoteroChatPlugin() as any;
    const retainedHost = mainDocument.createElement("div");
    mainDocument.body.appendChild(retainedHost);
    plugin.workbenchTabs = {
      entries: vi.fn(() => [{ id: "workbench-1", host: retainedHost, view: { focusComposer: vi.fn() } }]),
    };
    plugin.standaloneWorkbench = { isActive: vi.fn(() => false) };
    plugin.terminal = { isOpen: false };
    plugin.refreshContext = vi.fn(async () => {});

    vi.useFakeTimers();
    try {
      plugin.registerPageObserver();
      observer.notify("pageChange", "file", [1]);
      await vi.advanceTimersByTimeAsync(800);
      expect(plugin.refreshContext).not.toHaveBeenCalled();

      main.Zotero_Tabs.selectedID = "workbench-1";
      main.Zotero_Tabs.selectedType = "qlab";
      observer.notify("pageChange", "file", [1]);
      await vi.advanceTimersByTimeAsync(800);
      expect(plugin.refreshContext).toHaveBeenCalledWith(true);
    }
    finally {
      vi.useRealTimers();
      (globalThis as any).Zotero = previousZotero;
    }
  });
});

describe("visible chat surfaces", () => {
  it("does not reveal a Workbench when shutdown wins a pending capture refresh", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const mainDocument = document.implementation.createHTMLDocument("QLab reveal race");
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: { selectedID: "reader-1", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = {
      debug: vi.fn(),
      getMainWindow: () => main,
      getMainWindows: () => [main],
      Session: { debounceSave: vi.fn() },
    };
    const plugin = new ZoteroChatPlugin() as any;
    let releaseRefresh!: () => void;
    const refreshPending = new Promise<void>((resolve) => { releaseRefresh = resolve; });
    const focusComposer = vi.fn();
    plugin.readerContext = {
      captureTargetRegionImage: vi.fn(async () => "data:image/png;base64,region"),
    };
    plugin.refreshContext = vi.fn(() => refreshPending);
    plugin.workbenchTabs = {
      entries: vi.fn(() => []),
      open: vi.fn(() => ({
        id: "workbench-1",
        host: mainDocument.createElement("div"),
        view: { focusComposer },
      })),
      uninstall: vi.fn(),
    };
    plugin.terminal = { setVisible: vi.fn(), destroy: vi.fn() };
    plugin.codex = { state: { connected: true }, stop: vi.fn() };
    plugin.bridge = { stop: vi.fn(async () => {}) };
    plugin.renderChatViews = vi.fn();
    plugin.reportError = vi.fn();
    plugin.reportChatError = vi.fn();
    const target = {
      reader: { id: "reader-1" }, pageIndex: 8,
      context: {
        attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
        parent: { title: "Paper", creators: [], tags: [] },
        page: { pageIndex: 8, pageNumber: 9, pageLabel: "9" },
      },
    };

    try {
      const finishing = plugin.finishRegionScreenshot(
        { rect: { x: 40, y: 60, width: 100, height: 100 }, view: { width: 400, height: 600 } },
        target,
      );
      await vi.waitFor(() => expect(plugin.refreshContext).toHaveBeenCalledOnce());

      await plugin.shutdown();
      releaseRefresh();
      await expect(finishing).resolves.toBeUndefined();

      expect(plugin.workbenchTabs.open).not.toHaveBeenCalled();
      expect(plugin.renderChatViews).not.toHaveBeenCalled();
      expect(focusComposer).not.toHaveBeenCalled();
      expect(plugin.reportChatError).not.toHaveBeenCalled();
      expect(plugin.reportError).not.toHaveBeenCalled();
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("does not report a reveal rejection after shutdown wins region capture", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const mainDocument = document.implementation.createHTMLDocument("QLab rejected reveal race");
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: { selectedID: "reader-1", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = {
      debug: vi.fn(),
      logError: vi.fn(),
      getMainWindow: () => main,
      getMainWindows: () => [main],
      Session: { debounceSave: vi.fn() },
    };
    const plugin = new ZoteroChatPlugin() as any;
    const pageElement = mainDocument.createElement("div");
    mainDocument.body.appendChild(pageElement);
    pageElement.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 400, height: 600,
      right: 400, bottom: 600, x: 0, y: 0,
      toJSON: () => ({}),
    }) as DOMRect;
    let rejectRefresh!: (error: Error) => void;
    const refreshPending = new Promise<void>((_resolve, reject) => { rejectRefresh = reject; });
    const focusComposer = vi.fn();
    plugin.readerContext = {
      getCaptureTargetPageViewElement: vi.fn(async () => pageElement),
      captureTargetRegionImage: vi.fn(async () => "data:image/png;base64,region"),
    };
    plugin.refreshContext = vi.fn(() => refreshPending);
    plugin.workbenchTabs = {
      entries: vi.fn(() => []),
      open: vi.fn(() => ({
        id: "workbench-1",
        host: mainDocument.createElement("div"),
        view: { focusComposer },
      })),
      uninstall: vi.fn(),
    };
    plugin.terminal = { setVisible: vi.fn(), destroy: vi.fn() };
    plugin.codex = { state: { connected: true }, stop: vi.fn() };
    plugin.bridge = { stop: vi.fn(async () => {}) };
    plugin.renderChatViews = vi.fn();
    plugin.chatError = "existing message";
    const reportError = vi.spyOn(plugin, "reportError");
    const target = {
      reader: { id: "reader-1" }, pageIndex: 8,
      context: {
        attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
        parent: { title: "Paper", creators: [], tags: [] },
        page: { pageIndex: 8, pageNumber: 9, pageLabel: "9" },
      },
    };

    try {
      await plugin.startRegionScreenshot(target);
      const overlay = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;
      overlay.dispatchEvent(new MouseEvent("mousedown", {
        button: 0,
        clientX: 40,
        clientY: 60,
        bubbles: true,
      }));
      mainDocument.dispatchEvent(new MouseEvent("mouseup", {
        clientX: 140,
        clientY: 160,
        bubbles: true,
      }));
      await vi.waitFor(() => expect(plugin.refreshContext).toHaveBeenCalledOnce());

      await plugin.shutdown();
      rejectRefresh(new Error("Reader refresh failed after shutdown"));
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(reportError).not.toHaveBeenCalled();
      expect(plugin.workbenchTabs.open).not.toHaveBeenCalled();
      expect(plugin.renderChatViews).not.toHaveBeenCalled();
      expect(focusComposer).not.toHaveBeenCalled();
      expect(plugin.chatError).toBe("");
      expect((globalThis as any).Zotero.logError).not.toHaveBeenCalled();
    }
    finally {
      pageElement.remove();
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("preserves a reveal rejection while the plugin is still live", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const mainDocument = document.implementation.createHTMLDocument("QLab live reveal failure");
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: { selectedID: "reader-1", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = { getMainWindow: () => main };
    const plugin = new ZoteroChatPlugin() as any;
    const original = new Error("live Workbench reveal failed");
    plugin.workbenchTabs = { entries: vi.fn(() => []) };
    plugin.standaloneWorkbench = { isActive: vi.fn(() => false) };
    plugin.openResearchChat = vi.fn(async () => { throw original; });

    try {
      await expect(plugin.ensureCaptureChatSurface()).rejects.toBe(original);
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("classifies only visible chat surfaces", () => {
    const previousZotero = (globalThis as any).Zotero;
    const documentFor = () => document.implementation.createHTMLDocument("QLab surface");
    const mainDocument = documentFor();
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: {
        selectedID: "workbench-1",
        selectedType: "qlab",
        parseTabType: vi.fn((type: string) => ({ tabContentType: type })),
      },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = { getMainWindow: () => main };
    const plugin = new ZoteroChatPlugin() as any;
    const workbenchHost = mainDocument.createElement("div");
    mainDocument.body.appendChild(workbenchHost);
    const workbenchFocus = vi.fn();
    const standaloneDocument = documentFor();
    Object.defineProperty(standaloneDocument, "hidden", { configurable: true, value: false });
    const standaloneHost = standaloneDocument.createElement("div");
    standaloneHost.id = "qlab-standalone-workbench-host";
    standaloneDocument.body.appendChild(standaloneHost);
    const standalone = {
      closed: false,
      document: standaloneDocument,
      windowState: 0,
      STATE_MINIMIZED: 1,
    } as unknown as Window & { windowState: number; STATE_MINIMIZED: number };
    const standaloneFocus = vi.fn();
    const standaloneView = { focusComposer: standaloneFocus };
    const floatHost = mainDocument.createElement("div");
    mainDocument.body.appendChild(floatHost);
    const floatFocus = vi.fn();
    const floatVisible = vi.fn(() => true);
    const sidebarDetails = mainDocument.createElement("item-details");
    sidebarDetails.setAttribute("data-tab-id", "reader-1");
    const sidebarSection = mainDocument.createElement("collapsible-section");
    sidebarSection.setAttribute("open", "");
    const sidebarBody = mainDocument.createElement("div");
    sidebarSection.appendChild(sidebarBody);
    sidebarDetails.appendChild(sidebarSection);
    mainDocument.body.appendChild(sidebarDetails);
    const sidebarFocus = vi.fn();

    plugin.workbenchTabs = {
      entries: vi.fn(() => [{ id: "workbench-1", host: workbenchHost, view: { focusComposer: workbenchFocus } }]),
    };
    plugin.standaloneWorkbench = {
      isActive: vi.fn(() => true),
      window: vi.fn(() => standalone),
      currentView: vi.fn(() => standaloneView),
    };
    plugin.floatPanels.set(main, {
      host: floatHost,
      view: { isVisible: floatVisible, focusComposer: floatFocus },
      focusReturn: null,
    });
    plugin.chatViews.set(sidebarBody, { focusComposer: sidebarFocus });

    try {
      expect(plugin.visibleChatSurface()).toMatchObject({ kind: "workbench" });

      workbenchHost.remove();
      expect(plugin.visibleChatSurface()).toMatchObject({ kind: "standalone" });

      main.Zotero_Tabs.selectedID = "reader-1";
      main.Zotero_Tabs.selectedType = "reader";
      expect(plugin.visibleChatSurface()).toMatchObject({ kind: "standalone" });

      delete (standalone as any).windowState;
      delete (standalone as any).STATE_MINIMIZED;
      expect(plugin.visibleChatSurface()).toMatchObject({ kind: "standalone" });
      standalone.windowState = 0;
      standalone.STATE_MINIMIZED = 1;

      (standalone as any).closed = true;
      expect(plugin.visibleChatSurface()).toMatchObject({ kind: "float" });
      (standalone as any).closed = false;
      standaloneHost.remove();
      expect(plugin.visibleChatSurface()).toMatchObject({ kind: "float" });
      standaloneDocument.body.appendChild(standaloneHost);
      plugin.standaloneWorkbench.currentView.mockReturnValue(null);
      expect(plugin.visibleChatSurface()).toMatchObject({ kind: "float" });
      plugin.standaloneWorkbench.currentView.mockReturnValue(standaloneView);

      Object.defineProperty(standaloneDocument, "hidden", { configurable: true, value: true });
      expect(plugin.visibleChatSurface()).toMatchObject({ kind: "float" });
      Object.defineProperty(standaloneDocument, "hidden", { configurable: true, value: false });
      standalone.windowState = standalone.STATE_MINIMIZED;
      expect(plugin.visibleChatSurface()).toMatchObject({ kind: "float" });

      standalone.windowState = 0;
      Object.defineProperty(standaloneDocument, "hidden", { configurable: true, value: true });
      floatVisible.mockReturnValue(false);
      expect(plugin.visibleChatSurface()).toBeNull();
      floatVisible.mockReturnValue(true);
      floatHost.remove();
      expect(plugin.visibleChatSurface()).toBeNull();

      plugin.standaloneWorkbench.isActive.mockReturnValue(false);
      expect(plugin.visibleChatSurface()).toMatchObject({ kind: "reader-sidebar" });
      plugin.chatViews.delete(sidebarBody);
      expect(plugin.visibleChatSurface()).toBeNull();
      plugin.chatViews.set(sidebarBody, { focusComposer: sidebarFocus });
      sidebarDetails.remove();
      expect(plugin.visibleChatSurface()).toBeNull();
      mainDocument.body.appendChild(sidebarDetails);
      main.Zotero_Tabs.selectedType = "library";
      expect(plugin.visibleChatSurface()).toBeNull();
      main.Zotero_Tabs.selectedType = "reader";
      sidebarSection.removeAttribute("open");
      expect(plugin.visibleChatSurface()).toBeNull();
      sidebarSection.setAttribute("open", "");
      main.Zotero_Tabs.selectedID = "reader-2";
      expect(plugin.visibleChatSurface()).toBeNull();
      main.Zotero_Tabs.selectedID = "reader-1";
      plugin.standaloneWorkbench.isActive.mockReturnValue(true);
      expect(plugin.visibleChatSurface()).toBeNull();
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("reveals a retained Workbench before focusing a completed region capture", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const mainDocument = document.implementation.createHTMLDocument("QLab capture");
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: { selectedID: "reader-1", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = { getMainWindow: () => main };
    const plugin = new ZoteroChatPlugin() as any;
    const host = mainDocument.createElement("div");
    mainDocument.body.appendChild(host);
    const focusComposer = vi.fn();
    plugin.workbenchTabs = {
      entries: vi.fn(() => [{ id: "workbench-1", host, view: { focusComposer } }]),
    };
    plugin.readerContext = { captureTargetRegionImage: vi.fn(async () => "data:image/png;base64,region") };
    plugin.renderChatViews = vi.fn();
    plugin.openResearchChat = vi.fn(async () => {
      expect(focusComposer).not.toHaveBeenCalled();
      main.Zotero_Tabs.selectedID = "workbench-1";
      main.Zotero_Tabs.selectedType = "qlab";
    });
    const target = {
      reader: { id: "reader-b" }, pageIndex: 8,
      context: {
        attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
        parent: { title: "Paper", creators: [], tags: [] },
        page: { pageIndex: 8, pageNumber: 9, pageLabel: "9" },
      },
    };

    try {
      await plugin.finishRegionScreenshot(
        { rect: { x: 40, y: 60, width: 100, height: 100 }, view: { width: 400, height: 600 } },
        target,
      );

      expect(plugin.openResearchChat).toHaveBeenCalledWith(undefined, false);
      expect(plugin.workbenchTabs.entries).toHaveBeenCalledWith(main);
      expect(plugin.pendingScreenshots).toEqual([expect.objectContaining({
        image: "data:image/png;base64,region",
        kind: "region",
      })]);
      expect(plugin.renderChatViews).toHaveBeenCalledOnce();
      expect(focusComposer).toHaveBeenCalledOnce();
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("renders before focusing an already-visible float after region capture", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const mainDocument = document.implementation.createHTMLDocument("QLab float capture");
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: { selectedID: "reader-1", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = { getMainWindow: () => main };
    const plugin = new ZoteroChatPlugin() as any;
    const floatHost = mainDocument.createElement("div");
    mainDocument.body.appendChild(floatHost);
    const focusComposer = vi.fn();
    plugin.workbenchTabs = { entries: vi.fn(() => []) };
    plugin.standaloneWorkbench = { isActive: vi.fn(() => false) };
    plugin.floatPanels.set(main, {
      host: floatHost,
      view: { isVisible: vi.fn(() => true), focusComposer },
      focusReturn: null,
    });
    plugin.readerContext = {
      captureTargetRegionImage: vi.fn(async () => "data:image/png;base64,float-region"),
    };
    plugin.openResearchChat = vi.fn();
    plugin.renderChatViews = vi.fn();
    const target = {
      reader: { id: "reader-1" }, pageIndex: 8,
      context: {
        attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
        parent: { title: "Paper", creators: [], tags: [] },
        page: { pageIndex: 8, pageNumber: 9, pageLabel: "9" },
      },
    };

    try {
      await plugin.finishRegionScreenshot(
        { rect: { x: 40, y: 60, width: 100, height: 100 }, view: { width: 400, height: 600 } },
        target,
      );

      expect(plugin.openResearchChat).not.toHaveBeenCalled();
      expect(plugin.renderChatViews).toHaveBeenCalledOnce();
      expect(focusComposer).toHaveBeenCalledOnce();
      expect(plugin.renderChatViews.mock.invocationCallOrder[0]!)
        .toBeLessThan(focusComposer.mock.invocationCallOrder[0]!);
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it.each([
    ["rejection", () => Promise.reject(new Error("original crop failure"))],
    ["null image", () => Promise.resolve(null)],
  ])("reports a region %s inside chat after reveal", async (_label, capture) => {
    const previousZotero = (globalThis as any).Zotero;
    const mainDocument = document.implementation.createHTMLDocument("QLab capture error");
    const main = {
      closed: false,
      document: mainDocument,
      Zotero_Tabs: { selectedID: "reader-1", selectedType: "reader" },
    } as unknown as Window & { Zotero_Tabs: any };
    (globalThis as any).Zotero = { getMainWindow: () => main, logError: vi.fn() };
    const plugin = new ZoteroChatPlugin() as any;
    const host = mainDocument.createElement("div");
    mainDocument.body.appendChild(host);
    const focusComposer = vi.fn();
    plugin.workbenchTabs = { entries: vi.fn(() => [{ id: "workbench-1", host, view: { focusComposer } }]) };
    plugin.readerContext = { captureTargetRegionImage: vi.fn(capture) };
    plugin.renderChatViews = vi.fn();
    plugin.paneMode = "terminal";
    plugin.openResearchChat = vi.fn(async () => { main.Zotero_Tabs.selectedID = "workbench-1"; });
    const target = {
      reader: { id: "reader-b" }, pageIndex: 8,
      context: {
        attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
        parent: { title: "Paper", creators: [], tags: [] },
        page: { pageIndex: 8, pageNumber: 9, pageLabel: "9" },
      },
    };

    try {
      await plugin.finishRegionScreenshot(
        { rect: { x: 40, y: 60, width: 100, height: 100 }, view: { width: 400, height: 600 } },
        target,
      );

      expect(plugin.pendingScreenshots).toEqual([]);
      expect(plugin.openResearchChat).toHaveBeenCalledOnce();
      expect(plugin.chatError).toBe(_label === "rejection"
        ? "original crop failure"
        : "Zotero could not render the selected PDF region as an image");
      expect(plugin.renderChatViews).toHaveBeenCalledOnce();
      expect(focusComposer).toHaveBeenCalledOnce();
      expect(plugin.renderChatViews.mock.invocationCallOrder[0]!)
        .toBeLessThan(focusComposer.mock.invocationCallOrder[0]!);
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });
});

describe("QLab paper conversation reopening", () => {
  it("seeds a paper context by opening its PDF in a background Reader tab", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const context = { attachment: { key: "ATTACH", libraryID: 1 }, workspace: { root: "/w" } };
    const attachment = { id: 7, key: "ATTACH", libraryID: 1, isPDFAttachment: () => true };
    const open = vi.fn(async () => ({ itemID: 7 }));
    const win = {
      setTimeout: (fn: () => void) => setTimeout(fn, 0),
      Zotero_Tabs: { selectedID: "zotero-pane" },
    } as unknown as Window & { Zotero_Tabs: { selectedID: string } };
    (globalThis as any).Zotero = {
      Items: { getByLibraryAndKeyAsync: vi.fn(async () => attachment) },
      Reader: { open },
      getMainWindow: () => win,
    };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.readerContext = { acceptReaderHook: vi.fn(async () => context) };

    try {
      await expect(plugin.seedPaperContextForKey("1-ATTACH")).resolves.toBe(context);
      expect((globalThis as any).Zotero.Items.getByLibraryAndKeyAsync).toHaveBeenCalledWith(1, "ATTACH");
      expect(open).toHaveBeenCalledWith(7, null, expect.objectContaining({
        allowDuplicate: false,
        openInBackground: true,
        preventJumpback: true,
      }));
      expect(win.Zotero_Tabs.selectedID).toBe("zotero-pane");
      expect(plugin.readerContext.acceptReaderHook).toHaveBeenCalledWith({
        reader: { itemID: 7 },
        item: attachment,
        params: {},
      });
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("rejects seeding for an item with no readable PDF attachment", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const item = {
      isPDFAttachment: () => false,
      isRegularItem: () => true,
      getBestAttachment: async () => null,
    };
    (globalThis as any).Zotero = {
      Items: { getByLibraryAndKeyAsync: vi.fn(async () => item) },
      Reader: { open: vi.fn() },
      getMainWindow: () => ({}) as Window,
    };
    const plugin = new ZoteroChatPlugin() as any;

    try {
      await expect(plugin.seedPaperContextForKey("1-NOPDF"))
        .rejects.toThrow("This Zotero item has no readable PDF attachment");
      expect((globalThis as any).Zotero.Reader.open).not.toHaveBeenCalled();
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("supplies the background seeding hook to the codex service at startup", () => {
    const plugin = readFileSync(join(process.cwd(), "src/plugin.ts"), "utf8");
    const startup = plugin.slice(
      plugin.indexOf("async startup("),
      plugin.indexOf("async shutdown("),
    );
    expect(startup).toContain("seedPaperContext: (paperKey) => this.seedPaperContextForKey(paperKey)");
  });

  it("injects Open QLab Chat for This Paper into the library item context menu", () => {
    const plugin = new ZoteroChatPlugin() as any;
    const doc = document.implementation.createHTMLDocument("Main");
    (doc as any).createXULElement = (name: string) => doc.createElement(name);
    const toolsPopup = doc.createElement("menupopup");
    toolsPopup.id = "menu_ToolsPopup";
    const itemPopup = doc.createElement("menupopup");
    itemPopup.id = "zotero-itemmenu";
    doc.body.append(toolsPopup, itemPopup);
    const item = { id: 6, isPDFAttachment: () => false, isRegularItem: () => true };
    const win = {
      document: doc,
      ZoteroPane: { getSelectedItems: () => [item] },
    } as unknown as Window;
    plugin.openConversationForItem = vi.fn(async () => {});

    plugin.installQLabMenu(win);

    const menuItem = doc.getElementById("qlab-zotero-open-paper-chat");
    expect(menuItem).not.toBeNull();
    expect(menuItem?.getAttribute("label")).toBe("Open QLab Chat for This Paper");
    menuItem?.dispatchEvent(new Event("command"));
    expect(plugin.openConversationForItem).toHaveBeenCalledWith(win, item);

    plugin.removeQLabMenu(win);
    expect(doc.getElementById("qlab-zotero-open-paper-chat")).toBeNull();
  });

  it("shows a no-PDF library-menu error without changing the foreground conversation", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const originalServices = (globalThis as any).Services;
    const plugin = new ZoteroChatPlugin() as any;
    const doc = document.implementation.createHTMLDocument("Main");
    (doc as any).createXULElement = (name: string) => doc.createElement(name);
    const toolsPopup = doc.createElement("menupopup");
    toolsPopup.id = "menu_ToolsPopup";
    const itemPopup = doc.createElement("menupopup");
    itemPopup.id = "zotero-itemmenu";
    doc.body.append(toolsPopup, itemPopup);
    const item = {
      isPDFAttachment: () => false,
      isRegularItem: () => true,
      getBestAttachment: vi.fn(async () => null),
    };
    const win = {
      document: doc,
      ZoteroPane: { getSelectedItems: () => [item] },
      Zotero_Tabs: { selectedID: "zotero-pane" },
    } as unknown as Window & { Zotero_Tabs: { selectedID: string } };
    const originalContext = {
      attachment: { key: "CURRENT", libraryID: 1, title: "Current PDF", creators: [] },
      parent: { title: "Current Paper", creators: [], tags: [] },
      page: { pageIndex: 0, pageNumber: 1, pageLabel: "1" },
    };
    plugin.context = originalContext;
    plugin.codex = {
      state: { activeThreadId: "thread-current" },
      openConversationForPaper: vi.fn(async () => {}),
    };
    plugin.openWorkbenchTab = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();
    const alert = vi.fn();
    (globalThis as any).Zotero = { logError: vi.fn() };
    (globalThis as any).Services = { prompt: { alert } };

    try {
      plugin.installQLabMenu(win);
      doc.getElementById("qlab-zotero-open-paper-chat")!
        .dispatchEvent(new Event("command"));

      await vi.waitFor(() => {
        expect(plugin.chatError).toBe("This Zotero item has no readable PDF attachment");
      });

      expect(plugin.renderChatViews).toHaveBeenCalled();
      expect(alert).toHaveBeenCalledWith(
        win,
        "QLab Chat",
        "This Zotero item has no readable PDF attachment",
      );
      expect(plugin.openWorkbenchTab).not.toHaveBeenCalled();
      expect(plugin.codex.openConversationForPaper).not.toHaveBeenCalled();
      expect(plugin.codex.state.activeThreadId).toBe("thread-current");
      expect(plugin.context).toBe(originalContext);
      expect(win.Zotero_Tabs.selectedID).toBe("zotero-pane");
    }
    finally {
      plugin.removeQLabMenu(win);
      (globalThis as any).Zotero = originalZotero;
      (globalThis as any).Services = originalServices;
    }
  });

  it("shows no-PDF failures from local tabs, local History, and global History in the mounted chat", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const entries = ["local tab", "local History", "global History"] as const;

    try {
      for (const entry of entries) {
        const doc = document.implementation.createHTMLDocument(entry);
        const host = doc.createElement("div");
        doc.body.appendChild(host);
        const win = {
          document: doc,
          Zotero_Tabs: { selectedID: "reader-current", selectedType: "reader" },
        } as unknown as Window & { Zotero_Tabs: { selectedID: string; selectedType: string } };
        (globalThis as any).Zotero = { getMainWindow: () => win, logError: vi.fn() };

        const plugin = new ZoteroChatPlugin() as any;
        const originalContext = {
          attachment: { key: "CURRENT", libraryID: 1, title: "Current PDF", creators: [] },
          parent: { title: "Current Paper", creators: [], tags: [] },
          page: { pageIndex: 0, pageNumber: 1, pageLabel: "1" },
        };
        const failure = new Error("This Zotero item has no readable PDF attachment");
        const switchThread = vi.fn(async () => { throw failure; });
        const openGlobalThread = vi.fn(async () => { throw failure; });
        plugin.context = originalContext;
        plugin.chatPhase = "ready";
        plugin.terminal = { unmount: vi.fn() };
        plugin.codex = {
          state: {
            activeThreadId: "thread-current",
            activeTurnId: null,
            switchingThreadId: null,
            connected: true,
            running: false,
            creatingThread: false,
            fallbackReason: null,
            models: [],
            capabilities: { supportsAgentMode: true, supportsLogin: true },
            mode: "agent",
          },
          accountLabel: () => "Test account",
          isSignedIn: () => true,
          getActiveReaderContext: () => originalContext,
          getActivePlan: () => null,
          getActiveDiffs: () => [],
          getPendingApprovals: () => [],
          getCheckpoints: () => [],
          getChatEntries: () => [],
          getGlobalHistoryState: () => ({ loading: false, hasMore: false, error: "", query: "" }),
          getGlobalHistory: () => [{
            id: "thread-target",
            title: "Target paper",
            updatedAt: "2026-07-30T00:00:00.000Z",
            source: "codex",
            sourceLabel: "Codex CLI",
            pinned: false,
          }],
          getThreadOptions: () => [
            {
              id: "thread-current",
              title: "Current paper",
              paperTitle: "Current paper",
              updatedAt: "2026-07-31T00:00:00.000Z",
              active: true,
            },
            {
              id: "thread-target",
              title: "Target paper",
              paperTitle: "Target paper",
              updatedAt: "2026-07-30T00:00:00.000Z",
              active: false,
            },
          ],
          switchThread,
          openGlobalThread,
        };

        const view = entry === "global History"
          ? plugin.createWorkbenchView(host, win, "workbench")
          : plugin.mountChat(host);
        if (entry === "global History") {
          plugin.chatViews.set(host, view);
          plugin.renderChatViews();
          host.querySelector<HTMLButtonElement>(".zc-history-open")!.click();
        }
        else if (entry === "local History") {
          host.querySelector<HTMLButtonElement>('button[title="Conversation History"]')!.click();
          const target = [...host.querySelectorAll<HTMLButtonElement>(".zc-history-menu-item > button")]
            .find((button) => button.textContent?.includes("Target paper"));
          target!.click();
        }
        else {
          host.querySelector<HTMLButtonElement>('[data-thread-id="thread-target"]')!.click();
        }

        await vi.waitFor(() => {
          expect(host.querySelector(".zc-status-area.is-error")?.textContent, entry)
            .toBe(failure.message);
        });

        expect(entry === "global History" ? openGlobalThread : switchThread, entry)
          .toHaveBeenCalledWith("thread-target");
        expect(plugin.codex.state.activeThreadId, entry).toBe("thread-current");
        expect(plugin.context, entry).toBe(originalContext);
        expect(win.Zotero_Tabs.selectedID, entry).toBe("reader-current");
        view.destroy();
        plugin.chatViews.delete(host);
        host.remove();
      }
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("opens the stored conversation for a right-clicked library item through the codex service", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const attachment = { id: 7, key: "ATTACH", libraryID: 1, isPDFAttachment: () => true };
    const item = {
      isPDFAttachment: () => false,
      isRegularItem: () => true,
      getBestAttachment: async () => attachment,
    };
    const openConversationForPaper = vi.fn(async () => {});
    plugin.codex = { openConversationForPaper };
    plugin.openWorkbenchTab = vi.fn(async () => {});
    plugin.updateInteractionContext = vi.fn();
    plugin.renderChatViews = vi.fn();
    plugin.selectedWorkbenchEntry = vi.fn(() => null);
    const win = {} as Window;

    await plugin.openConversationForItem(win, item);

    expect(plugin.openWorkbenchTab).toHaveBeenCalledWith(win);
    expect(openConversationForPaper).toHaveBeenCalledWith("1-ATTACH");
    expect(plugin.renderChatViews).toHaveBeenCalled();
  });
});
