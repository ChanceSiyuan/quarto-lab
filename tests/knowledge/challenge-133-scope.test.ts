import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..");
const KNOWLEDGE_ROOT = path.join(REPO_ROOT, "knowledge");

const EXPECTED_QMD = [
  "index.qmd",
  "methods/circuit-sim/METHOD.qmd",
  "methods/circuit-sim/index.qmd",
  "methods/dmrg/METHOD.qmd",
  "methods/dmrg/index.qmd",
  "methods/ed-full/METHOD.qmd",
  "methods/ed-full/index.qmd",
  "methods/ed-lanczos/METHOD.qmd",
  "methods/ed-lanczos/index.qmd",
  "methods/index.qmd",
  "methods/peps-ipeps/METHOD.qmd",
  "methods/peps-ipeps/index.qmd",
  "methods/sdp-nctssos/METHOD.qmd",
  "methods/sdp-nctssos/index.qmd",
  "methods/tebd/METHOD.qmd",
  "methods/tebd/index.qmd",
  "methods/vmc-nqs/METHOD.qmd",
  "methods/vmc-nqs/index.qmd",
  "models/aklt/MODEL.qmd",
  "models/aklt/index.qmd",
  "models/heisenberg/MODEL.qmd",
  "models/heisenberg/index.qmd",
  "models/index.qmd",
  "models/j1-j2/MODEL.qmd",
  "models/j1-j2/index.qmd",
  "physics/frustration/PHYSICS.qmd",
  "physics/frustration/index.qmd",
  "physics/index.qmd",
  "physics/spin-liquid/PHYSICS.qmd",
  "physics/spin-liquid/index.qmd",
  "software/index.qmd",
  "software/quimb-api.qmd",
  "solvable/aklt-chain/ORACLE.qmd",
  "solvable/aklt-chain/index.qmd",
  "solvable/aklt-honeycomb/ORACLE.qmd",
  "solvable/aklt-honeycomb/index.qmd",
  "solvable/heisenberg-xxx/ORACLE.qmd",
  "solvable/heisenberg-xxx/index.qmd",
  "solvable/index.qmd",
] as const;

async function qmdFiles(directory: string, prefix = ""): Promise<string[]> {
  const files: string[] = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relative = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
    if (entry.isDirectory()) {
      files.push(...(await qmdFiles(path.join(directory, entry.name), relative)));
    } else if (entry.isFile() && entry.name.endsWith(".qmd")) {
      files.push(relative);
    }
  }
  return files.sort();
}

test("trusted knowledge contains only the issue #133 calibration scope", async () => {
  assert.deepEqual(await qmdFiles(KNOWLEDGE_ROOT), [...EXPECTED_QMD].sort());
});

test("the root page names every calibration challenge from issue #133", async () => {
  const root = await readFile(path.join(KNOWLEDGE_ROOT, "index.qmd"), "utf8");
  for (const issue of [124, 125, 126, 127, 128]) {
    assert.match(
      root,
      new RegExp(`https://github\\.com/QuantumBFS/quantum\\.harness/issues/${issue}\\b`),
      `knowledge/index.qmd must link calibration issue #${issue}`,
    );
  }
});
