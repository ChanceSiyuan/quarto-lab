import assert from "node:assert/strict";
import test from "node:test";

import { createQecPortfolioReader } from "../../src/lib/qec-portfolio/reader.mjs";
import { sortPortfolioRows } from "../../src/lib/qec-portfolio/view-model.mjs";

const QEC_AREA = "error-correction-and-fault-tolerance";

function summary(problemId, runId, combined, {
  researchValue = combined,
  autoresearchFit = combined,
  scientificAttention = {
    state: "known",
    interval: { low: 68.4, base: 68.4, high: 68.4 },
    unit: "score-100",
    formulaId: "qec-scientific-demand-v1",
    evidenceConfidence: "medium",
  },
  technicalSuccess = { state: "known", interval: { low: 60, base: 60, high: 60 }, unit: "percent", estimateKind: "model" },
} = {}) {
  return {
    runId,
    problemId,
    verdict: combined === null ? "DEFER" : "DO_NOW",
    confidence: "medium",
    scores: {
      researchValue: researchValue === null ? null : { min: researchValue - 1, estimate: researchValue, max: researchValue + 1 },
      autoresearchSuitability: autoresearchFit === null ? null : { min: autoresearchFit - 1, estimate: autoresearchFit, max: autoresearchFit + 1 },
      combined: combined === null ? null : { min: combined - 1, estimate: combined, max: combined + 1 },
    },
    largestBottleneck: combined === null ? null : `Bottleneck for ${problemId}`,
    reportHref: `/__local/assessments/reports/${problemId}/${runId}`,
    quantitative: {
      scientificAttention,
      technicalSuccess,
      socialValue: { state: "unknown", reason: "No model." },
      capturableValue: { state: "unknown", reason: "No pricing evidence." },
      snapshotId: `snapshot-${problemId}`,
    },
    privateInputs: { token: "must-not-leak" },
    eventsText: "must-not-leak",
  };
}

function fixtureReader() {
  const problems = Array.from({ length: 21 }, (_, index) => {
    const id = `Prob-${String(index + 1).padStart(3, "0")}`;
    return {
      id,
      title: `QEC ${id}`,
      status: "draft",
      domain: "quantum-computing",
      quantumArea: QEC_AREA,
    };
  });
  problems.push({
    id: "Prob-999",
    title: "Different area",
    status: "draft",
    domain: "quantum-computing",
    quantumArea: "hardware-and-control",
  });
  const runs = new Map(problems.slice(0, 21).map((problem) => [problem.id, [{
    runId: `run-${problem.id}`,
    status: "completed",
    updatedAt: "2026-07-29T09:00:00.000Z",
    summary: summary(problem.id, `run-${problem.id}`, 40),
  }]]));
  runs.set("Prob-002", [{ runId: "run-2", status: "completed", updatedAt: "2026-07-29T10:00:00.000Z", summary: summary("Prob-002", "run-2", 80) }]);
  runs.set("Prob-003", [
      { runId: "run-old", status: "completed", updatedAt: "2026-07-28T10:00:00.000Z", summary: summary("Prob-003", "run-old", 99) },
      { runId: "run-3", status: "completed", updatedAt: "2026-07-29T11:00:00.000Z", summary: summary("Prob-003", "run-3", 95, { scientificAttention: { state: "known", interval: { low: 90, base: 91, high: 92 } } }) },
      { runId: "run-incomplete", status: "needs-input", updatedAt: "2026-07-30T10:00:00.000Z", summary: summary("Prob-003", "run-incomplete", 100) },
  ]);
  return createQecPortfolioReader({
    repository: { listProblems: () => problems },
    assessmentStore: { listRuns: async (problemId) => runs.get(problemId) ?? [] },
  });
}

test("returns all QEC rows with the newest completed summary and public fields only", async () => {
  const response = await fixtureReader().read();
  assert.equal(response.schemaVersion, 1);
  assert.equal(response.evidenceLabel, "External-evidence-backed advisory comparison");
  assert.equal(response.count, 21);
  assert.deepEqual(response.rows.slice(0, 3).map((row) => row.problemId), ["Prob-003", "Prob-002", "Prob-001"]);
  assert.equal(response.rows[0].problemHref, "/problems/Prob-003");
  assert.equal(response.rows[0].reportHref, "/__local/assessments/reports/Prob-003/run-3");
  assert.equal(response.rows[0].combinedPriority.estimate, 95);
  assert.equal(response.rows[0].technicalSuccess.state, "known");
  assert.equal(response.rows[0].socialValue.state, "known");
  assert.equal(response.rows[0].capturableValue.state, "known");
  assert.equal(response.rows[0].capturableValue.id, "ibm-quantum-investment-floor-2026");
  assert.equal(response.rows[0].capturableValue.interval.base, 10_000_000_000);
  assert.doesNotMatch(JSON.stringify(response.rows), /"state":"unknown"|Unknown/i);
  for (const row of response.rows) {
    assert.equal(row.scientificAttention.state, "known");
    assert.equal(Number.isFinite(row.scientificAttention.interval.base), true);
    assert.equal(row.technicalSuccess.state, "known");
    assert.equal(Number.isFinite(row.technicalSuccess.interval.base), true);
    assert.equal(row.socialValue.state, "known");
    assert.equal(row.capturableValue.state, "known");
  }
  assert.doesNotMatch(JSON.stringify(response), /pending|not-modeled|Pending sealed evaluation/i);
  assert.deepEqual(Object.keys(response.rows[0]), [
    "problemId", "title", "status", "verdict", "confidence", "researchValue", "autoresearchFit", "combinedPriority",
    "scientificAttention", "technicalSuccess", "socialValue", "capturableValue", "largestBottleneck", "snapshotId", "problemHref", "reportHref",
  ]);
  assert.doesNotMatch(JSON.stringify(response), /must-not-leak/);
});

test("rejects an incomplete public portfolio row instead of displaying pending metrics", async () => {
  const incomplete = summary("Prob-002", "run-2", 80, {
    scientificAttention: { state: "unknown", reason: "No citation point." },
    technicalSuccess: { state: "unknown", reason: "No technical point." },
  });
  const reader = createQecPortfolioReader({
    repository: {
      listProblems: () => [{
        id: "Prob-002",
        title: "Incomplete public fixture",
        status: "draft",
        domain: "quantum-computing",
        quantumArea: QEC_AREA,
      }],
    },
    assessmentStore: {
      listRuns: async () => [{
        runId: "run-2",
        status: "completed",
        updatedAt: "2026-07-29T10:00:00.000Z",
        summary: incomplete,
      }],
    },
  });

  await assert.rejects(
    () => reader.read(),
    /Prob-002.*scientificAttention.*technicalSuccess/,
  );
});

test("sorts public portfolio copies without mutating the source rows", () => {
  const rows = [
    { problemId: "Prob-003", combinedPriority: { estimate: 80 }, researchValue: { estimate: 10 }, autoresearchFit: { estimate: 30 }, verdict: "DEFER", scientificAttention: { interval: { base: 20 } } },
    { problemId: "Prob-002", combinedPriority: { estimate: 80 }, researchValue: { estimate: 50 }, autoresearchFit: { estimate: 20 }, verdict: "DO_NOW", scientificAttention: { interval: { base: 30 } } },
    { problemId: "Prob-001", combinedPriority: null, researchValue: null, autoresearchFit: null, verdict: null, scientificAttention: null },
  ];
  assert.deepEqual(sortPortfolioRows(rows).map((row) => row.problemId), ["Prob-002", "Prob-003", "Prob-001"]);
  assert.deepEqual(sortPortfolioRows(rows, "research-value").map((row) => row.problemId), ["Prob-002", "Prob-003", "Prob-001"]);
  assert.deepEqual(sortPortfolioRows(rows, "autoresearch-fit").map((row) => row.problemId), ["Prob-003", "Prob-002", "Prob-001"]);
  assert.deepEqual(sortPortfolioRows(rows, "scientific-attention").map((row) => row.problemId), ["Prob-002", "Prob-003", "Prob-001"]);
  assert.deepEqual(sortPortfolioRows(rows, "verdict").map((row) => row.problemId), ["Prob-003", "Prob-002", "Prob-001"]);
  assert.deepEqual(rows.map((row) => row.problemId), ["Prob-003", "Prob-002", "Prob-001"]);
});

test("redacts private assessment values and leaves store-owned run order unchanged", async () => {
  const privateSummary = summary("Prob-001", "private-run", 77, {
    scientificAttention: {
      visibility: "private",
      state: "known",
      interval: { low: 700, base: 777, high: 800 },
      sources: [{ url: "https://private.example/value", locator: "Private locator" }],
    },
  });
  privateSummary.visibility = "private";
  privateSummary.quantitative.technicalSuccess = {
    visibility: "private",
    value: 1,
    sources: [{ url: "https://private.example/success", locator: "Secret success" }],
  };
  const runs = [
    { runId: "old-run", status: "completed", updatedAt: "2026-07-28T10:00:00.000Z", summary: summary("Prob-001", "old-run", 99) },
    { runId: "private-run", status: "completed", updatedAt: "2026-07-29T10:00:00.000Z", summary: privateSummary },
  ];
  const reader = createQecPortfolioReader({
    repository: {
      listProblems: () => [{ id: "Prob-001", title: "Private fixture", status: "draft", domain: "quantum-computing", quantumArea: QEC_AREA }],
    },
    assessmentStore: { listRuns: async () => runs },
  });

  const response = await reader.read();

  assert.deepEqual(runs.map((run) => run.runId), ["old-run", "private-run"]);
  assert.deepEqual(response.rows[0].combinedPriority, null);
  assert.equal(response.rows[0].scientificAttention, null);
  assert.equal(response.rows[0].technicalSuccess, null);
  assert.equal(response.rows[0].snapshotId, null);
  assert.doesNotMatch(JSON.stringify(response), /private\.example|Private locator|Secret success|777/);
});
