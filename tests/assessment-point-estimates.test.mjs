import assert from "node:assert/strict";
import test from "node:test";

import {
  TECHNICAL_SUCCESS_DIMENSION_WEIGHTS,
  deriveAssessmentPointEstimates,
} from "../lib/assessments/point-estimates.mjs";

function dimension(id, estimate) {
  return { id, score: { min: estimate, estimate, max: estimate } };
}

function fixture({
  measured = null,
  visibility = "public",
  rawCitationTotal = 3,
  citation = {
    formulaId: "qec-scientific-demand-v1",
    scientificDemand: {
      state: "known",
      interval: { low: 68.4, base: 68.4, high: 68.4 },
      unit: "score-100",
      visibility: "public",
    },
    components: {
      influence: { availability: "known", value: 0.72, weight: 0.45, unit: "fraction" },
      momentum: { availability: "known", value: 0.61, weight: 0.30, unit: "fraction" },
      breadth: { availability: "known", value: 0.45, weight: 0.15, unit: "fraction" },
      network: { availability: "reserved", weight: 0.10 },
    },
    evidenceConfidence: "high",
    coverage: 0.9,
    paperCount: 5,
    rawCitationTotal,
  },
  papers = [{ id: "W1", citedByCount: 3, citationNormalizedPercentile: 0.8, relevance: 1 }],
} = {}) {
  return {
    assessment: {
      visibility,
      dimensions: {
        researchValue: [dimension("plausibility", 3.75)],
        autoresearchSuitability: [
          dimension("executable_objective", 3),
          dimension("correctness_and_anti_gaming", 2.5),
          dimension("incremental_feedback", 3.5),
          dimension("attempt_runtime", 3),
        ],
      },
      quantitativeEvidence: { technicalFeasibility: measured },
    },
    input: {
      valuation: {
        recalculationInputs: {
          manifest: {
            createdAt: "2026-07-29T01:02:03.000Z",
            citation,
          },
          papers,
        },
      },
    },
  };
}

test("technical-success weights sum to one", () => {
  assert.equal(
    Object.values(TECHNICAL_SUCCESS_DIMENSION_WEIGHTS).reduce((total, weight) => total + weight, 0),
    1,
  );
});

test("derives the approved technical-success point formula", () => {
  const result = deriveAssessmentPointEstimates(fixture());

  assert.equal(result.technicalSuccess.interval.base, 64.8);
  assert.deepEqual(result.technicalSuccess.interval, { low: 64.8, base: 64.8, high: 64.8 });
  assert.equal(result.technicalSuccess.unit, "percent");
  assert.equal(result.technicalSuccess.estimateKind, "model");
  assert.equal(result.technicalSuccessMethod.formulaId, "qec-technical-success-v1");
  assert.equal(result.scientificAttention.interval.base, 68.4);
  assert.equal(result.scientificAttention.unit, "score-100");
  assert.equal(result.scientificAttention.estimateKind, "scientific-demand-model");
  assert.equal(result.scientificAttention.formulaId, "qec-scientific-demand-v1");
  assert.equal(result.scientificAttention.evidenceConfidence, "high");
});

test("preserves a measured technical result", () => {
  const measured = {
    state: "known",
    interval: { low: 70, base: 72.5, high: 75 },
    unit: "percent",
    visibility: "public",
  };
  const result = deriveAssessmentPointEstimates(fixture({ measured }));

  assert.equal(result.technicalSuccess, measured);
  assert.equal(result.technicalSuccessMethod.kind, "measured");
});

test("recalculates old snapshots from frozen normalized paper evidence", () => {
  const value = fixture({
    citation: { rawCitationTotal: 11 },
    papers: [
      { id: "W1", relevance: 1, citationNormalizedPercentile: 0.8, citedByCount: 4, institutionIds: ["I1"], countsByYear: [] },
      { id: "W2", relevance: 1, citationNormalizedPercentile: 0.6, institutionIds: ["I2"], countsByYear: [] },
    ],
  });
  const result = deriveAssessmentPointEstimates(value);

  assert.equal(result.scientificAttention.interval.base, 54);
  assert.equal(result.scientificAttention.unit, "score-100");
  assert.equal(result.scientificAttention.formulaId, "qec-scientific-demand-v1");
});

test("returns an evidence gap instead of zero when normalized evidence is absent", () => {
  const result = deriveAssessmentPointEstimates(fixture({
    citation: { rawCitationTotal: null },
    papers: [{ id: "W1" }],
  }));

  assert.equal(result.scientificAttention.state, "unknown");
  assert.match(result.scientificAttention.reason, /citation evidence insufficient/i);
});

test("does not derive public values from a private assessment", () => {
  assert.deepEqual(deriveAssessmentPointEstimates(fixture({ visibility: "private" })), {
    scientificAttention: null,
    technicalSuccess: null,
    technicalSuccessMethod: null,
  });
});

test("identifies every missing required dimension", () => {
  const value = fixture();
  value.assessment.dimensions.autoresearchSuitability = [];

  assert.throws(
    () => deriveAssessmentPointEstimates(value),
    /executable_objective, correctness_and_anti_gaming, incremental_feedback, attempt_runtime/,
  );
});
