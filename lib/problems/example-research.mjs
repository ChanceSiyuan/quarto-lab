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

function clone(value) {
  return structuredClone(value);
}

function validateStaticExample() {
  const seen = new Set();
  for (const [index, attempt] of rawAttempts.entries()) {
    if (attempt.problemId !== EXAMPLE_RESEARCH_PROBLEM_ID) {
      throw new Error(`Static example attempt ${attempt.id} has mismatched problemId.`);
    }
    if (seen.has(attempt.id)) {
      throw new Error(`Static example attempt ${attempt.id} is duplicated.`);
    }
    seen.add(attempt.id);
    if (attempt.sequence !== index + 1) {
      throw new Error(`Static example attempt ${attempt.id} has a non-contiguous sequence.`);
    }
    const expectedPredecessor = index === 0 ? null : rawAttempts[index - 1].id;
    if (attempt.method.learnedFrom !== expectedPredecessor) {
      throw new Error(`Static example attempt ${attempt.id} has an invalid predecessor.`);
    }
  }
}

validateStaticExample();

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
