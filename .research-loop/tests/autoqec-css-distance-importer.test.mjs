import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, mkdir, readFile, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import test from "node:test";

import {
  buildCohortManifests,
  buildInfrastructurePlan,
  expectedInfrastructureForAttempt,
} from "../../src/lib/problems/autoqec-css-distance/infrastructure.mjs";
import {
  assertSafeImportPath,
  importAutoqecCssDistance,
  sha256,
  verifyStagedImportTree,
} from "../../src/lib/problems/autoqec-css-distance/importer.mjs";

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

async function createSyntheticSource({
  invalidPublicContract = false,
  trialArtifactSymlink = false,
  infrastructureSymlink = false,
  infrastructureSubmodule = false,
} = {}) {
  const sourceDir = await mkdtemp(join(tmpdir(), "autoqec-import-source-"));
  await runGit(sourceDir, ["init", "--initial-branch=main"]);
  await runGit(sourceDir, ["config", "user.email", "test@example.com"]);
  await runGit(sourceDir, ["config", "user.name", "Importer Test"]);
  await writeFile(join(sourceDir, "README.md"), "synthetic AutoQEC\n");
  await writeFile(join(sourceDir, ".gitignore"), "scratch/\n");
  await runGit(sourceDir, ["add", "README.md", ".gitignore"]);
  await runGit(sourceDir, ["commit", "-m", "base"]);

  const firstParents = [];
  const trialCommits = [];
  for (const sequence of [1, 101, 200]) {
    await runGit(sourceDir, ["checkout", "main"]);
    await rm(join(sourceDir, "src"), { recursive: true, force: true });
    await rm(join(sourceDir, "containers"), { recursive: true, force: true });
    await rm(join(sourceDir, "zoo"), { recursive: true, force: true });
    await rm(join(sourceDir, "pyproject.toml"), { force: true });
    await mkdir(join(sourceDir, "src", "autoqec_search"), { recursive: true });
    await writeFile(join(sourceDir, "src", "autoqec_search", "__init__.py"), "");
    await writeFile(join(sourceDir, "src", "autoqec_search", "css_distance_autoresearch.py"), [
      "from autoqec_search.css_distance_container import DockerImage",
      "from autoqec_search.css_distance_eval import DEFAULT_TIMEOUT_SECONDS",
      "",
      `EPOCH = ${sequence}`,
      "",
    ].join("\n"));
    await writeFile(join(sourceDir, "src", "autoqec_search", "css_distance_container.py"), "class DockerImage:\n    pass\n");
    await writeFile(join(sourceDir, "src", "autoqec_search", "css_distance_eval.py"), "DEFAULT_TIMEOUT_SECONDS = 300\n");
    await writeFile(join(sourceDir, "src", "autoqec_search", "quantum_tanner_catalog.py"), "UNRELATED = True\n");
    await mkdir(join(sourceDir, "containers", "css-distance-autoresearch"), { recursive: true });
    await writeFile(join(sourceDir, "containers", "css-distance-autoresearch", "candidate-entrypoint.py"), "print('entry')\n");
    await writeFile(join(sourceDir, "containers", "css-distance-autoresearch", "evaluator.Dockerfile"), "FROM python:3.11\n");
    await writeFile(join(sourceDir, "containers", "css-distance-autoresearch", "proposal.Dockerfile"), "FROM python:3.11\n");
    await writeFile(join(sourceDir, "containers", "css-distance-autoresearch", "requirements.txt"), "numpy\n");
    await writeFile(join(sourceDir, "pyproject.toml"), "[project]\nname = \"synthetic-autoqec\"\n");
    await mkdir(join(sourceDir, "zoo", "external", "eczoo", "views", "site"), { recursive: true });
    await writeFile(join(sourceDir, "zoo", "external", "eczoo", "views", "site", "index.html"), "<!doctype html>\n");
    if (infrastructureSymlink && sequence === 1) {
      await rm(join(sourceDir, "src", "autoqec_search", "css_distance_container.py"));
      await symlink("css_distance_eval.py", join(sourceDir, "src", "autoqec_search", "css_distance_container.py"));
    }
    await runGit(sourceDir, ["add", "src", "containers", "pyproject.toml", "zoo"]);
    if (infrastructureSubmodule && sequence === 1) {
      const gitlinkCommit = await gitOutput(sourceDir, ["rev-parse", "HEAD"]);
      await runGit(sourceDir, ["update-index", "--add", "--cacheinfo", `160000,${gitlinkCommit},src/autoqec_search/css_distance_container.py`]);
    }
    await runGit(sourceDir, ["commit", "-m", `infrastructure ${sequence}`]);
    const firstParent = await gitOutput(sourceDir, ["rev-parse", "HEAD"]);
    firstParents.push(firstParent);

    const ref = `autoresearch/css-distance/run${sequence <= 100 ? "100" : "200"}-proposal-${String(sequence).padStart(3, "0")}`;
    await runGit(sourceDir, ["checkout", "-b", ref]);
    await writeFile(join(sourceDir, "LOG.md"), `log ${sequence}\n`);
    await writeFile(join(sourceDir, "REPORT.md"), report(sequence, sequence === 101
      ? { publicContract: invalidPublicContract ? "unknown" : "failed", runs: 0 }
      : {}));
    if (sequence !== 101) {
      await mkdir(join(sourceDir, "proposal-workspace"), { recursive: true });
      if (trialArtifactSymlink && sequence === 1) {
        await symlink("../LOG.md", join(sourceDir, "proposal-workspace", "candidate.py"));
      } else {
        await writeFile(join(sourceDir, "proposal-workspace", "candidate.py"), `# candidate ${sequence}\n`);
      }
    }
    if (sequence === 200) await writeFile(join(sourceDir, "proposal-workspace", "METHOD.txt"), "synthetic method\n");
    await runGit(sourceDir, ["add", "."]);
    await runGit(sourceDir, ["commit", "-m", `trial ${sequence}`]);
    trialCommits.push(await gitOutput(sourceDir, ["rev-parse", "HEAD"]));
  }
  await runGit(sourceDir, ["checkout", "main"]);

  return {
    sourceDir,
    firstParents,
    trialCommits,
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

test("safe artifact policy accepts Python package paths and rejects unsafe paths", () => {
  assert.equal(assertSafeImportPath("src/autoqec_search/__init__.py"), "src/autoqec_search/__init__.py");
  assert.throws(() => assertSafeImportPath("../candidate.py"), /unsafe/);
  assert.throws(() => assertSafeImportPath("/candidate.py"), /unsafe/);
  assert.throws(() => assertSafeImportPath("src/.cache/config"), /unsafe/);
  assert.throws(() => assertSafeImportPath("src/.git/config"), /unsafe/);
});

test("imports synthetic trials atomically with copied artifacts and snapshots", async () => {
  const root = await mkdtemp(join(tmpdir(), "autoqec-import-root-"));
  const { sourceDir, ranges, firstParents, trialCommits } = await createSyntheticSource();
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
    assert.equal(await fileExists(join(root, "problems", "Prob-001", "import-manifest.json")), true);
    assert.equal(await fileExists(join(root, "problems", "Prob-001", "infrastructure", "snapshots", firstParents[0], "source", ".gitignore")), false);
    const firstSnapshotSource = join(root, "problems", "Prob-001", "infrastructure", "snapshots", firstParents[0], "source");
    assert.equal(await fileExists(join(firstSnapshotSource, "src", "autoqec_search", "css_distance_autoresearch.py")), true);
    assert.equal(await fileExists(join(firstSnapshotSource, "src", "autoqec_search", "css_distance_container.py")), true);
    assert.equal(await fileExists(join(firstSnapshotSource, "src", "autoqec_search", "quantum_tanner_catalog.py")), false);
    assert.equal(await fileExists(join(firstSnapshotSource, "zoo", "external", "eczoo", "views", "site", "index.html")), false);
    const snapshotManifest = JSON.parse(await readFile(join(root, "problems", "Prob-001", "infrastructure", "snapshots", firstParents[0], "source-manifest.json"), "utf8"));
    assert.deepEqual(snapshotManifest.entryPoints, [
      "containers/css-distance-autoresearch/candidate-entrypoint.py",
      "src/autoqec_search/css_distance_autoresearch.py",
    ]);
    const provenance = JSON.parse(await readFile(join(root, "problems", "Prob-001", "attempts", "ATT-001", "attempt.json"), "utf8")).provenance;
    assert.equal(provenance.sourceCommit, trialCommits[0]);
    assert.equal(provenance.sourceInfrastructureCommit, firstParents[0]);
    assert.notEqual(provenance.sourceCommit, provenance.sourceInfrastructureCommit);
  } finally {
    await rm(root, { recursive: true, force: true });
    await rm(sourceDir, { recursive: true, force: true });
  }
});

test("stages a problems/Prob-001 tree before pre-rename verification", async () => {
  const root = await mkdtemp(join(tmpdir(), "autoqec-import-root-"));
  const { sourceDir, ranges } = await createSyntheticSource();
  let verificationRan = false;
  try {
    await importAutoqecCssDistance({
      rootDir: root,
      sourceDir,
      expectedAttempts: [1, 101, 200],
      infrastructureRanges: ranges,
      verifyStagedTree: async ({ rootDir }) => {
        verificationRan = true;
        assert.equal(await fileExists(join(rootDir, "problems", "Prob-001", "import-manifest.json")), true);
        assert.equal(await fileExists(join(root, "problems", "Prob-001")), false);
        return { ok: true };
      },
    });

    assert.equal(verificationRan, true);
    assert.equal(await fileExists(join(root, "problems", "Prob-001", "import-manifest.json")), true);
  } finally {
    await rm(root, { recursive: true, force: true });
    await rm(sourceDir, { recursive: true, force: true });
  }
});

test("canonical staged verification selects the default offline verifier", async () => {
  const root = await mkdtemp(join(tmpdir(), "autoqec-import-stage-"));
  const problem = join(root, "problems", "Prob-001");
  const log = Buffer.from("log\n");
  let injectedVerifierRan = false;
  try {
    await mkdir(join(problem, "attempts", "ATT-001"), { recursive: true });
    await writeFile(join(problem, "attempts", "ATT-001", "LOG.md"), log);
    await writeFile(join(problem, "import-manifest.json"), JSON.stringify({
      schemaVersion: 1,
      kind: "autoqec-css-distance-import",
      problemId: "Prob-001",
      sourceRepository: "AutoQEC",
      importedAt: "2026-07-28T00:00:00.000Z",
      attempts: 1,
      files: [{
        path: "attempts/ATT-001/LOG.md",
        sourcePath: "LOG.md",
        sha256: sha256(log),
        size: log.byteLength,
        generated: false,
      }],
    }));

    const result = await verifyStagedImportTree({
      rootDir: root,
      expectedAttempts: Array.from({ length: 200 }, (_, index) => index + 1),
      verifyStagedTree: async () => {
        injectedVerifierRan = true;
        return { ok: false, errors: [] };
      },
    });

    assert.equal(result.ok, true);
    assert.equal(injectedVerifierRan, false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("validates generated attempts even with injected infrastructure ranges", async () => {
  const root = await mkdtemp(join(tmpdir(), "autoqec-import-root-"));
  const { sourceDir, ranges } = await createSyntheticSource({ invalidPublicContract: true });
  try {
    await assert.rejects(importAutoqecCssDistance({
      rootDir: root,
      sourceDir,
      expectedAttempts: [1, 101, 200],
      infrastructureRanges: ranges,
    }), /Generated ATT-101 is invalid: gate\.publicContract/);
    assert.equal(await fileExists(join(root, "problems", "Prob-001")), false);
  } finally {
    await rm(root, { recursive: true, force: true });
    await rm(sourceDir, { recursive: true, force: true });
  }
});

test("rejects Git symlink trial artifacts without installing a destination", async () => {
  const root = await mkdtemp(join(tmpdir(), "autoqec-import-root-"));
  const { sourceDir, ranges } = await createSyntheticSource({ trialArtifactSymlink: true });
  try {
    await assert.rejects(importAutoqecCssDistance({
      rootDir: root,
      sourceDir,
      expectedAttempts: [1, 101, 200],
      infrastructureRanges: ranges,
    }), /unsafe non-regular or symlink Git entry: proposal-workspace\/candidate\.py/);
    assert.equal(await fileExists(join(root, "problems", "Prob-001")), false);
  } finally {
    await rm(root, { recursive: true, force: true });
    await rm(sourceDir, { recursive: true, force: true });
  }
});

test("rejects Git symlink and submodule infrastructure entries without installing a destination", async () => {
  for (const options of [{ infrastructureSymlink: true }, { infrastructureSubmodule: true }]) {
    const root = await mkdtemp(join(tmpdir(), "autoqec-import-root-"));
    const { sourceDir, ranges } = await createSyntheticSource(options);
    try {
      await assert.rejects(importAutoqecCssDistance({
        rootDir: root,
        sourceDir,
        expectedAttempts: [1, 101, 200],
        infrastructureRanges: ranges,
      }), /unsafe non-regular or symlink Git entry: src\/autoqec_search\/css_distance_container\.py/);
      assert.equal(await fileExists(join(root, "problems", "Prob-001")), false);
    } finally {
      await rm(root, { recursive: true, force: true });
      await rm(sourceDir, { recursive: true, force: true });
    }
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
