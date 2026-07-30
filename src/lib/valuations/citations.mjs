import { knownInterval, unknownValue } from "./types.mjs";

export const SCIENTIFIC_DEMAND_FORMULA_ID = "qec-scientific-demand-v1";

const COMPONENT_WEIGHTS = Object.freeze({
  influence: 0.45,
  momentum: 0.30,
  breadth: 0.15,
  network: 0.10,
});
const CONFIRMED_REFERENCE_RELEVANCE_FLOOR = 0.25;
const BREADTH_SATURATION_COUNT = 20;

function clamp(value, low = 0, high = 1) {
  return Math.min(high, Math.max(low, value));
}

function relevanceWeight(paper) {
  const reported = Number.isFinite(paper?.relevance) ? Math.max(0, paper.relevance) : 0;
  return paper?.inclusionReason === "confirmed-anchor"
    ? Math.max(CONFIRMED_REFERENCE_RELEVANCE_FLOOR, reported)
    : reported;
}

function institutionFrequencies(papers) {
  const frequencies = new Map();
  for (const paper of papers) {
    for (const id of new Set(paper?.institutionIds ?? [])) {
      frequencies.set(id, (frequencies.get(id) ?? 0) + 1);
    }
  }
  return frequencies;
}

function independenceDiscount(paper, frequencies) {
  if (Number.isFinite(paper?.independenceDiscount)) return clamp(paper.independenceDiscount);
  const ids = [...new Set(paper?.institutionIds ?? [])];
  if (ids.length === 0) return 1;
  return ids.reduce((total, id) => total + 1 / Math.sqrt(frequencies.get(id) ?? 1), 0) / ids.length;
}

function evidenceWeight(paper, frequencies) {
  const confidence = Number.isFinite(paper?.matchConfidence) ? clamp(paper.matchConfidence) : 1;
  return relevanceWeight(paper) * confidence * independenceDiscount(paper, frequencies);
}

function weightedMedian(entries) {
  const totalWeight = entries.reduce((total, entry) => total + entry.weight, 0);
  if (totalWeight <= 0) return null;
  let cumulative = 0;
  for (const entry of [...entries].sort((left, right) => left.value - right.value || left.id.localeCompare(right.id))) {
    cumulative += entry.weight;
    if (cumulative >= totalWeight / 2) return entry.value;
  }
  return null;
}

function citationCountForYear(paper, year) {
  const value = (paper.countsByYear ?? []).find((count) => count?.year === year)?.citedByCount;
  return Number.isFinite(value) && value >= 0 ? value : null;
}

function pointMetric(value, unit) {
  return knownInterval({ low: value, base: value, high: value, unit });
}

function logistic(value) {
  return 1 / (1 + Math.exp(-value));
}

function saturatedBreadth(count) {
  return Math.min(1, Math.log1p(count) / Math.log1p(BREADTH_SATURATION_COUNT));
}

function oneDecimal(value) {
  return Math.round((value + Number.EPSILON) * 10) / 10;
}

function evidenceConfidence(comparablePaperCount, coverage) {
  if (comparablePaperCount >= 5 && coverage >= 0.8) return "high";
  if (comparablePaperCount >= 3) return "medium";
  return "low";
}

export function calculateCitationMetrics(papers, { currentYear } = {}) {
  if (!Array.isArray(papers)) throw new TypeError("papers must be an array.");
  if (!Number.isInteger(currentYear)) throw new TypeError("currentYear must be an integer.");

  const frequencies = institutionFrequencies(papers);
  const weightedPapers = papers
    .map((paper) => ({ paper, weight: evidenceWeight(paper, frequencies) }))
    .filter(({ weight }) => weight > 0);
  const totalRelevantWeight = weightedPapers.reduce((total, entry) => total + entry.weight, 0);
  const comparable = weightedPapers.filter(({ paper }) => Number.isFinite(paper.citationNormalizedPercentile));
  const comparableWeight = comparable.reduce((total, entry) => total + entry.weight, 0);
  const coverage = totalRelevantWeight === 0 ? 0 : comparableWeight / totalRelevantWeight;
  const influenceValue = weightedMedian(comparable.map(({ paper, weight }) => ({
    id: String(paper.id ?? ""),
    value: clamp(paper.citationNormalizedPercentile),
    weight,
  })));

  const latestCompleteYear = currentYear - 1;
  const priorCompleteYear = currentYear - 2;
  const momentumEntries = weightedPapers.flatMap(({ paper, weight }) => {
    const latest = citationCountForYear(paper, latestCompleteYear);
    const prior = citationCountForYear(paper, priorCompleteYear);
    if (latest === null || prior === null) return [];
    return [{
      id: String(paper.id ?? ""),
      value: Math.log((latest + 1) / (prior + 1)),
      weight,
    }];
  });
  const momentumMedian = weightedMedian(momentumEntries);
  const momentumValue = momentumMedian === null ? null : logistic(momentumMedian);

  const independentInstitutionIds = [...new Set(weightedPapers.flatMap(({ paper }) => paper.institutionIds ?? []))];
  const paperBreadth = saturatedBreadth(weightedPapers.length);
  const institutionBreadth = saturatedBreadth(independentInstitutionIds.length);
  const breadthValue = 0.6 * paperBreadth + 0.4 * institutionBreadth;

  const components = {
    influence: influenceValue === null
      ? { availability: "unknown", reason: "Citation evidence insufficient.", weight: COMPONENT_WEIGHTS.influence, unit: "fraction" }
      : { availability: "known", value: influenceValue, weight: COMPONENT_WEIGHTS.influence, unit: "fraction", paperCount: comparable.length, coverage },
    momentum: momentumValue === null
      ? { availability: "unknown", reason: "No papers have citation counts for both complete years.", weight: COMPONENT_WEIGHTS.momentum, unit: "fraction" }
      : { availability: "known", value: momentumValue, rawLogGrowth: momentumMedian, weight: COMPONENT_WEIGHTS.momentum, unit: "fraction", paperCount: momentumEntries.length },
    breadth: weightedPapers.length === 0
      ? { availability: "unknown", reason: "No papers have positive evidence weight.", weight: COMPONENT_WEIGHTS.breadth, unit: "fraction" }
      : { availability: "known", value: breadthValue, weight: COMPONENT_WEIGHTS.breadth, unit: "fraction", paperBreadth, institutionBreadth, paperCount: weightedPapers.length, institutionCount: independentInstitutionIds.length },
    network: { availability: "reserved", weight: COMPONENT_WEIGHTS.network },
  };

  const availableComponents = [components.influence, components.momentum, components.breadth]
    .filter((component) => component.availability === "known");
  const availableWeight = availableComponents.reduce((total, component) => total + component.weight, 0);
  const confidence = evidenceConfidence(comparable.length, coverage);
  const scientificDemand = availableWeight <= 0
    ? unknownValue("Citation evidence insufficient.")
    : pointMetric(oneDecimal(100 * availableComponents.reduce((total, component) => total + component.weight * component.value, 0) / availableWeight), "score-100");

  const observedCitationCounts = papers
    .map((paper) => paper?.citedByCount)
    .filter((value) => Number.isFinite(value) && value >= 0);
  const citationContributions = weightedPapers.flatMap(({ paper, weight }) => Number.isFinite(paper.citedByCount) && paper.citedByCount >= 0
    ? [weight * paper.citedByCount]
    : []);
  const contributionTotal = citationContributions.reduce((total, contribution) => total + contribution, 0);
  const rawCitationTotal = observedCitationCounts.length > 0
    ? observedCitationCounts.reduce((total, count) => total + count, 0)
    : null;
  const warnings = [
    ...(totalRelevantWeight === 0 ? ["No papers have positive evidence weight."] : []),
    ...(coverage < 1 ? ["Normalized citation percentiles do not cover all relevant evidence weight."] : []),
    ...(components.momentum.availability === "unknown" ? ["Citation momentum is unavailable for the complete-year comparison."] : []),
    ...(observedCitationCounts.length < papers.length ? ["Some raw citation counts are not reported and were excluded."] : []),
  ];

  return {
    formulaId: SCIENTIFIC_DEMAND_FORMULA_ID,
    scientificDemand,
    scientificAttention: scientificDemand,
    components,
    momentum: momentumValue === null ? unknownValue(components.momentum.reason) : pointMetric(momentumValue, "fraction"),
    evidenceConfidence: confidence,
    coverage,
    paperCount: weightedPapers.length,
    comparablePaperCount: comparable.length,
    independentInstitutionCount: independentInstitutionIds.length,
    availableWeight,
    concentration: contributionTotal > 0 ? Math.max(...citationContributions) / contributionTotal : null,
    warnings,
    rawCitationTotal,
    rawCitationObservedPaperCount: observedCitationCounts.length,
    rawCitationMissingPaperCount: papers.length - observedCitationCounts.length,
  };
}
