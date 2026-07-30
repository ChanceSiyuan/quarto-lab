import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import { createArtifactStore } from "../lib/assessments/artifact-store.mjs";
import { createProblemRepository } from "../lib/problems/repository.mjs";
import { QEC_PORTFOLIO_BATCH_IDS, waitForTerminalState } from "../lib/qec-portfolio/batch-runner.mjs";
import { createRetryingOpenAlexClient } from "../lib/qec-portfolio/openalex-retry.mjs";
import { createQecPortfolioValuationResearcher } from "../lib/qec-portfolio/valuation-researcher.mjs";
import { refreshValuationOnlyProblem } from "../lib/qec-portfolio/valuation-only-refresh.mjs";
import { SCIENTIFIC_DEMAND_FORMULA_ID } from "../lib/valuations/citations.mjs";
import { createValuationJobManager } from "../lib/valuations/job-manager.mjs";
import { createOpenAlexClient } from "../lib/valuations/openalex-client.mjs";
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

export async function createQecValuationOnlyRepository(rootDir) {
  const index = JSON.parse(await readFile(join(rootDir, ".generated", "problem-index.json"), "utf8"));
  const repository = createProblemRepository(index);
  return {
    ...repository,
    async readProblemMarkdown(problemId) {
      if (!repository.getProblem(problemId)) return null;
      return readFile(join(rootDir, "problems", problemId, "problem.md"), "utf8");
    },
  };
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

function defaultDelay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function assertCurrentFormulaSnapshot(snapshot, problemId) {
  if (snapshot?.manifest?.complete === true
    && snapshot.manifest.problemId === problemId
    && snapshot.manifest.citation?.formulaId === SCIENTIFIC_DEMAND_FORMULA_ID) return snapshot;
  const error = new Error(`No complete verified ${SCIENTIFIC_DEMAND_FORMULA_ID} snapshot for ${problemId}.`);
  error.code = "VALUATION_SNAPSHOT_REQUIRED";
  throw error;
}

export async function ensureQecScientificDemandSnapshot({
  valuationManager,
  valuationStore,
  problemId,
  force = false,
  delay = defaultDelay,
  pollIntervalMs = 2_500,
  timeoutMs = 30 * 60 * 1000,
} = {}) {
  if (!force) {
    const existing = await latestCurrentFormulaSnapshot(valuationStore, problemId);
    if (existing) return { status: "verified-existing", problemId, snapshot: existing };
  }
  if (typeof valuationManager?.start !== "function") {
    const error = new Error("A valuation manager is required to create missing snapshots.");
    error.code = "VALUATION_MANAGER_REQUIRED";
    throw error;
  }
  const started = await valuationManager.start(problemId);
  if (!started?.accepted) {
    const error = new Error(started?.message ?? "Valuation start rejected.");
    error.code = started?.code ?? "VALUATION_START_REJECTED";
    throw error;
  }
  const pending = await waitForTerminalState(
    () => valuationManager.getJob(started.runId),
    { delay, pollIntervalMs, timeoutMs, success: new Set(["needs_confirmation"]) },
  );
  const confirmation = {
    candidateHash: pending.candidate.contentHash,
    acceptedAnchorIds: pending.candidate.anchorCandidates.map((anchor) => anchor.id),
    assumptionDecisions: [],
  };
  const accepted = await valuationManager.confirm(started.runId, confirmation);
  if (!accepted?.accepted) {
    const error = new Error(accepted?.message ?? "Valuation confirmation rejected.");
    error.code = accepted?.code ?? "VALUATION_CONFIRMATION_REJECTED";
    throw error;
  }
  await waitForTerminalState(
    () => valuationManager.getJob(started.runId),
    { delay, pollIntervalMs, timeoutMs, success: new Set(["ready"]) },
  );
  const state = await valuationManager.getProblemState(problemId);
  const snapshotId = state?.readySnapshotId;
  const snapshot = snapshotId ? await valuationStore.verify(problemId, snapshotId) : null;
  return { status: "completed", problemId, snapshot: assertCurrentFormulaSnapshot(snapshot, problemId) };
}

function createOpenAlexValuationManager({ rootDir, repository, valuationStore, apiKey }) {
  if (!apiKey) {
    const error = new Error("OPENALEX_API_KEY is required to create missing snapshots.");
    error.code = "OPENALEX_KEY_REQUIRED";
    throw error;
  }
  return createValuationJobManager({
    rootDir,
    repository,
    researcher: createQecPortfolioValuationResearcher(),
    openAlex: createRetryingOpenAlexClient({ client: createOpenAlexClient({ apiKey }) }),
    store: valuationStore,
  });
}

export async function refreshQecValuationOnlyPortfolio({
  rootDir,
  repository = null,
  store = null,
  valuationStore = null,
  valuationManager = null,
  problemIds = QEC_PORTFOLIO_BATCH_IDS,
  ensureSnapshots = false,
  snapshotsOnly = false,
  forceSnapshotRefresh = false,
  apiKey = process.env.OPENALEX_API_KEY?.trim(),
} = {}) {
  const workspaceRoot = resolve(rootDir ?? process.cwd());
  const activeRepository = repository ?? await createQecValuationOnlyRepository(workspaceRoot);
  const activeStore = store ?? createArtifactStore({ rootDir: workspaceRoot });
  const activeValuationStore = valuationStore ?? createValuationSnapshotStore({ rootDir: workspaceRoot });
  let activeValuationManager = valuationManager;
  const problems = [];
  const errors = [];

  try {
    for (const problemId of problemIds) {
      try {
        const existingSnapshot = forceSnapshotRefresh
          ? null
          : await latestCurrentFormulaSnapshot(activeValuationStore, problemId);
        let ensured = existingSnapshot
          ? { status: "verified-existing", problemId, snapshot: existingSnapshot }
          : { snapshot: null };
        if (!existingSnapshot && (ensureSnapshots || snapshotsOnly || forceSnapshotRefresh)) {
          if (!activeValuationManager) {
            activeValuationManager = createOpenAlexValuationManager({
              rootDir: workspaceRoot,
              repository: activeRepository,
              valuationStore: activeValuationStore,
              apiKey,
            });
          }
          ensured = await ensureQecScientificDemandSnapshot({
              valuationManager: activeValuationManager,
              valuationStore: activeValuationStore,
              problemId,
              force: forceSnapshotRefresh,
            });
        }
        const snapshot = assertCurrentFormulaSnapshot(ensured.snapshot, problemId);
        if (snapshotsOnly) {
          problems.push({
            status: ensured.status,
            problemId,
            snapshotId: snapshot.manifest.snapshotId,
          });
          continue;
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
  } finally {
    await activeValuationManager?.shutdown?.();
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
    ensureSnapshots: process.argv.includes("--ensure-snapshots"),
    snapshotsOnly: process.argv.includes("--snapshots-only"),
    forceSnapshotRefresh: process.argv.includes("--refresh-scientific-demand"),
  });
  console.log(JSON.stringify(result, null, 2));
  if (result.status !== "complete") process.exitCode = 1;
}
