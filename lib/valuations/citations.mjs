import { knownInterval, unknownValue } from "./types.mjs";

function relevantWeight(paper) {
  return Number.isFinite(paper?.relevance) ? Math.max(0, paper.relevance) : 0;
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

export function calculateCitationMetrics(papers, { currentYear } = {}) {
  if (!Array.isArray(papers)) throw new TypeError("papers must be an array.");
  if (!Number.isInteger(currentYear)) throw new TypeError("currentYear must be an integer.");
  const relevant = papers.filter((paper) => relevantWeight(paper) > 0);
  const totalRelevantWeight = relevant.reduce((total, paper) => total + relevantWeight(paper), 0);
  const comparable = relevant.filter((paper) => Number.isFinite(paper.citationNormalizedPercentile));
  const comparableWeight = comparable.reduce((total, paper) => total + relevantWeight(paper), 0);
  const coverage = totalRelevantWeight === 0 ? 0 : comparableWeight / totalRelevantWeight;
  const attentionMedian = weightedMedian(comparable.map((paper) => ({
    id: String(paper.id ?? ""), value: paper.citationNormalizedPercentile, weight: relevantWeight(paper),
  })));
  const scientificAttention = comparable.length < 2 || attentionMedian === null
    ? unknownValue("Fewer than two comparable relevant papers have normalized citation percentiles.")
    : pointMetric(100 * attentionMedian, "normalized-percentile-points");

  const latestCompleteYear = currentYear - 1;
  const priorCompleteYear = currentYear - 2;
  const momentumEntries = relevant.flatMap((paper) => {
    const latest = citationCountForYear(paper, latestCompleteYear);
    const prior = citationCountForYear(paper, priorCompleteYear);
    if (latest === null || prior === null) return [];
    return [{
      id: String(paper.id ?? ""),
      value: Math.log((latest + 1) / (prior + 1)),
      weight: relevantWeight(paper),
    }];
  });
  const momentumMedian = weightedMedian(momentumEntries);
  const momentum = momentumMedian === null
    ? unknownValue("No relevant papers have citation counts for both complete years.")
    : pointMetric(momentumMedian, "log-citation-growth");

  const contributions = relevant.map((paper) => relevantWeight(paper) * Math.max(0, Number.isFinite(paper.citedByCount) ? paper.citedByCount : 0));
  const contributionTotal = contributions.reduce((total, contribution) => total + contribution, 0);
  const concentration = contributionTotal === 0 ? 0 : Math.max(...contributions) / contributionTotal;
  const rawCitationTotal = papers.reduce((total, paper) => total + Math.max(0, Number.isFinite(paper?.citedByCount) ? paper.citedByCount : 0), 0);
  const warnings = [
    ...(totalRelevantWeight === 0 ? ["No papers have positive relevance weight."] : []),
    ...(coverage < 1 ? ["Normalized citation percentiles do not cover all relevant weight."] : []),
    ...(momentum.state === "unknown" ? ["Citation momentum is unavailable for the complete-year comparison."] : []),
  ];
  return { scientificAttention, momentum, coverage, concentration, warnings, rawCitationTotal };
}
