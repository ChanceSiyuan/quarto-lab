/**
 * The vocabulary of the knowledge system: what a knowledge page is, what may
 * appear in its frontmatter, and how a problem with one is reported.
 *
 * Everything here is data, plus the one predicate that says which frontmatter
 * *values* are safe — the rule two stages have to agree on exactly. The parser
 * (`parser.ts`) turns one `.qmd` file into a `ParsedKnowledgePage`; the graph
 * (`graph.ts`) resolves the relationships between pages. Neither stage throws
 * on bad user content: every problem is a `Diagnostic` with a true one-based
 * file location, so a whole tree can be reported at once instead of one failure
 * per run.
 */

/** The single category a content page must declare. */
export const KNOWLEDGE_CATEGORIES = ["theory", "experiment", "codes"] as const;

export type KnowledgeCategory = (typeof KNOWLEDGE_CATEGORIES)[number];

/**
 * The only frontmatter keys a knowledge page may set.
 *
 * This is a security boundary, not a style rule. A page is rendered by Quarto
 * with the site-level configuration; allowing `execute`, `filters`,
 * `include-*`, `resources`, or `format` here would let the content of a page
 * turn rendering into code execution, inject arbitrary HTML/Lua, or publish
 * files from outside the knowledge tree.
 */
export const ALLOWED_FRONTMATTER_KEYS = [
  "title",
  "description",
  "categories",
  "aliases",
] as const;

export type AllowedFrontmatterKey = (typeof ALLOWED_FRONTMATTER_KEYS)[number];

/**
 * An alias Quarto would turn into a path rather than into a name.
 *
 * The knowledge system means `aliases` as *other names for this page* — "2d
 * ising", "quspin hamiltonian" — and the resolver treats them as text. Quarto
 * means something else by the same key: each alias becomes a redirect page
 * written at that path, relative to the rendered page. Verified against Quarto
 * 1.9.38, `aliases: ["../../../../../../tmp/x"]` makes the renderer call
 * `mkdir` *outside* the output directory, outside the project, and outside the
 * workspace — it failed there only because that particular path was not
 * writable. A separator, a `.`, or a `..` is therefore refused: no legitimate
 * synonym needs one, and every escape does.
 */
const PATH_LIKE_ALIAS = /[/\\]|^\.{1,2}$|^~/u;

/**
 * Whether an alias would become a filesystem path at render time.
 *
 * This lives here, in the module both the validator and the projection already
 * import, because it is one security rule enforced in two places: validation
 * reports it as `ALIAS_PATH_FORBIDDEN` at review time, and the projection
 * refuses it again at build time for a tree that reached a renderer some other
 * way. Two copies of the predicate would be two rules, and they would drift.
 */
export function isPathLikeAlias(alias: string): boolean {
  return PATH_LIKE_ALIAS.test(alias);
}

/** `index.qmd` is topic navigation; every other page carries content. */
export type PageKind = "index" | "content";

/** A one-based location in a file, as an editor and a compiler report it. */
export interface SourceLocation {
  file: string;
  line: number;
  column: number;
}

/** One machine-readable problem found in a page or in the graph. */
export interface Diagnostic {
  code: string;
  message: string;
  location: SourceLocation;
}

/**
 * A Markdown link or image. `target` is the URL exactly as it was written,
 * query and fragment included; resolving it is the graph's job, not the
 * parser's.
 */
export interface MarkdownLink {
  kind: "link" | "image";
  label: string;
  target: string;
  location: SourceLocation;
}

/** One `.qmd` file, parsed into the parts the knowledge graph is built from. */
export interface ParsedKnowledgePage {
  /** POSIX path relative to `knowledge/`, for example `ising/proof.qmd`. */
  id: string;
  absolutePath: string;
  /** The id of the owning index. An index owns itself. */
  topicId: string;
  kind: PageKind;
  title?: string;
  description?: string;
  category?: KnowledgeCategory;
  aliases: readonly string[];
  /** The source after the frontmatter block, unchanged. */
  body: string;
  /**
   * The curated `## Reading map` entries, in the order the author wrote them.
   * These define containment: a page listed here is owned by this index.
   */
  readingMap: readonly MarkdownLink[];
  /**
   * The curated `## Related topics` entries. These are cross-references and
   * change no ownership; they may point across the tree and may form cycles.
   */
  relatedTopics: readonly MarkdownLink[];
  /**
   * The reserved level-two sections the page declares, in document order.
   *
   * A section is declared even when it lists nothing: `## Reading map` with
   * prose under it is how a topic says "nothing has been promoted here yet",
   * which is exactly what the empty production scaffold does. The entries above
   * cannot express that — they are empty in both cases — so the graph reads the
   * declaration from here rather than re-deriving the heading rule from the
   * body, where a fenced code sample showing `## Reading map` would satisfy any
   * cheaper test. Only the first occurrence of a heading is recorded; a second
   * is a `READING_MAP_DUPLICATE`/`RELATED_TOPICS_DUPLICATE` diagnostic.
   */
  reservedSections: readonly { heading: string; location: SourceLocation }[];
  /**
   * Every link and image on the page whose target must resolve inside the
   * knowledge tree, in document order. Reading-map and related-topic entries
   * appear here too, so link checking never has to be repeated per section.
   * HTTP(S), `mailto:`, `zotero:` (sanctioned deep links into the user's
   * Zotero library), and pure `#fragment` targets are excluded; anything
   * else, including a foreign scheme such as `javascript:`, is left for the
   * graph to reject.
   *
   * Reference-style links and images are resolved through their definitions
   * and reported at the reference; a definition nobody references is reported
   * at the definition line. Either way every declared target appears exactly
   * once per use.
   */
  localLinks: readonly MarkdownLink[];
  /** Pandoc citation keys found in Markdown text, one entry per occurrence. */
  citations: readonly { key: string; location: SourceLocation }[];
  /**
   * Raw `<script` tags and inline `on*=` handlers anywhere the renderer would
   * emit them verbatim: raw HTML, lenient tag syntax Pandoc accepts but
   * CommonMark does not, and Pandoc raw blocks (```` ```{=html} ````). Ordinary
   * code blocks and code spans are escaped by the renderer and are exempt.
   */
  unsafeHtml: readonly {
    kind: "script" | "inline-handler";
    location: SourceLocation;
  }[];
  /** Everything wrong with this page. A page is never rejected by throwing. */
  parseDiagnostics: readonly Diagnostic[];
}

/** Everything `parseKnowledgePage` needs; it never touches the filesystem. */
export interface ParseKnowledgePageInput {
  /** Absolute repository root; diagnostics are reported relative to it. */
  repoRoot: string;
  /** Absolute path of the knowledge tree; page ids are relative to it. */
  knowledgeRoot: string;
  /** Absolute path of the page being parsed. */
  absolutePath: string;
  /** The full text of the page, frontmatter included. */
  source: string;
}
