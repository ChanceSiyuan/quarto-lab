import { getStaticResearchArtifactPath } from "./example-research.mjs";

const titleCase = (value) => `${value.slice(0, 1).toUpperCase()}${value.slice(1)}`;

export function formatSeconds(value) {
  const digits = value < 10 && !Number.isInteger(value) ? 2 : 1;
  return `${value.toFixed(digits)} s`;
}

export function formatQuality(value) {
  return value.toFixed(3);
}

export function formatSpeedup(value) {
  return `${value.toFixed(1)}x`;
}

export function formatVerified(metrics) {
  return `${metrics.verifiedWitnesses}/${metrics.runs}`;
}

function formatGate(gate) {
  return [
    { label: "Containment", value: gate.containment },
    { label: "Public smoke", value: gate.publicSmoke },
    { label: "Development", value: gate.development },
  ];
}

function decisionLabel(attempt) {
  return attempt.promoted ? "Accepted, promoted" : titleCase(attempt.decision);
}

export function buildExampleResearchLedger(example) {
  const attempts = example.attempts;
  const acceptedCount = attempts.filter((attempt) => attempt.decision === "accepted").length;
  const bestHits = attempts.reduce((best, attempt) => Math.max(best, attempt.metrics.targetHits), 0);
  const bestRuns = attempts.reduce((best, attempt) => Math.max(best, attempt.metrics.runs), 0);
  const bestSpeedup = attempts.reduce((best, attempt) => Math.max(best, attempt.metrics.speedup), 0);

  return {
    cards: [
      { label: "Attempts", value: String(attempts.length) },
      { label: "Accepted", value: String(acceptedCount) },
      { label: "Best hits", value: `${bestHits}/${bestRuns}` },
      { label: "Best speedup", value: formatSpeedup(bestSpeedup) },
    ],
    rows: attempts.map((attempt) => ({
      id: attempt.id,
      title: attempt.title,
      method: attempt.title,
      summary: attempt.summary,
      stage: titleCase(attempt.stage),
      decision: decisionLabel(attempt),
      gate: formatGate(attempt.gate),
      verified: formatVerified(attempt.metrics),
      hits: String(attempt.metrics.targetHits),
      quality: formatQuality(attempt.metrics.normalizedQuality),
      runtime: formatSeconds(attempt.metrics.runtimeSeconds),
      p95: formatSeconds(attempt.metrics.p95Seconds),
      speedup: formatSpeedup(attempt.metrics.speedup),
      href: `/problems/${attempt.problemId}/attempts/${attempt.id}`,
    })),
  };
}

export function buildAttemptDossier(attempt, exampleManifest) {
  return {
    id: attempt.id,
    title: attempt.title,
    summary: attempt.summary,
    disclaimer: exampleManifest.disclaimer,
    stage: titleCase(attempt.stage),
    decision: decisionLabel(attempt),
    metrics: [
      { label: "Verified", value: formatVerified(attempt.metrics) },
      { label: "Target hits", value: String(attempt.metrics.targetHits) },
      { label: "Quality", value: formatQuality(attempt.metrics.normalizedQuality) },
      { label: "Runtime", value: formatSeconds(attempt.metrics.runtimeSeconds) },
      { label: "P95", value: formatSeconds(attempt.metrics.p95Seconds) },
      { label: "Speedup", value: formatSpeedup(attempt.metrics.speedup) },
    ],
    method: attempt.method,
    interpretation: attempt.interpretation,
    learnings: attempt.learnings,
    evaluationPath: [
      { label: "Containment", value: titleCase(attempt.gate.containment) },
      { label: "Public smoke", value: titleCase(attempt.gate.publicSmoke) },
      { label: "Development", value: titleCase(attempt.gate.development) },
      { label: "Decision", value: decisionLabel(attempt) },
    ],
    provenance: attempt.provenance,
    createdAt: attempt.createdAt,
    artifacts: attempt.artifacts.map((artifact) =>
      getStaticResearchArtifactPath(attempt.problemId, attempt.id, artifact),
    ),
  };
}
