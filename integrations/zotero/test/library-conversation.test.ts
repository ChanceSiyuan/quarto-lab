import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CodexDisconnectedError } from "../src/codex-app-server";
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
});
