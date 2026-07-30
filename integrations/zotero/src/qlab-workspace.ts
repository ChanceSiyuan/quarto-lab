export interface QLabPathHost {
  exists(path: string): Promise<boolean>;
  realPath(path: string): Promise<string>;
  entries(path: string): Promise<string[]>;
  join(...parts: string[]): string;
  filename(path: string): string;
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
