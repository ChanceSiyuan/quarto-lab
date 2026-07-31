import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..", "..");
const KNOWLEDGE_ROOT = path.join(REPO_ROOT, "knowledge");

const EXPECTED_TOPICS = [
  "CZsim",
  "Condensed_matter",
  "Digital-analog",
  "Dynamics",
  "Entanglement",
  "Factoring",
  "Fingerprint",
  "Magic",
  "Noisy_complexity",
  "Nonlocal_Games_Survey",
  "OSF",
  "QEC",
  "SLM_engineer",
  "TN_sim",
  "compatibility",
  "learning_theo",
  "optimization",
  "quantum_complexity",
  "rydberg_qc",
  "stab_simulation",
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

test("trusted knowledge is the adapted quarto-lab corpus, not the retired issue #133 subset", async () => {
  const files = await qmdFiles(KNOWLEDGE_ROOT);
  // Five QEC construction notes are intentionally under review in drafts/.
  assert.equal(files.length, 131);
  assert.deepEqual(
    [...new Set(files.filter((file) => file !== "index.qmd").map((file) => file.split("/")[0]))].sort(),
    [...EXPECTED_TOPICS].sort(),
  );
  assert.equal(files.some((file) => file.startsWith("methods/")), false);
  assert.equal(files.some((file) => file.startsWith("models/")), false);
  assert.equal(files.some((file) => file.startsWith("solvable/")), false);
});

test("the root reading map links every migrated top-level topic", async () => {
  const root = await readFile(path.join(KNOWLEDGE_ROOT, "index.qmd"), "utf8");
  for (const topic of EXPECTED_TOPICS) {
    assert.match(
      root,
      new RegExp(`\\(${topic.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&")}/index\\.qmd\\)`),
      `knowledge/index.qmd must link ${topic}/index.qmd`,
    );
  }
});
