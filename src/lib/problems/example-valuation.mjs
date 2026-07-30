import rawFixture from "../../../.research-loop/fixtures/showcase/problems/Prob-000/valuation.json" with { type: "json" };
import { calculateExpectedAttributableNetSocialValue } from "../valuations/formulas.mjs";

const PROBLEM_ID = "Prob-000";
const METRIC_ID = "prob-000-eansv-v1";
const TOP_LEVEL_FIELDS = new Set([
  "schemaVersion",
  "kind",
  "problemId",
  "metric",
  "evidence",
  "assumptions",
  "model",
]);
const STORED_ANSWER_FIELDS = new Set(["eansv", "headline", "displayValue", "finalValue"]);

function fail(message) {
  throw new Error(`Static example valuation ${message}.`);
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireObject(value, field) {
  if (!isPlainObject(value)) fail(`${field} must be an object`);
}

function requireString(value, field) {
  if (typeof value !== "string" || value.trim().length === 0) fail(`${field} must be a non-empty string`);
}

function rejectStoredAnswers(value) {
  if (Array.isArray(value)) {
    value.forEach(rejectStoredAnswers);
    return;
  }
  if (!isPlainObject(value)) return;
  for (const [key, child] of Object.entries(value)) {
    if (STORED_ANSWER_FIELDS.has(key)) fail(`has unsupported field ${key}`);
    rejectStoredAnswers(child);
  }
}

function validateSourceUrl(value, field) {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:") fail(`${field} url must use HTTPS`);
  } catch (error) {
    if (String(error.message).startsWith("Static example valuation")) throw error;
    fail(`${field} url is invalid`);
  }
}

function validateDate(value, field) {
  if (typeof value !== "string"
    || !/^\d{4}-\d{2}-\d{2}$/.test(value)
    || !Number.isFinite(Date.parse(`${value}T00:00:00Z`))) {
    fail(`${field} accessedAt is invalid`);
  }
}

function validateEvidence(records) {
  if (!Array.isArray(records) || records.length === 0) fail("evidence must be a non-empty array");
  const byId = new Map();
  for (const [index, record] of records.entries()) {
    const field = `evidence ${index + 1}`;
    requireObject(record, field);
    requireString(record.id, `${field} id`);
    if (byId.has(record.id)) fail(`${field} evidence id is duplicated`);
    requireString(record.title, `${field} title`);
    requireString(record.supports, `${field} supports`);
    validateSourceUrl(record.url, field);
    validateDate(record.accessedAt, field);
    if (!new Set(["technical-context", "external-price"]).has(record.kind)) {
      fail(`${field} kind is invalid`);
    }
    if (record.kind === "external-price") {
      if (!Number.isFinite(record.numericValue) || record.numericValue < 0) {
        fail(`${field} numericValue must be non-negative and finite`);
      }
      requireString(record.unit, `${field} unit`);
    }
    byId.set(record.id, record);
  }
  return byId;
}

function validateAssumptions(records) {
  if (!Array.isArray(records) || records.length === 0) fail("assumptions must be a non-empty array");
  const byId = new Map();
  for (const [index, record] of records.entries()) {
    const field = `assumption ${index + 1}`;
    requireObject(record, field);
    requireString(record.id, `${field} id`);
    if (byId.has(record.id)) fail(`${field} assumption id is duplicated`);
    requireString(record.label, `${field} label`);
    requireString(record.unit, `${field} unit`);
    requireString(record.rationale, `${field} rationale`);
    const validValue = Number.isFinite(record.value)
      || (Array.isArray(record.value)
        && record.value.length > 0
        && record.value.every(Number.isFinite));
    if (!validValue) fail(`${field} value must contain finite numbers`);
    byId.set(record.id, record);
  }
  return byId;
}

function resolveAssumption(assumptionsById, id, field) {
  const record = assumptionsById.get(id);
  if (!record) fail(`${field} assumption reference ${id ?? "<missing>"} is missing`);
  return structuredClone(record.value);
}

function resolveEvidence(evidenceById, id, field, expectedKind) {
  const record = evidenceById.get(id);
  if (!record) fail(`${field} evidence reference ${id ?? "<missing>"} is missing`);
  if (record.kind !== expectedKind) fail(`${field} evidence must have kind ${expectedKind}`);
  return record;
}

function resolveAnnualModel(valueModel, assumptionsById, evidenceById, field) {
  requireObject(valueModel.compute, `${field} compute`);
  requireObject(valueModel.productiveTime, `${field} productiveTime`);
  const priceEvidence = resolveEvidence(
    evidenceById,
    valueModel.compute.priceEvidenceId,
    `${field} compute priceEvidenceId`,
    "external-price",
  );
  return {
    kind: valueModel.kind,
    teams: resolveAssumption(assumptionsById, valueModel.teamsAssumptionId, `${field} teamsAssumptionId`),
    runsPerTeamPerYear: resolveAssumption(
      assumptionsById,
      valueModel.runsPerTeamPerYearAssumptionId,
      `${field} runsPerTeamPerYearAssumptionId`,
    ),
    years: resolveAssumption(assumptionsById, valueModel.yearsAssumptionId, `${field} yearsAssumptionId`),
    compute: {
      pricePerInstanceHour: priceEvidence.numericValue,
      instanceHoursAvoided: resolveAssumption(
        assumptionsById,
        valueModel.compute.instanceHoursAvoidedAssumptionId,
        `${field} compute instanceHoursAvoidedAssumptionId`,
      ),
    },
    productiveTime: {
      hoursReleased: resolveAssumption(
        assumptionsById,
        valueModel.productiveTime.hoursReleasedAssumptionId,
        `${field} productiveTime hoursReleasedAssumptionId`,
      ),
      loadedHourlyValue: resolveAssumption(
        assumptionsById,
        valueModel.productiveTime.loadedHourlyValueAssumptionId,
        `${field} productiveTime loadedHourlyValueAssumptionId`,
      ),
      recaptureRate: resolveAssumption(
        assumptionsById,
        valueModel.productiveTime.recaptureRateAssumptionId,
        `${field} productiveTime recaptureRateAssumptionId`,
      ),
    },
  };
}

function resolveFixture(fixture) {
  requireObject(fixture, "fixture");
  rejectStoredAnswers(fixture);
  for (const field of Object.keys(fixture)) {
    if (!TOP_LEVEL_FIELDS.has(field)) fail(`has unsupported field ${field}`);
  }
  if (fixture.schemaVersion !== 1) fail("schemaVersion must be 1");
  if (fixture.kind !== "static-eansv-example") fail("kind is invalid");
  if (fixture.problemId !== PROBLEM_ID) fail(`problemId must be ${PROBLEM_ID}`);

  requireObject(fixture.metric, "metric");
  if (fixture.metric.id !== METRIC_ID) fail(`metric id must be ${METRIC_ID}`);
  if (fixture.metric.label !== "Expected Attributable Net Social Value") fail("metric label is invalid");
  if (fixture.metric.currency !== "USD") fail("metric currency must be USD");
  if (fixture.metric.constantDollarYear !== 2026) fail("metric constantDollarYear must be 2026");

  const evidenceById = validateEvidence(fixture.evidence);
  const assumptionsById = validateAssumptions(fixture.assumptions);
  requireObject(fixture.model, "model");
  if (!Array.isArray(fixture.model.outcomes) || fixture.model.outcomes.length === 0) {
    fail("model outcomes must be a non-empty array");
  }
  const outcomes = fixture.model.outcomes.map((outcome, index) => {
    const field = `model outcome ${index + 1}`;
    requireObject(outcome, field);
    requireString(outcome.id, `${field} id`);
    if (!Array.isArray(outcome.technicalEvidenceIds) || outcome.technicalEvidenceIds.length === 0) {
      fail(`${field} technicalEvidenceIds must be a non-empty array`);
    }
    for (const evidenceId of outcome.technicalEvidenceIds) {
      resolveEvidence(evidenceById, evidenceId, `${field} technicalEvidenceIds`, "technical-context");
    }
    requireObject(outcome.valueModel, `${field} valueModel`);
    let valueModel;
    if (outcome.valueModel.kind === "annual-per-run") {
      valueModel = resolveAnnualModel(outcome.valueModel, assumptionsById, evidenceById, field);
    } else if (outcome.valueModel.kind === "present-value") {
      valueModel = {
        kind: outcome.valueModel.kind,
        amount: resolveAssumption(
          assumptionsById,
          outcome.valueModel.amountAssumptionId,
          `${field} amountAssumptionId`,
        ),
      };
    } else {
      fail(`${field} valueModel kind is unsupported`);
    }
    return {
      id: outcome.id,
      probability: resolveAssumption(
        assumptionsById,
        outcome.probabilityAssumptionId,
        `${field} probabilityAssumptionId`,
      ),
      valueModel,
    };
  });

  const resolved = {
    metadata: {
      metricId: fixture.metric.id,
      label: fixture.metric.label,
      currency: fixture.metric.currency,
      constantDollarYear: fixture.metric.constantDollarYear,
    },
    model: {
      socialDiscountRate: resolveAssumption(
        assumptionsById,
        fixture.model.socialDiscountRateAssumptionId,
        "model socialDiscountRateAssumptionId",
      ),
      outcomes,
      withoutResearchCounterfactualPresentValue: resolveAssumption(
        assumptionsById,
        fixture.model.withoutResearchCounterfactualAssumptionId,
        "model withoutResearchCounterfactualAssumptionId",
      ),
      researchCostPresentValue: resolveAssumption(
        assumptionsById,
        fixture.model.researchCostAssumptionId,
        "model researchCostAssumptionId",
      ),
    },
    evidence: structuredClone(fixture.evidence),
    assumptions: structuredClone(fixture.assumptions),
  };
  calculateExpectedAttributableNetSocialValue(resolved.model);
  return resolved;
}

export function validateStaticExampleValuationFixture(fixture) {
  resolveFixture(fixture);
}

const resolvedFixture = resolveFixture(rawFixture);

export function getStaticExampleValuation(problemId) {
  return problemId === PROBLEM_ID ? structuredClone(resolvedFixture) : null;
}
