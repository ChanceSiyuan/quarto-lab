import assert from "node:assert/strict";
import test from "node:test";

import { calculateCitationMetrics } from "../lib/valuations/citations.mjs";

function paper(overrides = {}) {
  return {
    id: "W1",
    relevance: 1,
    matchConfidence: 1,
    institutionIds: ["I1"],
    citationNormalizedPercentile: 0.5,
    citedByCount: 0,
    countsByYear: [
      { year: 2024, citedByCount: 2 },
      { year: 2025, citedByCount: 2 },
    ],
    ...overrides,
  };
}

test("calculates the versioned Scientific Demand Score from influence, momentum, and breadth", () => {
  const result = calculateCitationMetrics([
    paper({ id: "W1", institutionIds: ["I1"], citationNormalizedPercentile: 0.2 }),
    paper({ id: "W2", institutionIds: ["I2"], citationNormalizedPercentile: 0.4 }),
    paper({ id: "W3", institutionIds: ["I3"], citationNormalizedPercentile: 0.6 }),
    paper({ id: "W4", institutionIds: ["I4"], citationNormalizedPercentile: 0.8 }),
    paper({ id: "W5", institutionIds: ["I5"], citationNormalizedPercentile: 1 }),
  ], { currentYear: 2026 });

  assert.equal(result.formulaId, "qec-scientific-demand-v1");
  assert.equal(result.components.influence.weight, 0.45);
  assert.equal(result.components.influence.value, 0.6);
  assert.equal(result.components.momentum.weight, 0.30);
  assert.equal(result.components.momentum.value, 0.5);
  assert.equal(result.components.breadth.weight, 0.15);
  assert.equal(result.scientificDemand.state, "known");
  assert.equal(result.scientificDemand.unit, "score-100");
  assert.equal(result.scientificDemand.interval.base, 56.5);
  assert.equal(result.scientificAttention, result.scientificDemand);
  assert.equal(result.evidenceConfidence, "high");
  assert.equal(result.coverage, 1);
});

test("uses available nonzero demand components without fabricating a zero", () => {
  const result = calculateCitationMetrics([paper({ citationNormalizedPercentile: null })], { currentYear: 2026 });
  assert.equal(result.components.influence.availability, "unknown");
  assert.equal(result.components.breadth.availability, "known");
  assert.equal(result.scientificDemand.state, "known");
  assert.equal(result.scientificDemand.interval.base, 40.9);
  assert.ok(result.scientificDemand.interval.base > 0);
  assert.equal(result.scientificAttention, result.scientificDemand);
  assert.equal(result.coverage, 0);
  assert.equal(result.evidenceConfidence, "low");
});

test("maps the evidence-weighted median momentum through a logistic transform", () => {
  const result = calculateCitationMetrics([
    paper({ id: "W1", institutionIds: ["I1"], countsByYear: [{ year: 2024, citedByCount: 1 }, { year: 2025, citedByCount: 3 }] }),
    paper({ id: "W2", institutionIds: ["I2"], relevance: 0.1, countsByYear: [{ year: 2024, citedByCount: 100 }, { year: 2025, citedByCount: 0 }] }),
  ], { currentYear: 2026 });
  assert.equal(result.components.momentum.availability, "known");
  assert.equal(result.components.momentum.rawLogGrowth, Math.log(2));
  assert.equal(result.components.momentum.value, 2 / 3);
});

test("renormalizes available weights when momentum is missing", () => {
  const result = calculateCitationMetrics([
    paper({
      citationNormalizedPercentile: 0.8,
      countsByYear: [],
    }),
  ], { currentYear: 2026 });

  assert.equal(result.components.momentum.availability, "unknown");
  assert.equal(result.availableWeight, 0.6);
  assert.equal(result.scientificDemand.interval.base, 65.7);
  assert.equal(result.evidenceConfidence, "low");
});

test("excludes missing raw citation counts and reports evidence confidence by coverage", () => {
  const medium = calculateCitationMetrics([
    paper({ id: "W1", institutionIds: ["I1"], citedByCount: null }),
    paper({ id: "W2", institutionIds: ["I2"], citedByCount: 7 }),
    paper({ id: "W3", institutionIds: ["I3"], citedByCount: null }),
  ], { currentYear: 2026 });
  const low = calculateCitationMetrics([
    paper({ id: "W1", citedByCount: null }),
  ], { currentYear: 2026 });

  assert.equal(medium.rawCitationTotal, 7);
  assert.equal(medium.rawCitationObservedPaperCount, 1);
  assert.equal(medium.rawCitationMissingPaperCount, 2);
  assert.equal(medium.evidenceConfidence, "medium");
  assert.equal(low.evidenceConfidence, "low");
});
