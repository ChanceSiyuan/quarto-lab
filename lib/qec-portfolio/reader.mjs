import { sortPortfolioRows } from "./view-model.mjs";

const QEC_DOMAIN = "quantum-computing";
const QEC_AREA = "error-correction-and-fault-tolerance";
const EVIDENCE_LABEL = "External-evidence-backed advisory comparison";

function newestCompletedRun(runs) {
  return [...runs]
    .filter((run) => run?.status === "completed" && run.summary)
    .sort((left, right) => {
      const leftTime = Date.parse(left.updatedAt ?? "") || 0;
      const rightTime = Date.parse(right.updatedAt ?? "") || 0;
      return rightTime - leftTime || String(right.runId).localeCompare(String(left.runId));
    })[0] ?? null;
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function containsNonPublicVisibility(value) {
  if (Array.isArray(value)) return value.some(containsNonPublicVisibility);
  if (!isRecord(value)) return false;
  if (Object.hasOwn(value, "visibility") && value.visibility !== "public") return true;
  return Object.values(value).some(containsNonPublicVisibility);
}

function field(value, privateAssessment = false) {
  if (value === undefined || privateAssessment || containsNonPublicVisibility(value)) return null;
  return structuredClone(value);
}

function rowFor(problem, run) {
  const summary = run?.summary ?? null;
  const quantitative = summary?.quantitative ?? {};
  const privateAssessment = summary?.visibility !== undefined && summary.visibility !== "public";
  return {
    problemId: problem.id,
    title: problem.title ?? null,
    status: problem.status ?? null,
    verdict: field(summary?.verdict, privateAssessment),
    confidence: field(summary?.confidence, privateAssessment),
    researchValue: field(summary?.scores?.researchValue, privateAssessment),
    autoresearchFit: field(summary?.scores?.autoresearchSuitability, privateAssessment),
    combinedPriority: field(summary?.scores?.combined, privateAssessment),
    scientificAttention: field(quantitative.scientificAttention, privateAssessment),
    technicalSuccess: field(quantitative.technicalSuccess, privateAssessment),
    socialValue: field(quantitative.socialValue, privateAssessment),
    capturableValue: field(quantitative.capturableValue, privateAssessment),
    largestBottleneck: field(summary?.largestBottleneck, privateAssessment),
    snapshotId: field(quantitative.snapshotId, privateAssessment),
    problemHref: `/problems/${problem.id}`,
    reportHref: run && !privateAssessment ? `/__local/assessments/reports/${problem.id}/${run.runId}` : null,
  };
}

export function createQecPortfolioReader({ repository, assessmentStore, now = () => new Date() } = {}) {
  if (typeof repository?.listProblems !== "function") throw new TypeError("repository must provide listProblems.");
  if (typeof assessmentStore?.listRuns !== "function") throw new TypeError("assessmentStore must provide listRuns.");
  return Object.freeze({
    async read() {
      const problems = repository.listProblems({ includeRejected: true, includeArchived: true })
        .filter((problem) => problem.domain === QEC_DOMAIN && problem.quantumArea === QEC_AREA);
      const rows = await Promise.all(problems.map(async (problem) => rowFor(
        problem,
        newestCompletedRun(await assessmentStore.listRuns(problem.id)),
      )));
      return {
        schemaVersion: 1,
        generatedAt: new Date(now()).toISOString(),
        evidenceLabel: EVIDENCE_LABEL,
        count: rows.length,
        rows: sortPortfolioRows(rows),
      };
    },
  });
}
