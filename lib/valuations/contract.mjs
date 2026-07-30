import {
  EVIDENCE_STATES,
  EVIDENCE_TIERS,
  SUPPORTED_CURRENCIES,
  VALUE_STATES,
  VISIBILITIES,
} from "./types.mjs";

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function nonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function hasOnlyFields(value, fields) {
  return isRecord(value) && Object.keys(value).every((key) => fields.includes(key));
}

function intervalIsOrdered(interval) {
  return isRecord(interval)
    && Number.isFinite(interval.low)
    && Number.isFinite(interval.base)
    && Number.isFinite(interval.high)
    && interval.low <= interval.base
    && interval.base <= interval.high;
}

function monetaryUnit(unit) {
  const match = typeof unit === "string" && /^([A-Z]{3})_(\d{4})$/.exec(unit);
  return match && SUPPORTED_CURRENCIES.includes(match[1]) ? match[1] : null;
}

function validUnit(unit) {
  return nonEmptyString(unit) && (monetaryUnit(unit) !== null || [
    "fraction", "percent", "score-100", "count", "hours", "years", "qubits", "logical-qubits", "physical-qubits", "operations",
  ].includes(unit));
}

function validateSources(sources, errors) {
  if (!Array.isArray(sources)) {
    errors.push("sources must be an array.");
    return new Set();
  }
  const ids = new Set();
  for (const source of sources) {
    if (!hasOnlyFields(source, ["id", "url", "locator", "kind"])
      || !nonEmptyString(source.id)
      || !nonEmptyString(source.url)
      || !nonEmptyString(source.locator)
      || !nonEmptyString(source.kind)
      || ids.has(source.id)) {
      errors.push("sources must have unique IDs, URLs, kinds, and locators.");
      continue;
    }
    ids.add(source.id);
  }
  return ids;
}

function isCaptureShare(value) {
  return value.kind === "capture-share" || /capture[-_ ]?share/i.test(value.id);
}

export function validateAtomicEvidence(value) {
  const errors = [];
  if (!isRecord(value) || !VALUE_STATES.includes(value.state)) {
    return { ok: false, errors: ["value state is invalid."] };
  }
  if (value.state === "unknown") {
    if (!hasOnlyFields(value, ["id", "state", "reason"])
      || !nonEmptyString(value.reason)
      || (Object.hasOwn(value, "id") && !nonEmptyString(value.id))) errors.push("unknown values require a reason and optional ID only.");
    return errors.length === 0 ? { ok: true, value } : { ok: false, errors };
  }

  const allowed = ["id", "state", "interval", "unit", "visibility", "evidenceState", "evidenceTier", "sourceIds", "sources", "currency", "priceBaseYear", "conversionSourceId", "derivation", "kind", "estimateKind"];
  if (!hasOnlyFields(value, allowed)) errors.push("known evidence contains unsupported fields.");
  if (!nonEmptyString(value.id)) errors.push("known evidence requires an ID.");
  if (!intervalIsOrdered(value.interval)) errors.push("known evidence interval must be finite and ordered.");
  if (!validUnit(value.unit)) errors.push("unit is unsupported.");
  if (!VISIBILITIES.includes(value.visibility)) errors.push("visibility is invalid.");
  if (!EVIDENCE_STATES.includes(value.evidenceState)) errors.push("evidence state is invalid.");
  if (!EVIDENCE_TIERS.includes(value.evidenceTier)) errors.push("evidence tier is invalid.");
  if (!Array.isArray(value.sourceIds) || !value.sourceIds.every(nonEmptyString) || new Set(value.sourceIds).size !== value.sourceIds.length) errors.push("source IDs must be unique non-empty strings.");
  if (Object.hasOwn(value, "estimateKind") && value.estimateKind !== "scientific-demand-model") errors.push("estimate kind is unsupported.");

  if (!Array.isArray(value.sources)) errors.push("known evidence requires sources with locators.");
  const sourceIds = Array.isArray(value.sources) ? validateSources(value.sources, errors) : new Set();
  if (Array.isArray(value.sourceIds) && value.sourceIds.some((id) => !sourceIds.has(id))) errors.push("every source ID must resolve to a source with a locator.");

  if (value.evidenceState === "inferred") {
    const derivation = value.derivation;
    if (!isRecord(derivation)
      || !hasOnlyFields(derivation, ["formulaId", "inputIds"])
      || !nonEmptyString(derivation.formulaId)
      || !Array.isArray(derivation.inputIds)
      || derivation.inputIds.length === 0
      || !derivation.inputIds.every(nonEmptyString)
      || new Set(derivation.inputIds).size !== derivation.inputIds.length) errors.push("inferred evidence requires a formula ID and unique input IDs.");
  } else if (Object.hasOwn(value, "derivation")) {
    errors.push("reported evidence must not include a derivation.");
  }

  const currency = monetaryUnit(value.unit);
  if (currency !== null && (!SUPPORTED_CURRENCIES.includes(value.currency)
    || value.currency !== currency
    || !Number.isInteger(value.priceBaseYear)
    || value.priceBaseYear < 1900
    || !nonEmptyString(value.conversionSourceId)
    || !sourceIds.has(value.conversionSourceId))) errors.push("currency evidence requires currency, price base year, and conversion source.");
  if (currency === null && ["currency", "priceBaseYear", "conversionSourceId"].some((field) => Object.hasOwn(value, field))) errors.push("non-currency evidence must not include currency metadata.");

  if (isCaptureShare(value) && !Array.isArray(value.sources)) {
    errors.push("known capture-share evidence requires cited sources.");
  } else if (isCaptureShare(value) && !value.sources.some((source) => ["licensing", "contract", "usage-price", "product-margin", "business-model"].includes(source.kind))) {
    errors.push("known capture-share evidence requires a plausible capture-mechanism source.");
  }
  return errors.length === 0 ? { ok: true, value } : { ok: false, errors };
}

function registerIds(items, type, typeIds, allIds, errors) {
  if (!Array.isArray(items)) return;
  for (const item of items) {
    if (!isRecord(item) || !nonEmptyString(item.id) || allIds.has(item.id)) {
      errors.push(`${type} must have unique IDs.`);
      continue;
    }
    typeIds.add(item.id);
    allIds.add(item.id);
  }
}

function validateReferences(items, type, inputIds, sourceIds, entityIds, errors) {
  if (!Array.isArray(items)) {
    errors.push(`${type} must be an array.`);
    return;
  }
  for (const item of items) {
    if (!isRecord(item) || !nonEmptyString(item.id)) continue;
    if (!Array.isArray(item.inputIds) || item.inputIds.some((inputId) => !inputIds.has(inputId))) errors.push(`${type} has an unknown input reference.`);
    for (const sourceId of item.sourceIds || []) if (!sourceIds.has(sourceId)) errors.push(`${type} has an unknown source reference.`);
    for (const stageId of item.stageIds || []) if (!entityIds.stages.has(stageId)) errors.push(`${type} has an unknown stage reference.`);
    for (const outputId of item.outputIds || []) if (!entityIds.outputs.has(outputId)) errors.push(`${type} has an unknown output reference.`);
    for (const assumptionId of item.assumptionIds || []) if (!entityIds.assumptions.has(assumptionId)) errors.push(`${type} has an unknown assumption reference.`);
  }
}

export function validateQuantitativeEvidence(value) {
  const errors = [];
  if (!hasOnlyFields(value, ["sources", "inputs", "stages", "outputs", "assumptions", "scoreAnchors"])) return { ok: false, errors: ["quantitative evidence contains unsupported fields."] };
  const sourceIds = validateSources(value.sources, errors);
  const allIds = new Set(sourceIds);
  const inputIds = new Set();
  if (!Array.isArray(value.inputs)) errors.push("inputs must be an array.");
  else for (const input of value.inputs) {
    const atomic = validateAtomicEvidence(input);
    if (!atomic.ok || !nonEmptyString(input?.id) || allIds.has(input.id)) errors.push("inputs must contain valid atomic evidence with unique IDs.");
    else { inputIds.add(input.id); allIds.add(input.id); }
    for (const sourceId of input?.sourceIds || []) if (!sourceIds.has(sourceId)) errors.push("inputs have an unknown source reference.");
  }
  for (const input of value.inputs || []) {
    for (const inputId of input?.derivation?.inputIds || []) if (!inputIds.has(inputId)) errors.push("inputs have an unknown derivation input reference.");
  }
  const ids = { inputs: inputIds, stages: new Set(), outputs: new Set(), assumptions: new Set(), scoreAnchors: new Set() };
  registerIds(value.stages, "stages", ids.stages, allIds, errors);
  registerIds(value.outputs, "outputs", ids.outputs, allIds, errors);
  registerIds(value.assumptions, "assumptions", ids.assumptions, allIds, errors);
  registerIds(value.scoreAnchors, "scoreAnchors", ids.scoreAnchors, allIds, errors);
  validateReferences(value.stages, "stages", inputIds, sourceIds, ids, errors);
  validateReferences(value.outputs, "outputs", inputIds, sourceIds, ids, errors);
  validateReferences(value.assumptions, "assumptions", inputIds, sourceIds, ids, errors);
  if (!Array.isArray(value.scoreAnchors)) errors.push("scoreAnchors must be an array.");
  else for (const anchor of value.scoreAnchors) {
    if (!isRecord(anchor) || !nonEmptyString(anchor.id)) continue;
    if (!Array.isArray(anchor.outputIds) || anchor.outputIds.some((id) => !ids.outputs.has(id))) errors.push("scoreAnchors have an unknown output reference.");
    for (const sourceId of anchor.sourceIds || []) if (!sourceIds.has(sourceId)) errors.push("scoreAnchors have an unknown source reference.");
  }
  return errors.length === 0 ? { ok: true, value } : { ok: false, errors };
}
