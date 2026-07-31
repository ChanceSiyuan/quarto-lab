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

interface GeckoPrivateFileOS {
  Constants: { libc: Record<string, number | undefined> };
  File: {
    makeDir(path: string, options: Record<string, unknown>): Promise<void>;
    open(
      path: string,
      mode: Record<string, boolean>,
      options: Record<string, number>,
    ): Promise<GeckoPrivateFileHandle>;
  };
  Path: { dirname(path: string): string };
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

/** Uses OS.File descriptors so identity reads and exclusive creates reject symlinks at the leaf. */
export function createGeckoQLabPrivateFileHost(
  suppliedOS?: GeckoPrivateFileOS,
): QLabPrivateFileHost {
  const os = () => suppliedOS ?? loadGeckoPrivateFileOS();
  return {
    async readPrivate(path) {
      const runtime = os();
      try {
        await assertNoFollowDirectoryChain(runtime, runtime.Path.dirname(path));
      }
      catch (error) {
        if (isGeckoFileError(error, "becauseNoSuchFile")) return null;
        throw error;
      }
      let file: GeckoPrivateFileHandle;
      try {
        file = await runtime.File.open(
          path,
          { read: true, existing: true },
          { unixFlags: readNoFollowFlags(runtime) },
        );
      }
      catch (error) {
        if (isGeckoFileError(error, "becauseNoSuchFile")) return null;
        throw error;
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
      const runtime = os();
      await preparePrivateDirectory(runtime, runtime.Path.dirname(path));
      let file: GeckoPrivateFileHandle;
      try {
        file = await runtime.File.open(
          path,
          { write: true, create: true, append: false },
          { unixFlags: createNoFollowFlags(runtime), unixMode: mode },
        );
      }
      catch (error) {
        if (isGeckoFileError(error, "becauseExists")) return "exists";
        throw error;
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

function loadGeckoPrivateFileOS(): GeckoPrivateFileOS {
  try {
    return ChromeUtils.importESModule("resource://gre/modules/osfile.sys.mjs").OS as GeckoPrivateFileOS;
  }
  catch {
    return ChromeUtils.import("resource://gre/modules/osfile.jsm").OS as GeckoPrivateFileOS;
  }
}

function readNoFollowFlags(os: GeckoPrivateFileOS): number {
  const libc = os.Constants.libc;
  return requireGeckoFlag(libc, "O_RDONLY")
    | requireGeckoFlag(libc, "O_NOFOLLOW")
    | optionalGeckoFlag(libc, "O_CLOEXEC");
}

function createNoFollowFlags(os: GeckoPrivateFileOS): number {
  const libc = os.Constants.libc;
  return requireGeckoFlag(libc, "O_WRONLY")
    | requireGeckoFlag(libc, "O_CREAT")
    | requireGeckoFlag(libc, "O_EXCL")
    | requireGeckoFlag(libc, "O_NOFOLLOW")
    | optionalGeckoFlag(libc, "O_CLOEXEC");
}

function directoryNoFollowFlags(os: GeckoPrivateFileOS): number {
  const libc = os.Constants.libc;
  return requireGeckoFlag(libc, "O_RDONLY")
    | requireGeckoFlag(libc, "O_DIRECTORY")
    | requireGeckoFlag(libc, "O_NOFOLLOW")
    | optionalGeckoFlag(libc, "O_CLOEXEC");
}

async function preparePrivateDirectory(
  os: GeckoPrivateFileOS,
  directory: string,
): Promise<void> {
  await assertNoFollowDirectoryChain(os, os.Path.dirname(directory));
  try {
    await os.File.makeDir(directory, {
      ignoreExisting: false,
      unixMode: 0o700,
    });
  }
  catch (error) {
    if (!isGeckoFileError(error, "becauseExists")) throw error;
  }
  await assertNoFollowDirectoryChain(os, directory);
}

async function assertNoFollowDirectoryChain(
  os: GeckoPrivateFileOS,
  directory: string,
): Promise<void> {
  const directories: string[] = [];
  let current = directory;
  while (current) {
    directories.push(current);
    const parent = os.Path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  for (const path of directories.reverse()) {
    const handle = await os.File.open(
      path,
      { read: true, existing: true },
      { unixFlags: directoryNoFollowFlags(os) },
    );
    await handle.close();
  }
}

function requireGeckoFlag(
  flags: Record<string, number | undefined>,
  name: string,
): number {
  const value = flags[name];
  if (typeof value !== "number") {
    throw new Error(`Gecko does not expose the required private-file flag ${name}`);
  }
  return value;
}

function optionalGeckoFlag(
  flags: Record<string, number | undefined>,
  name: string,
): number {
  const value = flags[name];
  return typeof value === "number" ? value : 0;
}

function isGeckoFileError(error: unknown, property: string): boolean {
  return typeof error === "object"
    && error !== null
    && (error as Record<string, unknown>)[property] === true;
}

function pathIsAbsolute(path: string): boolean {
  if (typeof PathUtils.isAbsolute === "function") return PathUtils.isAbsolute(path);
  return /^(?:[\\/]|[A-Za-z]:[\\/])/u.test(path);
}
