import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  createQecPortfolioBatchRunner,
  EXTERNAL_VALUATION_ALTERNATIVE,
  verifyQecPortfolio,
  waitForTerminalState,
} from "../lib/qec-portfolio/batch-runner.mjs";
import { QEC_PORTFOLIO_BATCH_IDS } from "../lib/qec-portfolio/batch-runner.mjs";
import { QEC_PORTFOLIO_PROBLEMS } from "../lib/qec-portfolio/catalog.mjs";
import { renderProblemManifest } from "../lib/qec-portfolio/registration.mjs";
import { VALUATION_ONLY_NOTICE } from "../lib/qec-portfolio/valuation-only-refresh.mjs";
import { createLocalRepository, rebuildAndVerifyIndex } from "../scripts/run-qec-portfolio.mjs";
import { SCIENTIFIC_DEMAND_FORMULA_ID } from "../lib/valuations/citations.mjs";
import { createValuationSnapshotStore } from "../lib/valuations/snapshot-store.mjs";

const RECORDS = [
  { id: "Prob-003", title: "Third", summary: "Third approved QEC problem.", technicalAnchor: { id: "anchor-Prob-003" } },
  { id: "Prob-002", title: "Second", summary: "Second approved QEC problem.", technicalAnchor: { id: "anchor-Prob-002" } },
];

async function writeJson(path, value) {
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
}

function citationSource(problemId) {
  return {
    id: `citation-W${problemId.replace("Prob-", "")}`,
    url: `https://openalex.org/W${problemId.replace("Prob-", "")}`,
    locator: `OpenAlex work W${problemId.replace("Prob-", "")}`,
    kind: "citation-index",
  };
}

function citationValue(problemId, { id, unit, value, inferred }) {
  const source = citationSource(problemId);
  return {
    id,
    state: "known",
    interval: { low: value, base: value, high: value },
    unit,
    visibility: "public",
    evidenceState: inferred ? "inferred" : "reported",
    evidenceTier: "authoritative-secondary",
    sourceIds: [source.id],
    sources: [source],
    ...(inferred ? {
      estimateKind: "scientific-demand-model",
      derivation: { formulaId: SCIENTIFIC_DEMAND_FORMULA_ID, inputIds: [source.id] },
    } : {}),
  };
}

function snapshotManifest(problemId) {
  return {
    schemaVersion: 1,
    problemId,
    createdAt: "2026-07-30T01:02:03.000Z",
    complete: true,
    citation: {
      formulaId: SCIENTIFIC_DEMAND_FORMULA_ID,
      scientificDemand: citationValue(problemId, { id: "scientific-demand-score", unit: "score-100", value: 61.2, inferred: true }),
      scientificAttention: citationValue(problemId, { id: "scientific-demand-score", unit: "score-100", value: 61.2, inferred: true }),
      momentum: citationValue(problemId, { id: "citation-momentum", unit: "fraction", value: 0.2, inferred: false }),
      components: {
        influence: { availability: "known", value: 0.61, weight: 0.45, unit: "fraction" },
        momentum: { availability: "known", value: 0.2, weight: 0.30, unit: "fraction" },
        breadth: { availability: "known", value: 0.5, weight: 0.15, unit: "fraction" },
        network: { availability: "reserved", weight: 0.10 },
      },
      evidenceConfidence: "medium",
      coverage: 0.8,
      concentration: null,
      warnings: [],
      paperCount: 3,
    },
    feasibility: { state: "unknown", reason: "No sealed technical gate has been measured." },
    value: { state: "unknown", reason: "No problem-specific value model has been identified." },
  };
}

async function writeVerifierFixture(rootDir) {
  const valuationStore = createValuationSnapshotStore({
    rootDir,
    now: () => new Date("2026-07-30T01:02:03.000Z"),
  });
  const snapshots = {};
  for (const [index, problemId] of QEC_PORTFOLIO_BATCH_IDS.entries()) {
    const problemDir = join(rootDir, "problems", problemId);
    await mkdir(problemDir, { recursive: true });
    const record = QEC_PORTFOLIO_PROBLEMS.find((item) => item.id === problemId);
    const manifest = problemId === "Prob-001"
      ? {
          id: "Prob-001",
          title: "AutoQEC CSS Distance Campaign",
          summary: "Imported AutoQEC CSS-distance experimental audit record.",
          status: "active",
          domain: "quantum-computing",
          quantumArea: "error-correction-and-fault-tolerance",
        }
      : renderProblemManifest(record);
    await writeJson(join(problemDir, "problem.json"), manifest);
    await writeFile(join(problemDir, "problem.md"), `# ${manifest.title}\n\n${manifest.summary}\n`);
    const snapshot = await valuationStore.freeze(problemId, {
      manifest: snapshotManifest(problemId),
      papers: [],
      marketEvidence: [],
    });
    snapshots[problemId] = snapshot;
    const runId = `20260730T020304Z-${String(index + 1).padStart(6, "0")}`;
    const runDir = join(problemDir, "assessments", runId);
    await mkdir(runDir, { recursive: true });
    await writeJson(join(runDir, "run.json"), {
      schemaVersion: 1,
      runId,
      problemId,
      parentRunId: null,
      status: "completed",
      createdAt: "2026-07-30T02:03:04.000Z",
      updatedAt: "2026-07-30T02:04:04.000Z",
      error: null,
      summary: { runId, problemId, verdict: "DO_NOW" },
    });
    await writeJson(join(runDir, "input.json"), {
      schemaVersion: 2,
      problemId,
      valuation: {
        snapshotId: snapshot.manifest.snapshotId,
        contentHash: snapshot.manifest.contentHash,
      },
    });
    await writeJson(join(runDir, "assessment.json"), {
      envelope: { language: "en" },
    });
    await writeFile(join(runDir, "report.html"), "<!doctype html><html lang=\"en\"><body>Completed English report</body></html>");
  }
  return snapshots;
}

function fixtureRunner({
  records = RECORDS,
  verifiedSnapshot = false,
  snapshotFormulaId = SCIENTIFIC_DEMAND_FORMULA_ID,
  completedAssessment = false,
  valuationFailure = false,
  createManagers = false,
  forceValuationRefresh = false,
} = {}) {
  const calls = { register: [], valuationStart: [], confirm: [], assessmentStart: [], select: [], verify: [], phases: [] };
  const valuationStatuses = new Map();
  const assessmentStatuses = new Map();
  const snapshots = new Map();
  const valuationManager = {
    start: async (id) => { calls.valuationStart.push(id); valuationStatuses.set(`valuation-${id}`, valuationFailure ? "research_failed" : "needs_confirmation"); return { accepted: true, runId: `valuation-${id}` }; },
    getJob: (runId) => ({ status: valuationStatuses.get(runId), candidate: { contentHash: "a".repeat(64), anchorCandidates: [{ id: `anchor-${runId.replace("valuation-", "")}` }], materialAssumptions: [] } }),
    confirm: async (runId, confirmation) => { calls.confirm.push(confirmation); valuationStatuses.set(runId, "ready"); snapshots.set(runId, `snapshot-${runId.replace("valuation-", "")}`); return { accepted: true }; },
    getProblemState: async (id) => ({ readySnapshotId: snapshots.get(`valuation-${id}`) ?? `snapshot-${id}` }),
  };
  const valuationStore = {
    list: async (id) => verifiedSnapshot ? [`snapshot-${id}`] : [],
    verify: async (id, snapshotId) => {
      calls.verify.push([id, snapshotId]);
      const formulaId = calls.valuationStart.includes(id) ? SCIENTIFIC_DEMAND_FORMULA_ID : snapshotFormulaId;
      return { manifest: { snapshotId, contentHash: `hash-${id}`, complete: true, citation: { formulaId } } };
    },
  };
  const assessmentStore = {
    listRuns: async (id) => completedAssessment ? [{ runId: `assessment-${id}`, status: "completed", summary: { verdict: "DO_NOW" } }] : [],
    readInput: async (id, runId) => ({ schemaVersion: 2, valuation: { snapshotId: `snapshot-${id}`, contentHash: `hash-${id}` } }),
    readRun: async (id, runId) => ({ status: "completed", summary: { verdict: "DO_NOW" } }),
    readAssessment: async () => ({ envelope: { language: "en" } }),
    readReport: async () => "<html>English report</html>",
  };
  const assessmentManager = {
    start: async (id, options = {}) => { calls.assessmentStart.push({ id, options }); assessmentStatuses.set(`assessment-new-${id}`, "needs-input"); return { accepted: true, runId: `assessment-new-${id}` }; },
    getJob: (runId) => ({ status: assessmentStatuses.get(runId) }),
    select: async (runId, alternative) => { calls.select.push({ runId, alternative }); const selected = `${runId}-selected`; assessmentStatuses.set(selected, "completed"); return { accepted: true, runId: selected }; },
  };
  const runner = createQecPortfolioBatchRunner({
    records,
    validateCatalog: () => ({ ok: true, errors: [] }),
    register: async (options) => { calls.phases.push("register"); calls.register.push(options.records.map((record) => record.id)); return { published: options.records.map((record) => record.id), skipped: [], failed: [] }; },
    verifyIndex: async () => { calls.phases.push("index"); return true; },
    ...createManagers ? {
      createManagers: async () => {
        calls.phases.push("managers");
        return { valuationManager, valuationStore, assessmentManager, assessmentStore };
      },
    } : { valuationManager, valuationStore, assessmentManager, assessmentStore },
    verifyPortfolio: async () => ({ ok: !valuationFailure }),
    delay: async () => {},
    pollIntervalMs: 0,
    requiredCitationFormulaId: SCIENTIFIC_DEMAND_FORMULA_ID,
    forceValuationRefresh,
  });
  return { runner, calls };
}

test("confirms approved anchors and selects only the external valuation alternative", async () => {
  const { runner, calls } = fixtureRunner();
  const summary = await runner.run();
  assert.equal(summary.status, "complete");
  assert.deepEqual(calls.register[0], ["Prob-002", "Prob-003"]);
  assert.deepEqual(calls.confirm.find((confirmation) => confirmation.acceptedAnchorIds[0] === "anchor-Prob-002"), {
    candidateHash: "a".repeat(64),
    acceptedAnchorIds: ["anchor-Prob-002"],
    assumptionDecisions: [],
  });
  assert.deepEqual(calls.select[0].alternative, EXTERNAL_VALUATION_ALTERNATIVE);
});

test("starts fresh portfolio assessments through the explicit external valuation route", async () => {
  const { runner, calls } = fixtureRunner();

  await runner.run();

  assert.deepEqual(calls.assessmentStart[0], {
    id: "Prob-001",
    options: {
      valuationSnapshotId: "snapshot-Prob-001",
      selectedAlternative: EXTERNAL_VALUATION_ALTERNATIVE,
    },
  });
});

test("restart skips only verified snapshots and completed version-two assessments", async () => {
  const { runner, calls } = fixtureRunner({ verifiedSnapshot: true, completedAssessment: true });
  const summary = await runner.run();
  assert.equal(summary.status, "complete");
  assert.equal(summary.problems[0].valuation, "verified-existing");
  assert.equal(summary.problems[0].assessment, "verified-existing");
  assert.equal(calls.valuationStart.length, 0);
  assert.equal(calls.assessmentStart.length, 0);
});

test("replaces an old-formula snapshot with a new immutable valuation", async () => {
  const { runner, calls } = fixtureRunner({
    verifiedSnapshot: true,
    snapshotFormulaId: null,
    completedAssessment: true,
  });

  const summary = await runner.run();

  assert.equal(summary.problems[0].valuation, "completed");
  assert.equal(calls.valuationStart.includes("Prob-001"), true);
  assert.ok(calls.verify.some(([, snapshotId]) => snapshotId === "snapshot-Prob-001"));
});

test("force refresh creates a new valuation even when the current formula exists", async () => {
  const { runner, calls } = fixtureRunner({
    verifiedSnapshot: true,
    completedAssessment: true,
    forceValuationRefresh: true,
  });

  const summary = await runner.run();

  assert.equal(summary.problems[0].valuation, "completed");
  assert.equal(calls.valuationStart.includes("Prob-001"), true);
});

test("includes the existing Prob-001 profile in the production-shaped 21-problem valuation and assessment batch", async () => {
  const { runner, calls } = fixtureRunner({ records: QEC_PORTFOLIO_PROBLEMS });
  const summary = await runner.run();
  const prob001 = summary.problems.find((row) => row.id === "Prob-001");
  assert.deepEqual(calls.register[0], QEC_PORTFOLIO_PROBLEMS.map((record) => record.id));
  assert.deepEqual(summary.problems.map((row) => row.id), QEC_PORTFOLIO_BATCH_IDS);
  assert.equal(prob001.valuation, "completed");
  assert.equal(prob001.assessment, "completed");
  assert.equal(calls.valuationStart.includes("Prob-001"), true);
  assert.equal(calls.assessmentStart.some((call) => call.id === "Prob-001"), true);
});

test("creates managers only after registration and rebuilt-index verification", async () => {
  const { runner, calls } = fixtureRunner({ createManagers: true });
  await runner.run();
  assert.deepEqual(calls.phases.slice(0, 3), ["register", "index", "managers"]);
});

test("rebuild verification requires the explicit 21-problem batch ID set", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "qec-portfolio-index-"));
  await mkdir(join(rootDir, ".generated"), { recursive: true });
  const writeIndex = async (ids) => writeFile(join(rootDir, ".generated", "problem-index.json"), JSON.stringify({
    problems: ids.map((id) => ({
      id,
      domain: "quantum-computing",
      quantumArea: "error-correction-and-fault-tolerance",
    })),
  }));
  await writeIndex(QEC_PORTFOLIO_BATCH_IDS);
  assert.equal(await rebuildAndVerifyIndex(rootDir, { execFileFn: async () => ({ stdout: "" }) }), true);
  await writeIndex(QEC_PORTFOLIO_BATCH_IDS.filter((id) => id !== "Prob-001"));
  assert.equal(await rebuildAndVerifyIndex(rootDir, { execFileFn: async () => ({ stdout: "" }) }), false);
});

test("manager repository construction reads the rebuilt index state", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "qec-portfolio-repository-"));
  await mkdir(join(rootDir, ".generated"), { recursive: true });
  await writeFile(join(rootDir, ".generated", "problem-index.json"), JSON.stringify({
    summary: {},
    diagnostics: [],
    problems: [
      { id: "Prob-001", title: "Existing", summary: "Existing", domain: "quantum-computing", quantumArea: "error-correction-and-fault-tolerance" },
      { id: "Prob-002", title: "Fresh", summary: "Published after registration", domain: "quantum-computing", quantumArea: "error-correction-and-fault-tolerance" },
    ],
  }));
  const repository = await createLocalRepository(rootDir);
  assert.equal(repository.getProblem("Prob-002")?.summary, "Published after registration");
});

test("continues diagnostics after a terminal valuation failure and marks the batch incomplete", async () => {
  const { runner, calls } = fixtureRunner({ valuationFailure: true });
  const summary = await runner.run();
  assert.equal(summary.status, "incomplete");
  assert.equal(summary.problems[0].error.code, "VALUATION_FAILED");
  assert.deepEqual(calls.valuationStart, ["Prob-001", "Prob-002", "Prob-003"]);
});

test("polling rejects a terminal failure and deadline", async () => {
  await assert.rejects(
    waitForTerminalState(() => ({ status: "failed", error: { code: "FAILED" } }), { delay: async () => {}, timeoutMs: 1 }),
    (error) => error.code === "FAILED",
  );
});

test("portfolio verification rejects malformed valuation-only derivation provenance", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "qec-portfolio-derivation-"));
  const snapshots = await writeVerifierFixture(rootDir);
  const runId = "20260730T020304Z-000001";
  const derivationPath = join(rootDir, "problems", "Prob-001", "assessments", runId, "derivation.json");
  await writeJson(derivationPath, {
    schemaVersion: 1,
    kind: "qec-valuation-only-refresh",
    problemId: "Prob-001",
    runId,
    sourceRunId: "20260729T010203Z-abcdef",
    sourceSnapshotId: "20260729T010203Z-111111111111",
    refreshedSnapshotId: snapshots["Prob-001"].manifest.snapshotId,
    notice: "Malformed notice",
  });

  const malformed = await verifyQecPortfolio({ rootDir });

  assert.equal(malformed.ok, false);
  assert.match(malformed.errors.join("\n"), /invalid valuation-only derivation provenance/);

  await writeJson(derivationPath, {
    schemaVersion: 1,
    kind: "qec-valuation-only-refresh",
    problemId: "Prob-001",
    runId,
    sourceRunId: "20260729T010203Z-abcdef",
    sourceSnapshotId: "20260729T010203Z-111111111111",
    refreshedSnapshotId: snapshots["Prob-001"].manifest.snapshotId,
    notice: VALUATION_ONLY_NOTICE,
  });

  const valid = await verifyQecPortfolio({ rootDir });
  assert.equal(valid.ok, true, valid.errors.join("\n"));
});
