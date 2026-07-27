/**
 * Unpacks an arXiv source archive.
 *
 * This is the only place in the repository where a third party's bytes are
 * turned into files on disk, so it is written as an adversarial parser rather
 * than as a convenience wrapper over a tar library.
 *
 * **Nothing is written until the whole archive has been read.** Every header is
 * parsed, every name is validated, every declared size is added up, and the
 * main document is chosen — all from memory — before the staging directory is
 * created. An archive whose tenth member is a symbolic link therefore leaves no
 * trace of its first nine, which is the difference between "the extractor
 * refused" and "the extractor refused halfway".
 *
 * **Only regular files and directories exist.** A symbolic link is the classic
 * way out of an extraction directory (`link -> /etc`, then `link/passwd`), a
 * hard link is the same trick against an existing file, and a device node or a
 * FIFO has no business in a paper. None of them are unpacked-and-ignored: they
 * make the archive invalid, because an archive containing one is not a paper.
 *
 * **A name is bytes until it has been proven to be a path.** The 100-byte tar
 * name field is NUL-*padded*, not NUL-*terminated*, which is why an attacker
 * can write `safe.tex\0../../etc/cron.d/pwned` and have one reader see a
 * harmless file and another see the walk. Anything after the first NUL must be
 * zero. Beyond that: no control characters, no backslash (a `..\` walk is a
 * walk on the platform that matters, and no honest arXiv source has one), no
 * absolute path, no `..` segment anywhere, and no two members that normalize to
 * the same path — because the second write would silently replace the first.
 *
 * **Every ceiling is checked against the claim, not the delivery.** A header
 * that declares 200 MiB is refused for the claim; the extractor never has to
 * allocate anything to find out that it is too big.
 *
 * **The main document is chosen or the archive is refused.** A paper with two
 * equally plausible main documents is ambiguous, and the honest response to
 * ambiguity is a refusal that names both, not a lexical tie-break that quietly
 * picks `alpha.tex` today and `Alpha.tex` after a rename.
 *
 * TeX is never compiled and an image is never converted; see `figures.ts`.
 */

import { createHash } from "node:crypto";
import { mkdir, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";

import { SAFE_CITEKEY_PATTERN } from "./bibliography.js";
import { copyFigures, type CopiedFigure, type ExtractedFile } from "./figures.js";

/**
 * What one source archive may cost. These are the ceilings a fetch runs with;
 * a caller may lower them but, by construction, never raise them.
 */
export const ARCHIVE_LIMITS = {
  compressedBytes: 100 * 1024 * 1024,
  extractedBytes: 512 * 1024 * 1024,
  singleFileBytes: 128 * 1024 * 1024,
  entries: 10_000,
} as const;

export type ArchiveLimits = { -readonly [K in keyof typeof ARCHIVE_LIMITS]: number };

export interface ExtractionResult {
  format: "tar" | "tar-gzip" | "gzip-single-tex";
  sourceRoot: string;
  mainTex: string;
  files: readonly { path: string; bytes: number; sha256: string }[];
  figures: readonly { source: string; destination: string; sha256: string }[];
}

/** Why an archive was refused. Callers branch on this, not on message text. */
export type ArchiveErrorCode =
  | "unusable-citekey"
  | "staging-not-empty"
  | "unknown-format"
  | "malformed"
  | "unsafe-member"
  | "unsupported-entry-type"
  | "limit-exceeded"
  | "no-main-tex"
  | "ambiguous-main-tex";

/** Thrown for every refusal. An archive is either fully unpacked or not at all. */
export class ArchiveError extends Error {
  readonly code: ArchiveErrorCode;

  constructor(code: ArchiveErrorCode, message: string) {
    super(message);
    this.name = "ArchiveError";
    this.code = code;
  }
}

const BLOCK = 512;

/** Offsets of the ustar header fields this parser reads. */
const NAME = { offset: 0, length: 100 } as const;
const SIZE = { offset: 124, length: 12 } as const;
const CHKSUM = { offset: 148, length: 8 } as const;
const TYPEFLAG = 156;
const MAGIC = { offset: 257, length: 5 } as const;
const PREFIX = { offset: 345, length: 155 } as const;

/** Extensions that may hold a main document. */
const TEX_EXTENSIONS: readonly string[] = [".tex", ".ltx"];

/** Basenames that name a main document, best first. */
const PREFERRED_BASENAMES: readonly string[] = ["main", "paper", "article"];

/**
 * How much of a `.tex` file is read when looking for a main document. A
 * manuscript is never this large; a `.tex` file that is has something else in
 * it, and it is not worth decoding 128 MiB to find out what.
 */
const MAIN_TEX_SCAN_BYTES = 8 * 1024 * 1024;

function compare(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function refuse(code: ArchiveErrorCode, message: string): never {
  throw new ArchiveError(code, message);
}

/**
 * Applies caller-supplied ceilings.
 *
 * Each value is the *minimum* of the request and the approved ceiling, so an
 * option object — which may one day come from a configuration file — can only
 * ever make this module more careful.
 */
function resolveLimits(requested: Partial<ArchiveLimits> | undefined): ArchiveLimits {
  const limits = { ...ARCHIVE_LIMITS } as ArchiveLimits;
  if (requested === undefined) {
    return limits;
  }
  for (const key of Object.keys(limits) as (keyof ArchiveLimits)[]) {
    const value = requested[key];
    if (value === undefined) {
      continue;
    }
    if (!Number.isSafeInteger(value) || value < 1) {
      throw new ArchiveError(
        "limit-exceeded",
        `the ${key} ceiling must be a positive whole number, not ${String(value)}`,
      );
    }
    limits[key] = Math.min(limits[key], value);
  }
  return limits;
}

function sha256(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}

// --- tar headers -----------------------------------------------------------

/** A member that survived preflight: only these two kinds ever exist. */
interface TarMember {
  path: string;
  kind: "file" | "directory";
  offset: number;
  bytes: number;
}

function isZeroBlock(block: Buffer): boolean {
  for (let index = 0; index < block.length; index += 1) {
    if (block[index] !== 0) {
      return false;
    }
  }
  return true;
}

/**
 * Reads an octal header field.
 *
 * A field whose first byte has the high bit set is GNU's base-256 extension.
 * It is refused rather than decoded: it exists to describe files larger than
 * 8 GiB, which is two orders of magnitude past every ceiling here, so the only
 * archive that needs it is one trying to smuggle a size past an octal parser.
 */
function readOctal(header: Buffer, field: { offset: number; length: number }, label: string, member: string): number {
  const bytes = header.subarray(field.offset, field.offset + field.length);
  if (bytes.length > 0 && (bytes[0] & 0x80) !== 0) {
    refuse(
      "malformed",
      `${member} declares its ${label} with the unsupported GNU base-256 encoding`,
    );
  }

  let text = "";
  for (const byte of bytes) {
    if (byte === 0 || byte === 0x20) {
      if (text === "") {
        continue;
      }
      break;
    }
    if (byte < 0x30 || byte > 0x37) {
      refuse("malformed", `${member} has a ${label} field that is not octal`);
    }
    text += String.fromCharCode(byte);
  }

  if (text === "") {
    return 0;
  }
  const value = Number.parseInt(text, 8);
  if (!Number.isSafeInteger(value) || value < 0) {
    refuse("malformed", `${member} has an unreadable ${label} field`);
  }
  return value;
}

/**
 * Reads a NUL-padded name field.
 *
 * Padding is ordinary and stays valid; *content* after the first NUL is the
 * attack, because it is the one difference between what a checking reader and
 * an extracting reader see.
 */
function readNameField(
  header: Buffer,
  field: { offset: number; length: number },
  label: string,
  member: string,
): string {
  const bytes = header.subarray(field.offset, field.offset + field.length);
  const terminator = bytes.indexOf(0);
  const used = terminator === -1 ? bytes : bytes.subarray(0, terminator);

  if (terminator !== -1) {
    for (let index = terminator; index < bytes.length; index += 1) {
      if (bytes[index] !== 0) {
        refuse(
          "unsafe-member",
          `the ${label} field of ${member} has non-zero bytes after its NUL terminator; a name is padded with NULs, never continued after one`,
        );
      }
    }
  }

  const text = used.toString("utf8");
  for (const character of text) {
    const code = character.codePointAt(0) ?? 0;
    if (code < 0x20 || code === 0x7f) {
      refuse(
        "unsafe-member",
        `the ${label} field of ${member} contains a control character`,
      );
    }
  }
  return text;
}

/**
 * Turns a member name into a relative POSIX path, or refuses it.
 *
 * The checks are ordered from "not a path at all" to "a path somewhere else",
 * so the message names the first thing that is wrong rather than the last.
 */
function safeMemberPath(rawPath: string): string {
  const quoted = `member "${rawPath}"`;
  if (rawPath === "") {
    refuse("unsafe-member", "a member has an empty name");
  }
  if (rawPath.includes("\\")) {
    refuse(
      "unsafe-member",
      `${quoted} contains a backslash; a source archive names its files with "/" only`,
    );
  }
  if (rawPath.startsWith("/")) {
    refuse("unsafe-member", `${quoted} is an absolute path`);
  }
  if (/^[A-Za-z]:/.test(rawPath)) {
    refuse("unsafe-member", `${quoted} is an absolute path with a drive letter`);
  }

  const segments: string[] = [];
  for (const segment of rawPath.split("/")) {
    if (segment === "" || segment === ".") {
      continue;
    }
    if (segment === "..") {
      refuse(
        "unsafe-member",
        `${quoted} walks out of the archive with a ".." segment`,
      );
    }
    segments.push(segment);
  }
  if (segments.length === 0) {
    refuse("unsafe-member", `${quoted} names no file`);
  }
  return segments.join("/");
}

/** The refusal for every entry type that is not a regular file or a directory. */
function refuseEntryType(typeflag: string, member: string): never {
  const described: Record<string, string> = {
    "1": "a hard link",
    "2": "a symbolic link",
    "3": "a character device",
    "4": "a block device",
    "6": "a FIFO",
    "7": "a contiguous file",
  };
  if (typeflag === "x" || typeflag === "g" || typeflag === "L" || typeflag === "K") {
    refuse(
      "unsupported-entry-type",
      `${member} is an extended header (type "${typeflag}"); an extended header can rewrite the name of the member after it, so an archive that uses one is refused rather than partly understood`,
    );
  }
  const what = described[typeflag];
  refuse(
    "unsupported-entry-type",
    what === undefined
      ? `${member} has the unsupported entry type "${typeflag}"; only regular files and directories are unpacked`
      : `${member} is ${what}; only regular files and directories are unpacked`,
  );
}

/** Whether a buffer opens with something that claims to be a tar header. */
function looksLikeTar(bytes: Buffer): boolean {
  if (bytes.length < BLOCK) {
    return false;
  }
  // POSIX writes "ustar\0" + "00"; GNU writes "ustar  \0". Both start "ustar".
  return bytes.subarray(MAGIC.offset, MAGIC.offset + MAGIC.length).toString("latin1") === "ustar";
}

/**
 * Reads every header of a tar archive without writing anything.
 *
 * Returns the members in archive order. Throws on the first thing that is
 * wrong, which is also the last thing that happens.
 */
function readTarMembers(tar: Buffer, limits: ArchiveLimits): TarMember[] {
  const members: TarMember[] = [];
  const seen = new Set<string>();
  let offset = 0;
  let count = 0;
  let total = 0;
  let terminated = false;

  while (offset + BLOCK <= tar.length) {
    const header = tar.subarray(offset, offset + BLOCK);
    if (isZeroBlock(header)) {
      terminated = true;
      break;
    }

    count += 1;
    if (count > limits.entries) {
      refuse(
        "limit-exceeded",
        `the archive holds more than ${limits.entries} entries`,
      );
    }

    const label = `entry ${count}`;
    const stored = readOctal(header, CHKSUM, "checksum", label);
    let unsigned = 0;
    let signed = 0;
    for (let index = 0; index < BLOCK; index += 1) {
      const inChecksum = index >= CHKSUM.offset && index < CHKSUM.offset + CHKSUM.length;
      const byte = inChecksum ? 0x20 : header[index];
      unsigned += byte;
      signed += byte > 127 ? byte - 256 : byte;
    }
    if (stored !== unsigned && stored !== signed) {
      refuse(
        "malformed",
        `${label} has a header checksum of ${stored} where the header sums to ${unsigned}`,
      );
    }

    const name = readNameField(header, NAME, "name", label);
    const prefix = readNameField(header, PREFIX, "prefix", label);
    const memberPath = safeMemberPath(prefix === "" ? name : `${prefix}/${name}`);
    const member = `member "${memberPath}"`;

    const typeflag = String.fromCharCode(header[TYPEFLAG]);
    const kind =
      typeflag === "0" || typeflag === "\0" ? "file" : typeflag === "5" ? "directory" : undefined;
    if (kind === undefined) {
      refuseEntryType(typeflag, member);
    }

    if (seen.has(memberPath)) {
      refuse(
        "unsafe-member",
        `${member} appears twice; the second copy would silently replace the first`,
      );
    }
    seen.add(memberPath);

    const size = readOctal(header, SIZE, "size", member);
    if (kind === "directory" && size !== 0) {
      refuse("malformed", `${member} is a directory that declares ${size} bytes of content`);
    }
    if (size > limits.singleFileBytes) {
      refuse(
        "limit-exceeded",
        `${member} declares ${size} bytes, over the ${limits.singleFileBytes}-byte single-file ceiling`,
      );
    }
    total += size;
    if (total > limits.extractedBytes) {
      refuse(
        "limit-exceeded",
        `the archive declares at least ${total} bytes in total, over the ${limits.extractedBytes}-byte extracted ceiling`,
      );
    }

    const content = offset + BLOCK;
    if (content + size > tar.length) {
      refuse("malformed", `the archive ends inside the content of ${member}`);
    }
    if (kind === "file") {
      members.push({ path: memberPath, kind, offset: content, bytes: size });
    } else {
      members.push({ path: memberPath, kind, offset: content, bytes: 0 });
    }

    offset = content + Math.ceil(size / BLOCK) * BLOCK;
  }

  if (!terminated) {
    refuse("malformed", "the archive is truncated: it has no end-of-archive marker");
  }
  return members;
}

// --- format detection ------------------------------------------------------

/** Removes TeX comments so a commented-out preamble is not read as one. */
function stripTexComments(text: string): string {
  return text.replace(/(^|[^\\])%[^\n]*/g, "$1");
}

/** Whether a decoded TeX file is a main document rather than an input. */
function isMainDocument(text: string): boolean {
  const stripped = stripTexComments(text);
  return /\\documentclass/.test(stripped) && /\\begin\s*\{\s*document\s*\}/.test(stripped);
}

function hasTexExtension(relativePath: string): boolean {
  return TEX_EXTENSIONS.includes(path.posix.extname(relativePath).toLowerCase());
}

/** The archive as it arrived, decompressed if it needed to be. */
type DecodedArchive =
  | { format: "tar" | "tar-gzip"; tar: Buffer }
  | { format: "gzip-single-tex"; tex: Buffer };

function decodeArchive(archive: Buffer, limits: ArchiveLimits): DecodedArchive {
  if (archive.length >= 2 && archive[0] === 0x1f && archive[1] === 0x8b) {
    let inflated: Buffer;
    try {
      // The ceiling is enforced by zlib itself, so a stream that expands a
      // thousandfold is stopped while it decompresses rather than after.
      inflated = gunzipSync(archive, { maxOutputLength: limits.extractedBytes });
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ERR_BUFFER_TOO_LARGE") {
        refuse(
          "limit-exceeded",
          `the gzip stream decompresses to more than the ${limits.extractedBytes}-byte extracted ceiling`,
        );
      }
      refuse(
        "malformed",
        `the gzip stream could not be decompressed: ${error instanceof Error ? error.message : String(error)}`,
      );
    }

    if (looksLikeTar(inflated)) {
      return { format: "tar-gzip", tar: inflated };
    }
    if (inflated.includes(0) || !isMainDocument(inflated.toString("latin1"))) {
      refuse(
        "unknown-format",
        "the download is a gzip stream that holds neither a tar archive nor a LaTeX document",
      );
    }
    return { format: "gzip-single-tex", tex: inflated };
  }

  if (looksLikeTar(archive)) {
    return { format: "tar", tar: archive };
  }
  refuse(
    "unknown-format",
    "the download is neither a tar archive nor a gzip stream; arXiv source is one or the other",
  );
}

// --- main document ---------------------------------------------------------

interface MainTexCandidate {
  path: string;
  rank: number;
  depth: number;
}

/**
 * Ranks a candidate by what its name says it is.
 *
 * The order is the same one a human reads a source tree with: a file called
 * `main` is the paper, then `paper`, then `article`, then a file named after
 * the citekey (arXiv authors do upload `smith_2020_model.tex`), then anything
 * else that happens to be a document.
 */
function rankCandidate(relativePath: string, citekey: string): number {
  const base = path.posix
    .basename(relativePath)
    .replace(/\.(?:tex|ltx)$/i, "")
    .toLowerCase();
  const preferred = PREFERRED_BASENAMES.indexOf(base);
  if (preferred !== -1) {
    return preferred;
  }
  return base === citekey.toLowerCase()
    ? PREFERRED_BASENAMES.length
    : PREFERRED_BASENAMES.length + 1;
}

/**
 * Chooses the main document, or refuses the archive.
 *
 * Depth is the second key because a nested copy of `main.tex` is a supplement
 * or a leftover, never the manuscript. Lexical order is used only to print the
 * candidates of an ambiguity: picking the alphabetically first of two equally
 * ranked documents would be a guess dressed up as a rule.
 */
export function selectMainTex(
  candidates: readonly MainTexCandidate[],
): string {
  if (candidates.length === 0) {
    refuse(
      "no-main-tex",
      "the archive holds no LaTeX file with both \\documentclass and \\begin{document}, so it has no main document",
    );
  }

  const ordered = [...candidates].sort(
    (a, b) => a.rank - b.rank || a.depth - b.depth || compare(a.path, b.path),
  );
  const best = ordered[0];
  const tied = ordered.filter(
    (candidate) => candidate.rank === best.rank && candidate.depth === best.depth,
  );
  if (tied.length > 1) {
    refuse(
      "ambiguous-main-tex",
      `the archive has ${tied.length} equally ranked main documents (${tied
        .map((candidate) => candidate.path)
        .sort(compare)
        .join(", ")}); name one of them main.tex upstream rather than have this pick for you`,
    );
  }
  return best.path;
}

// --- extraction ------------------------------------------------------------

/** Creates a staging directory, refusing to unpack into one that holds files. */
async function takeStagingDirectory(directory: string): Promise<string> {
  const resolved = path.resolve(directory);
  await mkdir(resolved, { recursive: true, mode: 0o755 });
  const existing = await readdir(resolved);
  if (existing.length > 0) {
    refuse(
      "staging-not-empty",
      `the staging directory "${resolved}" already holds ${existing.length} entr${existing.length === 1 ? "y" : "ies"}; extraction never writes into a directory it does not own`,
    );
  }
  return resolved;
}

/** The destination of one member, re-checked against the staging root. */
function destinationOf(root: string, relativePath: string): string {
  const destination = path.resolve(root, relativePath);
  if (destination !== root && !destination.startsWith(root + path.sep)) {
    refuse(
      "unsafe-member",
      `member "${relativePath}" resolves to "${destination}", outside the staging directory`,
    );
  }
  return destination;
}

export interface ExtractSourceArchiveOptions {
  /** The downloaded bytes, exactly as they arrived. */
  archive: Uint8Array;
  /** Used to rank a main document named after the reference. */
  citekey: string;
  /** Staging directory for the extracted tree; must be empty or absent. */
  sourceDir: string;
  /** Staging directory for the figures; must be empty or absent. */
  figuresDir: string;
  /** Lower ceilings than the approved ones. Higher values are ignored. */
  limits?: Partial<ArchiveLimits>;
}

/**
 * Unpacks one source archive into caller-provided staging directories.
 *
 * The order is the contract: validate the request, decode the container, read
 * every header, choose the main document, and only then create a directory.
 */
export async function extractSourceArchive(
  options: ExtractSourceArchiveOptions,
): Promise<ExtractionResult> {
  if (!SAFE_CITEKEY_PATTERN.test(options.citekey)) {
    refuse("unusable-citekey", `"${options.citekey}" is not a usable citekey`);
  }
  const limits = resolveLimits(options.limits);

  const archive = Buffer.from(
    options.archive.buffer,
    options.archive.byteOffset,
    options.archive.byteLength,
  );
  if (archive.length > limits.compressedBytes) {
    refuse(
      "limit-exceeded",
      `the download is ${archive.length} bytes, over the ${limits.compressedBytes}-byte compressed ceiling`,
    );
  }

  const decoded = decodeArchive(archive, limits);

  // Preflight: everything below happens in memory.
  const members =
    decoded.format === "gzip-single-tex"
      ? [{ path: "main.tex", kind: "file" as const, offset: 0, bytes: decoded.tex.length }]
      : readTarMembers(decoded.tar, limits);
  const content = decoded.format === "gzip-single-tex" ? decoded.tex : decoded.tar;

  const candidates: MainTexCandidate[] = [];
  for (const member of members) {
    if (member.kind !== "file" || !hasTexExtension(member.path) || member.bytes > MAIN_TEX_SCAN_BYTES) {
      continue;
    }
    const text = content.subarray(member.offset, member.offset + member.bytes).toString("latin1");
    if (isMainDocument(text)) {
      candidates.push({
        path: member.path,
        rank: rankCandidate(member.path, options.citekey),
        depth: member.path.split("/").length - 1,
      });
    }
  }
  const mainTex = selectMainTex(candidates);

  // The archive is known good; now, and only now, touch the filesystem.
  const sourceRoot = await takeStagingDirectory(options.sourceDir);
  const figuresRoot = await takeStagingDirectory(options.figuresDir);

  const files: ExtractedFile[] = [];
  for (const member of members) {
    const destination = destinationOf(sourceRoot, member.path);
    if (member.kind === "directory") {
      await mkdir(destination, { recursive: true, mode: 0o755 });
      continue;
    }
    const bytes = content.subarray(member.offset, member.offset + member.bytes);
    await mkdir(path.dirname(destination), { recursive: true, mode: 0o755 });
    // The archive's mode is deliberately ignored: nothing unpacked from a
    // download is executable, setuid, or writable by anyone else.
    await writeFile(destination, bytes, { mode: 0o644 });
    files.push({ path: member.path, bytes: member.bytes, sha256: sha256(bytes) });
  }
  files.sort((a, b) => compare(a.path, b.path));

  const figures: readonly CopiedFigure[] = await copyFigures({
    sourceRoot,
    figuresRoot,
    files,
  });

  return { format: decoded.format, sourceRoot, mainTex, files, figures };
}
