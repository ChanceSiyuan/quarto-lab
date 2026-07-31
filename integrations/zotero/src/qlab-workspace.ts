export interface QLabPathHost {
  exists(path: string): Promise<boolean>;
  realPath(path: string): Promise<string>;
  entries(path: string): Promise<string[]>;
  join(...parts: string[]): string;
  filename(path: string): string;
}

interface GeckoPrivateFileHandle {
  read?(bytes?: number): Promise<Uint8Array>;
  write?(bytes: Uint8Array): Promise<number>;
  flush?(): Promise<void>;
  close(): Promise<void>;
}

interface GeckoPosixFlags {
  O_RDONLY: number;
  O_WRONLY: number;
  O_CREAT: number;
  O_EXCL: number;
  O_NOFOLLOW: number;
  O_DIRECTORY: number;
  O_CLOEXEC: number;
}

interface GeckoPrivateFileRuntime {
  flags: GeckoPosixFlags;
  open(path: string, flags: number, mode?: number): Promise<GeckoPrivateFileHandle>;
  openAt(
    parent: GeckoPrivateFileHandle,
    name: string,
    flags: number,
    mode?: number,
  ): Promise<GeckoPrivateFileHandle>;
  makeDirAt(
    parent: GeckoPrivateFileHandle,
    name: string,
    mode: number,
  ): Promise<"created" | "exists">;
}

export interface QLabPrivateFileHost {
  readPrivate(path: string): Promise<string | null>;
  createPrivateIfAbsent(path: string, value: string, mode: number): Promise<"created" | "exists">;
  resolvePath(root: string, path: string): string;
  isPathInside(root: string, candidate: string): boolean;
}

const REQUIRED_ENTRIES = ["AGENTS.md", "qlab", "literature", "drafts", "knowledge"] as const;
export const QLAB_STARTER_MARKER = ".research-loop/starter.json";
const IGNORABLE_EMPTY_DIRECTORY_ENTRIES = new Set([".DS_Store", ".git"]);
/** User-authored trees that may safely predate the application skeleton. */
const SAFE_PARTIAL_CONTENT_TREES = new Set(["knowledge", "drafts", "literature"]);

export type QLabRepositoryState = "missing" | "ready" | "empty" | "partial" | "incompatible";

export async function isQLabRepositoryShape(
  root: string,
  host: QLabPathHost,
): Promise<boolean> {
  if (!root.trim()) return false;
  const checks = await Promise.all(
    REQUIRED_ENTRIES.map((entry) => host.exists(host.join(root, entry))),
  );
  return checks.every(Boolean);
}

export async function normalizeQLabRoot(
  value: string,
  host: QLabPathHost,
): Promise<string> {
  const trimmed = value.trim().replace(/[\\/]+$/, "");
  if (!trimmed) return "";
  return (await host.realPath(trimmed)).replace(/[\\/]+$/, "");
}

/**
 * Empty directories are valid first-run targets. A starter marker admits a
 * safe retry after an interrupted extraction; every other non-repository
 * directory is rejected so initialization never overwrites arbitrary files.
 */
export async function qlabRepositoryState(
  root: string,
  host: QLabPathHost,
): Promise<QLabRepositoryState> {
  if (!root.trim()) return "missing";
  if (await isQLabRepositoryShape(root, host)) return "ready";
  if (await host.exists(host.join(root, QLAB_STARTER_MARKER))) return "partial";
  const entries = (await host.entries(root))
    .map((entry) => host.filename(entry))
    .filter((entry) => !IGNORABLE_EMPTY_DIRECTORY_ENTRIES.has(entry));
  if (entries.length === 0) return "empty";
  return entries.every((entry) => SAFE_PARTIAL_CONTENT_TREES.has(entry))
    ? "partial"
    : "incompatible";
}

export function createGeckoQLabPathHost(): QLabPathHost {
  return {
    exists: (path) => IOUtils.exists(path),
    entries: (path) => IOUtils.getChildren(path),
    realPath: async (path) => {
      const file = Components.classes["@mozilla.org/file/local;1"]
        .createInstance(Components.interfaces.nsIFile);
      file.initWithPath(path);
      file.normalize();
      return String(file.path || path);
    },
    join: (...parts) => PathUtils.join(...parts),
    filename: (path) => PathUtils.filename(path),
  };
}

const MAX_PRIVATE_FILE_BYTES = 128;

/** Traverses and opens the private identity descriptor-relatively without following symlinks. */
export function createGeckoQLabPrivateFileHost(
  suppliedRuntime?: GeckoPrivateFileRuntime,
): QLabPrivateFileHost {
  const loadRuntime = () => suppliedRuntime ?? createGeckoPrivateFileRuntime();
  return {
    async readPrivate(path) {
      const runtime = loadRuntime();
      let parent: GeckoPrivateFileHandle;
      let leaf: string;
      try {
        ({ parent, leaf } = await openPrivateParent(runtime, path, false));
      }
      catch (error) {
        if (isGeckoFileError(error, "becauseNoSuchFile")) return null;
        throw error;
      }
      let file: GeckoPrivateFileHandle;
      try {
        file = await runtime.openAt(parent, leaf, readNoFollowFlags(runtime));
      }
      catch (error) {
        if (isGeckoFileError(error, "becauseNoSuchFile")) return null;
        throw error;
      }
      finally {
        await parent.close();
      }
      try {
        if (!file.read) throw new Error("Gecko private file is not readable");
        const bytes = await file.read(MAX_PRIVATE_FILE_BYTES + 1);
        if (bytes.length > MAX_PRIVATE_FILE_BYTES) {
          throw new Error("Repository identity file is too large");
        }
        return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      }
      finally {
        await file.close();
      }
    },
    async createPrivateIfAbsent(path, value, mode) {
      const runtime = loadRuntime();
      const { parent, leaf } = await openPrivateParent(runtime, path, true);
      let file: GeckoPrivateFileHandle;
      try {
        file = await runtime.openAt(parent, leaf, createNoFollowFlags(runtime), mode);
      }
      catch (error) {
        if (isGeckoFileError(error, "becauseExists")) return "exists";
        throw error;
      }
      finally {
        await parent.close();
      }
      try {
        if (!file.write) throw new Error("Gecko private file is not writable");
        const bytes = new TextEncoder().encode(value);
        let offset = 0;
        while (offset < bytes.length) {
          const written = await file.write(bytes.subarray(offset));
          if (!Number.isInteger(written) || written <= 0) {
            throw new Error("Could not write the complete repository identity");
          }
          offset += written;
        }
        await file.flush?.();
        return "created";
      }
      finally {
        await file.close();
      }
    },
    resolvePath(root, path) {
      const value = pathIsAbsolute(path) ? path : PathUtils.join(root, path);
      return PathUtils.normalize(value);
    },
    isPathInside(root, candidate) {
      const normalizedRoot = PathUtils.normalize(root).replace(/[\\/]+$/u, "");
      const normalizedCandidate = PathUtils.normalize(candidate);
      return normalizedCandidate === normalizedRoot
        || normalizedCandidate.startsWith(`${normalizedRoot}/`)
        || normalizedCandidate.startsWith(`${normalizedRoot}\\`);
    },
  };
}

function readNoFollowFlags(runtime: GeckoPrivateFileRuntime): number {
  return runtime.flags.O_RDONLY
    | runtime.flags.O_NOFOLLOW
    | runtime.flags.O_CLOEXEC;
}

function createNoFollowFlags(runtime: GeckoPrivateFileRuntime): number {
  return runtime.flags.O_WRONLY
    | runtime.flags.O_CREAT
    | runtime.flags.O_EXCL
    | runtime.flags.O_NOFOLLOW
    | runtime.flags.O_CLOEXEC;
}

function directoryNoFollowFlags(runtime: GeckoPrivateFileRuntime): number {
  return runtime.flags.O_RDONLY
    | runtime.flags.O_DIRECTORY
    | runtime.flags.O_NOFOLLOW
    | runtime.flags.O_CLOEXEC;
}

async function openPrivateParent(
  runtime: GeckoPrivateFileRuntime,
  path: string,
  createFinalDirectory: boolean,
): Promise<{ parent: GeckoPrivateFileHandle; leaf: string }> {
  const components = privatePathComponents(path);
  const leaf = components.pop();
  if (!leaf) throw new Error("Repository identity path has no filename");
  let current = await runtime.open("/", directoryNoFollowFlags(runtime));
  try {
    for (let index = 0; index < components.length; index++) {
      const component = components[index]!;
      let next: GeckoPrivateFileHandle;
      try {
        next = await runtime.openAt(
          current,
          component,
          directoryNoFollowFlags(runtime),
        );
      }
      catch (error) {
        const mayCreate = createFinalDirectory
          && index === components.length - 1
          && isGeckoFileError(error, "becauseNoSuchFile");
        if (!mayCreate) throw error;
        await runtime.makeDirAt(current, component, 0o700);
        next = await runtime.openAt(
          current,
          component,
          directoryNoFollowFlags(runtime),
        );
      }
      const previous = current;
      current = next;
      await previous.close();
    }
    return { parent: current, leaf };
  }
  catch (error) {
    await current.close();
    throw error;
  }
}

function privatePathComponents(path: string): string[] {
  if (!path.startsWith("/")) {
    throw new Error("Repository identity path must be an absolute POSIX path");
  }
  const components = path.split("/").filter(Boolean);
  if (components.some((component) => component === "." || component === "..")) {
    throw new Error("Repository identity path must be normalized");
  }
  return components;
}

function isGeckoFileError(error: unknown, property: string): boolean {
  return typeof error === "object"
    && error !== null
    && (error as Record<string, unknown>)[property] === true;
}

function createGeckoPrivateFileRuntime(): GeckoPrivateFileRuntime {
  const platform = String(Services.appinfo.OS);
  const constants = posixConstants(platform);
  const { ctypes } = ChromeUtils.importESModule(
    "resource://gre/modules/ctypes.sys.mjs",
  ) as { ctypes: any };
  const library = ctypes.open(platform === "Darwin" ? "libSystem.B.dylib" : "libc.so.6");
  const open = library.declare(
    "open",
    ctypes.default_abi,
    ctypes.int,
    ctypes.char.ptr,
    ctypes.int,
    ctypes.int,
  );
  const openAt = library.declare(
    "openat",
    ctypes.default_abi,
    ctypes.int,
    ctypes.int,
    ctypes.char.ptr,
    ctypes.int,
    ctypes.int,
  );
  const makeDirAt = library.declare(
    "mkdirat",
    ctypes.default_abi,
    ctypes.int,
    ctypes.int,
    ctypes.char.ptr,
    ctypes.int,
  );
  const read = library.declare(
    "read",
    ctypes.default_abi,
    ctypes.ssize_t,
    ctypes.int,
    ctypes.void_t.ptr,
    ctypes.size_t,
  );
  const write = library.declare(
    "write",
    ctypes.default_abi,
    ctypes.ssize_t,
    ctypes.int,
    ctypes.void_t.ptr,
    ctypes.size_t,
  );
  const flush = library.declare(
    "fsync",
    ctypes.default_abi,
    ctypes.int,
    ctypes.int,
  );
  const close = library.declare(
    "close",
    ctypes.default_abi,
    ctypes.int,
    ctypes.int,
  );

  const descriptor = (fd: number): GeckoPrivateFileHandle & { fd: number } => {
    let openFd: number | null = fd;
    const requireFd = () => {
      if (openFd === null) throw new Error("Repository identity descriptor is closed");
      return openFd;
    };
    return {
      fd,
      async read(bytes = MAX_PRIVATE_FILE_BYTES + 1) {
        const BufferType = ctypes.uint8_t.array(bytes);
        const buffer = BufferType();
        const count = Number(read(requireFd(), buffer, bytes));
        if (count < 0) throw geckoPosixError("read", Number(ctypes.errno), constants);
        return Uint8Array.from({ length: count }, (_, index) => Number(buffer[index]));
      },
      async write(bytes) {
        const BufferType = ctypes.uint8_t.array(bytes.length);
        const buffer = BufferType();
        for (let index = 0; index < bytes.length; index++) buffer[index] = bytes[index]!;
        const count = Number(write(requireFd(), buffer, bytes.length));
        if (count < 0) throw geckoPosixError("write", Number(ctypes.errno), constants);
        return count;
      },
      async flush() {
        if (Number(flush(requireFd())) < 0) {
          throw geckoPosixError("fsync", Number(ctypes.errno), constants);
        }
      },
      async close() {
        if (openFd === null) return;
        const closing = openFd;
        openFd = null;
        if (Number(close(closing)) < 0) {
          throw geckoPosixError("close", Number(ctypes.errno), constants);
        }
      },
    };
  };
  const descriptorFd = (handle: GeckoPrivateFileHandle): number => {
    const fd = (handle as GeckoPrivateFileHandle & { fd?: unknown }).fd;
    if (typeof fd !== "number") throw new Error("Invalid repository directory descriptor");
    return fd;
  };
  const requireDescriptor = (
    operation: string,
    fd: number,
  ): GeckoPrivateFileHandle => {
    if (fd < 0) throw geckoPosixError(operation, Number(ctypes.errno), constants);
    return descriptor(fd);
  };
  return {
    flags: constants.flags,
    async open(path, flags, mode = 0) {
      return requireDescriptor("open", Number(open(path, flags, mode)));
    },
    async openAt(parent, name, flags, mode = 0) {
      return requireDescriptor(
        "openat",
        Number(openAt(descriptorFd(parent), name, flags, mode)),
      );
    },
    async makeDirAt(parent, name, mode) {
      if (Number(makeDirAt(descriptorFd(parent), name, mode)) === 0) return "created";
      const errno = Number(ctypes.errno);
      if (errno === constants.EEXIST) return "exists";
      throw geckoPosixError("mkdirat", errno, constants);
    },
  };
}

function posixConstants(platform: string): {
  flags: GeckoPosixFlags;
  ENOENT: number;
  EEXIST: number;
} {
  if (platform === "Darwin") {
    return {
      flags: {
        O_RDONLY: 0,
        O_WRONLY: 0x0001,
        O_CREAT: 0x0200,
        O_EXCL: 0x0800,
        O_NOFOLLOW: 0x0100,
        O_DIRECTORY: 0x00100000,
        O_CLOEXEC: 0x01000000,
      },
      ENOENT: 2,
      EEXIST: 17,
    };
  }
  if (platform === "Linux") {
    return {
      flags: {
        O_RDONLY: 0,
        O_WRONLY: 0x0001,
        O_CREAT: 0x0040,
        O_EXCL: 0x0080,
        O_NOFOLLOW: 0x20000,
        O_DIRECTORY: 0x10000,
        O_CLOEXEC: 0x80000,
      },
      ENOENT: 2,
      EEXIST: 17,
    };
  }
  throw new Error("Repository identity files require macOS or Linux");
}

function geckoPosixError(
  operation: string,
  errno: number,
  constants: { ENOENT: number; EEXIST: number },
): Error & { becauseNoSuchFile?: boolean; becauseExists?: boolean } {
  const error = new Error(`Repository identity ${operation} failed with errno ${errno}`) as
    Error & { becauseNoSuchFile?: boolean; becauseExists?: boolean };
  if (errno === constants.ENOENT) error.becauseNoSuchFile = true;
  if (errno === constants.EEXIST) error.becauseExists = true;
  return error;
}

function pathIsAbsolute(path: string): boolean {
  if (typeof PathUtils.isAbsolute === "function") return PathUtils.isAbsolute(path);
  return /^(?:[\\/]|[A-Za-z]:[\\/])/u.test(path);
}
