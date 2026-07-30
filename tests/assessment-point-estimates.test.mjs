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
  papers = [{ id: "W1", citedByCount: 3 }],
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
          manifest: { citation: { rawCitationTotal } },
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
  assert.equal(result.scientificAttention.interval.base, 3);
  assert.equal(result.scientificAttention.unit, "count");
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

test("falls back to anchor-paper counts and records missing citation inputs", () => {
  const value = fixture({
    rawCitationTotal: null,
    papers: [
      { id: "W1", citedByCount: 4 },
      { id: "W2" },
      { id: "W3", citedByCount: 7 },
    ],
  });
  const result = deriveAssessmentPointEstimates(value);

  assert.equal(result.scientificAttention.interval.base, 11);
  assert.equal(result.scientificAttention.missingCitationCount, 1);
});

test("uses zero for an anchor set without citation counts", () => {
  const result = deriveAssessmentPointEstimates(fixture({
    rawCitationTotal: null,
    papers: [{ id: "W1" }],
  }));

  assert.equal(result.scientificAttention.interval.base, 0);
  assert.equal(result.scientificAttention.missingCitationCount, 1);
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
