/**
 * Projects one validated `KnowledgeGraph` into a temporary Quarto project.
 *
 * Everything Quarto renders, it renders from a directory this module built, in
 * a temporary workspace that holds nothing else. That is the whole security
 * argument of the published site: a file that is not copied here cannot be
 * published, cannot be read by a shortcode, and cannot be reached by a relative
 * link, however the source page is written.
 *
 * Four rules follow from it:
 *
 * - **copy pages, generate chrome.** Pages and referenced assets arrive
 *   byte-for-byte; nothing rewrites a link or normalizes a page on the way in.
 *   The only files this module *writes* are the generated `_quarto.yml`, the
 *   Research Loop stylesheet, and the three category views, and none of them
 *   ever lands in `knowledge/`;
 * - **re-assert the schema, never trust it.** The committed base `_quarto.yml`
 *   is parsed and compared with the fixed safe schema exactly. A filter, an
 *   include, a resource glob, an extension, a render hook, or an execution
 *   override anywhere in that file stops the projection — and the file that is
 *   handed to Quarto is *generated* from the schema rather than copied, so the
 *   render cannot inherit a key nobody checked;
 * - **order comes from curation.** The sidebar is the reading maps and nothing
 *   else; a category view lists its pages in curated reading order, then POSIX
 *   path. No enumeration order reaches the output, so the same graph always
 *   produces byte-identical files;
 * - **a title is data, never syntax.** Titles and descriptions are author text
 *   that may carry `]`, `:`, quotes, and newlines. They are emitted through a
 *   YAML serializer and, in Markdown, through an escaper — never concatenated.
 *
 * The one thing validation cannot see is a Quarto shortcode: the parser models
 * links and images, and `{{< include ../../secret.qmd >}}` is neither. A
 * shortcode expands *after* validation has run and *before* `--no-execute` can
 * stop anything, which is exactly the gap between the two locks. Verified
 * against Quarto 1.9.38, `include` reads and publishes a file outside the
 * project directory and `env` publishes a build-host environment variable into
 * the site; `embed` reads a notebook, `meta`/`var` publish project metadata,
 * and `contents`/`video`/`kbd`/`pagebreak` merely emit markup today.
 *
 * So the gate is an allowlist of shortcodes known to read nothing, and that
 * allowlist is **empty**: the projection refuses every page carrying a
 * shortcode of any name, including one shown inside a fenced example. A
 * denylist is how `env` was missed — it named the dangerous shortcodes of the
 * day, and Quarto is free to ship another one. Admitting a shortcode is a
 * deliberate one-line change to `ALLOWED_SHORTCODES` with a reason next to it;
 * the knowledge tree needs none today.
 */

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { parse, stringify } from "yaml";

import { UNCURATED, comparePosix, curatedOrder, type KnowledgeGraph } from "./graph.js";
import { INDEX_FILENAME } from "./parser.js";
import {
  KNOWLEDGE_CATEGORIES,
  isPathLikeAlias,
  type KnowledgeCategory,
  type ParsedKnowledgePage,
} from "./types.js";

/** The base configuration a knowledge tree commits, next to its pages. */
export const BASE_CONFIG_FILENAME = "_quarto.yml";

/** Where the projection puts the project it builds inside the workspace. */
const PROJECT_DIRECTORY = "project";

/** Quarto's own default, named here because the site build renames it. */
const OUTPUT_DIRECTORY = "_site";

/** The generated directory holding the three category views. */
const CATEGORY_DIRECTORY = "categories";

/** The project-relative path of the bibliography copy. */
const BIBLIOGRAPHY_TARGET = "references/ref.bib";

/** The generated stylesheet that makes Quarto read as part of Research Loop. */
const THEME_CSS_FILENAME = "research-loop.css";

/**
 * Directories the projection writes into. A trusted page may not live under
 * either of them: the generated file would silently win, so a topic that took
 * one of these names would publish navigation instead of its own content.
 */
const RESERVED_DIRECTORIES = [CATEGORY_DIRECTORY, "references"] as const;

/** Files the projection writes at the project root. */
const RESERVED_FILES = [THEME_CSS_FILENAME] as const;

const RESEARCH_LOOP_STYLESHEET = String.raw`:root {
  --rl-ink: #17211d;
  --rl-muted: #65716c;
  --rl-paper: #f3f0e8;
  --rl-surface: #fbfaf6;
  --rl-soft: #f7f5ef;
  --rl-line: #d9d7ce;
  --rl-green: #174c3b;
  --rl-lime: #c8f06f;
  --rl-focus: #79a72f;
  --bs-body-bg: var(--rl-paper);
  --bs-body-color: var(--rl-ink);
  --bs-link-color: var(--rl-green);
  --bs-link-hover-color: #0f3529;
  --bs-border-color: var(--rl-line);
}

html,
body,
#quarto-content {
  background: var(--rl-paper);
  color: var(--rl-ink);
}

body {
  font-family: "Geist", Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

a {
  color: var(--rl-green);
  text-decoration-thickness: 1px;
  text-underline-offset: 0.18em;
}

a:hover {
  color: #0f3529;
}

:focus-visible {
  outline: 3px solid var(--rl-focus);
  outline-offset: 3px;
}

#quarto-header .quarto-secondary-nav,
#quarto-header .navbar {
  min-height: 68px;
  border-bottom: 1px solid var(--rl-line);
  background: var(--rl-surface);
  box-shadow: none;
}

#quarto-header .container-fluid {
  min-height: 68px;
  padding: 10px max(24px, calc((100vw - 1280px) / 2));
}

#quarto-header .quarto-page-breadcrumbs {
  color: var(--rl-muted);
  font-size: 11px;
}

#quarto-header .quarto-btn-toggle,
#quarto-header .quarto-search-button {
  min-height: 32px;
  border: 1px solid var(--rl-line);
  border-radius: 0;
  background: var(--rl-soft);
  color: var(--rl-green);
  box-shadow: none;
}

#quarto-header .quarto-btn-toggle:hover,
#quarto-header .quarto-search-button:hover {
  border-color: var(--rl-green);
  background: #edf0e8;
}

#quarto-header .rl-home-link,
#quarto-sidebar .rl-home-link {
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--rl-line);
  background: var(--rl-soft);
  color: var(--rl-green);
  padding: 0 11px;
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}

#quarto-header .rl-home-link:hover,
#quarto-sidebar .rl-home-link:hover {
  border-color: var(--rl-green);
  background: #edf0e8;
  color: var(--rl-green);
}

#quarto-sidebar .rl-home-link {
  width: fit-content;
  letter-spacing: 0;
}

#quarto-header .navbar-brand {
  display: inline-flex;
  align-items: center;
  gap: 11px;
  color: var(--rl-ink);
  font-weight: 650;
  letter-spacing: -0.02em;
}

#quarto-header .navbar-brand::before {
  width: 34px;
  height: 34px;
  display: inline-grid;
  place-items: center;
  border-radius: 50%;
  background: var(--rl-ink);
  color: var(--rl-lime);
  content: "RL";
  font: 700 11px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

#quarto-header .navbar-title {
  color: var(--rl-ink);
  font-size: 14px;
}

#quarto-header .navbar-nav .nav-link {
  color: var(--rl-muted);
  font-size: 12px;
  font-weight: 600;
}

#quarto-header .navbar-nav .nav-link:hover,
#quarto-header .navbar-nav .nav-link.active {
  color: var(--rl-green);
}

#quarto-search .aa-DetachedSearchButton {
  min-height: 32px;
  border: 1px solid var(--rl-line);
  border-radius: 0;
  background: var(--rl-soft);
  color: var(--rl-green);
  box-shadow: none;
}

#quarto-search .aa-DetachedSearchButton:hover {
  border-color: var(--rl-green);
  background: #edf0e8;
}

#quarto-sidebar {
  border-right: 1px solid var(--rl-line);
  background: var(--rl-paper);
}

#quarto-sidebar .sidebar-title {
  display: grid;
  gap: 10px;
  color: var(--rl-ink);
  font-size: 14px;
  font-weight: 650;
  letter-spacing: -0.02em;
}

#quarto-sidebar .sidebar-title > a {
  display: inline-flex;
  align-items: center;
  gap: 11px;
  color: var(--rl-ink);
}

#quarto-sidebar .sidebar-title > a::before {
  width: 34px;
  height: 34px;
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  background: var(--rl-ink);
  color: var(--rl-lime);
  content: "RL";
  font: 700 11px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

#quarto-sidebar .sidebar-item-text,
#quarto-sidebar .sidebar-item-toggle {
  color: var(--rl-muted);
}

#quarto-sidebar .sidebar-item-container:hover,
#quarto-sidebar .sidebar-item-container .active {
  background: #edf0e8;
  color: var(--rl-green);
}

#quarto-margin-sidebar {
  border-left: 1px solid var(--rl-line);
}

#TOC {
  color: var(--rl-muted);
  font-size: 12px;
}

#TOC .active {
  border-left-color: var(--rl-green);
  color: var(--rl-green);
}

main.content {
  padding-top: 34px;
}

#quarto-document-content {
  border: 1px solid var(--rl-line);
  background: var(--rl-surface);
  padding: clamp(22px, 4vw, 46px);
}

.quarto-title,
#title-block-header {
  margin-bottom: 22px;
}

.quarto-title h1.title,
h1.title {
  color: var(--rl-ink);
  font-size: clamp(32px, 5vw, 54px);
  font-weight: 600;
  letter-spacing: -0.055em;
  line-height: 1;
}

.description,
.abstract,
.subtitle,
.quarto-title-meta,
.quarto-title-meta-contents {
  color: var(--rl-muted);
}

h2,
h3,
h4 {
  color: var(--rl-ink);
  letter-spacing: -0.025em;
}

code:not(pre code) {
  border: 1px solid var(--rl-line);
  border-radius: 0;
  background: var(--rl-soft);
  color: var(--rl-green);
  padding: 0.08rem 0.22rem;
}

pre,
div.sourceCode {
  border: 1px solid var(--rl-line);
  border-radius: 0;
  background: #f7f5ef;
}

blockquote {
  border-left: 3px solid var(--rl-green);
  color: var(--rl-muted);
}

table {
  border-color: var(--rl-line);
}

thead,
th {
  background: #f7f5ef;
}

.callout {
  border-radius: 0;
  border-color: var(--rl-line);
  background: var(--rl-surface);
}

.breadcrumb,
.quarto-page-breadcrumbs {
  color: var(--rl-muted);
  font-size: 12px;
}

@media (max-width: 991.98px) {
  #quarto-document-content {
    border-left: 0;
    border-right: 0;
    padding: 22px;
  }

  #quarto-sidebar {
    background: var(--rl-surface);
  }
}
`;

/**
 * The exact contents the committed base configuration must have.
 *
 * This is a security schema, not a default: `_quarto.yml` sits inside the
 * trusted tree, so it is reviewed like any other trusted file, and anything
 * beyond these keys — `filters`, `include-*`, `resources`, `extensions`,
 * `pre-render`, `metadata-files`, `execute.enabled: true` — would turn a render
 * into code execution or into file disclosure. The projection compares rather
 * than merges, and then emits its own file from these values.
 */
const FIXED_BASE_CONFIG = {
  project: { type: "website" },
  website: {
    title: "Research Loop Knowledge",
    "site-path": "/knowledge/",
    search: true,
  },
  format: { html: { toc: true, css: THEME_CSS_FILENAME } },
  execute: { enabled: false },
} as const;

/** The human-readable name of each category view. */
const CATEGORY_TITLE: Readonly<Record<KnowledgeCategory, string>> = {
  theory: "Theory",
  experiment: "Experiment",
  codes: "Codes",
};

/**
 * The opener of a Quarto shortcode, and whatever name follows it.
 *
 * Matching `{{<` rather than a list of names is the whole point: the rule this
 * replaces enumerated `include` and `embed`, and `{{< env SECRET >}}` — which
 * publishes a build-host environment variable — walked straight through it. The
 * name is captured only so that a refusal can say which shortcode it saw; a
 * nameless or misspelt `{{<` matches too, and is refused just the same.
 */
const SHORTCODE = /\{\{<\s*(\/?[^\s>}]*)/gu;

/**
 * The shortcodes a knowledge page may carry — deliberately none.
 *
 * Quarto's built-ins split three ways and only the third is even arguably
 * admissible: `include`/`embed` read the filesystem, `env` reads the build
 * process's environment, `meta`/`var` read project metadata, and
 * `pagebreak`/`kbd`/`contents`/`video`/`lipsum` emit markup from their own
 * arguments. Nothing in the knowledge tree needs the third group, and every
 * page in it is Markdown a human reviewed, so the cost of refusing all of them
 * is zero and the cost of guessing wrong once is a published secret. Adding a
 * name here later is a one-line change that has to be argued for; leaving a
 * name out of a denylist is a change nobody makes.
 */
const ALLOWED_SHORTCODES: ReadonlySet<string> = new Set<string>();

/** One materialized project: where it is, where it renders to, and its views. */
export interface QuartoProject {
  projectDir: string;
  outputDir: string;
  categoryUrls: Readonly<Record<KnowledgeCategory, string>>;
}

/** Thrown when a graph or its base configuration may not be projected. */
export class QuartoProjectionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "QuartoProjectionError";
  }
}

/** One entry of the generated sidebar. */
type SidebarEntry =
  | { text: string; href: string }
  | { section: string; href: string; contents: SidebarEntry[] }
  | { section: string; contents: SidebarEntry[] };

function isMapping(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Every way `actual` differs from `expected`, as `path: what is wrong` lines.
 *
 * Both directions are reported: a missing key is as unsafe as an extra one,
 * because the projection re-emits the schema and a base file that no longer
 * says `execute.enabled: false` is a file nobody is reading any more. A
 * non-mapping is compared against an empty one so that an empty or malformed
 * configuration names the keys it lacks rather than failing with one word.
 */
function differences(expected: unknown, actual: unknown, at: string): string[] {
  if (!isMapping(expected)) {
    return expected === actual
      ? []
      : [`\`${at}\` must be ${JSON.stringify(expected)}, not ${JSON.stringify(actual)}`];
  }

  const found = isMapping(actual) ? actual : {};
  const problems: string[] = [];
  if (!isMapping(actual)) {
    problems.push(
      at === ""
        ? "the file is not a YAML mapping"
        : `\`${at}\` must be a mapping, not ${JSON.stringify(actual)}`,
    );
  }
  for (const key of [...new Set([...Object.keys(expected), ...Object.keys(found)])].sort(
    comparePosix,
  )) {
    const where = at === "" ? key : `${at}.${key}`;
    if (!(key in found)) {
      problems.push(`\`${where}\` is missing`);
    } else if (!(key in expected)) {
      problems.push(`\`${where}\` is not part of the fixed base configuration`);
    } else {
      problems.push(...differences(expected[key], found[key], where));
    }
  }
  return problems;
}

/**
 * Reads the committed base configuration and requires it to be the fixed safe
 * schema, exactly. It is never merged into the generated file; it is checked,
 * and then the generated file is built from `FIXED_BASE_CONFIG`.
 */
async function assertSafeBaseConfig(knowledgeRoot: string): Promise<void> {
  const file = path.join(knowledgeRoot, BASE_CONFIG_FILENAME);
  let text: string;
  try {
    text = await readFile(file, "utf8");
  } catch (error) {
    throw new QuartoProjectionError(
      `the knowledge tree has no readable \`${BASE_CONFIG_FILENAME}\` at "${file}": ${
        error instanceof Error ? error.message : String(error)
      }`,
    );
  }

  let parsed: unknown;
  try {
    parsed = parse(text, { uniqueKeys: true });
  } catch (error) {
    throw new QuartoProjectionError(
      `"${file}" is not valid YAML: ${error instanceof Error ? error.message : String(error)}`,
    );
  }

  const problems = differences(FIXED_BASE_CONFIG, parsed, "");
  if (problems.length > 0) {
    throw new QuartoProjectionError(
      [
        `"${file}" is not the fixed safe Quarto base configuration (${problems.length} problem${
          problems.length === 1 ? "" : "s"
        }):`,
        ...problems.map((problem) => `  ${problem}`),
        "the knowledge site is rendered from a generated copy of this schema; it may not gain filters, includes, resources, extensions, render hooks, or execution settings",
      ].join("\n"),
    );
  }
}

/** The line a match sits on, one-based, for an actionable refusal. */
function lineOf(source: string, index: number): number {
  let line = 1;
  for (let position = 0; position < index; position += 1) {
    if (source[position] === "\n") {
      line += 1;
    }
  }
  return line;
}

/**
 * Refuses a page that carries a Quarto shortcode.
 *
 * The whole source is scanned, frontmatter included: Quarto expands shortcodes
 * in metadata as well as in the body. This is deliberately fail-closed — a
 * fenced code block showing `{{< include … >}}` is refused too, and so is the
 * escaped `{{{< … >}}}` form — because the alternative is deciding, per
 * shortcode and per Quarto release, whether this one happens to read a file, an
 * environment variable, or the project's metadata.
 */
function assertNoShortcode(id: string, source: string): void {
  for (const match of source.matchAll(SHORTCODE)) {
    const name = (match[1] ?? "").toLowerCase();
    if (ALLOWED_SHORTCODES.has(name)) {
      continue;
    }
    throw new QuartoProjectionError(
      `\`${id}\` line ${lineOf(source, match.index)}: a knowledge page may not use ${
        name === "" ? "a Quarto shortcode" : `the \`${name}\` Quarto shortcode`
      }; shortcodes expand after validation has read the page and are unaffected by \`--no-execute\`, so what one publishes — a file from the filesystem (\`include\`, \`embed\`), a build-host environment variable (\`env\`), or project metadata (\`meta\`, \`var\`) — is never anything the projection could check`,
    );
  }
}

/**
 * Refuses a page whose aliases Quarto would read as paths.
 *
 * The frontmatter allowlist admits `aliases` because the resolver needs
 * synonyms; it cannot know that the renderer also builds a directory out of
 * each one. This is the same class of problem as the shortcode above — a
 * validated value that becomes a filesystem path at render time.
 *
 * Validation reports the same values as `ALIAS_PATH_FORBIDDEN`, so an author
 * hears about them at review time; both stages ask `isPathLikeAlias`, and this
 * one stays because the projection may never assume it was reached through a
 * validated path.
 */
function assertSafeAliases(page: ParsedKnowledgePage): void {
  for (const alias of page.aliases) {
    if (isPathLikeAlias(alias)) {
      throw new QuartoProjectionError(
        `\`${page.id}\`: the alias ${JSON.stringify(alias)} looks like a path; Quarto publishes every alias as a redirect directory of that name, so an alias may only be another name for the page — no \`/\`, \`\\\`, \`.\`, \`..\`, or \`~\``,
      );
    }
  }
}

/** Refuses an id that would collide with generated project chrome. */
function assertNotReserved(id: string, what: string): void {
  if ((RESERVED_FILES as readonly string[]).includes(id)) {
    throw new QuartoProjectionError(
      `\`${id}\` is ${what} with a generated file name; rename it so that generated site chrome cannot overwrite trusted content`,
    );
  }
  const [first] = id.split("/");
  if ((RESERVED_DIRECTORIES as readonly string[]).includes(first)) {
    throw new QuartoProjectionError(
      `\`${id}\` is ${what} under \`${first}/\`, which the projection generates; rename the directory so that generated navigation cannot overwrite trusted content`,
    );
  }
}

/** Writes one file inside the project, creating the directories it needs. */
async function writeInto(
  projectDir: string,
  relativePosixPath: string,
  contents: Buffer | string,
): Promise<void> {
  const target = path.join(projectDir, ...relativePosixPath.split("/"));
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, contents);
}

/** The title a page carries, or its id when it carries none. */
function titleOf(page: ParsedKnowledgePage | undefined, id: string): string {
  return page?.title ?? id;
}

/**
 * The sidebar entries for one curated list of pages, depth first.
 *
 * `seen` is both the cycle guard — containment cycles are rejected by
 * validation, but the pure layer must still terminate — and the guarantee that
 * a page claimed by two reading maps appears once, under the first that claims
 * it.
 */
function sidebarEntries(
  graph: KnowledgeGraph,
  ids: readonly string[],
  seen: Set<string>,
): SidebarEntry[] {
  const entries: SidebarEntry[] = [];
  for (const id of ids) {
    if (seen.has(id)) {
      continue;
    }
    seen.add(id);
    const text = titleOf(graph.pages.get(id), id);
    const contents = sidebarEntries(graph, graph.childrenByIndex.get(id) ?? [], seen);
    entries.push(
      contents.length === 0 ? { text, href: id } : { section: text, href: id, contents },
    );
  }
  return entries;
}

/** The whole sidebar: the curated tree, then the three generated views. */
function sidebarContents(graph: KnowledgeGraph): SidebarEntry[] {
  const contents: SidebarEntry[] = [];
  const seen = new Set<string>();
  if (graph.pages.has(INDEX_FILENAME)) {
    seen.add(INDEX_FILENAME);
    contents.push({
      text: titleOf(graph.pages.get(INDEX_FILENAME), INDEX_FILENAME),
      href: INDEX_FILENAME,
    });
    contents.push(
      ...sidebarEntries(graph, graph.childrenByIndex.get(INDEX_FILENAME) ?? [], seen),
    );
  }
  contents.push({
    section: "Categories",
    contents: KNOWLEDGE_CATEGORIES.map((category) => ({
      text: CATEGORY_TITLE[category],
      href: categoryPageId(category),
    })),
  });
  return contents;
}

/** The project-relative id of one generated category view. */
function categoryPageId(category: KnowledgeCategory): string {
  return `${CATEGORY_DIRECTORY}/${category}/${INDEX_FILENAME}`;
}

/**
 * One line of Markdown text made out of author text.
 *
 * Whitespace collapses, so a newline in a title cannot end a list item; and
 * every character that could close a link label, open emphasis, or start raw
 * HTML is backslash-escaped, which Pandoc and CommonMark both accept for ASCII
 * punctuation.
 */
function markdownText(value: string): string {
  return value
    .replace(/\s+/gu, " ")
    .trim()
    .replace(/[\\`*_[\]<>]/gu, (character) => `\\${character}`);
}

/**
 * A page id as a link destination, relative to a generated category view.
 *
 * Unreserved path characters pass through unchanged — the ordinary case, where
 * the destination is exactly the id — and everything else is percent-encoded,
 * so a space or a parenthesis in a file name cannot end the destination early.
 */
function markdownTarget(id: string): string {
  const encoded = id.replace(/[^A-Za-z0-9\-._~/]/gu, (character) =>
    [...new TextEncoder().encode(character)]
      .map((byte) => `%${byte.toString(16).toUpperCase().padStart(2, "0")}`)
      .join(""),
  );
  return `../../${encoded}`;
}

/** The source of one generated category view. */
function categoryPage(
  category: KnowledgeCategory,
  pages: readonly ParsedKnowledgePage[],
): string {
  const description = `Every trusted knowledge page filed under the ${category} category.`;
  return [
    "---",
    stringify({ title: CATEGORY_TITLE[category], description }, { lineWidth: 0 }).trimEnd(),
    "---",
    "",
    pages.length === 0
      ? `No trusted knowledge page is filed under \`${category}\` yet.`
      : `Every trusted knowledge page filed under \`${category}\`, in curated reading order.`,
    "",
    ...pages.map((page) => {
      const link = `- [${markdownText(titleOf(page, page.id))}](${markdownTarget(page.id)})`;
      return page.description === undefined
        ? link
        : `${link} — ${markdownText(page.description)}`;
    }),
    "",
  ].join("\n");
}

/**
 * Projects a graph into a Quarto project under `workspace`.
 *
 * The graph must already have passed validation: this module copies what it is
 * given and does not judge content. The workspace must be a directory the
 * caller owns and will remove.
 */
export async function materializeQuartoProject(input: {
  graph: KnowledgeGraph;
  workspace: string;
  bibliographyPath: string;
}): Promise<QuartoProject> {
  const { graph, bibliographyPath } = input;
  const projectDir = path.join(input.workspace, PROJECT_DIRECTORY);

  await assertSafeBaseConfig(graph.knowledgeRoot);

  // 1. The trusted pages, byte-for-byte, after the one check validation cannot
  // make. Reading the bytes once serves both the scan and the copy, so what is
  // scanned is exactly what is written.
  await mkdir(projectDir, { recursive: true });
  for (const [id, page] of graph.pages) {
    assertNotReserved(id, "a knowledge page");
    assertSafeAliases(page);
    const bytes = await readFile(page.absolutePath);
    assertNoShortcode(id, bytes.toString("utf8"));
    await writeInto(projectDir, id, bytes);
  }

  // 2. The assets those pages reference, and nothing else in the tree.
  for (const [id, absolutePath] of graph.assets) {
    assertNotReserved(id, "an asset");
    await writeInto(projectDir, id, await readFile(absolutePath));
  }

  // 3. The bibliography, copied in rather than referenced outside: the render
  // must not depend on a path that leaves the workspace.
  await writeInto(projectDir, BIBLIOGRAPHY_TARGET, await readFile(bibliographyPath));

  // 4. The code-owned stylesheet that makes the Quarto site share the
  // dashboard skin without letting the content tree control page chrome.
  await writeInto(projectDir, THEME_CSS_FILENAME, RESEARCH_LOOP_STYLESHEET);

  // 5. The three category views, in curated reading order then POSIX path.
  const order = curatedOrder(graph);
  const rankOf = (id: string): number => order.get(id) ?? UNCURATED;
  for (const category of KNOWLEDGE_CATEGORIES) {
    const pages = [...graph.pages.values()]
      .filter((page) => page.category === category)
      .sort((left, right) => rankOf(left.id) - rankOf(right.id) || comparePosix(left.id, right.id));
    await writeInto(projectDir, categoryPageId(category), categoryPage(category, pages));
  }

  // 6. The configuration, generated from the fixed schema plus the graph.
  const sitePath = FIXED_BASE_CONFIG.website["site-path"];
  await writeInto(
    projectDir,
    BASE_CONFIG_FILENAME,
    stringify(
      {
        project: { type: FIXED_BASE_CONFIG.project.type, "output-dir": OUTPUT_DIRECTORY },
        website: { ...FIXED_BASE_CONFIG.website, sidebar: { contents: sidebarContents(graph) } },
        format: FIXED_BASE_CONFIG.format,
        execute: FIXED_BASE_CONFIG.execute,
        bibliography: BIBLIOGRAPHY_TARGET,
      },
      { lineWidth: 0 },
    ),
  );

  return {
    projectDir,
    outputDir: path.join(projectDir, OUTPUT_DIRECTORY),
    categoryUrls: Object.fromEntries(
      KNOWLEDGE_CATEGORIES.map((category) => [
        category,
        `${sitePath}${CATEGORY_DIRECTORY}/${category}/`,
      ]),
    ) as Record<KnowledgeCategory, string>,
  };
}
