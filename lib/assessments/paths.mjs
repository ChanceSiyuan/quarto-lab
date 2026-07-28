import { randomBytes as nodeRandomBytes } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { join, resolve } from "node:path";

import { PROBLEM_ID_PATTERN } from "../problems/schema.mjs";

export const RUN_ID_PATTERN = /^\d{8}T\d{6}Z-[a-f0-9]{6}$/;

export function createRunId(now = new Date(), randomBytesFn = nodeRandomBytes) {
  const timestamp = now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  return `${timestamp}-${randomBytesFn(3).toString("hex")}`;
}

export async function assertContained(parent, child) {
  const parentResolved = resolve(parent);
  const childResolved = resolve(child);
  if (childResolved !== parentResolved && !childResolved.startsWith(`${parentResolved}/`)) {
    throw new Error(`Path escapes expected root: ${child}`);
  }
  return childResolved;
}

export async function resolveProblemDir(rootDir, problemId) {
  if (!PROBLEM_ID_PATTERN.test(problemId)) throw new Error(`Invalid problem ID: ${problemId}`);
  const problemsRoot = resolve(rootDir, "problems");
  await mkdir(problemsRoot, { recursive: true });
  return assertContained(problemsRoot, join(problemsRoot, problemId));
}

export async function resolveRunDir(rootDir, problemId, runId) {
  if (!RUN_ID_PATTERN.test(runId)) throw new Error(`Invalid run ID: ${runId}`);
  const problemDir = await resolveProblemDir(rootDir, problemId);
  return assertContained(problemDir, join(problemDir, "assessments", runId));
}
