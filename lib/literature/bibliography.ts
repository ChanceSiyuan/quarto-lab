/**
 * Reads `literature/ref.bib` into a small, validated model of external
 * evidence.
 *
 * The bibliography is the single source of truth for the literature tree, so
 * this module is deliberately strict:
 *
 * - parsing is delegated to `@retorquere/bibtex-parser`; there is no second,
 *   ad-hoc BibTeX grammar in this repository;
 * - any diagnostic the parser reports is a hard failure, never a warning that
 *   silently drops a reference;
 * - titles are kept exactly as written (the parser's sentence-casing guesswork
 *   is disabled) because external metadata must not be reworded;
 * - citekeys and method keywords are validated against conservative patterns,
 *   because both are used as directory names later in the pipeline;
 * - identifiers are normalized to their bare form (`10.1103/PhysRevLett.80.4558`,
 *   `1008.3477v2`, `cond-mat/9803107`) so callers can build URLs themselves.
 */

import { readFile } from "node:fs/promises";

// `@retorquere/bibtex-parser@10.0.0` publishes no type declarations (its
// package.json points at a `dist/types` directory that is missing from the
// tarball). The version is pinned exactly, so the shape below is stable; every
// value it produces is still validated at run time before it is trusted.
// @ts-expect-error -- untyped dependency, see the comment above.
import { parse as parseBibTeXUntyped } from "@retorquere/bibtex-parser";

/** A creator as returned by the parser: either a literal or a split name. */
interface BibTeXCreator {
  name?: string;
  firstName?: string;
  lastName?: string;
  prefix?: string;
  suffix?: string;
}

type BibTeXValue = string | readonly string[] | readonly BibTeXCreator[];

interface BibTeXEntry {
  type: string;
  key: string;
  fields: Readonly<Record<string, BibTeXValue | undefined>>;
}

interface BibTeXBibliography {
  entries: readonly BibTeXEntry[];
  errors: readonly { error: string }[];
}

type ParseBibTeX = (
  input: string,
  options: { sentenceCase: false },
) => BibTeXBibliography;

const parseBibTeX = parseBibTeXUntyped as ParseBibTeX;

/**
 * A method keyword. It becomes a directory name under `literature/`, so it is
 * restricted to lowercase, hyphen-separated ASCII.
 */
export const SAFE_METHOD_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/**
 * A citekey. It is used in paths, URLs, and Markdown, so it may never contain a
 * separator (`/`, `\`), whitespace, or a leading dot or dash.
 */
export const SAFE_CITEKEY_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]*$/;

/** A bare DOI, without the `https://doi.org/` resolver prefix. */
const DOI_PATTERN = /^10\.\d{4,9}\/[^\s"<>{}|\\^`]+$/;

/**
 * A bare arXiv identifier: the post-2007 `YYMM.NNNNN` form or the archival
 * `archive[.SC]/YYMMNNN` form, each with an optional explicit version.
 */
const ARXIV_PATTERN =
  /^(?:\d{4}\.\d{4,5}|[a-z]+(?:-[a-z]+)*(?:\.[A-Za-z]{2})?\/\d{7})(?:v\d+)?$/;

/** A four-digit publication year. */
const YEAR_PATTERN = /^\d{4}$/;

const ARXIV_HOSTS = new Set(["arxiv.org", "www.arxiv.org", "export.arxiv.org"]);

const DOI_URL_PREFIXES = [
  "https://doi.org/",
  "http://doi.org/",
  "https://dx.doi.org/",
  "http://dx.doi.org/",
];

export interface LiteratureEntry {
  citekey: string;
  type: string;
  title: string;
  authors: readonly string[];
  year?: string;
  doi?: string;
  arxiv?: string;
  methods: readonly string[];
}

function compare(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function fail(citekey: string, detail: string): never {
  throw new Error(`bibliography entry "${citekey}": ${detail}`);
}

/**
 * Reports control characters, which would corrupt a generated Markdown index
 * and can hide text from a reviewer.
 */
function hasControlCharacter(value: string): boolean {
  for (const character of value) {
    const code = character.codePointAt(0) ?? 0;
    if (code < 0x20 || code === 0x7f) {
      return true;
    }
  }
  return false;
}

/**
 * Reads a single-line string field, treating a blank value as absent.
 *
 * Text is normalized to Unicode NFC. The parser expands LaTeX escapes such as
 * `\"{o}` into decomposed sequences while already-Unicode input stays
 * composed; normalizing keeps one byte sequence per name in generated files.
 */
function stringField(
  entry: BibTeXEntry,
  citekey: string,
  field: string,
): string | undefined {
  const value = entry.fields[field];
  if (value === undefined) {
    return undefined;
  }
  if (typeof value !== "string") {
    fail(citekey, `expected "${field}" to be a single value`);
  }
  if (hasControlCharacter(value)) {
    fail(citekey, `"${field}" contains a control character`);
  }
  const trimmed = value.normalize("NFC").trim();
  return trimmed === "" ? undefined : trimmed;
}

/**
 * Renders one creator as `given prefix family, suffix`, or as the literal name
 * that a braced BibTeX group produces (`{The Fixture Collaboration}`).
 */
function formatCreator(creator: BibTeXCreator, citekey: string): string {
  const parts =
    typeof creator.name === "string"
      ? [creator.name]
      : [creator.firstName, creator.prefix, creator.lastName].filter(
          (part): part is string => typeof part === "string" && part !== "",
        );

  let name = parts.join(" ").normalize("NFC").replace(/\s+/g, " ").trim();
  if (typeof creator.suffix === "string" && creator.suffix.trim() !== "") {
    name = `${name}, ${creator.suffix.trim()}`;
  }
  if (name === "") {
    fail(citekey, "has an author with no name");
  }
  if (hasControlCharacter(name)) {
    fail(citekey, "has an author name with a control character");
  }
  return name;
}

function readAuthors(entry: BibTeXEntry, citekey: string): string[] {
  const value = entry.fields.author;
  if (value === undefined) {
    return [];
  }
  if (!Array.isArray(value)) {
    fail(citekey, 'expected "author" to be a creator list');
  }
  return (value as readonly BibTeXCreator[]).map((creator) => {
    if (typeof creator !== "object" || creator === null) {
      fail(citekey, 'expected "author" to be a creator list');
    }
    return formatCreator(creator, citekey);
  });
}

/** Strips a resolver URL or `doi:` prefix and validates the bare DOI. */
function normalizeDoi(raw: string, citekey: string): string {
  let value = raw;
  for (const prefix of DOI_URL_PREFIXES) {
    if (value.toLowerCase().startsWith(prefix)) {
      value = value.slice(prefix.length);
      break;
    }
  }
  if (value.toLowerCase().startsWith("doi:")) {
    value = value.slice("doi:".length);
  }
  value = value.trim();

  if (!DOI_PATTERN.test(value)) {
    fail(citekey, `"${raw}" is not a usable DOI`);
  }
  return value;
}

/**
 * Strips `arXiv:` and arXiv URL prefixes, keeps an explicit `vN` suffix, and
 * validates the remaining identifier.
 */
function normalizeArxiv(raw: string, citekey: string): string {
  let value = raw.trim();

  if (/^https?:\/\//i.test(value)) {
    let url: URL;
    try {
      url = new URL(value);
    } catch {
      return fail(citekey, `"${raw}" is not a usable arXiv identifier`);
    }
    if (!ARXIV_HOSTS.has(url.hostname.toLowerCase())) {
      fail(citekey, `"${raw}" is not an arXiv URL`);
    }
    const match = /^\/(?:abs|pdf)\/(.+)$/.exec(url.pathname);
    if (!match) {
      fail(citekey, `"${raw}" is not an arXiv abstract or PDF URL`);
    }
    value = decodeURIComponent(match[1]).replace(/\.pdf$/i, "");
  }

  if (value.toLowerCase().startsWith("arxiv:")) {
    value = value.slice("arxiv:".length).trim();
  }

  if (!ARXIV_PATTERN.test(value)) {
    fail(citekey, `"${raw}" is not a usable arXiv identifier`);
  }
  return value;
}

/**
 * Reads the arXiv identifier of an entry, ignoring an `eprint` that belongs to
 * another preprint archive.
 */
function readArxiv(entry: BibTeXEntry, citekey: string): string | undefined {
  const eprint = stringField(entry, citekey, "eprint");
  if (eprint === undefined) {
    return undefined;
  }
  const archive =
    stringField(entry, citekey, "archiveprefix") ??
    stringField(entry, citekey, "eprinttype");
  if (archive !== undefined && archive.toLowerCase() !== "arxiv") {
    return undefined;
  }
  return normalizeArxiv(eprint, citekey);
}

function readMethods(entry: BibTeXEntry, citekey: string): string[] {
  const value = entry.fields.keywords;
  if (value === undefined) {
    fail(citekey, "has no method keyword; add one to its `keywords` field");
  }
  if (!Array.isArray(value)) {
    fail(citekey, "has an unreadable `keywords` field");
  }

  const methods = new Set<string>();
  for (const keyword of value as readonly string[]) {
    if (typeof keyword !== "string") {
      fail(citekey, "has an unreadable `keywords` field");
    }
    const method = keyword.trim();
    if (!SAFE_METHOD_PATTERN.test(method)) {
      fail(
        citekey,
        `method keyword "${keyword}" must be lowercase and hyphen-separated`,
      );
    }
    methods.add(method);
  }
  if (methods.size === 0) {
    fail(citekey, "has no method keyword; add one to its `keywords` field");
  }
  return [...methods].sort(compare);
}

function toLiteratureEntry(entry: BibTeXEntry): LiteratureEntry {
  const citekey = typeof entry.key === "string" ? entry.key.trim() : "";
  if (!SAFE_CITEKEY_PATTERN.test(citekey)) {
    throw new Error(
      `bibliography citekey ${JSON.stringify(entry.key)} is unusable: expected ${String(SAFE_CITEKEY_PATTERN)}`,
    );
  }

  const type =
    typeof entry.type === "string" ? entry.type.trim().toLowerCase() : "";
  if (!/^[a-z]+$/.test(type)) {
    fail(citekey, `has an unusable entry type ${JSON.stringify(entry.type)}`);
  }

  const title = stringField(entry, citekey, "title");
  if (title === undefined) {
    fail(citekey, "has an empty or missing title");
  }

  const year = stringField(entry, citekey, "year");
  if (year !== undefined && !YEAR_PATTERN.test(year)) {
    fail(citekey, `has a year "${year}" that is not four digits`);
  }

  const doi = stringField(entry, citekey, "doi");
  const arxiv = readArxiv(entry, citekey);

  return {
    citekey,
    type,
    title,
    authors: readAuthors(entry, citekey),
    ...(year === undefined ? {} : { year }),
    ...(doi === undefined ? {} : { doi: normalizeDoi(doi, citekey) }),
    ...(arxiv === undefined ? {} : { arxiv }),
    methods: readMethods(entry, citekey),
  };
}

/**
 * Parses BibTeX text into validated entries, in bibliography order.
 *
 * Throws on any parser diagnostic, duplicate citekey, or entry that is missing
 * the metadata the literature tree depends on.
 */
export function parseBibliography(input: string): LiteratureEntry[] {
  let parsed: BibTeXBibliography;
  try {
    // Sentence casing rewrites titles the parser believes are over-capitalized;
    // the bibliography records external titles verbatim, so it stays off.
    parsed = parseBibTeX(input, { sentenceCase: false });
  } catch (error) {
    throw new Error(
      `bibliography could not be parsed: ${error instanceof Error ? error.message : String(error)}`,
      { cause: error },
    );
  }

  if (parsed.errors.length > 0) {
    const detail = parsed.errors.map(({ error }) => error).join("; ");
    throw new Error(
      `bibliography has ${parsed.errors.length} parser error(s): ${detail}`,
    );
  }

  const entries: LiteratureEntry[] = [];
  const seen = new Set<string>();
  for (const entry of parsed.entries) {
    const normalized = toLiteratureEntry(entry);
    if (seen.has(normalized.citekey)) {
      throw new Error(
        `bibliography defines citekey "${normalized.citekey}" more than once`,
      );
    }
    seen.add(normalized.citekey);
    entries.push(normalized);
  }
  return entries;
}

/** Reads and parses a BibTeX file. */
export async function loadBibliography(
  bibliographyPath: string,
): Promise<LiteratureEntry[]> {
  let text: string;
  try {
    text = await readFile(bibliographyPath, "utf8");
  } catch (error) {
    throw new Error(
      `could not read the bibliography "${bibliographyPath}": ${error instanceof Error ? error.message : String(error)}`,
      { cause: error },
    );
  }
  try {
    return parseBibliography(text);
  } catch (error) {
    throw new Error(
      `${bibliographyPath}: ${error instanceof Error ? error.message : String(error)}`,
      { cause: error },
    );
  }
}

/** Looks one entry up by citekey, failing loudly when it is absent. */
export function findEntry(
  entries: readonly LiteratureEntry[],
  citekey: string,
): LiteratureEntry {
  const found = entries.find((entry) => entry.citekey === citekey);
  if (!found) {
    throw new Error(`no bibliography entry has the citekey "${citekey}"`);
  }
  return found;
}
