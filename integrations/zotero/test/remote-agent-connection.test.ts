import { describe, expect, it } from "vitest";

import { RemoteAgentConnection } from "../src/remote-agent-connection";
import { encodeJsonlFrame, REMOTE_HELPER_VERSION } from "../src/remote-helper-protocol";
import type { ResolvedSshRepositoryTarget } from "../src/repository-target";
import type { SshChannel, SshChannelExit } from "../src/ssh-target-transport";

class Channel implements SshChannel {
  channelId = "agent-1";
  generation = 3;
  writes: Uint8Array[] = [];
  bytes = new Set<(value: Uint8Array) => void>();
  exits = new Set<(value: SshChannelExit) => void>();
  async write(value: Uint8Array): Promise<void> { this.writes.push(value.slice()); }
  onBytes(listener: (value: Uint8Array) => void): () => void {
    this.bytes.add(listener); return () => this.bytes.delete(listener);
  }
  onExit(listener: (value: SshChannelExit) => void): () => void {
    this.exits.add(listener); return () => this.exits.delete(listener);
  }
  async close(): Promise<void> {}
  emit(value: Uint8Array): void { for (const listener of this.bytes) listener(value); }
}

const target: ResolvedSshRepositoryTarget = {
  kind: "ssh",
  sshProfile: "gpu",
  root: "/srv/loop",
  canonicalRoot: "/srv/loop",
  acceptedHostKeyFingerprint: `SHA256:${"A".repeat(43)}`,
  endpointId: "e".repeat(64),
  hostInstanceId: "11111111-1111-4111-8111-111111111111",
  repositoryUuid: "22222222-2222-4222-8222-222222222222",
  repositoryId: "repository-id",
  targetId: "target-id",
};

describe("remote AgentConnection", () => {
  it("opens only after the bound helper handshake and then carries Codex JSONL", async () => {
    const channel = new Channel();
    const socket = new RemoteAgentConnection(channel, { target, targetEpoch: 4 }, "agent-hello-1");
    const events: string[] = [];
    const messages: string[] = [];
    socket.addEventListener("open", () => events.push("open"));
    socket.addEventListener("message", (event) => messages.push(event.data));
    await Promise.resolve();
    const hello = JSON.parse(new TextDecoder().decode(channel.writes[0]).trim());
    const server = {
      kind: "hello", phase: "bound", requestId: hello.requestId,
      protocolVersion: 1, helperVersion: REMOTE_HELPER_VERSION, mode: "agent",
      targetId: target.targetId, targetEpoch: 4, canonicalRoot: target.canonicalRoot,
      hostInstanceId: target.hostInstanceId, repositoryUuid: target.repositoryUuid,
      repositoryId: target.repositoryId, helperInstanceId: "helper-1",
      capabilities: ["codex-app-server"],
    };
    const ready = {
      protocolVersion: 1, helperVersion: REMOTE_HELPER_VERSION,
      targetId: target.targetId, targetEpoch: 4, hostInstanceId: target.hostInstanceId,
      repositoryId: target.repositoryId, capabilities: ["codex-app-server"],
      kind: "stream-ready", requestId: hello.requestId, stream: "codex-jsonl",
    };
    const payload = new Uint8Array([
      ...encodeJsonlFrame(server), ...encodeJsonlFrame(ready),
      ...new TextEncoder().encode('{"id":1,"result":{}}\n'),
    ]);
    channel.emit(payload);

    expect(events).toEqual(["open"]);
    expect(messages).toEqual(['{"id":1,"result":{}}']);
    socket.send('{"method":"initialized"}');
    await Promise.resolve();
    expect(new TextDecoder().decode(channel.writes.at(-1))).toBe('{"method":"initialized"}\n');
  });

  it("fails closed when the helper binds a different repository", async () => {
    const channel = new Channel();
    const socket = new RemoteAgentConnection(channel, { target, targetEpoch: 4 }, "agent-hello-2");
    const errors: unknown[] = [];
    socket.addEventListener("error", (event) => errors.push(event));
    await Promise.resolve();
    const hello = JSON.parse(new TextDecoder().decode(channel.writes[0]).trim());
    channel.emit(encodeJsonlFrame({
      kind: "hello", phase: "bound", requestId: hello.requestId,
      protocolVersion: 1, helperVersion: REMOTE_HELPER_VERSION, mode: "agent",
      targetId: target.targetId, targetEpoch: 4, canonicalRoot: target.canonicalRoot,
      hostInstanceId: target.hostInstanceId, repositoryUuid: target.repositoryUuid,
      repositoryId: "different", helperInstanceId: "helper-1",
      capabilities: ["codex-app-server"],
    }));
    expect(errors).toHaveLength(1);
    expect(socket.readyState).toBe(3);
  });
});
