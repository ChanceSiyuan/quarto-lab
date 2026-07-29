import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  createQecPortfolioBatchRunner,
  EXTERNAL_VALUATION_ALTERNATIVE,
  waitForTerminalState,
} from "../lib/qec-portfolio/batch-runner.mjs";
import { QEC_PORTFOLIO_BATCH_IDS } from "../lib/qec-portfolio/batch-runner.mjs";
import { QEC_PORTFOLIO_PROBLEMS } from "../lib/qec-portfolio/catalog.mjs";
import { createLocalRepository, rebuildAndVerifyIndex } from "../scripts/run-qec-portfolio.mjs";

const RECORDS = [
  { id: "Prob-003", title: "Third", summary: "Third approved QEC problem.", technicalAnchor: { id: "anchor-Prob-003" } },
  { id: "Prob-002", title: "Second", summary: "Second approved QEC problem.", technicalAnchor: { id: "anchor-Prob-002" } },
];

function fixtureRunner({ records = RECORDS, verifiedSnapshot = false, completedAssessment = false, valuationFailure = false, createManagers = false } = {}) {
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
      return { manifest: { snapshotId, contentHash: `hash-${id}`, complete: true } };
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
    start: async (id) => { calls.assessmentStart.push(id); assessmentStatuses.set(`assessment-new-${id}`, "needs-input"); return { accepted: true, runId: `assessment-new-${id}` }; },
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

test("restart skips only verified snapshots and completed version-two assessments", async () => {
  const { runner, calls } = fixtureRunner({ verifiedSnapshot: true, completedAssessment: true });
  const summary = await runner.run();
  assert.equal(summary.status, "complete");
  assert.equal(summary.problems[0].valuation, "verified-existing");
  assert.equal(summary.problems[0].assessment, "verified-existing");
  assert.equal(calls.valuationStart.length, 0);
  assert.equal(calls.assessmentStart.length, 0);
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
  assert.equal(calls.assessmentStart.includes("Prob-001"), true);
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
