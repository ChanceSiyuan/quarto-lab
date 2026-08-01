import { describe, expect, it, vi } from "vitest";
import type { AgentClient } from "../src/agent-client";
import { ENGINE_CAPABILITIES } from "../src/agent-client";
import { CodexAppServerClient } from "../src/codex-app-server";
import { CodexService } from "../src/codex-service";
import type { NativeBridge } from "../src/native-bridge";
import type { ReaderContextService } from "../src/reader-context";

describe("agent-client contract", () => {
  it("CodexAppServerClient conforms to AgentClient", () => {
    const client: AgentClient = new CodexAppServerClient({ url: "ws://unused" });
    expect(client.agentCapabilities.supportsSteering).toBe(true);
  });
});

function engineLikeService(client: Partial<AgentClient>) {
  const callbacks = { onState: vi.fn(), onError: vi.fn() };
  const service = new CodexService(
    {} as NativeBridge,
    { tools: [] } as unknown as ReaderContextService,
    "test",
    callbacks,
  );
  const internal = service as any;
  const targetId = "b".repeat(64);
  const snapshot = {
    target: {
      kind: "local" as const,
      root: "/w",
      canonicalRoot: "/w",
      repositoryId: "a".repeat(64),
      targetId,
    },
    targetEpoch: 1,
  };
  service.commitRepositoryTarget({
    snapshot,
    binding: { targetId, targetEpoch: 1, root: "/w" },
    activeDocument: null,
  });
  internal.client = client;
  internal.activePaperKey = "1-ATTACH";
  internal.activeContext = {
    attachment: { key: "ATTACH", libraryID: 1, title: "P", filename: "p.pdf", creators: [], tags: [] },
    page: { pageIndex: 0, pageNumber: 1, text: "", source: "pdfjs", warnings: [] },
    workspace: { root: "/w" },
    warnings: [],
  };
  internal.rememberThreadOwner("thread-a", "1-ATTACH", "foreground", {
    targetId,
    targetEpoch: 1,
    root: "/w",
  });
  service.state.connected = true;
  service.state.activeThreadId = "thread-a";
  service.state.capabilities = ENGINE_CAPABILITIES;
  return { service, callbacks };
}

describe("capability guards", () => {
  it("rejects steering when the backend does not support it", async () => {
    const { service } = engineLikeService({});
    service.state.running = true;
    service.state.activeTurnId = "turn-1";
    await expect(service.send("follow up", "engine:p:m", "medium"))
      .rejects.toThrow(/cannot append while a response is running/);
  });

  it("rejects agent mode when unsupported", async () => {
    const { service } = engineLikeService({});
    await expect(service.setMode("agent")).rejects.toThrow(/does not support Agent mode/);
  });

  it("rejects login when unsupported", async () => {
    const { service } = engineLikeService({});
    await expect(service.login()).rejects.toThrow(/does not require sign-in|does not support sign-in/);
  });
});
