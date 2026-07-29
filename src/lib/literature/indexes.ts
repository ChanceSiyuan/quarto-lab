/**
 * Generates the committed `literature/<method>/INDEX.md` files from the parsed
 * bibliography.
 *
 * An index is a derived view of `ref.bib` and nothing else:
 *
 * - it carries bibliographic metadata plus links to the external record, never
 *   copied paper text, an abstract, or a local `.raw`/`.figures` artifact;
 * - it contains no timestamp, so re-running the generator on an unchanged
 *   bibliography reproduces the same bytes;
 * - ordering comes from sorted method slugs and sorted citekeys, so the order
 *   of entries inside `ref.bib` cannot leak into the output;
 * - generation never deletes anything. A method directory holding a file the
 *   generator does not own makes the whole run fail before a single write.
 */

import { mkdir, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { SAFE_METHOD_PATTERN, type LiteratureEntry } from "./bibliography.js";

/** Name of the generated, committed index inside a method directory. */
export const METHOD_INDEX_FILENAME = "INDEX.md";

/** Downloaded artifacts. They are gitignored and are left strictly alone. */
const LOCAL_ARTIFACT_DIRECTORIES = new Set([".raw", ".figures"]);

const DOI_RESOLVER = "https://doi.org/";
const ARXIV_ABSTRACT = "https://arxiv.org/abs/";

function compare(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/**
 * Escapes the Markdown-active punctuation of a bibliographic value so a title
 * or a name is rendered as written instead of becoming emphasis, a link, raw
 * HTML, or math.
 */
function escapeInline(value: string): string {
  return value.replace(/[\\`*_[\]<>|&$~^]/g, (character) => `\\${character}`);
}

/** Groups entries by method: sorted methods, each with sorted entries. */
export function entriesByMethod(
  entries: readonly LiteratureEntry[],
): ReadonlyMap<string, readonly LiteratureEntry[]> {
  const groups = new Map<string, LiteratureEntry[]>();
  for (const entry of entries) {
    for (const method of entry.methods) {
      const group = groups.get(method);
      if (group) {
        group.push(entry);
      } else {
        groups.set(method, [entry]);
      }
    }
  }

  const sorted = new Map<string, readonly LiteratureEntry[]>();
  for (const method of [...groups.keys()].sort(compare)) {
    const group = groups.get(method) ?? [];
    sorted.set(
      method,
      [...group].sort((a, b) => compare(a.citekey, b.citekey)),
    );
  }
  return sorted;
}

/** Renders the Markdown index of one method. */
export function renderMethodIndex(
  method: string,
  entries: readonly LiteratureEntry[],
): string {
  if (!SAFE_METHOD_PATTERN.test(method)) {
    throw new Error(`"${method}" is not a usable method keyword`);
  }

  const lines: string[] = [
    `# Literature: ${method}`,
    "",
    "<!-- Generated from literature/ref.bib by `make literature-index`.",
    "     Edit the bibliography, not this file. -->",
    "",
    `${entries.length} bibliography ${entries.length === 1 ? "entry carries" : "entries carry"} the \`${method}\` keyword.`,
    "",
    "This is external evidence, not learned knowledge. Only bibliographic",
    "metadata is reproduced here; follow the links for the published record.",
  ];

  for (const entry of entries) {
    lines.push("", `## ${entry.citekey}`, "");
    lines.push(`- Title: ${escapeInline(entry.title)}`);
    if (entry.authors.length > 0) {
      lines.push(`- Authors: ${entry.authors.map(escapeInline).join(", ")}`);
    }
    if (entry.year !== undefined) {
      lines.push(`- Year: ${entry.year}`);
    }
    lines.push(`- Type: ${entry.type}`);
    lines.push(`- Methods: ${[...entry.methods].join(", ")}`);
    if (entry.doi !== undefined) {
      lines.push(`- DOI: <${DOI_RESOLVER}${entry.doi}>`);
    }
    if (entry.arxiv !== undefined) {
      lines.push(`- arXiv: <${ARXIV_ABSTRACT}${entry.arxiv}>`);
    }
  }

  return `${lines.join("\n")}\n`;
}

/**
 * Fails unless every file in an existing method directory is one this generator
 * owns, so a hand-written note is never overwritten or removed.
 */
async function requireGeneratorOwnedDirectory(
  directory: string,
  method: string,
): Promise<void> {
  let contents;
  try {
    contents = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return;
    }
    throw error;
  }

  const unexpected = contents
    .filter(
      (child) =>
        !(child.name === METHOD_INDEX_FILENAME && child.isFile()) &&
        !(LOCAL_ARTIFACT_DIRECTORIES.has(child.name) && child.isDirectory()),
    )
    .map((child) => child.name)
    .sort(compare);

  if (unexpected.length > 0) {
    throw new Error(
      `refusing to generate "${path.join(directory, METHOD_INDEX_FILENAME)}": the "${method}" directory holds ${unexpected.length} file(s) this command does not own: ${unexpected.join(", ")}`,
    );
  }
}

/**
 * Writes one `INDEX.md` per method keyword under `literatureRoot` and returns
 * the written paths, sorted by method.
 *
 * Every method directory is checked before anything is written, so a refusal
 * leaves the tree exactly as it was.
 */
export async function writeMethodIndexes(
  literatureRoot: string,
  entries: readonly LiteratureEntry[],
): Promise<readonly string[]> {
  const root = path.resolve(literatureRoot);
  const groups = entriesByMethod(entries);

  const planned = [...groups].map(([method, methodEntries]) => ({
    method,
    directory: path.join(root, method),
    content: renderMethodIndex(method, methodEntries),
  }));

  for (const { directory, method } of planned) {
    await requireGeneratorOwnedDirectory(directory, method);
  }

  const written: string[] = [];
  for (const { directory, content } of planned) {
    await mkdir(directory, { recursive: true });
    const file = path.join(directory, METHOD_INDEX_FILENAME);
    await writeFile(file, content, "utf8");
    written.push(file);
  }
  return written;
}
