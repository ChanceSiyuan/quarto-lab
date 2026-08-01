import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CodexService,
  readSessionRecords,
  saveSessionRecords,
} from "../src/codex-service";
import {
  CodexDisconnectedError,
  CodexRequestTimeoutError,
  CodexRpcError,
} from "../src/codex-app-server";
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
import type { RepositoryTargetSnapshot } from "../src/repository-target";
import { RepositoryTargetController } from "../src/repository-target-controller";

const TEST_TARGET_ID = "b".repeat(64);

function repositorySnapshot(
  root = "/repo",
  targetEpoch = 1,
  targetId = TEST_TARGET_ID,
): RepositoryTargetSnapshot {
  return {
    target: {
      kind: "local",
      root,
      canonicalRoot: root,
      repositoryId: "a".repeat(64),
      targetId,
    },
    targetEpoch,
  };
}

function bindRepository(
  service: CodexService,
  root = "/repo",
  targetEpoch = 1,
  targetId = TEST_TARGET_ID,
): void {
  const snapshot = repositorySnapshot(root, targetEpoch, targetId);
  service.commitRepositoryTarget({
    snapshot,
    binding: { targetId, targetEpoch, root },
    activeDocument: null,
  });
}

function currentTargetRecord<T extends Record<string, unknown>>(
  record: T,
): T & { recordedCwd: string; targetId: string } {
  return { ...record, recordedCwd: "/repo", targetId: TEST_TARGET_ID };
}

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
  bindRepository(service);
  internal.client = client;
  internal.activeContext = paperContext();
  internal.activePaperKey = "1-ATTACH";
  internal.rememberThreadOwner("thread-a", "1-ATTACH", "foreground", {
    targetId: TEST_TARGET_ID,
    targetEpoch: 1,
    root: "/repo",
  });
  service.state.connected = true;
  service.state.activeThreadId = "thread-a";
  return { service, callbacks };
}

function ownTurn(
  service: CodexService,
  threadId: string,
  turnId: string,
  paperKey = "1-ATTACH",
  kind: "foreground" | "background" | "utility" = "foreground",
): void {
  const internal = service as any;
  const binding = service.repositoryBinding();
  if (!binding) throw new Error("Test service is not target-bound");
  const owner = internal.threadOwners.get(threadId)
    || internal.rememberThreadOwner(threadId, paperKey, kind, binding);
  internal.registerOwnedTurn(owner, turnId);
  internal.syncActiveTurnState();
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

describe("CodexService repository target binding", () => {
  it("stages a new target only after the queued paper transition drains", async () => {
    const resumed = deferred<{ thread: { id: string; turns: never[] } }>();
    const client = {
      threadResume: vi.fn(() => resumed.promise),
      threadRead: vi.fn(async () => ({ thread: { id: "thread-b", turns: [] } })),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    internal.sessions = {
      version: 1,
      papers: {
        "1-ATTACH": {
          threadId: "thread-a",
          title: "A",
          workspace: "/profile/papers/1-ATTACH",
          recordedCwd: "/repo",
          targetId: TEST_TARGET_ID,
          updatedAt: "2026-07-31",
        },
      },
      history: {
        "1-ATTACH": [{
          threadId: "thread-b",
          title: "B",
          workspace: "/profile/papers/1-ATTACH",
          recordedCwd: "/repo",
          targetId: TEST_TARGET_ID,
          updatedAt: "2026-07-30",
        }],
      },
    };

    const opening = service.switchThread("thread-b");
    await vi.waitFor(() => expect(client.threadResume).toHaveBeenCalledOnce());
    let staged = false;
    const staging = service.stageRepositoryTarget(repositorySnapshot("/B", 2, "c".repeat(64)))
      .then((value) => { staged = true; return value; });
    await Promise.resolve();
    expect(staged).toBe(false);
    expect(service.repositoryBinding()).toEqual({
      targetId: TEST_TARGET_ID,
      targetEpoch: 1,
      root: "/repo",
    });

    resumed.resolve({ thread: { id: "thread-b", turns: [] } });
    await opening;
    const stage = await staging;
    expect(stage.binding).toEqual({ targetId: "c".repeat(64), targetEpoch: 2, root: "/B" });
    expect(service.repositoryBinding()?.root).toBe("/repo");
  });

  it("commits synchronously with exact undefined and validates before any mutation", async () => {
    const { service } = serviceWithClient({});
    service.setActiveDocument({ relativePath: "drafts/a.qmd" });
    const before = service.repositoryBinding();
    const next = repositorySnapshot("/B", 2, "c".repeat(64));

    expect(() => service.commitRepositoryTarget({
      snapshot: next,
      binding: { targetId: "c".repeat(64), targetEpoch: 2, root: "/wrong" },
      activeDocument: null,
    })).toThrow("staged repository target");
    expect(service.repositoryBinding()).toEqual(before);
    expect((service as any).activeDocument).not.toBeNull();

    const stage = await service.stageRepositoryTarget(next);
    expect(service.commitRepositoryTarget(stage)).toBeUndefined();
    expect(service.repositoryBinding()).toEqual(stage.binding);
    expect((service as any).activeDocument).toBeNull();

    service.state.activeThreadId = "thread-old-root";
    (service as any).activeContext = paperContext();
    const rootOnlyChange = repositorySnapshot("/C", 2, "c".repeat(64));
    const rootStage = await service.stageRepositoryTarget(rootOnlyChange);
    expect(service.commitRepositoryTarget(rootStage)).toBeUndefined();
    expect(service.state.activeThreadId).toBeNull();
    expect((service as any).activeContext).toBeNull();
  });

  it("starts a new target thread instead of reusing an old workspace object", async () => {
    const client = {
      threadStart: vi.fn(async () => ({ thread: { id: `thread-${client.threadStart.mock.calls.length}` } })),
      threadSetName: vi.fn(async () => ({})),
      turnStart: vi.fn(async () => ({ turn: { id: "turn-b" } })),
      turnSteer: vi.fn(),
    };
    const service = new CodexService(
      {} as NativeBridge,
      { tools: [] } as unknown as ReaderContextService,
      "test",
      { onState: vi.fn(), onError: vi.fn() },
    );
    (service as any).client = client;
    (service as any).saveSessions = vi.fn(async () => undefined);
    service.state.connected = true;
    bindRepository(service, "/A", 1, TEST_TARGET_ID);
    await service.setWorkspaceObject({ kind: "draft", key: "drafts/a.qmd", title: "A" });

    const next = repositorySnapshot("/B", 2, "c".repeat(64));
    service.commitRepositoryTarget(await service.stageRepositoryTarget(next));
    await service.setWorkspaceObject({
      kind: "draft",
      key: "drafts/b.qmd",
      title: "B",
      workspaceRoot: "/legacy-injected-root",
    } as any);
    await service.send("write a draft", "gpt-5.6-sol", "high");

    expect(client.turnSteer).not.toHaveBeenCalled();
    expect(client.threadStart).toHaveBeenLastCalledWith(expect.objectContaining({
      cwd: "/B",
      runtimeWorkspaceRoots: ["/B"],
    }));
    expect((service as any).activeContext.researchObject).not.toHaveProperty("workspaceRoot");
    expect((service as any).activeContext.workspace.root).toBe("/B");
  });

  it.each([
    ["different target", "d".repeat(64)],
    ["no target", undefined],
  ])("never resumes a stored record with %s", async (_label, targetId) => {
    const client = {
      threadResume: vi.fn(),
      threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
      threadSetName: vi.fn(async () => ({})),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    const second = {
      ...paperContext(),
      attachment: { ...paperContext().attachment, id: 8, key: "SECOND" },
      workspace: { ...paperContext().workspace!, root: "/profile/papers/1-SECOND" },
    };
    internal.paperContexts.set("1-SECOND", second);
    internal.sessions.papers["1-SECOND"] = {
      threadId: "stored-thread",
      title: "Stored",
      workspace: "/legacy",
      recordedCwd: "/legacy",
      ...(targetId ? { targetId } : {}),
      updatedAt: "2026-07-31",
    };

    await service.openConversationForPaper("1-SECOND");

    expect(client.threadResume).not.toHaveBeenCalled();
    expect(client.threadStart).toHaveBeenCalledWith(expect.objectContaining({ cwd: "/repo" }));
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({
      threadId: "thread-new",
      targetId: TEST_TARGET_ID,
      recordedCwd: "/repo",
    });
  });

  it("rejects writable turns when no repository target is active", async () => {
    const client = { turnStart: vi.fn() };
    const service = new CodexService(
      {} as NativeBridge,
      { tools: [] } as unknown as ReaderContextService,
      "test",
      { onState: vi.fn(), onError: vi.fn() },
    );
    const internal = service as any;
    internal.client = client;
    internal.activeContext = paperContext();
    internal.activePaperKey = "1-ATTACH";
    service.state.connected = true;
    service.state.activeThreadId = "thread-a";

    await expect(service.send("write", "gpt-5.6-sol", "high"))
      .rejects.toThrow("active repository target");
    expect(client.turnStart).not.toHaveBeenCalled();
  });

  it("keeps every turn class blocked after interrupt acknowledgement until matching terminal events", async () => {
    const client = { turnInterrupt: vi.fn(async () => ({})) };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.registerOwnedTurn({
      targetId: TEST_TARGET_ID,
      targetEpoch: 1,
      root: "/repo",
      paperKey: "1-ATTACH",
      threadId: "thread-a",
      kind: "foreground",
    }, "turn-a");
    internal.registerOwnedTurn({
      targetId: TEST_TARGET_ID,
      targetEpoch: 1,
      root: "/repo",
      paperKey: "1-SECOND",
      threadId: "thread-background",
      kind: "background",
    }, "turn-background");
    internal.registerOwnedTurn({
      targetId: TEST_TARGET_ID,
      targetEpoch: 1,
      root: "/repo",
      paperKey: null,
      threadId: "thread-utility",
      kind: "utility",
    }, "turn-utility");
    internal.syncActiveTurnState();

    expect(service.repositoryTargetBlockers()).toEqual([{ kind: "running-turn" }]);
    let stopped = false;
    const stopping = service.stopForRepositoryTargetSwitch().then(() => { stopped = true; });
    await vi.waitFor(() => expect(client.turnInterrupt).toHaveBeenCalledTimes(3));
    await Promise.resolve();
    expect(stopped).toBe(false);
    expect(service.repositoryTargetBlockers()).toEqual([{ kind: "running-turn" }]);
    expect(client.turnInterrupt).toHaveBeenCalledWith({ threadId: "thread-a", turnId: "turn-a" });
    expect(client.turnInterrupt).toHaveBeenCalledWith({
      threadId: "thread-background",
      turnId: "turn-background",
    });
    expect(client.turnInterrupt).toHaveBeenCalledWith({
      threadId: "thread-utility",
      turnId: "turn-utility",
    });

    internal.handleNotification({
      method: "turn/completed",
      params: { threadId: "thread-a", turn: { id: "turn-a" } },
    });
    internal.handleNotification({
      method: "turn/failed",
      params: { threadId: "thread-background", turn: { id: "turn-background", error: "stopped" } },
    });
    await Promise.resolve();
    expect(stopped).toBe(false);
    internal.handleNotification({
      method: "turn/completed",
      params: { threadId: "thread-utility", turn: { id: "turn-utility" } },
    });
    await stopping;
    expect(service.repositoryTargetBlockers()).toEqual([]);
  });

  it("fails closed on interrupt failure and terminal timeout without deleting blockers", async () => {
    vi.useFakeTimers();
    try {
      const interruptFailure = new Error("interrupt transport failed");
      const client = { turnInterrupt: vi.fn(async () => { throw interruptFailure; }) };
      const { service } = serviceWithClient(client);
      const internal = service as any;
      internal.registerOwnedTurn({
        targetId: TEST_TARGET_ID, targetEpoch: 1, root: "/repo",
        paperKey: "1-ATTACH", threadId: "thread-a", kind: "foreground",
      }, "turn-a");
      await expect(service.stopForRepositoryTargetSwitch()).rejects.toBe(interruptFailure);
      expect(service.repositoryTargetBlockers()).toEqual([{ kind: "running-turn" }]);

      (client.turnInterrupt as any).mockResolvedValueOnce({});
      const timedOut = service.stopForRepositoryTargetSwitch();
      const guarded = timedOut.catch((error) => error);
      await vi.advanceTimersByTimeAsync(60_000);
      expect(String(await guarded)).toContain("terminal state");
      expect(service.repositoryTargetBlockers()).toEqual([{ kind: "running-turn" }]);
    }
    finally {
      vi.useRealTimers();
    }
  });

  it("closes A admission throughout controller persistence and reopens it on persistence failure", async () => {
    const client = {
      threadStart: vi.fn(async () => ({ thread: { id: "must-not-start" } })),
      threadSetName: vi.fn(async () => ({})),
      threadRollback: vi.fn(async () => ({ thread: { id: "must-not-rollback" } })),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    const persistEntered = deferred<void>();
    const releasePersist = deferred<void>();
    const controller = new RepositoryTargetController({
      checkBlockers: async () => service.repositoryTargetBlockers(),
      resolveBlockers: async () => "cancel" as const,
      stage: (snapshot: RepositoryTargetSnapshot) => service.stageRepositoryTarget(snapshot),
      persist: async () => {
        persistEntered.resolve();
        await releasePersist.promise;
      },
      publish: (_snapshot: RepositoryTargetSnapshot, staged: any) => service.commitRepositoryTarget(staged),
      disposeStaged: (staged: any) => service.disposeStagedRepositoryTarget(staged),
      disposeOld: async () => undefined,
      markDegraded: () => undefined,
    }, repositorySnapshot());
    const nextTarget = repositorySnapshot("/B", 2, "c".repeat(64)).target;
    const switching = controller.switchTo(nextTarget);
    await persistEntered.promise;
    const before = {
      paperContexts: [...internal.paperContexts.entries()],
      focusedPaperKey: internal.focusedPaperKey,
      activePaperKey: internal.activePaperKey,
      globalHistory: structuredClone(internal.globalHistory),
    };

    await expect(service.setWorkspaceObject({ kind: "draft", key: "drafts/a.qmd", title: "A" }))
      .rejects.toThrow("repository target switch");
    await expect(service.runUtilityTurn("old target", { timeoutMs: 100 }))
      .rejects.toThrow("repository target switch");
    await expect(service.rollbackConversation(1)).rejects.toThrow("repository target switch");
    await expect(service.newThread()).rejects.toThrow("repository target switch");
    await expect(service.switchThread("thread-other")).rejects.toThrow("repository target switch");
    await expect(service.setGlobalThreadPinned("thread-a", true))
      .rejects.toThrow("repository target switch");
    expect(client.threadStart).not.toHaveBeenCalled();
    expect(client.threadRollback).not.toHaveBeenCalled();
    expect([...internal.paperContexts.entries()]).toEqual(before.paperContexts);
    expect(internal.focusedPaperKey).toBe(before.focusedPaperKey);
    expect(internal.activePaperKey).toBe(before.activePaperKey);
    expect(internal.globalHistory).toEqual(before.globalHistory);
    expect(service.state.creatingThread).toBe(false);
    expect(service.state.switchingThreadId).toBeNull();
    expect(service.repositoryTargetBlockers()).toEqual([]);

    releasePersist.resolve();
    await switching;
    expect(service.repositoryBinding()).toEqual({
      targetId: "c".repeat(64), targetEpoch: 2, root: "/B",
    });

    const failedPersist = deferred<void>();
    const failedController = new RepositoryTargetController({
      checkBlockers: async () => service.repositoryTargetBlockers(),
      resolveBlockers: async () => "cancel" as const,
      stage: (snapshot: RepositoryTargetSnapshot) => service.stageRepositoryTarget(snapshot),
      persist: async () => { failedPersist.resolve(); throw new Error("preferences read-only"); },
      publish: (_snapshot: RepositoryTargetSnapshot, staged: any) => service.commitRepositoryTarget(staged),
      disposeStaged: (staged: any) => service.disposeStagedRepositoryTarget(staged),
      disposeOld: async () => undefined,
      markDegraded: () => undefined,
    }, repositorySnapshot("/B", 2, "c".repeat(64)));
    await expect(failedController.switchTo(repositorySnapshot("/C", 3, "d".repeat(64)).target))
      .rejects.toThrow("preferences read-only");
    await expect(failedPersist.promise).resolves.toBeUndefined();
    client.threadStart.mockResolvedValueOnce({ thread: { id: "thread-after-failure" } });
    await expect(service.setWorkspaceObject({ kind: "draft", key: "drafts/b.qmd", title: "B" }))
      .resolves.toBeUndefined();
    expect(client.threadStart).toHaveBeenCalledOnce();
  });

  it("reopens the exact A admission lease when staging rejects before persistence", async () => {
    const client = {
      threadStart: vi.fn(async () => ({ thread: { id: "thread-after-rejection" } })),
      threadSetName: vi.fn(async () => ({})),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    ownTurn(service, "thread-a", "turn-a");

    await expect(service.stageRepositoryTarget(
      repositorySnapshot("/B", 2, "c".repeat(64)),
    )).rejects.toThrow("turn is running");
    internal.handleNotification({
      method: "turn/completed",
      params: { threadId: "thread-a", turn: { id: "turn-a" } },
    });

    await expect(service.newThread()).resolves.toBeUndefined();
    expect(client.threadStart).toHaveBeenCalledOnce();
  });

  it("invalidates old-target history requests and ignores late old-target turn notifications", async () => {
    const listed = deferred<{ data: Array<{ id: string; name: string }>; nextCursor: null }>();
    const client = { threadList: vi.fn(() => listed.promise) };
    const { service } = serviceWithClient(client);

    const refreshing = service.refreshGlobalHistory();
    const guardedRefresh = refreshing.catch((error) => error);
    await vi.waitFor(() => expect(client.threadList).toHaveBeenCalledOnce());
    expect(client.threadList).toHaveBeenCalledWith(expect.objectContaining({ cwd: "/repo" }));
    const next = repositorySnapshot("/B", 2, "c".repeat(64));
    const staging = service.stageRepositoryTarget(next);
    listed.resolve({ data: [{ id: "old-global", name: "Old target" }], nextCursor: null });
    expect(String(await guardedRefresh)).toContain("repository target changed");
    service.commitRepositoryTarget(await staging);
    (service as any).handleNotification({
      method: "turn/started",
      params: { threadId: "thread-a", turn: { id: "late-old-turn" } },
    });

    expect(service.getGlobalHistory()).toEqual([]);
    expect(service.repositoryTargetBlockers()).toEqual([]);
  });

  it("does not carry a duplicate global-history pin from A into B", async () => {
    const client = {
      threadList: vi.fn(async () => ({
        data: [{ id: "duplicate", name: "B conversation" }],
        nextCursor: null,
      })),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    internal.globalHistory = [{
      id: "duplicate", title: "A conversation", updatedAt: "2026-07-31",
      source: "codex", sourceLabel: "Codex App", pinned: false,
    }];
    await service.setGlobalThreadPinned("duplicate", true);
    expect(internal.sessions.pinnedThreadsByTarget[TEST_TARGET_ID]).toEqual(["duplicate"]);

    service.commitRepositoryTarget(await service.stageRepositoryTarget(
      repositorySnapshot("/B", 2, "c".repeat(64)),
    ));
    await service.refreshGlobalHistory();

    expect(client.threadList).toHaveBeenLastCalledWith(expect.objectContaining({ cwd: "/B" }));
    expect(service.getGlobalHistory()).toEqual([
      expect.objectContaining({ id: "duplicate", pinned: false }),
    ]);
  });

  it("rejects late old-target tools and approvals even after the same paper opens on B", async () => {
    const invokeTool = vi.fn(async () => ({ text: "must not run" }));
    const readerContext = {
      tools: [{ name: "get_current_page", description: "Read", inputSchema: { type: "object" } }],
      invokeTool,
    } as unknown as ReaderContextService;
    const service = new CodexService(
      {} as NativeBridge,
      readerContext,
      "test",
      { onState: vi.fn(), onError: vi.fn() },
    );
    const internal = service as any;
    internal.client = {};
    service.state.connected = true;
    bindRepository(service, "/A");
    internal.sessions.papers["1-ATTACH"] = currentTargetRecord({
      threadId: "thread-a",
      title: "A",
      workspace: "/profile/papers/1-ATTACH",
      updatedAt: "2026-07-31",
    });

    const next = repositorySnapshot("/B", 2, "c".repeat(64));
    service.commitRepositoryTarget(await service.stageRepositoryTarget(next));
    internal.paperContexts.set("1-ATTACH", paperContext());

    await expect(internal.handleDynamicTool({
      threadId: "thread-a",
      turnId: "old-turn",
      tool: "get_current_page",
      arguments: {},
    })).resolves.toMatchObject({ success: false });
    expect(invokeTool).not.toHaveBeenCalled();

    const approval = await internal.requestUserApproval({
      kind: "commandExecution",
      method: "item/commandExecution/requestApproval",
      requestId: "old-approval",
      params: {
        threadId: "thread-a",
        turnId: "old-turn",
        itemId: "old-item",
        startedAtMs: 1,
        command: "pwd",
        cwd: "/B",
        availableDecisions: ["accept", "decline"],
      },
    });
    expect(approval).toEqual({ decision: "decline" });
  });

  it("rejects an in-flight A tool after B reuses the same thread id and never persists A evidence into B", async () => {
    const toolResult = deferred<{ pages: number[]; snippets: string[] }>();
    const invokeTool = vi.fn(() => toolResult.promise);
    const readerContext = {
      tools: [{ name: "get_current_page", description: "Read", inputSchema: { type: "object" } }],
      invokeTool,
    } as unknown as ReaderContextService;
    const service = new CodexService(
      {} as NativeBridge,
      readerContext,
      "test",
      { onState: vi.fn(), onError: vi.fn() },
    );
    const internal = service as any;
    bindRepository(service, "/A", 1, TEST_TARGET_ID);
    internal.client = {};
    internal.saveSessions = vi.fn(async () => undefined);
    internal.activeContext = paperContext();
    internal.activePaperKey = "1-ATTACH";
    internal.paperContexts.set("1-ATTACH", paperContext());
    const ownerA = internal.rememberThreadOwner("same-thread", "1-ATTACH", "foreground", {
      targetId: TEST_TARGET_ID, targetEpoch: 1, root: "/A",
    });
    internal.registerOwnedTurn(ownerA, "turn-a");

    const pending = internal.handleDynamicTool({
      threadId: "same-thread",
      turnId: "turn-a",
      tool: "get_current_page",
      arguments: {},
    });
    await vi.waitFor(() => expect(invokeTool).toHaveBeenCalledOnce());
    internal.handleNotification({
      method: "turn/completed",
      params: { threadId: "same-thread", turn: { id: "turn-a" } },
    });
    const next = repositorySnapshot("/B", 2, "c".repeat(64));
    let staged = false;
    const staging = service.stageRepositoryTarget(next).then((value) => {
      staged = true;
      return value;
    });
    await Promise.resolve();
    expect(staged).toBe(false);
    toolResult.resolve({ pages: [3], snippets: ["A evidence"] });
    await expect(pending).resolves.toMatchObject({ success: false });
    service.commitRepositoryTarget(await staging);
    internal.activeContext = paperContext();
    internal.activePaperKey = "1-ATTACH";
    internal.paperContexts.set("1-ATTACH", paperContext());
    const ownerB = internal.rememberThreadOwner("same-thread", "1-ATTACH", "foreground", {
      targetId: "c".repeat(64), targetEpoch: 2, root: "/B",
    });
    internal.registerOwnedTurn(ownerB, "turn-b");
    expect(internal.sessions.evidence).toBeUndefined();
    expect(internal.saveSessions).not.toHaveBeenCalled();
  });
});

describe("Codex session target persistence", () => {
  it("updates duplicate thread ids by stable paper/history location while preserving unknown fields", async () => {
    const source = {
      version: 1,
      papers: {
        paper: {
          threadId: "duplicate",
          title: "Current",
          workspace: "/legacy/current",
          updatedAt: "2026-07-31",
          unknownRecordField: { current: true },
        },
      },
      history: {
        paper: [{
          threadId: "duplicate",
          title: "History",
          workspace: "/legacy/history",
          updatedAt: "2026-07-30",
          unknownRecordField: { history: true },
        }],
      },
      activeThreadId: "duplicate",
      unknownTopLevelField: { preserve: true },
    };
    let written = "";
    vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });
    vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
    vi.stubGlobal("IOUtils", {
      exists: vi.fn(async () => true),
      readUTF8: vi.fn(async () => JSON.stringify(source)),
      makeDirectory: vi.fn(async () => undefined),
      writeUTF8: vi.fn(async (_path: string, value: string) => { written = value; }),
    });

    const snapshot = await readSessionRecords();
    expect(snapshot.activeThreadId).toBe("duplicate");
    expect(snapshot.records).toEqual([
      expect.objectContaining({ recordedCwd: null, unknownRecordField: { current: true } }),
      expect.objectContaining({ recordedCwd: null, unknownRecordField: { history: true } }),
    ]);

    await saveSessionRecords(snapshot, [
      { ...snapshot.records[0]!, targetId: "c".repeat(64) },
      { ...snapshot.records[1]!, targetId: "d".repeat(64) },
    ]);

    const persisted = JSON.parse(written);
    expect(persisted.unknownTopLevelField).toEqual({ preserve: true });
    expect(persisted.papers.paper).toMatchObject({
      threadId: "duplicate",
      recordedCwd: null,
      targetId: "c".repeat(64),
      unknownRecordField: { current: true },
    });
    expect(persisted.history.paper[0]).toMatchObject({
      threadId: "duplicate",
      recordedCwd: null,
      targetId: "d".repeat(64),
      unknownRecordField: { history: true },
    });
  });

  it("treats only an absent session file as empty and rejects unreadable or invalid stores", async () => {
    vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });
    vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
    const readUTF8 = vi.fn();
    const exists = vi.fn(async () => false);
    vi.stubGlobal("IOUtils", { exists, readUTF8 });

    await expect(readSessionRecords()).resolves.toMatchObject({
      file: { version: 1, papers: {} },
      records: [],
      activeThreadId: null,
    });
    expect(readUTF8).not.toHaveBeenCalled();

    exists.mockResolvedValue(true);
    const unreadable = new Error("profile temporarily unavailable");
    readUTF8.mockRejectedValueOnce(unreadable);
    await expect(readSessionRecords()).rejects.toBe(unreadable);

    readUTF8.mockResolvedValueOnce("{malformed");
    await expect(readSessionRecords()).rejects.toBeInstanceOf(SyntaxError);

    readUTF8.mockResolvedValueOnce(JSON.stringify({
      version: 1,
      papers: { paper: { threadId: "thread", workspace: "/paper" } },
    }));
    await expect(readSessionRecords()).rejects.toThrow("invalid persisted record");
  });

  it.each([
    ["activeThreadId", { activeThreadId: 42 }],
    ["openThreads", { openThreads: "thread-a" }],
    ["openThreads item", { openThreads: ["thread-a", 42] }],
    ["openThreadRefs", { openThreadRefs: {} }],
    ["openThreadRefs item", { openThreadRefs: [{ targetId: "bad", paperKey: "paper", threadId: "thread" }] }],
    ["pinnedThreads", { pinnedThreads: {} }],
    ["pinnedThreadsByTarget", { pinnedThreadsByTarget: { bad: ["thread"] } }],
    ["checkpoints", { checkpoints: [] }],
    ["checkpoint bucket", { checkpoints: { paper: {} } }],
    ["checkpoint", { checkpoints: { paper: [{ id: "checkpoint" }] } }],
    ["anchors", { anchors: [] }],
    ["anchor bucket", { anchors: { paper: {} } }],
    ["anchor", { anchors: { paper: [{ anchorId: "anchor" }] } }],
    ["evidence", { evidence: [] }],
    ["evidence bucket", { evidence: { thread: {} } }],
    ["evidence record", { evidence: { thread: [{ id: "evidence" }] } }],
    ["paperTitle", { papers: { paper: currentTargetRecord({
      threadId: "thread", title: "Title", paperTitle: 42,
      workspace: "/paper", updatedAt: "2026-07-31",
    }) } }],
    ["backend", { papers: { paper: currentTargetRecord({
      threadId: "thread", title: "Title", backend: "other",
      workspace: "/paper", updatedAt: "2026-07-31",
    }) } }],
    ["targetId", { papers: { paper: {
      threadId: "thread", title: "Title", targetId: "not-a-target-id",
      recordedCwd: "/repo", workspace: "/paper", updatedAt: "2026-07-31",
    } } }],
  ])("rejects malformed known session field %s without writing", async (_label, patch) => {
    const writeUTF8 = vi.fn(async () => undefined);
    vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });
    vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
    vi.stubGlobal("IOUtils", {
      exists: vi.fn(async () => true),
      readUTF8: vi.fn(async () => JSON.stringify({
        version: 1,
        papers: {},
        ...patch,
      })),
      writeUTF8,
    });

    await expect(readSessionRecords()).rejects.toThrow("Codex session store");
    expect(writeUTF8).not.toHaveBeenCalled();
  });

  it("preserves unknown fields while validating all known session fields", async () => {
    const source = {
      version: 1,
      papers: {
        paper: currentTargetRecord({
          threadId: "thread",
          title: "Title",
          paperTitle: "Paper",
          workspace: "/paper",
          updatedAt: "2026-07-31",
          backend: "codex" as const,
          futureRecordField: { preserve: true },
        }),
      },
      activeThreadId: null,
      openThreads: ["thread"],
      pinnedThreads: ["thread"],
      futureTopLevelField: { preserve: true },
    };
    vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });
    vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
    vi.stubGlobal("IOUtils", {
      exists: vi.fn(async () => true),
      readUTF8: vi.fn(async () => JSON.stringify(source)),
    });

    const snapshot = await readSessionRecords();
    expect(snapshot.file).toMatchObject(source);
  });
});

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
    bindRepository(service, "/Users/test/research-loop");

    await service.setWorkspaceObject({
      kind: "collection",
      key: "collection:ABC123",
      title: "Quantum Algorithms",
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
      papers: { "1-ATTACH": currentTargetRecord({ threadId: "thread-a", title: "A", workspace: "/profile/papers/1-ATTACH", updatedAt: "2026-07-28" }) },
      history: { "1-ATTACH": [currentTargetRecord({ threadId: "thread-b", title: "B", workspace: "/profile/papers/1-ATTACH", updatedAt: "2026-07-27" })] },
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

  it("pins a targetless global Codex conversation but starts a target-bound paper thread", async () => {
    const client = {
      threadList: vi.fn(async () => ({
        data: [{ id: "global-a", name: "Global task", source: "vscode", updatedAt: 200 }],
        nextCursor: null,
      })),
      threadResume: vi.fn(),
      threadStart: vi.fn(async () => ({ thread: { id: "target-thread" } })),
      threadSetName: vi.fn(async () => ({})),
      turnInterrupt: vi.fn(async () => ({})),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => {});
    internal.sessions.papers["1-ATTACH"] = currentTargetRecord({
      threadId: "thread-a",
      title: "Paper thread",
      workspace: "/profile/papers/1-ATTACH",
      updatedAt: "2026-07-22T00:00:00.000Z",
      backend: "codex",
    });
    await service.refreshGlobalHistory();

    await service.setGlobalThreadPinned("global-a", true);
    expect(service.getGlobalHistory()[0]?.pinned).toBe(true);
    expect(internal.sessions.pinnedThreads).toEqual(["global-a"]);

    await service.openGlobalThread("global-a");
    expect(client.threadResume).not.toHaveBeenCalled();
    expect(client.threadStart).toHaveBeenCalledWith(expect.objectContaining({ cwd: "/repo" }));
    expect(service.state.activeThreadId).toBe("target-thread");
    expect(internal.sessions.papers["1-ATTACH"]).toMatchObject({
      threadId: "target-thread",
      recordedCwd: "/repo",
      targetId: TEST_TARGET_ID,
    });
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
        "1-ATTACH": currentTargetRecord({ threadId: "thread-a", title: "A Paper", paperTitle: "A Paper", workspace: first.workspace!.root, updatedAt: "2026-07-30" }),
        "1-SECOND": currentTargetRecord({ threadId: "thread-b", title: "Different proof", paperTitle: "A Different Paper", workspace: second.workspace!.root, updatedAt: "2026-07-30" }),
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
        "1-ATTACH": currentTargetRecord({ threadId: "thread-a", title: "A", workspace: first.workspace!.root, updatedAt: "2026-07-30" }),
        "1-SECOND": currentTargetRecord({ threadId: "thread-b", title: "B", workspace: second.workspace!.root, updatedAt: "2026-07-30" }),
      },
      openThreads: ["thread-a", "thread-b"],
    };
    internal.registerOwnedTurn(internal.threadOwners.get("thread-a"), "turn-a");
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
        "1-ATTACH": currentTargetRecord({ threadId: "thread-a", title: "A", workspace: "/profile/papers/1-ATTACH", updatedAt: "2026-07-30" }),
      },
      history: {
        "1-ATTACH": [currentTargetRecord({ threadId: "thread-b", title: "B", workspace: "/profile/papers/1-ATTACH", updatedAt: "2026-07-29" })],
      },
      openThreads: ["thread-a", "thread-b"],
    };

    await service.closeThread("thread-b");

    expect(service.getThreadOptions().map((thread) => thread.id)).toEqual(["thread-a"]);
    expect(internal.sessions.history["1-ATTACH"]).toEqual([
      expect.objectContaining({ threadId: "thread-b" }),
    ]);
  });

  it("does not select an open tab assigned to another repository target", async () => {
    const { service } = serviceWithClient({ turnInterrupt: vi.fn(async () => ({})) });
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => {});
    const second = {
      ...paperContext(),
      attachment: { ...paperContext().attachment, key: "SECOND" },
      workspace: { ...paperContext().workspace!, root: "/profile/papers/1-SECOND" },
    };
    internal.paperContexts.set("1-SECOND", second);
    internal.sessions = {
      version: 1,
      papers: {
        "1-ATTACH": currentTargetRecord({
          threadId: "thread-a",
          title: "Current target",
          workspace: "/profile/papers/1-ATTACH",
          updatedAt: "2026-07-30",
        }),
        "1-SECOND": {
          threadId: "thread-old-target",
          title: "Old target",
          workspace: "/profile/papers/1-SECOND",
          recordedCwd: "/old",
          targetId: "d".repeat(64),
          updatedAt: "2026-07-29",
        },
      },
      openThreads: ["thread-a", "thread-old-target"],
    };

    await expect(service.closeThread("thread-a")).resolves.toBeUndefined();

    expect(service.state.activeThreadId).toBeNull();
    expect(service.getThreadOptions()).toEqual([]);
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
        writableRoots: ["/repo/drafts", "/repo/literature", "/repo/work"],
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
    ownTurn(service, "thread-a", "turn-a");
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
            write: ["/repo/drafts"],
          },
        },
      },
    });
    await expect(permission).resolves.toEqual({
      permissions: {
        fileSystem: {
          read: ["/papers"],
          write: ["/repo/drafts"],
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
    ownTurn(service, "thread-a", "turn-a");
    const requestApproval = (service as any).requestUserApproval.bind(service);
    const requestedPermissions = {
      network: { enabled: true },
      fileSystem: {
        read: null,
        write: null,
        entries: [{
          access: "write",
          path: { type: "path", path: "/repo/drafts/staging" },
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
    bindRepository(service);
    internal.activeContext = paperContext();
    internal.activePaperKey = "1-ATTACH";
    internal.paperContexts.set("1-ATTACH", paperContext());
    service.state.activeThreadId = "thread-a";
    ownTurn(service, "thread-a", "turn-a");

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

  it("lets an in-flight proposal persist its anchor before interrupt waits for terminal", async () => {
    const releaseProposal = deferred<void>();
    const anchorUpdated = deferred<void>();
    const client = { turnInterrupt: vi.fn(async () => ({})) };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    internal.sessions.anchors = {
      "1-ATTACH": [{
        anchorId: "anchor-a",
        libraryID: 1,
        itemKey: "PARENT",
        attachmentKey: "ATTACH",
        pdfSha256: null,
        selectedText: "selection",
        question: "question",
        threadId: "thread-a",
        turnRange: [0, 0],
        status: "open",
        createdAt: "2026-07-25T00:00:00.000Z",
      }],
    };
    service.setAgentToolProvider({
      tools: [{ name: "apply_reviewed_annotation", description: "Apply", inputSchema: { type: "object" } }],
      invokeTool: vi.fn(async () => {
        await releaseProposal.promise;
        await service.updateAnchorById("anchor-a", { annotationKey: "ANN-A" });
        anchorUpdated.resolve();
        return { annotationKey: "ANN-A" };
      }),
    });
    ownTurn(service, "thread-a", "turn-a");

    const toolCall = internal.handleDynamicTool({
      threadId: "thread-a",
      turnId: "turn-a",
      callId: "call-a",
      namespace: null,
      tool: "apply_reviewed_annotation",
      arguments: {},
    });
    await vi.waitFor(() => expect(
      (service as any).targetAdmission.inFlight.size,
    ).toBeGreaterThan(0));
    const interrupting = service.interrupt();
    await vi.waitFor(() => expect(client.turnInterrupt).toHaveBeenCalledOnce());
    releaseProposal.resolve();

    try {
      await expect(Promise.race([
        anchorUpdated.promise.then(() => true),
        new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 50)),
      ])).resolves.toBe(true);
    }
    finally {
      internal.handleNotification({
        method: "turn/completed",
        params: { threadId: "thread-a", turn: { id: "turn-a" } },
      });
      await Promise.allSettled([toolCall, interrupting]);
    }
    expect(service.getAllAnchors()[0]).toMatchObject({ annotationKey: "ANN-A" });
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
    bindRepository(service);
    internal.saveSessions = vi.fn(async () => undefined);
    internal.activeContext = second;
    internal.activePaperKey = "1-SECOND";
    internal.paperContexts.set("1-ATTACH", first);
    internal.paperContexts.set("1-SECOND", second);
    internal.rememberThreadOwner("thread-a", "1-ATTACH", "background", service.repositoryBinding());
    internal.rememberThreadOwner("thread-b", "1-SECOND", "foreground", service.repositoryBinding());
    service.state.activeThreadId = "thread-b";
    ownTurn(service, "thread-a", "turn-a", "1-ATTACH", "background");

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
    bindRepository(service, "/Users/test/research-loop");
    await service.setWorkspaceObject({
      kind: "collection",
      key: "COLLECTION",
      title: "Quantum Algorithms",
      libraryID: 1,
    });
    ownTurn(service, "thread-object", "turn-object", "1-QLAB-collection-COLLECTION");

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
    internal.sessions.papers["1-ATTACH"] = currentTargetRecord({
      threadId: "thread-a", title: "A", workspace: "/paper", updatedAt: "2026-07-31",
    });
    internal.sessions.checkpoints = {
      "1-ATTACH": [{
        id: "checkpoint-1",
        sourceThreadId: "thread-a",
        beforeTurnId: "turn-mutating",
        label: "Before metadata update",
        createdAt: "2026-07-23T00:00:00.000Z",
        turnDiff: "--- old\n+++ new",
        targetId: TEST_TARGET_ID,
        targetEpoch: 1,
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

  it("filters checkpoints by target and refuses an old-target source before forking", async () => {
    const client = { threadFork: vi.fn() };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.sessions.papers["1-ATTACH"] = currentTargetRecord({
      threadId: "thread-a", title: "A", workspace: "/paper", updatedAt: "2026-07-31",
    });
    internal.sessions.checkpoints = {
      "1-ATTACH": [{
        id: "checkpoint-a",
        sourceThreadId: "thread-a",
        beforeTurnId: "turn-a",
        label: "A",
        createdAt: "2026-07-31",
        turnDiff: null,
        targetId: TEST_TARGET_ID,
        targetEpoch: 1,
      }],
    };
    const next = repositorySnapshot("/B", 2, "c".repeat(64));
    service.commitRepositoryTarget(await service.stageRepositoryTarget(next));
    internal.activeContext = paperContext();
    internal.activePaperKey = "1-ATTACH";

    expect(service.getCheckpoints()).toEqual([]);
    await expect(service.restoreCheckpoint("checkpoint-a"))
      .rejects.toThrow("checkpoint could not be found");
    expect(client.threadFork).not.toHaveBeenCalled();
  });

  it("persists a canonical checkpoint fork before publishing live state and rolls back on save failure", async () => {
    const client = {
      threadFork: vi.fn(async () => ({ thread: { id: "fork-canonical", turns: [] } })),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.sessions.papers["1-ATTACH"] = currentTargetRecord({
      threadId: "thread-a", title: "A", workspace: "/paper", updatedAt: "2026-07-31",
    });
    internal.sessions.checkpoints = {
      "1-ATTACH": [{
        id: "checkpoint-a", sourceThreadId: "thread-a", beforeTurnId: "turn-a",
        label: "A", createdAt: "2026-07-31", turnDiff: null,
        targetId: TEST_TARGET_ID, targetEpoch: 1,
      }],
    };
    const saveFailure = new Error("profile read-only");
    const before = structuredClone(internal.sessions);
    internal.saveSessions = vi.fn(async (next: any, activeThreadId: string) => {
      expect(service.state.activeThreadId).toBe("thread-a");
      expect(next.papers["1-ATTACH"].threadId).toBe("fork-canonical");
      expect(activeThreadId).toBe("fork-canonical");
      throw saveFailure;
    });

    await expect(service.restoreCheckpoint("checkpoint-a")).rejects.toBe(saveFailure);
    expect(internal.sessions).toEqual(before);
    expect(service.state.activeThreadId).toBe("thread-a");
    expect(internal.threadOwners.has("fork-canonical")).toBe(false);
  });

  it("serializes rollback, persists its canonical id before live publication, and preserves duplicate B records", async () => {
    const rolledBack = deferred<{ thread: { id: string } }>();
    const client = { threadRollback: vi.fn(() => rolledBack.promise) };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.sessions = {
      version: 1,
      papers: {
        "1-ATTACH": currentTargetRecord({
          threadId: "duplicate", title: "A", workspace: "/paper", updatedAt: "2026-07-31",
        }),
      },
      history: {
        "1-ATTACH": [{
          threadId: "duplicate", title: "B", workspace: "/paper",
          recordedCwd: "/B", targetId: "c".repeat(64), updatedAt: "2026-07-30",
        }],
      },
      openThreads: ["duplicate"],
    };
    service.state.activeThreadId = "duplicate";
    internal.activePaperKey = "1-ATTACH";
    internal.forgetThreadOwner("thread-a");
    internal.rememberThreadOwner("duplicate", "1-ATTACH", "foreground", {
      targetId: TEST_TARGET_ID, targetEpoch: 1, root: "/repo",
    });
    const persisted = deferred<void>();
    internal.saveSessions = vi.fn(async (next: any, activeThreadId: string) => {
      expect(service.state.activeThreadId).toBe("duplicate");
      expect(next.papers["1-ATTACH"].threadId).toBe("rollback-canonical");
      expect(activeThreadId).toBe("rollback-canonical");
      expect(next.history["1-ATTACH"]).toEqual([
        expect.objectContaining({ threadId: "duplicate", targetId: "c".repeat(64) }),
      ]);
      persisted.resolve();
    });

    const rollback = service.rollbackConversation(2);
    await vi.waitFor(() => expect(client.threadRollback).toHaveBeenCalledOnce());
    let staged = false;
    const staging = service.stageRepositoryTarget(
      repositorySnapshot("/B", 2, "c".repeat(64)),
    ).then((value) => { staged = true; return value; });
    await Promise.resolve();
    expect(staged).toBe(false);
    rolledBack.resolve({ thread: { id: "rollback-canonical" } });
    await persisted.promise;
    await rollback;
    expect(service.state.activeThreadId).toBe("rollback-canonical");
    expect(internal.threadOwners.get("rollback-canonical")).toMatchObject({
      targetId: TEST_TARGET_ID, targetEpoch: 1, paperKey: "1-ATTACH",
    });
    service.commitRepositoryTarget(await staging);
    expect(service.state.activeThreadId).toBeNull();
  });

  it("keeps rollback live state unchanged when canonical persistence fails", async () => {
    const saveFailure = new Error("profile read-only");
    const client = {
      threadRollback: vi.fn(async () => ({ thread: { id: "rollback-canonical" } })),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.sessions.papers["1-ATTACH"] = currentTargetRecord({
      threadId: "thread-a", title: "A", workspace: "/paper", updatedAt: "2026-07-31",
    });
    internal.sessions.openThreads = ["thread-a"];
    const before = structuredClone(internal.sessions);
    internal.saveSessions = vi.fn(async () => { throw saveFailure; });

    await expect(service.rollbackConversation(1)).rejects.toBe(saveFailure);
    expect(internal.sessions).toEqual(before);
    expect(service.state.activeThreadId).toBe("thread-a");
    expect(internal.threadOwners.has("rollback-canonical")).toBe(false);
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
  it("binds hidden threads and turns to the active repository with a network-off sandbox", async () => {
    const client = {
      threadStart: vi.fn(async () => ({ thread: { id: "util-bound" } })),
      turnStart: vi.fn(async () => ({ turn: { id: "turn-bound" } })),
    };
    const { service } = serviceWithClient(client);
    const pending = service.runUtilityTurn("summarize", { timeoutMs: 5000 });
    await vi.waitFor(() => expect(client.turnStart).toHaveBeenCalledOnce());

    expect(client.threadStart).toHaveBeenCalledWith(expect.objectContaining({
      cwd: "/repo",
      runtimeWorkspaceRoots: ["/repo"],
      approvalPolicy: "never",
      sandbox: "read-only",
    }));
    expect(client.turnStart).toHaveBeenCalledWith(expect.objectContaining({
      threadId: "util-bound",
      cwd: "/repo",
      runtimeWorkspaceRoots: ["/repo"],
      approvalPolicy: "never",
      sandboxPolicy: { type: "readOnly", networkAccess: false },
    }));
    expect(service.repositoryTargetBlockers()).toEqual([{ kind: "running-turn" }]);
    (service as any).handleNotification({
      method: "turn/failed",
      params: { threadId: "util-bound", turn: { id: "turn-bound", error: "done" } },
    });
    await expect(pending).rejects.toThrow("done");
    expect(service.repositoryTargetBlockers()).toEqual([]);
  });

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
    await vi.waitFor(() => expect((service as any).ownedTurns.size).toBe(1));
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

  it("rejects the utility caller on timeout while retaining the target-switch blocker", async () => {
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
    expect(service.repositoryTargetBlockers()).toEqual([{ kind: "running-turn" }]);
    (service as any).handleNotification({
      method: "turn/completed",
      params: { threadId: "util-2", turn: { id: "t9" } },
    });
    expect(service.repositoryTargetBlockers()).toEqual([]);
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
    expect((service as any).ownedTurns.size).toBe(0);
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
    await vi.waitFor(() => expect((service as any).ownedTurns.size).toBe(1));
    (service as any).handleNotification({
      method: "turn/failed",
      params: { threadId: "util-4", turn: { id: "t1", error: { message: "沙盒被Reject" } } },
    });
    await expect(pending).rejects.toThrow("沙盒被Reject");
    expect((service as any).ownedTurns.size).toBe(0);
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
    bindRepository(service);
    internal.client = client;
    internal.saveSessions = vi.fn(async () => {});
    service.state.connected = true;
    internal.sessions = {
      version: 1,
      papers: {
        "1-SECOND": currentTargetRecord({
          threadId: "thread-b",
          title: "Stored conversation",
          paperTitle: "A Different Paper",
          workspace: "/profile/papers/1-SECOND",
          updatedAt: "2026-07-30",
        }),
      },
      openThreads: ["thread-b"],
    };
    return { service, internal, callbacks };
  }

  it("scopes duplicate open-thread ids to their target and stable paper location", async () => {
    const { service } = serviceWithClient({});
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    const second = reopeningContext();
    internal.paperContexts.set("1-SECOND", second);
    internal.sessions = {
      version: 1,
      papers: {
        "1-ATTACH": currentTargetRecord({
          threadId: "duplicate", title: "Target A", workspace: "/paper-a", updatedAt: "2026-07-31",
        }),
        "1-SECOND": {
          threadId: "duplicate", title: "Target B", workspace: "/paper-b",
          recordedCwd: "/B", targetId: "c".repeat(64), updatedAt: "2026-07-31",
        },
      },
      openThreads: ["duplicate"],
    };
    service.state.activeThreadId = "duplicate";
    internal.activePaperKey = "1-ATTACH";
    internal.activeContext = paperContext();
    expect(service.getThreadOptions()).toEqual([
      expect.objectContaining({ id: "duplicate", title: "Target A" }),
    ]);

    const targetB = repositorySnapshot("/B", 2, "c".repeat(64));
    service.commitRepositoryTarget(await service.stageRepositoryTarget(targetB));
    internal.paperContexts.set("1-SECOND", second);
    expect(service.getThreadOptions()).toEqual([
      expect.objectContaining({ id: "duplicate", title: "Target B" }),
    ]);
    internal.activePaperKey = "1-SECOND";
    internal.activeContext = second;
    service.state.activeThreadId = "duplicate";
    await service.closeThread("duplicate");

    expect(internal.sessions.openThreadRefs).toEqual(expect.arrayContaining([
      { targetId: TEST_TARGET_ID, paperKey: "1-ATTACH", threadId: "duplicate" },
    ]));
    expect(internal.sessions.openThreadRefs).not.toEqual(expect.arrayContaining([
      { targetId: "c".repeat(64), paperKey: "1-SECOND", threadId: "duplicate" },
    ]));
  });

  it("resumes the active target's historical default instead of retargeting the paper's current record", async () => {
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
      threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
      threadStart: vi.fn(),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    const second = reopeningContext();
    internal.sessions = {
      version: 1,
      papers: {
        "1-SECOND": currentTargetRecord({
          threadId: "duplicate", title: "Target A", workspace: "/paper", updatedAt: "2026-07-31",
        }),
      },
      history: {
        "1-SECOND": [{
          threadId: "duplicate", title: "Target B", workspace: "/paper",
          recordedCwd: "/B", targetId: "c".repeat(64), updatedAt: "2026-07-30",
        }],
      },
      openThreads: ["duplicate"],
    };
    const targetB = repositorySnapshot("/B", 2, "c".repeat(64));
    service.commitRepositoryTarget(await service.stageRepositoryTarget(targetB));
    internal.paperContexts.set("1-SECOND", second);

    await service.openConversationForPaper("1-SECOND");

    expect(client.threadResume).toHaveBeenCalledWith(expect.objectContaining({ threadId: "duplicate", cwd: "/B" }));
    expect(client.threadStart).not.toHaveBeenCalled();
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({
      threadId: "duplicate", targetId: "c".repeat(64), title: "Target B",
    });
    expect(internal.sessions.history["1-SECOND"]).toEqual(expect.arrayContaining([
      expect.objectContaining({ threadId: "duplicate", targetId: TEST_TARGET_ID, title: "Target A" }),
    ]));
  });

  it("canonicalizes only B's duplicate record and open tab while preserving A", async () => {
    const client = {
      threadResume: vi.fn(async () => ({ thread: { id: "duplicate-resume", turns: [] } })),
      threadRead: vi.fn(async () => ({ thread: { id: "canonical-b", turns: [] } })),
    };
    const { service } = serviceWithClient(client);
    const internal = service as any;
    internal.saveSessions = vi.fn(async () => undefined);
    const second = reopeningContext();
    internal.sessions = {
      version: 1,
      papers: {
        "1-SECOND": currentTargetRecord({
          threadId: "duplicate", title: "Target A", workspace: "/paper", updatedAt: "2026-07-31",
        }),
      },
      history: {
        "1-SECOND": [{
          threadId: "duplicate", title: "Target B", workspace: "/paper",
          recordedCwd: "/B", targetId: "c".repeat(64), updatedAt: "2026-07-30",
        }],
      },
      openThreads: ["duplicate"],
    };
    service.commitRepositoryTarget(await service.stageRepositoryTarget(
      repositorySnapshot("/B", 2, "c".repeat(64)),
    ));
    internal.paperContexts.set("1-SECOND", second);

    await service.openConversationForPaper("1-SECOND");

    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({
      threadId: "canonical-b", targetId: "c".repeat(64),
    });
    expect(internal.sessions.history["1-SECOND"]).toEqual(expect.arrayContaining([
      expect.objectContaining({ threadId: "duplicate", targetId: TEST_TARGET_ID }),
    ]));
    expect(internal.sessions.openThreadRefs).toEqual(expect.arrayContaining([
      { targetId: TEST_TARGET_ID, paperKey: "1-SECOND", threadId: "duplicate" },
      { targetId: "c".repeat(64), paperKey: "1-SECOND", threadId: "canonical-b" },
    ]));
  });

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

  it("preserves a stored conversation on operational resume failures", async () => {
    const cases = [
      ["timeout", new CodexRequestTimeoutError("thread/resume", 30_000, 7)],
      ["disconnect", new CodexDisconnectedError()],
      ["authentication RPC", new CodexRpcError({ code: -32603, message: "authentication required" }, "thread/resume", 8)],
      ["generic error", new Error("thread resume failed")],
      ["thread read", new Error("thread read failed")],
      ["session save", new Error("profile is read-only")],
    ] as const;

    for (const [name, failure] of cases) {
      const client = {
        threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
        threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
        threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
        threadSetName: vi.fn(async () => ({})),
      };
      if (name !== "thread read" && name !== "session save") {
        client.threadResume.mockRejectedValueOnce(failure);
      }
      if (name === "thread read") client.threadRead.mockRejectedValueOnce(failure);
      const seedPaperContext = vi.fn(async () => reopeningContext());
      const { service, internal } = serviceWithSeeder(client, seedPaperContext);
      internal.rememberThreadOwner("thread-b", "1-SECOND", "foreground", service.repositoryBinding());
      if (name === "session save") {
        internal.saveSessions = vi.fn(async () => { throw failure; });
      }
      const before = structuredClone(internal.sessions);
      const mapBefore = [...internal.threadOwners.entries()];

      await expect(service.openConversationForPaper("1-SECOND"), name).rejects.toBe(failure);

      expect(client.threadStart, name).not.toHaveBeenCalled();
      expect(internal.sessions, name).toEqual(before);
      expect([...internal.threadOwners.entries()], name).toEqual(mapBefore);
      expect(service.state.activeThreadId, name).toBeNull();
    }
  });

  it("preserves stored state on timeout through every stored-conversation entry point", async () => {
    const entries = [
      ["setPaper", (service: CodexService) => service.setPaper(reopeningContext())],
      ["switchThread", (service: CodexService) => service.switchThread("thread-b")],
      ["openGlobalThread", (service: CodexService) => service.openGlobalThread("thread-b")],
      ["openConversationForPaper", (service: CodexService) => service.openConversationForPaper("1-SECOND")],
    ] as const;

    for (const [name, open] of entries) {
      const timeout = new CodexRequestTimeoutError("thread/resume", 30_000, 11);
      const client = {
        threadResume: vi.fn(async () => { throw timeout; }),
        threadRead: vi.fn(),
        threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
        threadSetName: vi.fn(async () => ({})),
      };
      const { service, internal } = serviceWithSeeder(client, async () => reopeningContext());
      internal.rememberThreadOwner("thread-b", "1-SECOND", "foreground", service.repositoryBinding());
      internal.globalHistory = [{
        id: "thread-b",
        title: "Stored conversation",
        updatedAt: "2026-07-30T00:00:00.000Z",
        source: "codex",
        sourceLabel: "Codex CLI",
        pinned: false,
      }];
      if (name === "openGlobalThread") {
        internal.activeContext = paperContext();
        internal.activePaperKey = "1-ATTACH";
        internal.rememberThreadOwner("thread-a", "1-ATTACH", "foreground", service.repositoryBinding());
        service.state.activeThreadId = "thread-a";
      }
      const before = structuredClone(internal.sessions);
      const activeBefore = service.state.activeThreadId;
      const mapBefore = [...internal.threadOwners.entries()];

      await expect(open(service), name).rejects.toBe(timeout);

      expect(client.threadStart, name).not.toHaveBeenCalled();
      expect(internal.sessions, name).toEqual(before);
      expect([...internal.threadOwners.entries()], name).toEqual(mapBefore);
      expect(service.state.activeThreadId, name).toBe(activeBefore);
    }
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

  it("archives an explicitly missing default once before starting one fresh thread", async () => {
    const client = {
      threadResume: vi.fn(async () => {
        throw new CodexRpcError({ code: -32602, message: "thread not found" }, "thread/resume", 12);
      }),
      threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
      threadSetName: vi.fn(async () => ({})),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service, internal } = serviceWithSeeder(client, seedPaperContext);

    await service.openConversationForPaper("1-SECOND");

    expect(service.state.activeThreadId).toBe("thread-new");
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({ threadId: "thread-new" });
    expect(client.threadStart).toHaveBeenCalledTimes(1);
    expect(internal.sessions.history["1-SECOND"].filter((record: { threadId: string }) => record.threadId === "thread-b")).toHaveLength(1);
    expect(internal.sessions.openThreads).toEqual(["thread-new"]);
  });

  it("rolls back selected conversation state when fresh replacement persistence fails", async () => {
    const saveFailure = new Error("profile is read-only");
    const client = {
      threadResume: vi.fn(async () => {
        throw new CodexRpcError({ code: -32602, message: "thread not found" }, "thread/resume", 14);
      }),
      threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
      threadSetName: vi.fn(async () => ({})),
    };
    const { service, internal } = serviceWithSeeder(client, async () => reopeningContext());
    internal.saveSessions = vi.fn(async () => { throw saveFailure; });
    const before = structuredClone(internal.sessions);

    await expect(service.openConversationForPaper("1-SECOND")).rejects.toBe(saveFailure);

    expect(client.threadStart).toHaveBeenCalledTimes(1);
    expect(internal.sessions).toEqual(before);
    expect(internal.threadOwners.has("thread-new")).toBe(false);
    expect(service.state).toMatchObject({ activeThreadId: null, activeTurnId: null, running: false });
  });

  it("preserves a concurrent global pin after a stored conversation resume commits", async () => {
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
      threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
    };
    const { service, internal } = serviceWithSeeder(client, async () => reopeningContext());
    internal.globalHistory = [{
      id: "global-a",
      title: "Pinned task",
      updatedAt: "2026-07-30T00:00:00.000Z",
      source: "codex",
      sourceLabel: "Codex CLI",
      pinned: false,
    }];
    const resumeSaveEntered = deferred<void>();
    const releaseResumeSave = deferred<void>();
    let saveCalls = 0;
    let persisted: Record<string, unknown> | null = null;
    internal.saveSessions = vi.fn(async (next = internal.sessions) => {
      const candidate = structuredClone(next) as Record<string, unknown>;
      saveCalls += 1;
      if (saveCalls === 1) {
        resumeSaveEntered.resolve();
        await releaseResumeSave.promise;
      }
      persisted = candidate;
    });

    const opening = service.openConversationForPaper("1-SECOND");
    await resumeSaveEntered.promise;
    const pinning = service.setGlobalThreadPinned("global-a", true);

    expect(service.getGlobalHistory()[0]?.pinned).toBe(true);
    releaseResumeSave.resolve();
    await Promise.all([opening, pinning]);

    expect(internal.sessions.pinnedThreads).toEqual(["global-a"]);
    expect(persisted).toMatchObject({
      pinnedThreads: ["global-a"],
      papers: { "1-SECOND": { threadId: "thread-b" } },
    });
  });

  it("preserves a queued global pin after missing-thread replacement rolls back", async () => {
    const saveFailure = new Error("profile is read-only");
    const client = {
      threadResume: vi.fn(async () => {
        throw new CodexRpcError({ code: -32602, message: "thread not found" }, "thread/resume", 16);
      }),
      threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
      threadSetName: vi.fn(async () => ({})),
    };
    const { service, internal } = serviceWithSeeder(client, async () => reopeningContext());
    internal.globalHistory = [{
      id: "global-a",
      title: "Pinned task",
      updatedAt: "2026-07-30T00:00:00.000Z",
      source: "codex",
      sourceLabel: "Codex CLI",
      pinned: false,
    }];
    const replacementSaveEntered = deferred<void>();
    const rejectReplacementSave = deferred<void>();
    let saveCalls = 0;
    let persisted: Record<string, unknown> | null = null;
    internal.saveSessions = vi.fn(async (next = internal.sessions) => {
      const candidate = structuredClone(next) as Record<string, unknown>;
      saveCalls += 1;
      if (saveCalls === 1) {
        replacementSaveEntered.resolve();
        await rejectReplacementSave.promise;
        throw saveFailure;
      }
      persisted = candidate;
    });

    const opening = service.openConversationForPaper("1-SECOND");
    await replacementSaveEntered.promise;
    const pinning = service.setGlobalThreadPinned("global-a", true);

    expect(service.getGlobalHistory()[0]?.pinned).toBe(true);
    rejectReplacementSave.resolve();
    await expect(opening).rejects.toBe(saveFailure);
    await pinning;

    expect(internal.sessions).toMatchObject({
      pinnedThreads: ["global-a"],
      papers: { "1-SECOND": { threadId: "thread-b" } },
    });
    expect(persisted).toMatchObject({
      pinnedThreads: ["global-a"],
      papers: { "1-SECOND": { threadId: "thread-b" } },
    });
  });

  it("persists the authoritative read id as the selected stored conversation", async () => {
    const client = {
      threadResume: vi.fn(async () => ({ thread: { id: "thread-b-resume", turns: [] } })),
      threadRead: vi.fn(async () => ({ thread: { id: "thread-b-canonical", turns: [] } })),
    };
    const { service, internal } = serviceWithSeeder(client, async () => reopeningContext());
    let persistedActiveThreadId: string | null | undefined;
    internal.saveSessions = vi.fn(async (
      _next: unknown,
      activeThreadId = service.state.activeThreadId,
    ) => {
      persistedActiveThreadId = activeThreadId;
    });
    internal.rememberThreadOwner("thread-b", "1-OTHER", "foreground", service.repositoryBinding());

    await service.openConversationForPaper("1-SECOND");

    expect(client.threadRead).toHaveBeenCalledWith("thread-b-resume", true);
    expect(internal.sessions.papers["1-SECOND"].threadId).toBe("thread-b-canonical");
    expect(internal.threadOwners.get("thread-b-canonical")?.paperKey).toBe("1-SECOND");
    expect(internal.threadOwners.has("thread-b")).toBe(false);
    expect(internal.sessions.openThreads).toEqual(["thread-b-canonical"]);
    expect(internal.sessions.activeThreadId).toBe("thread-b-canonical");
    expect(service.state.activeThreadId).toBe("thread-b-canonical");
    expect(persistedActiveThreadId).toBe("thread-b-canonical");
  });

  it("does not retain a requested alias when a queued global open canonicalizes the active thread", async () => {
    let service!: CodexService;
    let resumeCalls = 0;
    let readCalls = 0;
    let activeAtQueuedResume: string | null = null;
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => {
        resumeCalls += 1;
        if (resumeCalls === 2) {
          activeAtQueuedResume = service.state.activeThreadId;
          return { thread: { id: "thread-b-resume", turns: [] } };
        }
        return { thread: { id: threadId, turns: [] } };
      }),
      threadRead: vi.fn(async () => {
        readCalls += 1;
        return { thread: { id: readCalls === 1 ? "thread-b" : "thread-b-canonical", turns: [] } };
      }),
    };
    const fixture = serviceWithSeeder(client, async () => reopeningContext());
    service = fixture.service;
    const { internal } = fixture;
    const persisted: Array<{ openThreads?: string[] }> = [];
    internal.saveSessions = vi.fn(async (next = internal.sessions) => {
      persisted.push(structuredClone(next));
    });
    internal.globalHistory = [{
      id: "thread-b",
      title: "Stored conversation",
      updatedAt: "2026-07-30T00:00:00.000Z",
      source: "codex",
      sourceLabel: "Codex CLI",
      pinned: false,
    }];

    const selecting = service.switchThread("thread-b");
    const opening = service.openGlobalThread("thread-b");
    await Promise.all([selecting, opening]);

    expect(activeAtQueuedResume).toBe("thread-b");
    expect(persisted.at(-1)?.openThreads).toEqual(["thread-b-canonical"]);
    expect(internal.sessions.openThreads).toEqual(["thread-b-canonical"]);
    expect(service.state.activeThreadId).toBe("thread-b-canonical");
  });

  it("does not retain a missing requested id when a queued global open replaces the active thread", async () => {
    let service!: CodexService;
    let resumeCalls = 0;
    let activeAtQueuedResume: string | null = null;
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => {
        resumeCalls += 1;
        if (resumeCalls === 2) {
          activeAtQueuedResume = service.state.activeThreadId;
          throw new CodexRpcError({ code: -32602, message: "thread not found" }, "thread/resume", 15);
        }
        return { thread: { id: threadId, turns: [] } };
      }),
      threadRead: vi.fn(async () => ({ thread: { id: "thread-b", turns: [] } })),
      threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
      threadSetName: vi.fn(async () => ({})),
    };
    const fixture = serviceWithSeeder(client, async () => reopeningContext());
    service = fixture.service;
    const { internal } = fixture;
    const persisted: Array<{ openThreads?: string[] }> = [];
    internal.saveSessions = vi.fn(async (next = internal.sessions) => {
      persisted.push(structuredClone(next));
    });
    internal.globalHistory = [{
      id: "thread-b",
      title: "Stored conversation",
      updatedAt: "2026-07-30T00:00:00.000Z",
      source: "codex",
      sourceLabel: "Codex CLI",
      pinned: false,
    }];

    const selecting = service.switchThread("thread-b");
    const opening = service.openGlobalThread("thread-b");
    await Promise.all([selecting, opening]);

    expect(activeAtQueuedResume).toBe("thread-b");
    expect(persisted.at(-1)?.openThreads).toEqual(["thread-new"]);
    expect(internal.sessions.openThreads).toEqual(["thread-new"]);
    expect(service.state.activeThreadId).toBe("thread-new");
  });

  it.each([
    ["local History", (service: CodexService) => service.switchThread("thread-b")],
    ["global History", (service: CodexService) => service.openGlobalThread("thread-b")],
  ])("archives a missing %s record and a different default before creating a fresh sole default", async (_source, open) => {
    const client = {
      threadResume: vi.fn(async () => {
        throw new CodexRpcError({ code: -32602, message: "thread not found" }, "thread/resume", 13);
      }),
      threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
      threadSetName: vi.fn(async () => ({})),
    };
    const { service, internal } = serviceWithSeeder(client, async () => reopeningContext());
    internal.sessions.papers["1-SECOND"] = currentTargetRecord({
      threadId: "thread-a",
      title: "Current default",
      workspace: "/profile/papers/1-SECOND",
      updatedAt: "2026-07-30",
    });
    internal.sessions.history = {
      "1-SECOND": [currentTargetRecord({
        threadId: "thread-b",
        title: "Historical conversation",
        workspace: "/profile/papers/1-SECOND",
        updatedAt: "2026-07-29",
      })],
    };
    internal.globalHistory = [{
      id: "thread-b",
      title: "Historical conversation",
      updatedAt: "2026-07-29T00:00:00.000Z",
      source: "codex",
      sourceLabel: "Codex CLI",
      pinned: false,
    }];

    await open(service);

    expect(client.threadStart).toHaveBeenCalledTimes(1);
    expect(internal.sessions.papers["1-SECOND"].threadId).toBe("thread-new");
    expect(internal.sessions.history["1-SECOND"].filter((record: { threadId: string }) => record.threadId === "thread-b")).toHaveLength(1);
    expect(internal.sessions.history["1-SECOND"].filter((record: { threadId: string }) => record.threadId === "thread-a")).toHaveLength(1);
  });

  it("preserves conversation state when no-PDF seeding fails through every public reopen entry", async () => {
    const entries = [
      {
        name: "local conversation tab",
        prepare: (_internal: any) => {},
        open: (service: CodexService) => service.switchThread("thread-b"),
      },
      {
        name: "local History",
        prepare: (internal: any) => {
          const historical = internal.sessions.papers["1-SECOND"];
          internal.sessions.papers["1-SECOND"] = {
            ...historical,
            threadId: "thread-default",
            title: "Current default",
          };
          internal.sessions.history = { "1-SECOND": [historical] };
          internal.sessions.openThreads = ["thread-default", "thread-b"];
        },
        open: (service: CodexService) => service.switchThread("thread-b"),
      },
      {
        name: "global History",
        prepare: (internal: any) => {
          internal.globalHistory = [{
            id: "thread-b",
            title: "Stored conversation",
            updatedAt: "2026-07-30T00:00:00.000Z",
            source: "codex",
            sourceLabel: "Codex CLI",
            pinned: false,
          }];
        },
        open: (service: CodexService) => service.openGlobalThread("thread-b"),
      },
      {
        name: "library item command",
        prepare: (_internal: any) => {},
        open: (service: CodexService) => service.openConversationForPaper("1-SECOND"),
      },
    ];

    for (const entry of entries) {
      const client = {
        threadResume: vi.fn(),
        threadStart: vi.fn(),
      };
      const seedPaperContext = vi.fn(async () => {
        throw new Error("This Zotero item has no readable PDF attachment");
      });
      const { service, internal } = serviceWithSeeder(client, seedPaperContext);
      entry.prepare(internal);
      const before = {
        sessions: structuredClone(internal.sessions),
        activeThreadId: service.state.activeThreadId,
        activePaperKey: internal.activePaperKey,
        activeContext: internal.activeContext,
        paperContexts: [...internal.paperContexts.entries()],
        threadOwners: [...internal.threadOwners.entries()],
      };

      await expect(entry.open(service), entry.name)
        .rejects.toThrow("This Zotero item has no readable PDF attachment");

      expect(seedPaperContext, entry.name).toHaveBeenCalledWith("1-SECOND");
      expect(client.threadResume, entry.name).not.toHaveBeenCalled();
      expect(client.threadStart, entry.name).not.toHaveBeenCalled();
      expect(internal.sessions, entry.name).toEqual(before.sessions);
      expect(service.state.activeThreadId, entry.name).toBe(before.activeThreadId);
      expect(service.state.switchingThreadId, entry.name).toBeNull();
      expect(internal.activePaperKey, entry.name).toBe(before.activePaperKey);
      expect(internal.activeContext, entry.name).toBe(before.activeContext);
      expect([...internal.paperContexts.entries()], entry.name).toEqual(before.paperContexts);
      expect([...internal.threadOwners.entries()], entry.name).toEqual(before.threadOwners);
    }
  });
});
