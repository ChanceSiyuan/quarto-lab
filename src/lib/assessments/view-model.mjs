export function formatScoreInterval(interval) {
  if (!interval) return "—";
  return formatPlainNumber(interval.estimate);
}

export const assessmentScoreMetrics = Object.freeze([
  {
    key: "researchValue",
    shortLabel: "V",
    label: "Research Value",
    description: "Problem-level value: importance, novelty, plausibility, publication potential, and value relative to cost.",
  },
  {
    key: "autoresearchSuitability",
    shortLabel: "A",
    label: "Autoresearch Fit",
    description: "Fit for a local automated research loop: executable objective, verification, feedback, auditability, and runtime.",
  },
  {
    key: "combined",
    shortLabel: "S",
    label: "Combined Priority",
    description: "Priority score combining research value and autoresearch fit with a harmonic mean.",
  },
]);

const PREREGISTRATION_DIMENSIONS = new Set([
  "fresh_evaluation",
  "generality_and_publication",
]);

const VALUATION_MODEL_DIMENSIONS = new Set([
  "expected_value_relative_to_cost",
]);

export function evidenceStateCopy(state, dimensionId = "") {
  if (state === "supported") return "Supported";
  if (state === "inferred") return "Inferred";
  if (state === "unknown" && PREREGISTRATION_DIMENSIONS.has(dimensionId)) return "Needs preregistration";
  if (state === "unknown" && VALUATION_MODEL_DIMENSIONS.has(dimensionId)) return "Needs valuation model";
  if (state === "unknown") return "Needs evidence";
  return state ? String(state) : "—";
}

function isPrivateValue(value) {
  return value?.visibility === "private" || value?.redacted === true;
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function formatPlainNumber(value) {
  if (!finiteNumber(value)) return "—";
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2))).replace(/\.0+$/, "");
}

function formatUnknownReason(value) {
  return value?.reason ? `Evidence gap — ${value.reason}` : "Evidence gap";
}

function formatPercent(value) {
  if (!finiteNumber(value)) return "—";
  return `${formatPlainNumber(value)}%`;
}

export function formatKnownInterval(value) {
  if (!value) return "—";
  if (isPrivateValue(value)) return "Private";
  if (value.state === "unknown") return formatUnknownReason(value);
  if (value.state !== "known") return "—";
  if (!value.interval) return "—";
  if (value.unit === "percent") return formatPercent(value.interval.base);
  if (value.unit === "fraction") return formatPercent(value.interval.base * 100);
  const suffix = value.unit ? ` ${value.unit}` : "";
  const point = formatPlainNumber(value.interval.base);
  return point === "—" ? point : `${point}${suffix}`;
}

export function formatScientificAttention(value) {
  if (!value) return "—";
  if (isPrivateValue(value)) return "Private";
  if (value.state !== "known" || !value.interval) return formatUnknownReason(value);
  if (value.unit === "score-100") {
    const score = formatPlainNumber(value.interval.base);
    const confidence = typeof value.evidenceConfidence === "string" && value.evidenceConfidence
      ? `${value.evidenceConfidence[0].toUpperCase()}${value.evidenceConfidence.slice(1).toLowerCase()} evidence confidence`
      : "Evidence confidence unavailable";
    return `${score} / 100 · ${confidence}`;
  }
  const count = formatPlainNumber(value.interval.base);
  if (count === "0") return "No matched citations";
  return count === "1" ? "1 matched citation" : `${count} matched citations`;
}

function moneySymbol(currency) {
  return currency === "USD" ? "$" : `${currency ?? ""} `;
}

function formatMoneyAmount(value, currency) {
  if (!finiteNumber(value)) return "—";
  const abs = Math.abs(value);
  const symbol = moneySymbol(currency);
  if (abs >= 1_000_000_000) return `${symbol}${formatPlainNumber(value / 1_000_000_000)}B`;
  if (abs >= 1_000_000) return `${symbol}${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${symbol}${formatPlainNumber(value / 1_000)}K`;
  return `${symbol}${formatPlainNumber(value)}`;
}

export function formatMoneyInterval(value) {
  if (!value) return "—";
  if (isPrivateValue(value)) return "Private";
  if (value.state === "unknown") return formatUnknownReason(value);
  if (value.state !== "known" || !value.interval) return "—";
  const currency = value.currency ?? /^([A-Z]{3})_\d{4}$/.exec(value.unit ?? "")?.[1] ?? "USD";
  const year = value.priceBaseYear ?? /^([A-Z]{3})_(\d{4})$/.exec(value.unit ?? "")?.[2] ?? null;
  const base = formatMoneyAmount(value.interval.base, currency);
  return `${base}${currency || year ? ` · ${currency}${year ? ` ${year}` : ""}` : ""}`;
}

const INDUSTRY_SOCIAL_PROXY = Object.freeze({
  state: "known",
  interval: { low: 43_000_000_000, base: 57_000_000_000, high: 71_000_000_000 },
  unit: "USD_2035",
  currency: "USD",
  priceBaseYear: 2035,
  visibility: "public",
});

const COMMERCIAL_INVESTMENT_PROXY = Object.freeze({
  state: "known",
  interval: { low: 10_000_000_000, base: 10_000_000_000, high: 10_000_000_000 },
  unit: "USD_2026",
  currency: "USD",
  priceBaseYear: 2026,
  visibility: "public",
});

function publicMoneyValue(value) {
  if (!value || isPrivateValue(value)) return null;
  if (value.state !== "known" || !value.interval) return null;
  return value.currency || /^[A-Z]{3}_\d{4}$/.test(value.unit ?? "") ? value : null;
}

export function formatTechnicalSuccessEstimate(value) {
  if (value?.state !== "known") return "—";
  const point = formatKnownInterval(value);
  return value.estimateKind === "model" ? `${point} · Model estimate` : `${point} · Measured`;
}

export function formatIndustrySocialProxy(value) {
  return formatMoneyInterval(publicMoneyValue(value) ?? INDUSTRY_SOCIAL_PROXY);
}

export function formatCommercialInvestmentProxy(value) {
  return formatMoneyInterval(publicMoneyValue(value) ?? COMMERCIAL_INVESTMENT_PROXY);
}

export function valuationStatusCopy(state) {
  switch (state?.kind ?? state?.status) {
    case "no_evidence":
      return {
        heading: "No valuation evidence",
        body: "Research public evidence before running a quantum assessment.",
        actionLabel: "Research evidence",
      };
    case "queued":
    case "researching":
    case "confirming":
      return {
        heading: "Evidence research running",
        body: "The local valuation workflow is collecting and freezing evidence.",
        actionLabel: null,
      };
    case "needs_confirmation":
      return {
        heading: "Review valuation assumptions",
        body: "Confirm selected reference papers and material assumptions before freezing the snapshot.",
        actionLabel: "Review assumptions",
      };
    case "ready":
      return {
        heading: "Evidence ready",
        body: "A frozen valuation snapshot is ready for assessment.",
        actionLabel: "Run assessment",
      };
    case "stale":
      return {
        heading: "Evidence may be stale",
        body: "A newer or expired valuation signal is available.",
        actionLabel: "Refresh evidence",
      };
    case "research_failed":
      return {
        heading: "Evidence research failed",
        body: state?.error?.message ?? state?.reason ?? "Retry evidence research.",
        actionLabel: "Retry research",
      };
    default:
      return {
        heading: "Valuation evidence unavailable",
        body: "Quantum valuation is available only through the local assessment service.",
        actionLabel: null,
      };
  }
}

export function assessmentStatusCopy(state) {
  switch (state?.kind) {
    case "never":
      return {
        heading: "No assessment yet",
        body: "Run a local Codex assessment for this problem.",
        actionLabel: "Run assessment",
      };
    case "queued":
      return {
        heading: "Assessment queued",
        body: `Queue position ${state.queuePosition}.`,
        actionLabel: null,
      };
    case "running":
      return {
        heading: "Assessment running",
        body: `Elapsed ${state.elapsedSeconds ?? 0}s.`,
        actionLabel: null,
      };
    case "needs-input":
      return {
        heading: "Knowledge match needs input",
        body: "Choose the exact trusted knowledge match to continue.",
        actionLabel: null,
      };
    case "completed":
      return {
        heading: "Assessment complete",
        body: "Recommendation is advisory and does not change lifecycle status.",
        actionLabel: "Rerun",
      };
    case "failed":
      return {
        heading: "Assessment failed",
        body: state.reason ?? "Open diagnostics for details.",
        actionLabel: "Retry",
      };
    case "stale":
      return {
        heading: "Assessment may be stale",
        body: "Inputs changed since this report was generated.",
        actionLabel: "Run new assessment",
      };
    default:
      return {
        heading: "Local assessment unavailable",
        body: "Start the local development server to run assessments.",
        actionLabel: null,
      };
  }
}

export function latestAssessmentSummary(problemState) {
  const runs = [...(problemState?.runs ?? [])];
  runs.sort((a, b) => String(b.runId ?? "").localeCompare(String(a.runId ?? "")));
  return runs.find((run) => run.status === "completed" && run.summary)?.summary ?? null;
}

export function assessmentStateFromProblemResponse(body) {
  const runs = body?.runs ?? [];
  if (body?.activeJob) {
    const status = body.activeJob.status;
    return {
      kind: status === "queued" ? "queued" : status,
      ...body.activeJob,
      runs,
    };
  }
  const latestRun = runs[0];
  if (latestRun?.status === "failed") {
    return {
      kind: "failed",
      reason: latestRun.error?.message ?? "Open diagnostics for details.",
      latest: body?.latest ?? latestAssessmentSummary(body),
      runs,
    };
  }
  if (body?.stale) return { kind: "stale", latest: body.latest, runs };
  if (body?.latest) return { kind: "completed", latest: body.latest, runs };
  const latest = latestAssessmentSummary(body);
  if (latest) return { kind: "completed", latest, runs };
  if (latestRun?.status === "completed") {
    return {
      kind: "completed",
      latest: {
        reportHref: `/__local/assessments/reports/${encodeURIComponent(latestRun.problemId)}/${encodeURIComponent(latestRun.runId)}`,
      },
      runs,
    };
  }
  return { kind: "never", runs };
}

export function isLocalAssessmentUnavailable(errorOrResponse) {
  return errorOrResponse instanceof TypeError || errorOrResponse?.status === 404;
}

export async function assessmentServiceFailure(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // Fall back to the HTTP status when the proxy did not return JSON.
  }
  const code = payload?.code ?? payload?.error ?? null;
  const reason = payload?.message
    ? `${payload.message}${code ? ` (${code})` : ""}`
    : `Local service returned ${response.status}${code ? ` (${code})` : ""}.`;
  return { kind: "failed", reason };
}
