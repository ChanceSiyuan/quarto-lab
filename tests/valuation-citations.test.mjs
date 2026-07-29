import assert from "node:assert/strict";
import test from "node:test";

import { calculateCitationMetrics } from "../lib/valuations/citations.mjs";

function paper(overrides = {}) {
  return {
    id: "W1",
    relevance: 1,
    citationNormalizedPercentile: 0.5,
    citedByCount: 0,
    countsByYear: [
      { year: 2024, citedByCount: 2 },
      { year: 2025, citedByCount: 8 },
    ],
    ...overrides,
  };
}

test("uses relevance-weighted normalized percentiles, not raw citations", () => {
  const result = calculateCitationMetrics([
    paper({ id: "W1", relevance: 1, citationNormalizedPercentile: 0.8, citedByCount: 10 }),
    paper({ id: "W2", relevance: 0.2, citationNormalizedPercentile: 0.2, citedByCount: 10000 }),
  ], { currentYear: 2026 });
  assert.equal(result.scientificAttention.state, "known");
  assert.equal(result.scientificAttention.interval.base, 80);
  assert.equal(result.rawCitationTotal, 10010);
  assert.equal(result.coverage, 1);
  assert.ok(result.concentration > 0.99);
});

test("returns unknown when comparable coverage is insufficient", () => {
  const result = calculateCitationMetrics([paper({ citationNormalizedPercentile: null })], { currentYear: 2026 });
  assert.equal(result.scientificAttention.state, "unknown");
  assert.match(result.scientificAttention.reason, /two comparable relevant papers/i);
  assert.equal(result.coverage, 0);
});

test("reports a relevance-weighted median momentum from complete years", () => {
  const result = calculateCitationMetrics([
    paper({ id: "W1", relevance: 1, countsByYear: [{ year: 2024, citedByCount: 1 }, { year: 2025, citedByCount: 3 }] }),
    paper({ id: "W2", relevance: 0.1, countsByYear: [{ year: 2024, citedByCount: 100 }, { year: 2025, citedByCount: 0 }] }),
  ], { currentYear: 2026 });
  assert.equal(result.momentum.state, "known");
  assert.equal(result.momentum.interval.base, Math.log(2));
});
