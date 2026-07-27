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
 * must be able to see.
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

/** The only line that opens or closes a frontmatter block. */
const FRONTMATTER_DELIMITER = "---";

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

/** Characters that may continue an HTML tag name. */
const HTML_TAG_NAME_START = /[a-zA-Z]/;

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
 * Splits a page on its exact `---` delimiters.
 *
 * The opening delimiter must be the whole of line one and the closing
 * delimiter the whole of a later line; nothing else counts, so a horizontal
 * rule or a `---` inside prose can never be read as metadata.
 */
function splitFrontmatter(source: string): SourceSplit {
  const starts = lineStarts(source);
  const lineText = (index: number): string => {
    const from = starts[index] ?? source.length;
    const to = starts[index + 1] ?? source.length;
    return source.slice(from, to).replace(/\r?\n$/, "");
  };

  if (source.length === 0 || lineText(0) !== FRONTMATTER_DELIMITER) {
    return { frontmatterLine: 2, unterminated: false, body: source, bodyLine: 1 };
  }

  for (let index = 1; index < starts.length; index += 1) {
    if (lineText(index) !== FRONTMATTER_DELIMITER) {
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
}

/**
 * The ranges of every code block and code span in the body.
 *
 * Ordinary code is escaped by the renderer and is the one place a knowledge
 * page may legitimately show `<script>` or `onclick=`. A Pandoc raw block
 * (```` ```{=html} ````, `` `…`{=html} ``) is the opposite: a `code` node in
 * mdast, but copied straight into the output, so it is marked `raw` and stays
 * in scope for the unsafe-HTML scan.
 */
function collectCodeRanges(tree: Root): CodeRange[] {
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
      ranges.push({ start, end, raw: RAW_ATTRIBUTE.test((node.lang ?? "").trim()) });
      return;
    }
    // An inline raw block is a code span followed by its `{=format}` attribute.
    const next =
      index === undefined || parent === undefined
        ? undefined
        : parent.children[index + 1];
    const attribute = next?.type === "text" ? next.value : "";
    ranges.push({ start, end, raw: RAW_ATTRIBUTE.test(attribute) });
  });
  return ranges;
}

/**
 * True when an offset sits inside an HTML start tag: after a `<name` with no
 * unquoted `>` between them.
 *
 * This is what keeps whole-document handler scanning honest in both
 * directions. A quoted `>` (`<div title="a>b" onclick="…">`) does not end the
 * tag, so the evasion is still caught; and an `onload=` that is merely prose or
 * a URL query parameter (`…?online=true`) is not inside a tag, so it is not
 * reported.
 */
function isInsideTag(text: string, offset: number): boolean {
  const open = text.lastIndexOf("<", offset);
  if (open < 0 || !HTML_TAG_NAME_START.test(text[open + 1] ?? "")) {
    return false;
  }
  let quote: string | undefined;
  for (let index = open + 1; index < offset; index += 1) {
    const character = text[index];
    if (quote !== undefined) {
      if (character === quote) {
        quote = undefined;
      }
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
      continue;
    }
    if (character === ">") {
      return false;
    }
  }
  return true;
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
  const escaped = codeRanges.filter((range) => !range.raw);
  const isEscaped = (offset: number): boolean =>
    escaped.some((range) => offset >= range.start && offset < range.end);

  const found: UnsafeHtml[] = [];
  for (const match of body.matchAll(HTML_SCRIPT_TAG)) {
    const offset = match.index ?? 0;
    if (!isEscaped(offset)) {
      found.push({ kind: "script", location: at(offset) });
    }
  }
  for (const match of body.matchAll(HTML_EVENT_HANDLER)) {
    const offset = match.index ?? 0;
    if (!isEscaped(offset) && isInsideTag(body, offset)) {
      found.push({ kind: "inline-handler", location: at(offset) });
    }
  }
  return found.sort(
    (left, right) =>
      left.location.line - right.location.line ||
      left.location.column - right.location.column,
  );
}

/** True when a text block is a YAML mapping, which is what Pandoc requires. */
function isYamlMapping(text: string): boolean {
  try {
    const document = parseDocument(text, { prettyErrors: false });
    return document.errors.length === 0 && isMap(document.contents);
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
 * Detection follows Pandoc's own rule rather than the mdast shape (which is a
 * thematic break, a paragraph, and possibly a setext heading): a `---` line
 * that starts the body or follows a blank line, is not followed by a blank
 * line, is closed by a later `---` or `...` line, and whose contents parse as a
 * YAML mapping. Requiring a mapping is what keeps an ordinary `---` horizontal
 * rule from being reported.
 */
function scanMetadataBlocks(
  body: string,
  starts: readonly number[],
  codeRanges: readonly CodeRange[],
  /** True when the body is the whole file, so its first line starts it. */
  atDocumentStart: boolean,
  at: (offset: number) => SourceLocation,
  diagnostics: Diagnostic[],
): void {
  const lineAt = (index: number): string =>
    body
      .slice(starts[index] ?? body.length, starts[index + 1] ?? body.length)
      .replace(/\r?\n$/, "");
  const isCode = (index: number): boolean => {
    const offset = starts[index] ?? body.length;
    return codeRanges.some((range) => offset >= range.start && offset < range.end);
  };

  let index = 0;
  while (index < starts.length) {
    const opensBlock =
      lineAt(index) === FRONTMATTER_DELIMITER &&
      !isCode(index) &&
      (index === 0 ? atDocumentStart : lineAt(index - 1).trim() === "") &&
      index + 1 < starts.length &&
      lineAt(index + 1).trim() !== "";
    if (!opensBlock) {
      index += 1;
      continue;
    }

    let close: number | undefined;
    for (let candidate = index + 1; candidate < starts.length; candidate += 1) {
      const text = lineAt(candidate);
      if ((text === FRONTMATTER_DELIMITER || text === "...") && !isCode(candidate)) {
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

  const codeRanges = collectCodeRanges(tree);
  result.unsafeHtml.push(...scanUnsafeHtml(body, codeRanges, atOffset));
  scanMetadataBlocks(body, starts, codeRanges, bodyLine === 1, atOffset, diagnostics);

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
    localLinks: body.localLinks,
    citations: body.citations,
    unsafeHtml: body.unsafeHtml,
    parseDiagnostics: diagnostics,
  };
}
