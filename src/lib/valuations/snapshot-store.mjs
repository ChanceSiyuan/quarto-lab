import { createHash } from "node:crypto";
import { lstat, mkdir, readFile, readdir, realpath, rename, rm, writeFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";

import { assertContained, createRunId, resolveProblemDir } from "../assessments/paths.mjs";
import { validateAtomicEvidence } from "./contract.mjs";
import { propagateVisibility, assertPublicSafeValuation } from "./privacy.mjs";

const SNAPSHOT_ID_PATTERN = /^\d{8}T\d{6}Z-[a-f0-9]{12}$/;
const SNAPSHOT_FILES = Object.freeze(["manifest.json", "papers.json", "market-evidence.json"]);

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function canonicalValue(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError("Canonical JSON only accepts finite numbers.");
    return value;
  }
  if (Array.isArray(value)) return value.map(canonicalValue);
  if (!isRecord(value)) throw new TypeError("Canonical JSON only accepts JSON values.");
  return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalValue(value[key])]));
}

export function canonicalJson(value) {
  return JSON.stringify(canonicalValue(value));
}

function identityFreeManifest(manifest) {
  if (!isRecord(manifest)) throw new TypeError("snapshot manifest must be an object.");
  const content = { ...manifest };
  delete content.snapshotId;
  delete content.contentHash;
  return content;
}

export function snapshotDigest({ manifest, papers, marketEvidence }) {
  return createHash("sha256").update(canonicalJson({
    manifest: identityFreeManifest(manifest),
    papers,
    marketEvidence,
  })).digest("hex");
}

async function existing(path) {
  try {
    return await lstat(path);
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

async function assertNoSymlink(rootDir, path) {
  const root = resolve(rootDir);
  const target = resolve(path);
  if (target !== root && !target.startsWith(`${root}/`)) throw new Error(`Path escapes expected root: ${path}`);
  let current = root;
  const rootStat = await existing(current);
  if (rootStat?.isSymbolicLink()) throw new Error(`Refusing symbolic link: ${current}`);
  for (const segment of relative(root, target).split("/").filter(Boolean)) {
    current = join(current, segment);
    const stat = await existing(current);
    if (stat?.isSymbolicLink()) throw new Error(`Refusing symbolic link: ${current}`);
  }
}

async function contained(rootDir, path) {
  await assertNoSymlink(rootDir, path);
  await assertContained(rootDir, path);
  return path;
}

async function ensureContainedDirectory(rootDir, path) {
  await contained(rootDir, path);
  await mkdir(path, { recursive: true });
  await contained(rootDir, path);
  return path;
}

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

async function readJsonIfPresent(path, fallback) {
  try {
    return await readJson(path);
  } catch (error) {
    if (error.code === "ENOENT") return fallback;
    throw error;
  }
}

function overlay(publicValue, privateValue) {
  if (Array.isArray(privateValue) || !isRecord(privateValue)) return structuredClone(privateValue);
  const base = isRecord(publicValue) ? publicValue : {};
  return Object.fromEntries([...new Set([...Object.keys(base), ...Object.keys(privateValue)])].map((key) => [
    key,
    Object.hasOwn(privateValue, key) ? overlay(base[key], privateValue[key]) : structuredClone(base[key]),
  ]));
}

function validateAtomicValues(value) {
  if (Array.isArray(value)) {
    value.forEach(validateAtomicValues);
    return;
  }
  if (!isRecord(value)) return;
  if (typeof value.state === "string") {
    const validation = validateAtomicEvidence(value);
    if (!validation.ok) throw new Error(`Invalid atomic valuation evidence: ${validation.errors.join(" ")}`);
    return;
  }
  Object.values(value).forEach(validateAtomicValues);
}

function snapshotFromFiles(manifest, papers, marketEvidence) {
  return { manifest, papers, marketEvidence };
}

function timestamp(now) {
  return new Date(now).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

export function createValuationSnapshotStore({ rootDir = process.cwd(), now = () => new Date() } = {}) {
  if (typeof now !== "function") throw new TypeError("now must be a function.");
  const workspaceRoot = realpath(resolve(rootDir));

  async function valuationDir(problemId) {
    const root = await workspaceRoot;
    const problemDir = await resolveProblemDir(root, problemId);
    await assertNoSymlink(root, problemDir);
    const path = join(problemDir, "valuation");
    await ensureContainedDirectory(root, path);
    return path;
  }

  async function snapshotDir(problemId, snapshotId, { ensure = false } = {}) {
    if (!SNAPSHOT_ID_PATTERN.test(snapshotId)) throw new Error(`Invalid snapshot ID: ${snapshotId}`);
    const base = join(await valuationDir(problemId), "snapshots");
    const root = await workspaceRoot;
    if (ensure) await ensureContainedDirectory(root, base);
    else await contained(root, base);
    const path = join(base, snapshotId);
    await contained(root, path);
    return path;
  }

  async function inputPath(base, name) {
    const path = join(base, name);
    await contained(await workspaceRoot, path);
    return path;
  }

  async function readRaw(problemId, snapshotId) {
    const directory = await snapshotDir(problemId, snapshotId);
    const directoryStat = await existing(directory);
    if (!directoryStat?.isDirectory()) throw new Error(`Snapshot does not exist: ${snapshotId}`);
    const entries = await readdir(directory, { withFileTypes: true });
    const names = entries.map((entry) => entry.name).sort();
    if (JSON.stringify(names) !== JSON.stringify([...SNAPSHOT_FILES].sort())
      || entries.some((entry) => !entry.isFile() || entry.isSymbolicLink())) throw new Error(`Snapshot has unsupported files: ${snapshotId}`);
    const [manifest, papers, marketEvidence] = await Promise.all([
      readJson(join(directory, "manifest.json")),
      readJson(join(directory, "papers.json")),
      readJson(join(directory, "market-evidence.json")),
    ]);
    return snapshotFromFiles(manifest, papers, marketEvidence);
  }

  async function verify(problemId, snapshotId) {
    const snapshot = await readRaw(problemId, snapshotId);
    if (snapshot.manifest?.snapshotId !== snapshotId) throw new Error(`Snapshot ID mismatch: ${snapshotId}`);
    const actual = snapshotDigest(snapshot);
    if (snapshot.manifest?.contentHash !== actual) throw new Error(`Snapshot hash mismatch: ${snapshotId}`);
    return snapshot;
  }

  return Object.freeze({
    async readInputs(problemId) {
      const base = await valuationDir(problemId);
      const publicInputs = await readJsonIfPresent(await inputPath(base, "inputs.json"), {});
      const privateInputs = await readJsonIfPresent(await inputPath(base, "inputs.private.json"), {});
      return overlay(publicInputs, privateInputs);
    },

    async writeInputs(problemId, inputs) {
      assertPublicSafeValuation(inputs);
      const base = await valuationDir(problemId);
      await writeFile(await inputPath(base, "inputs.json"), `${canonicalJson(inputs)}\n`);
      return structuredClone(inputs);
    },

    async freeze(problemId, { manifest, papers, marketEvidence }) {
      validateAtomicValues(manifest);
      validateAtomicValues(papers);
      validateAtomicValues(marketEvidence);
      if (!Array.isArray(papers) || !Array.isArray(marketEvidence)) throw new TypeError("snapshot papers and market evidence must be arrays.");
      const createdAt = new Date(now());
      if (Number.isNaN(createdAt.valueOf())) throw new TypeError("now must return a valid date.");
      const visibility = propagateVisibility([manifest, papers, marketEvidence]);
      const contentManifest = {
        ...structuredClone(identityFreeManifest(manifest)),
        ...(visibility === "private" ? { visibility: "private" } : {}),
      };
      const digest = snapshotDigest({ manifest: contentManifest, papers, marketEvidence });
      const snapshotId = `${timestamp(createdAt)}-${digest.slice(0, 12)}`;
      const frozenManifest = { ...contentManifest, snapshotId, contentHash: digest };
      const snapshot = snapshotFromFiles(frozenManifest, structuredClone(papers), structuredClone(marketEvidence));
      const root = await workspaceRoot;
      const generatedRoot = join(root, ".generated", "valuation-snapshots");
      await ensureContainedDirectory(root, generatedRoot);
      const stage = join(generatedRoot, createRunId(createdAt));
      await contained(root, stage);
      if (await existing(stage)) throw new Error(`Snapshot staging directory already exists: ${stage}`);
      const destination = await snapshotDir(problemId, snapshotId, { ensure: true });
      if (await existing(destination)) throw new Error(`Snapshot already exists: ${snapshotId}`);
      try {
        await mkdir(stage);
        await Promise.all([
          writeFile(join(stage, "manifest.json"), `${canonicalJson(snapshot.manifest)}\n`),
          writeFile(join(stage, "papers.json"), `${canonicalJson(snapshot.papers)}\n`),
          writeFile(join(stage, "market-evidence.json"), `${canonicalJson(snapshot.marketEvidence)}\n`),
        ]);
        const staged = await readRawFromDirectory(stage, snapshotId);
        if (snapshotDigest(staged) !== digest || staged.manifest.contentHash !== digest || staged.manifest.snapshotId !== snapshotId) throw new Error("Staged snapshot hash mismatch.");
        await contained(root, destination);
        if (await existing(destination)) throw new Error(`Snapshot already exists: ${snapshotId}`);
        await rename(stage, destination);
        return verify(problemId, snapshotId);
      } finally {
        if (await existing(stage)) await rm(stage, { recursive: true, force: true });
      }
    },

    async read(problemId, snapshotId) {
      return verify(problemId, snapshotId);
    },

    async list(problemId) {
      const base = join(await valuationDir(problemId), "snapshots");
      try {
        await contained(await workspaceRoot, base);
        const entries = await readdir(base, { withFileTypes: true });
        return entries.filter((entry) => entry.isDirectory() && SNAPSHOT_ID_PATTERN.test(entry.name)).map((entry) => entry.name).sort();
      } catch (error) {
        if (error.code === "ENOENT") return [];
        throw error;
      }
    },

    verify,
  });
}

async function readRawFromDirectory(directory, snapshotId) {
  const entries = await readdir(directory, { withFileTypes: true });
  const names = entries.map((entry) => entry.name).sort();
  if (JSON.stringify(names) !== JSON.stringify([...SNAPSHOT_FILES].sort())
    || entries.some((entry) => !entry.isFile() || entry.isSymbolicLink())) throw new Error(`Snapshot has unsupported files: ${snapshotId}`);
  const [manifest, papers, marketEvidence] = await Promise.all([
    readJson(join(directory, "manifest.json")),
    readJson(join(directory, "papers.json")),
    readJson(join(directory, "market-evidence.json")),
  ]);
  return snapshotFromFiles(manifest, papers, marketEvidence);
}
