import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CodexDisconnectedError,
  CodexRequestTimeoutError,
  CodexRpcError,
} from "../src/codex-app-server";
import { CodexService } from "../src/codex-service";
import type { LibraryMessageContext } from "../src/library-conversation";
import type { NativeBridge } from "../src/native-bridge";
import { READER_CONTEXT_TOOLS } from "../src/reader-context";
import type { ReaderContextService } from "../src/reader-context";

beforeEach(() => {
  vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });
  vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
});

afterEach(() => vi.unstubAllGlobals());

function libraryServiceHarness(options: {
  activePaperThread?: string;
  storedLibraryThread?: string;
} = {}) {
  const callbacks = { onState: vi.fn(), onError: vi.fn() };
  const paperTools = {
    tools: [{
      name: "zotero_propose_changes",
      description: "Paper-only proposal",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
    }],
    invokeTool: vi.fn().mockResolvedValue({ proposed: true }),
  };
  const libraryTools = {
    tools: [{
      name: "zotero_lookup_citations",
      description: "Resolve bounded citation requests",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
    }],
    invokeTool: vi.fn().mockResolvedValue({ candidates: ["candidate-1"] }),
  };
  const readerContext = {
    tools: [
      READER_CONTEXT_TOOLS.find((tool) => tool.name === "zotero_get_current_page")!,
      READER_CONTEXT_TOOLS.find((tool) => tool.name === "zotero_search_library_items")!,
    ],
    invokeTool: vi.fn().mockResolvedValue({ matches: [] }),
  } as unknown as ReaderContextService;
  const client = {
    threadStart: vi.fn().mockResolvedValue({ thread: { id: "library-thread" } }),
    threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
    threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
    threadSetName: vi.fn(async () => ({})),
    turnStart: vi.fn().mockResolvedValue({ turn: { id: "library-turn" } }),
    turnInterrupt: vi.fn().mockResolvedValue({}),
  };
  const service = new CodexService(
    {} as NativeBridge,
    readerContext,
    "test",
    callbacks,
    paperTools,
  );
  service.setLibraryToolProvider(libraryTools);
  const internal = service as any;
  const saved: any[] = [];
  internal.client = client;
  internal.sessions = {
    version: 1,
    papers: options.activePaperThread
      ? {
          "1-ATTACH": {
            threadId: options.activePaperThread,
            title: "Paper thread",
            workspace: "/profile/papers/1-ATTACH",
            updatedAt: "2026-07-31T00:00:00.000Z",
          },
        }
      : {},
    ...(options.storedLibraryThread
      ? {
          libraries: {
            "library:1": {
              threadId: options.storedLibraryThread,
              title: "My Library",
              workspace: "/profile/libraries/1",
              updatedAt: "2026-07-31T00:00:00.000Z",
            },
          },
        }
      : {}),
  };
  internal.saveSessions = vi.fn(async (next: unknown) => { saved.push(next); });
  service.state.connected = true;
  service.state.activeThreadId = options.activePaperThread || null;
  return { service, client, saved, callbacks, libraryTools, paperTools, readerContext };
}

function libraryMessageContext(selectedCount = 2): LibraryMessageContext {
  return {
    libraryID: 1,
    libraryName: "My Library",
    collection: { key: "COLL1", path: "Research / Quantum" },
    selectedItems: Array.from({ length: selectedCount }, (_, index) => ({
      key: `ITEM${index + 1}`,
      itemType: "journalArticle",
      title: `Paper ${index + 1}`,
      creators: "Ada Lovelace",
      year: "2026",
      doi: `10.1000/example-${index + 1}`,
    })),
    omittedItemCount: 0,
  };
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

describe("library conversations", () => {
  it("reports library opening state only to that library subject", async () => {
    const { service, callbacks } = libraryServiceHarness();

    await service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" });

    expect(callbacks.onState).toHaveBeenCalledWith({ kind: "library", key: "library:1" });
    expect(callbacks.onState).not.toHaveBeenCalledWith();
  });

  it("starts a read-only library turn without changing the running paper", async () => {
    const { service, client } = libraryServiceHarness({ activePaperThread: "paper-thread" });

    await service.sendLibraryMessage(
      { libraryID: 1, libraryName: "My Library" },
      { text: "Find these citations", model: "gpt-5.6-codex", effort: "medium" },
      libraryMessageContext(),
    );

    expect(client.turnStart).toHaveBeenCalledWith(expect.objectContaining({
      threadId: "library-thread",
      cwd: "/profile/zotkit",
      runtimeWorkspaceRoots: [],
      approvalPolicy: "never",
      sandboxPolicy: { type: "readOnly", networkAccess: false },
    }));
    expect(service.state.activeThreadId).toBe("paper-thread");
    expect(service.state.running).toBe(false);
    expect(service.getLibraryConversationState({ libraryID: 1, libraryName: "My Library" }))
      .toMatchObject({ running: true, activeTurnId: "library-turn" });
  });

  it("rejects a message whose context belongs to another normalized library id", async () => {
    const { service, client } = libraryServiceHarness();
    const context = { ...libraryMessageContext(), libraryID: "2" };

    await expect(service.sendLibraryMessage(
      { libraryID: 1, libraryName: "My Library" },
      { text: "Do not cross libraries", model: "gpt-5.6-codex", effort: "medium" },
      context,
    )).rejects.toThrow("does not match");

    expect(client.threadStart).not.toHaveBeenCalled();
    expect(client.turnStart).not.toHaveBeenCalled();
  });

  it("resumes a stored library conversation before sending its first turn", async () => {
    const { service, client } = libraryServiceHarness({ storedLibraryThread: "stored-library" });

    await service.sendLibraryMessage(
      { libraryID: 1, libraryName: "My Library" },
      { text: "Continue", model: "gpt-5.6-codex", effort: "medium" },
      libraryMessageContext(),
    );

    expect(client.threadResume).toHaveBeenCalledWith(expect.objectContaining({
      threadId: "stored-library",
    }));
    expect(client.turnStart).toHaveBeenCalledWith(expect.objectContaining({
      threadId: "stored-library",
    }));
  });

  it("copies and freezes a turn context before routing its exact dynamic tool call", async () => {
    const { service, libraryTools, paperTools } = libraryServiceHarness();
    const context = libraryMessageContext(1);

    await service.sendLibraryMessage(
      { libraryID: 1, libraryName: "My Library" },
      { text: "Resolve it", model: "gpt-5.6-codex", effort: "medium" },
      context,
    );
    (context.selectedItems as unknown as Array<{ title: string }>)[0]!.title = "Changed after send";
    context.collection!.path = "Changed / Collection";

    const result = await (service as any).handleDynamicTool({
      threadId: "library-thread",
      turnId: "library-turn",
      callId: "call-1",
      namespace: null,
      tool: "zotero_lookup_citations",
      arguments: { requests: [{ client_ref: "r1", doi: "10.1000/example" }] },
    });

    expect(result.success).toBe(true);
    expect(libraryTools.invokeTool).toHaveBeenCalledWith(
      "zotero_lookup_citations",
      { requests: [{ client_ref: "r1", doi: "10.1000/example" }] },
      expect.objectContaining({
        collection: { key: "COLL1", path: "Research / Quantum" },
        selectedItems: [expect.objectContaining({ title: "Paper 1" })],
      }),
      { threadId: "library-thread", turnId: "library-turn" },
    );
    const routedContext = libraryTools.invokeTool.mock.calls[0]![2];
    expect(Object.isFrozen(routedContext)).toBe(true);
    expect(Object.isFrozen(routedContext.collection)).toBe(true);
    expect(Object.isFrozen(routedContext.selectedItems)).toBe(true);
    expect(Object.isFrozen(routedContext.selectedItems[0])).toBe(true);
    expect(paperTools.invokeTool).not.toHaveBeenCalled();
  });

  it("rejects a library tool call whose turn id does not own the captured context", async () => {
    const { service, libraryTools, paperTools } = libraryServiceHarness();
    await service.sendLibraryMessage(
      { libraryID: 1, libraryName: "My Library" },
      { text: "Resolve it", model: "gpt-5.6-codex", effort: "medium" },
      libraryMessageContext(1),
    );

    const result = await (service as any).handleDynamicTool({
      threadId: "library-thread",
      turnId: "other-turn",
      callId: "call-stale",
      namespace: null,
      tool: "zotero_lookup_citations",
      arguments: {},
    });

    expect(result).toMatchObject({
      success: false,
      contentItems: [{ text: expect.stringContaining("context is unavailable") }],
    });
    expect(libraryTools.invokeTool).not.toHaveBeenCalled();
    expect(paperTools.invokeTool).not.toHaveBeenCalled();
  });

  it("exposes only library-safe reader tools and library provider tools on library threads", async () => {
    const { service, client } = libraryServiceHarness();

    await service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" });

    const dynamicTools = client.threadStart.mock.calls[0]![0].dynamicTools;
    expect(dynamicTools.map((tool: { name: string }) => tool.name)).toEqual([
      "zotero_search_library_items",
      "zotero_lookup_citations",
    ]);
  });

  it("allows only one running turn for a library subject across concurrent senders", async () => {
    const { service, client } = libraryServiceHarness();
    const subject = { libraryID: 1, libraryName: "My Library" };

    const results = await Promise.allSettled([
      service.sendLibraryMessage(subject, { text: "First", model: "gpt-5.6-codex", effort: "medium" }, libraryMessageContext()),
      service.sendLibraryMessage(subject, { text: "Second", model: "gpt-5.6-codex", effort: "medium" }, libraryMessageContext()),
    ]);

    expect(results.map((result) => result.status)).toEqual(["fulfilled", "rejected"]);
    expect((results[1] as PromiseRejectedResult).reason).toMatchObject({
      message: expect.stringContaining("already running"),
    });
    expect(client.threadStart).toHaveBeenCalledOnce();
    expect(client.turnStart).toHaveBeenCalledOnce();
  });

  it("stops only the requested library turn and preserves a running paper", async () => {
    const { service, client } = libraryServiceHarness({ activePaperThread: "paper-thread" });
    const internal = service as any;
    internal.runningTurns.set("paper-thread", "paper-turn");
    internal.syncActiveTurnState();
    await service.sendLibraryMessage(
      { libraryID: 1, libraryName: "My Library" },
      { text: "Resolve it", model: "gpt-5.6-codex", effort: "medium" },
      libraryMessageContext(),
    );

    await service.stopLibraryTurn({ libraryID: 1, libraryName: "My Library" });

    expect(client.turnInterrupt).toHaveBeenCalledWith({
      threadId: "library-thread",
      turnId: "library-turn",
    });
    expect(service.getLibraryConversationState({ libraryID: 1, libraryName: "My Library" }))
      .toMatchObject({ running: false, activeTurnId: null });
    expect(service.state).toMatchObject({
      activeThreadId: "paper-thread",
      running: true,
      activeTurnId: "paper-turn",
    });
  });

  it("ignores late retired events while a replacement turn is starting", async () => {
    const { service, client, libraryTools } = libraryServiceHarness();
    const replacement = deferred<{ turn: { id: string } }>();
    client.turnStart
      .mockResolvedValueOnce({ turn: { id: "old-turn" } })
      .mockImplementationOnce(() => replacement.promise);
    const subject = { libraryID: 1, libraryName: "My Library" };

    await service.sendLibraryMessage(
      subject,
      { text: "Old request", model: "gpt-5.6-codex", effort: "medium" },
      libraryMessageContext(1),
    );
    await service.stopLibraryTurn(subject);
    const replacementSend = service.sendLibraryMessage(
      subject,
      { text: "Replacement request", model: "gpt-5.6-codex", effort: "medium" },
      { ...libraryMessageContext(1), selectedItems: [{
        ...libraryMessageContext(1).selectedItems[0]!,
        title: "Replacement paper",
      }] },
    );
    await vi.waitFor(() => expect(client.turnStart).toHaveBeenCalledTimes(2));

    (service as any).handleNotification({
      method: "turn/started",
      params: { threadId: "library-thread", turn: { id: "old-turn" } },
    });
    (service as any).handleNotification({
      method: "turn/completed",
      params: { threadId: "library-thread", turn: { id: "old-turn" } },
    });
    replacement.resolve({ turn: { id: "replacement-turn" } });
    await replacementSend;

    expect(service.getLibraryConversationState(subject)).toMatchObject({
      running: true,
      activeTurnId: "replacement-turn",
    });
    await expect((service as any).handleDynamicTool({
      threadId: "library-thread",
      turnId: "replacement-turn",
      callId: "call-replacement",
      namespace: null,
      tool: "zotero_lookup_citations",
      arguments: {},
    })).resolves.toMatchObject({ success: true });
    expect(libraryTools.invokeTool).toHaveBeenCalledWith(
      "zotero_lookup_citations",
      {},
      expect.objectContaining({
        selectedItems: [expect.objectContaining({ title: "Replacement paper" })],
      }),
      { threadId: "library-thread", turnId: "replacement-turn" },
    );
    await expect(service.sendLibraryMessage(
      subject,
      { text: "Third request", model: "gpt-5.6-codex", effort: "medium" },
      libraryMessageContext(),
    )).rejects.toThrow("already running");
  });

  it("buffers an early terminal event until turnStart identifies the pending turn", async () => {
    const { service, client } = libraryServiceHarness();
    const started = deferred<{ turn: { id: string } }>();
    client.turnStart.mockImplementationOnce(() => started.promise);
    const subject = { libraryID: 1, libraryName: "My Library" };
    const sending = service.sendLibraryMessage(
      subject,
      { text: "Quick request", model: "gpt-5.6-codex", effort: "medium" },
      libraryMessageContext(),
    );
    await vi.waitFor(() => expect(client.turnStart).toHaveBeenCalledOnce());

    (service as any).handleNotification({
      method: "turn/completed",
      params: { threadId: "library-thread", turn: { id: "quick-turn" } },
    });
    expect(service.getLibraryConversationState(subject).running).toBe(true);
    started.resolve({ turn: { id: "quick-turn" } });
    await sending;

    expect(service.getLibraryConversationState(subject)).toMatchObject({
      running: false,
      activeTurnId: null,
    });
  });

  it.each(["turn/completed", "turn/failed"])(
    "routes %s to the owning library subject without changing paper state",
    async (method) => {
      const { service, callbacks } = libraryServiceHarness({ activePaperThread: "paper-thread" });
      const internal = service as any;
      internal.runningTurns.set("paper-thread", "paper-turn");
      internal.syncActiveTurnState();
      await service.sendLibraryMessage(
        { libraryID: 1, libraryName: "My Library" },
        { text: "Resolve it", model: "gpt-5.6-codex", effort: "medium" },
        libraryMessageContext(),
      );
      callbacks.onState.mockClear();

      internal.handleNotification({
        method,
        params: {
          threadId: "library-thread",
          turn: { id: "library-turn", ...(method === "turn/failed" ? { error: "resolver failed" } : {}) },
        },
      });

      expect(service.getLibraryConversationState({ libraryID: 1, libraryName: "My Library" }))
        .toMatchObject({
          running: false,
          activeTurnId: null,
          ...(method === "turn/failed" ? { error: "resolver failed" } : {}),
        });
      expect(service.state).toMatchObject({
        activeThreadId: "paper-thread",
        running: true,
        activeTurnId: "paper-turn",
      });
      expect(callbacks.onState).toHaveBeenCalledWith({ kind: "library", key: "library:1" });
      expect(callbacks.onState).not.toHaveBeenCalledWith();
    },
  );

  it("uses one stable subject per library without selecting it in Workbench", async () => {
    const { service, client, saved } = libraryServiceHarness({ activePaperThread: "paper-thread" });
    const subject = { libraryID: 1, libraryName: "My Library" };

    const state = await service.openLibraryConversation(subject);

    expect(state.subject.key).toBe("library:1");
    expect(state.threadId).toBe("library-thread");
    expect(service.state.activeThreadId).toBe("paper-thread");
    expect(client.threadStart).toHaveBeenCalledOnce();
    expect(saved.at(-1)?.libraries?.["library:1"]?.threadId).toBe("library-thread");
    expect(saved.at(-1)?.papers?.["1-ATTACH"]?.threadId).toBe("paper-thread");
  });

  it("resumes the stored library thread and preserves operational failures", async () => {
    const { service, client } = libraryServiceHarness({ storedLibraryThread: "stored-library" });
    client.threadResume.mockRejectedValueOnce(new CodexDisconnectedError("offline"));

    await expect(service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" }))
      .rejects.toThrow("offline");
    expect(client.threadStart).not.toHaveBeenCalled();
    expect(service.getLibraryConversationState({ libraryID: 1, libraryName: "My Library" }).error)
      .toContain("offline");
  });

  it("replaces only an explicitly missing library thread", async () => {
    const { service, client, saved } = libraryServiceHarness({ storedLibraryThread: "missing-library" });
    client.threadResume.mockRejectedValueOnce(new CodexRpcError(
      { code: -32602, message: "thread not found" },
      "thread/resume",
      1,
    ));

    await expect(service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" }))
      .resolves.toMatchObject({ threadId: "library-thread" });

    expect(client.threadStart).toHaveBeenCalledOnce();
    expect(saved.at(-1)?.libraries?.["library:1"]?.threadId).toBe("library-thread");
  });

  it("persists the canonical id returned after a library resume", async () => {
    const { service, client, saved } = libraryServiceHarness({ storedLibraryThread: "resume-alias" });
    client.threadResume.mockResolvedValueOnce({ thread: { id: "resume-alias", turns: [] } });
    client.threadRead.mockResolvedValueOnce({ thread: { id: "canonical-library", turns: [] } });

    await expect(service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" }))
      .resolves.toMatchObject({ threadId: "canonical-library" });

    expect(client.threadStart).not.toHaveBeenCalled();
    expect(saved.at(-1)?.libraries?.["library:1"]?.threadId).toBe("canonical-library");
  });

  it.each([
    ["disconnect", new CodexDisconnectedError("offline")],
    ["timeout", new CodexRequestTimeoutError("thread/resume", 30_000, 2)],
  ])("preserves the stored library record after a %s", async (_kind, error) => {
    const { service, client, saved } = libraryServiceHarness({ storedLibraryThread: "stored-library" });
    const internal = service as any;
    const original = structuredClone(internal.sessions.libraries["library:1"]);
    client.threadResume.mockRejectedValueOnce(error);

    await expect(service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" }))
      .rejects.toBe(error);

    expect(client.threadStart).not.toHaveBeenCalled();
    expect(saved).toEqual([]);
    expect(internal.sessions.libraries["library:1"]).toEqual(original);
  });

  it("preserves the stored library record when the resumed thread cannot be read", async () => {
    const { service, client, saved } = libraryServiceHarness({ storedLibraryThread: "stored-library" });
    const internal = service as any;
    const original = structuredClone(internal.sessions.libraries["library:1"]);
    const readFailure = new Error("read failed");
    client.threadRead.mockRejectedValueOnce(readFailure);

    await expect(service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" }))
      .rejects.toBe(readFailure);

    expect(client.threadStart).not.toHaveBeenCalled();
    expect(saved).toEqual([]);
    expect(internal.sessions.libraries["library:1"]).toEqual(original);
  });

  it("rejects an incompatible stored backend without replacing its library thread", async () => {
    const { service, client, saved } = libraryServiceHarness({ storedLibraryThread: "engine-library" });
    const internal = service as any;
    internal.sessions.libraries["library:1"].backend = "engine";
    const original = structuredClone(internal.sessions.libraries["library:1"]);

    await expect(service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" }))
      .rejects.toThrow("different backend");

    expect(client.threadResume).not.toHaveBeenCalled();
    expect(client.threadStart).not.toHaveBeenCalled();
    expect(saved).toEqual([]);
    expect(internal.sessions.libraries["library:1"]).toEqual(original);
  });

  it("keeps library threads out of appended global history after canonicalization", async () => {
    const { service, client } = libraryServiceHarness({ storedLibraryThread: "resume-alias" });
    const internal = service as any;
    client.threadResume.mockResolvedValueOnce({ thread: { id: "resume-alias", turns: [] } });
    client.threadRead.mockResolvedValueOnce({ thread: { id: "canonical-library", turns: [] } });
    (client as any).threadList = vi.fn(async () => ({
      data: [{ id: "ordinary-thread", name: "Ordinary", source: "cli", updatedAt: 2 }],
      nextCursor: null,
    }));
    internal.globalHistory = [{
      id: "canonical-library",
      title: "Library transcript",
      updatedAt: "2026-07-31T00:00:00.000Z",
      source: "codex",
      sourceLabel: "Codex CLI",
    }];
    internal.globalHistoryCursor = "next-page";
    internal.globalHistoryQuery = "";

    await service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" });
    await service.refreshGlobalHistory("", true);

    expect(service.getGlobalHistory().map((thread) => thread.id)).toEqual(["ordinary-thread"]);
  });

  it("rejects attempts to open a library thread from global Workbench history", async () => {
    const { service } = libraryServiceHarness({ storedLibraryThread: "stored-library" });
    const internal = service as any;
    internal.globalHistory = [{
      id: "stored-library",
      title: "Library transcript",
      updatedAt: "2026-07-31T00:00:00.000Z",
      source: "codex",
      sourceLabel: "Codex CLI",
    }];

    await expect(service.openGlobalThread("stored-library"))
      .rejects.toThrow("Library Palette");
  });
});
