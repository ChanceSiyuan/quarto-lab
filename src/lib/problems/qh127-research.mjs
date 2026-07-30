import run from "../../../problems/Prob-127/autoresearch/run.json" with { type: "json" };
import attempt001 from "../../../problems/Prob-127/autoresearch/attempts/attempt-001.json" with { type: "json" };
import attempt002 from "../../../problems/Prob-127/autoresearch/attempts/attempt-002.json" with { type: "json" };
import attempt003 from "../../../problems/Prob-127/autoresearch/attempts/attempt-003.json" with { type: "json" };
import attempt004 from "../../../problems/Prob-127/autoresearch/attempts/attempt-004.json" with { type: "json" };
import attempt005 from "../../../problems/Prob-127/autoresearch/attempts/attempt-005.json" with { type: "json" };
import attempt006 from "../../../problems/Prob-127/autoresearch/attempts/attempt-006.json" with { type: "json" };
import attempt007 from "../../../problems/Prob-127/autoresearch/attempts/attempt-007.json" with { type: "json" };
import attempt008 from "../../../problems/Prob-127/autoresearch/attempts/attempt-008.json" with { type: "json" };
import attempt009 from "../../../problems/Prob-127/autoresearch/attempts/attempt-009.json" with { type: "json" };

export const QH127_RESEARCH_PROBLEM_ID = "Prob-127";

const rawAttempts = [
  attempt001,
  attempt002,
  attempt003,
  attempt004,
  attempt005,
  attempt006,
  attempt007,
  attempt008,
  attempt009,
].toSorted((left, right) => left.sequence - right.sequence);

const ATTEMPT_ID_PATTERN = /^attempt-\d{3}$/;
const VERDICTS = new Set(["passed", "failed"]);
const DECISIONS = new Set(["accepted", "rejected"]);
const NUMERIC_STRING = /^\d+$/;

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function assertCondition(condition, message) {
  if (!condition) {
    throw new Error(`qh-127 research record ${message}.`);
  }
}

function validateRun(manifest) {
  assertCondition(isPlainObject(manifest), "run must be an object");
  assertCondition(manifest.schemaVersion === 1, "run schemaVersion must be 1");
  assertCondition(
    manifest.kind === "quantum-harness-autoresearch-run",
    "run kind is invalid",
  );
  assertCondition(manifest.problemId === QH127_RESEARCH_PROBLEM_ID, "run problemId is invalid");
  assertCondition(isNonEmptyString(manifest.runId), "run runId is invalid");
  assertCondition(isNonEmptyString(manifest.status), "run status is invalid");
  assertCondition(isPlainObject(manifest.baseline), "run baseline must be an object");
  assertCondition(
    NUMERIC_STRING.test(manifest.baseline.cost),
    "run baseline cost must be a numeric string",
  );
  assertCondition(
    Number.isInteger(manifest.attemptsRecorded) && manifest.attemptsRecorded > 0,
    "run attemptsRecorded is invalid",
  );
  assertCondition(isPlainObject(manifest.finalization), "run finalization must be an object");
  assertCondition(
    VERDICTS.has(manifest.finalization.verdict),
    "run finalization verdict is invalid",
  );
  assertCondition(
    typeof manifest.finalization.strictlyBetter === "boolean",
    "run finalization strictlyBetter must be boolean",
  );
}

function validateAttempt(attempt, index, seen) {
  const label = `attempt ${attempt?.id ?? index + 1}`;
  assertCondition(isPlainObject(attempt), `${label} must be an object`);
  assertCondition(attempt.schemaVersion === 1, `${label} schemaVersion must be 1`);
  assertCondition(attempt.problemId === QH127_RESEARCH_PROBLEM_ID, `${label} problemId is invalid`);
  assertCondition(ATTEMPT_ID_PATTERN.test(attempt.id), `${label} id is invalid`);
  assertCondition(!seen.has(attempt.id), `${label} is duplicated`);
  seen.add(attempt.id);
  assertCondition(attempt.sequence === index + 1, `${label} sequence is not contiguous`);
  assertCondition(DECISIONS.has(attempt.decision), `${label} decision is invalid`);
  assertCondition(typeof attempt.promoted === "boolean", `${label} promoted must be boolean`);
  assertCondition(
    !attempt.promoted || attempt.decision === "accepted",
    `${label} promoted decision is invalid`,
  );
  assertCondition(isPlainObject(attempt.strategy), `${label} strategy must be an object`);
  assertCondition(
    Array.isArray(attempt.strategy.slots) && attempt.strategy.slots.length > 0,
    `${label} strategy slots are invalid`,
  );
  for (const slot of attempt.strategy.slots) {
    assertCondition(isNonEmptyString(slot.slot), `${label} slot name is invalid`);
    assertCondition(isNonEmptyString(slot.method), `${label} slot method is invalid`);
    assertCondition(
      Number.isFinite(slot.seconds) && slot.seconds > 0,
      `${label} slot seconds are invalid`,
    );
  }
  assertCondition(isPlainObject(attempt.outcome), `${label} outcome must be an object`);
  assertCondition(VERDICTS.has(attempt.outcome.verdict), `${label} verdict is invalid`);
  assertCondition(
    NUMERIC_STRING.test(attempt.outcome.exactCost),
    `${label} exactCost must be a numeric string`,
  );
  assertCondition(
    NUMERIC_STRING.test(attempt.outcome.baselineCost),
    `${label} baselineCost must be a numeric string`,
  );
}

function validate() {
  validateRun(run);
  const seen = new Set();
  rawAttempts.forEach((attempt, index) => validateAttempt(attempt, index, seen));
  assertCondition(
    rawAttempts.length === run.attemptsRecorded,
    "attempt count does not match the run manifest",
  );
  const promoted = rawAttempts.filter((attempt) => attempt.promoted);
  assertCondition(promoted.length === 1, "exactly one attempt must be promoted");
  assertCondition(promoted[0].id === run.bestAttempt, "promoted attempt must be the run best");
  assertCondition(
    promoted[0].outcome.exactCost === run.bestCost,
    "run bestCost must match the promoted attempt",
  );
}

validate();

export function isQh127ResearchProblem(problemId) {
  return problemId === QH127_RESEARCH_PROBLEM_ID;
}

export function getQh127Research() {
  return {
    run: structuredClone(run),
    attempts: structuredClone(rawAttempts),
  };
}

function formatCost(numericString) {
  return Number(numericString).toExponential(3);
}

function formatRatio(numericString, baselineString) {
  const ratio = Number(numericString) / Number(baselineString);
  const text = ratio >= 1 ? ratio.toFixed(2) : ratio.toPrecision(3);
  return `${text.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "")}x`;
}

function summarizeSlots(slots) {
  return slots.map((slot) => `${slot.slot}=${slot.method}`).join(" + ");
}

export function buildQh127ResearchLedger(research) {
  const { run: manifest, attempts } = research;
  const best = attempts.find((attempt) => attempt.promoted);
  const cards = [
    { label: "Baseline cost", value: formatCost(manifest.baseline.cost) },
    { label: "Best public cost", value: formatCost(manifest.bestCost) },
    {
      label: "Best public ratio",
      value: formatRatio(manifest.bestCost, manifest.baseline.cost),
    },
    {
      label: "Attempts",
      value: `${attempts.length} / ${manifest.attemptBudget}`,
    },
    {
      label: "Sealed finalization",
      value: manifest.finalization.verdict,
    },
    { label: "Run status", value: manifest.status },
  ];
  const rows = attempts.map((attempt) => ({
    id: attempt.id,
    method: summarizeSlots(attempt.strategy.slots),
    summary: attempt.strategy.selectionReason,
    stage: attempt.stage,
    verdict: attempt.outcome.verdict,
    exactCost: formatCost(attempt.outcome.exactCost),
    ratio: formatRatio(attempt.outcome.exactCost, attempt.outcome.baselineCost),
    decision: attempt.decision,
    promoted: attempt.promoted,
    learnedFrom: attempt.learnedFrom ?? "—",
    href: `#${attempt.id}`,
  }));
  return { cards, rows, best, finalization: manifest.finalization };
}
