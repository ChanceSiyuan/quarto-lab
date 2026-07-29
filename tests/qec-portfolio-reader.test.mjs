import assert from "node:assert/strict";
import test from "node:test";

import { createQecPortfolioReader } from "../lib/qec-portfolio/reader.mjs";
import { sortPortfolioRows } from "../lib/qec-portfolio/view-model.mjs";

const QEC_AREA = "error-correction-and-fault-tolerance";

function summary(problemId, runId, combined, { researchValue = combined, autoresearchFit = combined, scientificAttention = null } = {}) {
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
      technicalSuccess: { state: "unknown", reason: "Not run." },
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
  const runs = new Map([
    ["Prob-002", [{ runId: "run-2", status: "completed", updatedAt: "2026-07-29T10:00:00.000Z", summary: summary("Prob-002", "run-2", 80) }]],
    ["Prob-003", [
      { runId: "run-old", status: "completed", updatedAt: "2026-07-28T10:00:00.000Z", summary: summary("Prob-003", "run-old", 99) },
      { runId: "run-3", status: "completed", updatedAt: "2026-07-29T11:00:00.000Z", summary: summary("Prob-003", "run-3", 95, { scientificAttention: { state: "known", interval: { low: 90, base: 91, high: 92 } } }) },
      { runId: "run-incomplete", status: "needs-input", updatedAt: "2026-07-30T10:00:00.000Z", summary: summary("Prob-003", "run-incomplete", 100) },
    ]],
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
  assert.equal(response.rows.at(-1).combinedPriority, null);
  assert.deepEqual(Object.keys(response.rows[0]), [
    "problemId", "title", "status", "verdict", "confidence", "researchValue", "autoresearchFit", "combinedPriority",
    "scientificAttention", "technicalSuccess", "socialValue", "capturableValue", "largestBottleneck", "snapshotId", "problemHref", "reportHref",
  ]);
  assert.doesNotMatch(JSON.stringify(response), /must-not-leak/);
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
