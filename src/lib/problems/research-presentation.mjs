function titleCase(value) {
  return `${value.slice(0, 1).toUpperCase()}${value.slice(1)}`.replaceAll("-", " ");
}

function formatQuality(value) {
  return Number(value).toFixed(3);
}

function formatVerified(metrics) {
  return `${metrics.verifiedWitnesses}/${metrics.runs}`;
}

export function formatMetricValue(value, timingStatus) {
  if (timingStatus === "not-run") return "not run";
  if (value === null || value === undefined) return "legacy not recorded";
  return `${Number(value).toFixed(2)} s`;
}

export function formatCandidate(candidate) {
  return candidate.status === "present" ? "present" : "not generated";
}

export function formatGateLabel(value) {
  return titleCase(value);
}

export function buildResearchArtifactPath(problemId, attemptId, artifactPath) {
  return `problems/${problemId}/attempts/${attemptId}/${artifactPath}`;
}

export function buildResearchLedger(record) {
  const attempts = [...record.attempts].sort((left, right) => left.sequence - right.sequence);
  const acceptedCount = attempts.filter((attempt) => attempt.decision === "accepted").length;
  const bestAttempt = attempts.reduce(
    (best, attempt) => (!best || attempt.metrics.targetHits > best.metrics.targetHits ? attempt : best),
    null,
  );
  const candidateCount = attempts.filter((attempt) => attempt.candidate.status === "present").length;

  return {
    cards: [
      { label: "Attempts", value: String(attempts.length) },
      { label: "Accepted", value: String(acceptedCount) },
      { label: "Best hits", value: bestAttempt ? `${bestAttempt.metrics.targetHits}/${bestAttempt.metrics.runs}` : "0/0" },
      { label: "Candidates", value: `${candidateCount} present` },
    ],
    rows: attempts.map((attempt) => ({
      id: attempt.id,
      title: attempt.title,
      method: attempt.method.description,
      summary: attempt.summary,
      cohort: attempt.cohort,
      stage: formatGateLabel(attempt.stage),
      decision: formatGateLabel(attempt.decision),
      publicContract: formatGateLabel(attempt.gate.publicContract),
      runs: String(attempt.metrics.runs),
      verified: formatVerified(attempt.metrics),
      hits: String(attempt.metrics.targetHits),
      quality: formatQuality(attempt.metrics.normalizedQuality),
      runtime: formatMetricValue(attempt.metrics.runtimeSeconds, attempt.metrics.timingStatus),
      p95: formatMetricValue(attempt.metrics.p95Seconds, attempt.metrics.timingStatus),
      candidate: formatCandidate(attempt.candidate),
      href: `/problems/${attempt.problemId}/attempts/${attempt.id}`,
    })),
  };
}

export function buildResearchAttemptDossier(attempt, recordManifest) {
  const timingStatus = attempt.metrics.timingStatus;
  const candidatePresent = attempt.candidate.status === "present";

  return {
    id: attempt.id,
    title: attempt.title,
    summary: attempt.summary,
    disclaimer: recordManifest.disclaimer,
    cohort: attempt.cohort,
    stage: formatGateLabel(attempt.stage),
    decision: formatGateLabel(attempt.decision),
    metrics: [
      { label: "Verified", value: formatVerified(attempt.metrics) },
      { label: "Target hits", value: String(attempt.metrics.targetHits) },
      { label: "Quality", value: formatQuality(attempt.metrics.normalizedQuality) },
      { label: "Runtime", value: formatMetricValue(attempt.metrics.runtimeSeconds, timingStatus) },
      { label: "Median", value: formatMetricValue(attempt.metrics.medianSeconds, timingStatus) },
      { label: "P95", value: formatMetricValue(attempt.metrics.p95Seconds, timingStatus) },
    ],
    method: {
      description: attempt.method.description,
      learnedFrom: attempt.method.learnedFrom,
    },
    evaluationPath: [
      { label: "Containment", value: formatGateLabel(attempt.gate.containment) },
      { label: "Public contract", value: formatGateLabel(attempt.gate.publicContract) },
      { label: "Development", value: formatGateLabel(attempt.gate.development) },
      { label: "Decision", value: formatGateLabel(attempt.decision) },
    ],
    provenance: attempt.provenance,
    candidate: {
      ...attempt.candidate,
      label: formatCandidate(attempt.candidate),
      message: candidatePresent ? "Candidate code is available." : "Candidate code was not generated.",
    },
    artifacts: attempt.artifacts.map((artifact) => ({
      ...artifact,
      path: buildResearchArtifactPath(attempt.problemId, attempt.id, artifact.path),
    })),
  };
}
