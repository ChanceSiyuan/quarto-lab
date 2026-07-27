/**
 * Fetches the source material of one bibliography entry, or of all of them.
 *
 * What lands on disk is the evidence itself — the archive arXiv served, the
 * tree inside it, the typeset PDF, and a manifest describing all three. There
 * is deliberately no rendered Markdown, no extracted plain text, and no summary
 * anywhere in this module: a lossy transcription of a paper is the thing an
 * agent would later quote as if it were the paper.
 *
 * Three properties are worth reading the code for.
 *
 * **A version is pinned once.** The order is: an explicit `vN` in the
 * bibliography, then the version already pinned on disk, then — only if neither
 * exists — what the arXiv API currently reports. A local pin is never quietly
 * replaced: if the bibliography moves from `v2` to `v9` the fetch stops and
 * says so, because "the paper changed under the note that cites it" is a fact a
 * human has to see, not a download to perform. Re-pinning is a refresh feature,
 * and there isn't one yet.
 *
 * **A fetch either happens completely or not at all.** Everything is built
 * under `literature/.staging/<uuid>`: the response, the extracted tree, the
 * PDF, the manifest, and one copy per method directory the entry belongs to.
 * Only when all of that exists is anything swapped in, and a swap moves the old
 * directory aside first so a failure can put it back. A failed download, a
 * malicious archive, or a rename that loses a race therefore leaves the
 * previous `.raw/<citekey>` and `.figures/<citekey>` byte for byte as they
 * were, and the staging tree is removed either way.
 *
 * **A reference filed under two methods is one download.** `weinberg_2016_quspin`
 * is both `ed` and `software`; it is fetched once and materialized into both
 * method directories as identical bytes, verified against the same manifest.
 * Not a symbolic link: `.raw/` is local-only data, and a link is a path that
 * outlives what it points at.
 */

import { createHash, randomUUID } from "node:crypto";
import { cp, mkdir, readFile, rename, rm, rmdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  ARCHIVE_LIMITS,
  ArchiveError,
  extractSourceArchive,
  type ExtractionResult,
} from "./archive.js";
import {
  ArxivError,
  arxivPdfUrl,
  arxivSourceUrl,
  downloadBounded,
  resolveLatestArxivVersion,
  splitArxivIdentifier,
} from "./arxiv.js";
import {
  SAFE_CITEKEY_PATTERN,
  SAFE_METHOD_PATTERN,
  loadBibliography,
  type LiteratureEntry,
} from "./bibliography.js";

/** The bibliography, relative to the literature root. */
const BIBLIOGRAPHY_FILENAME = "ref.bib";

/** Where a fetch is assembled before any of it is published. Gitignored. */
const STAGING_DIRECTORY = ".staging";

/** The two local-only trees of a method directory. Both are gitignored. */
const RAW_DIRECTORY = ".raw";
const FIGURES_DIRECTORY = ".figures";

/** What one `.raw/<citekey>` directory holds. */
const MANIFEST_FILENAME = "manifest.json";
const SOURCE_ARCHIVE_FILENAME = "source.tar.gz";
const SOURCE_TREE_DIRECTORY = "source";
const PDF_FILENAME = "paper.pdf";

/**
 * What was fetched, and what it hashes to.
 *
 * There is no timestamp in here, on purpose: re-fetching the same pinned
 * version writes the same bytes, so a manifest can be compared, and a
 * difference means the content differs rather than that the clock moved.
 */
export interface LiteratureManifest {
  schemaVersion: 1;
  citekey: string;
  arxiv: { id: string; version: string };
  source: { url: string; bytes: number; sha256: string };
  pdf: { url: string; bytes: number; sha256: string };
  extraction: {
    format: ExtractionResult["format"];
    mainTex: string;
    files: ExtractionResult["files"];
    figures: ExtractionResult["figures"];
  };
}

export type LiteratureFetchErrorCode =
  | "unknown-citekey"
  | "no-arxiv"
  | "pin-conflict"
  | "pinned-version-changed"
  | "download-failed"
  | "unusable-source"
  | "unusable-pdf"
  | "swap-failed";

/** Thrown for every refusal; the cause carries the layer that refused. */
export class LiteratureFetchError extends Error {
  readonly code: LiteratureFetchErrorCode;

  constructor(
    code: LiteratureFetchErrorCode,
    message: string,
    options?: { cause?: unknown },
  ) {
    super(message, options);
    this.name = "LiteratureFetchError";
    this.code = code;
  }
}

function sha256(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function compare(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

async function pathExists(target: string): Promise<boolean> {
  try {
    await stat(target);
    return true;
  } catch {
    return false;
  }
}

/** Where one entry lives, once per method keyword, in method order. */
interface Destination {
  method: string;
  raw: string;
  figures: string;
}

function destinationsOf(literatureRoot: string, entry: LiteratureEntry): Destination[] {
  if (!SAFE_CITEKEY_PATTERN.test(entry.citekey)) {
    throw new LiteratureFetchError(
      "unknown-citekey",
      `"${entry.citekey}" is not a usable citekey`,
    );
  }
  return [...entry.methods].sort(compare).map((method) => {
    if (!SAFE_METHOD_PATTERN.test(method)) {
      throw new LiteratureFetchError(
        "unknown-citekey",
        `"${entry.citekey}" carries the unusable method keyword "${method}"`,
      );
    }
    return {
      method,
      raw: path.join(literatureRoot, method, RAW_DIRECTORY, entry.citekey),
      figures: path.join(literatureRoot, method, FIGURES_DIRECTORY, entry.citekey),
    };
  });
}

/** Canonical JSON: two-space indent, one trailing newline, fixed key order. */
function serializeManifest(manifest: LiteratureManifest): string {
  return `${JSON.stringify(manifest, null, 2)}\n`;
}

/**
 * Reads a manifest, treating anything unreadable as absent.
 *
 * A truncated or foreign manifest is not a reason to refuse: it is a reason to
 * fetch again and replace it. What it is *not* allowed to do is contribute a
 * version pin, which is why the identifier and citekey are checked here.
 */
async function readManifest(
  rawDirectory: string,
  entry: LiteratureEntry,
  id: string,
): Promise<LiteratureManifest | undefined> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(await readFile(path.join(rawDirectory, MANIFEST_FILENAME), "utf8"));
  } catch {
    return undefined;
  }
  if (typeof parsed !== "object" || parsed === null) {
    return undefined;
  }
  const manifest = parsed as LiteratureManifest;
  if (
    manifest.schemaVersion !== 1 ||
    manifest.citekey !== entry.citekey ||
    typeof manifest.arxiv !== "object" ||
    manifest.arxiv === null ||
    manifest.arxiv.id !== id ||
    typeof manifest.arxiv.version !== "string" ||
    !/^v[1-9]\d*$/.test(manifest.arxiv.version) ||
    typeof manifest.source?.sha256 !== "string" ||
    typeof manifest.pdf?.sha256 !== "string" ||
    typeof manifest.extraction?.mainTex !== "string"
  ) {
    return undefined;
  }
  return manifest;
}

async function fileMatches(
  file: string,
  expected: { bytes: number; sha256: string },
): Promise<boolean> {
  let bytes: Buffer;
  try {
    bytes = await readFile(file);
  } catch {
    return false;
  }
  return bytes.length === expected.bytes && sha256(bytes) === expected.sha256;
}

/**
 * Whether one method directory already holds the whole fetch.
 *
 * The archive and the PDF are re-digested rather than merely counted, because
 * "the same verified bytes are in every method directory" is the promise a
 * shared download makes, and only a digest keeps it.
 */
async function isComplete(
  destination: Destination,
  manifest: LiteratureManifest,
): Promise<boolean> {
  if (!(await fileMatches(path.join(destination.raw, SOURCE_ARCHIVE_FILENAME), manifest.source))) {
    return false;
  }
  if (!(await fileMatches(path.join(destination.raw, PDF_FILENAME), manifest.pdf))) {
    return false;
  }
  if (
    !(await pathExists(
      path.join(destination.raw, SOURCE_TREE_DIRECTORY, manifest.extraction.mainTex),
    ))
  ) {
    return false;
  }
  for (const figure of manifest.extraction.figures) {
    if (!(await pathExists(path.join(destination.figures, figure.destination)))) {
      return false;
    }
  }
  return true;
}

/** One directory move, with the displaced directory kept until the end. */
interface CompletedSwap {
  destination: string;
  backup?: string;
}

/**
 * Moves every staged directory into place, or puts everything back.
 *
 * Each destination is displaced to a sibling backup first, so both renames stay
 * inside one directory and therefore inside one filesystem. If any step fails,
 * every completed step is undone in reverse before the failure is reported: a
 * reference filed under two methods must never end up half-updated.
 */
async function swapIntoPlace(
  swaps: readonly { from: string; to: string }[],
): Promise<void> {
  const completed: CompletedSwap[] = [];
  try {
    for (const swap of swaps) {
      await mkdir(path.dirname(swap.to), { recursive: true });
      const backup = path.join(
        path.dirname(swap.to),
        `.${path.basename(swap.to)}-replaced-${randomUUID()}`,
      );
      const displaced = await pathExists(swap.to);
      if (displaced) {
        await rename(swap.to, backup);
      }
      try {
        await rename(swap.from, swap.to);
      } catch (error) {
        if (displaced) {
          await rename(backup, swap.to);
        }
        throw error;
      }
      completed.push(displaced ? { destination: swap.to, backup } : { destination: swap.to });
    }
  } catch (error) {
    for (const step of [...completed].reverse()) {
      try {
        await rm(step.destination, { recursive: true, force: true });
        if (step.backup !== undefined) {
          await rename(step.backup, step.destination);
        }
      } catch {
        // A rollback that cannot finish must not replace the original failure.
      }
    }
    throw new LiteratureFetchError(
      "swap-failed",
      `the fetched source could not be moved into place: ${error instanceof Error ? error.message : String(error)}`,
      { cause: error },
    );
  }

  // Nothing points at the displaced directories any more.
  for (const step of completed) {
    if (step.backup !== undefined) {
      await rm(step.backup, { recursive: true, force: true });
    }
  }
}

/**
 * Downloads one artifact under the compressed-source ceiling.
 *
 * No `Accept` is sent: arXiv labels e-print bodies with several media types
 * depending on how the submission was packaged, and a narrow `Accept` is a way
 * to be refused a file that would have been perfectly usable.
 */
async function download(url: string, fetchImpl?: typeof fetch): Promise<Buffer> {
  try {
    return await downloadBounded({
      url,
      maxBytes: ARCHIVE_LIMITS.compressedBytes,
      ...(fetchImpl === undefined ? {} : { fetchImpl }),
    });
  } catch (error) {
    if (error instanceof ArxivError) {
      throw new LiteratureFetchError("download-failed", error.message, { cause: error });
    }
    throw error;
  }
}

/** What one entry cost: either the network, or nothing at all. */
interface FetchOutcome {
  manifest: LiteratureManifest;
  reused: boolean;
}

async function fetchEntry(options: {
  literatureRoot: string;
  entry: LiteratureEntry;
  fetchImpl?: typeof fetch;
}): Promise<FetchOutcome> {
  const { entry } = options;
  const literatureRoot = path.resolve(options.literatureRoot);

  if (entry.arxiv === undefined) {
    throw new LiteratureFetchError(
      "no-arxiv",
      `"${entry.citekey}" has no arXiv identifier, so it has no source material to fetch`,
    );
  }
  const { id, version: explicit } = splitArxivIdentifier(entry.arxiv);
  const destinations = destinationsOf(literatureRoot, entry);

  // 1. What is already here, and what does it pin?
  const existing = await Promise.all(
    destinations.map(async (destination) => ({
      destination,
      manifest: await readManifest(destination.raw, entry, id),
    })),
  );
  const pins = [
    ...new Set(
      existing
        .map(({ manifest }) => manifest?.arxiv.version)
        .filter((version): version is string => version !== undefined),
    ),
  ].sort(compare);
  if (pins.length > 1) {
    throw new LiteratureFetchError(
      "pin-conflict",
      `"${entry.citekey}" is pinned to ${pins.join(" and ")} in different method directories; remove the local copies and fetch again`,
    );
  }
  const pinned = pins[0];

  // 2. Resolve the version, in the approved order.
  let version: string;
  if (explicit !== undefined) {
    version = explicit;
  } else if (pinned !== undefined) {
    version = pinned;
  } else {
    try {
      version = await resolveLatestArxivVersion({
        id,
        ...(options.fetchImpl === undefined ? {} : { fetchImpl: options.fetchImpl }),
      });
    } catch (error) {
      if (error instanceof ArxivError) {
        throw new LiteratureFetchError("download-failed", error.message, { cause: error });
      }
      throw error;
    }
  }
  if (pinned !== undefined && pinned !== version) {
    throw new LiteratureFetchError(
      "pinned-version-changed",
      `"${entry.citekey}" is pinned locally to ${pinned} but the bibliography now asks for ${version}; delete the local ${RAW_DIRECTORY}/${entry.citekey} directories to move the pin deliberately`,
    );
  }

  // 3. Reuse when every method directory already holds this exact fetch.
  const complete = await Promise.all(
    existing.map(async ({ destination, manifest }) =>
      manifest !== undefined &&
      manifest.arxiv.version === version &&
      (await isComplete(destination, manifest)),
    ),
  );
  if (complete.every(Boolean)) {
    const manifest = existing[0].manifest;
    if (manifest !== undefined) {
      return { manifest, reused: true };
    }
  }

  // 4. Build the whole thing in staging.
  const stagingRoot = path.join(literatureRoot, STAGING_DIRECTORY);
  const staging = path.join(stagingRoot, randomUUID());
  try {
    const rawStage = path.join(staging, "raw");
    const figuresStage = path.join(staging, "figures");
    await mkdir(rawStage, { recursive: true });

    const sourceUrl = arxivSourceUrl({ id, version });
    const sourceBytes = await download(sourceUrl, options.fetchImpl);
    await writeFile(path.join(rawStage, SOURCE_ARCHIVE_FILENAME), sourceBytes);

    let extraction: ExtractionResult;
    try {
      extraction = await extractSourceArchive({
        archive: sourceBytes,
        citekey: entry.citekey,
        sourceDir: path.join(rawStage, SOURCE_TREE_DIRECTORY),
        figuresDir: figuresStage,
      });
    } catch (error) {
      if (error instanceof ArchiveError) {
        throw new LiteratureFetchError(
          "unusable-source",
          `the source archive of "${entry.citekey}" (${sourceUrl}) could not be unpacked: ${error.message}`,
          { cause: error },
        );
      }
      throw error;
    }

    const pdfUrl = arxivPdfUrl({ id, version });
    const pdfBytes = await download(pdfUrl, options.fetchImpl);
    if (pdfBytes.subarray(0, 5).toString("latin1") !== "%PDF-") {
      throw new LiteratureFetchError(
        "unusable-pdf",
        `"${pdfUrl}" did not answer with a PDF; arXiv serves an HTML notice while a PDF is still being built, so try again later`,
      );
    }
    await writeFile(path.join(rawStage, PDF_FILENAME), pdfBytes);

    const manifest: LiteratureManifest = {
      schemaVersion: 1,
      citekey: entry.citekey,
      arxiv: { id, version },
      source: { url: sourceUrl, bytes: sourceBytes.length, sha256: sha256(sourceBytes) },
      pdf: { url: pdfUrl, bytes: pdfBytes.length, sha256: sha256(pdfBytes) },
      extraction: {
        format: extraction.format,
        mainTex: extraction.mainTex,
        files: extraction.files,
        figures: extraction.figures,
      },
    };
    await writeFile(
      path.join(rawStage, MANIFEST_FILENAME),
      serializeManifest(manifest),
      "utf8",
    );

    // 5. One staged copy per method directory, so every swap is a rename.
    const swaps: { from: string; to: string }[] = [];
    for (const destination of destinations) {
      const methodStage = path.join(staging, "methods", destination.method);
      await mkdir(methodStage, { recursive: true });
      await cp(rawStage, path.join(methodStage, "raw"), {
        recursive: true,
        dereference: false,
        preserveTimestamps: false,
      });
      await cp(figuresStage, path.join(methodStage, "figures"), {
        recursive: true,
        dereference: false,
        preserveTimestamps: false,
      });
      swaps.push(
        { from: path.join(methodStage, "raw"), to: destination.raw },
        { from: path.join(methodStage, "figures"), to: destination.figures },
      );
    }

    await swapIntoPlace(swaps);
    return { manifest, reused: false };
  } finally {
    await rm(staging, { recursive: true, force: true });
    try {
      await rmdir(stagingRoot);
    } catch {
      // Another fetch is still using it, or it was never created.
    }
  }
}

/**
 * Fetches the pinned source material of one bibliography entry.
 *
 * Returns the manifest, whether it was downloaded now or already on disk.
 */
export async function fetchLiteratureEntry(options: {
  literatureRoot: string;
  citekey: string;
  fetchImpl?: typeof fetch;
}): Promise<LiteratureManifest> {
  const entries = await loadBibliography(
    path.join(options.literatureRoot, BIBLIOGRAPHY_FILENAME),
  );
  const entry = entries.find((candidate) => candidate.citekey === options.citekey);
  if (entry === undefined) {
    throw new LiteratureFetchError(
      "unknown-citekey",
      `the bibliography has no entry with the citekey "${options.citekey}"`,
    );
  }
  const outcome = await fetchEntry({
    literatureRoot: options.literatureRoot,
    entry,
    ...(options.fetchImpl === undefined ? {} : { fetchImpl: options.fetchImpl }),
  });
  return outcome.manifest;
}

/**
 * Fetches every entry that has arXiv source material, in citekey order.
 *
 * Entries without a preprint are counted rather than skipped silently — the
 * difference between "65 of 85 have source" and "20 failed" is exactly what an
 * operator needs to know. Any real failure stops the run; re-running is cheap,
 * because everything already fetched is reused.
 */
export async function syncLiterature(options: {
  literatureRoot: string;
  fetchImpl?: typeof fetch;
}): Promise<{ fetched: number; reused: number; skippedNoArxiv: number }> {
  const entries = [
    ...(await loadBibliography(path.join(options.literatureRoot, BIBLIOGRAPHY_FILENAME))),
  ].sort((a, b) => compare(a.citekey, b.citekey));

  let fetched = 0;
  let reused = 0;
  let skippedNoArxiv = 0;
  for (const entry of entries) {
    if (entry.arxiv === undefined) {
      skippedNoArxiv += 1;
      continue;
    }
    const outcome = await fetchEntry({
      literatureRoot: options.literatureRoot,
      entry,
      ...(options.fetchImpl === undefined ? {} : { fetchImpl: options.fetchImpl }),
    });
    if (outcome.reused) {
      reused += 1;
    } else {
      fetched += 1;
    }
  }
  return { fetched, reused, skippedNoArxiv };
}
