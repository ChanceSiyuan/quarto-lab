import assert from "node:assert/strict";
import test from "node:test";

import {
  getStaticEvaluation,
  getStaticEvaluationPoints,
} from "../../src/lib/pages-showcase/evaluation-scenarios.mjs";

const EXPECTED = {
  "Prob-124": { scientificDemand: 79, eansv: 300_000, autoresearchFit: 71 },
  "Prob-125": { scientificDemand: 85, eansv: 0, autoresearchFit: 85 },
  "Prob-126": { scientificDemand: 70, eansv: 800_000, autoresearchFit: 65 },
  "Prob-127": { scientificDemand: 81, eansv: 3_000_000, autoresearchFit: 98 },
  "Prob-128": { scientificDemand: 79, eansv: 1_400_000, autoresearchFit: 92 },
};

test("recomputes the five published Pages evaluation points from scenario inputs", () => {
  for (const [problemId, expected] of Object.entries(EXPECTED)) {
    assert.deepEqual(getStaticEvaluationPoints(problemId), expected, problemId);
  }
});

test("renders the same three metric definitions for every public Pages problem", () => {
  for (const problemId of Object.keys(EXPECTED)) {
    const evaluation = getStaticEvaluation(problemId);
    assert.deepEqual(evaluation.cards.map((card) => card.label), [
      "Scientific Demand Score",
      "Expected Attributable Net Social Value (EANSV)",
      "Autoresearch Fit",
    ]);
    const eansv = evaluation.cards[1].formula.join("\n");
    assert.match(eansv, /P\(useful outcome with this research\) - P\(useful outcome without this research\)/);
    assert.match(eansv, /expected information value - expected research cost/);
  }
});

test("does not invent an evaluation for a non-showcase problem", () => {
  assert.equal(getStaticEvaluation("Prob-017"), null);
  assert.equal(getStaticEvaluationPoints("Prob-017"), null);
});
