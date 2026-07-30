import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";

import { QEC_PORTFOLIO_PROBLEMS, validateQecPortfolioCatalog } from "./catalog.mjs";
import { renderProblemManifest } from "./registration.mjs";
import { PROB_001_VALUATION_PROFILE } from "./valuation-researcher.mjs";
import { createArtifactStore } from "../assessments/artifact-store.mjs";
import { resolveExistingRunDir } from "../assessments/paths.mjs";
import { createValuationSnapshotStore } from "../valuations/snapshot-store.mjs";
import { SCIENTIFIC_DEMAND_FORMULA_ID } from "../valuations/citations.mjs";

export const EXTERNAL_VALUATION_ALTERNATIVE = Object.freeze({
  page: "__external__/valuation-snapshot",
  topic: "external-valuation",
  title: "Continue with external valuation evidence only",
  matchKind: "external-valuation",
});

const CJK = /\p{Script=Han}/u;
const EXPECTED_IDS = Array.from({ length: 21 }, (_, index) => `Prob-${String(index + 1).padStart(3, "0")}`);

export const QEC_PORTFOLIO_BATCH_PROBLEMS = Object.freeze([
  PROB_001_VALUATION_PROFILE,
  ...QEC_PORTFOLIO_PROBLEMS,
]);
export const QEC_PORTFOLIO_BATCH_IDS = Object.freeze(QEC_PORTFOLIO_BATCH_PROBLEMS.map((record) => record.id));

function defaultDelay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function terminalError(state) {
  const error = new Error(state?.error?.message ?? `Terminal state: ${state?.status}`);
  error.code = state?.error?.code ?? state?.status?.toUpperCase() ?? "TERMINAL_FAILURE";
  return error;
}

export async function waitForTerminalState(read, {
  delay = defaultDelay,
  pollIntervalMs = 2_500,
  timeoutMs = 30 * 60 * 1000,
  now = () => Date.now(),
  success = new Set(["needs_confirmation", "needs-input", "ready", "completed"]),
} = {}) {
  const deadline = now() + timeoutMs;
  for (;;) {
    const state = await read();
    if (["failed", "research_failed"].includes(state?.status)) throw terminalError(state);
    if (success.has(state?.status)) return state;
    if (now() >= deadline) {
      const error = new Error("Timed out waiting for terminal state.");
      error.code = "TIMEOUT";
      throw error;
    }
    await delay(pollIntervalMs);
  }
}

async function verifiedSnapshot(store, problemId, { requiredCitationFormulaId = null } = {}) {
  for (const snapshotId of [...await store.list(problemId)].reverse()) {
    try {
      const snapshot = await store.verify(problemId, snapshotId);
      if (snapshot?.manifest?.snapshotId === snapshotId
        && snapshot.manifest.complete === true
        && (!requiredCitationFormulaId || snapshot.manifest.citation?.formulaId === requiredCitationFormulaId)) return snapshot;
    } catch {
      // A tampered or incomplete immutable snapshot is retained but never reused.
    }
  }
  return null;
}

async function reusableAssessment(store, problemId, snapshot) {
  if (!store?.listRuns || !store?.readInput || !store?.readAssessment || !store?.readReport) return null;
  for (const run of await store.listRuns(problemId)) {
    if (run.status !== "completed" || !run.summary) continue;
    try {
      const [input, assessment, report] = await Promise.all([
        store.readInput(problemId, run.runId),
        store.readAssessment(problemId, run.runId),
        store.readReport(problemId, run.runId),
      ]);
      if (input?.schemaVersion !== 2
        || input?.valuation?.snapshotId !== snapshot.manifest.snapshotId
        || input?.valuation?.contentHash !== snapshot.manifest.contentHash
        || assessment?.envelope?.language !== "en"
        || typeof report !== "string"
        || CJK.test(JSON.stringify(run.summary))
        || CJK.test(JSON.stringify(assessment))
        || CJK.test(report)) continue;
      return run;
    } catch {
      // Immutable incomplete or malformed runs are not reusable.
    }
  }
  return null;
}

export function createQecPortfolioBatchRunner({
  records = QEC_PORTFOLIO_PROBLEMS,
  validateCatalog = validateQecPortfolioCatalog,
  register,
  verifyIndex = async () => true,
  createManagers = null,
  valuationManager,
  valuationStore,
  assessmentManager,
  assessmentStore,
  verifyPortfolio = async () => ({ ok: true }),
  delay = defaultDelay,
  pollIntervalMs = 2_500,
  timeoutMs = 30 * 60 * 1000,
  requiredCitationFormulaId = SCIENTIFIC_DEMAND_FORMULA_ID,
  forceValuationRefresh = false,
} = {}) {
  if (typeof register !== "function") throw new TypeError("register is required.");
  if (typeof createManagers !== "function" && (!valuationManager || !valuationStore || !assessmentManager)) throw new TypeError("valuation and assessment dependencies are required.");
  const ordered = (records === QEC_PORTFOLIO_PROBLEMS
    ? [...QEC_PORTFOLIO_BATCH_PROBLEMS]
    : [PROB_001_VALUATION_PROFILE, ...records.filter((record) => record.id !== "Prob-001")])
    .sort((left, right) => left.id.localeCompare(right.id));

  async function poll(read, success) {
    return waitForTerminalState(read, { delay, pollIntervalMs, timeoutMs, success });
  }

  return Object.freeze({
    async run() {
      const phases = {};
      const problems = ordered.map((record) => ({ id: record.id, registration: "pending", valuation: "pending", assessment: "pending", error: null }));
      const validation = validateCatalog(records);
      phases.catalog = validation.ok ? "verified" : "failed";
      if (!validation.ok) return { status: "incomplete", phases, problems, errors: validation.errors };
      const registration = await register({ records: ordered.filter((record) => record.id !== "Prob-001") });
      phases.registration = registration;
      for (const row of problems) row.registration = registration.failed.some((failure) => failure.id === row.id)
        ? "failed" : registration.skipped.includes(row.id) ? "verified-existing" : row.id === "Prob-001" ? "existing" : "published";
      if (registration.failed.length) return { status: "incomplete", phases, problems, errors: registration.failed };
      phases.index = await verifyIndex() ? "verified" : "failed";
      if (phases.index === "failed") return { status: "incomplete", phases, problems };

      const managers = createManagers
        ? await createManagers()
        : { valuationManager, valuationStore, assessmentManager, assessmentStore };
      const activeValuationManager = managers.valuationManager;
      const activeValuationStore = managers.valuationStore;
      const activeAssessmentManager = managers.assessmentManager;
      const activeAssessmentStore = managers.assessmentStore;
      if (!activeValuationManager || !activeValuationStore || !activeAssessmentManager) {
        throw new TypeError("createManagers must provide valuation and assessment dependencies.");
      }

      for (const row of problems) {
        let snapshot = forceValuationRefresh
          ? null
          : await verifiedSnapshot(activeValuationStore, row.id, { requiredCitationFormulaId });
        if (snapshot) row.valuation = "verified-existing";
        else {
          try {
            const started = await activeValuationManager.start(row.id);
            if (!started?.accepted) throw Object.assign(new Error(started?.message ?? "Valuation start rejected."), { code: started?.code });
            const pending = await poll(() => activeValuationManager.getJob(started.runId), new Set(["needs_confirmation"]));
            const confirmation = {
              candidateHash: pending.candidate.contentHash,
              acceptedAnchorIds: pending.candidate.anchorCandidates.map((anchor) => anchor.id),
              assumptionDecisions: [],
            };
            const accepted = await activeValuationManager.confirm(started.runId, confirmation);
            if (!accepted?.accepted) throw Object.assign(new Error(accepted?.message ?? "Valuation confirmation rejected."), { code: accepted?.code });
            await poll(() => activeValuationManager.getJob(started.runId), new Set(["ready"]));
            const state = await activeValuationManager.getProblemState(row.id);
            snapshot = state?.readySnapshotId ? await activeValuationStore.verify(row.id, state.readySnapshotId) : null;
            if (!snapshot?.manifest?.complete
              || snapshot.manifest.citation?.formulaId !== requiredCitationFormulaId) {
              throw Object.assign(new Error(`No complete verified ${requiredCitationFormulaId} valuation snapshot.`), { code: "VALUATION_INCOMPLETE" });
            }
            row.valuation = "completed";
          } catch (error) {
            row.valuation = "failed";
            row.error = { code: "VALUATION_FAILED", message: error.message };
            row.assessment = "skipped";
            continue;
          }
        }
        const reusable = await reusableAssessment(activeAssessmentStore, row.id, snapshot);
        if (reusable) {
          row.assessment = "verified-existing";
          continue;
        }
        try {
          const started = await activeAssessmentManager.start(row.id, {
            valuationSnapshotId: snapshot.manifest.snapshotId,
            selectedAlternative: EXTERNAL_VALUATION_ALTERNATIVE,
          });
          if (!started?.accepted) throw Object.assign(new Error(started?.message ?? "Assessment start rejected."), { code: started?.code });
          const pending = await poll(() => activeAssessmentManager.getJob(started.runId), new Set(["needs-input", "completed"]));
          if (pending.status === "needs-input") {
            const selected = await activeAssessmentManager.select(started.runId, EXTERNAL_VALUATION_ALTERNATIVE);
            if (!selected?.accepted) throw Object.assign(new Error(selected?.message ?? "Assessment selection rejected."), { code: selected?.code });
            await poll(() => activeAssessmentManager.getJob(selected.runId), new Set(["completed"]));
          }
          row.assessment = "completed";
        } catch (error) {
          row.assessment = "failed";
          row.error = row.error ?? { code: "ASSESSMENT_FAILED", message: error.message };
        }
      }
      const verification = await verifyPortfolio();
      phases.verification = verification;
      const status = problems.some((row) => row.error) || !verification.ok ? "incomplete" : "complete";
      return { status, phases, problems };
    },
  });
}

export async function verifyQecPortfolio({ rootDir }) {
  const errors = [];
  const problemIds = [];
  const snapshotIds = {};
  const assessmentRunIds = {};
  const citationFormulaIds = {};
  const valuationStore = createValuationSnapshotStore({ rootDir });
  const artifactStore = createArtifactStore({ rootDir });
  const assessmentStore = {
    ...artifactStore,
    async readAssessment(problemId, runId) {
      const runDir = await resolveExistingRunDir(rootDir, problemId, runId);
      return JSON.parse(await readFile(join(runDir, "assessment.json"), "utf8"));
    },
    async readReport(problemId, runId) {
      const runDir = await resolveExistingRunDir(rootDir, problemId, runId);
      return readFile(join(runDir, "report.html"), "utf8");
    },
  };
  const qecIds = [];
  try {
    const entries = await readdir(join(rootDir, "problems"), { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      try {
        const manifest = JSON.parse(await readFile(join(rootDir, "problems", entry.name, "problem.json"), "utf8"));
        if (manifest.domain === "quantum-computing" && manifest.quantumArea === "error-correction-and-fault-tolerance") qecIds.push(manifest.id);
      } catch {
        // Each expected portfolio member receives a specific diagnostic below.
      }
    }
  } catch (error) {
    errors.push(`Cannot read problem manifests: ${error.message}`);
  }
  if (JSON.stringify(qecIds.sort()) !== JSON.stringify(EXPECTED_IDS)) errors.push("QEC portfolio IDs are not exactly Prob-001 through Prob-021.");
  for (const id of EXPECTED_IDS) {
    try {
      const manifest = JSON.parse(await readFile(join(rootDir, "problems", id, "problem.json"), "utf8"));
      if (manifest.domain !== "quantum-computing" || manifest.quantumArea !== "error-correction-and-fault-tolerance") errors.push(`${id} is not a QEC portfolio problem.`);
      if (id !== "Prob-001") {
        const record = QEC_PORTFOLIO_PROBLEMS.find((item) => item.id === id);
        if (JSON.stringify(manifest) !== JSON.stringify(renderProblemManifest(record))) errors.push(`${id} manifest does not match the approved catalog.`);
        const markdown = await readFile(join(rootDir, "problems", id, "problem.md"), "utf8");
        if (CJK.test(JSON.stringify(manifest)) || CJK.test(markdown)) errors.push(`${id} visible draft content is not English-only.`);
      }
      problemIds.push(id);
      const snapshot = await verifiedSnapshot(valuationStore, id, { requiredCitationFormulaId: SCIENTIFIC_DEMAND_FORMULA_ID });
      if (!snapshot) { errors.push(`${id} has no complete verified ${SCIENTIFIC_DEMAND_FORMULA_ID} snapshot.`); continue; }
      snapshotIds[id] = snapshot.manifest.snapshotId;
      citationFormulaIds[id] = snapshot.manifest.citation.formulaId;
      const reusable = await reusableAssessment(assessmentStore, id, snapshot);
      if (!reusable) { errors.push(`${id} has no completed bound English assessment.`); continue; }
      assessmentRunIds[id] = reusable.runId;
    } catch (error) {
      errors.push(`${id}: ${error.message}`);
    }
  }
  return { ok: errors.length === 0, problemIds, snapshotIds, citationFormulaIds, assessmentRunIds, errors };
}
