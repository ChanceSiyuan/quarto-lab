import assert from "node:assert/strict";
import test from "node:test";

import {
  calculateCapturableEnpv,
  calculateInformationValue,
  calculateSocialEnpv,
  calculateStageTree,
  rankOneWaySensitivity,
} from "../../src/lib/valuations/formulas.mjs";

const fixed = (value) => ({ low: value, base: value, high: value });

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
