#!/usr/bin/env -S node --import tsx
/**
 * CLI for the external literature corpus.
 *
 *   literature.ts index
 *
 * `index` re-derives `literature/<method>/INDEX.md` from `literature/ref.bib`.
 * It is safe to re-run: an unchanged bibliography produces identical bytes, and
 * the command refuses rather than overwrite or delete a file it does not own.
 */

import path from "node:path";
import { fileURLToPath } from "node:url";

import { loadBibliography, writeMethodIndexes } from "../lib/literature/index.js";

const USAGE = ["usage:", "  literature.ts index"].join("\n");

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..");
const LITERATURE_ROOT = path.join(REPO_ROOT, "literature");
const BIBLIOGRAPHY = path.join(LITERATURE_ROOT, "ref.bib");

class UsageError extends Error {}

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
  process.exitCode = 1;
}
