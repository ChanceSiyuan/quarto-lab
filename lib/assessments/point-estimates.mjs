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

function citationSummary(input) {
  const papers = frozenPapers(input);
  const recorded = input?.valuation?.recalculationInputs?.manifest?.citation?.rawCitationTotal;
  const missingCitationCount = papers.filter((paper) => !Number.isFinite(paper?.citedByCount)).length;
  if (Number.isFinite(recorded)) {
    return { total: Math.max(0, recorded), missingCitationCount };
  }
  return {
    total: papers.reduce(
      (total, paper) => total + (Number.isFinite(paper?.citedByCount) ? Math.max(0, paper.citedByCount) : 0),
      0,
    ),
    missingCitationCount,
  };
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

  const citation = citationSummary(input);
  const scientificAttention = {
    id: "scientific-attention-citation-total",
    state: "known",
    interval: point(citation.total),
    unit: "count",
    visibility: "public",
    estimateKind: "citation-total",
    missingCitationCount: citation.missingCitationCount,
  };

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
