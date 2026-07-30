import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";

import { buildProblemIndex } from "../../../src/lib/problems/indexer.mjs";
import { buildResearchIndex } from "../../../src/lib/problems/research-indexer.mjs";
import { assertPublicSafeValuation } from "../../../src/lib/valuations/privacy.mjs";

function readArg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index === -1 ? fallback : process.argv[index + 1];
}

function readArgs(name) {
  return process.argv.flatMap((value, index) => (
    value === name && process.argv[index + 1] ? [process.argv[index + 1]] : []
  ));
}

async function jsonFilesBelow(directory, { onlySummary = false } = {}) {
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
  const files = [];
  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`Cannot validate symbolic link in public build: ${path}`);
    if (entry.isDirectory()) files.push(...await jsonFilesBelow(path, { onlySummary }));
    else if (entry.isFile() && entry.name.endsWith(".json") && (!onlySummary || entry.name === "summary.json")) files.push(path);
  }
  return files;
}

async function assertPublicArtifacts(root, problemsDir) {
  const problemsPath = resolve(root, problemsDir);
  let entries;
  try {
    entries = await readdir(problemsPath, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return;
    throw error;
  }
  for (const entry of entries) {
    if (entry.isSymbolicLink()) throw new Error(`Cannot validate symbolic link in public build: ${relative(root, join(problemsPath, entry.name))}`);
    if (!entry.isDirectory()) continue;
    const problemPath = join(problemsPath, entry.name);
    const files = [
      ...await jsonFilesBelow(join(problemPath, "valuation", "snapshots")),
      ...await jsonFilesBelow(join(problemPath, "assessments"), { onlySummary: true }),
    ];
    for (const path of files) {
      const relativePath = relative(root, path);
      let value;
      try {
        value = JSON.parse(await readFile(path, "utf8"));
      } catch (error) {
        throw new Error(`Cannot validate public valuation artifact ${relativePath}: ${error.message}`);
      }
      try {
        assertPublicSafeValuation(value);
      } catch (error) {
        throw new Error(`Public valuation privacy violation at ${relativePath}: ${error.message}`);
      }
    }
  }
}

const rootDir = resolve(readArg("--root", process.cwd()));
const outputPath = resolve(readArg("--out", join(rootDir, ".generated/problem-index.json")));
const problemsDir = readArg("--problems-dir", "problems");
const reservedIds = readArgs("--reserve-id");
const index = await buildProblemIndex({ rootDir, problemsDir, reservedIds });

if (process.argv.includes("--public")) await assertPublicArtifacts(rootDir, problemsDir);

await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(index, null, 2)}\n`);
console.log(`problem index: wrote ${relative(rootDir, outputPath)}`);

const researchOutputPath = resolve(readArg("--research-out", join(rootDir, ".generated/research-index.json")));
const researchIndex = await buildResearchIndex({ rootDir, problemsDir });
await mkdir(dirname(researchOutputPath), { recursive: true });
await writeFile(researchOutputPath, `${JSON.stringify(researchIndex, null, 2)}\n`);
console.log(`research index: wrote ${relative(rootDir, researchOutputPath)}`);
