export function formatScoreInterval(interval) {
  if (!interval) return "—";
  return `${interval.estimate} (${interval.min}-${interval.max})`;
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

function formatPercent(value) {
  if (!finiteNumber(value)) return "—";
  return `${formatPlainNumber(value)}%`;
}

function formatPercentInterval(value, multiplier = 1) {
  const interval = value?.interval;
  if (!interval) return "—";
  return `${formatPercent(interval.base * multiplier)} (${formatPlainNumber(interval.low * multiplier)}-${formatPlainNumber(interval.high * multiplier)}%)`;
}

function formatIntervalParts(value, formatter) {
  const interval = value?.interval;
  if (!interval) return "—";
  return `${formatter(interval.base)} (${formatter(interval.low)}-${formatter(interval.high)})`;
}

export function formatKnownInterval(value) {
  if (!value) return "—";
  if (isPrivateValue(value)) return "Private";
  if (value.state === "unknown") return "Unknown";
  if (value.state !== "known") return "—";
  if (value.unit === "percent") return formatPercentInterval(value);
  if (value.unit === "fraction") return formatPercentInterval(value, 100);
  const suffix = value.unit ? ` ${value.unit}` : "";
  const interval = formatIntervalParts(value, formatPlainNumber);
  return interval === "—" ? interval : `${interval}${suffix}`;
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
  if (value.state === "unknown") return "Unknown";
  if (value.state !== "known" || !value.interval) return "—";
  const currency = value.currency ?? /^([A-Z]{3})_\d{4}$/.exec(value.unit ?? "")?.[1] ?? "USD";
  const year = value.priceBaseYear ?? /^([A-Z]{3})_(\d{4})$/.exec(value.unit ?? "")?.[2] ?? null;
  const base = formatMoneyAmount(value.interval.base, currency);
  const low = formatMoneyAmount(value.interval.low, currency);
  const high = formatMoneyAmount(value.interval.high, currency);
  return `${base} (${low}-${high}${currency || year ? `, ${currency}${year ? ` ${year}` : ""}` : ""})`;
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
        body: "Confirm anchor papers and material assumptions before freezing the snapshot.",
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
