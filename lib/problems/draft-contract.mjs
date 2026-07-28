import { lstat, readFile, readdir, realpath } from "node:fs/promises";
import { basename, isAbsolute, join, relative, resolve } from "node:path";

import { markdownHasHeading, validateProblemManifest } from "./schema.mjs";

export const DRAFT_PROBLEM_MD_HEADINGS = [
  "Candidate Question",
  "Motivation and Context",
  "Discussion Summary",
  "Evidence Mentioned",
  "Open Qualification Questions",
];

export class DraftStageError extends Error {
  constructor(errors) {
    super(`Invalid staged problem (${errors.length} error${errors.length === 1 ? "" : "s"}).`);
    this.name = "DraftStageError";
    this.code = "INVALID_STAGE";
    this.errors = errors;
  }
}

function isInside(parent, child) {
  const path = relative(parent, child);
  return path === "" || (!path.startsWith("..") && !isAbsolute(path));
}

async function exactEntries(path, expected, label, errors) {
  try {
    const entries = (await readdir(path, { withFileTypes: true }))
      .map((entry) => entry.name)
      .sort();
    const wanted = [...expected].sort();
    if (entries.length !== wanted.length || entries.some((entry, index) => entry !== wanted[index])) {
      errors.push(`${label} must contain exactly: ${wanted.join(", ")}.`);
      return false;
    }
    return true;
  } catch (error) {
    errors.push(`${label} cannot be read: ${error.message}`);
    return false;
  }
}

async function readRequiredText(path, label, errors) {
  try {
    return await readFile(path, "utf8");
  } catch (error) {
    errors.push(`${label} cannot be read: ${error.message}`);
    return null;
  }
}

export async function validateStagedDraft({ rootDir, stageDir, expectedId }) {
  const errors = [];
  let rootPath;
  let stagingRoot;
  let stagePath;
  try {
    rootPath = await realpath(resolve(rootDir));
    stagingRoot = await realpath(join(rootPath, ".generated", "problem-staging"));
    stagePath = await realpath(resolve(rootPath, stageDir));
  } catch (error) {
    throw new DraftStageError([`Staging path cannot be resolved: ${error.message}`]);
  }

  if (!isInside(rootPath, stagingRoot) || !isInside(stagingRoot, stagePath)) {
    errors.push("STAGE must resolve inside .generated/problem-staging/.");
  }
  if (basename(stagePath) !== expectedId) errors.push("Staged directory name must match ID.");

  await exactEntries(stagePath, ["generation", "problem.json", "problem.md"], "stage", errors);
  await exactEntries(
    join(stagePath, "generation"),
    ["decision.md", "initial-prompt.md", "transcript.md"],
    "generation",
    errors,
  );

  const files = {
    manifest: join(stagePath, "problem.json"),
    markdown: join(stagePath, "problem.md"),
    initialPrompt: join(stagePath, "generation", "initial-prompt.md"),
    transcript: join(stagePath, "generation", "transcript.md"),
    decision: join(stagePath, "generation", "decision.md"),
  };
  try {
    const generationStats = await lstat(join(stagePath, "generation"));
    if (generationStats.isSymbolicLink() || !generationStats.isDirectory()) {
      errors.push("generation must be a real directory.");
    }
  } catch (error) {
    errors.push(`generation cannot be read: ${error.message}`);
  }
  for (const [label, path] of Object.entries(files)) {
    try {
      const stats = await lstat(path);
      if (stats.isSymbolicLink() || !stats.isFile()) errors.push(`${label} must be a regular file.`);
    } catch (error) {
      errors.push(`${label} cannot be read: ${error.message}`);
    }
  }

  const problemMdText = await readRequiredText(files.markdown, "problem.md", errors);
  const manifestText = await readRequiredText(files.manifest, "problem.json", errors);
  let manifest = null;
  if (manifestText !== null) {
    try {
      manifest = JSON.parse(manifestText);
    } catch (error) {
      errors.push(`problem.json is invalid JSON: ${error.message}`);
    }
  }
  if (manifest !== null && problemMdText !== null) {
    const schema = validateProblemManifest(manifest, {
      relativePath: `problems/${expectedId}/problem.json`,
      problemMdText,
    });
    if (!schema.ok) errors.push(...schema.errors.map((error) => `${error.field}: ${error.message}`));
    if (manifest.id !== expectedId) errors.push("Manifest ID must match requested ID.");
    if (manifest.status !== "draft") errors.push("Status must be draft.");
    if (Object.hasOwn(manifest, "rejection")) errors.push("Draft must not contain rejection.");
    if (!["missing", "specified"].includes(manifest.gate?.readiness)) {
      errors.push("Draft gate readiness must be missing or specified.");
    }
    const timestamps = [manifest.createdAt, manifest.updatedAt, manifest.lastActivity?.at];
    if (new Set(timestamps).size !== 1) errors.push("Draft registration timestamps must match.");
  }
  if (problemMdText !== null) {
    for (const heading of DRAFT_PROBLEM_MD_HEADINGS) {
      if (!markdownHasHeading(problemMdText, heading)) errors.push(`problem.md is missing: ${heading}.`);
    }
  }
  for (const [label, path] of [
    ["initial-prompt.md", files.initialPrompt],
    ["transcript.md", files.transcript],
    ["decision.md", files.decision],
  ]) {
    const content = await readRequiredText(path, label, errors);
    if (content !== null && !content.trim()) errors.push(`${label} must be non-empty.`);
  }
  if (errors.length) throw new DraftStageError(errors);
  return { stagePath, manifest, files };
}
