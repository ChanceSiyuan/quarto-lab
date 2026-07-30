import {
  AUTORESEARCH_DIMENSIONS,
  CONFIDENCE_LEVELS,
  EVIDENCE_STATES,
  RECOMMENDATIONS,
  RESEARCH_VALUE_DIMENSIONS,
  VERDICT_LABELS,
  deriveVerdict,
  harmonicInterval,
  weightedInterval,
} from "./policy.mjs";
import { QUANTUM_AREAS, QUANTUM_DOMAIN } from "../problems/schema.mjs";
import { validateQuantitativeEvidence as validateValuationQuantitativeEvidence } from "../valuations/contract.mjs";
import { propagateVisibility } from "../valuations/privacy.mjs";
import { deriveAssessmentPointEstimates } from "./point-estimates.mjs";

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function intervalOk(interval, max) {
  return isRecord(interval)
    && Number.isFinite(interval.min)
    && Number.isFinite(interval.estimate)
    && Number.isFinite(interval.max)
    && interval.min >= 0
    && interval.estimate >= interval.min
    && interval.max >= interval.estimate
    && interval.max <= max;
}

function sameInterval(left, right) {
  return Math.abs(left.min - right.min) <= 0.01
    && Math.abs(left.estimate - right.estimate) <= 0.01
    && Math.abs(left.max - right.max) <= 0.01;
}

function hasOnlyFields(value, fields) {
  return isRecord(value) && Object.keys(value).every((key) => fields.includes(key));
}

function hasRequiredFields(value, fields) {
  return isRecord(value) && fields.every((field) => Object.hasOwn(value, field));
}

function nonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function isTrustedKnowledgePath(value) {
  return typeof value === "string"
    && value.startsWith("knowledge/")
    && value.endsWith(".qmd")
    && !value.includes("\\")
    && !value.split("/").includes("..");
}

function visibilityOk(value) {
  return value === "public" || value === "private";
}

function quantitativeValueOk(value) {
  return isRecord(value) && ["known", "unknown"].includes(value.state);
}

function emptyArray(value) {
  return Array.isArray(value) && value.length === 0;
}

function normalizeQuantitativeValue(value) {
  if (!isRecord(value)) return value;
  if (value.state === "unknown") {
    const placeholdersOk = (
      (value.id === null || value.id === undefined || nonEmptyString(value.id))
      && value.interval == null
      && value.unit == null
      && value.visibility == null
      && value.evidenceState == null
      && value.evidenceTier == null
      && emptyArray(value.sourceIds ?? [])
      && emptyArray(value.sources ?? [])
      && value.currency == null
      && value.priceBaseYear == null
      && value.conversionSourceId == null
      && value.derivation == null
      && value.kind == null
    );
    if (!placeholdersOk) return value;
    return {
      ...(nonEmptyString(value.id) ? { id: value.id } : {}),
      state: "unknown",
      reason: value.reason,
    };
  }

  const normalized = { ...value };
  if (normalized.reason === null) delete normalized.reason;
  for (const field of ["currency", "priceBaseYear", "conversionSourceId", "derivation", "kind"]) {
    if (normalized[field] === null) delete normalized[field];
  }
  return normalized;
}

function normalizeAssessmentEnvelope(value) {
  if (!isRecord(value) || !isRecord(value.assessment) || !isRecord(value.assessment.quantitativeEvidence)) return value;
  const envelope = structuredClone(value);
  const quantitative = envelope.assessment.quantitativeEvidence;
  if (isRecord(quantitative.scientificAttention)) {
    quantitative.scientificAttention.value = normalizeQuantitativeValue(quantitative.scientificAttention.value);
    quantitative.scientificAttention.momentum = normalizeQuantitativeValue(quantitative.scientificAttention.momentum);
    if (isRecord(quantitative.scientificAttention.components)) {
      quantitative.scientificAttention.components = Object.fromEntries(
        Object.entries(quantitative.scientificAttention.components).map(([key, component]) => [
          key,
          isRecord(component)
            ? Object.fromEntries(Object.entries(component).filter(([, fieldValue]) => fieldValue !== null))
            : component,
        ]),
      );
    }
  }
  for (const field of ["technicalFeasibility", "socialValue", "capturableValue", "informationValue"]) {
    quantitative[field] = normalizeQuantitativeValue(quantitative[field]);
  }
  if (Array.isArray(quantitative.scoreAnchors)) {
    quantitative.scoreAnchors = quantitative.scoreAnchors.map((anchor) => {
      if (!isRecord(anchor) || anchor.momentumAdjustment !== null) return anchor;
      const { momentumAdjustment: _momentumAdjustment, ...rest } = anchor;
      return rest;
    });
  }
  return envelope;
}

function isoTimestampOk(value) {
  return typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}

function snapshotOk(snapshot) {
  return hasOnlyFields(snapshot, ["snapshotId", "contentHash", "createdAt", "freshness", "visibility"])
    && typeof snapshot.snapshotId === "string"
    && /^\d{8}T\d{6}Z-[a-f0-9]{12}$/.test(snapshot.snapshotId)
    && typeof snapshot.contentHash === "string"
    && /^[a-f0-9]{64}$/.test(snapshot.contentHash)
    && typeof snapshot.createdAt === "string"
    && isoTimestampOk(snapshot.createdAt)
    && ["fresh", "stale"].includes(snapshot.freshness)
    && visibilityOk(snapshot.visibility);
}

function demandComponentOk(component) {
  if (!isRecord(component) || !["known", "unknown", "reserved"].includes(component.availability)) return false;
  const optionalNumeric = ["rawLogGrowth", "paperCount", "coverage", "paperBreadth", "institutionBreadth", "institutionCount"];
  if (optionalNumeric.some((field) => Object.hasOwn(component, field) && !Number.isFinite(component[field]))) return false;
  if (!Number.isFinite(component.weight) || component.weight < 0 || component.weight > 1) return false;
  if (component.availability === "reserved") {
    return hasOnlyFields(component, ["availability", "weight"]);
  }
  if (component.availability === "unknown") {
    return hasOnlyFields(component, ["availability", "reason", "weight", "unit"])
      && nonEmptyString(component.reason)
      && component.unit === "fraction";
  }
  return hasOnlyFields(component, ["availability", "value", "weight", "unit", ...optionalNumeric])
    && Number.isFinite(component.value)
    && component.value >= 0
    && component.value <= 1
    && component.unit === "fraction";
}

function scientificDemandAuditOk(attention) {
  const auditFields = ["formulaId", "components", "evidenceConfidence", "paperCount"];
  const present = auditFields.filter((field) => Object.hasOwn(attention, field));
  if (present.length === 0) return true;
  return present.length === auditFields.length
    && attention.formulaId === "qec-scientific-demand-v1"
    && ["low", "medium", "high"].includes(attention.evidenceConfidence)
    && Number.isInteger(attention.paperCount)
    && attention.paperCount >= 0
    && hasOnlyFields(attention.components, ["influence", "momentum", "breadth", "network"])
    && ["influence", "momentum", "breadth", "network"].every((field) => demandComponentOk(attention.components[field]));
}

const QUANTITATIVE_OUTPUT_TYPES = Object.freeze({
  "scientific-attention": "scientificAttention",
  momentum: "momentum",
  "technical-feasibility": "technicalFeasibility",
  "social-value": "socialValue",
  "capturable-value": "capturableValue",
  "information-value": "informationValue",
});

function quantitativeOutputTypes() {
  return new Map(Object.entries(QUANTITATIVE_OUTPUT_TYPES));
}

function metricValues(quantitative) {
  return [
    ["scientific-attention", quantitative.scientificAttention.value],
    ["momentum", quantitative.scientificAttention.momentum],
    ["technical-feasibility", quantitative.technicalFeasibility],
    ["social-value", quantitative.socialValue],
    ["capturable-value", quantitative.capturableValue],
    ["information-value", quantitative.informationValue],
  ];
}

function frozenDerivationProjection(values) {
  const projectedIds = new Map();
  for (const [, value] of values) {
    for (const inputId of value?.derivation?.inputIds ?? []) {
      if (nonEmptyString(inputId) && !projectedIds.has(inputId)) {
        projectedIds.set(inputId, `input-frozen-derivation-${projectedIds.size + 1}`);
      }
    }
  }
  return projectedIds;
}

function cloneAtomicInput(id, value, projectedDerivationIds) {
  const clone = { ...value, id: `input-${id}` };
  if (isRecord(value?.derivation) && Array.isArray(value.derivation.inputIds)) {
    clone.derivation = {
      ...value.derivation,
      inputIds: value.derivation.inputIds.map((inputId) => projectedDerivationIds.get(inputId) ?? inputId),
    };
  }
  return clone;
}

function sourceIdsFor(value) {
  return Array.isArray(value?.sourceIds) ? value.sourceIds : [];
}

function buildValuationEvidenceGraph(quantitative) {
  const sourcesById = new Map();
  const values = metricValues(quantitative);
  const projectedDerivationIds = frozenDerivationProjection(values);
  for (const [, value] of values) {
    if (!Array.isArray(value?.sources)) continue;
    for (const source of value.sources) {
      if (isRecord(source) && nonEmptyString(source.id) && !sourcesById.has(source.id)) {
        sourcesById.set(source.id, source);
      }
    }
  }
  return {
    sources: [...sourcesById.values()],
    inputs: [
      ...values.map(([id, value]) => cloneAtomicInput(id, value, projectedDerivationIds)),
      ...[...projectedDerivationIds.values()].map((id) => ({
        id,
        state: "unknown",
        reason: "The derivation input is validated in the frozen valuation snapshot and is not duplicated in the assessment envelope.",
      })),
    ],
    stages: [],
    outputs: values.map(([id, value]) => ({
      id,
      inputIds: [`input-${id}`],
      sourceIds: sourceIdsFor(value),
    })),
    assumptions: [],
    scoreAnchors: quantitative.scoreAnchors.map((anchor, index) => ({
      id: `score-anchor-${index + 1}`,
      outputIds: anchor.evidenceIds,
      sourceIds: [],
    })),
  };
}

function anchorIntervalContains(anchor, score) {
  return score.min >= anchor.min - 0.01
    && score.estimate >= anchor.min - 0.01
    && score.max >= anchor.min - 0.01
    && score.min <= anchor.max + 0.01
    && score.estimate <= anchor.max + 0.01
    && score.max <= anchor.max + 0.01;
}

function collectScoreAnchorErrors(assessment, errors, outputTypes = quantitativeOutputTypes()) {
  const quantitative = assessment.quantitativeEvidence;
  if (!Array.isArray(quantitative.scoreAnchors)) {
    errors.push("quantitative scoreAnchors must be an array.");
    return;
  }
  const dimensions = [...(assessment.dimensions?.researchValue ?? []), ...(assessment.dimensions?.autoresearchSuitability ?? [])];
  const byId = new Map(dimensions.map((dimension) => [dimension.id, dimension]));
  for (const anchor of quantitative.scoreAnchors) {
    if (Number.isFinite(anchor?.momentumAdjustment) && Math.abs(anchor.momentumAdjustment) > 0.25) {
      errors.push("momentum may move Importance by at most 0.25 points.");
      continue;
    }
    if (!hasOnlyFields(anchor, ["dimensionId", "recommended", "evidenceIds", "override", "momentumAdjustment"])
      || !byId.has(anchor.dimensionId)
      || !intervalOk(anchor.recommended, 5)
      || !Array.isArray(anchor.evidenceIds)
      || anchor.evidenceIds.length === 0
      || !anchor.evidenceIds.every(nonEmptyString)
      || !(anchor.override === null || (hasOnlyFields(anchor.override, ["reason"]) && nonEmptyString(anchor.override.reason)))
      || !(anchor.momentumAdjustment === undefined || (Number.isFinite(anchor.momentumAdjustment) && Math.abs(anchor.momentumAdjustment) <= 0.25))) {
      errors.push("quantitative score anchor is invalid.");
      continue;
    }
    const anchorTypes = anchor.evidenceIds.map((id) => outputTypes.get(id) ?? null);
    if (anchor.evidenceIds.includes("coverage")) {
      errors.push("coverage is confidence-only and concentration is warning-only; neither may be a score anchor.");
    }
    if (anchor.evidenceIds.includes("concentration")) {
      errors.push("coverage is confidence-only and concentration is warning-only; neither may be a score anchor.");
    }
    if (anchorTypes.some((type) => type === null)) {
      errors.push("score anchors must reference known quantitative outputs.");
    }
    if ((anchorTypes.some((type) => type === "scientificAttention" || type === "momentum") || anchor.momentumAdjustment !== undefined)
      && anchor.dimensionId !== "importance") {
      errors.push("scientific attention and momentum may anchor Importance only, never novelty.");
    }
    const inside = anchorIntervalContains(anchor.recommended, byId.get(anchor.dimensionId).score);
    if (inside && anchor.override !== null) errors.push("score anchors require a null override inside the recommended interval.");
    if (!inside && anchor.override === null) errors.push("scores outside a quantitative anchor require an override reason.");
  }
}

export function validateScoreAnchors(assessment) {
  const errors = [];
  if (!isRecord(assessment) || assessment.schemaVersion !== 2 || !isRecord(assessment.quantitativeEvidence)) {
    return { ok: false, errors: ["score anchors require a version 2 assessment."] };
  }
  collectScoreAnchorErrors(assessment, errors, quantitativeOutputTypes());
  return errors.length === 0 ? { ok: true, value: assessment.quantitativeEvidence.scoreAnchors } : { ok: false, errors };
}

function validateAssessmentQuantitativeEvidence(assessment, errors) {
  const quantitative = assessment.quantitativeEvidence;
  const fields = ["domain", "quantumArea", "snapshot", "scientificAttention", "technicalFeasibility", "socialValue", "capturableValue", "informationValue", "scoreAnchors", "sensitivity", "assumptions", "warnings"];
  if (!snapshotOk(quantitative?.snapshot)) {
    errors.push("quantitative snapshot identity is invalid.");
    return;
  }
  if (!hasOnlyFields(quantitative, fields)
    || quantitative.domain !== QUANTUM_DOMAIN
    || !QUANTUM_AREAS.includes(quantitative.quantumArea)
    || !hasOnlyFields(quantitative.scientificAttention, ["value", "momentum", "coverage", "concentration", "warnings", "formulaId", "components", "evidenceConfidence", "paperCount"])
    || !scientificDemandAuditOk(quantitative.scientificAttention)
    || !quantitativeValueOk(quantitative.scientificAttention?.value)
    || !quantitativeValueOk(quantitative.scientificAttention?.momentum)
    || !Number.isFinite(quantitative.scientificAttention?.coverage)
    || quantitative.scientificAttention.coverage < 0
    || quantitative.scientificAttention.coverage > 1
    || !(quantitative.scientificAttention?.concentration === null
      || (Number.isFinite(quantitative.scientificAttention.concentration)
        && quantitative.scientificAttention.concentration >= 0
        && quantitative.scientificAttention.concentration <= 1))
    || !Array.isArray(quantitative.scientificAttention.warnings)
    || !quantitative.scientificAttention.warnings.every(nonEmptyString)
    || !quantitativeValueOk(quantitative.technicalFeasibility)
    || !quantitativeValueOk(quantitative.socialValue)
    || !quantitativeValueOk(quantitative.capturableValue)
    || !quantitativeValueOk(quantitative.informationValue)
    || !Array.isArray(quantitative.sensitivity)
    || !quantitative.sensitivity.every((item) => hasOnlyFields(item, ["id", "label", "swing"])
      && nonEmptyString(item.id) && nonEmptyString(item.label) && Number.isFinite(item.swing))
    || !Array.isArray(quantitative.assumptions)
    || !quantitative.assumptions.every(nonEmptyString)
    || !Array.isArray(quantitative.warnings)
    || !quantitative.warnings.every(nonEmptyString)) {
    errors.push("quantitativeEvidence is invalid.");
    return;
  }
  const valuationEvidence = validateValuationQuantitativeEvidence(buildValuationEvidenceGraph(quantitative));
  if (!valuationEvidence.ok) {
    errors.push(...valuationEvidence.errors.map((error) => `quantitativeEvidence ${error}`));
  }
  if (propagateVisibility([quantitative]) === "private" && assessment.visibility !== "private") {
    errors.push("private quantitative evidence requires private assessment visibility.");
  }
  const scoreAnchors = validateScoreAnchors(assessment);
  if (!scoreAnchors.ok) errors.push(...scoreAnchors.errors);
}

function validateDimensions(dimensions, expected, errors, evidenceIds) {
  if (!Array.isArray(dimensions) || dimensions.length !== expected.length) {
    errors.push("dimensions must contain the policy dimensions exactly once.");
    return false;
  }

  let valid = true;
  for (let index = 0; index < expected.length; index += 1) {
    const dimension = dimensions[index];
    const policy = expected[index];
    if (!isRecord(dimension) || dimension.id !== policy.id || dimension.weight !== policy.weight) {
      errors.push("dimensions must contain the policy dimensions exactly once.");
      valid = false;
      continue;
    }
    if (!hasOnlyFields(dimension, ["id", "label", "weight", "score", "evidenceState", "rationale", "evidenceRefs"])
      || !nonEmptyString(dimension.label)
      || !nonEmptyString(dimension.rationale)
      || !intervalOk(dimension.score, 5)
      || !EVIDENCE_STATES.includes(dimension.evidenceState)
      || !Array.isArray(dimension.evidenceRefs)
      || !dimension.evidenceRefs.every((id) => nonEmptyString(id) && evidenceIds.has(id))) {
      errors.push(`dimension ${policy.id} is invalid.`);
      valid = false;
    }
    if (dimension.evidenceState === "unknown"
      && intervalOk(dimension.score, 5)
      && dimension.score.min === 0
      && dimension.score.estimate === 0
      && dimension.score.max === 0) {
      errors.push("unknown dimensions must use nonzero intervals when uncertainty remains.");
      valid = false;
    }
  }
  return valid;
}

function validateEvidence(evidence, errors) {
  if (!Array.isArray(evidence)) {
    errors.push("evidence must be an array.");
    return new Set();
  }
  const ids = new Set();
  for (const item of evidence) {
    if (!hasOnlyFields(item, ["id", "kind", "path", "locator", "summary"])
      || !nonEmptyString(item.id)
      || !["knowledge", "problem", "resolver", "unknown"].includes(item.kind)
      || !(item.path === null || typeof item.path === "string")
      || !(item.locator === null || typeof item.locator === "string")
      || typeof item.summary !== "string"
      || ids.has(item.id)) {
      errors.push("evidence entries must be valid and have unique IDs.");
      continue;
    }
    if (item.kind === "knowledge" && !isTrustedKnowledgePath(item.path)) {
      errors.push("knowledge evidence must use a trusted knowledge path.");
      continue;
    }
    ids.add(item.id);
  }
  return ids;
}

function validateAssessmentObject(assessment, resolution, errors) {
  const v1Fields = ["schemaVersion", "normalizedProblem", "verdict", "recommendation", "scores", "confidence", "dimensions", "largestBottleneck", "recommendedReframe", "informationGaps", "evidence"];
  const v2Fields = [...v1Fields, "quantitativeEvidence", "visibility"];
  if (!hasOnlyFields(assessment, assessment?.schemaVersion === 2 ? v2Fields : v1Fields)) {
    errors.push("assessment must be an object with only supported fields.");
    return {};
  }
  if (![1, 2].includes(assessment.schemaVersion) || !nonEmptyString(assessment.normalizedProblem)) errors.push("assessment schemaVersion and normalizedProblem are invalid.");
  if (assessment.schemaVersion === 2 && (!Object.hasOwn(assessment, "quantitativeEvidence") || !visibilityOk(assessment.visibility))) errors.push("version 2 assessments require quantitativeEvidence and visibility.");
  if (!RECOMMENDATIONS.includes(assessment.recommendation)) errors.push("recommendation is invalid.");
  if (!nonEmptyString(assessment.largestBottleneck)) errors.push("largestBottleneck is required.");
  if (!Array.isArray(assessment.informationGaps) || !assessment.informationGaps.every(nonEmptyString)) errors.push("informationGaps must be strings.");

  const evidenceIds = validateEvidence(assessment.evidence, errors);
  const researchDimensions = assessment.dimensions?.researchValue;
  const fitDimensions = assessment.dimensions?.autoresearchSuitability;
  if (!hasOnlyFields(assessment.dimensions, ["researchValue", "autoresearchSuitability"])) errors.push("dimensions must contain researchValue and autoresearchSuitability.");
  const researchValid = validateDimensions(researchDimensions, RESEARCH_VALUE_DIMENSIONS, errors, evidenceIds);
  const fitValid = validateDimensions(fitDimensions, AUTORESEARCH_DIMENSIONS, errors, evidenceIds);
  if (assessment.schemaVersion === 2) validateAssessmentQuantitativeEvidence(assessment, errors);

  const scoreIntervalsValid = hasOnlyFields(assessment.scores, ["researchValue", "autoresearchSuitability", "combined"])
    && intervalOk(assessment.scores?.researchValue, 100)
    && intervalOk(assessment.scores?.autoresearchSuitability, 100)
    && intervalOk(assessment.scores?.combined, 100);
  if (!scoreIntervalsValid
  ) {
    errors.push("assessment score intervals are invalid.");
  }

  if (!hasOnlyFields(assessment.confidence, ["level", "rationale"])
    || !CONFIDENCE_LEVELS.includes(assessment.confidence?.level)
    || !nonEmptyString(assessment.confidence?.rationale)) errors.push("confidence is invalid.");
  if (!hasOnlyFields(assessment.recommendedReframe, ["kind", "text"])
    || !["bounded", "none"].includes(assessment.recommendedReframe?.kind)
    || !nonEmptyString(assessment.recommendedReframe?.text)) errors.push("recommendedReframe is invalid.");
  if (!hasOnlyFields(assessment.verdict, ["label", "provisional", "possibleLabels"])
    || !VERDICT_LABELS.includes(assessment.verdict?.label)
    || typeof assessment.verdict?.provisional !== "boolean"
    || !Array.isArray(assessment.verdict?.possibleLabels)
    || assessment.verdict.possibleLabels.length === 0
    || !assessment.verdict.possibleLabels.every((label) => VERDICT_LABELS.includes(label))
    || !assessment.verdict.possibleLabels.includes(assessment.verdict.label)
    || new Set(assessment.verdict.possibleLabels).size !== assessment.verdict.possibleLabels.length) errors.push("verdict is invalid.");

  if (resolution?.status === "no-match" && Array.isArray(assessment.evidence)
    && assessment.evidence.some((item) => item?.kind === "knowledge")) {
    errors.push("no-match assessments must not cite knowledge evidence.");
  }

  if (!researchValid || !fitValid) return {};
  const researchValue = weightedInterval(researchDimensions);
  const autoresearchSuitability = weightedInterval(fitDimensions);
  const combined = harmonicInterval(researchValue, autoresearchSuitability);
  const label = deriveVerdict({
    valueScore: researchValue.estimate,
    fitScore: autoresearchSuitability.estimate,
    hasBoundedReframe: assessment.recommendedReframe?.kind === "bounded",
  });
  if (scoreIntervalsValid && !sameInterval(assessment.scores.researchValue, researchValue)) errors.push("researchValue model arithmetic does not match host arithmetic.");
  if (scoreIntervalsValid && !sameInterval(assessment.scores.autoresearchSuitability, autoresearchSuitability)) errors.push("autoresearchSuitability model arithmetic does not match host arithmetic.");
  if (scoreIntervalsValid && !sameInterval(assessment.scores.combined, combined)) errors.push("combined model arithmetic does not match host arithmetic.");
  if (assessment.verdict?.label !== label) errors.push("verdict label does not match host verdict rule.");

  return { scores: { researchValue, autoresearchSuitability, combined }, verdict: { label } };
}

function validateClarificationObject(clarification, resolution, errors) {
  if (!hasOnlyFields(clarification, ["query", "reason", "alternatives"])
    || !nonEmptyString(clarification.query)
    || !nonEmptyString(clarification.reason)
    || !Array.isArray(clarification.alternatives)
    || clarification.alternatives.length < 2) {
    errors.push("clarification is invalid.");
    return {};
  }
  for (const alternative of clarification.alternatives) {
    if (!hasOnlyFields(alternative, ["page", "topic", "title", "matchKind"])
      || !nonEmptyString(alternative.page)
      || !nonEmptyString(alternative.topic)
      || !nonEmptyString(alternative.title)
      || !nonEmptyString(alternative.matchKind)) {
      errors.push("clarification alternatives are invalid.");
      break;
    }
  }
  if (resolution?.status !== "ambiguous") errors.push("needs_input requires ambiguous knowledge resolution.");
  return {};
}

function validateKnowledgeResolution(resolution, errors) {
  if (!hasOnlyFields(resolution, ["query", "status", "topic", "orderedFiles"])
    || !nonEmptyString(resolution.query)
    || !["match", "no-match", "ambiguous"].includes(resolution.status)
    || !(resolution.topic === null || typeof resolution.topic === "string")
    || !Array.isArray(resolution.orderedFiles)
    || !resolution.orderedFiles.every((file) => nonEmptyString(file))) {
    errors.push("knowledgeResolution is invalid.");
    return;
  }
  if ((resolution.topic !== null && !isTrustedKnowledgePath(resolution.topic))
    || !resolution.orderedFiles.every(isTrustedKnowledgePath)) {
    errors.push("knowledgeResolution paths must use trusted knowledge paths.");
  }
}

export function validateAssessmentEnvelope(value) {
  value = normalizeAssessmentEnvelope(value);
  const errors = [];
  if (!isRecord(value)) return { ok: false, errors: ["Envelope must be an object."] };
  const envelopeFields = ["outcome", "language", "knowledgeResolution", "assessment", "clarification"];
  if (!hasOnlyFields(value, envelopeFields)) errors.push("Envelope contains unsupported fields.");
  if (!hasRequiredFields(value, ["assessment", "clarification"])) errors.push("Envelope must contain assessment and clarification fields.");
  if (!["assessment", "needs_input"].includes(value.outcome)) errors.push("outcome must be assessment or needs_input.");
  if (typeof value.language !== "string" || value.language.trim().length < 2) errors.push("language must be a string.");
  validateKnowledgeResolution(value.knowledgeResolution, errors);

  const hasAssessment = value.assessment !== null && value.assessment !== undefined;
  const hasClarification = value.clarification !== null && value.clarification !== undefined;
  if (Number(hasAssessment) + Number(hasClarification) !== 1) {
    errors.push("Envelope must contain exactly one of assessment or clarification.");
  }
  if (value.outcome === "assessment" && !hasAssessment) errors.push("assessment outcome requires assessment.");
  if (value.outcome === "needs_input" && !hasClarification) errors.push("needs_input outcome requires clarification.");
  if (value.outcome === "assessment" && value.knowledgeResolution?.status === "ambiguous") errors.push("ambiguous knowledge resolution requires needs_input.");

  const computed = hasAssessment
    ? validateAssessmentObject(value.assessment, value.knowledgeResolution, errors)
    : validateClarificationObject(value.clarification, value.knowledgeResolution, errors);
  return errors.length ? { ok: false, errors } : { ok: true, value, computed };
}

export function parseAssessmentFinalMessage(text) {
  try {
    return validateAssessmentEnvelope(JSON.parse(text));
  } catch (error) {
    return { ok: false, errors: [`Final message is not valid JSON: ${error.message}`] };
  }
}

export function summarizeCompletedAssessment({ run, envelope, computed, input = null }) {
  const assessment = envelope.assessment;
  const summary = {
    runId: run.runId,
    problemId: run.problemId,
    createdAt: run.createdAt,
    verdict: assessment.verdict.label,
    recommendation: assessment.recommendation,
    confidence: assessment.confidence.level,
    scores: computed.scores,
    largestBottleneck: assessment.largestBottleneck,
    provisional: assessment.verdict.provisional,
    reportHref: `/__local/assessments/reports/${run.problemId}/${run.runId}`,
    lifecycleMutation: false,
  };
  if (assessment.schemaVersion === 2) {
    const quantitative = assessment.quantitativeEvidence;
    const points = deriveAssessmentPointEstimates({ assessment, input });
    summary.visibility = assessment.visibility;
    summary.quantitative = {
      scientificAttention: points.scientificAttention ?? quantitative.scientificAttention.value,
      technicalSuccess: points.technicalSuccess ?? quantitative.technicalFeasibility,
      socialValue: quantitative.socialValue,
      capturableValue: quantitative.capturableValue,
      largestSensitivity: [...quantitative.sensitivity].sort((left, right) => Math.abs(right.swing) - Math.abs(left.swing) || left.id.localeCompare(right.id))[0] ?? null,
      snapshotId: quantitative.snapshot.snapshotId,
      freshness: quantitative.snapshot.freshness,
      ...(points.technicalSuccessMethod ? { technicalSuccessMethod: points.technicalSuccessMethod } : {}),
    };
  }
  return summary;
}
