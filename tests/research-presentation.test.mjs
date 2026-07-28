import assert from "node:assert/strict";
import test from "node:test";

import {
  buildResearchAttemptDossier,
  buildResearchLedger,
  formatCandidate,
  formatMetricValue,
} from "../lib/problems/research-presentation.mjs";
import { RESEARCH_DISCLAIMER } from "../lib/problems/research-schema.mjs";

const manifest = {
  problemId: "Prob-001",
  disclaimer: RESEARCH_DISCLAIMER,
};

function attempt(id, overrides = {}) {
  const sequence = Number(id.slice(4));
  return {
    problemId: "Prob-001",
    id,
    sequence,
    cohort: sequence <= 100 ? "cohort-001-100" : "cohort-101-200",
    title: `CSS Distance Proposal ${String(sequence).padStart(3, "0")}`,
    summary: "Imported AutoQEC trial record.",
    stage: "development",
    decision: "rejected",
    gate: { containment: "passed", publicContract: "passed", development: "failed" },
    method: { description: "kernel sampling", learnedFrom: null },
    metrics: {
      runs: 24,
      verifiedWitnesses: 12,
      targetHits: 12,
      timeouts: 0,
      crashes: 0,
      invalidClaims: 12,
      weightedTargetHits: 12,
      normalizedQuality: 0.5,
      runtimeSeconds: 4.705462539917789,
      averageSeconds: null,
      medianSeconds: null,
      p95Seconds: null,
      timingStatus: "legacy-not-recorded",
      speedup: null,
    },
    provenance: {
      sourceRepository: "AutoQEC",
      sourceBranch: `autoresearch/css-distance/run200-proposal-${sequence}`,
      sourceCommit: "d".repeat(40),
      sourceInfrastructureCommit: "b6a0e03c05a653b4e85160a703c0be4eef06b619",
      sourceCohort: "cohort-101-200",
      model: null,
    },
    candidate: { status: "present", path: "candidate.py" },
    artifacts: [
      { path: "LOG.md", sha256: "a".repeat(64), sourcePath: "LOG.md" },
      { path: "REPORT.md", sha256: "b".repeat(64), sourcePath: "REPORT.md" },
    ],
    ...overrides,
  };
}

test("builds aggregate cards and ordered rows without synthetic speedups", () => {
  const record = {
    problemId: "Prob-001",
    manifest,
    attempts: [
      attempt("ATT-002", { decision: "accepted", metrics: { ...attempt("ATT-002").metrics, targetHits: 23, normalizedQuality: 0.9722222222222222 } }),
      attempt("ATT-001"),
    ],
  };

  const ledger = buildResearchLedger(record);

  assert.deepEqual(ledger.cards, [
    { label: "Attempts", value: "2" },
    { label: "Accepted", value: "1" },
    { label: "Best hits", value: "23/24" },
    { label: "Candidates", value: "2 present" },
  ]);
  assert.deepEqual(ledger.rows.map((row) => row.id), ["ATT-001", "ATT-002"]);
  assert.equal(ledger.rows[0].p95, "legacy not recorded");
  assert.equal(ledger.rows[0].candidate, "present");
  assert.equal(ledger.rows[0].href, "/problems/Prob-001/attempts/ATT-001");
});

test("formats recorded, legacy, not-run, and missing candidate states distinctly", () => {
  assert.equal(formatMetricValue(9.437287125037983, "recorded"), "9.44 s");
  assert.equal(formatMetricValue(null, "legacy-not-recorded"), "legacy not recorded");
  assert.equal(formatMetricValue(null, "not-run"), "not run");
  assert.equal(formatCandidate({ status: "not-generated" }), "not generated");
});

test("builds an attempt dossier with provenance, artifacts, and missing-candidate message", () => {
  const dossier = buildResearchAttemptDossier(attempt("ATT-101", {
    candidate: { status: "not-generated" },
    gate: { containment: "passed", publicContract: "failed", development: "failed" },
    metrics: {
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
    },
  }), manifest);

  assert.equal(dossier.candidate.message, "Candidate code was not generated.");
  assert.deepEqual(dossier.metrics.map((metric) => metric.value), ["0/0", "0", "0.000", "not run", "not run", "not run"]);
  assert.equal(dossier.provenance.sourceRepository, "AutoQEC");
  assert.deepEqual(dossier.artifacts.map((artifact) => artifact.path), [
    "problems/Prob-001/attempts/ATT-101/LOG.md",
    "problems/Prob-001/attempts/ATT-101/REPORT.md",
  ]);
});
