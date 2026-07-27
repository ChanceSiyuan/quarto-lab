/**
 * Parses one Quarto knowledge page (`.qmd`) into typed data.
 *
 * The parser is deliberately dumb about the world: it never reads the
 * filesystem and never resolves a link. It answers "what does this file say?"
 * so that `graph.ts` can answer "do these files agree?".
 *
 * Three properties matter to everything built on top of it:
 *
 * - it never throws on user content. A page with ten problems yields ten
 *   diagnostics, so one bad page cannot hide the rest of the tree;
 * - every location is a true one-based location in the file on disk. Markdown
 *   positions are offset by the frontmatter, so an editor jumps to the right
 *   line;
 * - frontmatter keys are an allowlist. A page may set `title`, `description`,
 *   `categories`, and `aliases` and nothing else, so page content can never
 *   turn rendering into execution or inject filters, includes, or resources.
 *   The allowlist covers the whole file, not just its first block: a second
 *   YAML metadata block further down is reported as well.
 *
 * Where the renderer is more permissive than CommonMark — lenient HTML tags,
 * Pandoc raw blocks, mid-document metadata — this parser follows the renderer,
 * not remark. Anything Quarto would put on the page is something the graph
 * must be able to see. Where the two cannot be reconciled at all — a fence that
 * never closes is code to remark and ordinary Markdown to Pandoc, so the two
 * disagree about what the page *says* — the page is failed closed with
 * `FENCE_UNCLOSED` rather than validated against a body Quarto will not render.
 */

import path from "node:path";

import { toString as mdastToString } from "mdast-util-to-string";
import remarkParse from "remark-parse";
import { unified } from "unified";
import { visit } from "unist-util-visit";
import { isMap, isScalar, isSeq, parseDocument, type Node as YamlNode } from "yaml";

import type { Definition, Root } from "mdast";

import {
  ALLOWED_FRONTMATTER_KEYS,
  KNOWLEDGE_CATEGORIES,
  type Diagnostic,
  type KnowledgeCategory,
  type MarkdownLink,
  type PageKind,
  type ParseKnowledgePageInput,
  type ParsedKnowledgePage,
  type SourceLocation,
} from "./types.js";

/** The file that makes a directory a topic and carries its curated map. */
export const INDEX_FILENAME = "index.qmd";

/** The level-two heading that defines containment and reading order. */
export const READING_MAP_HEADING = "Reading map";

/** The level-two heading that defines cross-topic references. */
export const RELATED_TOPICS_HEADING = "Related topics";

/** The line that opens a frontmatter block, and one of the two that close it. */
const FRONTMATTER_DELIMITER = "---";

/** The other closing delimiter Pandoc accepts. */
const FRONTMATTER_TERMINATOR = "...";

/** Link targets the knowledge tree does not own and never resolves on disk. */
const EXTERNAL_TARGET = /^(?:https?|mailto):/i;

/**
 * A Pandoc citation key: `@` then a letter, digit, or `_`, then alphanumerics
 * and internal punctuation. Trailing punctuation is trimmed afterwards, so
 * `[@key].` and `@key,` both yield `key`.
 */
const CITATION_KEY = /@[A-Za-z0-9_][A-Za-z0-9_:.#$%&+?<>~/-]*/g;

/**
 * What may sit immediately before a citation. Requiring one of these is what
 * separates `[@key]` from the `@` of `user@example.com` or
 * `https://example.com/@handle`; `-` allows Pandoc's `[-@key]`.
 */
const CITATION_PREFIX = /[\s[;({,-]/;

/** A `<script` start tag in raw HTML. `</script>` is not matched again. */
const HTML_SCRIPT_TAG = /<script\b/gi;

/**
 * An inline event handler attribute (`onclick=`).
 *
 * The lookbehind rejects only characters that could continue an attribute
 * name, so every delimiter HTML actually allows before an attribute counts:
 * whitespace, `/` (`<svg/onload=1>`), and a closing quote
 * (`<div id="a"onclick=1>`). Requiring whitespace here — as an earlier version
 * did — misses exactly the canonical evasions.
 */
const HTML_EVENT_HANDLER = /(?<![A-Za-z0-9_.:-])on[a-z][a-z0-9_.:-]*\s*=/gi;

/** The first character of an HTML tag name. */
const HTML_TAG_NAME_START = /[a-zA-Z]/;

/** A later character of an HTML tag name. */
const HTML_TAG_NAME_PART = /[a-zA-Z0-9-]/;

/**
 * Element names Pandoc's HTML reader recognises, which is what decides whether
 * a tag may contain a blank line.
 *
 * Measured, not assumed: `<div⏎⏎onclick=…>`, and the same with `span`, `svg`,
 * `table`, `section`, and `p`, all render a live handler, while `<my-widget⏎⏎…>`
 * and prose openers such as `<x …` do not. Keeping the list is what lets the
 * scan span blank lines for real elements without dragging two paragraphs of
 * physics prose into an imaginary tag.
 */
const HTML_ELEMENT_NAMES = new Set([
  // HTML
  "a", "abbr", "address", "area", "article", "aside", "audio", "b", "base",
  "bdi", "bdo", "blockquote", "body", "br", "button", "canvas", "caption",
  "cite", "code", "col", "colgroup", "data", "datalist", "dd", "del",
  "details", "dfn", "dialog", "div", "dl", "dt", "em", "embed", "fieldset",
  "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
  "h6", "head", "header", "hgroup", "hr", "html", "i", "iframe", "img",
  "input", "ins", "kbd", "label", "legend", "li", "link", "main", "map",
  "mark", "menu", "meta", "meter", "nav", "noscript", "object", "ol",
  "optgroup", "option", "output", "p", "param", "picture", "pre", "progress",
  "q", "rp", "rt", "ruby", "s", "samp", "script", "search", "section",
  "select", "slot", "small", "source", "span", "strong", "style", "sub",
  "summary", "sup", "table", "tbody", "td", "template", "textarea", "tfoot",
  "th", "thead", "time", "title", "tr", "track", "u", "ul", "var", "video",
  "wbr",
  // Obsolete, still parsed by lenient readers
  "applet", "basefont", "big", "center", "dir", "font", "frame", "frameset",
  "isindex", "keygen", "listing", "marquee", "nobr", "noframes", "plaintext",
  "strike", "tt", "xmp",
  // SVG and MathML: the classic handler carriers
  "animate", "animatetransform", "circle", "defs", "ellipse", "filter",
  "foreignobject", "g", "image", "line", "marker", "mask", "math", "mi",
  "mn", "mo", "ms", "mtext", "path", "pattern", "polygon", "polyline",
  "rect", "set", "svg", "symbol", "text", "tspan", "use",
]);

/**
 * A Pandoc raw attribute: ```` ```{=html} ```` on a fence, or `` `…`{=html} ``
 * after a code span. Pandoc copies the contents of such a block verbatim into
 * the output, so it is raw HTML wearing a code node's clothes.
 *
 * Every raw format is treated as raw output, not just `{=html}`. Only `html`
 * reaches this site's renderer today, but a raw block is by definition content
 * the author wrote to bypass Markdown, and the tag-shaped gate below keeps the
 * cost of scanning a `{=latex}` block at essentially zero.
 */
const RAW_ATTRIBUTE = /^\{=[A-Za-z0-9_-]+\}/;

type Citation = ParsedKnowledgePage["citations"][number];
type UnsafeHtml = ParsedKnowledgePage["unsafeHtml"][number];
type ReservedSectionRecord = ParsedKnowledgePage["reservedSections"][number];

/** Turns a native path into the POSIX form every id and diagnostic uses. */
function toPosix(value: string): string {
  return value.split(path.sep).join("/");
}

/** Byte-order marks are invisible; they must not hide the frontmatter. */
function stripBom(source: string): string {
  return source.startsWith("﻿") ? source.slice(1) : source;
}

/** The offset of the first character of every line. */
function lineStarts(text: string): number[] {
  const starts = [0];
  for (let index = 0; index < text.length; index += 1) {
    if (text[index] === "\n") {
      starts.push(index + 1);
    }
  }
  return starts;
}

/** Converts a character offset into a one-based line and column. */
function offsetToLineColumn(
  starts: readonly number[],
  offset: number,
): { line: number; column: number } {
  let low = 0;
  let high = starts.length - 1;
  while (low < high) {
    const middle = (low + high + 1) >> 1;
    if ((starts[middle] ?? 0) <= offset) {
      low = middle;
    } else {
      high = middle - 1;
    }
  }
  return { line: low + 1, column: offset - (starts[low] ?? 0) + 1 };
}

/** The frontmatter block and the body, with the source line each starts on. */
interface SourceSplit {
  /** The text between the delimiters; absent when there is no usable block. */
  frontmatter?: string;
  /** One-based source line of the first frontmatter line. */
  frontmatterLine: number;
  /** True when the block opens on line one but is never closed. */
  unterminated: boolean;
  body: string;
  /** One-based source line of the first body line. */
  bodyLine: number;
}

/**
 * Splits a page on its frontmatter delimiters, exactly where Pandoc does.
 *
 * The opening delimiter is the whole of line one and the closing delimiter the
 * whole of a later line, so a horizontal rule or a `---` inside prose can never
 * be read as metadata. Two details come from Pandoc's behaviour rather than
 * from taste, and both were verified with `quarto pandoc`:
 *
 * - trailing whitespace on either delimiter is ignored;
 * - `...` closes a block just as `---` does. Missing that ends the block at the
 *   *next* `---` instead, which would hide every key in between from the
 *   allowlist while Pandoc reads a later block as metadata.
 *
 * An indented delimiter, or one with four dashes, is not a delimiter — Pandoc
 * agrees, and reads no metadata at all in those files.
 */
function splitFrontmatter(source: string): SourceSplit {
  const starts = lineStarts(source);
  const lineText = (index: number): string => {
    const from = starts[index] ?? source.length;
    const to = starts[index + 1] ?? source.length;
    return source.slice(from, to).replace(/\r?\n$/, "").trimEnd();
  };
  const closes = (index: number): boolean => {
    const text = lineText(index);
    return text === FRONTMATTER_DELIMITER || text === FRONTMATTER_TERMINATOR;
  };

  if (source.length === 0 || lineText(0) !== FRONTMATTER_DELIMITER) {
    return { frontmatterLine: 2, unterminated: false, body: source, bodyLine: 1 };
  }

  for (let index = 1; index < starts.length; index += 1) {
    if (!closes(index)) {
      continue;
    }
    return {
      frontmatter: source.slice(starts[1] ?? source.length, starts[index]),
      frontmatterLine: 2,
      unterminated: false,
      body: source.slice(starts[index + 1] ?? source.length),
      bodyLine: index + 2,
    };
  }

  return { frontmatterLine: 2, unterminated: true, body: source, bodyLine: 1 };
}

/** The frontmatter values a page is allowed to carry. */
interface Frontmatter {
  title?: string;
  description?: string;
  category?: KnowledgeCategory;
  aliases: string[];
}

function isAllowedKey(name: string): boolean {
  return (ALLOWED_FRONTMATTER_KEYS as readonly string[]).includes(name);
}

function isKnownCategory(value: string): value is KnowledgeCategory {
  return (KNOWLEDGE_CATEGORIES as readonly string[]).includes(value);
}

/** The trimmed string a YAML node holds, or undefined if it holds anything else. */
function scalarText(node: unknown): string | undefined {
  if (!isScalar(node) || typeof node.value !== "string") {
    return undefined;
  }
  const text = node.value.trim();
  return text === "" ? undefined : text;
}

/**
 * Reads the frontmatter block, enforcing the key allowlist and the required
 * fields. Every problem is recorded; nothing throws.
 */
function readFrontmatter(
  split: SourceSplit,
  kind: PageKind,
  file: string,
  diagnostics: Diagnostic[],
): Frontmatter {
  const frontmatter: Frontmatter = { aliases: [] };
  /** The opening `---`, used for anything that is missing rather than wrong. */
  const blockStart: SourceLocation = { file, line: 1, column: 1 };
  const report = (code: string, message: string, location: SourceLocation): void => {
    diagnostics.push({ code, message, location });
  };

  if (split.unterminated) {
    report(
      "FRONTMATTER_INVALID",
      "the frontmatter block opens with `---` but is never closed by a `---` line of its own",
      blockStart,
    );
    return frontmatter;
  }
  if (split.frontmatter === undefined) {
    report(
      "FRONTMATTER_MISSING",
      "the page must start with a YAML frontmatter block delimited by `---` on its first line",
      blockStart,
    );
    return frontmatter;
  }

  const text = split.frontmatter;
  const starts = lineStarts(text);
  const at = (offset: number): SourceLocation => {
    const position = offsetToLineColumn(starts, offset);
    return {
      file,
      line: position.line + split.frontmatterLine - 1,
      column: position.column,
    };
  };
  const nodeAt = (node: unknown, fallback: SourceLocation): SourceLocation => {
    const range = (node as YamlNode | null)?.range;
    return range === undefined || range === null ? fallback : at(range[0]);
  };

  let document;
  try {
    document = parseDocument(text, { prettyErrors: false, uniqueKeys: true });
  } catch (error) {
    report(
      "FRONTMATTER_INVALID",
      `the frontmatter is not valid YAML: ${(error as Error).message}`,
      blockStart,
    );
    return frontmatter;
  }

  const failure = document.errors[0];
  if (failure !== undefined) {
    report(
      "FRONTMATTER_INVALID",
      `the frontmatter is not valid YAML: ${failure.message}`,
      at(failure.pos[0]),
    );
    return frontmatter;
  }

  const contents = document.contents;
  const pairs = new Map<string, { key: unknown; value: unknown }>();
  if (contents !== null && !(isScalar(contents) && contents.value === null)) {
    if (!isMap(contents)) {
      report(
        "FRONTMATTER_INVALID",
        "the frontmatter must be a YAML mapping of keys to values",
        nodeAt(contents, blockStart),
      );
      return frontmatter;
    }

    for (const pair of contents.items) {
      const name = isScalar(pair.key) ? String(pair.key.value) : String(pair.key);
      if (!isAllowedKey(name)) {
        report(
          "FRONTMATTER_KEY_FORBIDDEN",
          `\`${name}\` is not an allowed frontmatter key; a knowledge page may set only ${ALLOWED_FRONTMATTER_KEYS.join(", ")}`,
          nodeAt(pair.key, blockStart),
        );
        continue;
      }
      pairs.set(name, { key: pair.key, value: pair.value });
    }
  }

  const title = pairs.get("title");
  const titleText = title === undefined ? undefined : scalarText(title.value);
  if (titleText === undefined) {
    report(
      "TITLE_REQUIRED",
      "every knowledge page needs a non-empty `title`",
      title === undefined ? blockStart : nodeAt(title.value, nodeAt(title.key, blockStart)),
    );
  } else {
    frontmatter.title = titleText;
  }

  const description = pairs.get("description");
  const descriptionText =
    description === undefined ? undefined : scalarText(description.value);
  if (descriptionText === undefined) {
    report(
      "DESCRIPTION_REQUIRED",
      "every knowledge page needs a non-empty `description`",
      description === undefined
        ? blockStart
        : nodeAt(description.value, nodeAt(description.key, blockStart)),
    );
  } else {
    frontmatter.description = descriptionText;
  }

  const categories = pairs.get("categories");
  if (kind === "index") {
    if (categories !== undefined) {
      report(
        "INDEX_CATEGORY_FORBIDDEN",
        "`index.qmd` is topic navigation and must not declare `categories`",
        nodeAt(categories.key, blockStart),
      );
    }
  } else if (categories === undefined) {
    report(
      "CATEGORY_REQUIRED",
      `every content page needs \`categories\` with exactly one of ${KNOWLEDGE_CATEGORIES.join(", ")}`,
      blockStart,
    );
  } else {
    const valueLocation = nodeAt(categories.value, nodeAt(categories.key, blockStart));
    const items = isSeq(categories.value) ? categories.value.items : undefined;
    if (items === undefined) {
      report(
        "CATEGORY_INVALID",
        `\`categories\` must be a list holding exactly one of ${KNOWLEDGE_CATEGORIES.join(", ")}`,
        valueLocation,
      );
    } else if (items.length === 0) {
      report(
        "CATEGORY_REQUIRED",
        `\`categories\` is empty; a content page needs exactly one of ${KNOWLEDGE_CATEGORIES.join(", ")}`,
        valueLocation,
      );
    } else if (items.length > 1) {
      report(
        "CATEGORY_INVALID",
        `a content page has exactly one category; \`categories\` lists ${items.length}`,
        valueLocation,
      );
    } else {
      const only = scalarText(items[0]);
      if (only !== undefined && isKnownCategory(only)) {
        frontmatter.category = only;
      } else {
        report(
          "CATEGORY_INVALID",
          `\`${only ?? String(items[0])}\` is not a knowledge category; use one of ${KNOWLEDGE_CATEGORIES.join(", ")}`,
          nodeAt(items[0], valueLocation),
        );
      }
    }
  }

  const aliases = pairs.get("aliases");
  if (aliases !== undefined) {
    const valueLocation = nodeAt(aliases.value, nodeAt(aliases.key, blockStart));
    if (!isSeq(aliases.value)) {
      report(
        "ALIASES_INVALID",
        "`aliases` must be a list of non-empty strings",
        valueLocation,
      );
    } else {
      for (const item of aliases.value.items) {
        const alias = scalarText(item);
        if (alias === undefined) {
          report(
            "ALIASES_INVALID",
            "every `aliases` entry must be a non-empty string",
            nodeAt(item, valueLocation),
          );
          continue;
        }
        frontmatter.aliases.push(alias);
      }
    }
  }

  return frontmatter;
}

/** Everything the Markdown body contributes to a parsed page. */
interface Body {
  readingMap: MarkdownLink[];
  relatedTopics: MarkdownLink[];
  reservedSections: ReservedSectionRecord[];
  localLinks: MarkdownLink[];
  citations: Citation[];
  unsafeHtml: UnsafeHtml[];
}

/** One of the two reserved level-two sections while the body is scanned. */
interface ReservedSection {
  heading: string;
  /** The diagnostic code this section reports a duplicate with. */
  code: string;
  seen: boolean;
  targets: Set<string>;
  entries: MarkdownLink[];
}

/** A target that must resolve inside the knowledge tree. */
function isLocalTarget(target: string): boolean {
  const trimmed = target.trim();
  if (trimmed === "" || trimmed.startsWith("#")) {
    return false;
  }
  return !EXTERNAL_TARGET.test(trimmed);
}

/** A half-open source range of a code block or code span. */
interface CodeRange {
  start: number;
  end: number;
  /** True for a Pandoc raw block, whose contents reach the output verbatim. */
  raw: boolean;
  /** True for a fence that is never closed, which Pandoc does not treat as code. */
  unclosed: boolean;
}

/**
 * True when a fenced code block never closes.
 *
 * remark runs an unclosed fence to the end of the file and calls all of it
 * code; Pandoc requires the closing fence and falls back to reading the rest as
 * ordinary Markdown. Believing remark here blinds every scan below to the whole
 * tail of the page — `quarto pandoc` emits a `<script>` written after an
 * unclosed fence as raw HTML, and every link, citation, and curated entry below
 * it disappears from the graph. `FENCE_UNCLOSED` reports it, so the answer has
 * to be right in both directions.
 *
 * `indent` is the column the opener sits at, minus one. remark reports a fence
 * inside a block quote or a list item from its backticks onwards, so every
 * *later* line of the slice still carries the container prefix that line one
 * lost (`> `, `>   `, five spaces …). At most that many leading spaces, tabs,
 * and `>` are therefore stripped from the closing candidate before CommonMark's
 * own rule — at most three spaces, then at least as many markers as the opener
 * — is applied to what is left. Without it every quoted or deeply nested fence
 * reads as unclosed.
 */
function isUnclosedFence(raw: string, indent: number): boolean {
  const opening = /^ {0,3}(`{3,}|~{3,})/.exec(raw);
  if (opening === null) {
    return false;
  }
  const fence = opening[1] ?? "";
  const marker = fence[0] ?? "`";
  const container = new RegExp(`^[ \t>]{0,${indent}}`);
  const closing = new RegExp(`^ {0,3}[${marker}]{${fence.length},}\\s*$`);
  const lines = raw.split("\n");
  for (let index = lines.length - 1; index >= 1; index -= 1) {
    const line = lines[index] ?? "";
    if (line.trim() === "") {
      continue;
    }
    return !closing.test(line.replace(container, ""));
  }
  return true;
}

/**
 * The ranges of every code block and code span in the body.
 *
 * Ordinary code is escaped by the renderer and is the one place a knowledge
 * page may legitimately show `<script>` or `onclick=`. Two kinds of node only
 * look like code:
 *
 * - a Pandoc raw block (```` ```{=html} ````, `` `…`{=html} ``) is copied
 *   straight into the output, so it is marked `raw`;
 * - an unclosed fence is not code to Pandoc at all, so it is marked `unclosed`.
 *
 * Both stay in scope for the unsafe-HTML scan, and an unclosed fence also stops
 * hiding metadata blocks.
 */
function collectCodeRanges(body: string, tree: Root): CodeRange[] {
  const ranges: CodeRange[] = [];
  visit(tree, (node, index, parent) => {
    if (node.type !== "code" && node.type !== "inlineCode") {
      return;
    }
    const start = node.position?.start.offset;
    const end = node.position?.end.offset;
    if (start === undefined || end === undefined) {
      return;
    }
    if (node.type === "code") {
      ranges.push({
        start,
        end,
        raw: RAW_ATTRIBUTE.test((node.lang ?? "").trim()),
        unclosed: isUnclosedFence(
          body.slice(start, end),
          (node.position?.start.column ?? 1) - 1,
        ),
      });
      return;
    }
    // An inline raw block is a code span followed by its `{=format}` attribute.
    const next =
      index === undefined || parent === undefined
        ? undefined
        : parent.children[index + 1];
    const attribute = next?.type === "text" ? next.value : "";
    ranges.push({ start, end, raw: RAW_ATTRIBUTE.test(attribute), unclosed: false });
  });
  return ranges;
}

/** A half-open range of the body source. */
interface Range {
  start: number;
  end: number;
}

/** A tag opener: where its name ends, and whether it is a known element. */
interface TagOpener {
  /** The offset just past `<name`. */
  end: number;
  /** Known elements may contain a blank line; invented names may not. */
  known: boolean;
}

/**
 * Reads the opener of a tag at `open`, or undefined when this is not one.
 *
 * A tag name is a letter followed by letters, digits, and hyphens, and it must
 * end where HTML allows one to end: whitespace, `/`, or `>`. That single rule
 * is what separates a real tag from the shapes clean content is full of —
 * `$x<y$` (name ends at `$`), the autolink `<https://…>` and `<a@b.com>` (name
 * ends at `:` or `@`) are all rejected without special-casing them.
 */
function readTagOpener(text: string, open: number): TagOpener | undefined {
  let index = open + 1;
  if (text[index] === "/") {
    index += 1;
  }
  if (!HTML_TAG_NAME_START.test(text[index] ?? "")) {
    return undefined;
  }
  const nameStart = index;
  index += 1;
  while (HTML_TAG_NAME_PART.test(text[index] ?? "")) {
    index += 1;
  }
  const next = text[index];
  if (next !== undefined && !/[\s/>]/.test(next)) {
    return undefined;
  }
  return {
    end: index,
    known: HTML_ELEMENT_NAMES.has(text.slice(nameStart, index).toLowerCase()),
  };
}

/** The offset after a blank line starting at `position`, or undefined. */
function blankLineEnd(text: string, position: number): number | undefined {
  let index = position;
  while (index < text.length && /[ \t\r]/.test(text[index] ?? "")) {
    index += 1;
  }
  if (index >= text.length) {
    return index;
  }
  return text[index] === "\n" ? index + 1 : undefined;
}

/**
 * The ranges of the body that sit inside an HTML start tag.
 *
 * A forward, quote-aware pass is the only way to get this right in both
 * directions. Scanning backwards from a candidate attribute (an earlier
 * version of this file) is fooled by a `<` inside a quoted attribute value —
 * `<div title="a < b" onclick="…">` — which is a live handler Pandoc renders,
 * and it also drags unrelated prose into a tag that a stray `<` opened.
 *
 * Rules that matter:
 *
 * - a quoted attribute value consumes `<` and `>`, so neither an evasion nor a
 *   legitimate `title="a>b"` confuses the boundary;
 * - a quote only opens a value when it follows `=`, as HTML requires. A stray
 *   quote inside an unquoted value (`<div id=a' onclick=…>`, `title=it's`) is
 *   an ordinary character; treating every quote as a delimiter swallows the `>`
 *   and drops a tag Pandoc renders live;
 * - escaped code is jumped over without changing the tag state, so a `` `<div` ``
 *   in a code span cannot open a tag while a code span *inside* a tag cannot
 *   close one;
 * - a blank line ends a candidate only when the name is not a real element.
 *   Pandoc spans blank lines for `div`, `span`, `svg`, `table`, `section` and
 *   `p` — each renders a live handler that way — but not for an invented name
 *   (`<my-widget⏎⏎onclick=…>`) or for prose (`<x is less than y`), which is
 *   what stops two paragraphs from fusing into an imaginary tag;
 * - a candidate that never reaches `>` is discarded, because no renderer makes
 *   it a tag: `If x<y and y>z then online=true` produces the raw tag
 *   `<y and y>` with `online=` safely after it, while `If x<y then the
 *   online=true branch runs` stays plain text throughout.
 */
function collectTagRanges(body: string, escaped: readonly CodeRange[]): Range[] {
  const ranges: Range[] = [];
  let index = 0;
  let open: number | undefined;
  let spansBlankLines = false;
  let quote: string | undefined;
  /** The last non-whitespace character, used to spot the `=` before a value. */
  let significant = "";

  while (index < body.length) {
    const skip = escaped.find((range) => index >= range.start && index < range.end);
    if (skip !== undefined) {
      index = skip.end;
      continue;
    }

    const character = body[index] ?? "";
    if (open === undefined) {
      const opener = character === "<" ? readTagOpener(body, index) : undefined;
      if (opener === undefined) {
        index += 1;
        continue;
      }
      open = index;
      spansBlankLines = opener.known;
      significant = "";
      index = opener.end;
      continue;
    }

    if (quote !== undefined) {
      if (character === quote) {
        quote = undefined;
      }
      index += 1;
      continue;
    }
    if ((character === '"' || character === "'") && significant === "=") {
      quote = character;
      index += 1;
      continue;
    }
    if (character === ">") {
      ranges.push({ start: open, end: index + 1 });
      open = undefined;
      index += 1;
      continue;
    }
    if (character === "\n" && !spansBlankLines) {
      const afterBlank = blankLineEnd(body, index + 1);
      if (afterBlank !== undefined) {
        // Never closed, so it was never a tag.
        open = undefined;
        quote = undefined;
        index = afterBlank;
        continue;
      }
    }
    if (!/\s/.test(character)) {
      significant = character;
    }
    index += 1;
  }

  return ranges;
}

/**
 * Finds raw `<script` tags and inline event handlers anywhere the renderer
 * would emit them verbatim.
 *
 * The scan runs over the body source rather than over mdast `html` nodes,
 * because CommonMark is stricter than Pandoc about what a tag is:
 * `<svg/onload=alert(1)>` is a plain *text* node to remark, while Pandoc's
 * lenient HTML reader passes it through to the page. Only ordinary code is
 * exempt.
 */
function scanUnsafeHtml(
  body: string,
  codeRanges: readonly CodeRange[],
  at: (offset: number) => SourceLocation,
): UnsafeHtml[] {
  const escaped = codeRanges.filter((range) => !range.raw && !range.unclosed);
  const isEscaped = (offset: number): boolean =>
    escaped.some((range) => offset >= range.start && offset < range.end);
  const tags = collectTagRanges(body, escaped);
  const isInTag = (offset: number): boolean =>
    tags.some((range) => offset >= range.start && offset < range.end);

  const found: UnsafeHtml[] = [];
  for (const match of body.matchAll(HTML_SCRIPT_TAG)) {
    const offset = match.index ?? 0;
    if (!isEscaped(offset)) {
      found.push({ kind: "script", location: at(offset) });
    }
  }
  for (const match of body.matchAll(HTML_EVENT_HANDLER)) {
    const offset = match.index ?? 0;
    if (!isEscaped(offset) && isInTag(offset)) {
      found.push({ kind: "inline-handler", location: at(offset) });
    }
  }
  return found.sort(
    (left, right) =>
      left.location.line - right.location.line ||
      left.location.column - right.location.column,
  );
}

/**
 * True when a text block is a YAML mapping, which is what Pandoc requires of a
 * metadata block.
 *
 * Parse errors are ignored on purpose. `yaml` rejects duplicate keys that
 * Pandoc accepts, and a partially parsed mapping is still a mapping; treating
 * "not clean YAML" as "not metadata" would hand back the bypass.
 */
function isYamlMapping(text: string): boolean {
  try {
    const contents = parseDocument(text, {
      prettyErrors: false,
      uniqueKeys: false,
    }).contents;
    return isMap(contents) && contents.items.length > 0;
  } catch {
    return false;
  }
}

/**
 * Reports Pandoc YAML metadata blocks written *after* the frontmatter.
 *
 * Pandoc merges every metadata block in a file, so a second block halfway down
 * a page silently sets page metadata — `header-includes` injects raw content
 * into `<head>`, `execute` turns rendering into execution. The frontmatter
 * allowlist would be worthless if it only guarded the first block.
 *
 * Detection works on the source, not on the mdast shape (which degenerates into
 * a thematic break, a paragraph, and sometimes a setext heading depending on
 * the contents). A block is reported when a line of exactly `---` — ignoring
 * trailing whitespace, which Pandoc ignores too — is followed by a non-blank
 * line, closed by a later `---` or `...` line, sits outside every code block,
 * and holds a YAML mapping.
 *
 * The rules come from running the variants through `quarto pandoc` rather than
 * from the documentation, which says a mid-document block must follow a blank
 * line. It need not: Pandoc merged the block in every one of these, none of
 * which has a blank line before it — directly after the frontmatter's closing
 * `---`, directly after a fenced code block, directly after a setext heading,
 * and with trailing spaces or a tab on either delimiter.
 *
 * Where the two disagree the parser reports more than Pandoc accepts (for
 * instance a block right after a paragraph line, which Pandoc reads as a setext
 * heading). Guessing a parser's precedence rules is not a safe basis for a
 * security check, and the shape is a mistake worth reporting either way.
 * Ordinary `---` horizontal rules, indented or longer rules, and `---` inside a
 * fence stay valid, which is what keeps prose readable.
 */
function scanMetadataBlocks(
  body: string,
  starts: readonly number[],
  codeRanges: readonly CodeRange[],
  /** One-based body lines that underline a setext heading. */
  setextUnderlines: ReadonlySet<number>,
  at: (offset: number) => SourceLocation,
  diagnostics: Diagnostic[],
): void {
  // Pandoc ignores trailing whitespace on a delimiter line; so must this.
  const lineAt = (index: number): string =>
    body
      .slice(starts[index] ?? body.length, starts[index + 1] ?? body.length)
      .replace(/\r?\n$/, "")
      .trimEnd();
  const isCode = (index: number): boolean => {
    const offset = starts[index] ?? body.length;
    return codeRanges.some(
      (range) => !range.unclosed && offset >= range.start && offset < range.end,
    );
  };

  let index = 0;
  while (index < starts.length) {
    const opensBlock =
      lineAt(index) === FRONTMATTER_DELIMITER &&
      !isCode(index) &&
      // A `---` that closes an open paragraph is a setext underline, not an
      // opener. `Results⏎---⏎Temperature: 4.2` is a heading and a sentence.
      !setextUnderlines.has(index + 1) &&
      index + 1 < starts.length &&
      lineAt(index + 1).trim() !== "";
    if (!opensBlock) {
      index += 1;
      continue;
    }

    let close: number | undefined;
    for (let candidate = index + 1; candidate < starts.length; candidate += 1) {
      const text = lineAt(candidate);
      if (
        (text === FRONTMATTER_DELIMITER || text === FRONTMATTER_TERMINATOR) &&
        !isCode(candidate)
      ) {
        close = candidate;
        break;
      }
    }
    if (close === undefined) {
      index += 1;
      continue;
    }

    const contents = body.slice(
      starts[index + 1] ?? body.length,
      starts[close] ?? body.length,
    );
    if (!isYamlMapping(contents)) {
      index += 1;
      continue;
    }

    diagnostics.push({
      code: "FRONTMATTER_INVALID",
      message:
        "a second YAML metadata block appears here; Pandoc merges it into the page metadata, so only the frontmatter block at the top of the file may set metadata",
      location: at(starts[index] ?? 0),
    });
    index = close + 1;
  }
}

/**
 * Reads the Markdown body.
 *
 * Reserved-heading scope is deliberately narrow: an entry counts only when it
 * is a link written directly in a list item of a list that sits directly under
 * a level-two `## Reading map` or `## Related topics` heading, before the next
 * heading of any level. Prose, sub-headings, nested lists, code, and inline
 * code are all outside the machine-readable contract, so a sentence that
 * happens to link to a page never silently becomes a containment edge.
 *
 * Reference-style links (`[Proof][proof]`, `[proof]`, `![Fig][fig]`) are
 * resolved through their definitions, so the curated contract does not depend
 * on which link syntax the author used. A reference with no definition renders
 * as literal text and contributes nothing; the missing child then surfaces
 * loudly in the graph rather than quietly here.
 */
function readBody(
  body: string,
  bodyLine: number,
  file: string,
  diagnostics: Diagnostic[],
): Body {
  const result: Body = {
    readingMap: [],
    relatedTopics: [],
    reservedSections: [],
    localLinks: [],
    citations: [],
    unsafeHtml: [],
  };

  const starts = lineStarts(body);
  const lineOffset = bodyLine - 1;
  const atOffset = (offset: number): SourceLocation => {
    const position = offsetToLineColumn(starts, offset);
    return { file, line: position.line + lineOffset, column: position.column };
  };
  const atNode = (node: {
    position?: { start: { line: number; column: number } };
  }): SourceLocation => ({
    file,
    line: (node.position?.start.line ?? 1) + lineOffset,
    column: node.position?.start.column ?? 1,
  });

  const tree = unified().use(remarkParse).parse(body) as Root;

  // Link definitions first: the reserved sections and the link list both
  // resolve reference-style links through them. CommonMark keeps the first
  // definition when an identifier is defined twice.
  const definitions = new Map<string, Definition>();
  visit(tree, "definition", (node) => {
    if (!definitions.has(node.identifier)) {
      definitions.set(node.identifier, node);
    }
  });
  const usedDefinitions = new Set<string>();
  /** The target a link node points at, following a reference if needed. */
  const targetOf = (node: {
    type: string;
    url?: string;
    identifier?: string;
  }): string | undefined => {
    if (node.type === "link" || node.type === "image") {
      return node.url;
    }
    if (node.identifier === undefined) {
      return undefined;
    }
    const definition = definitions.get(node.identifier);
    if (definition === undefined) {
      return undefined;
    }
    usedDefinitions.add(node.identifier);
    return definition.url;
  };

  // The two reserved sections: the curated contract of an index page.
  const sections: ReservedSection[] = [
    {
      heading: READING_MAP_HEADING,
      code: "READING_MAP_DUPLICATE",
      seen: false,
      targets: new Set<string>(),
      entries: result.readingMap,
    },
    {
      heading: RELATED_TOPICS_HEADING,
      code: "RELATED_TOPICS_DUPLICATE",
      seen: false,
      targets: new Set<string>(),
      entries: result.relatedTopics,
    },
  ];
  let open: ReservedSection | undefined;

  for (const child of tree.children) {
    if (child.type === "heading") {
      const label = mdastToString(child).trim();
      const reserved =
        child.depth === 2
          ? sections.find((section) => section.heading === label)
          : undefined;
      if (reserved === undefined) {
        open = undefined;
        continue;
      }
      if (reserved.seen) {
        diagnostics.push({
          code: reserved.code,
          message: `\`## ${reserved.heading}\` appears more than once; a page has at most one`,
          location: atNode(child),
        });
        open = undefined;
        continue;
      }
      reserved.seen = true;
      // The declaration itself, which an empty section cannot express through
      // its entries: `## Reading map` with no list is a topic with no children
      // yet, and the graph must tell that from an index with no section at all.
      result.reservedSections.push({
        heading: reserved.heading,
        location: atNode(child),
      });
      open = reserved;
      continue;
    }

    if (open === undefined || child.type !== "list") {
      continue;
    }

    for (const item of child.children) {
      for (const block of item.children) {
        if (block.type !== "paragraph") {
          continue;
        }
        for (const inline of block.children) {
          if (inline.type !== "link" && inline.type !== "linkReference") {
            continue;
          }
          const target = targetOf(inline);
          if (target === undefined) {
            continue;
          }
          const entry: MarkdownLink = {
            kind: "link",
            label: mdastToString(inline),
            target,
            location: atNode(inline),
          };
          if (open.targets.has(entry.target)) {
            diagnostics.push({
              code: open.code,
              message: `\`${entry.target}\` is listed more than once under \`## ${open.heading}\``,
              location: entry.location,
            });
            continue;
          }
          open.targets.add(entry.target);
          open.entries.push(entry);
        }
      }
    }
  }

  visit(tree, (node) => {
    if (
      node.type === "link" ||
      node.type === "image" ||
      node.type === "linkReference" ||
      node.type === "imageReference"
    ) {
      const target = targetOf(node);
      if (target !== undefined && isLocalTarget(target)) {
        result.localLinks.push({
          kind:
            node.type === "image" || node.type === "imageReference"
              ? "image"
              : "link",
          label: mdastToString(node),
          target,
          location: atNode(node),
        });
      }
      return;
    }

    if (node.type !== "text") {
      return;
    }
    const start = node.position?.start.offset;
    const end = node.position?.end.offset;
    if (start === undefined || end === undefined) {
      return;
    }

    // Citations are read from the raw source of the text node, not from its
    // decoded value, so escapes and character references cannot shift a
    // location or invent a key.
    for (const match of body.slice(start, end).matchAll(CITATION_KEY)) {
      const offset = start + (match.index ?? 0);
      const before = offset === 0 ? "" : (body[offset - 1] ?? "");
      if (before !== "" && !CITATION_PREFIX.test(before)) {
        continue;
      }
      // Pandoc allows punctuation inside a key but not at its end.
      let key = match[0].slice(1);
      while (key.length > 0 && !/[A-Za-z0-9_]$/.test(key)) {
        key = key.slice(0, -1);
      }
      if (key.length > 0) {
        result.citations.push({ key, location: atOffset(offset) });
      }
    }
  });

  // A definition nobody references still names a target, and its URL is the
  // only place that target is written; a referenced definition is already
  // covered at each usage.
  for (const [identifier, definition] of definitions) {
    if (usedDefinitions.has(identifier) || !isLocalTarget(definition.url)) {
      continue;
    }
    result.localLinks.push({
      kind: "link",
      label: definition.label ?? identifier,
      target: definition.url,
      location: atNode(definition),
    });
  }
  result.localLinks.sort(
    (left, right) =>
      left.location.line - right.location.line ||
      left.location.column - right.location.column,
  );

  // A setext heading spans its text and the `---`/`===` line under it, so its
  // last line is the underline.
  const setextUnderlines = new Set<number>();
  for (const child of tree.children) {
    if (
      child.type === "heading" &&
      child.position !== undefined &&
      child.position.start.line < child.position.end.line
    ) {
      setextUnderlines.add(child.position.end.line);
    }
  }

  // An unclosed fence is where this parser and Pandoc stop agreeing about what
  // the page even says, so it is reported rather than compensated for. The
  // scans below already look through it; the graph cannot, because
  // `localLinks`, `citations`, and the two curated sections are read from the
  // mdast tree, and remark has swallowed everything after the opener into one
  // code node. Reporting it at the opener fails the page closed instead of
  // publishing a tail that nothing validated.
  const codeRanges = collectCodeRanges(body, tree);
  for (const range of codeRanges) {
    if (range.unclosed) {
      diagnostics.push({
        code: "FENCE_UNCLOSED",
        message:
          "this fenced code block is never closed; Pandoc reads the rest of the page as Markdown while this parser reads it as code, so every link, citation, and curated section below it would go unvalidated",
        location: atOffset(range.start),
      });
    }
  }
  result.unsafeHtml.push(...scanUnsafeHtml(body, codeRanges, atOffset));
  scanMetadataBlocks(body, starts, codeRanges, setextUnderlines, atOffset, diagnostics);

  return result;
}

/** The id of the index that owns a page. An index owns itself. */
function owningTopicId(id: string, kind: PageKind): string {
  if (kind === "index") {
    return id;
  }
  const directory = path.posix.dirname(id);
  return directory === "." || directory === "" || directory === "/"
    ? INDEX_FILENAME
    : `${directory}/${INDEX_FILENAME}`;
}

/** The path a diagnostic names: repository-relative and POSIX, when possible. */
function diagnosticFile(repoRoot: string, absolutePath: string): string {
  const relative = path.relative(repoRoot, absolutePath);
  if (relative === "" || relative.startsWith("..") || path.isAbsolute(relative)) {
    return toPosix(absolutePath);
  }
  return toPosix(relative);
}

/**
 * Parses one knowledge page. Never throws on page content: everything wrong
 * with the page comes back in `parseDiagnostics`.
 */
export function parseKnowledgePage(
  input: ParseKnowledgePageInput,
): ParsedKnowledgePage {
  const source = stripBom(input.source);
  const id = toPosix(path.relative(input.knowledgeRoot, input.absolutePath));
  const kind: PageKind =
    path.basename(input.absolutePath) === INDEX_FILENAME ? "index" : "content";
  const file = diagnosticFile(input.repoRoot, input.absolutePath);

  const diagnostics: Diagnostic[] = [];
  const split = splitFrontmatter(source);
  const frontmatter = readFrontmatter(split, kind, file, diagnostics);
  const body = readBody(split.body, split.bodyLine, file, diagnostics);

  return {
    id,
    absolutePath: input.absolutePath,
    topicId: owningTopicId(id, kind),
    kind,
    ...(frontmatter.title === undefined ? {} : { title: frontmatter.title }),
    ...(frontmatter.description === undefined
      ? {}
      : { description: frontmatter.description }),
    ...(frontmatter.category === undefined ? {} : { category: frontmatter.category }),
    aliases: frontmatter.aliases,
    body: split.body,
    readingMap: body.readingMap,
    relatedTopics: body.relatedTopics,
    reservedSections: body.reservedSections,
    localLinks: body.localLinks,
    citations: body.citations,
    unsafeHtml: body.unsafeHtml,
    parseDiagnostics: diagnostics,
  };
}
