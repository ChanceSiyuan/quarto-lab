import assert from "node:assert/strict";
import test from "node:test";

import {
  calculateCapturableEnpv,
  calculateExpectedAttributableNetSocialValue,
  calculateInformationValue,
  calculateSocialEnpv,
  calculateStageTree,
  rankOneWaySensitivity,
} from "../../src/lib/valuations/formulas.mjs";

const fixed = (value) => ({ low: value, base: value, high: value });

const approvedEansvModel = {
  socialDiscountRate: 0.035,
  outcomes: [
    {
      id: "full-success",
      probability: 0.35,
      valueModel: {
        kind: "annual-per-run",
        teams: 30,
        runsPerTeamPerYear: 1000,
        years: [1, 2, 3, 4, 5],
        compute: { pricePerInstanceHour: 0.403216, instanceHoursAvoided: 0.5 },
        productiveTime: { hoursReleased: 0.5, loadedHourlyValue: 100, recaptureRate: 0.2 },
      },
    },
    {
      id: "partial-success",
      probability: 0.25,
      valueModel: {
        kind: "annual-per-run",
        teams: 10,
        runsPerTeamPerYear: 500,
        years: [1, 2, 3],
        compute: { pricePerInstanceHour: 0.403216, instanceHoursAvoided: 0.25 },
        productiveTime: { hoursReleased: 0.25, loadedHourlyValue: 100, recaptureRate: 0.2 },
      },
    },
    {
      id: "useful-negative-result",
      probability: 0.4,
      valueModel: { kind: "present-value", amount: 75000 },
    },
  ],
  withoutResearchCounterfactualPresentValue: 100000,
  researchCostPresentValue: 250000,
};

test("calculates the approved Prob-000 branch values and net EANSV", () => {
  const result = calculateExpectedAttributableNetSocialValue(approvedEansvModel);

  assert.equal(result.outcomes[0].computeSavingPerRun, 0.2);
  assert.equal(result.outcomes[0].productiveTimeValuePerRun, 10);
  assert.equal(result.outcomes[0].perRunBenefit, 10.2);
  assert.equal(result.outcomes[0].annualBenefit, 306000);
  assert.ok(Math.abs(result.outcomes[0].presentValue - 1381606.026894049) < 1e-7);
  assert.ok(Math.abs(result.outcomes[1].presentValue - 71441.74301329814) < 1e-7);
  assert.equal(result.outcomes[2].presentValue, 75000);
  assert.ok(Math.abs(result.withResearchPresentValue - 531422.5451662417) < 1e-7);
  assert.equal(result.withoutResearchCounterfactualPresentValue, 100000);
  assert.equal(result.researchCostPresentValue, 250000);
  assert.ok(Math.abs(result.eansv - 181422.5451662417) < 1e-7);
});

test("keeps a negative EANSV instead of clamping it to zero", () => {
  const result = calculateExpectedAttributableNetSocialValue({
    socialDiscountRate: 0,
    outcomes: [
      { id: "no-benefit", probability: 1, valueModel: { kind: "present-value", amount: 0 } },
    ],
    withoutResearchCounterfactualPresentValue: 10,
    researchCostPresentValue: 20,
  });

  assert.equal(result.eansv, -30);
});

test("rejects invalid EANSV models before doing arithmetic", () => {
  const invalidCases = [
    ["outcome probability", (model) => { model.outcomes[0].probability = -0.1; }, /probability/],
    ["probability total", (model) => { model.outcomes[0].probability = 0.2; }, /sum to one/],
    ["discount rate", (model) => { model.socialDiscountRate = -1; }, /socialDiscountRate/],
    ["present-value amount", (model) => { model.outcomes[2].valueModel.amount = -1; }, /amount/],
    ["annual team count", (model) => { model.outcomes[0].valueModel.teams = -1; }, /teams/],
    ["duplicate years", (model) => { model.outcomes[0].valueModel.years = [1, 1]; }, /years/],
    ["non-positive year", (model) => { model.outcomes[0].valueModel.years = [0]; }, /years/],
    ["duplicate outcome ID", (model) => { model.outcomes[1].id = "full-success"; }, /outcome id/],
    ["unsupported value model", (model) => { model.outcomes[0].valueModel.kind = "market-share"; }, /kind/],
  ];

  for (const [name, mutate, expectedMessage] of invalidCases) {
    const model = structuredClone(approvedEansvModel);
    mutate(model);
    assert.throws(
      () => calculateExpectedAttributableNetSocialValue(model),
      expectedMessage,
      `${name} must be rejected`,
    );
  }
});

test("charges stage costs even when the final path fails", () => {
  const result = calculateStageTree([
    { id: "theory", success: fixed(0.5), cost: fixed(100), year: 0 },
    { id: "validation", success: fixed(0.5), cost: fixed(80), year: 1 },
  ]);
  assert.deepEqual(result.success, fixed(0.25));
  assert.equal(result.expectedCost.base, 140);
});

test("discounts social benefits and costs separately by their year", () => {
  const result = calculateSocialEnpv({
    discountRate: fixed(0.1),
    yearlyBenefits: [{ year: 1, value: fixed(220) }],
    yearlyCosts: [{ year: 0, value: fixed(100) }, { year: 1, value: fixed(22) }],
  });
  assert.deepEqual(result, fixed(80));
});

test("calculates a separate capturable ENPV track", () => {
  const result = calculateCapturableEnpv({
    discountRate: fixed(0.1),
    yearlyBenefits: [{ year: 2, value: fixed(121) }],
    yearlyCosts: [{ year: 0, value: fixed(10) }],
  });
  assert.deepEqual(result, fixed(90));
});

test("computes information value separately from deployment value", () => {
  assert.deepEqual(calculateInformationValue({
    valueWithSampleInformation: { low: 90, base: 120, high: 150 },
    valueCurrentInformation: { low: 70, base: 80, high: 90 },
    studyCost: { low: 10, base: 15, high: 20 },
  }), {
    evsi: { low: 0, base: 40, high: 80 },
    enbs: { low: -20, base: 25, high: 70 },
  });
});

test("ranks one-way sensitivity by swing and then stable input ID", () => {
  const result = rankOneWaySensitivity({
    model: { inputs: [{ id: "zeta", interval: { low: 1, base: 2, high: 4 } }, { id: "alpha", interval: { low: 1, base: 2, high: 4 } }] },
    calculate: (model) => ({ score: model.inputs.reduce((sum, input) => sum + input.interval.base, 0) }),
    decisionMetric: "score",
  });
  assert.deepEqual(result, [
    { id: "alpha", low: 3, base: 4, high: 6, swing: 3 },
    { id: "zeta", low: 3, base: 4, high: 6, swing: 3 },
  ]);
});
