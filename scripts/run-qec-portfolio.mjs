import { execFile as execFileCallback } from "node:child_process";
import { readFile } from "node:fs/promises";
import { relative, resolve, join } from "node:path";
import { promisify } from "node:util";

import { createArtifactStore } from "../lib/assessments/artifact-store.mjs";
import { resolveExistingRunDir } from "../lib/assessments/paths.mjs";
import { createAssessmentJobManager } from "../lib/assessments/job-manager.mjs";
import { createProblemRepository } from "../lib/problems/repository.mjs";
import {
  createQecPortfolioBatchRunner,
  QEC_PORTFOLIO_BATCH_IDS,
  verifyQecPortfolio,
} from "../lib/qec-portfolio/batch-runner.mjs";
import { QEC_PORTFOLIO_PROBLEMS } from "../lib/qec-portfolio/catalog.mjs";
import { createRetryingOpenAlexClient } from "../lib/qec-portfolio/openalex-retry.mjs";
import { registerQecPortfolio } from "../lib/qec-portfolio/registration.mjs";
import { createQecPortfolioValuationResearcher } from "../lib/qec-portfolio/valuation-researcher.mjs";
import { createValuationJobManager } from "../lib/valuations/job-manager.mjs";
import { createOpenAlexClient } from "../lib/valuations/openalex-client.mjs";
import { createValuationSnapshotStore } from "../lib/valuations/snapshot-store.mjs";
import { createKnowledgeResolver } from "./local-assessment-service.mjs";

const execFile = promisify(execFileCallback);

function readArg(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

export async function createLocalRepository(rootDir) {
  const index = JSON.parse(await readFile(join(rootDir, ".generated", "problem-index.json"), "utf8"));
  const repository = createProblemRepository(index);
  return {
    ...repository,
    async readProblemMarkdown(problemId) {
      if (!repository.getProblem(problemId)) return null;
      return readFile(join(rootDir, "problems", problemId, "problem.md"), "utf8");
    },
  };
}

function withAssessmentReaders(rootDir, store) {
  return {
    ...store,
    async readAssessment(problemId, runId) {
      const runDir = await resolveExistingRunDir(rootDir, problemId, runId);
      return JSON.parse(await readFile(join(runDir, "assessment.json"), "utf8"));
    },
    async readReport(problemId, runId) {
      const runDir = await resolveExistingRunDir(rootDir, problemId, runId);
      return readFile(join(runDir, "report.html"), "utf8");
    },
  };
}

export async function rebuildAndVerifyIndex(rootDir, { execFileFn = execFile, readFileFn = readFile } = {}) {
  await execFileFn(process.execPath, ["scripts/build-problem-index.mjs", "--reserve-id", "Prob-000"], { cwd: rootDir });
  const index = JSON.parse(await readFileFn(join(rootDir, ".generated", "problem-index.json"), "utf8"));
  const qecIds = index.problems
    .filter((problem) => problem.domain === "quantum-computing" && problem.quantumArea === "error-correction-and-fault-tolerance")
    .map((problem) => problem.id)
    .sort();
  return JSON.stringify(qecIds) === JSON.stringify([...QEC_PORTFOLIO_BATCH_IDS].sort());
}

export async function runQecPortfolio({ rootDir, apiKey = process.env.OPENALEX_API_KEY?.trim() } = {}) {
  const workspaceRoot = resolve(rootDir ?? process.cwd());
  if (!apiKey) return {
    status: "incomplete",
    phases: { preflight: "failed" },
    problems: [],
    error: { code: "OPENALEX_KEY_REQUIRED" },
  };
  let valuationManager = null;
  let assessmentManager = null;
  try {
    const valuationStore = createValuationSnapshotStore({ rootDir: workspaceRoot });
    const assessmentStore = withAssessmentReaders(workspaceRoot, createArtifactStore({ rootDir: workspaceRoot }));
    const runner = createQecPortfolioBatchRunner({
      records: QEC_PORTFOLIO_PROBLEMS,
      register: ({ records }) => registerQecPortfolio({
        rootDir: workspaceRoot,
        records,
        publish: async ({ id, stageDir }) => {
          const { stdout } = await execFile("make", ["problem-publish", `STAGE=${relative(workspaceRoot, stageDir)}`, `ID=${id}`], { cwd: workspaceRoot });
          return JSON.parse(stdout);
        },
      }),
      verifyIndex: () => rebuildAndVerifyIndex(workspaceRoot),
      createManagers: async () => {
        const repository = await createLocalRepository(workspaceRoot);
        valuationManager = createValuationJobManager({
          rootDir: workspaceRoot,
          repository,
          researcher: createQecPortfolioValuationResearcher(),
          openAlex: createRetryingOpenAlexClient({ client: createOpenAlexClient({ apiKey }) }),
          store: valuationStore,
        });
        assessmentManager = createAssessmentJobManager({
          rootDir: workspaceRoot,
          repository,
          store: assessmentStore,
          valuationStore,
          resolveKnowledge: createKnowledgeResolver(workspaceRoot),
        });
        return { valuationManager, valuationStore, assessmentManager, assessmentStore };
      },
      verifyPortfolio: () => verifyQecPortfolio({ rootDir: workspaceRoot }),
    });
    return await runner.run();
  } catch (error) {
    return {
      status: "incomplete",
      phases: { execution: "failed" },
      problems: [],
      error: { code: error?.code ?? "QEC_PORTFOLIO_RUN_FAILED", message: error.message },
    };
  } finally {
    await assessmentManager?.shutdown?.();
    await valuationManager?.shutdown?.();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const summary = await runQecPortfolio({ rootDir: readArg("--root") });
  console.log(JSON.stringify(summary));
  if (summary.status !== "complete") process.exitCode = 1;
}
