import { describe, expect, it, vi } from "vitest";

import {
  BoundedJsonlDecoder,
  REMOTE_HELPER_VERSION,
  REMOTE_HELPER_MAX_FRAME_BYTES,
  RemoteHelperProtocolError,
  RemoteRequestIdRegistry,
  decodeActivationClientHello,
  decodeActivationProtocolError,
  decodeActivationRequest,
  decodeActivationResponse,
  decodeActivationServerHello,
  decodeBoundClientHello,
  decodeBoundProtocolError,
  decodeBoundServerHello,
  decodeSetupReady,
  decodeStreamReady,
  encodeJsonlFrame,
  type ActivationClientHello,
  type ActivationFrameContext,
  type ActivationServerHello,
  type BoundClientHello,
  type BoundFrameContext,
  type BoundServerHello,
} from "../src/remote-helper-protocol";

const HOST_UUID = "11111111-1111-4111-8111-111111111111";
const REPOSITORY_UUID = "22222222-2222-4222-8222-222222222222";

function activationHello(
  overrides: Partial<ActivationClientHello> = {},
): ActivationClientHello {
  return {
    kind: "hello",
    phase: "activation",
    requestId: "hello-1",
    protocolVersion: 1,
    helperVersion: REMOTE_HELPER_VERSION,
    activationId: "activation-1",
    mode: "browse",
    candidateRoot: null,
    expectedHostInstanceId: null,
    requestedCapabilities: ["browse", "codex-probe"],
    ...overrides,
  };
}

function activationServer(
  overrides: Partial<ActivationServerHello> = {},
): ActivationServerHello {
  return {
    kind: "hello",
    phase: "activation",
    requestId: "hello-1",
    protocolVersion: 1,
    helperVersion: REMOTE_HELPER_VERSION,
    activationId: "activation-1",
    mode: "browse",
    hostInstanceId: HOST_UUID,
    canonicalRoot: null,
    repositoryUuid: null,
    capabilities: ["browse", "codex-probe"],
    ...overrides,
  };
}

function activationContext(
  overrides: Partial<ActivationFrameContext> = {},
): ActivationFrameContext {
  return {
    protocolVersion: 1,
    helperVersion: REMOTE_HELPER_VERSION,
    activationId: "activation-1",
    hostInstanceId: HOST_UUID,
    capabilities: ["browse", "codex-probe"],
    ...overrides,
  };
}

function browseBinding(context = activationContext()) {
  return { mode: "browse" as const, context };
}

function boundHello(overrides: Partial<BoundClientHello> = {}): BoundClientHello {
  return {
    kind: "hello",
    phase: "bound",
    requestId: "bound-hello-1",
    protocolVersion: 1,
    helperVersion: REMOTE_HELPER_VERSION,
    mode: "agent",
    targetId: "target-a",
    targetEpoch: 7,
    canonicalRoot: "/srv/research loop",
    expectedHostInstanceId: HOST_UUID,
    expectedRepositoryUuid: REPOSITORY_UUID,
    expectedRepositoryId: "repository-a",
    requestedCapabilities: ["codex-app-server"],
    ...overrides,
  };
}

function boundContext(overrides: Partial<BoundFrameContext> = {}): BoundFrameContext {
  return {
    protocolVersion: 1,
    helperVersion: REMOTE_HELPER_VERSION,
    targetId: "target-a",
    targetEpoch: 7,
    hostInstanceId: HOST_UUID,
    repositoryId: "repository-a",
    capabilities: ["codex-app-server"],
    ...overrides,
  };
}

function boundServer(overrides: Partial<BoundServerHello> = {}): BoundServerHello {
  const client = boundHello();
  return {
    kind: "hello",
    phase: "bound",
    requestId: client.requestId,
    protocolVersion: 1,
    helperVersion: client.helperVersion,
    mode: client.mode,
    targetId: client.targetId,
    targetEpoch: client.targetEpoch,
    canonicalRoot: client.canonicalRoot,
    hostInstanceId: client.expectedHostInstanceId,
    repositoryUuid: client.expectedRepositoryUuid,
    repositoryId: client.expectedRepositoryId,
    helperInstanceId: "helper-instance-1",
    capabilities: client.requestedCapabilities,
    ...overrides,
  };
}

function expectProtocolError(
  action: () => unknown,
  code: RemoteHelperProtocolError["code"],
): void {
  try {
    action();
    throw new Error("expected protocol decoder to reject the frame");
  }
  catch (error) {
    expect(error).toBeInstanceOf(RemoteHelperProtocolError);
    expect((error as RemoteHelperProtocolError).code).toBe(code);
  }
}

describe("bounded UTF-8 JSONL codec", () => {
  it.each([
    ["setup-ready", { kind: "setup-ready" }],
    ["stream-ready", { kind: "stream-ready" }],
  ])("transitions after a fragmented %s frame and returns untouched coalesced raw bytes", (
    _label,
    ready,
  ) => {
    // Break caught: the machine decoder consumes/copies raw bytes that share the ready chunk.
    const encodedReady = encodeJsonlFrame(ready);
    const split = encodedReady.length - 4;
    const raw = Uint8Array.from([0x00, 0xff, 0x0a, 0x7b, 0x22, 0x78, 0x22]);
    const coalesced = new Uint8Array(encodedReady.length - split + raw.length);
    coalesced.set(encodedReady.subarray(split));
    coalesced.set(raw, encodedReady.length - split);
    const decoder = new BoundedJsonlDecoder(
      (frame) => typeof frame === "object" && frame !== null
        && "kind" in frame && frame.kind === ready.kind,
    );

    expect(decoder.push(encodedReady.subarray(0, split)).frames).toEqual([]);
    const result = decoder.push(coalesced);
    expect(result.frames).toEqual([ready]);
    expect(result.transitioned).toBe(true);
    expect(result.rawRemainder).toEqual(raw);
    expect(result.rawRemainder?.buffer).toBe(coalesced.buffer);
    expect(result.rawRemainder?.byteOffset).toBe(
      coalesced.byteOffset + encodedReady.length - split,
    );
    expectProtocolError(() => decoder.push(encodeJsonlFrame({ ignored: true })), "INVALID_FRAME");
  });

  it("preserves a multibyte path split across arbitrary byte chunks", () => {
    // Break caught: decoding chunks independently replaces a split UTF-8 code point.
    const encoded = encodeJsonlFrame({ path: "/home/alice/研究" });
    const split = encoded.findIndex((byte) => byte >= 0x80) + 1;
    const decoder = new BoundedJsonlDecoder();

    expect(decoder.push(encoded.slice(0, split)).frames).toEqual([]);
    expect(decoder.push(encoded.slice(split, -1)).frames).toEqual([]);
    expect(decoder.push(encoded.slice(-1)).frames).toEqual([{ path: "/home/alice/研究" }]);
    expect(decoder.finish()).toEqual([]);
  });

  it("accepts the largest physical frame and rejects one byte more", () => {
    // Break caught: enforcing the bound on JSON payload rather than payload plus LF.
    const prefix = new TextEncoder().encode('{"value":"').length;
    const suffix = new TextEncoder().encode('"}\n').length;
    const value = "x".repeat(REMOTE_HELPER_MAX_FRAME_BYTES - prefix - suffix);
    const valid = new TextEncoder().encode(`{"value":"${value}"}\n`);
    const decoder = new BoundedJsonlDecoder();
    expect(valid).toHaveLength(REMOTE_HELPER_MAX_FRAME_BYTES);
    expect(decoder.push(valid).frames).toHaveLength(1);

    const overlong = new TextEncoder().encode(`{"value":"${value}x"}\n`);
    expectProtocolError(
      () => new BoundedJsonlDecoder().push(overlong),
      "FRAME_TOO_LARGE",
    );
  });

  it("rejects an oversized unfinished frame before copying its bytes", () => {
    // Break caught: the decoder clones an already-oversized chunk before checking its bound.
    const oversized = new Uint8Array(REMOTE_HELPER_MAX_FRAME_BYTES);
    Object.defineProperty(oversized, "slice", {
      value: () => { throw new Error("oversized frame was copied"); },
    });
    expectProtocolError(
      () => new BoundedJsonlDecoder().push(oversized),
      "FRAME_TOO_LARGE",
    );
  });

  it("copies only linearly when a frame arrives as one-byte fragments", () => {
    // Break caught: joining the entire pending frame per byte performs quadratic copying.
    const encoded = new TextEncoder().encode(`{"value":"${"x".repeat(4096)}"}\n`);
    const originalSet = Uint8Array.prototype.set;
    let copiedBytes = 0;
    const setSpy = vi.spyOn(Uint8Array.prototype, "set").mockImplementation(function (
      this: Uint8Array,
      source: ArrayLike<number>,
      offset?: number,
    ): void {
      copiedBytes += source.length;
      originalSet.call(this, source, offset);
    });
    try {
      const decoder = new BoundedJsonlDecoder();
      let finalFrames: readonly unknown[] = [];
      for (let index = 0; index < encoded.length; index++) {
        finalFrames = decoder.push(encoded.subarray(index, index + 1)).frames;
      }
      expect(finalFrames).toEqual([{ value: "x".repeat(4096) }]);
      expect(copiedBytes).toBeLessThan(encoded.length * 4);
    }
    finally {
      setSpy.mockRestore();
    }
  });

  it("rejects invalid UTF-8, malformed JSON, and an unterminated final frame", () => {
    // Break caught: forgiving TextDecoder/JSONL EOF handling admits corrupted frames.
    expectProtocolError(
      () => new BoundedJsonlDecoder().push(Uint8Array.from([0x7b, 0xff, 0x7d, 0x0a])),
      "MALFORMED_FRAME",
    );
    expectProtocolError(
      () => new BoundedJsonlDecoder().push(new TextEncoder().encode("{broken}\n")),
      "MALFORMED_FRAME",
    );
    const decoder = new BoundedJsonlDecoder();
    decoder.push(new TextEncoder().encode('{"kind":"hello"}'));
    expectProtocolError(() => decoder.finish(), "TRUNCATED_FRAME");
  });

  it.each([
    ['{"same":1,"same":2}\n'],
    ['{"same":1,"\\u0073ame":2}\n'],
    ['{"outer":{"nested":1,"nested":2}}\n'],
  ])("rejects duplicate JSON object keys before value collapse", (source) => {
    // Break caught: JSON.parse silently keeps only the final duplicate value.
    expectProtocolError(
      () => new BoundedJsonlDecoder().push(new TextEncoder().encode(source)),
      "MALFORMED_FRAME",
    );
  });

  it("rejects EOF before the required first hello and remains terminal after an error", () => {
    expectProtocolError(() => new BoundedJsonlDecoder().finish(), "TRUNCATED_FRAME");

    const decoder = new BoundedJsonlDecoder();
    expect(decoder.push(encodeJsonlFrame({
      kind: "protocol-error",
      requestId: null,
      code: "INVALID_REQUEST",
      message: "stop",
    })).frames).toHaveLength(1);
    expectProtocolError(
      () => decoder.push(encodeJsonlFrame({ kind: "response" })),
      "INVALID_FRAME",
    );
  });
});

describe("activation hello and RPC codecs", () => {
  it("keeps activation identity separate from target and repository identity", () => {
    // Break caught: pre-resolution code fabricates target/repository identity.
    const decoded = decodeActivationClientHello(activationHello());
    expect(decoded).toEqual(activationHello());
    expect(decoded).not.toHaveProperty("targetId");
    expect(decoded).not.toHaveProperty("repositoryId");
  });

  it("requires a repository candidate only for repository-handshake", () => {
    const hello = activationHello({
      mode: "repository-handshake",
      candidateRoot: "/srv/repository",
      expectedHostInstanceId: HOST_UUID,
      requestedCapabilities: [],
    });
    expect(decodeActivationClientHello(hello)).toEqual(hello);
    expectProtocolError(
      () => decodeActivationClientHello({ ...hello, candidateRoot: null }),
      "INVALID_FRAME",
    );
    expectProtocolError(
      () => decodeActivationClientHello({ ...activationHello(), candidateRoot: "/surprise" }),
      "INVALID_FRAME",
    );
  });

  it.each([
    ["extra field", { ...activationHello(), targetId: "fabricated" }],
    ["missing field", (({ activationId: _ignored, ...rest }) => rest)(activationHello())],
    ["wrong type", { ...activationHello(), requestedCapabilities: "browse" }],
    ["invalid id", { ...activationHello(), activationId: "contains space" }],
    ["relative root", activationHello({ mode: "repository-handshake", candidateRoot: "repo" })],
  ])("rejects an activation hello with %s", (_label, value) => {
    // Break caught: structural casting trusts a TypeScript brand/object shape at runtime.
    expectProtocolError(() => decodeActivationClientHello(value), "INVALID_FRAME");
  });

  it("enforces the canonical helper version and exact capabilities for each mode", () => {
    expectProtocolError(
      () => decodeActivationClientHello(activationHello({ helperVersion: "1.0.1" })),
      "INVALID_FRAME",
    );
    expectProtocolError(
      () => decodeActivationClientHello(activationHello({ requestedCapabilities: ["browse"] })),
      "INVALID_FRAME",
    );
    expect(decodeActivationClientHello(activationHello({
      mode: "repository-handshake",
      candidateRoot: "/srv/repository",
      requestedCapabilities: [],
    }))).toMatchObject({ mode: "repository-handshake", requestedCapabilities: [] });
    expectProtocolError(
      () => decodeActivationClientHello(activationHello({
        mode: "setup-auth",
        requestedCapabilities: [],
      })),
      "INVALID_FRAME",
    );
  });

  it("validates the complete activation server binding", () => {
    const client = activationHello({ expectedHostInstanceId: HOST_UUID });
    expect(decodeActivationServerHello(activationServer(), client))
      .toEqual(activationServer());
    expectProtocolError(
      () => decodeActivationServerHello(
        activationServer({ hostInstanceId: "33333333-3333-4333-8333-333333333333" }),
        client,
      ),
      "CONTEXT_MISMATCH",
    );
    expectProtocolError(
      () => decodeActivationServerHello(activationServer(), undefined as never),
      "CONTEXT_MISMATCH",
    );
    expectProtocolError(
      () => decodeActivationServerHello(
        activationServer({ capabilities: ["browse"] }),
        client,
      ),
      "INVALID_FRAME",
    );
  });

  it("validates all four closed activation methods and their parameters", () => {
    const context = activationContext();
    const requests = [
      { ...context, kind: "request", id: "home-1", method: "browse.home", params: {} },
      {
        ...context, kind: "request", id: "list-1", method: "browse.listDirectories",
        params: { path: "/home/alice" },
      },
      {
        ...context, kind: "request", id: "canonical-1", method: "browse.canonicalize",
        params: { input: "/srv/repository" },
      },
      { ...context, kind: "request", id: "probe-1", method: "codex.probe", params: {} },
    ];
    expect(requests.map((request) => decodeActivationRequest(
      request,
      browseBinding(context),
    ).method))
      .toEqual(["browse.home", "browse.listDirectories", "browse.canonicalize", "codex.probe"]);
    expectProtocolError(
      () => decodeActivationRequest(requests[0], undefined as never),
      "CONTEXT_MISMATCH",
    );
  });

  it("gates activation RPCs by the originating channel mode without widening wire context", () => {
    // Break caught: a repository/setup channel can dispatch browse or probe RPCs.
    const browseContext = activationContext();
    const browseRequest = {
      ...browseContext,
      kind: "request",
      id: "home-mode",
      method: "browse.home",
      params: {},
    };
    expect(decodeActivationRequest(browseRequest, {
      mode: "browse",
      context: browseContext,
    })).toMatchObject({ method: "browse.home" });

    for (const [mode, capabilities] of [
      ["repository-handshake", []],
      ["setup-auth", ["codex-device-auth-pty"]],
    ] as const) {
      const context = activationContext({ capabilities });
      for (const [method, params] of [
        ["browse.home", {}],
        ["codex.probe", {}],
      ] as const) {
        expectProtocolError(() => decodeActivationRequest({
          ...context,
          kind: "request",
          id: `${mode}-${method}`,
          method,
          params,
        }, { mode, context }), "METHOD_NOT_ALLOWED");
      }
    }
  });

  it.each([
    ["unknown method", { method: "process.run", params: {} }, "METHOD_NOT_ALLOWED"],
    ["extra empty params", { method: "browse.home", params: { cwd: "/tmp" } }, "INVALID_FRAME"],
    ["missing path", { method: "browse.listDirectories", params: {} }, "INVALID_FRAME"],
    ["relative canonicalize", { method: "browse.canonicalize", params: { input: "../repo" } }, "INVALID_FRAME"],
    ["traversal canonicalize", { method: "browse.canonicalize", params: { input: "/srv/../repo" } }, "INVALID_FRAME"],
  ] as const)("rejects %s without admitting a generic execution RPC", (_label, fields, code) => {
    const context = activationContext();
    expectProtocolError(
      () => decodeActivationRequest({
        ...context, kind: "request", id: "request-1", ...fields,
      }, browseBinding(context)),
      code,
    );
  });

  it("strictly decodes directory and Codex probe responses", () => {
    const context = activationContext();
    const listRequest = decodeActivationRequest({
      ...context,
      kind: "request",
      id: "list-1",
      method: "browse.listDirectories",
      params: { path: "/home/alice" },
    }, browseBinding(context));
    const list = decodeActivationResponse({
      ...context,
      kind: "response",
      id: "list-1",
      method: "browse.listDirectories",
      result: {
        entries: [{ name: "research", path: "/home/alice/research", kind: "directory" }],
      },
    }, listRequest);
    expect(list).toMatchObject({ method: "browse.listDirectories" });

    for (const result of [
      { state: "missing" },
      { state: "incompatible", foundVersion: "0.0.1", minimumVersion: "0.146.0" },
      { state: "unauthenticated", version: "1.2.3" },
      { state: "ready", version: "1.2.3" },
    ]) {
      const request = decodeActivationRequest({
        ...context,
        kind: "request",
        id: `probe-${result.state}`,
        method: "codex.probe",
        params: {},
      }, browseBinding(context));
      expect(decodeActivationResponse({
        ...context, kind: "response", id: `probe-${result.state}`,
        method: "codex.probe", result,
      }, request)).toMatchObject({ method: "codex.probe", result });
    }
  });

  it("enforces the exact Codex floor and state semantics at 0.146.0", () => {
    // Break caught: syntactically valid probe states contradict the negotiated floor.
    const context = activationContext();
    const request = decodeActivationRequest({
      ...context,
      kind: "request",
      id: "probe-floor",
      method: "codex.probe",
      params: {},
    }, browseBinding(context));
    const frame = (result: unknown) => ({
      ...context,
      kind: "response",
      id: "probe-floor",
      method: "codex.probe",
      result,
    });
    for (const result of [
      { state: "incompatible", foundVersion: "0.145.999", minimumVersion: "0.146.0" },
      { state: "ready", version: "0.146.0" },
      { state: "unauthenticated", version: "10.0.0" },
    ]) {
      expect(decodeActivationResponse(frame(result), request)).toMatchObject({ result });
    }
    for (const result of [
      { state: "incompatible", foundVersion: "0.145.999", minimumVersion: "0.145.0" },
      { state: "incompatible", foundVersion: "0.146.0", minimumVersion: "0.146.0" },
      { state: "incompatible", foundVersion: "1.0.0", minimumVersion: "0.146.0" },
      { state: "ready", version: "0.145.999" },
      { state: "unauthenticated", version: "0.0.1" },
      { state: "ready", version: "0.146.0-beta" },
    ]) {
      expectProtocolError(() => decodeActivationResponse(frame(result), request), "INVALID_FRAME");
    }
  });

  it("rejects response context drift, request drift, and extra result fields", () => {
    const context = activationContext();
    const request = decodeActivationRequest({
      ...context,
      kind: "request",
      id: "home-1",
      method: "browse.home",
      params: {},
    }, browseBinding(context));
    expectProtocolError(() => decodeActivationResponse({
      ...context,
      helperVersion: "2.0.0",
      kind: "response",
      id: "home-1",
      method: "browse.home",
      result: { path: "/home/alice" },
    }, request), "INVALID_FRAME");
    expectProtocolError(() => decodeActivationResponse({
      ...context,
      kind: "response",
      id: "home-1",
      method: "browse.home",
      result: { path: "/home/alice" },
    }, undefined as never), "CONTEXT_MISMATCH");
    expectProtocolError(() => decodeActivationResponse({
      ...context,
      kind: "response",
      id: "home-2",
      method: "browse.home",
      result: { path: "/home/alice" },
    }, request), "CONTEXT_MISMATCH");
    expectProtocolError(() => decodeActivationResponse({
      ...context,
      kind: "response",
      id: "home-1",
      method: "codex.probe",
      result: { state: "missing" },
    }, request), "CONTEXT_MISMATCH");
    expectProtocolError(() => decodeActivationResponse({
      ...context,
      kind: "response",
      id: "home-1",
      method: "browse.home",
      result: { path: "/home/alice", command: "id" },
    }, request), "INVALID_FRAME");
  });

  it("uses the same 1,024-entry directory bound as the native helper", () => {
    const context = activationContext();
    const request = decodeActivationRequest({
      ...context,
      kind: "request",
      id: "list-1",
      method: "browse.listDirectories",
      params: { path: "/home/alice" },
    }, browseBinding(context));
    const entries = Array.from({ length: 1025 }, (_unused, index) => ({
      name: `directory-${index}`,
      path: `/home/alice/directory-${index}`,
      kind: "directory",
    }));
    expectProtocolError(() => decodeActivationResponse({
      ...context,
      kind: "response",
      id: "list-1",
      method: "browse.listDirectories",
      result: { entries },
    }, request), "INVALID_FRAME");
  });

  it("decodes only the resolved terminal activation protocol-error union", () => {
    const context = activationContext();
    expect(decodeActivationProtocolError({
      ...context,
      kind: "protocol-error",
      requestId: "bad-1",
      code: "METHOD_NOT_ALLOWED",
      message: "unknown activation method",
    }, context)).toMatchObject({ code: "METHOD_NOT_ALLOWED", requestId: "bad-1" });
    expectProtocolError(() => decodeActivationProtocolError({
      ...context,
      kind: "protocol-error",
      requestId: "bad-1",
      code: "METHOD_NOT_ALLOWED",
      message: "unknown activation method",
    }, undefined as never), "CONTEXT_MISMATCH");
    expectProtocolError(() => decodeActivationProtocolError({
      ...context,
      kind: "protocol-error",
      requestId: null,
      code: "INTERNAL",
      message: "not a terminal wire code",
    }, context), "INVALID_FRAME");
  });
});

describe("bound handshake and context", () => {
  it("accepts the common agent/repository hello codec but no unknown bound mode", () => {
    expect(decodeBoundClientHello(boundHello())).toEqual(boundHello());
    expect(decodeBoundClientHello(boundHello({
      mode: "repository",
      requestedCapabilities: [],
    }))).toEqual(
      boundHello({ mode: "repository", requestedCapabilities: [] }),
    );
    expectProtocolError(
      () => decodeBoundClientHello({ ...boundHello(), mode: "shell" }),
      "INVALID_FRAME",
    );
    expectProtocolError(
      () => decodeBoundClientHello(boundHello({ requestedCapabilities: [] })),
      "INVALID_FRAME",
    );
  });

  it("accepts a server hello only when every cross-channel binding agrees", () => {
    const client = boundHello();
    const server = {
      kind: "hello",
      phase: "bound",
      requestId: client.requestId,
      protocolVersion: 1,
      helperVersion: client.helperVersion,
      mode: client.mode,
      targetId: client.targetId,
      targetEpoch: client.targetEpoch,
      canonicalRoot: client.canonicalRoot,
      hostInstanceId: client.expectedHostInstanceId,
      repositoryUuid: client.expectedRepositoryUuid,
      repositoryId: client.expectedRepositoryId,
      helperInstanceId: "helper-instance-1",
      capabilities: client.requestedCapabilities,
    };
    expect(decodeBoundServerHello(server, client)).toEqual(server);
    expectProtocolError(
      () => decodeBoundServerHello(server, undefined as never),
      "CONTEXT_MISMATCH",
    );

    const mutations: Array<[
      { [key: string]: unknown },
      RemoteHelperProtocolError["code"],
    ]> = [
      [{ canonicalRoot: "/srv/other" }, "CONTEXT_MISMATCH"],
      [{ hostInstanceId: "33333333-3333-4333-8333-333333333333" }, "CONTEXT_MISMATCH"],
      [{ repositoryUuid: "44444444-4444-4444-8444-444444444444" }, "CONTEXT_MISMATCH"],
      [{ repositoryId: "repository-b" }, "CONTEXT_MISMATCH"],
      [{ targetId: "target-b" }, "CONTEXT_MISMATCH"],
      [{ targetEpoch: 8 }, "CONTEXT_MISMATCH"],
      [{ helperVersion: "2.0.0" }, "INVALID_FRAME"],
      [{ capabilities: [] }, "INVALID_FRAME"],
    ];
    for (const [mutation, code] of mutations) {
      expectProtocolError(
        () => decodeBoundServerHello({ ...server, ...mutation }, client),
        code,
      );
    }
  });

  it("validates stream/setup transitions against their complete contexts", () => {
    const context = boundContext();
    const expectedBoundHello = boundServer();
    expect(decodeStreamReady({
      ...context,
      kind: "stream-ready",
      requestId: "bound-hello-1",
      stream: "codex-jsonl",
    }, expectedBoundHello)).toMatchObject({ stream: "codex-jsonl" });
    expectProtocolError(() => decodeStreamReady({
      ...context,
      targetEpoch: 8,
      kind: "stream-ready",
      requestId: "bound-hello-1",
      stream: "codex-jsonl",
    }, expectedBoundHello), "CONTEXT_MISMATCH");
    expectProtocolError(() => decodeStreamReady({
      ...context,
      kind: "stream-ready",
      requestId: "bound-hello-1",
      stream: "codex-jsonl",
    }, undefined as never), "CONTEXT_MISMATCH");
    expectProtocolError(() => decodeStreamReady({
      ...context,
      kind: "stream-ready",
      requestId: "stale-bound-hello",
      stream: "codex-jsonl",
    }, boundServer()), "CONTEXT_MISMATCH");

    const client = activationHello({
      mode: "setup-auth",
      requestedCapabilities: ["codex-device-auth-pty"],
    });
    const server = activationServer({
      mode: "setup-auth",
      capabilities: ["codex-device-auth-pty"],
    });
    expect(decodeSetupReady({
      kind: "setup-ready",
      requestId: client.requestId,
      protocolVersion: 1,
      helperVersion: client.helperVersion,
      activationId: client.activationId,
      hostInstanceId: HOST_UUID,
      capability: "codex-device-auth-pty",
    }, client, server)).toMatchObject({ capability: "codex-device-auth-pty" });
    expectProtocolError(
      () => decodeSetupReady({
        kind: "setup-ready",
        requestId: client.requestId,
        protocolVersion: 1,
        helperVersion: client.helperVersion,
        activationId: client.activationId,
        hostInstanceId: HOST_UUID,
        capability: "codex-device-auth-pty",
      }, undefined as never, server),
      "CONTEXT_MISMATCH",
    );
  });

  it("decodes only the resolved terminal bound protocol-error union", () => {
    const context = boundContext();
    expect(decodeBoundProtocolError({
      ...context,
      kind: "protocol-error",
      requestId: null,
      code: "INVALID_REQUEST",
      message: "malformed bound frame",
    }, context)).toMatchObject({ code: "INVALID_REQUEST" });
    expectProtocolError(() => decodeBoundProtocolError({
      ...context,
      kind: "protocol-error",
      requestId: null,
      code: "INVALID_REQUEST",
      message: "malformed bound frame",
    }, undefined as never), "CONTEXT_MISMATCH");
  });
});

describe("request ID ownership", () => {
  it("rejects a duplicate bounded ID with a typed protocol error", () => {
    // Break caught: a repeated request can alias an in-flight result.
    const ids = new RemoteRequestIdRegistry();
    expect(ids.claim("request-1")).toBe("request-1");
    expectProtocolError(() => ids.claim("request-1"), "DUPLICATE_ID");
  });

  it("rejects empty, overlong, Unicode, and whitespace IDs", () => {
    for (const id of ["", "x".repeat(129), "snow☃", "two words"]) {
      expectProtocolError(() => new RemoteRequestIdRegistry().claim(id), "INVALID_FRAME");
    }
  });
});
