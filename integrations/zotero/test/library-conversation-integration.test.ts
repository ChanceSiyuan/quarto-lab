import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CodexAppServerClient,
  type WebSocketLike,
} from "../src/codex-app-server";
import { CodexService } from "../src/codex-service";
import type { NativeBridge } from "../src/native-bridge";
import type { ReaderContextService } from "../src/reader-context";

class MockWebSocket implements WebSocketLike {
  readyState = 0;
  readonly sent: string[] = [];
  private readonly listeners = new Map<string, Set<(event: any) => void>>();

  addEventListener(type: string, listener: (event: any) => void): void {
    const listeners = this.listeners.get(type) || new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: (event: any) => void): void {
    this.listeners.get(type)?.delete(listener);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
  }

  open(): void {
    this.readyState = 1;
    this.dispatch("open", {});
  }

  receive(message: unknown): void {
    this.dispatch("message", { data: JSON.stringify(message) });
  }

  last(): Record<string, unknown> {
    return JSON.parse(this.sent.at(-1)!) as Record<string, unknown>;
  }

  private dispatch(type: string, event: unknown): void {
    for (const listener of [...(this.listeners.get(type) || [])]) listener(event);
  }
}

beforeEach(() => {
  vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });
  vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
});

afterEach(() => vi.unstubAllGlobals());

describe("library notification integration order", () => {
  it("scopes both ThreadStore emissions and subsequent AgentClient notifications to the library", async () => {
    const callbacks = { onState: vi.fn(), onError: vi.fn() };
    const service = new CodexService(
      {} as NativeBridge,
      { tools: [] } as unknown as ReaderContextService,
      "test",
      callbacks,
    );
    const internal = service as any;
    internal.client = {
      threadStart: vi.fn().mockResolvedValue({ thread: { id: "library-thread" } }),
      threadSetName: vi.fn().mockResolvedValue({}),
    };
    internal.saveSessions = vi.fn().mockResolvedValue(undefined);
    service.state.connected = true;
    await service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" });
    callbacks.onState.mockClear();

    internal.unsubscribeStore = service.store.subscribe((snapshot, notification, affectedThreadIds) => {
      internal.handleStoreMutation(snapshot, notification, affectedThreadIds);
    });
    const socket = new MockWebSocket();
    const client = new CodexAppServerClient({
      url: "ws://library-test",
      webSocketFactory: () => socket,
      store: service.store,
      onNotification: (notification) => internal.handleNotification(notification),
    });
    const connecting = client.connect();
    socket.open();
    await Promise.resolve();
    const initialize = socket.last();
    socket.receive({
      id: initialize.id,
      result: {
        userAgent: "codex-test",
        codexHome: "/tmp/codex-home",
        platformFamily: "unix",
        platformOs: "linux",
      },
    });
    await connecting;

    socket.receive({
      method: "turn/started",
      params: {
        threadId: "library-thread",
        turn: { id: "stream-turn", status: "inProgress", items: [] },
      },
    });
    socket.receive({
      method: "item/agentMessage/delta",
      params: {
        threadId: "library-thread",
        turnId: "stream-turn",
        itemId: "message-1",
        delta: "Working",
      },
    });

    expect(callbacks.onState).toHaveBeenCalledTimes(4);
    expect(callbacks.onState.mock.calls).toEqual([
      [{ kind: "library", key: "library:1" }],
      [{ kind: "library", key: "library:1" }],
      [{ kind: "library", key: "library:1" }],
      [{ kind: "library", key: "library:1" }],
    ]);
  });
});
