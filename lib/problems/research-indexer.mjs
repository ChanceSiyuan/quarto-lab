import { readFile, readdir } from "node:fs/promises";
import { join, relative, resolve } from "node:path";

import {
  ATTEMPT_ID_PATTERN,
  validateResearchAttempt,
  validateResearchManifest,
} from "./research-schema.mjs";

function diagnostic(relativePath, field, message) {
  return { relativePath, field, message };
}

async function readJson(path, workspacePath) {
  const relativePath = relative(workspacePath, path);
  try {
    return { value: JSON.parse(await readFile(path, "utf8")), relativePath };
  } catch (error) {
    return {
      relativePath,
      error: diagnostic(
        relativePath,
        "manifest",
        error.code === "ENOENT" ? "Missing JSON file." : `Invalid JSON: ${error.message}`,
      ),
    };
  }
}

async function directoriesAt(path) {
  try {
    return await readdir(path, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

export async function buildResearchIndex({
  rootDir = process.cwd(),
  problemsDir = "problems",
} = {}) {
  const workspacePath = resolve(rootDir);
  const problemsPath = resolve(workspacePath, problemsDir);
  const diagnostics = [];
  const records = [];
  const entries = await directoriesAt(problemsPath);
  const problemDirectories = entries
    .filter((entry) => entry.isDirectory())
    .sort((left, right) => left.name.localeCompare(right.name));

  for (const entry of problemDirectories) {
    const problemPath = join(problemsPath, entry.name);
    const manifestPath = join(problemPath, "research.json");
    const manifestResult = await readJson(manifestPath, workspacePath);

    if (manifestResult.error?.message === "Missing JSON file.") continue;
    if (manifestResult.error) {
      diagnostics.push(manifestResult.error);
      continue;
    }

    const manifestValidation = validateResearchManifest(manifestResult.value, {
      relativePath: manifestResult.relativePath,
    });
    if (!manifestValidation.ok) {
      diagnostics.push(...manifestValidation.errors);
      continue;
    }

    const attemptsPath = join(problemPath, "attempts");
    const attemptEntries = (await directoriesAt(attemptsPath))
      .filter((attemptEntry) => attemptEntry.isDirectory() && ATTEMPT_ID_PATTERN.test(attemptEntry.name))
      .sort((left, right) => left.name.localeCompare(right.name));
    const attempts = [];
    const problemDiagnostics = [];

    for (const attemptEntry of attemptEntries) {
      const attemptPath = join(attemptsPath, attemptEntry.name, "attempt.json");
      const attemptResult = await readJson(attemptPath, workspacePath);
      if (attemptResult.error) {
        problemDiagnostics.push(attemptResult.error);
        continue;
      }
      const attemptValidation = validateResearchAttempt(attemptResult.value, {
        relativePath: attemptResult.relativePath,
      });
      if (!attemptValidation.ok) {
        problemDiagnostics.push(...attemptValidation.errors);
        continue;
      }
      attempts.push(attemptValidation.value);
    }

    if (problemDiagnostics.length > 0) {
      diagnostics.push(...problemDiagnostics);
      continue;
    }

    records.push({
      problemId: manifestValidation.value.problemId,
      manifest: manifestValidation.value,
      attempts,
      attemptCount: attempts.length,
    });
  }

  return {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    workspacePath,
    records,
    diagnostics,
  };
}
