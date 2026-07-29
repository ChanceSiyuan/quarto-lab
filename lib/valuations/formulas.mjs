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
