/** Materialize and verify PDF/LaTeX evidence beside one Zotero metadata record. */

import { createHash, randomUUID } from "node:crypto";
import { cp, mkdir, readFile, readdir, rename, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import { parse, stringify } from "yaml";

import { ARCHIVE_LIMITS, extractSourceArchive } from "./archive.js";
import {
  arxivPdfUrl,
  arxivSourceUrl,
  downloadBounded,
  resolveLatestArxivVersion,
  splitArxivIdentifier,
} from "./arxiv.js";
import { writeZoteroManifest } from "./zotero.js";

async function exists(target: string): Promise<boolean> {
  try {
    await stat(target);
    return true;
  } catch {
    return false;
  }
}

async function walkRecords(root: string): Promise<string[]> {
  const found: string[] = [];
  const visit = async (directory: string): Promise<void> => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) await visit(target);
      else if (entry.isFile() && entry.name === "record.yml") found.push(target);
    }
  };
  if (await exists(root)) await visit(root);
  return found.sort();
}

export async function findZoteroRecord(literatureRoot: string, itemKey: string): Promise<string> {
  const matches = [];
  for (const recordPath of await walkRecords(path.resolve(literatureRoot))) {
    const record = parse(await readFile(recordPath, "utf8")) ?? {};
    if (record.zotero_import?.item_key === itemKey || record.identifiers?.arxiv === itemKey) matches.push(recordPath);
  }
  if (matches.length === 0) throw new Error(`No literature record found for item key ${JSON.stringify(itemKey)}`);
  if (matches.length > 1) throw new Error(`Multiple literature records match item key ${JSON.stringify(itemKey)}`);
  return matches[0];
}

function sha256(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}

export async function materializeZoteroRecord(options: {
  literatureRoot: string;
  workRoot: string;
  itemKey: string;
  fetchImpl?: typeof fetch;
}): Promise<string> {
  const recordPath = await findZoteroRecord(options.literatureRoot, options.itemKey);
  const paperRoot = path.dirname(recordPath);
  const record = parse(await readFile(recordPath, "utf8")) ?? {};
  const rawArxiv = record.identifiers?.arxiv;
  if (typeof rawArxiv !== "string" || rawArxiv.trim() === "") {
    throw new Error("The Zotero record has no explicit arXiv identifier; add one before materializing instead of guessing by title");
  }
  const split = splitArxivIdentifier(rawArxiv);
  const version = split.version ?? await resolveLatestArxivVersion({
    id: split.id,
    ...(options.fetchImpl === undefined ? {} : { fetchImpl: options.fetchImpl }),
  });
  const pin = { id: split.id, version };
  const sourceUrl = arxivSourceUrl(pin);
  const pdfUrl = arxivPdfUrl(pin);
  const sourceArchive = await downloadBounded({
    url: sourceUrl,
    maxBytes: ARCHIVE_LIMITS.compressedBytes,
    ...(options.fetchImpl === undefined ? {} : { fetchImpl: options.fetchImpl }),
  });
  const pdf = await downloadBounded({
    url: pdfUrl,
    maxBytes: ARCHIVE_LIMITS.compressedBytes,
    accept: "application/pdf",
    ...(options.fetchImpl === undefined ? {} : { fetchImpl: options.fetchImpl }),
  });
  if (!pdf.subarray(0, 5).equals(Buffer.from("%PDF-", "ascii"))) {
    throw new Error(`The response from ${pdfUrl} is not a PDF`);
  }

  const workRoot = path.resolve(options.workRoot);
  const stagingRoot = path.join(workRoot, randomUUID());
  const stagedPaper = path.join(stagingRoot, "paper");
  await mkdir(stagingRoot, { recursive: true });
  try {
    await cp(paperRoot, stagedPaper, { recursive: true });
    const raw = path.join(stagedPaper, ".raw");
    await rm(raw, { recursive: true, force: true });
    await mkdir(raw, { recursive: true });
    const extraction = await extractSourceArchive({
      archive: sourceArchive,
      citekey: options.itemKey,
      sourceDir: path.join(raw, "source"),
      figuresDir: path.join(raw, "figures"),
    });
    await writeFile(path.join(raw, "paper.pdf"), pdf, { mode: 0o644 });

    const generatedAt = new Date().toISOString().replace(/\.\d{3}Z$/u, "Z");
    record.schema_version = 2;
    record.materialization = "source-verified";
    record.evidence_mode = "source-verified";
    record.identifiers = { ...(record.identifiers ?? {}), arxiv: `${pin.id}${pin.version}` };
    record.source_url = sourceUrl;
    record.pdf_url = pdfUrl;
    record.retrieved_at = generatedAt;
    record.source_archive_sha256 = sha256(sourceArchive);
    record.paper_pdf_sha256 = sha256(pdf);
    record.latex = { entrypoint: `.raw/source/${extraction.mainTex}` };
    const stagedRecord = path.join(stagedPaper, "record.yml");
    await writeFile(stagedRecord, stringify(record, { sortMapEntries: false }), "utf8");
    await writeZoteroManifest(stagedRecord, record, generatedAt);

    const backup = `${paperRoot}.replaced-${randomUUID()}`;
    await rename(paperRoot, backup);
    try {
      await rename(stagedPaper, paperRoot);
    } catch (error) {
      await rename(backup, paperRoot);
      throw error;
    }
    await rm(backup, { recursive: true, force: true });
  } finally {
    await rm(stagingRoot, { recursive: true, force: true });
  }
  await verifyZoteroRecord({ literatureRoot: options.literatureRoot, itemKey: options.itemKey });
  return paperRoot;
}

export async function verifyZoteroRecord(options: {
  literatureRoot: string;
  itemKey: string;
}): Promise<string> {
  const recordPath = await findZoteroRecord(options.literatureRoot, options.itemKey);
  const manifestPath = path.join(path.dirname(recordPath), "manifest.json");
  if (!(await exists(manifestPath))) throw new Error(`Missing manifest: ${manifestPath}`);
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  for (const entry of manifest.files ?? []) {
    const target = path.join(path.dirname(recordPath), entry.path);
    if (!(await exists(target))) throw new Error(`Missing literature file: ${target}`);
    const digest = sha256(await readFile(target));
    if (digest !== entry.sha256) throw new Error(`Checksum mismatch: ${target}`);
  }
  const record = parse(await readFile(recordPath, "utf8")) ?? {};
  if (record.materialization === "source-verified") {
    const roles = new Set((manifest.files ?? []).map((entry: { role?: string }) => entry.role));
    for (const role of ["primary-pdf", "latex-entrypoint"]) {
      if (!roles.has(role)) throw new Error(`Materialized record is missing role: ${role}`);
    }
  }
  return recordPath;
}
