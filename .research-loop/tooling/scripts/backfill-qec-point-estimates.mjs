import { readFile, readdir } from "node:fs/promises";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

import { summarizeCompletedAssessment } from "../../../src/lib/assessments/contract.mjs";
import { renderAssessmentReport } from "../../../src/lib/assessments/html-report.mjs";

const DEFAULT_PROBLEM_IDS = Object.freeze(
  Array.from({ length: 21 }, (_, index) => `Prob-${String(index + 1).padStart(3, "0")}`),
);

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

async function newestCompletedRun(rootDir, problemId) {
  const assessmentsDir = join(rootDir, "problems", problemId, "assessments");
  const entries = await readdir(assessmentsDir, { withFileTypes: true });
  for (const entry of entries.filter((item) => item.isDirectory()).sort((a, b) => b.name.localeCompare(a.name))) {
    const runDir = join(assessmentsDir, entry.name);
    const run = await readJson(join(runDir, "run.json"));
    if (run.status === "completed") return { runDir, run };
  }
  throw new Error(`No completed assessment found for ${problemId}.`);
}

function assertCompleteSummary(problemId, summary) {
  const quantitative = summary?.quantitative;
  const missing = [];
  if (!Number.isFinite(summary?.scores?.researchValue?.estimate)) missing.push("researchValue");
  if (!Number.isFinite(summary?.scores?.autoresearchSuitability?.estimate)) missing.push("autoresearchFit");
  if (!Number.isFinite(summary?.scores?.combined?.estimate)) missing.push("combinedPriority");
  if (!Number.isFinite(quantitative?.scientificAttention?.interval?.base)) missing.push("scientificAttention");
  if (!Number.isFinite(quantitative?.technicalSuccess?.interval?.base)) missing.push("technicalSuccess");
  if (missing.length > 0) {
    throw new Error(`Incomplete point estimates for ${problemId}: ${missing.join(", ")}.`);
  }
}

export async function backfillQecPointEstimates({
  rootDir = process.cwd(),
  problemIds = DEFAULT_PROBLEM_IDS,
} = {}) {
  const workspaceRoot = resolve(rootDir);
  const result = { updated: [], ready: [], skipped: [], errors: [] };
  for (const problemId of problemIds) {
    try {
      const { runDir, run } = await newestCompletedRun(workspaceRoot, problemId);
      const input = await readJson(join(runDir, "input.json"));
      const artifact = await readJson(join(runDir, "assessment.json"));
      const { envelope, computed } = artifact;
      const summary = summarizeCompletedAssessment({ run, envelope, computed, input });
      assertCompleteSummary(problemId, summary);
      const reportHtml = renderAssessmentReport({ run, input, envelope, computed });
      if (/Pending sealed evaluation|Pending measurement/.test(reportHtml)) {
        throw new Error(`Generated report still contains pending assessment copy for ${problemId}.`);
      }
      result.ready.push(problemId);
    } catch (error) {
      result.errors.push({ problemId, message: error instanceof Error ? error.message : String(error) });
    }
  }
  return result;
}

async function main() {
  const result = await backfillQecPointEstimates();
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (result.errors.length > 0) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
