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
    const open = vi.fn(async (path: string, mode: Record<string, boolean>) => {
      if (!path.endsWith("/repository-id")) return directoryHandle;
      return mode.create ? writeHandle : readHandle;
    });
    const os = {
      Constants: {
        libc: {
          O_RDONLY: 0,
          O_WRONLY: 1,
          O_CREAT: 0x0200,
          O_EXCL: 0x0800,
          O_NOFOLLOW: 0x0100,
          O_DIRECTORY: 0x200000,
          O_CLOEXEC: 0x1000000,
        },
      },
      File: {
        makeDir: vi.fn(async () => undefined),
        open,
      },
      Path: { dirname: parentPath },
    };
    const host = createGeckoQLabPrivateFileHost(os);

    await expect(host.createPrivateIfAbsent(
      "/repo/.git/qlab/repository-id",
      `${GENERATED_UUID}\n`,
      0o600,
    )).resolves.toBe("created");
    await expect(host.readPrivate("/repo/.git/qlab/repository-id"))
      .resolves.toBe(`${WINNING_UUID}\n`);

    const createCall = open.mock.calls.find((call) =>
      call[0].endsWith("/repository-id") && call[1].create);
    const readCall = open.mock.calls.find((call) =>
      call[0].endsWith("/repository-id") && call[1].read);
    expect(createCall).toEqual([
      "/repo/.git/qlab/repository-id",
      { write: true, create: true, append: false },
      { unixFlags: 0x0200 | 0x0800 | 0x0100 | 0x1000000 | 1, unixMode: 0o600 },
    ]);
    expect(readCall).toEqual([
      "/repo/.git/qlab/repository-id",
      { read: true, existing: true },
      { unixFlags: 0x0100 | 0x1000000 },
    ]);
    expect(writeHandle.write).toHaveBeenCalledWith(
      new TextEncoder().encode(`${GENERATED_UUID}\n`),
    );
    expect(writeHandle.close).toHaveBeenCalledOnce();
    expect(readHandle.close).toHaveBeenCalledOnce();
    expect(open).toHaveBeenCalledWith(
      "/repo/.git/qlab",
      { read: true, existing: true },
      { unixFlags: 0x200000 | 0x0100 | 0x1000000 },
    );
  });

  it("reports an exclusive-create winner and a missing descriptor without overwriting", async () => {
    const directoryHandle = { close: vi.fn(async () => undefined) };
    const open = vi.fn(async (path: string, mode: Record<string, boolean>) => {
      if (!path.endsWith("/repository-id")) return directoryHandle;
      if (mode.create) throw { becauseExists: true };
      throw { becauseNoSuchFile: true };
    });
    const os = {
      Constants: {
        libc: {
          O_RDONLY: 0,
          O_WRONLY: 1,
          O_CREAT: 0x0200,
          O_EXCL: 0x0800,
          O_NOFOLLOW: 0x0100,
          O_DIRECTORY: 0x200000,
        },
      },
      File: {
        makeDir: vi.fn(async () => undefined),
        open,
      },
      Path: { dirname: parentPath },
    };
    const host = createGeckoQLabPrivateFileHost(os);

    await expect(host.createPrivateIfAbsent("/repo/.git/qlab/repository-id", "value", 0o600))
      .resolves.toBe("exists");
    await expect(host.readPrivate("/repo/.git/qlab/repository-id"))
      .resolves.toBeNull();
  });

  it("rejects a symlinked Git-private ancestor before opening the identity file", async () => {
    const directoryHandle = { close: vi.fn(async () => undefined) };
    const open = vi.fn(async (path: string) => {
      if (path === "/repo/.git/qlab") throw new Error("symbolic link refused");
      return directoryHandle;
    });
    const os = {
      Constants: {
        libc: {
          O_RDONLY: 0,
          O_WRONLY: 1,
          O_CREAT: 0x0200,
          O_EXCL: 0x0800,
          O_NOFOLLOW: 0x0100,
          O_DIRECTORY: 0x200000,
        },
      },
      File: {
        makeDir: vi.fn(async () => undefined),
        open,
      },
      Path: { dirname: parentPath },
    };
    const host = createGeckoQLabPrivateFileHost(os);

    await expect(host.createPrivateIfAbsent(
      "/repo/.git/qlab/repository-id",
      `${GENERATED_UUID}\n`,
      0o600,
    )).rejects.toThrow("symbolic link refused");
    expect(open).not.toHaveBeenCalledWith(
      "/repo/.git/qlab/repository-id",
      expect.anything(),
      expect.anything(),
    );
  });
});

function parentPath(path: string): string {
  if (path === "/") return "/";
  const parent = path.slice(0, path.lastIndexOf("/"));
  return parent || "/";
}
