import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";

import { buildProblemIndex } from "../lib/problems/indexer.mjs";

function readArg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index === -1 ? fallback : process.argv[index + 1];
}

function readArgs(name) {
  return process.argv.flatMap((value, index) => (
    value === name && process.argv[index + 1] ? [process.argv[index + 1]] : []
  ));
}

const rootDir = resolve(readArg("--root", process.cwd()));
const outputPath = resolve(readArg("--out", join(rootDir, ".generated/problem-index.json")));
const problemsDir = readArg("--problems-dir", "problems");
const reservedIds = readArgs("--reserve-id");
const index = await buildProblemIndex({ rootDir, problemsDir, reservedIds });

await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(index, null, 2)}\n`);
console.log(`problem index: wrote ${relative(rootDir, outputPath)}`);
