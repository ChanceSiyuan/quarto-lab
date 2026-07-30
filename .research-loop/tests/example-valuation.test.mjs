import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  getStaticExampleValuation,
  validateStaticExampleValuationFixture,
} from "../../src/lib/problems/example-valuation.mjs";
import {
  buildStaticExampleEansvCard,
} from "../../src/lib/problems/example-valuation-presentation.mjs";

const rawFixture = JSON.parse(await readFile(
  new URL("../fixtures/showcase/problems/Prob-000/valuation.json", import.meta.url),
  "utf8",
));

test("Prob-000 fixture resolves evidence and assumptions into the approved model", () => {
  const example = getStaticExampleValuation("Prob-000");

  assert.equal(example.metadata.metricId, "prob-000-eansv-v1");
  assert.equal(example.metadata.currency, "USD");
  assert.equal(example.metadata.constantDollarYear, 2026);
  assert.equal(example.model.socialDiscountRate, 0.035);
  assert.deepEqual(example.model.outcomes.map(({ id, probability }) => ({ id, probability })), [
    { id: "full-success", probability: 0.35 },
    { id: "partial-success", probability: 0.25 },
    { id: "useful-negative-result", probability: 0.4 },
  ]);
  assert.equal(example.model.outcomes[0].valueModel.compute.pricePerInstanceHour, 0.403216);
  assert.equal(example.model.withoutResearchCounterfactualPresentValue, 100000);
  assert.equal(example.model.researchCostPresentValue, 250000);
  assert.equal(getStaticExampleValuation("Prob-999"), null);

  example.model.outcomes[0].probability = 0;
  assert.equal(getStaticExampleValuation("Prob-000").model.outcomes[0].probability, 0.35);
});

test("Prob-000 card derives one rounded headline from fixture inputs", () => {
  const card = buildStaticExampleEansvCard(getStaticExampleValuation("Prob-000"));

  assert.equal(card.label, "Expected Attributable Net Social Value");
  assert.equal(card.value, "+$180K USD 2026");
  assert.match(card.formula.join("\n"), /With-research expected PV = \$531,422\.55/);
  assert.match(card.formula.join("\n"), /EANSV = \$181,422\.55/);
  assert.match(card.reason, /scenario assumptions/i);
  assert.match(card.reason, /external price anchor/i);
});

test("valuation fixture validation rejects broken provenance and stored answers", () => {
  const invalidCases = [
    ["schema version", (fixture) => { fixture.schemaVersion = 2; }, /schemaVersion/],
    ["problem ID", (fixture) => { fixture.problemId = "Prob-999"; }, /problemId/],
    ["metric ID", (fixture) => { fixture.metric.id = "market-share-v1"; }, /metric id/],
    ["duplicate evidence", (fixture) => { fixture.evidence[1].id = fixture.evidence[0].id; }, /evidence id/],
    ["duplicate assumption", (fixture) => { fixture.assumptions[1].id = fixture.assumptions[0].id; }, /assumption id/],
    ["missing assumption reference", (fixture) => { fixture.model.socialDiscountRateAssumptionId = "missing"; }, /assumption reference/],
    ["wrong assumption reference type", (fixture) => { fixture.model.socialDiscountRateAssumptionId = fixture.evidence[0].id; }, /assumption reference/],
    ["wrong evidence reference type", (fixture) => { fixture.model.outcomes[0].valueModel.compute.priceEvidenceId = fixture.assumptions[0].id; }, /evidence reference/],
    ["non-price evidence", (fixture) => { fixture.model.outcomes[0].valueModel.compute.priceEvidenceId = "qdis-rnd-joss-2022"; }, /external-price/],
    ["source URL", (fixture) => { fixture.evidence[0].url = "not-a-url"; }, /url/],
    ["source date", (fixture) => { fixture.evidence[0].accessedAt = "30 July"; }, /accessedAt/],
    ["stored EANSV", (fixture) => { fixture.eansv = 181422.55; }, /unsupported field eansv/],
    ["stored headline", (fixture) => { fixture.headline = "+$180K"; }, /unsupported field headline/],
  ];

  for (const [name, mutate, expectedMessage] of invalidCases) {
    const fixture = structuredClone(rawFixture);
    mutate(fixture);
    assert.throws(
      () => validateStaticExampleValuationFixture(fixture),
      expectedMessage,
      `${name} must be rejected`,
    );
  }
});
