import assert from "node:assert/strict";
import test from "node:test";

import {
  AUTOQEC_INFRASTRUCTURE_RANGES,
  RESEARCH_DISCLAIMER,
  validateCohortManifest,
  validateImportManifest,
  validateResearchAttempt,
  validateResearchManifest,
  validateSourceManifest,
} from "../lib/problems/research-schema.mjs";

const baseAttempt = {
  schemaVersion: 1,
  problemId: "Prob-001",
  id: "ATT-200",
  sequence: 200,
  cohort: "cohort-101-200",
  title: "CSS Distance Proposal 200",
  summary: "Imported AutoQEC trial record.",
  stage: "development",
  decision: "rejected",
  gate: {
    containment: "passed",
    publicContract: "passed",
    development: "failed",
  },
  method: {
    description: "Randomized CSS kernel-combination search.",
    learnedFrom: null,
  },
  metrics: {
    runs: 24,
    verifiedWitnesses: 13,
    targetHits: 13,
    timeouts: 0,
    crashes: 0,
    invalidClaims: 11,
    weightedTargetHits: 13,
    normalizedQuality: 0.541666666666667,
    runtimeSeconds: 85.7838381199399,
    averageSeconds: 3.574326588330829,
    medianSeconds: 2.232983041496482,
    p95Seconds: 9.437287125037983,
    timingStatus: "recorded",
    speedup: null,
  },
  provenance: {
    sourceRepository: "AutoQEC",
    sourceBranch: "autoresearch/css-distance/run200-proposal-200",
    sourceCommit: "705563faed99c094534394e5ca8774f3d74863aa",
    sourceInfrastructureCommit: "b6a0e03c05a653b4e85160a703c0be4eef06b619",
    sourceCohort: "cohort-101-200",
    model: null,
  },
  candidate: {
    status: "present",
    path: "candidate.py",
  },
  artifacts: [
    {
      path: "LOG.md",
      sha256: "e28b7dffb8945e10907df9c136e95a5c57ee6a75fb9cb2237316bc6fcbb41a91",
      sourcePath: "LOG.md",
    },
    {
      path: "REPORT.md",
      sha256: "48fc9413bfa907579039c51a1a6c8f3b24e92b570f6ddb724b961ecde6104dfe",
      sourcePath: "REPORT.md",
    },
    {
      path: "candidate.py",
      sha256: "2fb483016f9e8894da309d3079e35c598d412c0c377a84454efae5bfe5322bac",
      sourcePath: "proposal-workspace/candidate.py",
    },
  ],
};

test("validates the imported research manifest contract", () => {
  const result = validateResearchManifest({
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
  }, { relativePath: "problems/Prob-001/research.json" });

  assert.equal(result.ok, true);
});

test("rejects malformed research manifests before indexing", () => {
  const result = validateResearchManifest({
    schemaVersion: 1,
    kind: "imported-research-record",
    problemId: "Prob-001",
    attemptCount: 199,
    attemptIdRange: ["ATT-001", "ATT-200"],
    disclaimer: "reviewed knowledge",
    cohorts: [],
  });

  assert.equal(result.ok, false);
  assert.match(result.errors.map((error) => error.field).join("\n"), /attemptCount/);
  assert.match(result.errors.map((error) => error.field).join("\n"), /disclaimer/);
  assert.match(result.errors.map((error) => error.field).join("\n"), /cohorts/);
});

test("validates real attempt metadata including present and missing candidates", () => {
  assert.equal(validateResearchAttempt(baseAttempt).ok, true);

  const missingCandidate = structuredClone(baseAttempt);
  missingCandidate.id = "ATT-101";
  missingCandidate.sequence = 101;
  missingCandidate.provenance.sourceInfrastructureCommit = "12a8f794f68d63f07303df0cc38fa244c1ab1248";
  missingCandidate.gate.publicContract = "failed";
  missingCandidate.gate.development = "failed";
  missingCandidate.metrics = {
    runs: 0,
    verifiedWitnesses: 0,
    targetHits: 0,
    timeouts: 0,
    crashes: 0,
    invalidClaims: 1,
    weightedTargetHits: 0,
    normalizedQuality: 0,
    runtimeSeconds: null,
    averageSeconds: null,
    medianSeconds: null,
    p95Seconds: null,
    timingStatus: "not-run",
    speedup: null,
  };
  missingCandidate.candidate = { status: "not-generated" };
  missingCandidate.artifacts = missingCandidate.artifacts.filter((artifact) => artifact.path !== "candidate.py");

  assert.equal(validateResearchAttempt(missingCandidate).ok, true);
});

test("rejects unsafe attempt artifacts and unexplained missing candidates", () => {
  const unsafe = structuredClone(baseAttempt);
  unsafe.artifacts[0].path = "../LOG.md";
  assert.equal(validateResearchAttempt(unsafe).ok, false);

  const unexplained = structuredClone(baseAttempt);
  unexplained.candidate = { status: "not-generated" };
  unexplained.artifacts = unexplained.artifacts.filter((artifact) => artifact.path !== "candidate.py");
  assert.equal(validateResearchAttempt(unexplained).ok, false);
});

test("locks the exact AutoQEC infrastructure range map", () => {
  assert.deepEqual(AUTOQEC_INFRASTRUCTURE_RANGES, [
    { first: 1, last: 1, cohort: "cohort-001-100", commit: "c4533f982ece376c5f299a13edfabff0f489182c" },
    { first: 2, last: 100, cohort: "cohort-001-100", commit: "3e61f5ac8143e4848e5e814188c83683c74dfe4c" },
    { first: 101, last: 104, cohort: "cohort-101-200", commit: "12a8f794f68d63f07303df0cc38fa244c1ab1248" },
    { first: 105, last: 107, cohort: "cohort-101-200", commit: "87f0972ca2551074546c723cf48053d569b9bf59" },
    { first: 108, last: 108, cohort: "cohort-101-200", commit: "3f30f39a2f9be8ceead3821706aae77acdd980aa" },
    { first: 109, last: 200, cohort: "cohort-101-200", commit: "b6a0e03c05a653b4e85160a703c0be4eef06b619" },
  ]);
});

test("validates cohort, snapshot, and import manifests", () => {
  const cohort = validateCohortManifest({
    schemaVersion: 1,
    kind: "autoqec-css-distance-cohort",
    id: "cohort-101-200",
    problemId: "Prob-001",
    attempts: [
      { first: 101, last: 104, sourceInfrastructureCommit: "12a8f794f68d63f07303df0cc38fa244c1ab1248" },
      { first: 105, last: 107, sourceInfrastructureCommit: "87f0972ca2551074546c723cf48053d569b9bf59" },
      { first: 108, last: 108, sourceInfrastructureCommit: "3f30f39a2f9be8ceead3821706aae77acdd980aa" },
      { first: 109, last: 200, sourceInfrastructureCommit: "b6a0e03c05a653b4e85160a703c0be4eef06b619" },
    ],
  });
  assert.equal(cohort.ok, true);

  const snapshot = validateSourceManifest({
    schemaVersion: 1,
    kind: "autoqec-css-distance-source-snapshot",
    problemId: "Prob-001",
    sourceRepository: "AutoQEC",
    sourceCommit: "b6a0e03c05a653b4e85160a703c0be4eef06b619",
    attemptRanges: [{ first: 109, last: 200 }],
    entryPoints: [
      "src/autoqec_search/css_distance_autoresearch_batch.py",
      "containers/css-distance-autoresearch/candidate-entrypoint.py",
    ],
    excludedPathClasses: ["blind-evaluation-private", "credentials", "git-metadata"],
    files: [
      {
        path: "src/autoqec_search/css_distance_autoresearch_batch.py",
        sha256: "f".repeat(64),
        size: 1234,
        executable: false,
      },
    ],
    blindDatasetReproducible: false,
  });
  assert.equal(snapshot.ok, true);

  const importManifest = validateImportManifest({
    schemaVersion: 1,
    kind: "autoqec-css-distance-import",
    problemId: "Prob-001",
    sourceRepository: "AutoQEC",
    importedAt: "2026-07-28T00:00:00.000Z",
    attempts: 200,
    files: [
      {
        path: "attempts/ATT-200/REPORT.md",
        sourcePath: "REPORT.md",
        sha256: "a".repeat(64),
        size: 222,
        generated: false,
      },
      {
        path: "attempts/ATT-200/attempt.json",
        sourcePath: null,
        sha256: "b".repeat(64),
        size: 333,
        generated: true,
      },
    ],
  });
  assert.equal(importManifest.ok, true);
});
