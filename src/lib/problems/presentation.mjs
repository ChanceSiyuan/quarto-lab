import { buildProblemHref } from "./view-state.mjs";
import { getStaticEvaluationPoints } from "../pages-showcase/evaluation-scenarios.mjs";

export function formatProblemTimestamp(value) {
  return String(value).replace("T", " ").replace(/(?:\.\d{3})?Z$/, " UTC");
}

export function buildTierMetrics(summary) {
  return [
    ["Total", summary.total],
    ["Accepted", summary.accepted],
    ["Solved", summary.solved],
    ["Published", summary.published],
    ["Rejected", summary.rejected],
  ];
}

export function judgmentStatusCopy(status, problemId) {
  if (problemId === "Prob-000") {
    return "Done";
  }
  if (getStaticEvaluationPoints(problemId)) {
    return "Judged";
  }

  switch (status) {
    case "accepted":
    case "solving":
      return "Solving";
    case "solved":
    case "publishing":
      return "Judged";
    case "published":
      return "Done";
    case "rejected":
      return "Rejected";
    case "archived":
      return "Archived";
    default:
      return "Awaiting judgment";
  }
}

export function judgmentStatusTone(status, problemId) {
  switch (judgmentStatusCopy(status, problemId)) {
    case "Solving":
      return "solving";
    case "Judged":
      return "solved";
    case "Done":
      return "published";
    default:
      return status;
  }
}

// Problems without a recorded evaluation scenario are unjudged, so their
// score cells stay empty instead of showing invented numbers.
const UNSCORED = "—";

function formatEansvPoint(value) {
  const sign = value < 0 ? "-" : "";
  const millions = Math.abs(value) / 1_000_000;
  const digits = millions > 0 && millions < 1 && !Number.isInteger(millions * 10) ? 2 : 1;
  return `${sign}$${millions.toFixed(digits)}M USD 2026`;
}

export function buildProblemPresentation(problem) {
  const href = buildProblemHref(problem.id);
  const points = getStaticEvaluationPoints(problem.id);
  const problemField = {
    key: "problem",
    label: "Problem",
    id: problem.id,
    title: problem.title,
    summary: problem.summary,
  };
  const statusField = { key: "status", label: "Status", value: problem.status };
  const gateField = {
    key: "gate",
    label: "Executable gate",
    primary: problem.gate.type,
    secondary: problem.gate.readiness,
  };
  const scientificDemandField = {
    key: "scientificDemand",
    label: "Scientific Demand Score",
    value: points ? `${points.scientificDemand} / 100` : UNSCORED,
  };
  const eansvField = {
    key: "eansv",
    label: "Expected Attributable Net Social Value (EANSV)",
    value: points ? points.eansvDisplay ?? formatEansvPoint(points.eansv) : UNSCORED,
  };
  const autoresearchFitField = {
    key: "autoresearchFit",
    label: "Autoresearch Fit",
    value: points ? `${points.autoresearchFit} / 100` : UNSCORED,
  };
  const openField = { key: "open", label: "Open", value: "Open problem", href };

  return {
    problem: problemField,
    status: statusField,
    gate: gateField,
    scientificDemand: scientificDemandField,
    eansv: eansvField,
    autoresearchFit: autoresearchFitField,
    open: openField,
    fields: [
      problemField,
      statusField,
      gateField,
      scientificDemandField,
      eansvField,
      autoresearchFitField,
    ],
  };
}
