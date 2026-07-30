function isInterval(value) {
  return value !== null && typeof value === "object"
    && Number.isFinite(value.low)
    && Number.isFinite(value.base)
    && Number.isFinite(value.high);
}

function interval(low, base, high) {
  const clean = (value) => Math.round(value * 1e12) / 1e12;
  return { low: clean(low), base: clean(base), high: clean(high) };
}

function assertInterval(value, name) {
  if (!isInterval(value) || value.low > value.base || value.base > value.high) throw new TypeError(`${name} must be an ordered finite interval.`);
}

export function addIntervals(left, right) {
  assertInterval(left, "left interval");
  assertInterval(right, "right interval");
  return interval(left.low + right.low, left.base + right.base, left.high + right.high);
}

export function subtractIntervals(left, right) {
  assertInterval(left, "left interval");
  assertInterval(right, "right interval");
  return interval(left.low - right.high, left.base - right.base, left.high - right.low);
}

export function multiplyIntervals(left, right) {
  assertInterval(left, "left interval");
  assertInterval(right, "right interval");
  const products = [left.low * right.low, left.low * right.high, left.high * right.low, left.high * right.high];
  return interval(Math.min(...products), left.base * right.base, Math.max(...products));
}

export function clampIntervalFloor(interval, floor) {
  assertInterval(interval, "interval");
  if (!Number.isFinite(floor)) throw new TypeError("floor must be finite.");
  return { low: Math.max(interval.low, floor), base: Math.max(interval.base, floor), high: Math.max(interval.high, floor) };
}

function divideByPositiveInterval(numerator, denominator) {
  assertInterval(numerator, "numerator interval");
  assertInterval(denominator, "denominator interval");
  if (denominator.low <= 0) throw new RangeError("discount denominator must be positive.");
  const quotients = [numerator.low / denominator.low, numerator.low / denominator.high, numerator.high / denominator.low, numerator.high / denominator.high];
  return interval(Math.min(...quotients), numerator.base / denominator.base, Math.max(...quotients));
}

function discount(interval, rate, year) {
  assertInterval(interval, "yearly value");
  assertInterval(rate, "discount rate");
  if (!Number.isInteger(year) || year < 0 || rate.low <= -1) throw new RangeError("year and discount rate are invalid.");
  return divideByPositiveInterval(interval, {
    low: (1 + rate.low) ** year,
    base: (1 + rate.base) ** year,
    high: (1 + rate.high) ** year,
  });
}

export function calculateStageTree(stages) {
  if (!Array.isArray(stages)) throw new TypeError("stages must be an array.");
  let reach = { low: 1, base: 1, high: 1 };
  let expectedCost = { low: 0, base: 0, high: 0 };
  for (const stage of stages) {
    if (stage === null || typeof stage !== "object") throw new TypeError("stage must be an object.");
    assertInterval(stage.success, "stage success");
    assertInterval(stage.cost, "stage cost");
    expectedCost = addIntervals(expectedCost, multiplyIntervals(reach, stage.cost));
    reach = multiplyIntervals(reach, stage.success);
  }
  return { success: reach, expectedCost };
}

function calculateEnpv(model, rateKeys) {
  if (model === null || typeof model !== "object") throw new TypeError("model must be an object.");
  const rate = rateKeys.map((key) => model[key]).find((value) => value !== undefined);
  assertInterval(rate, "discount rate");
  const benefits = model.yearlyBenefits ?? model.benefits;
  const costs = model.yearlyCosts ?? model.costs;
  if (!Array.isArray(benefits) || !Array.isArray(costs)) throw new TypeError("yearly benefits and costs must be arrays.");
  const total = (items, fields) => items.reduce((sum, item) => {
    const value = fields.map((field) => item?.[field]).find((candidate) => candidate !== undefined);
    return addIntervals(sum, discount(value, rate, item?.year));
  }, { low: 0, base: 0, high: 0 });
  return subtractIntervals(total(benefits, ["value", "expectedBenefit", "benefit"]), total(costs, ["value", "expectedCost", "cost"]));
}

export function calculateSocialEnpv(model) {
  return calculateEnpv(model, ["discountRate", "socialDiscountRate"]);
}

export function calculateCapturableEnpv(model) {
  return calculateEnpv(model, ["discountRate", "privateDiscountRate", "capturableDiscountRate"]);
}

export function calculateInformationValue({ valueWithSampleInformation, valueCurrentInformation, studyCost }) {
  const evsi = clampIntervalFloor(subtractIntervals(valueWithSampleInformation, valueCurrentInformation), 0);
  return { evsi, enbs: subtractIntervals(evsi, studyCost) };
}

function assertPlainObject(value, name) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`${name} must be an object.`);
  }
}

function assertNonNegativeFinite(value, name) {
  if (!Number.isFinite(value) || value < 0) {
    throw new TypeError(`${name} must be a non-negative finite number.`);
  }
}

function assertPositiveInteger(value, name) {
  if (!Number.isInteger(value) || value <= 0) {
    throw new TypeError(`${name} must be a positive integer.`);
  }
}

function validateAnnualPerRunModel(valueModel, outcomeLabel) {
  assertPositiveInteger(valueModel.teams, `${outcomeLabel} teams`);
  assertPositiveInteger(valueModel.runsPerTeamPerYear, `${outcomeLabel} runsPerTeamPerYear`);
  if (!Array.isArray(valueModel.years) || valueModel.years.length === 0) {
    throw new TypeError(`${outcomeLabel} years must be a non-empty array.`);
  }
  const years = new Set();
  for (const year of valueModel.years) {
    assertPositiveInteger(year, `${outcomeLabel} years`);
    if (years.has(year)) {
      throw new TypeError(`${outcomeLabel} years must be unique.`);
    }
    years.add(year);
  }

  assertPlainObject(valueModel.compute, `${outcomeLabel} compute`);
  assertNonNegativeFinite(
    valueModel.compute.pricePerInstanceHour,
    `${outcomeLabel} compute pricePerInstanceHour`,
  );
  assertNonNegativeFinite(
    valueModel.compute.instanceHoursAvoided,
    `${outcomeLabel} compute instanceHoursAvoided`,
  );

  assertPlainObject(valueModel.productiveTime, `${outcomeLabel} productiveTime`);
  assertNonNegativeFinite(
    valueModel.productiveTime.hoursReleased,
    `${outcomeLabel} productiveTime hoursReleased`,
  );
  assertNonNegativeFinite(
    valueModel.productiveTime.loadedHourlyValue,
    `${outcomeLabel} productiveTime loadedHourlyValue`,
  );
  assertNonNegativeFinite(
    valueModel.productiveTime.recaptureRate,
    `${outcomeLabel} productiveTime recaptureRate`,
  );
  if (valueModel.productiveTime.recaptureRate > 1) {
    throw new RangeError(`${outcomeLabel} productiveTime recaptureRate must not exceed one.`);
  }
}

function validateEansvModel(model) {
  assertPlainObject(model, "EANSV model");
  if (!Number.isFinite(model.socialDiscountRate) || model.socialDiscountRate <= -1) {
    throw new RangeError("EANSV model socialDiscountRate must be finite and greater than -1.");
  }
  assertNonNegativeFinite(
    model.withoutResearchCounterfactualPresentValue,
    "EANSV model withoutResearchCounterfactualPresentValue",
  );
  assertNonNegativeFinite(model.researchCostPresentValue, "EANSV model researchCostPresentValue");
  if (!Array.isArray(model.outcomes) || model.outcomes.length === 0) {
    throw new TypeError("EANSV model outcomes must be a non-empty array.");
  }

  const outcomeIds = new Set();
  let probabilityTotal = 0;
  for (const [index, outcome] of model.outcomes.entries()) {
    const outcomeLabel = `EANSV outcome ${index + 1}`;
    assertPlainObject(outcome, outcomeLabel);
    if (typeof outcome.id !== "string" || outcome.id.trim().length === 0 || outcomeIds.has(outcome.id)) {
      throw new TypeError(`${outcomeLabel} outcome id must be a unique non-empty string.`);
    }
    outcomeIds.add(outcome.id);
    if (!Number.isFinite(outcome.probability)
      || outcome.probability < 0
      || outcome.probability > 1) {
      throw new RangeError(`${outcomeLabel} probability must be between zero and one.`);
    }
    probabilityTotal += outcome.probability;

    assertPlainObject(outcome.valueModel, `${outcomeLabel} valueModel`);
    if (outcome.valueModel.kind === "annual-per-run") {
      validateAnnualPerRunModel(outcome.valueModel, outcomeLabel);
    } else if (outcome.valueModel.kind === "present-value") {
      assertNonNegativeFinite(outcome.valueModel.amount, `${outcomeLabel} amount`);
    } else {
      throw new TypeError(`${outcomeLabel} valueModel kind is unsupported.`);
    }
  }
  if (Math.abs(probabilityTotal - 1) > 1e-12) {
    throw new RangeError("EANSV model outcome probabilities must sum to one.");
  }
}

function roundToCents(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function calculateEansvOutcome(outcome, socialDiscountRate) {
  if (outcome.valueModel.kind === "present-value") {
    const presentValue = outcome.valueModel.amount;
    return {
      id: outcome.id,
      probability: outcome.probability,
      kind: outcome.valueModel.kind,
      presentValue,
      expectedPresentValue: outcome.probability * presentValue,
    };
  }

  const computeSavingPerRun = roundToCents(
    outcome.valueModel.compute.pricePerInstanceHour
      * outcome.valueModel.compute.instanceHoursAvoided,
  );
  const productiveTimeValuePerRun = roundToCents(
    outcome.valueModel.productiveTime.hoursReleased
      * outcome.valueModel.productiveTime.loadedHourlyValue
      * outcome.valueModel.productiveTime.recaptureRate,
  );
  const perRunBenefit = computeSavingPerRun + productiveTimeValuePerRun;
  const annualBenefit = outcome.valueModel.teams
    * outcome.valueModel.runsPerTeamPerYear
    * perRunBenefit;
  const presentValue = outcome.valueModel.years.reduce(
    (sum, year) => sum + annualBenefit / ((1 + socialDiscountRate) ** year),
    0,
  );
  return {
    id: outcome.id,
    probability: outcome.probability,
    kind: outcome.valueModel.kind,
    computeSavingPerRun,
    productiveTimeValuePerRun,
    perRunBenefit,
    annualBenefit,
    presentValue,
    expectedPresentValue: outcome.probability * presentValue,
  };
}

export function calculateExpectedAttributableNetSocialValue(model) {
  validateEansvModel(model);
  const outcomes = model.outcomes.map(
    (outcome) => calculateEansvOutcome(outcome, model.socialDiscountRate),
  );
  const withResearchPresentValue = outcomes.reduce(
    (sum, outcome) => sum + outcome.expectedPresentValue,
    0,
  );
  return {
    outcomes,
    withResearchPresentValue,
    withoutResearchCounterfactualPresentValue: model.withoutResearchCounterfactualPresentValue,
    researchCostPresentValue: model.researchCostPresentValue,
    eansv: withResearchPresentValue
      - model.withoutResearchCounterfactualPresentValue
      - model.researchCostPresentValue,
  };
}

function metricValue(result, metric) {
  const value = result?.[metric];
  if (Number.isFinite(value)) return value;
  if (isInterval(value)) return value.base;
  throw new TypeError(`decision metric ${metric} must be a number or interval.`);
}

function clone(value) {
  return structuredClone(value);
}

export function rankOneWaySensitivity({ model, calculate, decisionMetric }) {
  if (!model || !Array.isArray(model.inputs) || typeof calculate !== "function" || typeof decisionMetric !== "string") throw new TypeError("sensitivity model, inputs, calculate, and decision metric are required.");
  const rows = model.inputs.map((input, index) => {
    if (!input || typeof input.id !== "string") throw new TypeError("each sensitivity input requires an ID.");
    assertInterval(input.interval, `input ${input.id}`);
    const evaluate = (base) => {
      const scenario = clone(model);
      scenario.inputs[index].interval.base = base;
      return metricValue(calculate(scenario), decisionMetric);
    };
    const low = evaluate(input.interval.low);
    const base = evaluate(input.interval.base);
    const high = evaluate(input.interval.high);
    return { id: input.id, low, base, high, swing: Math.abs(high - low) };
  });
  return rows.sort((left, right) => right.swing - left.swing || left.id.localeCompare(right.id));
}
