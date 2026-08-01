import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  LocalRepositoryTargetResolver,
  type LocalRepositoryTargetRuntime,
} from "../src/local-repository-target-resolver";
import type {
  LocalRepositoryCandidate,
  ResolvedLocalRepositoryTarget,
  TargetDigest,
} from "../src/repository-target";
import {
  createGeckoQLabPrivateFileHost,
  type QLabRepositoryState,
} from "../src/qlab-workspace";
import { createResearchLoopSiteRuntime } from "../src/research-loop-site";
import type { BridgeEvent, NativeBridge, SpawnOptions } from "../src/native-bridge";

const WINNING_UUID = "11111111-1111-4111-8111-111111111111";
const GENERATED_UUID = "22222222-2222-4222-8222-222222222222";

type RuntimeOptions = Readonly<{
  state: QLabRepositoryState;
  gitPath?: string;
  uuidFile?: string | null;
  createConflictThenRead?: string;
}>;

type FakeRuntime = LocalRepositoryTargetRuntime & {
  initialize: ReturnType<typeof vi.fn>;
  readPrivate: ReturnType<typeof vi.fn>;
  createPrivateIfAbsent: ReturnType<typeof vi.fn>;
  setState(state: QLabRepositoryState): void;
};

function digest(bytes: Uint8Array): string {
  let value = 0;
  for (const byte of bytes) value = (value * 31 + byte) >>> 0;
  return value.toString(16).padStart(8, "0").repeat(8);
}

function fakeRuntime(options: RuntimeOptions): FakeRuntime {
  let state = options.state;
  let privateValue = options.uuidFile ?? null;
  const createPrivateIfAbsent = vi.fn(async (_path: string, value: string) => {
    if (options.createConflictThenRead !== undefined) {
      privateValue = options.createConflictThenRead;
      return "exists" as const;
    }
    if (privateValue !== null) return "exists" as const;
    privateValue = value;
    return "created" as const;
  });
  return {
    canonicalize: vi.fn(async (root: string) => root.replace("/alias", "")),
    state: vi.fn(async () => state),
    initialize: vi.fn(async () => { state = "ready"; }),
    gitPrivatePath: vi.fn(async (root: string) =>
      options.gitPath ?? `${root}/.git/qlab/repository-id`),
    readPrivate: vi.fn(async () => privateValue),
    createPrivateIfAbsent,
    resolvePath: (root: string, path: string) => {
      const absolute = path.startsWith("/") ? path : `${root}/${path}`;
      const parts: string[] = [];
      for (const part of absolute.split("/")) {
        if (!part || part === ".") continue;
        if (part === "..") parts.pop();
        else parts.push(part);
      }
      return `/${parts.join("/")}`;
    },
    isPathInside: (root: string, candidate: string) =>
      candidate === root || candidate.startsWith(`${root}/`),
    digest: digest as TargetDigest,
    setState(nextState) { state = nextState; },
  };
}

describe("LocalRepositoryTargetResolver", () => {
  const originalServices = (globalThis as any).Services;

  beforeEach(() => {
    (globalThis as any).Services = {
      uuid: { generateUUID: vi.fn(() => `{${GENERATED_UUID.toUpperCase()}}`) },
    };
  });

  afterEach(() => {
    (globalThis as any).Services = originalServices;
  });

  it("creates the private UUID only after a ready Git repository passes validation", async () => {
    const runtime = fakeRuntime({
      state: "ready",
      gitPath: "/repo/.git/qlab/repository-id",
      uuidFile: null,
    });

    const inspected = await new LocalRepositoryTargetResolver(runtime).inspect("/alias/repo");

    expect(inspected.kind).toBe("local");
    const target = inspected as ResolvedLocalRepositoryTarget;
    expect(runtime.createPrivateIfAbsent).toHaveBeenCalledWith(
      "/repo/.git/qlab/repository-id",
      `${GENERATED_UUID}\n`,
      0o600,
    );
    expect(target).toMatchObject({ kind: "local", root: "/repo", canonicalRoot: "/repo" });
    expect(target.repositoryId).toMatch(/^[a-f0-9]{64}$/);
    expect(target.targetId).toMatch(/^[a-f0-9]{64}$/);
  });

  it("canonicalizes a trimmed relative Git path and converges after an exclusive-create conflict", async () => {
    const runtime = fakeRuntime({
      state: "ready",
      gitPath: "  .git/qlab/repository-id\n",
      createConflictThenRead: `${WINNING_UUID}\n`,
    });
    const resolver = new LocalRepositoryTargetResolver(runtime);

    const [first, second] = await Promise.all([
      resolver.inspect("/repo"),
      resolver.inspect("/repo"),
    ]);

    expect(first).toMatchObject({ kind: "local", canonicalRoot: "/repo" });
    expect(second).toEqual(first);
    expect(runtime.createPrivateIfAbsent).toHaveBeenCalledWith(
      "/repo/.git/qlab/repository-id",
      expect.stringMatching(/^[0-9a-f-]{36}\n$/),
      0o600,
    );
  });

  it("shares one in-flight identity resolution for concurrent inspection of the same root", async () => {
    const runtime = fakeRuntime({ state: "ready", uuidFile: null });
    const resolver = new LocalRepositoryTargetResolver(runtime);

    const [first, second] = await Promise.all([
      resolver.inspect("/repo"),
      resolver.inspect("/repo"),
    ]);

    expect(second).toEqual(first);
    expect(runtime.createPrivateIfAbsent).toHaveBeenCalledOnce();
    expect((globalThis as any).Services.uuid.generateUUID).toHaveBeenCalledOnce();
  });

  it("does not initialize an empty candidate before explicit confirmation", async () => {
    const runtime = fakeRuntime({ state: "empty" });
    const resolver = new LocalRepositoryTargetResolver(runtime);

    const inspected = await resolver.inspect("/new");

    expect(inspected).toEqual({ kind: "candidate", canonicalRoot: "/new", state: "empty" });
    expect(runtime.initialize).not.toHaveBeenCalled();
    const confirmed = await resolver.confirm(inspected as LocalRepositoryCandidate);
    expect(runtime.initialize).toHaveBeenCalledWith("/new");
    expect(confirmed).toMatchObject({ kind: "local", canonicalRoot: "/new" });
  });

  it("refuses to initialize a candidate that became incompatible before confirmation", async () => {
    const runtime = fakeRuntime({ state: "empty" });
    const resolver = new LocalRepositoryTargetResolver(runtime);
    const inspected = await resolver.inspect("/new") as LocalRepositoryCandidate;
    runtime.setState("incompatible");

    await expect(resolver.confirm(inspected))
      .rejects.toThrow("Choose a valid local Research Loop Git repository");
    expect(runtime.initialize).not.toHaveBeenCalled();
    expect(runtime.createPrivateIfAbsent).not.toHaveBeenCalled();
  });

  it.each(["missing", "incompatible"] as const)(
    "returns unavailable for %s without initialization or identity creation",
    async (state) => {
      const runtime = fakeRuntime({ state });

      await expect(new LocalRepositoryTargetResolver(runtime).inspect("/bad"))
        .resolves.toEqual({ kind: "unavailable", reason: state });
      expect(runtime.initialize).not.toHaveBeenCalled();
      expect(runtime.createPrivateIfAbsent).not.toHaveBeenCalled();
    },
  );

  it.each(["canonicalization", "state inspection"] as const)(
    "treats a stale legacy root as missing when %s fails",
    async (failure) => {
      const runtime = fakeRuntime({ state: "ready" });
      if (failure === "canonicalization") {
        vi.mocked(runtime.canonicalize).mockRejectedValueOnce(new Error("path does not exist"));
      }
      else {
        vi.mocked(runtime.state).mockRejectedValueOnce(new Error("directory disappeared"));
      }

      await expect(new LocalRepositoryTargetResolver(runtime).inspect("/stale"))
        .resolves.toEqual({ kind: "unavailable", reason: "missing" });
      expect(runtime.initialize).not.toHaveBeenCalled();
      expect(runtime.createPrivateIfAbsent).not.toHaveBeenCalled();
    },
  );

  it("fails closed instead of following a Git-private path outside the canonical root", async () => {
    const runtime = fakeRuntime({ state: "ready", gitPath: "../outside/repository-id" });

    await expect(new LocalRepositoryTargetResolver(runtime).inspect("/repo"))
      .resolves.toEqual({ kind: "unavailable", reason: "identity-unavailable" });
    expect(runtime.readPrivate).not.toHaveBeenCalled();
    expect(runtime.createPrivateIfAbsent).not.toHaveBeenCalled();
  });

  it("rejects malformed private identity content without replacing it", async () => {
    const runtime = fakeRuntime({ state: "ready", uuidFile: "not-a-repository-uuid\n" });

    await expect(new LocalRepositoryTargetResolver(runtime).inspect("/repo"))
      .resolves.toEqual({ kind: "unavailable", reason: "identity-unavailable" });
    expect(runtime.createPrivateIfAbsent).not.toHaveBeenCalled();
  });

  it("reuses an existing identity idempotently without generating or rewriting a UUID", async () => {
    const runtime = fakeRuntime({ state: "ready", uuidFile: `${WINNING_UUID}\n` });
    const resolver = new LocalRepositoryTargetResolver(runtime);

    const first = await resolver.inspect("/repo");
    const second = await resolver.inspect("/repo");

    expect(second).toEqual(first);
    expect(runtime.createPrivateIfAbsent).not.toHaveBeenCalled();
    expect((globalThis as any).Services.uuid.generateUUID).not.toHaveBeenCalled();
  });
});

describe("local repository Gecko adapters", () => {
  it("discovers the Git-private path through fixed structured argv", async () => {
    const listeners = new Set<(event: BridgeEvent) => void>();
    const spawnPipe = vi.fn(async (sessionId: string, options: SpawnOptions) => {
      const encoded = Buffer.from(".git/qlab/repository-id\n", "utf8").toString("base64");
      for (const listener of listeners) {
        listener({ type: "output", sessionId, encoding: "base64", data: encoded });
        listener({ type: "exit", sessionId, exitCode: 0, signal: null });
      }
    });
    const bridge = {
      start: vi.fn(async () => undefined),
      spawnPipe,
      onEvent: vi.fn((listener: (event: BridgeEvent) => void) => {
        listeners.add(listener);
        return () => listeners.delete(listener);
      }),
      decodeOutput: vi.fn((_sessionId: string, data: string) =>
        Buffer.from(data, "base64").toString("utf8")),
      flushOutput: vi.fn(() => ""),
    } satisfies Pick<NativeBridge, "start" | "spawnPipe" | "onEvent" | "decodeOutput" | "flushOutput">;
    const runtime = createResearchLoopSiteRuntime(bridge, "resource://qlab/", "1.2.3");

    await expect(runtime.gitPrivatePath("/repo with spaces"))
      .resolves.toBe(".git/qlab/repository-id\n");
    expect(spawnPipe).toHaveBeenCalledWith(
      expect.stringMatching(/^repository-identity-\d+$/),
      {
        argv: [
          "/usr/bin/git",
          "-C",
          "/repo with spaces",
          "rev-parse",
          "--git-path",
          "qlab/repository-id",
        ],
        cwd: "/repo with spaces",
        env: { PATH: "/usr/bin:/bin:/usr/sbin:/sbin" },
      },
    );
  });

  it.each([
    {
      os: "Darwin",
      abi: "x86_64-gcc3",
      modeType: "int",
      fixedModeType: "uint16_t",
      createFlags: 0x0001 | 0x0200 | 0x0800 | 0x0100 | 0x01000000,
      readFlags: 0x0100 | 0x01000000,
    },
    {
      os: "Darwin",
      abi: "aarch64-gcc3",
      modeType: "int",
      fixedModeType: "uint16_t",
      createFlags: 0x0001 | 0x0200 | 0x0800 | 0x0100 | 0x01000000,
      readFlags: 0x0100 | 0x01000000,
    },
    {
      os: "Linux",
      abi: "x86_64-gcc3",
      modeType: "unsigned_int",
      fixedModeType: "unsigned_int",
      createFlags: 0x0001 | 0x0040 | 0x0080 | 0x20000 | 0x80000,
      readFlags: 0x20000 | 0x80000,
    },
    {
      os: "Linux",
      abi: "aarch64-gcc3",
      modeType: "unsigned_int",
      fixedModeType: "unsigned_int",
      createFlags: 0x0001 | 0x0040 | 0x0080 | 0x20000 | 0x80000,
      readFlags: 0x20000 | 0x80000,
    },
  ])("uses true variadic mode CData on $os/$abi", async ({
    os,
    abi,
    modeType,
    fixedModeType,
    createFlags,
    readFlags,
  }) => {
    const globals = globalThis as any;
    const originalServices = globals.Services;
    const originalChromeUtils = globals.ChromeUtils;
    const defaultAbi = Symbol("default_abi");
    const charPointer = Symbol("char.ptr");
    const intType = vi.fn((value: number) => ({ type: "int", value }));
    const unsignedIntType = vi.fn((value: number) => ({ type: "unsigned_int", value }));
    const uint16Type = vi.fn((value: number) => ({ type: "uint16_t", value }));
    const openNative = vi.fn(() => 10);
    const openAtNative = vi.fn(() => 11);
    const nativeFunctions: Record<string, ReturnType<typeof vi.fn>> = {
      open: openNative,
      openat: openAtNative,
      mkdirat: vi.fn(() => 0),
      read: vi.fn(() => 0),
      write: vi.fn((_fd: number, _buffer: unknown, length: number) => length),
      fsync: vi.fn(() => 0),
      close: vi.fn(() => 0),
    };
    const declare = vi.fn((name: string) => nativeFunctions[name]);
    const ctypes = {
      default_abi: defaultAbi,
      int: intType,
      unsigned_int: unsignedIntType,
      uint16_t: uint16Type,
      char: { ptr: charPointer },
      ssize_t: Symbol("ssize_t"),
      void_t: { ptr: Symbol("void.ptr") },
      size_t: Symbol("size_t"),
      uint8_t: {
        array: (length: number) => () => Array.from({ length }, () => 0),
      },
      errno: 0,
      open: vi.fn(() => ({ declare })),
    };
    globals.Services = { appinfo: { OS: os, XPCOMABI: abi } };
    globals.ChromeUtils = {
      importESModule: vi.fn(() => ({ ctypes })),
    };

    try {
      const host = createGeckoQLabPrivateFileHost();

      await expect(host.createPrivateIfAbsent(
        "/repository-id",
        `${GENERATED_UUID}\n`,
        0o600,
      )).resolves.toBe("created");
      await expect(host.readPrivate("/repository-id")).resolves.toBe("");

      expect(declare).toHaveBeenCalledWith(
        "open",
        defaultAbi,
        intType,
        charPointer,
        intType,
        "...",
      );
      expect(declare).toHaveBeenCalledWith(
        "openat",
        defaultAbi,
        intType,
        intType,
        charPointer,
        intType,
        "...",
      );
      expect(declare).toHaveBeenCalledWith(
        "mkdirat",
        defaultAbi,
        intType,
        intType,
        charPointer,
        fixedModeType === "uint16_t" ? uint16Type : unsignedIntType,
      );
      expect(openNative.mock.calls).toEqual([
        ["/", expect.any(Number)],
        ["/", expect.any(Number)],
      ]);
      expect(openAtNative.mock.calls).toEqual([
        [10, "repository-id", createFlags, { type: modeType, value: 0o600 }],
        [10, "repository-id", readFlags],
      ]);
    }
    finally {
      if (originalServices === undefined) delete globals.Services;
      else globals.Services = originalServices;
      if (originalChromeUtils === undefined) delete globals.ChromeUtils;
      else globals.ChromeUtils = originalChromeUtils;
    }
  });

  it("reads and exclusively creates private identity files through no-follow descriptors", async () => {
    const directoryHandle = { close: vi.fn(async () => undefined) };
    const writeHandle = {
      write: vi.fn(async (bytes: Uint8Array) => bytes.length),
      flush: vi.fn(async () => undefined),
      close: vi.fn(async () => undefined),
    };
    const readBytes = new TextEncoder().encode(`${WINNING_UUID}\n`);
    const readHandle = {
      read: vi.fn(async () => readBytes),
      close: vi.fn(async () => undefined),
    };
    const flags = {
      O_RDONLY: 0,
      O_WRONLY: 1,
      O_CREAT: 0x0200,
      O_EXCL: 0x0800,
      O_NOFOLLOW: 0x0100,
      O_DIRECTORY: 0x200000,
      O_CLOEXEC: 0x1000000,
    };
    const openAt = vi.fn(async (_parent, name: string, openFlags: number) => {
      if (name !== "repository-id") return directoryHandle;
      return openFlags & flags.O_CREAT ? writeHandle : readHandle;
    });
    const runtime = {
      flags,
      open: vi.fn(async () => directoryHandle),
      openAt,
      makeDirAt: vi.fn(async () => "created" as const),
    };
    const host = createGeckoQLabPrivateFileHost(runtime);

    await expect(host.createPrivateIfAbsent(
      "/repo/.git/qlab/repository-id",
      `${GENERATED_UUID}\n`,
      0o600,
    )).resolves.toBe("created");
    await expect(host.readPrivate("/repo/.git/qlab/repository-id"))
      .resolves.toBe(`${WINNING_UUID}\n`);

    const createCall = openAt.mock.calls.find((call) =>
      call[1] === "repository-id" && (call[2] & flags.O_CREAT));
    const readCall = openAt.mock.calls.find((call) =>
      call[1] === "repository-id" && !(call[2] & flags.O_CREAT));
    expect(createCall).toEqual([
      directoryHandle,
      "repository-id",
      0x0200 | 0x0800 | 0x0100 | 0x1000000 | 1,
      0o600,
    ]);
    expect(readCall).toEqual([
      directoryHandle,
      "repository-id",
      0x0100 | 0x1000000,
    ]);
    expect(writeHandle.write).toHaveBeenCalledWith(
      new TextEncoder().encode(`${GENERATED_UUID}\n`),
    );
    expect(writeHandle.close).toHaveBeenCalledOnce();
    expect(readHandle.close).toHaveBeenCalledOnce();
    expect(openAt).toHaveBeenCalledWith(
      directoryHandle,
      "qlab",
      0x200000 | 0x0100 | 0x1000000,
    );
  });

  it("reports an exclusive-create winner and a missing descriptor without overwriting", async () => {
    const directoryHandle = { close: vi.fn(async () => undefined) };
    const flags = {
      O_RDONLY: 0,
      O_WRONLY: 1,
      O_CREAT: 0x0200,
      O_EXCL: 0x0800,
      O_NOFOLLOW: 0x0100,
      O_DIRECTORY: 0x200000,
      O_CLOEXEC: 0,
    };
    const runtime = {
      flags,
      open: vi.fn(async () => directoryHandle),
      openAt: vi.fn(async (_parent, name: string, openFlags: number) => {
        if (name !== "repository-id") return directoryHandle;
        if (openFlags & flags.O_CREAT) throw { becauseExists: true };
        throw { becauseNoSuchFile: true };
      }),
      makeDirAt: vi.fn(async () => "created" as const),
    };
    const host = createGeckoQLabPrivateFileHost(runtime);

    await expect(host.createPrivateIfAbsent("/repo/.git/qlab/repository-id", "value", 0o600))
      .resolves.toBe("exists");
    await expect(host.readPrivate("/repo/.git/qlab/repository-id"))
      .resolves.toBeNull();
  });

  it("rejects a symlinked Git-private ancestor before opening the identity file", async () => {
    const directoryHandle = { close: vi.fn(async () => undefined) };
    const openAt = vi.fn(async (_parent, name: string) => {
      if (name === "qlab") throw new Error("symbolic link refused");
      return directoryHandle;
    });
    const runtime = {
      flags: {
        O_RDONLY: 0,
        O_WRONLY: 1,
        O_CREAT: 0x0200,
        O_EXCL: 0x0800,
        O_NOFOLLOW: 0x0100,
        O_DIRECTORY: 0x200000,
        O_CLOEXEC: 0,
      },
      open: vi.fn(async () => directoryHandle),
      openAt,
      makeDirAt: vi.fn(async () => "created" as const),
    };
    const host = createGeckoQLabPrivateFileHost(runtime);

    await expect(host.createPrivateIfAbsent(
      "/repo/.git/qlab/repository-id",
      `${GENERATED_UUID}\n`,
      0o600,
    )).rejects.toThrow("symbolic link refused");
    expect(openAt).not.toHaveBeenCalledWith(
      expect.anything(),
      "repository-id",
      expect.anything(),
      expect.anything(),
    );
  });

  it("retains the verified parent descriptor when its path is retargeted before leaf creation", async () => {
    type Node = {
      children?: Map<string, Node>;
      value?: string;
    };
    type Descriptor = {
      node: Node;
      read?(): Promise<Uint8Array>;
      write?(bytes: Uint8Array): Promise<number>;
      flush?(): Promise<void>;
      close(): Promise<void>;
    };
    const originalIdentity: Node = {};
    const outsideIdentity: Node = { value: "outside-sentinel" };
    const originalPrivate: Node = { children: new Map() };
    const outsidePrivate: Node = {
      children: new Map([["repository-id", outsideIdentity]]),
    };
    const git: Node = { children: new Map([["qlab", originalPrivate]]) };
    const repo: Node = { children: new Map([[".git", git]]) };
    const root: Node = { children: new Map([["repo", repo]]) };
    let retargeted = false;

    const retarget = () => {
      if (retargeted) return;
      retargeted = true;
      git.children!.set("qlab", outsidePrivate);
    };
    const descriptor = (node: Node): Descriptor => ({
      node,
      ...(node.children ? {} : {
        read: async () => new TextEncoder().encode(node.value || ""),
        write: async (bytes: Uint8Array) => {
          node.value = new TextDecoder().decode(bytes);
          return bytes.length;
        },
        flush: async () => undefined,
      }),
      close: async () => undefined,
    });
    const resolveAbsolute = (path: string): Node => {
      let current = root;
      for (const component of path.split("/").filter(Boolean)) {
        const next = current.children?.get(component);
        if (!next) throw { becauseNoSuchFile: true };
        current = next;
      }
      return current;
    };
    const flags = {
      O_RDONLY: 0,
      O_WRONLY: 1,
      O_CREAT: 0x40,
      O_EXCL: 0x80,
      O_NOFOLLOW: 0x20000,
      O_DIRECTORY: 0x10000,
      O_CLOEXEC: 0x80000,
    };
    const runtime = {
      flags,
      open: async (path: string) => descriptor(resolveAbsolute(path)),
      openAt: async (parent: Descriptor, name: string, openFlags: number) => {
        let child = parent.node.children?.get(name);
        if (!child && (openFlags & flags.O_CREAT)) {
          child = originalIdentity;
          parent.node.children!.set(name, child);
        }
        if (!child) throw { becauseNoSuchFile: true };
        const childDescriptor = descriptor(child);
        if (parent.node === git && name === "qlab") retarget();
        return childDescriptor;
      },
      makeDirAt: async () => "created" as const,
    };
    const host = createGeckoQLabPrivateFileHost(runtime);

    await expect(host.createPrivateIfAbsent(
      "/repo/.git/qlab/repository-id",
      `${GENERATED_UUID}\n`,
      0o600,
    )).resolves.toBe("created");

    expect(originalIdentity.value).toBe(`${GENERATED_UUID}\n`);
    expect(outsideIdentity.value).toBe("outside-sentinel");
  });

  it("closes a read leaf and preserves its error when the retained parent close also fails", async () => {
    const leafError = new Error("leaf read failed");
    const parentError = new Error("parent close failed");
    const leaf = {
      read: vi.fn(async () => { throw leafError; }),
      close: vi.fn(async () => undefined),
    };
    const ordinaryDirectory = () => ({ close: vi.fn(async () => undefined) });
    const retainedParent = { close: vi.fn(async () => { throw parentError; }) };
    const flags = {
      O_RDONLY: 0,
      O_WRONLY: 1,
      O_CREAT: 0x40,
      O_EXCL: 0x80,
      O_NOFOLLOW: 0x20000,
      O_DIRECTORY: 0x10000,
      O_CLOEXEC: 0x80000,
    };
    const runtime = {
      flags,
      open: vi.fn(async () => ordinaryDirectory()),
      openAt: vi.fn(async (_parent, name: string) => {
        if (name === "repository-id") return leaf;
        if (name === "qlab") return retainedParent;
        return ordinaryDirectory();
      }),
      makeDirAt: vi.fn(async () => "created" as const),
    };
    const host = createGeckoQLabPrivateFileHost(runtime);

    await expect(host.readPrivate("/repo/.git/qlab/repository-id"))
      .rejects.toBe(leafError);
    expect(leaf.read).toHaveBeenCalledOnce();
    expect(leaf.close).toHaveBeenCalledOnce();
    expect(retainedParent.close).toHaveBeenCalledOnce();
    expect(leaf.close.mock.invocationCallOrder[0]!)
      .toBeLessThan(retainedParent.close.mock.invocationCallOrder[0]!);
  });

  it("writes and closes a created leaf before reporting retained parent close failure", async () => {
    const parentError = new Error("parent close failed");
    let stored = "";
    const leaf = {
      write: vi.fn(async (bytes: Uint8Array) => {
        stored += new TextDecoder().decode(bytes);
        return bytes.length;
      }),
      flush: vi.fn(async () => undefined),
      close: vi.fn(async () => undefined),
    };
    const ordinaryDirectory = () => ({ close: vi.fn(async () => undefined) });
    const retainedParent = { close: vi.fn(async () => { throw parentError; }) };
    const flags = {
      O_RDONLY: 0,
      O_WRONLY: 1,
      O_CREAT: 0x40,
      O_EXCL: 0x80,
      O_NOFOLLOW: 0x20000,
      O_DIRECTORY: 0x10000,
      O_CLOEXEC: 0x80000,
    };
    const runtime = {
      flags,
      open: vi.fn(async () => ordinaryDirectory()),
      openAt: vi.fn(async (_parent, name: string) => {
        if (name === "repository-id") return leaf;
        if (name === "qlab") return retainedParent;
        return ordinaryDirectory();
      }),
      makeDirAt: vi.fn(async () => "created" as const),
    };
    const host = createGeckoQLabPrivateFileHost(runtime);

    await expect(host.createPrivateIfAbsent(
      "/repo/.git/qlab/repository-id",
      `${GENERATED_UUID}\n`,
      0o600,
    )).rejects.toBe(parentError);
    expect(stored).toBe(`${GENERATED_UUID}\n`);
    expect(leaf.flush).toHaveBeenCalledOnce();
    expect(leaf.close).toHaveBeenCalledOnce();
    expect(retainedParent.close).toHaveBeenCalledOnce();
    expect(leaf.close.mock.invocationCallOrder[0]!)
      .toBeLessThan(retainedParent.close.mock.invocationCallOrder[0]!);
  });
});
