import { randomID } from "./platform";
import type { WebSocketLike } from "./protocol";
import {
  BoundedJsonlDecoder,
  decodeBoundServerHello,
  decodeStreamReady,
  encodeJsonlFrame,
  REMOTE_HELPER_PROTOCOL_VERSION,
  REMOTE_HELPER_VERSION,
  type BoundClientHello,
  type BoundServerHello,
} from "./remote-helper-protocol";
import type { ResolvedSshRepositoryTarget } from "./repository-target";
import type { SshChannel } from "./ssh-target-transport";

type Listener = (event: any) => void;

/**
 * WebSocket-like AgentConnection over one identity-bound SSH helper channel.
 * Codex cannot observe the transport until the helper has proved the expected
 * host, repository, target epoch, and protocol capabilities.
 */
export class RemoteAgentConnection implements WebSocketLike {
  readyState = 0;
  private readonly listeners = new Map<string, Set<Listener>>();
  private readonly decoder = new BoundedJsonlDecoder(
    (frame) => typeof frame === "object" && frame !== null
      && (frame as { kind?: unknown }).kind === "stream-ready",
  );
  private readonly textDecoder = new TextDecoder("utf-8", { fatal: true });
  private text = "";
  private serverHello: BoundServerHello | null = null;
  private readonly hello: BoundClientHello;
  private unsubscribeBytes: (() => void) | null;
  private unsubscribeExit: (() => void) | null;

  constructor(
    private readonly channel: SshChannel,
    binding: Readonly<{ target: ResolvedSshRepositoryTarget; targetEpoch: number }>,
    requestId = randomID("agent-hello").slice(0, 128),
  ) {
    const { target, targetEpoch } = binding;
    this.hello = Object.freeze({
      kind: "hello",
      phase: "bound",
      requestId,
      protocolVersion: REMOTE_HELPER_PROTOCOL_VERSION,
      helperVersion: REMOTE_HELPER_VERSION,
      mode: "agent",
      targetId: target.targetId,
      targetEpoch,
      canonicalRoot: target.canonicalRoot,
      expectedHostInstanceId: target.hostInstanceId,
      expectedRepositoryUuid: target.repositoryUuid,
      expectedRepositoryId: target.repositoryId,
      requestedCapabilities: Object.freeze(["codex-app-server"]),
    });
    this.unsubscribeBytes = channel.onBytes((bytes) => this.receive(bytes));
    this.unsubscribeExit = channel.onExit((exit) => {
      this.finish(exit.code === 0 ? 1000 : 1011, exit.reason);
    });
    void channel.write(encodeJsonlFrame(this.hello)).catch((error) => this.fail(error));
  }

  addEventListener(type: string, listener: Listener): void {
    let listeners = this.listeners.get(type);
    if (!listeners) {
      listeners = new Set();
      this.listeners.set(type, listeners);
    }
    listeners.add(listener);
  }

  removeEventListener(type: string, listener: Listener): void {
    this.listeners.get(type)?.delete(listener);
  }

  send(data: string): void {
    if (this.readyState !== 1) throw new Error("Remote Codex AgentConnection is not open");
    const source = String(data);
    void this.channel.write(new TextEncoder().encode(source.endsWith("\n") ? source : `${source}\n`))
      .catch((error) => this.fail(error));
  }

  close(code = 1000, reason = "Client closed"): void {
    if (this.readyState >= 2) return;
    this.readyState = 2;
    void this.channel.close().finally(() => this.finish(code, reason));
  }

  private receive(bytes: Uint8Array): void {
    if (this.readyState >= 2) return;
    try {
      if (this.readyState === 0) {
        const result = this.decoder.push(bytes);
        for (const frame of result.frames) {
          if (!this.serverHello) this.serverHello = decodeBoundServerHello(frame, this.hello);
          else decodeStreamReady(frame, this.serverHello);
        }
        if (!result.transitioned) return;
        if (!this.serverHello) throw new Error("Remote helper omitted its bound server hello");
        this.readyState = 1;
        this.dispatch("open", {});
        if (result.rawRemainder?.length) this.receiveCodexBytes(result.rawRemainder);
        return;
      }
      this.receiveCodexBytes(bytes);
    }
    catch (error) { this.fail(error); }
  }

  private receiveCodexBytes(bytes: Uint8Array): void {
    this.text += this.textDecoder.decode(bytes, { stream: true });
    if (this.text.length > 8 * 1024 * 1024) {
      throw new Error("Remote Codex app-server emitted an oversized JSONL frame");
    }
    while (true) {
      const newline = this.text.indexOf("\n");
      if (newline < 0) return;
      let line = this.text.slice(0, newline);
      this.text = this.text.slice(newline + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (line.trim()) this.dispatch("message", { data: line });
    }
  }

  private fail(error: unknown): void {
    if (this.readyState === 3) return;
    this.dispatch("error", error instanceof Error ? error : new Error(String(error)));
    void this.channel.close().catch(() => {});
    this.finish(1007, "Remote helper protocol failed");
  }

  private finish(code: number, reason: string): void {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.unsubscribeBytes?.();
    this.unsubscribeBytes = null;
    this.unsubscribeExit?.();
    this.unsubscribeExit = null;
    this.dispatch("close", { code, reason });
  }

  private dispatch(type: string, event: unknown): void {
    for (const listener of [...(this.listeners.get(type) || [])]) {
      try { listener(event); }
      catch { /* one consumer must not break transport teardown */ }
    }
  }
}
