import { createHash } from "node:crypto";
import { access, mkdir, mkdtemp, rename, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  AUTOQEC_INFRASTRUCTURE_RANGES,
  RESEARCH_DISCLAIMER,
  validateResearchAttempt,
} from "../research-schema.mjs";
import { buildInfrastructurePlan, buildCohortManifests, expectedInfrastructureForAttempt } from "./infrastructure.mjs";
import {
  assertReadableGitRepository,
  getCommitAndFirstParent,
  git,
  readGitBlob,
} from "./git-source.mjs";
import { buildTrialRef, parseAutoqecReport } from "./reports.mjs";

const TRIAL_ARTIFACT_SOURCES = [
  { sourcePath: "LOG.md", targetPath: "LOG.md", required: true },
  { sourcePath: "REPORT.md", targetPath: "REPORT.md", required: true },
  { sourcePath: "proposal-workspace/candidate.py", targetPath: "candidate.py", required: false },
  { sourcePath: "proposal-workspace/METHOD.txt", targetPath: "METHOD.txt", required: false },
  { sourcePath: "METHOD.txt", targetPath: "METHOD.txt", required: false },
];

const EXCLUDED_PATH_CLASSES = [
  "blind-evaluation-private",
  "selection-secrets",
  "salts",
  "answer-keys",
  "case-level-results",
  "credentials",
  "git-metadata",
];
const PRIVATE_PATH_SEGMENT = /^(?:.*private.*|blind(?:[-_].*)?|.*(?:secret|salt|credential|answer[-_]?key|case[-_]?result).*)$/i;

export function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

export function assertSafeImportPath(path) {
  if (!/^(?!\/)(?!\.)(?!.*(?:^|\/)\.\.(?:\/|$))(?!.*\/\/)[A-Za-z0-9][A-Za-z0-9._@+-]*(?:\/[A-Za-z0-9][A-Za-z0-9._@+-]*)*$/.test(path)) {
    throw new Error(`unsafe import path: ${path}`);
  }
  if (path.includes(".git/") || path === ".git") throw new Error(`unsafe Git metadata path: ${path}`);
  return path;
}

export function normalizeAttempt({
  sequence,
  parsedReport,
  sourceBranch,
  sourceCommit,
  sourceInfrastructureCommit,
  artifacts,
  infrastructureRanges = AUTOQEC_INFRASTRUCTURE_RANGES,
}) {
  const id = `ATT-${String(sequence).padStart(3, "0")}`;
  const expected = expectedInfrastructureForAttempt(sequence, infrastructureRanges);
  const hasCandidate = artifacts.some((artifact) => artifact.path === "candidate.py");
  return {
    schemaVersion: 1,
    problemId: "Prob-001",
    id,
    sequence,
    cohort: expected.cohort,
    title: `CSS Distance Proposal ${String(sequence).padStart(3, "0")}`,
    summary: "Imported AutoQEC trial record.",
    stage: "development",
    decision: parsedReport.metrics.decision,
    gate: {
      containment: "passed",
      publicContract: parsedReport.publicContract,
      development: parsedReport.metrics.decision === "accepted" ? "passed" : "failed",
    },
    method: {
      description: parsedReport.methodDescription,
      learnedFrom: null,
    },
    metrics: parsedReport.metrics,
    provenance: {
      sourceRepository: "AutoQEC",
      sourceBranch,
      sourceCommit,
      sourceInfrastructureCommit,
      sourceCohort: expected.cohort,
      model: null,
    },
    candidate: hasCandidate ? { status: "present", path: "candidate.py" } : { status: "not-generated" },
    artifacts,
  };
}

export async function importAutoqecCssDistance({
  rootDir,
  sourceDir,
  now = () => new Date(),
  expectedAttempts = Array.from({ length: 200 }, (_, index) => index + 1),
  infrastructureRanges = AUTOQEC_INFRASTRUCTURE_RANGES,
}) {
  const destination = join(rootDir, "problems", "Prob-001");
  if (await exists(destination)) throw new Error(`Refusing to overwrite existing imported problem: ${destination}`);
  await assertReadableGitRepository(sourceDir);

  const tempRoot = await mkdtemp(join(tmpdir(), "research-loop-autoqec-import-"));
  const stagedProblem = join(tempRoot, "Prob-001");
  try {
    await mkdir(stagedProblem, { recursive: true });
    const trials = [];
    for (const sequence of expectedAttempts) {
      const ref = buildTrialRef(sequence);
      const { commit, firstParent } = await getCommitAndFirstParent(sourceDir, ref);
      trials.push({ sequence, ref, commit, firstParent });
    }
    const infrastructurePlan = await buildInfrastructurePlan(trials, { ranges: infrastructureRanges });

    await writeProblemFiles(stagedProblem, now());
    await writeCohorts(stagedProblem, infrastructureRanges);
    for (const trial of infrastructurePlan) {
      await importTrial(stagedProblem, sourceDir, trial, infrastructureRanges);
    }
    await freezeSnapshots(stagedProblem, sourceDir, infrastructurePlan);

    await mkdir(join(rootDir, "problems"), { recursive: true });
    if (await exists(destination)) throw new Error(`Refusing to overwrite existing imported problem: ${destination}`);
    await rename(stagedProblem, destination);
    return destination;
  } catch (error) {
    await rm(tempRoot, { recursive: true, force: true });
    throw error;
  } finally {
    await rm(tempRoot, { recursive: true, force: true });
  }
}

async function importTrial(stagedProblem, sourceDir, trial, infrastructureRanges) {
  const tree = await readTreeEntries(sourceDir, trial.ref);
  const attemptDir = join(stagedProblem, "attempts", `ATT-${String(trial.sequence).padStart(3, "0")}`);
  await mkdir(attemptDir, { recursive: true });
  const artifacts = [];
  for (const artifactSource of TRIAL_ARTIFACT_SOURCES) {
    if (artifacts.some((artifact) => artifact.path === artifactSource.targetPath)) continue;
    const entry = tree.get(artifactSource.sourcePath);
    if (!entry) {
      if (artifactSource.required) throw new Error(`Required trial artifact is missing from ${trial.ref}: ${artifactSource.sourcePath}`);
      continue;
    }
    requireRegularBlob(entry, artifactSource.sourcePath);
    const contents = await readGitBlob(sourceDir, trial.ref, artifactSource.sourcePath);
    assertSafeImportPath(artifactSource.targetPath);
    await writeFile(join(attemptDir, artifactSource.targetPath), contents, { flag: "wx" });
    artifacts.push({
      path: artifactSource.targetPath,
      sha256: sha256(contents),
      sourcePath: artifactSource.sourcePath,
    });
  }

  const reportArtifact = artifacts.find((artifact) => artifact.path === "REPORT.md");
  const report = await readGitBlob(sourceDir, trial.ref, reportArtifact.sourcePath);
  const parsedReport = parseAutoqecReport(report.toString("utf8"), { proposalNumber: trial.sequence });
  const attempt = normalizeAttempt({
    sequence: trial.sequence,
    parsedReport,
    sourceBranch: trial.ref,
    sourceCommit: trial.commit,
    sourceInfrastructureCommit: trial.firstParent,
    artifacts,
    infrastructureRanges,
  });
  validateGeneratedAttempt(attempt, infrastructureRanges);
  await writeJson(join(attemptDir, "attempt.json"), attempt);
}

async function writeProblemFiles(stagedProblem, createdAt) {
  const timestamp = createdAt.toISOString();
  await writeJson(join(stagedProblem, "problem.json"), {
    schemaVersion: 1,
    id: "Prob-001",
    title: "AutoQEC CSS Distance Campaign",
    summary: "Imported AutoQEC CSS-distance experimental audit record.",
    status: "solved",
    gate: { type: "repository-import", readiness: "passed" },
    provenance: { sourceCount: 1 },
    lastActivity: { summary: "Imported AutoQEC trial record.", at: timestamp },
    createdAt: timestamp,
    updatedAt: timestamp,
  });
  await writeFile(join(stagedProblem, "problem.md"), `# Background and Gap\n\nImported experimental history, not reviewed knowledge.\n\n# Research Objective\n\nPreserve the CSS-distance campaign audit record.\n\n# Publication Threshold\n\nNo publication decision is implied by this import.\n\n# Executable Gate\n\nRepository import integrity is recorded as passed.\n\n# Novelty Evidence\n\nThe source record is preserved without treating it as trusted knowledge.\n\n# Provenance\n\nImported from AutoQEC Git objects.\n\n# Fresh Evaluation Plan\n\nAny new evaluation must be performed separately.\n`);
  await writeJson(join(stagedProblem, "research.json"), {
    schemaVersion: 1,
    kind: "imported-research-record",
    problemId: "Prob-001",
    attemptCount: 200,
    attemptIdRange: ["ATT-001", "ATT-200"],
    disclaimer: RESEARCH_DISCLAIMER,
    cohorts: [
      { id: "cohort-001-100", first: 1, last: 100 },
      { id: "cohort-101-200", first: 101, last: 200 },
    ],
  });
  const generationDir = join(stagedProblem, "generation");
  await mkdir(generationDir, { recursive: true });
  await writeFile(join(generationDir, "initial-prompt.md"), "Imported from existing AutoQEC experiment history.\n");
  await writeFile(join(generationDir, "transcript.md"), "No Research Loop execution transcript; this is a source-record import.\n");
  await writeFile(join(generationDir, "decision.md"), "Import preserves experimental provenance and does not make a scientific decision.\n");
}

async function writeCohorts(stagedProblem, ranges) {
  const cohortDir = join(stagedProblem, "infrastructure", "cohorts");
  await mkdir(cohortDir, { recursive: true });
  for (const manifest of buildCohortManifests(ranges)) {
    await writeJson(join(cohortDir, `${manifest.id}.json`), manifest);
  }
}

async function freezeSnapshots(stagedProblem, sourceDir, plan) {
  const snapshots = new Map();
  for (const item of plan) if (!snapshots.has(item.commit)) snapshots.set(item.commit, item.range);
  for (const [commit, range] of snapshots) {
    const snapshotDir = join(stagedProblem, "infrastructure", "snapshots", commit);
    const sourceRoot = join(snapshotDir, "source");
    const entries = await readTreeEntries(sourceDir, commit);
    const files = [];
    for (const entry of [...entries.values()].sort((left, right) => left.path.localeCompare(right.path))) {
      assertSafeImportPath(entry.path);
      if (isExcludedInfrastructurePath(entry.path)) continue;
      requireRegularBlob(entry, entry.path);
      const contents = await readGitBlob(sourceDir, commit, entry.path);
      await mkdir(join(sourceRoot, ...entry.path.split("/").slice(0, -1)), { recursive: true });
      await writeFile(join(sourceRoot, entry.path), contents, { flag: "wx" });
      files.push({
        path: entry.path,
        sha256: sha256(contents),
        size: contents.length,
        executable: entry.mode === "100755",
      });
    }
    if (files.length === 0) throw new Error(`Infrastructure snapshot ${commit} has no importable source files`);
    const entryPoints = files.filter((file) => file.path.endsWith(".py")).map((file) => file.path);
    await writeJson(join(snapshotDir, "source-manifest.json"), {
      schemaVersion: 1,
      kind: "autoqec-css-distance-source-snapshot",
      problemId: "Prob-001",
      sourceRepository: "AutoQEC",
      sourceCommit: commit,
      attemptRanges: [{ first: range.first, last: range.last }],
      entryPoints: entryPoints.length > 0 ? entryPoints : [files[0].path],
      excludedPathClasses: EXCLUDED_PATH_CLASSES,
      files,
      blindDatasetReproducible: false,
    });
  }
}

function validateGeneratedAttempt(attempt, ranges) {
  if (ranges !== AUTOQEC_INFRASTRUCTURE_RANGES) return;
  const validation = validateResearchAttempt(attempt);
  if (!validation.ok) {
    throw new Error(`Generated ${attempt.id} is invalid: ${validation.errors.map((error) => `${error.field}: ${error.message}`).join("; ")}`);
  }
}

function isExcludedInfrastructurePath(path) {
  return path.split("/").some((segment) => PRIVATE_PATH_SEGMENT.test(segment));
}

function requireRegularBlob(entry, path) {
  if (entry.type !== "blob" || !["100644", "100755"].includes(entry.mode)) {
    throw new Error(`unsafe non-regular or symlink Git entry: ${path}`);
  }
}

async function readTreeEntries(sourceDir, ref) {
  const output = await git(sourceDir, ["ls-tree", "-r", "-z", ref], { encoding: "buffer" });
  const entries = new Map();
  for (const record of output.toString("utf8").split("\0")) {
    if (!record) continue;
    const match = record.match(/^(\d+) (\w+) ([0-9a-f]{40})\t(.+)$/);
    if (!match) throw new Error(`Unable to parse Git tree entry for ${ref}`);
    const [, mode, type, , path] = match;
    assertSafeImportPath(path);
    entries.set(path, { mode, type, path });
  }
  return entries;
}

async function writeJson(path, value) {
  await mkdir(join(path, ".."), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
}

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}
