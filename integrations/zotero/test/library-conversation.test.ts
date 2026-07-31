import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CodexDisconnectedError,
  CodexRequestTimeoutError,
  CodexRpcError,
} from "../src/codex-app-server";
import { CodexService } from "../src/codex-service";
import type { NativeBridge } from "../src/native-bridge";
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
  const client = {
    threadStart: vi.fn().mockResolvedValue({ thread: { id: "library-thread" } }),
    threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
    threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
    threadSetName: vi.fn(async () => ({})),
  };
  const service = new CodexService(
    {} as NativeBridge,
    { tools: [] } as unknown as ReaderContextService,
    "test",
    { onState: vi.fn(), onError: vi.fn() },
  );
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
  return { service, client, saved };
}

describe("library conversations", () => {
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
