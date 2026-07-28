import { spawn } from "node:child_process";
import { copyFile, mkdir, readFile, rename, rm } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { validateStagedDraft } from "./draft-contract.mjs";
import { deriveNextProblemId, scanReservedProblemIds } from "./indexer.mjs";

export const DEFAULT_PUBLISH_FILE_OPS = { copyFile, mkdir, rename, rm };
const INDEX_SCRIPT = fileURLToPath(new URL("../../scripts/build-problem-index.mjs", import.meta.url));

export async function rebuildGeneratedProblemIndex(rootDir) {
  await new Promise((resolveBuild, rejectBuild) => {
    const child = spawn(
      process.execPath,
      [INDEX_SCRIPT, "--root", rootDir, "--reserve-id", "Prob-000"],
      { cwd: rootDir, stdio: "ignore" },
    );
    child.once("error", rejectBuild);
    child.once("exit", (code) => code === 0
      ? resolveBuild()
      : rejectBuild(new Error(`Problem index build exited with status ${code}.`)));
  });
  return JSON.parse(await readFile(join(rootDir, ".generated", "problem-index.json"), "utf8"));
}

export async function publishStagedDraft({
  rootDir = process.cwd(),
  stageDir,
  expectedId,
  fileOps = DEFAULT_PUBLISH_FILE_OPS,
  rebuildIndex = rebuildGeneratedProblemIndex,
}) {
  const rootPath = resolve(rootDir);
  const staged = await validateStagedDraft({ rootDir: rootPath, stageDir, expectedId });
  const reserved = await scanReservedProblemIds({ rootDir: rootPath, reservedIds: ["Prob-000"] });
  if (reserved.includes(expectedId)) {
    return {
      status: "collision",
      id: expectedId,
      nextProblemId: deriveNextProblemId(reserved.map((id) => ({ id }))),
    };
  }

  await fileOps.mkdir(join(rootPath, "problems"), { recursive: true });
  const target = join(rootPath, "problems", expectedId);
  const targetGeneration = join(target, "generation");
  const temporaryManifest = join(target, ".problem.json.tmp");
  let targetCreated = false;
  let manifestPublished = false;
  try {
    await fileOps.mkdir(target, { recursive: false });
    targetCreated = true;
    await fileOps.mkdir(targetGeneration, { recursive: false });
    await fileOps.copyFile(staged.files.markdown, join(target, "problem.md"));
    await fileOps.copyFile(staged.files.initialPrompt, join(targetGeneration, "initial-prompt.md"));
    await fileOps.copyFile(staged.files.transcript, join(targetGeneration, "transcript.md"));
    await fileOps.copyFile(staged.files.decision, join(targetGeneration, "decision.md"));
    await fileOps.copyFile(staged.files.manifest, temporaryManifest);
    await fileOps.rename(temporaryManifest, join(target, "problem.json"));
    manifestPublished = true;
  } catch (error) {
    if (error.code === "EEXIST" && !targetCreated) {
      const refreshed = await scanReservedProblemIds({ rootDir: rootPath, reservedIds: ["Prob-000"] });
      return {
        status: "collision",
        id: expectedId,
        nextProblemId: deriveNextProblemId(refreshed.map((id) => ({ id }))),
      };
    }
    if (targetCreated && !manifestPublished) await fileOps.rm(target, { recursive: true, force: true });
    throw error;
  }

  const problemPath = relative(rootPath, target);
  try {
    const index = await rebuildIndex(rootPath);
    if (!index.problems.some((problem) => problem.id === expectedId && problem.status === "draft")) {
      throw new Error(`Rebuilt index does not contain ${expectedId} as a draft.`);
    }
    return { status: "published", id: expectedId, problemPath, indexPath: ".generated/problem-index.json" };
  } catch (error) {
    return { status: "published-index-stale", id: expectedId, problemPath, error: error.message };
  }
}
