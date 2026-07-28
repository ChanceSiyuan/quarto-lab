#!/usr/bin/env -S node --import tsx
/** Stable QLab-compatible CLI used by the Zotero add-on. */

import { rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  LiteratureFetchError,
  fetchLiteratureEntry,
  loadBibliography,
  syncLiterature,
  writeMethodIndexes,
} from "../lib/literature/index.js";
import { materializeZoteroRecord, verifyZoteroRecord } from "../lib/literature/zotero-materialize.js";
import { ZoteroClient, importZoteroSnapshot } from "../lib/literature/zotero.js";

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..");

const HELP = `Research Loop literature commands:
  ./qlab literature connect zotero
  ./qlab literature import zotero [--rehome-metadata-only]
  ./qlab literature materialize <item-key>
  ./qlab literature verify <item-key>
  ./qlab literature index
  ./qlab literature fetch <citekey>
  ./qlab literature sync`;

class UsageError extends Error {}

function option(args: string[], name: string, fallback: string): string {
  const position = args.indexOf(name);
  if (position < 0) return fallback;
  const value = args[position + 1];
  if (value === undefined || value.startsWith("--")) throw new UsageError(`${name} requires a value`);
  args.splice(position, 2);
  return value;
}

async function writeZoteroBib(literatureRoot: string, contents: string): Promise<void> {
  const target = path.join(literatureRoot, "zotero.bib");
  const temporary = `${target}.tmp-${process.pid}`;
  await writeFile(temporary, contents, "utf8");
  await rename(temporary, target);
}

async function importFromZotero(command: "connect" | "import", args: string[]): Promise<void> {
  if (args.shift() !== "zotero") throw new UsageError(`${command} requires the source "zotero"`);
  const literatureRoot = path.resolve(option(args, "--literature-root", path.join(REPO_ROOT, "literature")));
  const baseUrl = option(args, "--base-url", "http://127.0.0.1:23119/api");
  const library = option(args, "--library", "users/0");
  const rehomePosition = args.indexOf("--rehome-metadata-only");
  const rehomeMetadataOnly = rehomePosition >= 0;
  if (rehomePosition >= 0) args.splice(rehomePosition, 1);
  if (command === "connect" && rehomeMetadataOnly) throw new UsageError("connect does not accept --rehome-metadata-only");
  if (args.length > 0) throw new UsageError(`unknown option ${JSON.stringify(args[0])}`);

  const client = new ZoteroClient({ baseUrl, library });
  const [collections, items, bibtex] = await Promise.all([
    client.collections(),
    client.topItems(),
    client.bibtex(),
  ]);
  const report = await importZoteroSnapshot({
    literatureRoot,
    collections,
    items,
    library,
    connected: command === "connect",
    rehomeMetadataOnly,
  });
  await writeZoteroBib(literatureRoot, bibtex);
  console.log(`Imported ${report.imported} Zotero metadata records into ${literatureRoot}`);
  if (Object.keys(report.duplicateCandidates).length > 0) {
    console.log(`Duplicate DOI candidates (not merged): ${JSON.stringify(report.duplicateCandidates)}`);
  }
}

async function main(argv: string[]): Promise<void> {
  if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h") {
    console.log(HELP);
    return;
  }
  if (argv.shift() !== "literature") throw new UsageError("the only supported surface is literature");
  if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h") {
    console.log(HELP);
    return;
  }
  const command = argv.shift();
  if (command === "connect" || command === "import") {
    await importFromZotero(command, argv);
    return;
  }
  const literatureRoot = path.resolve(option(argv, "--literature-root", path.join(REPO_ROOT, "literature")));
  if (command === "materialize") {
    const itemKey = argv.shift();
    if (itemKey === undefined) throw new UsageError("materialize requires an item key");
    const workRoot = path.resolve(option(argv, "--work-root", path.join(REPO_ROOT, "work", "literature-import")));
    if (argv.length > 0) throw new UsageError(`unknown option ${JSON.stringify(argv[0])}`);
    console.log(`Materialized ${itemKey} at ${await materializeZoteroRecord({ literatureRoot, workRoot, itemKey })}`);
    return;
  }
  if (command === "verify") {
    const itemKey = argv.shift();
    if (itemKey === undefined || argv.length > 0) throw new UsageError("verify requires exactly one item key");
    console.log(`Verified ${itemKey}: ${await verifyZoteroRecord({ literatureRoot, itemKey })}`);
    return;
  }
  if (command === "index") {
    if (argv.length > 0) throw new UsageError("index takes no arguments");
    const entries = await loadBibliography(path.join(literatureRoot, "ref.bib"));
    const written = await writeMethodIndexes(literatureRoot, entries);
    console.log(`${entries.length} bibliography entries; ${written.length} method indexes`);
    return;
  }
  if (command === "fetch") {
    const citekey = argv.shift();
    if (citekey === undefined || argv.length > 0) throw new UsageError("fetch requires exactly one citekey");
    const manifest = await fetchLiteratureEntry({ literatureRoot, citekey });
    console.log(`${manifest.citekey}: arXiv ${manifest.arxiv.id}${manifest.arxiv.version}`);
    return;
  }
  if (command === "sync") {
    if (argv.length > 0) throw new UsageError("sync takes no arguments");
    const counts = await syncLiterature({ literatureRoot });
    console.log(`${counts.fetched} fetched, ${counts.reused} reused, ${counts.skippedNoArxiv} without arXiv`);
    return;
  }
  throw new UsageError(`unknown literature command ${JSON.stringify(command)}`);
}

try {
  await main(process.argv.slice(2));
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`qlab: ${message}${error instanceof UsageError ? `\n${HELP}` : ""}`);
  process.exitCode = error instanceof UsageError ||
    (error instanceof LiteratureFetchError && error.code === "unknown-citekey") ? 2 : 1;
}
