import { buildProblemHref } from "./view-state.mjs";

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

export function judgmentStatusCopy(status) {
  switch (status) {
    case "accepted":
    case "solving":
    case "solved":
    case "publishing":
    case "published":
      return "Solving judged done";
    case "rejected":
      return "Rejected";
    case "archived":
      return "Archived";
    default:
      return "Awaiting judgment";
  }
}

// Demo-score values shown while assessments are synthetic; they mirror the
// static assessment cards on the problem detail page.
const DEMO_SCORES = Object.freeze({
  scientificDemand: "33.4 / 100",
  eansv: "$1.1B USD 2035",
  autoresearchFit: "38.5 / 100",
});

export function buildProblemPresentation(problem) {
  const href = buildProblemHref(problem.id);
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
    value: DEMO_SCORES.scientificDemand,
  };
  const eansvField = {
    key: "eansv",
    label: "Expected Attributable Net Social Value (EANSV)",
    value: DEMO_SCORES.eansv,
  };
  const autoresearchFitField = {
    key: "autoresearchFit",
    label: "Autoresearch Fit",
    value: DEMO_SCORES.autoresearchFit,
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
