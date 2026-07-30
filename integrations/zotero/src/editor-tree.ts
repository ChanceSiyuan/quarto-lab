/**
 * The two trees this editor may open, and every way they differ.
 *
 * `knowledge/` is trusted: it is published, and it has a validation gate.
 * `drafts/` is untrusted: it is never published, and it has no gate — there is
 * no `drafts:check` in this repository, and one is not invented here. Routing
 * both through a single descriptor is what keeps that difference visible
 * instead of scattered across half a dozen hard-coded prefixes.
 */

export type EditorTreeId = "knowledge" | "drafts";

export interface EditorTree {
  id: EditorTreeId;
  /** Repository-relative directory, with its trailing slash. */
  prefix: string;
  /** What the interface calls this tree. */
  label: string;
  /** Whether `npm run build` publishes it. */
  published: boolean;
  /** What the Check button runs, or null when the tree has no gate. */
  validateCommand: string | null;
  /** Which preview process serves the render tab. */
  renderCommand: "knowledge-preview" | "draft-preview";
}

export const EDITOR_TREES: readonly EditorTree[] = [
  {
    id: "knowledge",
    prefix: "knowledge/",
    label: "Trusted Knowledge",
    published: true,
    validateCommand: "npm run knowledge:check",
    renderCommand: "knowledge-preview",
  },
  {
    id: "drafts",
    prefix: "drafts/",
    label: "Draft",
    published: false,
    validateCommand: null,
    renderCommand: "draft-preview",
  },
];

/**
 * A path component that may never appear, whatever tree it is in.
 *
 * A leading `-` is refused along with the traversal components because these
 * paths become arguments to Quarto, which would read `--output-dir=` as an
 * option rather than as part of a file name.
 */
function hasUnsafeComponent(relativePath: string): boolean {
  return relativePath
    .split("/")
    .some((part) => part === "" || part === "." || part === ".." || part.startsWith("-"));
}

export function treeForPath(relativePath: string): EditorTree | null {
  if (!relativePath.endsWith(".qmd") || hasUnsafeComponent(relativePath)) return null;
  return EDITOR_TREES.find((tree) => relativePath.startsWith(tree.prefix)) ?? null;
}

export function isEditablePath(relativePath: string): boolean {
  return treeForPath(relativePath) !== null;
}

function normalizedRoot(root: string): string {
  return root.trim().replace(/[\\/]+$/, "");
}

/**
 * The absolute path of an editable file.
 *
 * Containment is enforced here rather than in the view, so that no caller can
 * reach the filesystem without having passed it.
 */
export function resolveEditablePath(repoRoot: string, relativePath: string): string {
  const root = normalizedRoot(repoRoot);
  if (!root) throw new Error("Choose a Research Loop repository first");
  if (!isEditablePath(relativePath)) {
    throw new Error("Only QMD files in knowledge/ or drafts/ can be edited");
  }
  return `${root}/${relativePath}`;
}

/** The knowledge page a served URL corresponds to, or null. */
export function knowledgeUrlToQmdPath(value: string): string | null {
  let url: URL;
  try {
    url = new URL(value);
  }
  catch {
    return null;
  }
  if (url.hostname !== "127.0.0.1" && url.hostname !== "localhost") return null;
  let path: string;
  try {
    path = decodeURIComponent(url.pathname);
  }
  catch {
    return null;
  }
  if (!path.startsWith("/knowledge/")) return null;
  const relative = path.slice("/knowledge/".length);
  if (!relative) return "knowledge/index.qmd";
  if (relative.startsWith("categories/") || relative === "search.html") return null;
  const qmd = relative.endsWith("/")
    ? `${relative}index.qmd`
    : relative.endsWith(".html")
      ? `${relative.slice(0, -".html".length)}.qmd`
      : null;
  if (!qmd) return null;
  const result = `knowledge/${qmd}`;
  return isEditablePath(result) ? result : null;
}

/** Where a preview server serves this file. */
export function previewPathFor(tree: EditorTree, relativePath: string): string {
  const within = relativePath.slice(tree.prefix.length);
  if (within === "index.qmd") return "/";
  if (within.endsWith("/index.qmd")) return `/${within.slice(0, -"index.qmd".length)}`;
  return `/${within.slice(0, -".qmd".length)}.html`;
}
