/**
 * Turns the `knowledge/` directory into a graph of curated pages.
 *
 * The parser answers "what does this file say?"; this module answers "what do
 * these files say about each other?" — which page contains which, which topics
 * are related, and which files on disk a page actually needs. It reads the
 * filesystem and it resolves links, and those are the only two things it does
 * that the parser will not.
 *
 * Three rules shape everything below:
 *
 * - **containment is curated, not inferred.** A directory becomes a topic by
 *   having an `index.qmd`, and a page becomes part of a topic by being listed
 *   in that index's `## Reading map`. The filesystem supplies the candidates;
 *   the author supplies the order and the meaning. Enumeration order is never
 *   allowed to leak into the result: ids are sorted before use;
 * - **nothing outside the tree is reachable.** Every local link and image is
 *   resolved against the real path of the knowledge root, so a `../` escape, an
 *   absolute path, a foreign URL scheme, and a symbolic link are all
 *   unresolvable — a symlink even when it points back inside the tree, because
 *   the published site is built by copying the files this graph names;
 * - **loading never judges.** `loadKnowledge` builds the best graph it can from
 *   whatever is on disk and reports nothing; `validate.ts` turns the same data
 *   into diagnostics. That split is what lets one run report every problem in a
 *   tree instead of stopping at the first.
 *
 * The functions below `loadKnowledge` are internal to `lib/knowledge`:
 * `validate.ts` needs exactly the same resolution rules, and a second
 * implementation of "where does this link point?" is precisely the kind of
 * drift this boundary cannot survive. Task 6's `index.ts` exports the public
 * surface.
 */

import { lstat, readFile, readdir, realpath, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { toString as mdastToString } from "mdast-util-to-string";
import remarkParse from "remark-parse";
import { unified } from "unified";

import type { Root } from "mdast";

import { INDEX_FILENAME, parseKnowledgePage } from "./parser.js";
import type { MarkdownLink, ParsedKnowledgePage } from "./types.js";

/** The directory of trusted pages, relative to the repository root. */
export const KNOWLEDGE_DIRECTORY = "knowledge";

/** The extension of a knowledge page. Nothing else in the tree is parsed. */
export const PAGE_EXTENSION = ".qmd";

/** `lib/knowledge/graph.ts` → the repository root. */
const DEFAULT_REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..");

/**
 * A URL scheme: `https:`, `mailto:`, `javascript:`, and also `C:` in a Windows
 * path. The parser has already dropped the schemes the site may link to, so
 * anything still carrying one here is not a path into the knowledge tree.
 */
const URL_SCHEME = /^([A-Za-z][A-Za-z0-9+.-]*):/;

/** The start of a URL query or fragment; neither is part of the file name. */
const QUERY_OR_FRAGMENT = /[?#]/;

/**
 * One resolved knowledge tree: pages, curated edges, and referenced files.
 *
 * Every key and every id is a POSIX path relative to `knowledgeRoot`, the same
 * form `ParsedKnowledgePage.id` uses, and every list is in the author's curated
 * order rather than the filesystem's. `childrenByIndex` and `relatedByIndex`
 * hold an entry for each index page, empty when the section lists nothing;
 * `parentByPage` holds the structural owner of each page, so the root index is
 * the one page absent from it.
 */
export interface KnowledgeGraph {
  repoRoot: string;
  knowledgeRoot: string;
  pages: ReadonlyMap<string, ParsedKnowledgePage>;
  childrenByIndex: ReadonlyMap<string, readonly string[]>;
  parentByPage: ReadonlyMap<string, string>;
  relatedByIndex: ReadonlyMap<string, readonly string[]>;
  /** Referenced files that are not pages, for example an embedded diagram. */
  assets: ReadonlyMap<string, string>; // POSIX relative path -> absolute path
}

export interface LoadKnowledgeOptions {
  /** Defaults to the repository this file is installed in. */
  repoRoot?: string;
  /** Defaults to `knowledge`; resolved against `repoRoot`. */
  knowledgeDir?: string;
}

/** Where a link points, once the filesystem has had its say. */
export type TargetResolution =
  | { status: "page"; id: string; absolutePath: string }
  | { status: "asset"; id: string; absolutePath: string }
  | { status: "unresolvable"; reason: UnresolvableReason; detail: string };

/**
 * Why a target is not usable. `validate.ts` maps these to diagnostic codes; the
 * split keeps the resolution rules here and the vocabulary there.
 */
export type UnresolvableReason =
  /** Nothing exists at the target path. */
  | "missing"
  /** Something exists, but it is a directory rather than a file. */
  | "not-a-file"
  /** A `.qmd` file the tree does not own, for example inside a dot directory. */
  | "not-a-page"
  /** An absolute path, a foreign scheme, or a path that leaves the tree. */
  | "outside"
  /** The path is, or passes through, a symbolic link. */
  | "symlink";

/** Everything `resolveTarget` needs; a `KnowledgeGraph` satisfies it. */
export type ResolutionScope = Pick<KnowledgeGraph, "knowledgeRoot" | "pages">;

/** Orders POSIX ids independently of locale, so reports never drift. */
export function comparePosix(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function toPosix(value: string): string {
  return value.split(path.sep).join("/");
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** True for the errors a path that simply is not there produces. */
function isMissingPathError(error: unknown): boolean {
  const code = (error as NodeJS.ErrnoException | null)?.code;
  return code === "ENOENT" || code === "ENOTDIR" || code === "ENAMETOOLONG";
}

/** The path a diagnostic names: repository-relative and POSIX, when possible. */
export function diagnosticFile(repoRoot: string, absolutePath: string): string {
  const relative = path.relative(repoRoot, absolutePath);
  if (relative === "" || relative.startsWith("..") || path.isAbsolute(relative)) {
    return toPosix(absolutePath);
  }
  return toPosix(relative);
}

/**
 * The index that owns a page.
 *
 * A content page belongs to the index of its own directory; a topic index
 * belongs to the index of its parent directory. The root index belongs to
 * nobody, which is what makes containment a tree rather than a ring.
 */
export function parentIdOf(pageId: string): string | undefined {
  const directory = path.posix.dirname(pageId);
  const isIndex = path.posix.basename(pageId) === INDEX_FILENAME;
  if (isIndex && (directory === "." || directory === "" || directory === "/")) {
    return undefined;
  }
  const owner = isIndex ? path.posix.dirname(directory) : directory;
  return owner === "." || owner === "" || owner === "/"
    ? INDEX_FILENAME
    : `${owner}/${INDEX_FILENAME}`;
}

/** The page id of the index of a POSIX directory relative to the root. */
export function indexIdOf(directory: string): string {
  return directory === "" || directory === "."
    ? INDEX_FILENAME
    : `${directory}/${INDEX_FILENAME}`;
}

/**
 * True when the body carries a level-two heading with this text.
 *
 * The reserved sections are a contract, so an index must declare
 * `## Reading map` even when it is still empty — the production scaffold is
 * exactly that page. The parser reports only the *entries* of a section, so the
 * heading itself is read here, with remark and the parser's own rule (a
 * level-two heading whose text is the reserved name) rather than a second,
 * looser regular expression that a fenced code sample could satisfy.
 */
export function hasSection(body: string, heading: string): boolean {
  const tree = unified().use(remarkParse).parse(body) as Root;
  return tree.children.some(
    (child) =>
      child.type === "heading" &&
      child.depth === 2 &&
      mdastToString(child).trim() === heading,
  );
}

/** Percent-decoding, which a malformed escape must not turn into a throw. */
function decodeTarget(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function unresolvable(reason: UnresolvableReason, detail: string): TargetResolution {
  return { status: "unresolvable", reason, detail };
}

/**
 * Resolves one link target written on `fromAbsolutePath`.
 *
 * The order of the checks is the security argument. A foreign scheme and an
 * absolute path are rejected before any filesystem call; a path that leaves the
 * tree lexically is rejected whether or not it exists, so a `../../etc/passwd`
 * link is an escape rather than a typo; and the real path is compared with the
 * lexical one, so a symbolic link anywhere in the chain — final component or
 * parent directory — is caught even though `lstat` silently follows the parents.
 */
export async function resolveTarget(
  scope: ResolutionScope,
  fromAbsolutePath: string,
  target: string,
): Promise<TargetResolution> {
  const trimmed = target.trim();
  if (trimmed.includes("\0")) {
    return unresolvable("outside", "contains a NUL character");
  }

  const scheme = URL_SCHEME.exec(trimmed);
  if (scheme !== null) {
    return unresolvable(
      "outside",
      `is a \`${scheme[1]}:\` URL, not a path inside the knowledge tree`,
    );
  }

  const cut = trimmed.search(QUERY_OR_FRAGMENT);
  const decoded = decodeTarget(cut === -1 ? trimmed : trimmed.slice(0, cut));
  if (decoded === "") {
    // `?query` or `#fragment` alone: the page links to itself.
    const id = toPosix(path.relative(scope.knowledgeRoot, fromAbsolutePath));
    return { status: "page", id, absolutePath: fromAbsolutePath };
  }
  if (decoded.startsWith("/") || path.isAbsolute(decoded)) {
    return unresolvable("outside", "is an absolute path");
  }

  const lexical = path.resolve(path.dirname(fromAbsolutePath), decoded);
  const relative = path.relative(scope.knowledgeRoot, lexical);
  if (relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    return unresolvable("outside", "points outside the knowledge tree");
  }

  let entry;
  try {
    entry = await lstat(lexical);
  } catch (error) {
    if (isMissingPathError(error)) {
      return unresolvable("missing", "does not exist");
    }
    throw error;
  }
  if (entry.isSymbolicLink()) {
    return unresolvable("symlink", "is a symbolic link");
  }

  let real;
  try {
    real = await realpath(lexical);
  } catch (error) {
    if (isMissingPathError(error)) {
      return unresolvable("missing", "does not exist");
    }
    throw error;
  }
  if (real !== lexical) {
    return unresolvable("symlink", "is reached through a symbolic link");
  }
  if (!entry.isFile()) {
    return unresolvable("not-a-file", "is a directory, not a file");
  }

  const id = toPosix(relative);
  if (scope.pages.has(id)) {
    return { status: "page", id, absolutePath: lexical };
  }
  if (id.endsWith(PAGE_EXTENSION)) {
    return unresolvable("not-a-page", "is not a page of the knowledge tree");
  }
  return { status: "asset", id, absolutePath: lexical };
}

/**
 * Resolves every distinct local target of one page, keyed by the target exactly
 * as it was written. Reading-map and related-topic entries appear in
 * `localLinks` too, so one pass covers prose, curation, and assets alike.
 */
export async function resolvePageTargets(
  scope: ResolutionScope,
  page: ParsedKnowledgePage,
): Promise<Map<string, TargetResolution>> {
  const resolutions = new Map<string, TargetResolution>();
  for (const link of page.localLinks) {
    if (resolutions.has(link.target)) {
      continue;
    }
    resolutions.set(link.target, await resolveTarget(scope, page.absolutePath, link.target));
  }
  return resolutions;
}

/** The pages a curated section names, in the author's order, without repeats. */
function curatedPageIds(
  entries: readonly MarkdownLink[],
  resolutions: ReadonlyMap<string, TargetResolution>,
): string[] {
  const ids: string[] = [];
  for (const entry of entries) {
    const resolution = resolutions.get(entry.target);
    if (resolution?.status === "page" && !ids.includes(resolution.id)) {
      ids.push(resolution.id);
    }
  }
  return ids;
}

/**
 * Every page under the root, as sorted POSIX ids.
 *
 * Dot directories are skipped, and symbolic links are never followed: a
 * symlinked directory could otherwise walk the whole filesystem into the graph,
 * or loop forever. A reference *to* one is still reported, by `resolveTarget`,
 * so nothing disappears silently from a page that needs it. `_quarto.yml`,
 * `drafts/`, `literature/`, and generated output are excluded by construction —
 * the first is not a `.qmd`, the rest are not under the knowledge root.
 */
async function discoverPages(knowledgeRoot: string): Promise<string[]> {
  const found: string[] = [];

  const walk = async (directory: string, prefix: string): Promise<void> => {
    const entries = await readdir(directory, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name.startsWith(".") || entry.isSymbolicLink()) {
        continue;
      }
      const id = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
      if (entry.isDirectory()) {
        await walk(path.join(directory, entry.name), id);
      } else if (entry.isFile() && entry.name.endsWith(PAGE_EXTENSION)) {
        found.push(id);
      }
    }
  };

  await walk(knowledgeRoot, "");
  return found.sort(comparePosix);
}

/** Resolves a configured root to its real path, failing loudly if it cannot. */
async function resolveRoot(target: string, label: string): Promise<string> {
  const absolute = path.resolve(target);
  let real: string;
  try {
    real = await realpath(absolute);
  } catch (error) {
    throw new Error(`could not read the ${label} "${absolute}": ${describe(error)}`, {
      cause: error,
    });
  }
  if (!(await stat(real)).isDirectory()) {
    throw new Error(`the ${label} "${absolute}" is not a directory`);
  }
  return real;
}

/**
 * Reads the knowledge tree into a graph.
 *
 * Nothing here rejects content: a tree with a missing index, a broken link, or
 * a page that claims a child in another directory still loads, and every one of
 * those problems is reported by `validateGraph`. Callers that publish or
 * resolve must go through validation first.
 */
export async function loadKnowledge(
  options: LoadKnowledgeOptions = {},
): Promise<KnowledgeGraph> {
  const repoRoot = await resolveRoot(options.repoRoot ?? DEFAULT_REPO_ROOT, "repository root");
  const knowledgeRoot = await resolveRoot(
    path.resolve(repoRoot, options.knowledgeDir ?? KNOWLEDGE_DIRECTORY),
    "knowledge tree",
  );

  const pages = new Map<string, ParsedKnowledgePage>();
  for (const id of await discoverPages(knowledgeRoot)) {
    const absolutePath = path.join(knowledgeRoot, ...id.split("/"));
    pages.set(
      id,
      parseKnowledgePage({
        repoRoot,
        knowledgeRoot,
        absolutePath,
        source: await readFile(absolutePath, "utf8"),
      }),
    );
  }

  const scope: ResolutionScope = { knowledgeRoot, pages };
  const assets = new Map<string, string>();
  const childrenByIndex = new Map<string, readonly string[]>();
  const relatedByIndex = new Map<string, readonly string[]>();

  // `pages` is already in sorted id order, so every map below is too.
  for (const page of pages.values()) {
    const resolutions = await resolvePageTargets(scope, page);
    for (const resolution of resolutions.values()) {
      if (resolution.status === "asset") {
        assets.set(resolution.id, resolution.absolutePath);
      }
    }
    if (page.kind !== "index") {
      continue;
    }
    childrenByIndex.set(page.id, curatedPageIds(page.readingMap, resolutions));
    relatedByIndex.set(page.id, curatedPageIds(page.relatedTopics, resolutions));
  }

  const parentByPage = new Map<string, string>();
  for (const id of pages.keys()) {
    const parent = parentIdOf(id);
    if (parent !== undefined && pages.has(parent)) {
      parentByPage.set(id, parent);
    }
  }

  return {
    repoRoot,
    knowledgeRoot,
    pages,
    childrenByIndex,
    parentByPage,
    relatedByIndex,
    assets,
  };
}
