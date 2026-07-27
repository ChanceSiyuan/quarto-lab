import { buildProblemHref } from "./view-state.mjs";

export function formatProblemTimestamp(value) {
  return String(value).replace("T", " ").replace(/(?:\.\d{3})?Z$/, " UTC");
}

export function buildTierMetrics(summary) {
  return [
    ["Total", summary.total],
    ["Accepted", `${summary.accepted} / ${summary.target}`],
    ["Solved", `${summary.solved} / ${summary.target}`],
    ["Published", `${summary.published} / ${summary.target}`],
    ["Rejected", summary.rejected],
  ];
}

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
  const provenanceField = {
    key: "provenance",
    label: "Provenance",
    value: `${problem.provenance.sourceCount} sources`,
  };
  const activityField = {
    key: "activity",
    label: "Recent activity",
    primary: problem.lastActivity.summary,
    secondary: formatProblemTimestamp(problem.lastActivity.at),
  };
  const updatedField = {
    key: "updated",
    label: "Updated",
    value: formatProblemTimestamp(problem.updatedAt),
  };
  const openField = { key: "open", label: "Open", value: "Open problem", href };

  return {
    problem: problemField,
    status: statusField,
    gate: gateField,
    provenance: provenanceField,
    activity: activityField,
    updated: updatedField,
    open: openField,
    fields: [
      problemField,
      statusField,
      gateField,
      provenanceField,
      activityField,
      updatedField,
      openField,
    ],
  };
}
