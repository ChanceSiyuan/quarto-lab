import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";

import { parse, stringify } from "yaml";

import {
  ZoteroClient,
  importZoteroSnapshot,
  type ZoteroCollection,
  type ZoteroItem,
} from "../../lib/literature/zotero.js";

async function makeLiteratureRoot(t: TestContext): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), "research-loop-zotero-"));
  t.after(async () => rm(root, { recursive: true, force: true }));
  const literature = path.join(root, "literature");
  await mkdir(literature, { recursive: true });
  await writeFile(path.join(literature, "ref.bib"), "@article{reviewed, title={Reviewed}}\n");
  return literature;
}

const collections = (): ZoteroCollection[] => [
  { key: "C-DYN", data: { name: "Dynamics", parentCollection: false } },
  { key: "C-ALG", data: { name: "Algorithms", parentCollection: false } },
  { key: "C-SHOR", data: { name: "Shor", parentCollection: "C-ALG" } },
];

function item(key = "ITEM0001", membership: string[] = ["C-DYN", "C-ALG"]): ZoteroItem {
  return {
    key,
    version: 7,
    data: {
      itemType: "journalArticle",
      title: key === "ITEM0001" ? "A Many Collection Paper" : "Another Paper",
      creators: [{ creatorType: "author", firstName: "Ada", lastName: "Lovelace" }],
      date: "2024-05-02",
      abstractNote: "A test abstract.",
      DOI: "10.1234/EXAMPLE",
      extra: "arXiv: 2401.00001v2",
      tags: [{ tag: "quantum" }],
      collections: membership,
    },
  };
}

test("connect creates one collection-owned record and leaves ref.bib untouched", async (t) => {
  const literatureRoot = await makeLiteratureRoot(t);
  const report = await importZoteroSnapshot({
    literatureRoot,
    collections: collections(),
    items: [item()],
    library: "users/0",
    connected: true,
    importedAt: "2026-07-28T00:00:00Z",
  });

  assert.equal(report.imported, 1);
  assert.equal(
    report.records[0],
    path.join(
      literatureRoot,
      "collections",
      "dynamics",
      "papers",
      "ITEM0001_a-many-collection-paper",
      "record.yml",
    ),
  );
  const record = parse(await readFile(report.records[0], "utf8"));
  assert.equal(record.zotero_import.item_key, "ITEM0001");
  assert.equal(record.qlab.primary_collection, "C-DYN");
  assert.deepEqual(record.qlab.indexed_collections, ["C-ALG", "C-DYN"]);
  assert.deepEqual(record.qlab.indexed_topics, ["algorithms", "dynamics"]);
  assert.equal(record.identifiers.doi, "10.1234/example");
  assert.equal(record.identifiers.arxiv, "2401.00001v2");

  const manifest = JSON.parse(await readFile(path.join(path.dirname(report.records[0]), "manifest.json"), "utf8"));
  assert.equal(manifest.schema_version, 2);
  assert.equal(manifest.paper.zotero_item_key, "ITEM0001");
  assert.deepEqual(
    new Set(manifest.paper.collections.map((entry: { path: string }) => entry.path)),
    new Set(["Dynamics", "Algorithms"]),
  );
  assert.equal(await readFile(path.join(literatureRoot, "ref.bib"), "utf8"), "@article{reviewed, title={Reviewed}}\n");
});

test("nested Zotero collections preserve hierarchy and inherit the root topic", async (t) => {
  const literatureRoot = await makeLiteratureRoot(t);
  const report = await importZoteroSnapshot({
    literatureRoot,
    collections: collections(),
    items: [item("ITEM0001", ["C-SHOR"])],
    library: "users/0",
    connected: true,
    importedAt: "2026-07-28T00:00:00Z",
  });

  const record = parse(await readFile(report.records[0], "utf8"));
  assert.equal(record.qlab.primary_collection, "C-SHOR");
  assert.equal(record.qlab.primary_topic, "algorithms");
  assert.equal(
    path.dirname(path.dirname(report.records[0])),
    path.join(literatureRoot, "collections", "algorithms", "shor", "papers"),
  );
  const metadata = parse(
    await readFile(path.join(literatureRoot, "collections", "algorithms", "shor", "collection.yml"), "utf8"),
  );
  assert.equal(metadata.parent_key, "C-ALG");
  assert.equal(metadata.path, "Algorithms/Shor");
});

test("refresh is idempotent, preserves materialized files, and does not propagate Zotero deletion", async (t) => {
  const literatureRoot = await makeLiteratureRoot(t);
  const first = await importZoteroSnapshot({
    literatureRoot,
    collections: collections(),
    items: [item()],
    library: "users/0",
    connected: true,
    importedAt: "2026-07-28T00:00:00Z",
  });
  const pdf = path.join(path.dirname(first.records[0]), "paper.pdf");
  await writeFile(pdf, "%PDF-preserve-me");

  const second = await importZoteroSnapshot({
    literatureRoot,
    collections: collections(),
    items: [],
    library: "users/0",
    connected: false,
    importedAt: "2026-07-29T00:00:00Z",
  });

  assert.equal(second.imported, 0);
  assert.deepEqual(second.records, first.records);
  assert.equal(await readFile(pdf, "utf8"), "%PDF-preserve-me");
  assert.match(
    await readFile(path.join(literatureRoot, "collections", "dynamics", "INDEX.md"), "utf8"),
    /A Many Collection Paper/,
  );
});

test("duplicate DOI candidates remain distinct Zotero identities", async (t) => {
  const literatureRoot = await makeLiteratureRoot(t);
  const report = await importZoteroSnapshot({
    literatureRoot,
    collections: collections(),
    items: [item("ITEM0001", []), item("ITEM0002", [])],
    library: "users/0",
    connected: true,
    importedAt: "2026-07-28T00:00:00Z",
  });

  assert.equal(report.records.length, 2);
  assert.deepEqual(report.duplicateCandidates, {
    "10.1234/example": ["ITEM0001", "ITEM0002"],
  });
});

test("import refuses to invent zotero.yml before connect", async (t) => {
  const literatureRoot = await makeLiteratureRoot(t);
  await assert.rejects(
    importZoteroSnapshot({
      literatureRoot,
      collections: collections(),
      items: [item()],
      library: "users/0",
    }),
    /connect zotero/i,
  );
});

test("ZoteroClient paginates metadata and exports a BibTeX snapshot", async () => {
  const calls: string[] = [];
  const fetchImpl = (async (input: RequestInfo | URL) => {
    const url = input.toString();
    calls.push(url);
    const parsed = new URL(url);
    if (parsed.searchParams.get("format") === "bibtex") {
      return new Response("@article{zotero_snapshot}\n");
    }
    const start = Number(parsed.searchParams.get("start") ?? 0);
    const length = start === 0 ? 100 : 1;
    return Response.json(Array.from({ length }, (_, index) => ({ key: `K${start + index}`, data: {} })));
  }) as typeof fetch;
  const client = new ZoteroClient({ fetchImpl });

  assert.equal((await client.collections()).length, 101);
  assert.equal(await client.bibtex(), "@article{zotero_snapshot}\n");
  assert.ok(calls.every((url) => url.startsWith("http://127.0.0.1:23119/api/users/0/")));
});

test("an existing mapping can ignore one collection without deleting its metadata", async (t) => {
  const literatureRoot = await makeLiteratureRoot(t);
  await importZoteroSnapshot({
    literatureRoot,
    collections: collections(),
    items: [],
    library: "users/0",
    connected: true,
  });
  const configPath = path.join(literatureRoot, "zotero.yml");
  const config = parse(await readFile(configPath, "utf8"));
  config.ignored_collections = ["C-ALG"];
  await writeFile(configPath, stringify(config));

  const report = await importZoteroSnapshot({
    literatureRoot,
    collections: collections(),
    items: [item()],
    library: "users/0",
  });
  const record = parse(await readFile(report.records[0], "utf8"));
  assert.deepEqual(record.qlab.indexed_collections, ["C-DYN"]);
  assert.deepEqual(record.qlab.indexed_topics, ["dynamics"]);
});
