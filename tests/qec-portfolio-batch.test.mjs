import assert from "node:assert/strict";
import test from "node:test";

import {
  createQecPortfolioBatchRunner,
  EXTERNAL_VALUATION_ALTERNATIVE,
  waitForTerminalState,
} from "../lib/qec-portfolio/batch-runner.mjs";

const RECORDS = [
  { id: "Prob-003", title: "Third", summary: "Third approved QEC problem.", technicalAnchor: { id: "anchor-Prob-003" } },
  { id: "Prob-002", title: "Second", summary: "Second approved QEC problem.", technicalAnchor: { id: "anchor-Prob-002" } },
];

function fixtureRunner({ verifiedSnapshot = false, completedAssessment = false, valuationFailure = false } = {}) {
  const calls = { register: [], valuationStart: [], confirm: [], assessmentStart: [], select: [], verify: [] };
  const valuationStatuses = new Map();
  const assessmentStatuses = new Map();
  const snapshots = new Map();
  const runner = createQecPortfolioBatchRunner({
    records: RECORDS,
    validateCatalog: () => ({ ok: true, errors: [] }),
    register: async (options) => { calls.register.push(options.records.map((record) => record.id)); return { published: options.records.map((record) => record.id), skipped: [], failed: [] }; },
    verifyIndex: async () => true,
    valuationStore: {
      list: async (id) => verifiedSnapshot ? [`snapshot-${id}`] : [],
      verify: async (id, snapshotId) => {
        calls.verify.push([id, snapshotId]);
        return { manifest: { snapshotId, contentHash: `hash-${id}`, complete: true } };
      },
    },
    valuationManager: {
      start: async (id) => { calls.valuationStart.push(id); valuationStatuses.set(`valuation-${id}`, valuationFailure ? "research_failed" : "needs_confirmation"); return { accepted: true, runId: `valuation-${id}` }; },
      getJob: (runId) => ({ status: valuationStatuses.get(runId), candidate: { contentHash: "a".repeat(64), anchorCandidates: [{ id: `anchor-${runId.replace("valuation-", "")}` }], materialAssumptions: [] } }),
      confirm: async (runId, confirmation) => { calls.confirm.push(confirmation); valuationStatuses.set(runId, "ready"); snapshots.set(runId, `snapshot-${runId.replace("valuation-", "")}`); return { accepted: true }; },
      getProblemState: async (id) => ({ readySnapshotId: snapshots.get(`valuation-${id}`) ?? `snapshot-${id}` }),
    },
    assessmentStore: {
      listRuns: async (id) => completedAssessment ? [{ runId: `assessment-${id}`, status: "completed", summary: { verdict: "DO_NOW" } }] : [],
      readInput: async (id, runId) => ({ schemaVersion: 2, valuation: { snapshotId: `snapshot-${id}`, contentHash: `hash-${id}` } }),
      readRun: async (id, runId) => ({ status: "completed", summary: { verdict: "DO_NOW" } }),
      readAssessment: async () => ({ envelope: { language: "en" } }),
      readReport: async () => "<html>English report</html>",
    },
    assessmentManager: {
      start: async (id) => { calls.assessmentStart.push(id); assessmentStatuses.set(`assessment-new-${id}`, "needs-input"); return { accepted: true, runId: `assessment-new-${id}` }; },
      getJob: (runId) => ({ status: assessmentStatuses.get(runId) }),
      select: async (runId, alternative) => { calls.select.push({ runId, alternative }); const selected = `${runId}-selected`; assessmentStatuses.set(selected, "completed"); return { accepted: true, runId: selected }; },
    },
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
  assert.deepEqual(calls.confirm[0], {
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

test("continues diagnostics after a terminal valuation failure and marks the batch incomplete", async () => {
  const { runner, calls } = fixtureRunner({ valuationFailure: true });
  const summary = await runner.run();
  assert.equal(summary.status, "incomplete");
  assert.equal(summary.problems[0].error.code, "VALUATION_FAILED");
  assert.deepEqual(calls.valuationStart, ["Prob-002", "Prob-003"]);
});

test("polling rejects a terminal failure and deadline", async () => {
  await assert.rejects(
    waitForTerminalState(() => ({ status: "failed", error: { code: "FAILED" } }), { delay: async () => {}, timeoutMs: 1 }),
    (error) => error.code === "FAILED",
  );
});
