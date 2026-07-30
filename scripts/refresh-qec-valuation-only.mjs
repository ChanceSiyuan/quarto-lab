import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import { createArtifactStore } from "../lib/assessments/artifact-store.mjs";
import { createProblemRepository } from "../lib/problems/repository.mjs";
import { QEC_PORTFOLIO_BATCH_IDS } from "../lib/qec-portfolio/batch-runner.mjs";
import { refreshValuationOnlyProblem } from "../lib/qec-portfolio/valuation-only-refresh.mjs";
import { SCIENTIFIC_DEMAND_FORMULA_ID } from "../lib/valuations/citations.mjs";
import { createValuationSnapshotStore } from "../lib/valuations/snapshot-store.mjs";

function readArg(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

function selectedProblemIds(defaultIds = QEC_PORTFOLIO_BATCH_IDS) {
  const index = process.argv.indexOf("--problem");
  if (index === -1) return [...defaultIds];
  return [process.argv[index + 1]].filter(Boolean);
}

async function createRepository(rootDir) {
  const index = JSON.parse(await readFile(join(rootDir, ".generated", "problem-index.json"), "utf8"));
  return createProblemRepository(index);
}

async function latestCurrentFormulaSnapshot(valuationStore, problemId) {
  const snapshotIds = await valuationStore.list(problemId);
  for (const snapshotId of [...snapshotIds].reverse()) {
    try {
      const snapshot = await valuationStore.verify(problemId, snapshotId);
      if (snapshot?.manifest?.complete === true
        && snapshot.manifest.citation?.formulaId === SCIENTIFIC_DEMAND_FORMULA_ID) return snapshot;
    } catch {
      // Tampered snapshots remain on disk for audit but are never reused.
    }
  }
  return null;
}

export async function refreshQecValuationOnlyPortfolio({
  rootDir,
  repository = null,
  store = null,
  valuationStore = null,
  problemIds = QEC_PORTFOLIO_BATCH_IDS,
} = {}) {
  const workspaceRoot = resolve(rootDir ?? process.cwd());
  const activeRepository = repository ?? await createRepository(workspaceRoot);
  const activeStore = store ?? createArtifactStore({ rootDir: workspaceRoot });
  const activeValuationStore = valuationStore ?? createValuationSnapshotStore({ rootDir: workspaceRoot });
  const problems = [];
  const errors = [];

  for (const problemId of problemIds) {
    try {
      const snapshot = await latestCurrentFormulaSnapshot(activeValuationStore, problemId);
      if (!snapshot) {
        throw Object.assign(
          new Error(`No complete verified ${SCIENTIFIC_DEMAND_FORMULA_ID} snapshot for ${problemId}.`),
          { code: "VALUATION_SNAPSHOT_REQUIRED" },
        );
      }
      const result = await refreshValuationOnlyProblem({
        rootDir: workspaceRoot,
        repository: activeRepository,
        store: activeStore,
        problemId,
        snapshot,
      });
      problems.push(result);
    } catch (error) {
      const failure = {
        status: "failed",
        problemId,
        code: error?.code ?? "VALUATION_ONLY_REFRESH_FAILED",
        message: error.message,
      };
      problems.push(failure);
      errors.push(failure);
    }
  }

  return {
    status: errors.length === 0 ? "complete" : "incomplete",
    problemIds: [...problemIds],
    problems,
    errors,
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const result = await refreshQecValuationOnlyPortfolio({
    rootDir: readArg("--root"),
    problemIds: selectedProblemIds(),
  });
  console.log(JSON.stringify(result, null, 2));
  if (result.status !== "complete") process.exitCode = 1;
}
