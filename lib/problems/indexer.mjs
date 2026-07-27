import { readFile, readdir } from "node:fs/promises";
import { join, relative, resolve } from "node:path";

import {
  ACTIVE_WITH_GATE_STATUSES,
  PUBLISHED_STATUSES,
  SOLVED_OR_LATER_STATUSES,
  validateProblemManifest,
} from "./schema.mjs";

const TARGET_PROBLEM_COUNT = 5;

export function deriveNextProblemId(problems) {
  const max = problems.reduce((current, problem) => {
    const match = /^QMB-(\d{3})$/.exec(problem.id);
    return match ? Math.max(current, Number(match[1])) : current;
  }, 0);
  return `QMB-${String(max + 1).padStart(3, "0")}`;
}

function diagnostic(relativePath, field, message) {
  return { relativePath, field, message };
}

async function readProblemMarkdown(path) {
  try {
    return await readFile(path, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return undefined;
    throw error;
  }
}

function summarize(problems) {
  return {
    total: problems.length,
    accepted: problems.filter((problem) => ACTIVE_WITH_GATE_STATUSES.includes(problem.status)).length,
    solved: problems.filter((problem) => SOLVED_OR_LATER_STATUSES.includes(problem.status)).length,
    published: problems.filter((problem) => PUBLISHED_STATUSES.includes(problem.status)).length,
    rejected: problems.filter((problem) => problem.status === "rejected").length,
    archived: problems.filter((problem) => problem.status === "archived").length,
    target: TARGET_PROBLEM_COUNT,
  };
}

export async function buildProblemIndex({ rootDir = process.cwd() } = {}) {
  const workspacePath = resolve(rootDir);
  const problemsPath = join(workspacePath, "problems");
  const diagnostics = [];
  const problems = [];
  const seenIds = new Set();
  let entries = [];

  try {
    entries = await readdir(problemsPath, { withFileTypes: true });
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }

  const directories = entries
    .filter((entry) => entry.isDirectory())
    .sort((left, right) => left.name.localeCompare(right.name));

  for (const entry of directories) {
    const problemPath = join(problemsPath, entry.name);
    const manifestPath = join(problemPath, "problem.json");
    const relativePath = relative(workspacePath, manifestPath);
    let manifest;

    try {
      manifest = JSON.parse(await readFile(manifestPath, "utf8"));
    } catch (error) {
      const message = error.code === "ENOENT"
        ? "Missing problem.json."
        : `Invalid JSON: ${error.message}`;
      diagnostics.push(diagnostic(relativePath, "manifest", message));
      continue;
    }

    const problemMdText = await readProblemMarkdown(join(problemPath, "problem.md"));
    const validation = validateProblemManifest(manifest, { relativePath, problemMdText });
    if (!validation.ok) {
      diagnostics.push(...validation.errors);
      continue;
    }

    if (seenIds.has(manifest.id)) {
      diagnostics.push(diagnostic(relativePath, "id", `Duplicate problem id: ${manifest.id}.`));
      continue;
    }

    if (entry.name !== manifest.id) {
      diagnostics.push(diagnostic(
        relativePath,
        "id",
        `Directory name ${entry.name} does not match manifest id ${manifest.id}.`,
      ));
      continue;
    }

    seenIds.add(manifest.id);
    problems.push(manifest);
  }

  problems.sort((left, right) => (
    Date.parse(right.updatedAt) - Date.parse(left.updatedAt)
    || left.id.localeCompare(right.id)
  ));

  return {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    workspacePath,
    nextProblemId: deriveNextProblemId(problems),
    problems,
    summary: summarize(problems),
    diagnostics,
  };
}
