export function formatScoreInterval(interval) {
  if (!interval) return "—";
  return `${interval.estimate} (${interval.min}-${interval.max})`;
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

export function isLocalAssessmentUnavailable(errorOrResponse) {
  return errorOrResponse instanceof TypeError || errorOrResponse?.status === 404;
}
