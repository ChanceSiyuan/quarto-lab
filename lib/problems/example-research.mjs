import exampleManifest from "../../problems/QMB-001/example.json" with { type: "json" };
import attempt001 from "../../problems/QMB-001/attempts/ATT-001/attempt.json" with { type: "json" };
import attempt002 from "../../problems/QMB-001/attempts/ATT-002/attempt.json" with { type: "json" };
import attempt003 from "../../problems/QMB-001/attempts/ATT-003/attempt.json" with { type: "json" };
import attempt004 from "../../problems/QMB-001/attempts/ATT-004/attempt.json" with { type: "json" };
import attempt005 from "../../problems/QMB-001/attempts/ATT-005/attempt.json" with { type: "json" };

export const EXAMPLE_RESEARCH_PROBLEM_ID = "QMB-001";

const rawAttempts = [attempt001, attempt002, attempt003, attempt004, attempt005]
  .toSorted((left, right) => left.sequence - right.sequence);
const attemptById = new Map(rawAttempts.map((attempt) => [attempt.id, attempt]));
const EXAMPLE_DISCLAIMER = "Example data - synthetic results for interface demonstration only.";
const ATTEMPT_ID_PATTERN = /^ATT-\d{3}$/;
const SAFE_ARTIFACT_NAME_PATTERN = /^(?!\.)(?!.*(?:^|\/)\.\.(?:\/|$))[A-Za-z0-9][A-Za-z0-9._-]*$/;
const GATE_RESULTS = new Set(["passed", "failed"]);

function clone(value) {
  return structuredClone(value);
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function assertCondition(condition, message) {
  if (!condition) {
    throw new Error(`Static example ${message}.`);
  }
}

function assertNonEmptyString(value, message) {
  assertCondition(isNonEmptyString(value), message);
}

function assertTimestamp(value, message) {
  assertNonEmptyString(value, message);
  assertCondition(Number.isFinite(Date.parse(value)), message);
}

function assertCount(value, message, maximum = Number.POSITIVE_INFINITY) {
  assertCondition(Number.isInteger(value) && value >= 0 && value <= maximum, message);
}

function validateManifest(manifest) {
  assertCondition(isPlainObject(manifest), "manifest must be an object");
  assertCondition(manifest.schemaVersion === 1, "manifest schemaVersion must be 1");
  assertCondition(manifest.kind === "static-research-example", "manifest kind is invalid");
  assertCondition(manifest.disclaimer === EXAMPLE_DISCLAIMER, "manifest disclaimer is invalid");
  assertCondition(isPlainObject(manifest.baseline), "manifest baseline must be an object");
  assertNonEmptyString(manifest.baseline.label, "manifest baseline label is invalid");
  assertCondition(
    Number.isFinite(manifest.baseline.suiteRuntimeSeconds) && manifest.baseline.suiteRuntimeSeconds > 0,
    "manifest baseline suiteRuntimeSeconds is invalid",
  );
}

function validateAttempt(attempt, index, attempts, seen) {
  const label = `attempt ${attempt?.id ?? index + 1}`;
  assertCondition(isPlainObject(attempt), `${label} must be an object`);
  assertCondition(attempt.schemaVersion === 1, `${label} schemaVersion must be 1`);
  assertCondition(attempt.problemId === EXAMPLE_RESEARCH_PROBLEM_ID, `${label} has mismatched problemId`);
  assertCondition(ATTEMPT_ID_PATTERN.test(attempt.id), `${label} has an invalid id`);
  assertCondition(!seen.has(attempt.id), `${label} is duplicated`);
  seen.add(attempt.id);
  assertCondition(attempt.sequence === index + 1, `${label} has a non-contiguous sequence`);
  assertNonEmptyString(attempt.title, `${label} title is invalid`);
  assertNonEmptyString(attempt.summary, `${label} summary is invalid`);
  assertCondition(attempt.stage === "development", `${label} stage is invalid`);
  assertCondition(["accepted", "rejected"].includes(attempt.decision), `${label} decision is invalid`);
  assertCondition(typeof attempt.promoted === "boolean", `${label} promoted must be boolean`);
  assertCondition(!attempt.promoted || attempt.decision === "accepted", `${label} promoted decision is invalid`);

  assertCondition(isPlainObject(attempt.gate), `${label} gate must be an object`);
  for (const name of ["publicSmoke", "containment", "development"]) {
    assertCondition(GATE_RESULTS.has(attempt.gate[name]), `${label} gate ${name} is invalid`);
  }
  assertCondition(
    attempt.decision !== "accepted" || attempt.gate.development === "passed",
    `${label} accepted gate is invalid`,
  );

  assertCondition(isPlainObject(attempt.method), `${label} method must be an object`);
  assertNonEmptyString(attempt.method.hypothesis, `${label} method hypothesis is invalid`);
  assertCondition(
    Array.isArray(attempt.method.changes) && attempt.method.changes.length > 0
      && attempt.method.changes.every(isNonEmptyString),
    `${label} method changes are invalid`,
  );
  const expectedPredecessor = index === 0 ? null : attempts[index - 1].id;
  assertCondition(attempt.method.learnedFrom === expectedPredecessor, `${label} has an invalid predecessor`);

  assertCondition(isPlainObject(attempt.metrics), `${label} metrics must be an object`);
  const metrics = attempt.metrics;
  assertCount(metrics.runs, `${label} metrics runs are invalid`);
  assertCondition(metrics.runs > 0, `${label} metrics runs are invalid`);
  assertCount(metrics.verifiedWitnesses, `${label} metrics verifiedWitnesses are invalid`, metrics.runs);
  assertCount(metrics.targetHits, `${label} metrics targetHits are invalid`, metrics.verifiedWitnesses);
  assertCount(metrics.timeouts, `${label} metrics timeouts are invalid`, metrics.runs);
  assertCount(metrics.crashes, `${label} metrics crashes are invalid`, metrics.runs);
  assertCount(metrics.invalidClaims, `${label} metrics invalidClaims are invalid`, metrics.runs);
  assertCondition(
    metrics.verifiedWitnesses + metrics.timeouts + metrics.crashes <= metrics.runs,
    `${label} metrics outcome counts are inconsistent`,
  );
  assertCondition(
    Number.isFinite(metrics.normalizedQuality)
      && metrics.normalizedQuality >= 0 && metrics.normalizedQuality <= 1,
    `${label} metrics normalizedQuality is invalid`,
  );
  for (const name of ["runtimeSeconds", "medianSeconds", "p95Seconds", "speedup"]) {
    assertCondition(Number.isFinite(metrics[name]) && metrics[name] > 0, `${label} metrics ${name} is invalid`);
  }
  assertCondition(metrics.medianSeconds <= metrics.p95Seconds, `${label} metrics latency range is invalid`);

  assertNonEmptyString(attempt.interpretation, `${label} interpretation is invalid`);
  assertCondition(
    Array.isArray(attempt.learnings) && attempt.learnings.length > 0 && attempt.learnings.every(isNonEmptyString),
    `${label} learnings are invalid`,
  );
  assertCondition(isPlainObject(attempt.provenance), `${label} provenance must be an object`);
  for (const name of ["branch", "commit", "worktreeState", "model"]) {
    assertNonEmptyString(attempt.provenance[name], `${label} provenance ${name} is invalid`);
  }
  assertCondition(
    Array.isArray(attempt.artifacts) && attempt.artifacts.length > 0
      && attempt.artifacts.every((artifact) => SAFE_ARTIFACT_NAME_PATTERN.test(artifact)),
    `${label} artifact name is unsafe`,
  );
  assertTimestamp(attempt.createdAt, `${label} createdAt is invalid`);
}

export function validateStaticResearchFixture(manifest, attempts) {
  validateManifest(manifest);
  assertCondition(Array.isArray(attempts) && attempts.length > 0, "attempt list is invalid");
  const seen = new Set();
  for (const [index, attempt] of attempts.entries()) {
    validateAttempt(attempt, index, attempts, seen);
  }
  assertCondition(
    attempts.filter((attempt) => attempt.promoted).length === 1,
    "attempt promoted state is inconsistent",
  );
}

validateStaticResearchFixture(exampleManifest, rawAttempts);

export function isStaticResearchExampleProblem(problemId) {
  return problemId === EXAMPLE_RESEARCH_PROBLEM_ID;
}

export function getStaticResearchExample(problemId) {
  if (!isStaticResearchExampleProblem(problemId)) {
    return null;
  }
  return {
    manifest: clone(exampleManifest),
    attempts: clone(rawAttempts),
  };
}

export function listStaticResearchAttempts(problemId) {
  return getStaticResearchExample(problemId)?.attempts ?? [];
}

export function getStaticResearchAttempt(problemId, attemptId) {
  if (!isStaticResearchExampleProblem(problemId)) {
    return null;
  }
  const attempt = attemptById.get(attemptId);
  return attempt ? clone(attempt) : null;
}

export function getStaticResearchArtifactPath(problemId, attemptId, artifact) {
  return `problems/${problemId}/attempts/${attemptId}/${artifact}`;
}
