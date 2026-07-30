export const TECHNICAL_SUCCESS_DIMENSION_WEIGHTS = Object.freeze({
  plausibility: 0.35,
  executable_objective: 0.20,
  correctness_and_anti_gaming: 0.20,
  incremental_feedback: 0.15,
  attempt_runtime: 0.10,
});

function point(value) {
  return { low: value, base: value, high: value };
}

function frozenPapers(input) {
  const papers = input?.valuation?.recalculationInputs?.papers;
  return Array.isArray(papers) ? papers : [];
}

function evaluationYear(manifest, papers) {
  const createdAt = new Date(manifest?.createdAt ?? "");
  if (Number.isFinite(createdAt.valueOf())) return createdAt.getUTCFullYear();
  const latestRecordedYear = Math.max(
    0,
    ...papers.flatMap((paper) => (paper?.countsByYear ?? []).map((count) => count?.year).filter(Number.isInteger)),
  );
  return latestRecordedYear > 0 ? latestRecordedYear + 1 : 2026;
}

function scientificDemandPoint(metric, audit) {
  if (metric?.state !== "known") {
    return { state: "unknown", reason: metric?.reason ?? "Citation evidence insufficient." };
  }
  const value = metric.interval.base;
  return {
    id: "scientific-demand-score",
    state: "known",
    interval: point(value),
    unit: "score-100",
    visibility: "public",
    estimateKind: "scientific-demand-model",
    formulaId: SCIENTIFIC_DEMAND_FORMULA_ID,
    components: structuredClone(audit.components ?? {}),
    evidenceConfidence: audit.evidenceConfidence ?? "low",
    coverage: Number.isFinite(audit.coverage) ? audit.coverage : 0,
    paperCount: Number.isInteger(audit.paperCount) ? audit.paperCount : 0,
  };
}

function citationSummary(input) {
  const papers = frozenPapers(input);
  const manifest = input?.valuation?.recalculationInputs?.manifest ?? {};
  const citation = manifest.citation ?? {};
  if (citation.formulaId === SCIENTIFIC_DEMAND_FORMULA_ID) {
    return scientificDemandPoint(citation.scientificDemand ?? citation.scientificAttention, citation);
  }
  const recalculated = calculateCitationMetrics(papers, {
    currentYear: evaluationYear(manifest, papers),
  });
  return scientificDemandPoint(recalculated.scientificDemand, recalculated);
}

function dimensionEstimates(assessment) {
  const dimensions = [
    ...(assessment?.dimensions?.researchValue ?? []),
    ...(assessment?.dimensions?.autoresearchSuitability ?? []),
  ];
  return new Map(dimensions.map((item) => [item.id, item.score?.estimate]));
}

export function deriveAssessmentPointEstimates({ assessment, input }) {
  if (assessment?.visibility === "private") {
    return { scientificAttention: null, technicalSuccess: null, technicalSuccessMethod: null };
  }

  const scientificAttention = citationSummary(input);

  const measured = assessment?.quantitativeEvidence?.technicalFeasibility;
  if (measured?.state === "known") {
    return {
      scientificAttention,
      technicalSuccess: measured,
      technicalSuccessMethod: { kind: "measured" },
    };
  }

  const estimates = dimensionEstimates(assessment);
  const missing = Object.keys(TECHNICAL_SUCCESS_DIMENSION_WEIGHTS)
    .filter((id) => !Number.isFinite(estimates.get(id)));
  if (missing.length > 0) {
    throw new Error(`Missing technical-success dimensions: ${missing.join(", ")}`);
  }

  const weighted = Object.entries(TECHNICAL_SUCCESS_DIMENSION_WEIGHTS)
    .reduce((total, [id, weight]) => total + estimates.get(id) * weight, 0);
  const value = Number(((weighted / 5) * 100).toFixed(1));
  return {
    scientificAttention,
    technicalSuccess: {
      id: "technical-success-model-estimate",
      state: "known",
      interval: point(value),
      unit: "percent",
      visibility: "public",
      estimateKind: "model",
    },
    technicalSuccessMethod: {
      kind: "model",
      formulaId: "qec-technical-success-v1",
      weights: TECHNICAL_SUCCESS_DIMENSION_WEIGHTS,
    },
  };
}
import {
  SCIENTIFIC_DEMAND_FORMULA_ID,
  calculateCitationMetrics,
} from "../valuations/citations.mjs";
