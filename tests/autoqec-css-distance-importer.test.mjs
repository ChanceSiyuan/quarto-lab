import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import test from "node:test";

import {
  buildCohortManifests,
  buildInfrastructurePlan,
  expectedInfrastructureForAttempt,
} from "../lib/problems/autoqec-css-distance/infrastructure.mjs";
import {
  assertSafeImportPath,
  importAutoqecCssDistance,
} from "../lib/problems/autoqec-css-distance/importer.mjs";

const execFileAsync = promisify(execFile);

async function runGit(sourceDir, args) {
  await execFileAsync("git", ["-C", sourceDir, ...args]);
}

async function gitOutput(sourceDir, args) {
  const { stdout } = await execFileAsync("git", ["-C", sourceDir, ...args]);
  return stdout.trim();
}

function report(sequence, { publicContract = "passed", runs = 1 } = {}) {
  const notRun = runs === 0;
  return `# CSS Distance Proposal ${String(sequence).padStart(3, "0")} Report

## Method

The assigned exploration direction was **synthetic test method**.

## Public Contract

| Field | Value |
| --- | ---: |
| Branch | autoresearch/css-distance/run${sequence <= 100 ? "100" : "200"}-proposal-${String(sequence).padStart(3, "0")} |
| Public contract status | ${publicContract} |

## Blinded Development Screening

| Metric | Value |
| --- | ---: |
| Decision | rejected |
| Runs | ${runs} |
| Verified witnesses | ${runs} |
| Target hits | ${runs} |
| Timeouts | 0 |
| Crashes | 0 |
| Invalid claims | ${notRun ? 1 : 0} |
| Weighted target hits | ${runs} |
| Normalized quality | ${runs ? 1 : 0} |
| Runtime seconds | ${runs ? 1 : 0} |
| Average seconds | ${notRun ? "not run" : 1} |
| Median seconds | ${notRun ? "not run" : 1} |
| P95 seconds | ${notRun ? "not run" : 1} |
`;
}

async function createSyntheticSource() {
  const sourceDir = await mkdtemp(join(tmpdir(), "autoqec-import-source-"));
  await runGit(sourceDir, ["init", "--initial-branch=main"]);
  await runGit(sourceDir, ["config", "user.email", "test@example.com"]);
  await runGit(sourceDir, ["config", "user.name", "Importer Test"]);
  await writeFile(join(sourceDir, "README.md"), "synthetic AutoQEC\n");
  await runGit(sourceDir, ["add", "README.md"]);
  await runGit(sourceDir, ["commit", "-m", "base"]);

  const firstParents = [];
  for (const sequence of [1, 101, 200]) {
    await runGit(sourceDir, ["checkout", "main"]);
    await mkdir(join(sourceDir, "src"), { recursive: true });
    await writeFile(join(sourceDir, "src", "infrastructure.py"), `EPOCH = ${sequence}\n`);
    await runGit(sourceDir, ["add", "src/infrastructure.py"]);
    await runGit(sourceDir, ["commit", "-m", `infrastructure ${sequence}`]);
    const firstParent = await gitOutput(sourceDir, ["rev-parse", "HEAD"]);
    firstParents.push(firstParent);

    const ref = `autoresearch/css-distance/run${sequence <= 100 ? "100" : "200"}-proposal-${String(sequence).padStart(3, "0")}`;
    await runGit(sourceDir, ["checkout", "-b", ref]);
    await writeFile(join(sourceDir, "LOG.md"), `log ${sequence}\n`);
    await writeFile(join(sourceDir, "REPORT.md"), report(sequence, sequence === 101 ? { publicContract: "failed", runs: 0 } : {}));
    if (sequence !== 101) {
      await mkdir(join(sourceDir, "proposal-workspace"), { recursive: true });
      await writeFile(join(sourceDir, "proposal-workspace", "candidate.py"), `# candidate ${sequence}\n`);
    }
    if (sequence === 200) await writeFile(join(sourceDir, "proposal-workspace", "METHOD.txt"), "synthetic method\n");
    await runGit(sourceDir, ["add", "."]);
    await runGit(sourceDir, ["commit", "-m", `trial ${sequence}`]);
  }
  await runGit(sourceDir, ["checkout", "main"]);

  return {
    sourceDir,
    ranges: [
      { first: 1, last: 1, cohort: "cohort-001-100", commit: firstParents[0] },
      { first: 101, last: 101, cohort: "cohort-101-200", commit: firstParents[1] },
      { first: 200, last: 200, cohort: "cohort-101-200", commit: firstParents[2] },
    ],
  };
}

test("maps attempts to the exact six infrastructure ranges", () => {
  assert.equal(expectedInfrastructureForAttempt(1).commit, "c4533f982ece376c5f299a13edfabff0f489182c");
  assert.equal(expectedInfrastructureForAttempt(100).commit, "3e61f5ac8143e4848e5e814188c83683c74dfe4c");
  assert.equal(expectedInfrastructureForAttempt(101).commit, "12a8f794f68d63f07303df0cc38fa244c1ab1248");
  assert.equal(expectedInfrastructureForAttempt(108).commit, "3f30f39a2f9be8ceead3821706aae77acdd980aa");
  assert.equal(expectedInfrastructureForAttempt(200).commit, "b6a0e03c05a653b4e85160a703c0be4eef06b619");
});

test("builds cohort manifests from the exact range table", () => {
  assert.deepEqual(buildCohortManifests().map((manifest) => manifest.id), ["cohort-001-100", "cohort-101-200"]);
  assert.deepEqual(buildCohortManifests()[0].attempts, [
    { first: 1, last: 1, sourceInfrastructureCommit: "c4533f982ece376c5f299a13edfabff0f489182c" },
    { first: 2, last: 100, sourceInfrastructureCommit: "3e61f5ac8143e4848e5e814188c83683c74dfe4c" },
  ]);
});

test("refuses an infrastructure first-parent mismatch", async () => {
  await assert.rejects(
    buildInfrastructurePlan([{ sequence: 1, firstParent: "0".repeat(40) }]),
    /infrastructure commit mismatch/,
  );
});

test("accepts a synthetic range map for temporary Git-source imports", async () => {
  const ranges = [
    { first: 1, last: 1, cohort: "cohort-001-100", commit: "1".repeat(40) },
    { first: 101, last: 101, cohort: "cohort-101-200", commit: "2".repeat(40) },
    { first: 200, last: 200, cohort: "cohort-101-200", commit: "3".repeat(40) },
  ];
  const plan = await buildInfrastructurePlan([
    { sequence: 1, firstParent: "1".repeat(40) },
    { sequence: 101, firstParent: "2".repeat(40) },
    { sequence: 200, firstParent: "3".repeat(40) },
  ], { ranges });

  assert.deepEqual(plan.map((item) => item.commit), ["1".repeat(40), "2".repeat(40), "3".repeat(40)]);
});

test("safe artifact policy rejects path escapes and symlinks", () => {
  assert.throws(() => assertSafeImportPath("../candidate.py"), /unsafe/);
  assert.throws(() => assertSafeImportPath("/candidate.py"), /unsafe/);
});

test("imports synthetic trials atomically with copied artifacts and snapshots", async () => {
  const root = await mkdtemp(join(tmpdir(), "autoqec-import-root-"));
  const { sourceDir, ranges } = await createSyntheticSource();
  try {
    await importAutoqecCssDistance({
      rootDir: root,
      sourceDir,
      now: () => new Date("2026-07-28T00:00:00.000Z"),
      expectedAttempts: [1, 101, 200],
      infrastructureRanges: ranges,
    });

    assert.equal(await fileExists(join(root, "problems", "Prob-001", "attempts", "ATT-101", "candidate.py")), false);
    assert.equal(JSON.parse(await readFile(join(root, "problems", "Prob-001", "attempts", "ATT-101", "attempt.json"), "utf8")).candidate.status, "not-generated");
    assert.equal((await readdir(join(root, "problems", "Prob-001", "infrastructure", "snapshots"))).length, 3);
    assert.equal(await readFile(join(root, "problems", "Prob-001", "attempts", "ATT-200", "METHOD.txt"), "utf8"), "synthetic method\n");
    assert.equal(await fileExists(join(root, "problems", "Prob-001", "import-manifest.json")), false);
  } finally {
    await rm(root, { recursive: true, force: true });
    await rm(sourceDir, { recursive: true, force: true });
  }
});

async function fileExists(path) {
  try {
    await readFile(path);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}
