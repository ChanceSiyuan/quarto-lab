import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CodexService } from "../src/codex-service";
import { READER_CONTEXT_TOOLS, READER_TOOL_NAMES } from "../src/reader-context";
import type { ReaderContext, ReaderContextService } from "../src/reader-context";
import type { NativeBridge } from "../src/native-bridge";
import { ZOTERO_MUTATION_TOOL, ZoteroMutationService } from "../src/zotero-mutations";
import {
  ANNOTATION_PROPOSAL_TOOL,
  AnnotationProposalService,
} from "../src/annotation-proposals";
import {
  NOTE_FROM_QMD_TOOL,
  NoteDraftBridgeService,
} from "../src/note-draft-bridge";

beforeEach(() => {
  vi.stubGlobal("Services", {
    uuid: { generateUUID: () => "{codex-service-test}" },
  });
});

afterEach(() => vi.unstubAllGlobals());

function paperContext(): ReaderContext {
  return {
    schemaVersion: 1,
    capturedAt: "2026-07-22T00:00:00.000Z",
    attachment: {
      id: 7,
      key: "ATTACH",
      libraryID: 1,
      title: "Paper PDF",
      filename: "paper.pdf",
      creators: [],
      tags: []
    },
    parent: {
      id: 6,
      key: "PARENT",
      libraryID: 1,
      title: "A Paper",
      creators: [],
      tags: []
    },
    pdfPath: "/papers/paper.pdf",
    page: {
      pageIndex: 2,
      pageNumber: 3,
      pageLabel: "3",
      text: "Current page",
      source: "pdfjs",
      warnings: []
    },
    selection: {
      text: "Selected theorem",
      pageIndex: 2,
      pageNumber: 3,
      capturedAt: "2026-07-22T00:00:00.000Z"
    },
    fullText: { source: "indexed-fulltext", characters: 1000 },
    workspace: {
      root: "/profile/papers/1-ATTACH",
      context: "/profile/papers/1-ATTACH/context.json",
      currentPage: "/profile/papers/1-ATTACH/current-page.md",
      currentSelection: "/profile/papers/1-ATTACH/current-selection.md",
      pdfText: "/profile/papers/1-ATTACH/current-pdf-text.txt",
      agents: "/profile/papers/1-ATTACH/AGENTS.md",
    },
    warnings: []
  };
}

function serviceWithClient(client: Record<string, unknown>) {
  const callbacks = { onState: vi.fn(), onError: vi.fn() };
  const service = new CodexService(
    {} as NativeBridge,
    { tools: [] } as unknown as ReaderContextService,
    "test",
    callbacks
  );
  const internal = service as any;
  internal.client = client;
  internal.activeContext = paperContext();
  internal.activePaperKey = "1-ATTACH";
  internal.threadPaperKeys.set("thread-a", "1-ATTACH");
  service.state.connected = true;
  service.state.activeThreadId = "thread-a";
  return { service, callbacks };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("CodexService follow-up turns", () => {
  it("starts a repository-scoped object conversation without requiring an open PDF", async () => {
    const client = {
      threadStart: vi.fn().mockResolvedValue({ thread: { id: "thread-object" } }),
      threadSetName: vi.fn(async () => ({})),
      turnStart: vi.fn().mockResolvedValue({ turn: { id: "turn-object" } }),
    };
    const callbacks = { onState: vi.fn(), onError: vi.fn() };
    const service = new CodexService(
      {} as NativeBridge,
      { tools: [] } as unknown as ReaderContextService,
      "test",
      callbacks,
    );
    const internal = service as any;
    internal.client = client;
    internal.saveSessions = vi.fn(async () => undefined);
    service.state.connected = true;

    await service.setWorkspaceObject({
      kind: "collection",
      key: "collection:ABC123",
      title: "Quantum Algorithms",
      workspaceRoot: "/Users/test/research-loop",
      libraryID: 1,
    });
    await service.send("Summarize this collection.", "gpt-5.6-sol", "high");

    expect(client.threadStart).toHaveBeenCalledWith(expect.objectContaining({
      cwd: "/Users/test/research-loop",
      runtimeWorkspaceRoots: ["/Users/test/research-loop"],
    }));
    const turn = client.turnStart.mock.calls[0]![0];
    expect(turn.additionalContext["Research object"]).toMatchObject({
      kind: "application",
      value: expect.stringContaining("Quantum Algorithms"),
    });
    expect(turn.additionalContext["Zotero Reader"]).toBeUndefined();
  });

  it("publishes an immediate switching state and clears it after the selected conversation is ready", async () => {
    const resumed = deferred<{ thread: { id: string; turns: never[] } }>();
    const client = {
      threadResume: vi.fn(() => resumed.promise),
      threadRead: vi.fn(async () => ({ thread: { id: "thread-b", turns: [] } })),
      turnInterrupt: vi.fn(async () => ({})),
    };
    const { service, callbacks } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    internal.sessions = {
      version: 1,
      papers: { "1-ATTACH": { threadId: "thread-a", title: "A", workspace: "/profile/papers/1-ATTACH", updatedAt: "2026-07-28" } },
      history: { "1-ATTACH": [{ threadId: "thread-b", title: "B", workspace: "/profile/papers/1-ATTACH", updatedAt: "2026-07-27" }] },
    };

    const switching = service.switchThread("thread-b");
    expect(service.state.switchingThreadId).toBe("thread-b");
    expect(callbacks.onState).toHaveBeenCalled();
    expect(service.state.activeThreadId).toBe("thread-a");

    resumed.resolve({ thread: { id: "thread-b", turns: [] } });
    await switching;

    expect(service.state.activeThreadId).toBe("thread-b");
    expect(service.state.switchingThreadId).toBeNull();
    expect(client.threadRead).toHaveBeenCalledWith("thread-b", true);
  });

  it("coalesces repeated new-conversation clicks while creation is in flight", async () => {
    const started = deferred<{ thread: { id: string } }>();
    const client = {
      threadStart: vi.fn(() => started.promise),
      threadSetName: vi.fn(async () => ({})),
      turnInterrupt: vi.fn(async () => ({})),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);

    const first = service.newThread();
    const second = service.newThread();
    expect(service.state.creatingThread).toBe(true);
    expect(first).toBe(second);
    started.resolve({ thread: { id: "thread-new" } });
    await first;

    expect(client.threadStart).toHaveBeenCalledOnce();
    expect(service.state.creatingThread).toBe(false);
  });

  it("marks Reader and pinned paper content untrusted while keeping host guidance application-owned", async () => {
    const client = {
      turnStart: vi.fn().mockResolvedValue({ turn: { id: "turn-a" } }),
    };
    const { service } = serviceWithClient(client);
    service.setInteractionContext({
      "Pinned Reader selection": { kind: "untrusted", value: "Selected theorem" },
    });

    await service.send("Explain this.", "gpt-5.6-sol", "medium");

    const additionalContext = client.turnStart.mock.calls[0]![0].additionalContext;
    expect(additionalContext["Zotkit Reader integration"]).toMatchObject({
      kind: "application",
    });
    expect(additionalContext["Zotero Reader"]).toMatchObject({
      kind: "untrusted",
      value: expect.stringContaining("Current page"),
    });
    expect(additionalContext["Pinned Reader selection"]).toEqual({
      kind: "untrusted",
      value: "Selected theorem",
    });
    expect(Object.values(
      additionalContext as Record<string, { kind: string }>,
    ).every(
      (entry) => entry.kind === "application" || entry.kind === "untrusted",
    )).toBe(true);
  });

  it("exposes only the active conversation's reviewable Reader anchor IDs to the model", async () => {
    const client = {
      turnStart: vi.fn().mockResolvedValue({ turn: { id: "turn-a" } }),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    internal.sessions.anchors = {
      "1-ATTACH": [
        {
          anchorId: "anchor-reviewable",
          libraryID: 1,
          itemKey: "PARENT",
          attachmentKey: "ATTACH",
          pdfSha256: "a".repeat(64),
          pageNumber: 3,
          position: { pageIndex: 2, rects: [[1, 2, 3, 4]] },
          selectedText: "Selected theorem",
          question: "Why is this bound tight?",
          threadId: "thread-a",
          turnRange: [0, 1],
          status: "open",
          createdAt: "2026-07-25T00:00:00.000Z",
        },
        {
          anchorId: "anchor-other-thread",
          libraryID: 1,
          itemKey: "PARENT",
          attachmentKey: "ATTACH",
          pdfSha256: "a".repeat(64),
          pageNumber: 4,
          position: { pageIndex: 3, rects: [[1, 2, 3, 4]] },
          selectedText: "Do not leak this anchor",
          question: "Other conversation",
          threadId: "thread-b",
          turnRange: [0, 0],
          status: "open",
          createdAt: "2026-07-25T00:00:01.000Z",
        },
        {
          anchorId: "anchor-without-pdf-fingerprint",
          libraryID: 1,
          itemKey: "PARENT",
          attachmentKey: "ATTACH",
          pdfSha256: null,
          pageNumber: 5,
          position: { pageIndex: 4, rects: [[1, 2, 3, 4]] },
          selectedText: "Legacy selection",
          question: "Can this be highlighted?",
          threadId: "thread-a",
          turnRange: [2, 2],
          status: "open",
          createdAt: "2026-07-25T00:00:02.000Z",
        },
      ],
    };

    await service.send("Propose a highlight.", "gpt-5.6-sol", "medium");

    const additionalContext = client.turnStart.mock.calls[0]![0].additionalContext;
    expect(additionalContext["Annotation proposal bridge"]).toMatchObject({
      kind: "application",
      value: expect.stringContaining("zotero_propose_annotations"),
    });
    expect(additionalContext["Reviewable Reader anchors"]).toMatchObject({
      kind: "untrusted",
      value: expect.stringContaining("anchor-reviewable"),
    });
    expect(additionalContext["Reviewable Reader anchors"].value).toContain("Selected theorem");
    expect(additionalContext["Reviewable Reader anchors"].value).not.toContain("anchor-other-thread");
    expect(additionalContext["Reviewable Reader anchors"].value).not.toContain("anchor-without-pdf-fingerprint");
  });

  it("sends the active Draft and Zotero PDF context together", async () => {
    const client = {
      turnStart: vi.fn().mockResolvedValue({ turn: { id: "turn-a" } }),
    };
    const { service } = serviceWithClient(client);
    const editablePath = `work/qlab-zotero/draft-changes/${"a".repeat(64)}/draft.qmd`;
    service.setActiveDocument({ relativePath: "drafts/topic/note.qmd", editablePath });

    await service.send("Revise the current Draft.", "gpt-5.6-sol", "medium");

    const additionalContext = client.turnStart.mock.calls[0]![0].additionalContext;
    expect(additionalContext["QMD Editor"]).toMatchObject({
      kind: "application",
      value: expect.stringContaining("drafts/topic/note.qmd"),
    });
    expect(additionalContext["QMD Editor"].value).toContain(editablePath);
    expect(additionalContext["QMD Editor"].value).toContain("one latest cumulative AI version");
    expect(additionalContext["Zotero Reader"]).toMatchObject({
      kind: "untrusted",
      value: expect.stringContaining("Current PDF page: 3"),
    });
  });

  it("omits Reader context chips that the user deselected", async () => {
    const client = {
      turnStart: vi.fn().mockResolvedValue({ turn: { id: "turn-a" } }),
    };
    const { service } = serviceWithClient(client);
    service.setReaderContextSelection({ paper: false, page: true, selection: false });

    await service.send("Explain the visible page.", "gpt-5.6-sol", "medium");

    const additionalContext = client.turnStart.mock.calls[0]![0].additionalContext;
    const readerValue = additionalContext["Zotero Reader"].value as string;
    expect(readerValue).toContain("Current PDF page: 3");
    expect(readerValue).toContain("Current page text:\nCurrent page");
    expect(readerValue).not.toContain("Current Zotero paper");
    expect(readerValue).not.toContain("Attachment key");
    expect(readerValue).not.toContain("Current selection");
  });

  it("sends no implicit Reader payload after all Reader chips are deselected", async () => {
    const client = {
      turnStart: vi.fn().mockResolvedValue({ turn: { id: "turn-a" } }),
    };
    const { service } = serviceWithClient(client);
    service.setInteractionContext({
      "QLab repository": { kind: "application", value: "/research-loop" },
    });
    service.setReaderContextSelection({ paper: false, page: false, selection: false });

    await service.send("Work only from the repository.", "gpt-5.6-sol", "medium");

    const additionalContext = client.turnStart.mock.calls[0]![0].additionalContext;
    expect(additionalContext["Zotkit Reader integration"]).toBeUndefined();
    expect(additionalContext["Zotero Reader"]).toBeUndefined();
    expect(additionalContext["QLab repository"]).toEqual({
      kind: "application",
      value: "/research-loop",
    });
  });

  it("enforces a read-only sandbox for canonical read-only Research Actions", async () => {
    const client = {
      turnStart: vi.fn().mockResolvedValue({ turn: { id: "turn-read-only" } }),
    };
    const { service } = serviceWithClient(client);

    await service.send(
      "Follow $evidence-review in summary mode.",
      "gpt-5.6-sol",
      "medium",
      [],
      { readOnly: true },
    );

    expect(client.turnStart).toHaveBeenCalledWith(expect.objectContaining({
      sandboxPolicy: { type: "readOnly", networkAccess: false },
    }));
  });

  it("does not steer a read-only Action into an already-running writable turn", async () => {
    const client = {
      turnSteer: vi.fn(),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.runningTurns.set("thread-a", "turn-running");
    service.state.capabilities = {
      ...service.state.capabilities,
      supportsSteering: true,
    };

    await expect(service.send(
      "Follow $evidence-review in evidence-qa mode.",
      "gpt-5.6-sol",
      "medium",
      [],
      { readOnly: true },
    )).rejects.toThrow(/read-only Action.*current response/i);
    expect(client.turnSteer).not.toHaveBeenCalled();
  });

  it("lists all user-facing Codex sources with pagination and stable history metadata", async () => {
    const client = {
      threadList: vi.fn()
        .mockResolvedValueOnce({
          data: [{
            id: "global-a",
            name: "Pinned task",
            preview: "Fix the project",
            source: "appServer",
            cwd: "/repo/a",
            updatedAt: 200,
            isPinned: true,
          }],
          nextCursor: "page-2",
        })
        .mockResolvedValueOnce({
          data: [{
            id: "global-b",
            preview: "CLI task",
            source: "cli",
            updatedAt: 100,
          }],
          nextCursor: null,
        }),
    };
    const { service } = serviceWithClient(client);
    (service as any).sessions.pinnedThreads = ["global-a"];

    await service.refreshGlobalHistory();
    expect(client.threadList).toHaveBeenNthCalledWith(1, expect.objectContaining({
      cursor: null,
      sourceKinds: ["cli", "vscode", "appServer"],
      archived: false,
      sortKey: "updated_at",
    }));
    expect(service.getGlobalHistory()).toEqual([
      expect.objectContaining({
        id: "global-a",
        title: "Pinned task",
        sourceLabel: "Codex App",
        cwd: "/repo/a",
        pinned: true,
      }),
    ]);
    expect(service.getGlobalHistoryState()).toMatchObject({ hasMore: true, loading: false });

    await service.loadMoreGlobalHistory();
    expect(client.threadList).toHaveBeenNthCalledWith(2, expect.objectContaining({ cursor: "page-2" }));
    expect(service.getGlobalHistory().map((thread) => thread.id)).toEqual(["global-a", "global-b"]);
    expect(service.getGlobalHistoryState().hasMore).toBe(false);
  });

  it("pins a global Codex conversation and resumes it into the current paper safely", async () => {
    const client = {
      threadList: vi.fn(async () => ({
        data: [{ id: "global-a", name: "Global task", source: "vscode", updatedAt: 200 }],
        nextCursor: null,
      })),
      threadResume: vi.fn(async () => ({ thread: { id: "global-a", turns: [] } })),
      threadRead: vi.fn(async () => ({ thread: { id: "global-a", turns: [] } })),
      turnInterrupt: vi.fn(async () => ({})),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => {});
    internal.sessions.papers["1-ATTACH"] = {
      threadId: "thread-a",
      title: "Paper thread",
      workspace: "/profile/papers/1-ATTACH",
      updatedAt: "2026-07-22T00:00:00.000Z",
      backend: "codex",
    };
    await service.refreshGlobalHistory();

    await service.setGlobalThreadPinned("global-a", true);
    expect(service.getGlobalHistory()[0]?.pinned).toBe(true);
    expect(internal.sessions.pinnedThreads).toEqual(["global-a"]);

    await service.openGlobalThread("global-a");
    expect(client.threadResume).toHaveBeenCalledWith(expect.objectContaining({
      threadId: "global-a",
      approvalPolicy: "never",
      approvalsReviewer: "auto_review",
      sandbox: "workspace-write",
    }));
    expect(client.threadRead).toHaveBeenCalledWith("global-a", true);
    expect(service.state.activeThreadId).toBe("global-a");
    expect(service.getThreadOptions()).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: "global-a", active: true }),
      expect.objectContaining({ id: "thread-a", active: false }),
    ]));
  });

  it("keeps open conversation tabs across papers and restores the matching Reader context", async () => {
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
      threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
      turnInterrupt: vi.fn(async () => ({})),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => {});
    const first = paperContext();
    const second: ReaderContext = {
      ...paperContext(),
      attachment: { ...paperContext().attachment, id: 17, key: "SECOND", title: "Second PDF" },
      parent: { ...paperContext().parent!, id: 16, key: "SECOND-PARENT", title: "A Different Paper" },
      workspace: { ...paperContext().workspace!, root: "/profile/papers/1-SECOND" },
    };
    internal.activeContext = first;
    internal.activePaperKey = "1-ATTACH";
    internal.paperContexts.set("1-ATTACH", first);
    internal.paperContexts.set("1-SECOND", second);
    internal.sessions = {
      version: 1,
      papers: {
        "1-ATTACH": { threadId: "thread-a", title: "A Paper", paperTitle: "A Paper", workspace: first.workspace!.root, updatedAt: "2026-07-30" },
        "1-SECOND": { threadId: "thread-b", title: "Different proof", paperTitle: "A Different Paper", workspace: second.workspace!.root, updatedAt: "2026-07-30" },
      },
      openThreads: ["thread-a", "thread-b"],
    };

    await service.switchThread("thread-b");

    expect(service.getActiveReaderContext()?.parent?.title).toBe("A Different Paper");
    expect(service.getThreadOptions()).toEqual([
      expect.objectContaining({ id: "thread-a", paperTitle: "A Paper", active: false }),
      expect.objectContaining({ id: "thread-b", paperTitle: "A Different Paper", active: true }),
    ]);
  });

  it("keeps PDF focus, selected chat, and running turns independent", async () => {
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
      threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
      threadSetName: vi.fn(async () => ({})),
      turnStart: vi.fn(async () => ({ turn: { id: "turn-b" } })),
      turnInterrupt: vi.fn(async () => ({})),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => {});
    const first = paperContext();
    const second: ReaderContext = {
      ...paperContext(),
      attachment: { ...paperContext().attachment, id: 17, key: "SECOND", title: "Second PDF" },
      parent: { ...paperContext().parent!, id: 16, key: "SECOND-PARENT", title: "A Different Paper" },
      workspace: { ...paperContext().workspace!, root: "/profile/papers/1-SECOND" },
    };
    internal.paperContexts.set("1-ATTACH", first);
    internal.sessions = {
      version: 1,
      papers: {
        "1-ATTACH": { threadId: "thread-a", title: "A", workspace: first.workspace!.root, updatedAt: "2026-07-30" },
        "1-SECOND": { threadId: "thread-b", title: "B", workspace: second.workspace!.root, updatedAt: "2026-07-30" },
      },
      openThreads: ["thread-a", "thread-b"],
    };
    internal.runningTurns.set("thread-a", "turn-a");
    internal.syncActiveTurnState();

    await service.setPaper(second);

    expect(service.state).toMatchObject({
      activeThreadId: "thread-a",
      activeTurnId: "turn-a",
      running: true,
    });
    expect(service.getActiveReaderContext()?.attachment.key).toBe("ATTACH");
    expect(internal.focusedContext.attachment.key).toBe("SECOND");
    expect(client.threadResume).not.toHaveBeenCalled();
    expect(client.turnInterrupt).not.toHaveBeenCalled();

    await service.switchThread("thread-b");
    expect(service.state).toMatchObject({
      activeThreadId: "thread-b",
      activeTurnId: null,
      running: false,
    });
    expect(client.turnInterrupt).not.toHaveBeenCalled();
    expect(service.getThreadOptions()).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: "thread-a", status: "running", active: false }),
      expect.objectContaining({ id: "thread-b", status: "idle", active: true }),
    ]));

    await service.send("Work on B too.", "gpt-5.6-sol", "high");
    expect(client.turnStart).toHaveBeenCalledWith(expect.objectContaining({ threadId: "thread-b" }));
    expect(internal.runningTurns.get("thread-a")).toBe("turn-a");
    expect(internal.runningTurns.get("thread-b")).toBe("turn-b");

    await service.switchThread("thread-a");
    expect(service.state).toMatchObject({ activeThreadId: "thread-a", activeTurnId: "turn-a", running: true });
    internal.handleNotification({
      method: "turn/completed",
      params: { threadId: "thread-a", turn: { id: "turn-a" } },
    });
    expect(service.state).toMatchObject({ activeThreadId: "thread-a", activeTurnId: null, running: false });
    expect(service.getThreadOptions()).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: "thread-b", status: "running" }),
    ]));
  });

  it("closes a tab without deleting its conversation record", async () => {
    const { service } = serviceWithClient({ turnInterrupt: vi.fn(async () => ({})) });
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => {});
    internal.sessions = {
      version: 1,
      papers: {
        "1-ATTACH": { threadId: "thread-a", title: "A", workspace: "/profile/papers/1-ATTACH", updatedAt: "2026-07-30" },
      },
      history: {
        "1-ATTACH": [{ threadId: "thread-b", title: "B", workspace: "/profile/papers/1-ATTACH", updatedAt: "2026-07-29" }],
      },
      openThreads: ["thread-a", "thread-b"],
    };

    await service.closeThread("thread-b");

    expect(service.getThreadOptions().map((thread) => thread.id)).toEqual(["thread-a"]);
    expect(internal.sessions.history["1-ATTACH"]).toEqual([
      expect.objectContaining({ threadId: "thread-b" }),
    ]);
  });

  it("steers the exact active thread and turn while a response is running", async () => {
    const client = {
      turnStart: vi.fn(),
      turnSteer: vi.fn().mockResolvedValue({ turnId: "turn-a" })
    };
    const { service } = serviceWithClient(client);
    service.state.running = true;
    service.state.activeTurnId = "turn-a";

    await service.send("Also check the appendix.", "gpt-5.6-sol", "max");

    expect(client.turnStart).not.toHaveBeenCalled();
    expect(client.turnSteer).toHaveBeenCalledWith(expect.objectContaining({
      threadId: "thread-a",
      expectedTurnId: "turn-a",
      input: [{ type: "text", text: "Also check the appendix.", text_elements: [] }]
    }));
    expect(service.state).toMatchObject({ running: true, activeTurnId: "turn-a" });
  });

  it("serializes an immediate second submission behind turn/start and then steers that turn", async () => {
    const started = deferred<{ turn: { id: string } }>();
    const client = {
      turnStart: vi.fn(() => started.promise),
      turnSteer: vi.fn().mockResolvedValue({ turnId: "turn-new" })
    };
    const { service } = serviceWithClient(client);

    const first = service.send("Explain the proof.", "gpt-5.6-sol", "high");
    const second = service.send("Focus on the third step.", "gpt-5.6-sol", "high");
    await vi.waitFor(() => expect(client.turnStart).toHaveBeenCalledOnce());
    expect(client.turnSteer).not.toHaveBeenCalled();

    started.resolve({ turn: { id: "turn-new" } });
    await Promise.all([first, second]);

    expect(client.turnSteer).toHaveBeenCalledWith(expect.objectContaining({
      threadId: "thread-a",
      expectedTurnId: "turn-new",
      input: [{ type: "text", text: "Focus on the third step.", text_elements: [] }]
    }));
  });

  it("does not mark the active answer stopped when steering fails", async () => {
    const client = {
      turnSteer: vi.fn().mockRejectedValue(new Error("turn already completed"))
    };
    const { service } = serviceWithClient(client);
    service.state.running = true;
    service.state.activeTurnId = "turn-a";

    await expect(service.send("One more detail.", "", "medium"))
      .rejects.toThrow("turn already completed");
    expect(service.state).toMatchObject({ running: true, activeTurnId: "turn-a" });
  });
});

describe("CodexService model capabilities", () => {
  it("preserves per-model supported and default reasoning efforts including max and ultra", async () => {
    const client = {
      modelList: vi.fn().mockResolvedValue({
        data: [{
          id: "gpt-5.6-sol",
          displayName: "GPT-5.6 Sol",
          isDefault: true,
          supportedReasoningEfforts: [
            { reasoningEffort: "low", description: "Fast" },
            { reasoningEffort: "max", description: "Maximum" },
            { reasoningEffort: "ultra", description: "Automatic delegation" }
          ],
          defaultReasoningEffort: "low"
        }],
        nextCursor: null
      })
    };
    const { service } = serviceWithClient(client);

    await service.refreshModels();

    expect(service.state.models).toEqual([{
      id: "gpt-5.6-sol",
      label: "GPT-5.6 Sol",
      isDefault: true,
      defaultReasoningEffort: "low",
      supportedReasoningEfforts: [
        { reasoningEffort: "low", description: "Fast" },
        { reasoningEffort: "max", description: "Maximum" },
        { reasoningEffort: "ultra", description: "Automatic delegation" }
      ]
    }]);
  });

  it("clears live turn state when the transport disconnects", () => {
    const { service, callbacks } = serviceWithClient({});
    service.state.running = true;
    service.state.activeTurnId = "turn-a";

    (service as any).markDisconnected();

    expect(service.state).toMatchObject({
      connected: false,
      running: false,
      activeThreadId: null,
      activeTurnId: null
    });
    expect(callbacks.onState).toHaveBeenCalledOnce();
  });
});

describe("CodexService Cursor-style modes and approvals", () => {
  it("uses only untrusted QLab content and generated work as writable roots", async () => {
    vi.stubGlobal("Services", {
      uuid: { generateUUID: () => "{checkpoint-test}" },
      prefs: {
        getStringPref: (name: string, fallback: string) =>
          name.endsWith("qlabRoot") ? "/repo" : fallback,
      },
    });
    const client = {
      turnStart: vi.fn().mockResolvedValueOnce({ turn: { id: "turn-agent" } }),
    };
    const { service } = serviceWithClient(client);

    await service.send("Edit the untrusted Draft.", "gpt-5.6-sol", "high");

    expect(client.turnStart).toHaveBeenCalledWith(expect.objectContaining({
      sandboxPolicy: expect.objectContaining({
        writableRoots: ["/repo/drafts", "/repo/literature", "/repo/work"],
      }),
    }));
  });

  it("uses an auto-reviewed sandboxed Agent turn and rejects Ask mode", async () => {
    vi.stubGlobal("Services", {
      uuid: { generateUUID: () => "{checkpoint-test}" },
    });
    const client = {
      turnStart: vi.fn().mockResolvedValueOnce({ turn: { id: "turn-agent" } }),
      threadResume: vi.fn().mockResolvedValue({ thread: { id: "thread-a", turns: [] } }),
      turnInterrupt: vi.fn(),
    };
    const { service } = serviceWithClient(client);
    (service as any).saveSessions = vi.fn().mockResolvedValue(undefined);

    await service.send("Update the reviewed metadata.", "gpt-5.6-sol", "high");
    expect(client.turnStart).toHaveBeenCalledWith(expect.objectContaining({
      approvalPolicy: "never",
      approvalsReviewer: "auto_review",
      sandboxPolicy: expect.objectContaining({
        type: "workspaceWrite",
        writableRoots: ["/profile/papers/1-ATTACH"],
        networkAccess: false,
      }),
    }));
    expect(service.getCheckpoints()).toEqual([
      expect.objectContaining({ sourceThreadId: "thread-a", beforeTurnId: "turn-agent" }),
    ]);
    await expect(service.setMode("ask")).rejects.toThrow("only supports Agent mode");
    vi.unstubAllGlobals();
  });

  it("auto-approves safe requests and silently rejects out-of-scope writes", async () => {
    const { service, callbacks } = serviceWithClient({});
    service.state.mode = "agent";
    service.state.running = true;
    service.state.activeTurnId = "turn-a";
    const requestApproval = (service as any).requestUserApproval.bind(service);

    const command = requestApproval({
      kind: "commandExecution",
      method: "item/commandExecution/requestApproval",
      requestId: "rpc-command",
      params: {
        threadId: "thread-a",
        turnId: "turn-a",
        itemId: "item-command",
        startedAtMs: 1,
        command: "python update_metadata.py",
        cwd: "/papers",
        availableDecisions: ["accept", "decline"],
      },
    });
    expect(service.getPendingApprovals()).toEqual([]);
    await expect(command).resolves.toEqual({ decision: "acceptForSession" });

    const permission = requestApproval({
      kind: "permissions",
      method: "item/permissions/requestApproval",
      requestId: 17,
      params: {
        threadId: "thread-a",
        turnId: "turn-a",
        itemId: "item-permission",
        startedAtMs: 2,
        environmentId: null,
        cwd: "/papers",
        reason: "Write the selected attachment",
        permissions: {
          network: null,
          fileSystem: {
            read: ["/papers"],
            write: ["/profile/papers/1-ATTACH"],
          },
        },
      },
    });
    await expect(permission).resolves.toEqual({
      permissions: {
        fileSystem: {
          read: ["/papers"],
          write: ["/profile/papers/1-ATTACH"],
        },
      },
      scope: "session",
    });

    await expect(requestApproval({
      kind: "fileChange",
      method: "item/fileChange/requestApproval",
      requestId: "rpc-outside",
      params: {
        threadId: "thread-a",
        turnId: "turn-a",
        itemId: "item-outside",
        startedAtMs: 2,
        grantRoot: "/papers",
      },
    })).resolves.toEqual({ decision: "decline" });
    expect(service.getPendingApprovals()).toEqual([]);

    await expect(requestApproval({
      kind: "permissions",
      method: "item/permissions/requestApproval",
      requestId: "rpc-modern-outside",
      params: {
        threadId: "thread-a",
        turnId: "turn-a",
        itemId: "item-modern-outside",
        startedAtMs: 2,
        environmentId: null,
        cwd: "/profile/papers/1-ATTACH",
        reason: "Request modern filesystem entry",
        permissions: {
          network: null,
          fileSystem: {
            read: null,
            write: null,
            entries: [{
              access: "write",
              path: { type: "path", path: "/profile/papers/1-ATTACH/../../outside" },
            }],
          },
        },
      },
    })).resolves.toEqual({ permissions: {}, scope: "turn" });
    expect(service.getPendingApprovals()).toEqual([]);
    expect(callbacks.onError).toHaveBeenCalledWith(expect.objectContaining({
      message: expect.stringContaining("outside its private staging workspace"),
    }));

    await expect(requestApproval({
      kind: "fileChange",
      method: "item/fileChange/requestApproval",
      requestId: "rpc-traversal",
      params: {
        threadId: "thread-a",
        turnId: "turn-a",
        itemId: "item-traversal",
        startedAtMs: 2,
        grantRoot: "/profile/papers/1-ATTACH/../../outside",
      },
    })).resolves.toEqual({ decision: "decline" });
    expect(service.getPendingApprovals()).toEqual([]);

    service.state.mode = "ask";
    await expect(requestApproval({
      kind: "fileChange",
      method: "item/fileChange/requestApproval",
      requestId: "rpc-file",
      params: {
        threadId: "thread-a",
        turnId: "turn-a",
        itemId: "item-file",
        startedAtMs: 3,
      },
    })).resolves.toEqual({ decision: "decline" });
    expect(service.getPendingApprovals()).toEqual([]);
  });

  it("rejects network escalation without showing an approval card", async () => {
    const { service, callbacks } = serviceWithClient({});
    service.state.mode = "agent";
    service.state.running = true;
    service.state.activeTurnId = "turn-a";
    const requestApproval = (service as any).requestUserApproval.bind(service);
    const requestedPermissions = {
      network: { enabled: true },
      fileSystem: {
        read: null,
        write: null,
        entries: [{
          access: "write",
          path: { type: "path", path: "/profile/papers/1-ATTACH/staging" },
        }],
      },
    };

    const response = requestApproval({
      kind: "permissions",
      method: "item/permissions/requestApproval",
      requestId: "rpc-modern-inside",
      params: {
        threadId: "thread-a",
        turnId: "turn-a",
        itemId: "item-modern-inside",
        startedAtMs: 2,
        environmentId: null,
        cwd: "/profile/papers/1-ATTACH",
        reason: "Stage a generated PDF",
        permissions: requestedPermissions,
      },
    });

    expect(service.getPendingApprovals()).toEqual([]);
    await expect(response).resolves.toEqual({ permissions: {}, scope: "turn" });
    expect(callbacks.onError).toHaveBeenCalledWith(expect.objectContaining({
      message: expect.stringContaining("network access"),
    }));
  });

  it("rejects a writable path whose existing workspace symlink resolves outside", async () => {
    vi.stubGlobal("Components", {
      interfaces: { nsIFile: {} },
      classes: {
        "@mozilla.org/file/local;1": {
          createInstance: () => {
            let path = "";
            return {
              initWithPath(value: string) { path = value; },
              exists: () => true,
              normalize() {
                path = path.replace(
                  "/profile/papers/1-ATTACH/link",
                  "/outside-through-symlink",
                );
              },
              get path() { return path; },
              get leafName() { return path.split("/").pop() || ""; },
              get parent() { return null; },
            };
          },
        },
      },
    });
    const { service } = serviceWithClient({});
    service.state.mode = "agent";
    service.state.running = true;
    service.state.activeTurnId = "turn-a";
    const requestApproval = (service as any).requestUserApproval.bind(service);

    try {
      await expect(requestApproval({
        kind: "fileChange",
        method: "item/fileChange/requestApproval",
        requestId: "rpc-symlink-escape",
        params: {
          threadId: "thread-a",
          turnId: "turn-a",
          itemId: "item-symlink-escape",
          startedAtMs: 3,
          grantRoot: "/profile/papers/1-ATTACH/link/escape.pdf",
        },
      })).resolves.toEqual({ decision: "decline" });
      expect(service.getPendingApprovals()).toEqual([]);
    }
    finally {
      vi.unstubAllGlobals();
    }
  });

  it("always exposes the injected Agent tools", async () => {
    const readerContext = {
      tools: [{ name: "get_current_page", description: "Read", inputSchema: { type: "object" } }],
      getCachedContext: vi.fn(() => paperContext()),
      invokeTool: vi.fn().mockResolvedValue({ page: 3 }),
    } as unknown as ReaderContextService;
    const provider = {
      tools: [{ name: "preview_zotero_change", description: "Preview", inputSchema: { type: "object" } }],
      invokeTool: vi.fn().mockResolvedValue({ preview: true }),
    };
    const service = new CodexService(
      {} as NativeBridge,
      readerContext,
      "test",
      { onState: vi.fn(), onError: vi.fn() },
      provider,
    );
    const internal = service as any;
    internal.activeContext = paperContext();
    internal.activePaperKey = "1-ATTACH";
    internal.threadPaperKeys.set("thread-a", "1-ATTACH");
    service.state.activeThreadId = "thread-a";

    expect(internal.dynamicToolSpecs().map((tool: { name: string }) => tool.name))
      .toEqual(["get_current_page", "preview_zotero_change"]);
    await expect(internal.handleDynamicTool({
      threadId: "thread-a",
      turnId: "turn-a",
      callId: "call-b",
      namespace: null,
      tool: "preview_zotero_change",
      arguments: { title: "New title" },
    })).resolves.toMatchObject({ success: true });
    expect(provider.invokeTool).toHaveBeenCalledWith(
      "preview_zotero_change",
      { title: "New title" },
      expect.objectContaining({ pdfPath: "/papers/paper.pdf" }),
      { threadId: "thread-a", turnId: "turn-a" },
    );
  });

  it("keeps background Reader tool calls scoped to their conversation paper", async () => {
    const first = paperContext();
    const second: ReaderContext = {
      ...paperContext(),
      attachment: { ...paperContext().attachment, id: 17, key: "SECOND" },
      parent: { ...paperContext().parent!, id: 16, key: "SECOND-PARENT", title: "Second" },
    };
    const readerContext = {
      tools: [{ name: "zotero_get_current_page", description: "Read", inputSchema: { type: "object" } }],
      invokeTool: vi.fn().mockResolvedValue({ pageNumber: 3 }),
    } as unknown as ReaderContextService;
    const service = new CodexService(
      {} as NativeBridge,
      readerContext,
      "test",
      { onState: vi.fn(), onError: vi.fn() },
    );
    const internal = service as any;
    internal.activeContext = second;
    internal.activePaperKey = "1-SECOND";
    internal.paperContexts.set("1-ATTACH", first);
    internal.paperContexts.set("1-SECOND", second);
    internal.threadPaperKeys.set("thread-a", "1-ATTACH");
    internal.threadPaperKeys.set("thread-b", "1-SECOND");
    service.state.activeThreadId = "thread-b";

    await expect(internal.handleDynamicTool({
      threadId: "thread-a",
      turnId: "turn-a",
      callId: "call-a",
      namespace: null,
      tool: "zotero_get_current_page",
      arguments: {},
    })).resolves.toMatchObject({ success: true });
    expect(readerContext.invokeTool).toHaveBeenCalledWith(
      "zotero_get_current_page",
      {},
      expect.objectContaining({ attachment: expect.objectContaining({ key: "ATTACH" }) }),
    );
  });

  it("allows library tools but blocks active-PDF tools for Note, Collection, and Draft conversations", async () => {
    const readerContext = {
      tools: [
        READER_CONTEXT_TOOLS.find((tool) => tool.name === "zotero_get_current_page")!,
        READER_CONTEXT_TOOLS.find((tool) => tool.name === "zotero_search_library_items")!,
      ],
      invokeTool: vi.fn().mockResolvedValue({ matches: [] }),
    } as unknown as ReaderContextService;
    const client = {
      threadStart: vi.fn().mockResolvedValue({ thread: { id: "thread-object" } }),
      threadSetName: vi.fn(async () => ({})),
    };
    const service = new CodexService(
      {} as NativeBridge,
      readerContext,
      "test",
      { onState: vi.fn(), onError: vi.fn() },
    );
    const internal = service as any;
    internal.client = client;
    internal.saveSessions = vi.fn(async () => undefined);
    service.state.connected = true;
    await service.setWorkspaceObject({
      kind: "collection",
      key: "COLLECTION",
      title: "Quantum Algorithms",
      workspaceRoot: "/Users/test/research-loop",
      libraryID: 1,
    });

    await expect(internal.handleDynamicTool({
      threadId: "thread-object",
      turnId: "turn-object",
      callId: "call-pdf",
      namespace: null,
      tool: "zotero_get_current_page",
      arguments: {},
    })).resolves.toMatchObject({
      success: false,
      contentItems: [{ text: expect.stringContaining("Open or attach a PDF") }],
    });
    expect(readerContext.invokeTool).not.toHaveBeenCalled();

    await expect(internal.handleDynamicTool({
      threadId: "thread-object",
      turnId: "turn-object",
      callId: "call-search",
      namespace: null,
      tool: "zotero_search_library_items",
      arguments: { query: "quantum algorithms" },
    })).resolves.toMatchObject({ success: true });
    expect(readerContext.invokeTool).toHaveBeenCalledWith(
      "zotero_search_library_items",
      { query: "quantum algorithms" },
      expect.objectContaining({ attachment: expect.objectContaining({ itemType: "collection" }) }),
    );
  });

  it("statically composes read tools plus only the three reviewed Zotero proposal boundaries", () => {
    // Uses the REAL tool registries (not a hand-rolled fake list), so this
    // locks the actual composition site (dynamicToolSpecs(), around
    // codex-service.ts:readerContext.tools + agentToolProvider.tools).
    const readerContext = { tools: READER_CONTEXT_TOOLS } as unknown as ReaderContextService;
    const mutations = new ZoteroMutationService(
      {} as any,
      { onState: () => {}, getContext: () => null },
    );
    const annotations = new AnnotationProposalService(
      {} as any,
      { onState: () => {}, getAnchors: () => [], setAnnotationKey: async () => {} },
    );
    const notes = new NoteDraftBridgeService({} as any, { onState: () => {} });
    const provider = {
      tools: [...mutations.tools, ...annotations.tools, ...notes.tools],
      invokeTool: async () => undefined,
    };
    const service = new CodexService(
      {} as NativeBridge,
      readerContext,
      "test",
      { onState: vi.fn(), onError: vi.fn() },
      provider,
    );
    const internal = service as any;
    service.state.mode = "agent";

    const names: string[] = internal.dynamicToolSpecs().map((tool: { name: string }) => tool.name);

    expect(names).toEqual([
      ...READER_TOOL_NAMES,
      ZOTERO_MUTATION_TOOL,
      ANNOTATION_PROPOSAL_TOOL,
      NOTE_FROM_QMD_TOOL,
    ]);

    // Defense in depth: write-shaped names are either read-only list/read
    // tools or explicit proposal tools. No direct create/delete tool exists.
    const writeLike = /annot|attach|write|create|delete|erase/i;
    const knownSafeSubstringHits = new Set([
      ZOTERO_MUTATION_TOOL,
      ANNOTATION_PROPOSAL_TOOL,
      NOTE_FROM_QMD_TOOL,
      "zotero_list_annotations",
    ]);
    for (const name of names) {
      if (knownSafeSubstringHits.has(name)) continue;
      expect(name).not.toMatch(writeLike);
    }
  });

  it("restores a checkpoint by forking before its turn without claiming file restoration", async () => {
    const client = {
      threadFork: vi.fn().mockResolvedValue({
        thread: { id: "thread-restored", turns: [] },
      }),
      turnInterrupt: vi.fn(),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn().mockResolvedValue(undefined);
    internal.sessions.checkpoints = {
      "1-ATTACH": [{
        id: "checkpoint-1",
        sourceThreadId: "thread-a",
        beforeTurnId: "turn-mutating",
        label: "Before metadata update",
        createdAt: "2026-07-23T00:00:00.000Z",
        turnDiff: "--- old\n+++ new",
      }],
    };

    await expect(service.restoreCheckpoint("checkpoint-1")).resolves.toEqual({
      threadId: "thread-restored",
      turnDiff: "--- old\n+++ new",
      filesystemRestored: false,
    });
    expect(client.threadFork).toHaveBeenCalledWith(expect.objectContaining({
      threadId: "thread-a",
      beforeTurnId: "turn-mutating",
    }));
    expect(service.state.activeThreadId).toBe("thread-restored");
  });

  it("offers an explicit terminal fallback hook without starting a second transport", () => {
    const onFallbackRequested = vi.fn();
    const service = new CodexService(
      {} as NativeBridge,
      { tools: [] } as unknown as ReaderContextService,
      "test",
      { onState: vi.fn(), onError: vi.fn(), onFallbackRequested },
    );
    service.state.fallbackReason = "app-server protocol mismatch";

    service.requestTerminalFallback();

    expect(onFallbackRequested).toHaveBeenCalledWith(
      expect.objectContaining({ message: "app-server protocol mismatch" }),
    );
  });
});

describe("CodexService anchors", () => {
  function anchor(id: string): any {
    return {
      anchorId: id, libraryID: 1, itemKey: "PARENT", attachmentKey: "ATTACH",
      pdfSha256: null, selectedText: "s", question: "q", threadId: "thread-a",
      turnRange: [0, 0], status: "open", createdAt: "2026-07-25T00:00:00.000Z",
    };
  }

  it("records, updates, and removes anchors per paper", async () => {
    const { service } = serviceWithClient({});
    (service as any).saveSessions = vi.fn(async () => {});
    const context = paperContext();
    await service.recordAnchor(context, anchor("a1"));
    await service.recordAnchor(context, anchor("a2"));
    expect(service.getAnchors(context).map((a) => a.anchorId)).toEqual(["a1", "a2"]);
    await service.updateAnchor(context, "a1", { status: "resolved", annotationKey: "ANN1" });
    expect(service.getAnchors(context)[0]).toMatchObject({ status: "resolved", annotationKey: "ANN1" });
    await service.removeAnchor(context, "a2");
    expect(service.getAnchors(context).map((a) => a.anchorId)).toEqual(["a1"]);
    expect((service as any).saveSessions).toHaveBeenCalledTimes(4);
  });

  it("returns [] for a paper with no anchors and counts active thread turns", () => {
    const { service } = serviceWithClient({});
    expect(service.getAnchors(paperContext())).toEqual([]);
    (service as any).store = { getThread: () => ({ turns: [{}, {}, {}] }) };
    expect(service.activeThreadTurnCount()).toBe(3);
  });

  it("buckets a recorded anchor by the RECORD's own identity, not the live context passed in (MUST 2)", async () => {
    const { service } = serviceWithClient({});
    (service as any).saveSessions = vi.fn(async () => {});
    // The live context is a different paper than the anchor's own identity --
    // this can happen after a live-context flip mid-turn.
    const liveContext = paperContext();
    const recordAnchor = anchor("a1");
    recordAnchor.libraryID = 2;
    recordAnchor.attachmentKey = "OTHER_ATTACH";

    await service.recordAnchor(liveContext, recordAnchor);

    expect(service.getAnchors(liveContext)).toEqual([]);
    const recordContext: ReaderContext = {
      ...paperContext(),
      attachment: { ...paperContext().attachment, key: "OTHER_ATTACH", libraryID: 2 },
    };
    expect(service.getAnchors(recordContext).map((a) => a.anchorId)).toEqual(["a1"]);
  });

  it("updateAnchor/removeAnchor locate the anchor across buckets, bucket-agnostic (MUST 2)", async () => {
    const { service } = serviceWithClient({});
    (service as any).saveSessions = vi.fn(async () => {});
    const recordContext = paperContext();
    await service.recordAnchor(recordContext, anchor("a1"));

    // Called with a context for a DIFFERENT paper than the anchor's bucket.
    const otherLiveContext: ReaderContext = {
      ...paperContext(),
      attachment: { ...paperContext().attachment, key: "DIFFERENT", libraryID: 9 },
    };
    await service.updateAnchor(otherLiveContext, "a1", { status: "resolved", annotationKey: "ANN1" });
    expect(service.getAnchors(recordContext)[0]).toMatchObject({ status: "resolved", annotationKey: "ANN1" });

    await service.removeAnchor(otherLiveContext, "a1");
    expect(service.getAnchors(recordContext)).toEqual([]);
  });

  it("exposes only anchors belonging to the active conversation and updates them by id", async () => {
    const { service } = serviceWithClient({});
    (service as any).saveSessions = vi.fn(async () => {});
    const first = anchor("a1");
    const second = { ...anchor("a2"), threadId: "thread-b", attachmentKey: "SECOND" };
    await service.recordAnchor(paperContext(), first);
    await service.recordAnchor(paperContext(), second);

    expect(service.getActiveThreadAnchors().map((entry) => entry.anchorId)).toEqual(["a1"]);
    await service.updateAnchorById("a1", { annotationKey: "ANN1" });
    expect(service.getActiveThreadAnchors()[0]).toMatchObject({ annotationKey: "ANN1" });
  });
});

describe("CodexService utility turns", () => {
  it("runs a turn on a hidden thread and resolves with the assistant text", async () => {
    const store = new Map<string, any>();
    store.set("util-1", { turns: [{ id: "t1", status: "completed", items: [
      { id: "i1", type: "agentMessage", text: "两句要点." },
    ] }] });
    const client = {
      threadStart: vi.fn(async () => ({ thread: { id: "util-1" } })),
      turnStart: vi.fn(async () => ({ turn: { id: "t1" } })),
    };
    const { service } = serviceWithClient(client);
    (service as any).store = { getThread: (id: string) => store.get(id) };
    const pending = service.runUtilityTurn("总结一下", { timeoutMs: 5000 });
    await Promise.resolve();
    // handleNotification's real eventThreadId extraction reads params.threadId
    // (or params.turn.threadId) — not params.thread.id — so the notification
    // below is shaped to match src/codex-service.ts:776-778, not the brief's
    // literal `{ thread: { id } }` shape.
    (service as any).handleNotification({
      method: "turn/completed",
      params: { threadId: "util-1", turn: { id: "t1" } },
    });
    await expect(pending).resolves.toBe("两句要点.");
    expect(service.state.activeThreadId).toBe("thread-a"); // 活动线程未被切换
  });

  it("rejects on timeout", async () => {
    const client = {
      threadStart: vi.fn(async () => ({ thread: { id: "util-2" } })),
      turnStart: vi.fn(async () => ({ turn: { id: "t9" } })),
    };
    const { service } = serviceWithClient(client);
    vi.useFakeTimers();
    const pending = service.runUtilityTurn("x", { timeoutMs: 50 });
    const guarded = pending.catch((error) => error);
    await vi.advanceTimersByTimeAsync(60);
    expect(String(await guarded)).toContain("timed out");
    vi.useRealTimers();
  });

  it("cleans up the waiter if turnStart throws", async () => {
    const client = {
      threadStart: vi.fn(async () => ({ thread: { id: "util-3" } })),
      turnStart: vi.fn(async () => {
        throw new Error("network down");
      }),
    };
    const { service } = serviceWithClient(client);
    await expect(service.runUtilityTurn("x", { timeoutMs: 5000 })).rejects.toThrow("network down");
    expect((service as any).utilityWaiters.size).toBe(0);
    expect(service.state.activeThreadId).toBe("thread-a");
    expect(service.state.running).toBe(false);
  });

  it("rejects (not resolves) when the hidden turn fails, so a partial agentMessage is never returned as success", async () => {
    const store = new Map<string, any>();
    // The failed turn still has a partially-streamed agentMessage in the
    // store; runUtilityTurn must never hand this back as if it succeeded.
    store.set("util-4", { turns: [{ id: "t1", status: "failed", items: [
      { id: "i1", type: "agentMessage", text: "半句还没说完" },
    ] }] });
    const client = {
      threadStart: vi.fn(async () => ({ thread: { id: "util-4" } })),
      turnStart: vi.fn(async () => ({ turn: { id: "t1" } })),
    };
    const { service } = serviceWithClient(client);
    (service as any).store = { getThread: (id: string) => store.get(id) };
    const pending = service.runUtilityTurn("总结一下", { timeoutMs: 5000 });
    await Promise.resolve();
    (service as any).handleNotification({
      method: "turn/failed",
      params: { threadId: "util-4", turn: { id: "t1", error: { message: "沙盒被Reject" } } },
    });
    await expect(pending).rejects.toThrow("沙盒被Reject");
    expect((service as any).utilityWaiters.size).toBe(0);
    expect(service.state.activeThreadId).toBe("thread-a");
    expect(service.state.running).toBe(false);
  });

  it("reads another thread's turns without touching active state", async () => {
    const client = { threadRead: vi.fn(async () => ({ thread: { id: "old" } })) };
    const { service } = serviceWithClient(client);
    (service as any).store = { getThread: (id: string) => (id === "old" ? { turns: [
      { id: "t1", status: "completed", items: [
        { id: "u1", type: "userMessage", content: [{ type: "text", text: "问" }] },
        { id: "a1", type: "agentMessage", text: "答" },
      ] },
    ] } : undefined) };
    const turns = await service.readThreadTurns("old");
    expect(turns).toHaveLength(1);
    expect(turns[0]!.map((entry) => entry.kind)).toEqual(["user", "assistant"]);
    expect(service.state.activeThreadId).toBe("thread-a");
  });

  it("returns [] when threadRead fails and the store has nothing for the thread", async () => {
    const client = { threadRead: vi.fn(async () => { throw new Error("offline"); }) };
    const { service } = serviceWithClient(client);
    (service as any).store = { getThread: () => undefined };
    await expect(service.readThreadTurns("missing")).resolves.toEqual([]);
  });
});

describe("CodexService entriesForTurn duplicate-user defense (bug-triage #1)", () => {
  it("renders commentary as collapsible progress, dedupes repeats, and keeps only the final answer as assistant content", () => {
    const { service } = serviceWithClient({});
    (service as any).store = {
      getThread: () => ({
        turns: [{
          id: "t1",
          status: "completed",
          items: [
            { id: "u1", type: "userMessage", content: [{ type: "text", text: "总结论文" }] },
            { id: "c1", type: "agentMessage", phase: "commentary", text: "Reading the paper…" },
            { id: "c2", type: "agentMessage", phase: "commentary", text: "Reading the paper…" },
            { id: "a1", type: "agentMessage", phase: "final_answer", text: "The main result is…" },
          ],
        }],
      }),
    };

    const entries = service.getChatEntries();
    expect(entries.map((entry) => entry.kind)).toEqual(["user", "reasoning", "assistant"]);
    expect(entries[1]).toMatchObject({ title: "Progress", text: "Reading the paper…" });
    expect(entries[2]).toMatchObject({ text: "The main result is…" });
  });

  it("collapses two userMessage items with different ids but identical text into a single user entry", () => {
    const { service } = serviceWithClient({});
    (service as any).store = {
      getThread: () => ({
        turns: [
          {
            id: "t1",
            status: "completed",
            items: [
              // Index-fallback id from a turn/started snapshot ...
              { id: "t1:item:0", type: "userMessage", content: [{ type: "text", text: "浮点数怎么表示?" }] },
              // ... and the server's real id from a later item/completed notification.
              { id: "real-item-9", type: "userMessage", content: [{ type: "text", text: "浮点数怎么表示?" }] },
              { id: "a1", type: "agentMessage", text: "用 IEEE 754." },
            ],
          },
        ],
      }),
    };
    const chatEntries = service.getChatEntries();
    const userEntries = chatEntries.filter((entry) => entry.kind === "user");
    expect(userEntries).toHaveLength(1);
    expect(userEntries[0]!.text).toBe("浮点数怎么表示?");
    expect(chatEntries.map((entry) => entry.kind)).toEqual(["user", "assistant"]);
  });

  it("keeps both user entries when the texts genuinely differ (steering within the same turn)", () => {
    const { service } = serviceWithClient({});
    (service as any).store = {
      getThread: () => ({
        turns: [
          {
            id: "t1",
            status: "completed",
            items: [
              { id: "u1", type: "userMessage", content: [{ type: "text", text: "先看Page 2 节" }] },
              { id: "u2", type: "userMessage", content: [{ type: "text", text: "不,先看摘要" }] },
              { id: "a1", type: "agentMessage", text: "好的." },
            ],
          },
        ],
      }),
    };
    const userEntries = service.getChatEntries().filter((entry) => entry.kind === "user");
    expect(userEntries.map((entry) => entry.text)).toEqual(["先看Page 2 节", "不,先看摘要"]);
  });

  it("does not dedup identical user text across two different turns", () => {
    const { service } = serviceWithClient({});
    (service as any).store = {
      getThread: () => ({
        turns: [
          {
            id: "t1",
            status: "completed",
            items: [
              { id: "u1", type: "userMessage", content: [{ type: "text", text: "重复问题" }] },
              { id: "a1", type: "agentMessage", text: "答一" },
            ],
          },
          {
            id: "t2",
            status: "completed",
            items: [
              { id: "u2", type: "userMessage", content: [{ type: "text", text: "重复问题" }] },
              { id: "a2", type: "agentMessage", text: "答二" },
            ],
          },
        ],
      }),
    };
    const userEntries = service.getChatEntries().filter((entry) => entry.kind === "user");
    expect(userEntries).toHaveLength(2);
    expect(userEntries.map((entry) => entry.text)).toEqual(["重复问题", "重复问题"]);
  });
});

describe("CodexService conversation reopening", () => {
  function reopeningContext(): ReaderContext {
    return {
      ...paperContext(),
      attachment: { ...paperContext().attachment, id: 17, key: "SECOND", title: "Second PDF" },
      parent: { ...paperContext().parent!, id: 16, key: "SECOND-PARENT", title: "A Different Paper" },
      workspace: { ...paperContext().workspace!, root: "/profile/papers/1-SECOND" },
    };
  }

  function serviceWithSeeder(
    client: Record<string, unknown>,
    seedPaperContext: (paperKey: string) => Promise<ReaderContext>,
  ) {
    const callbacks = { onState: vi.fn(), onError: vi.fn(), seedPaperContext };
    const service = new CodexService(
      {} as NativeBridge,
      { tools: [] } as unknown as ReaderContextService,
      "test",
      callbacks,
    );
    const internal = service as any;
    internal.client = client;
    internal.saveSessions = vi.fn(async () => {});
    service.state.connected = true;
    internal.sessions = {
      version: 1,
      papers: {
        "1-SECOND": {
          threadId: "thread-b",
          title: "Stored conversation",
          paperTitle: "A Different Paper",
          workspace: "/profile/papers/1-SECOND",
          updatedAt: "2026-07-30",
        },
      },
      openThreads: ["thread-b"],
    };
    return { service, internal, callbacks };
  }

  it("reopens a stored conversation tab by seeding its paper context through the host hook", async () => {
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
      threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service } = serviceWithSeeder(client, seedPaperContext);

    await service.switchThread("thread-b");

    expect(seedPaperContext).toHaveBeenCalledWith("1-SECOND");
    expect(client.threadResume).toHaveBeenCalledWith(expect.objectContaining({ threadId: "thread-b" }));
    expect(service.state.activeThreadId).toBe("thread-b");
    expect(service.getActiveReaderContext()?.attachment.key).toBe("SECOND");
  });

  it("reopens a known History conversation by seeding its paper context through the host hook", async () => {
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
      threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service, internal } = serviceWithSeeder(client, seedPaperContext);
    internal.globalHistory = [{
      id: "thread-b",
      title: "Stored conversation",
      updatedAt: "2026-07-30T00:00:00.000Z",
      source: "codex",
      sourceLabel: "Codex CLI",
      pinned: false,
    }];

    await service.openGlobalThread("thread-b");

    expect(seedPaperContext).toHaveBeenCalledWith("1-SECOND");
    expect(service.state.activeThreadId).toBe("thread-b");
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({ threadId: "thread-b" });
  });

  it("opens a paper's stored conversation after seeding the context through the host hook", async () => {
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
      threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service } = serviceWithSeeder(client, seedPaperContext);

    await service.openConversationForPaper("1-SECOND");

    expect(seedPaperContext).toHaveBeenCalledWith("1-SECOND");
    expect(client.threadResume).toHaveBeenCalledWith(expect.objectContaining({ threadId: "thread-b" }));
    expect(service.state.activeThreadId).toBe("thread-b");
    expect(service.getActiveReaderContext()?.attachment.key).toBe("SECOND");
  });

  it("starts a fresh thread when the paper has no stored conversation", async () => {
    const client = {
      threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
      threadSetName: vi.fn(async () => ({})),
      threadResume: vi.fn(),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service, internal } = serviceWithSeeder(client, seedPaperContext);
    internal.sessions = { version: 1, papers: {} };

    await service.openConversationForPaper("1-SECOND");

    expect(seedPaperContext).toHaveBeenCalledWith("1-SECOND");
    expect(client.threadResume).not.toHaveBeenCalled();
    expect(client.threadStart).toHaveBeenCalled();
    expect(service.state.activeThreadId).toBe("thread-new");
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({ threadId: "thread-new" });
  });

  it("falls back to a fresh thread when the stored thread no longer exists on the backend", async () => {
    const client = {
      threadResume: vi.fn(async () => { throw new Error("thread not found"); }),
      threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
      threadSetName: vi.fn(async () => ({})),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service, internal } = serviceWithSeeder(client, seedPaperContext);

    await service.openConversationForPaper("1-SECOND");

    expect(service.state.activeThreadId).toBe("thread-new");
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({ threadId: "thread-new" });
    expect(internal.sessions.history["1-SECOND"]).toEqual([
      expect.objectContaining({ threadId: "thread-b" }),
    ]);
  });

  it("surfaces a seeding failure without touching conversation state", async () => {
    const client = {
      threadResume: vi.fn(),
      threadStart: vi.fn(),
    };
    const seedPaperContext = vi.fn(async () => {
      throw new Error("This Zotero item has no readable PDF attachment");
    });
    const { service, internal } = serviceWithSeeder(client, seedPaperContext);

    await expect(service.openConversationForPaper("1-SECOND"))
      .rejects.toThrow("This Zotero item has no readable PDF attachment");

    expect(service.state.activeThreadId).toBeNull();
    expect(client.threadResume).not.toHaveBeenCalled();
    expect(client.threadStart).not.toHaveBeenCalled();
    expect(internal.paperContexts.has("1-SECOND")).toBe(false);
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({ threadId: "thread-b" });
  });
});
