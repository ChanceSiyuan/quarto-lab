#!/usr/bin/env -S node --import tsx
/**
 * CLI for the external literature corpus.
 *
 *   literature.ts index
 *   literature.ts fetch --key <citekey>
 *   literature.ts sync
 *
 * `index` re-derives `literature/<method>/INDEX.md` from `literature/ref.bib`.
 * It is safe to re-run: an unchanged bibliography produces identical bytes, and
 * the command refuses rather than overwrite or delete a file it does not own.
 *
 * `fetch` downloads the pinned arXiv source and PDF of one reference into the
 * gitignored `.raw/` and `.figures/` trees of every method directory it belongs
 * to. `sync` does the same for the whole bibliography, in citekey order.
 * Neither command ever writes into the bibliography, an `INDEX.md`, or anything
 * Git tracks, and neither compiles the LaTeX it downloads.
 *
 * Exit codes: 0 when the material is in place, 2 when the citekey is not in the
 * bibliography, and 1 for everything else — an unreadable bibliography, a
 * refused archive, or arXiv being unreachable.
 */

import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  LiteratureFetchError,
  fetchLiteratureEntry,
  loadBibliography,
  syncLiterature,
  writeMethodIndexes,
} from "../../../src/lib/literature/index.js";

const USAGE = [
  "usage:",
  "  literature.ts index",
  "  literature.ts fetch --key <citekey>",
  "  literature.ts sync",
].join("\n");

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..", "..");
const LITERATURE_ROOT = path.join(REPO_ROOT, "literature");
const BIBLIOGRAPHY = path.join(LITERATURE_ROOT, "ref.bib");

class UsageError extends Error {}

/** Reads `--key <citekey>`, the only option any subcommand takes. */
function readKeyOption(rest: readonly string[]): string {
  if (rest.length !== 2 || rest[0] !== "--key") {
    throw new UsageError("fetch takes exactly one option: --key <citekey>");
  }
  const citekey = rest[1];
  if (citekey === undefined || citekey.startsWith("-") || citekey.trim() === "") {
    throw new UsageError("--key needs a citekey");
  }
  return citekey;
}

async function main(argv: readonly string[]): Promise<void> {
  const [command, ...rest] = argv;

  switch (command) {
    case "index": {
      if (rest.length > 0) {
        throw new UsageError("index takes no arguments");
      }
      const entries = await loadBibliography(BIBLIOGRAPHY);
      const written = await writeMethodIndexes(LITERATURE_ROOT, entries);
      const arxiv = entries.filter((entry) => entry.arxiv !== undefined).length;
      console.log(
        `${entries.length} bibliography entries; ${written.length} method indexes; ${arxiv} arXiv entries`,
      );
      return;
    }
    case "fetch": {
      const citekey = readKeyOption(rest);
      const manifest = await fetchLiteratureEntry({
        literatureRoot: LITERATURE_ROOT,
        citekey,
      });
      console.log(
        `${manifest.citekey}: arXiv ${manifest.arxiv.id}${manifest.arxiv.version}; ` +
          `${manifest.extraction.files.length} source files, ${manifest.extraction.figures.length} figures; ` +
          `main document ${manifest.extraction.mainTex}`,
      );
      return;
    }
    case "sync": {
      if (rest.length > 0) {
        throw new UsageError("sync takes no arguments");
      }
      const counts = await syncLiterature({ literatureRoot: LITERATURE_ROOT });
      const total = counts.fetched + counts.reused + counts.skippedNoArxiv;
      console.log(
        `${total} bibliography entries; ${counts.fetched} fetched, ${counts.reused} already present, ` +
          `${counts.skippedNoArxiv} without arXiv source`,
      );
      return;
    }
    case undefined:
      throw new UsageError("a subcommand is required");
    default:
      throw new UsageError(`unknown subcommand "${command}"`);
  }
}

try {
  await main(process.argv.slice(2));
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(
    error instanceof UsageError
      ? `literature: ${message}\n${USAGE}`
      : `literature: ${message}`,
  );
  process.exitCode =
    error instanceof LiteratureFetchError && error.code === "unknown-citekey" ? 2 : 1;
}
