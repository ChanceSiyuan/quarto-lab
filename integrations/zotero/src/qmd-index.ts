import { EDITOR_TREES, treeForPath, type EditorTreeId } from "./editor-tree";

export interface QmdIndexEntry {
  relativePath: string;
  treeId: EditorTreeId;
  /** File name without the extension; what a search usually means. */
  name: string;
  /** Lower-cased path segments, for matching. */
  segments: string[];
  /** A persistent Agent working copy differs from the original Draft. */
  pendingChange?: boolean;
}

export interface QmdIndexScanner {
  list(absoluteDirectory: string): Promise<{ name: string; directory: boolean }[]>;
}

/** Directories that hold generated output rather than sources. */
const SKIPPED_DIRECTORIES = new Set([".preview", ".raw", ".figures", "_site", "work", "node_modules"]);

export async function buildQmdIndex(
  scanner: QmdIndexScanner,
  repoRoot: string,
): Promise<QmdIndexEntry[]> {
  const entries: QmdIndexEntry[] = [];
  const root = repoRoot.replace(/[\\/]+$/, "");

  const walk = async (relativeDirectory: string): Promise<void> => {
    let children: { name: string; directory: boolean }[];
    try {
      children = await scanner.list(`${root}/${relativeDirectory}`);
    }
    catch {
      return; // A tree that is not present is simply empty.
    }
    for (const child of children) {
      const relative = `${relativeDirectory}/${child.name}`;
      if (child.directory) {
        if (SKIPPED_DIRECTORIES.has(child.name) || child.name.startsWith(".")) continue;
        await walk(relative);
        continue;
      }
      if (child.name.startsWith(".") || child.name.includes(".qlab-preview-")) continue;
      const tree = treeForPath(relative);
      if (!tree) continue;
      entries.push({
        relativePath: relative,
        treeId: tree.id,
        name: child.name.slice(0, -".qmd".length),
        segments: relative.toLowerCase().split("/"),
      });
    }
  };

  for (const tree of EDITOR_TREES) await walk(tree.prefix.slice(0, -1));
  entries.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
  return entries;
}

/**
 * Quick-open filtering.
 *
 * The query is matched as a contiguous run inside the path, so `magic/bell`
 * finds `knowledge/Magic/Bell_magic.qmd` and `magbel` does not. Rewarding a
 * reordered query with a hit the user cannot explain is worse than no hit.
 */
export function filterQmdIndex(entries: readonly QmdIndexEntry[], query: string): QmdIndexEntry[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [...entries];
  const scored: { entry: QmdIndexEntry; score: number }[] = [];
  for (const entry of entries) {
    const haystack = entry.relativePath.toLowerCase();
    const at = haystack.indexOf(needle);
    if (at < 0) continue;
    const inName = entry.name.toLowerCase().includes(needle);
    scored.push({ entry, score: (inName ? 0 : 1_000) + at });
  }
  scored.sort((left, right) => left.score - right.score
    || left.entry.relativePath.localeCompare(right.entry.relativePath));
  return scored.map((hit) => hit.entry);
}

export interface QmdTreeNode {
  name: string;
  /** Repository-relative path of this node. */
  path: string;
  treeId: EditorTreeId;
  children: QmdTreeNode[];
  /** Present on leaves. */
  entry?: QmdIndexEntry;
}

export function groupIntoTree(entries: readonly QmdIndexEntry[]): QmdTreeNode[] {
  const roots: QmdTreeNode[] = EDITOR_TREES.map((tree) => ({
    name: tree.prefix.slice(0, -1),
    path: tree.prefix.slice(0, -1),
    treeId: tree.id,
    children: [],
  }));

  for (const entry of entries) {
    const parts = entry.relativePath.split("/");
    const root = roots.find((candidate) => candidate.treeId === entry.treeId);
    if (!root) continue;
    let node = root;
    for (let index = 1; index < parts.length - 1; index++) {
      const name = parts[index]!;
      let next = node.children.find((child) => child.name === name && child.entry === undefined);
      if (!next) {
        next = {
          name,
          path: parts.slice(0, index + 1).join("/"),
          treeId: entry.treeId,
          children: [],
        };
        node.children.push(next);
      }
      node = next;
    }
    node.children.push({
      name: entry.name,
      path: entry.relativePath,
      treeId: entry.treeId,
      children: [],
      entry,
    });
  }

  const sort = (node: QmdTreeNode): void => {
    node.children.sort((left, right) => {
      const leftIsDirectory = left.entry === undefined;
      const rightIsDirectory = right.entry === undefined;
      if (leftIsDirectory !== rightIsDirectory) return leftIsDirectory ? -1 : 1;
      return left.name.localeCompare(right.name);
    });
    node.children.forEach(sort);
  };
  roots.forEach(sort);
  return roots;
}

/** Reads directories through Zotero's IOUtils. */
export const geckoScanner: QmdIndexScanner = {
  async list(directory) {
    const children = await IOUtils.getChildren(directory);
    return Promise.all(children.map(async (child: string) => {
      const name = child.split("/").pop() || child;
      try {
        const info = await IOUtils.stat(child);
        return { name, directory: info.type === "directory" };
      }
      catch {
        return { name, directory: false };
      }
    }));
  },
};
