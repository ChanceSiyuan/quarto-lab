import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";
import { fileURLToPath } from "node:url";

import { stringify } from "yaml";

import {
  materializeZoteroRecord,
  verifyZoteroRecord,
} from "../../lib/literature/zotero-materialize.js";

const FIXTURES = path.resolve(fileURLToPath(import.meta.url), "..", "..", "fixtures", "archives");

async function fixture(t: TestContext): Promise<{ literatureRoot: string; workRoot: string; record: string }> {
  const root = await mkdtemp(path.join(tmpdir(), "research-loop-materialize-"));
  t.after(async () => rm(root, { recursive: true, force: true }));
  const literatureRoot = path.join(root, "literature");
  const paper = path.join(literatureRoot, "inbox", "papers", "ITEM0001_paper");
  await mkdir(paper, { recursive: true });
  const record = path.join(paper, "record.yml");
  await writeFile(
    record,
    stringify({
      schema_version: 2,
      origin: "zotero-import",
      materialization: "metadata-only",
      zotero_import: { item_key: "ITEM0001" },
      qlab: { primary_collection: null, indexed_collections: [], primary_topic: "inbox", indexed_topics: ["inbox"] },
      title: "Fixture paper",
      authors: [],
      year: 2024,
      identifiers: { arxiv: "1610.03042v2" },
    }),
  );
  return { literatureRoot, workRoot: path.join(root, "work"), record };
}

test("materialize writes verified PDF and LaTeX beside the Zotero record", async (t) => {
  const { literatureRoot, workRoot, record } = await fixture(t);
  const archive = gzipSync(await readFile(path.join(FIXTURES, "benign-plain.tar")));
  const pdf = Buffer.from("%PDF-1.7\nfixture\n%%EOF\n", "latin1");
  const fetchImpl = (async (input: RequestInfo | URL) => {
    const url = input.toString();
    if (url.includes("e-print")) return new Response(archive);
    if (url.includes("/pdf/")) return new Response(pdf, { headers: { "content-type": "application/pdf" } });
    return new Response(null, { status: 404 });
  }) as typeof fetch;

  const result = await materializeZoteroRecord({
    literatureRoot,
    workRoot,
    itemKey: "ITEM0001",
    fetchImpl,
  });

  assert.equal(result, path.dirname(record));
  assert.equal(await readFile(path.join(result, "paper.pdf"), "latin1"), pdf.toString("latin1"));
  assert.ok((await readFile(path.join(result, "source", "main.tex"))).length > 0);
  const manifest = JSON.parse(await readFile(path.join(result, "manifest.json"), "utf8"));
  assert.equal(manifest.paper.zotero_item_key, "ITEM0001");
  assert.ok(manifest.files.some((entry: { role: string }) => entry.role === "primary-pdf"));
  assert.ok(manifest.files.some((entry: { role: string }) => entry.role === "latex-entrypoint"));
  await verifyZoteroRecord({ literatureRoot, itemKey: "ITEM0001" });
});

test("verify detects a changed materialized file", async (t) => {
  const { literatureRoot, workRoot } = await fixture(t);
  const archive = gzipSync(await readFile(path.join(FIXTURES, "benign-plain.tar")));
  const fetchImpl = (async (input: RequestInfo | URL) =>
    input.toString().includes("e-print")
      ? new Response(archive)
      : new Response(Buffer.from("%PDF-1.7\nfixture\n%%EOF\n", "latin1"))) as typeof fetch;
  const paper = await materializeZoteroRecord({ literatureRoot, workRoot, itemKey: "ITEM0001", fetchImpl });
  await writeFile(path.join(paper, "paper.pdf"), "tampered");

  await assert.rejects(
    verifyZoteroRecord({ literatureRoot, itemKey: "ITEM0001" }),
    /checksum mismatch/i,
  );
});

test("materialize requires an explicit arXiv identity and never guesses by title", async (t) => {
  const { literatureRoot, workRoot, record } = await fixture(t);
  const source = (await import("yaml")).parse(await readFile(record, "utf8"));
  source.identifiers = { doi: "10.1234/example" };
  await writeFile(record, stringify(source));

  await assert.rejects(
    materializeZoteroRecord({ literatureRoot, workRoot, itemKey: "ITEM0001" }),
    /arXiv identifier/i,
  );
});
