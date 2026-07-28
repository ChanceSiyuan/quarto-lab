import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { buildResearchIndex } from "../lib/problems/research-indexer.mjs";
import { createResearchRepository } from "../lib/problems/research-repository.mjs";
import { RESEARCH_DISCLAIMER } from "../lib/problems/research-schema.mjs";

async function makeRoot() {
  const root = await mkdtemp(join(tmpdir(), "research-loop-research-index-"));
  await mkdir(join(root, "problems", "Prob-001", "attempts", "ATT-001"), { recursive: true });
  await mkdir(join(root, "problems", "Prob-001", "infrastructure", "cohorts"), { recursive: true });
  await mkdir(join(root, "problems", "Prob-001", "infrastructure", "snapshots", "c4533f982ece376c5f299a13edfabff0f489182c"), { recursive: true });
  return root;
}

function attempt(sequence = 1) {
  return {
    schemaVersion: 1,
    problemId: "Prob-001",
    id: `ATT-${String(sequence).padStart(3, "0")}`,
    sequence,
    cohort: "cohort-001-100",
    title: `CSS Distance Proposal ${String(sequence).padStart(3, "0")}`,
    summary: "Imported AutoQEC trial record.",
    stage: "development",
    decision: "rejected",
    gate: { containment: "passed", publicContract: "passed", development: "failed" },
    method: { description: "randomized kernel sampling", learnedFrom: null },
    metrics: {
      runs: 24, verifiedWitnesses: 12, targetHits: 12, timeouts: 0, crashes: 0,
      invalidClaims: 12, weightedTargetHits: 12, normalizedQuality: 0.5,
      runtimeSeconds: 4.705462539917789, averageSeconds: null, medianSeconds: null,
      p95Seconds: null, timingStatus: "legacy-not-recorded", speedup: null,
    },
    provenance: {
      sourceRepository: "AutoQEC", sourceBranch: "autoresearch/css-distance/run100-proposal-001",
      sourceCommit: "f".repeat(40), sourceInfrastructureCommit: "c4533f982ece376c5f299a13edfabff0f489182c",
      sourceCohort: "cohort-001-100", model: null,
    },
    candidate: { status: "present", path: "candidate.py" },
    artifacts: [
      { path: "LOG.md", sha256: "a".repeat(64), sourcePath: "LOG.md" },
      { path: "REPORT.md", sha256: "b".repeat(64), sourcePath: "REPORT.md" },
      { path: "candidate.py", sha256: "c".repeat(64), sourcePath: "proposal-workspace/candidate.py" },
    ],
  };
}

async function writeValidResearch(root) {
  await writeFile(join(root, "problems", "Prob-001", "research.json"), JSON.stringify({
    schemaVersion: 1, kind: "imported-research-record", problemId: "Prob-001", attemptCount: 200,
    attemptIdRange: ["ATT-001", "ATT-200"], disclaimer: RESEARCH_DISCLAIMER,
    cohorts: [
      { id: "cohort-001-100", first: 1, last: 100 },
      { id: "cohort-101-200", first: 101, last: 200 },
    ],
  }, null, 2));
  await writeFile(join(root, "problems", "Prob-001", "attempts", "ATT-001", "attempt.json"), JSON.stringify(attempt(), null, 2));
}

test("builds a deterministic research index from committed attempts", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);

  const index = await buildResearchIndex({ rootDir: root });

  assert.equal(index.schemaVersion, 1);
  assert.deepEqual(index.records.map((record) => record.problemId), ["Prob-001"]);
  assert.deepEqual(index.records[0].attempts.map((item) => item.id), ["ATT-001"]);
  assert.deepEqual(index.diagnostics, []);
});

test("surfaces corrupt attempts as diagnostics without returning a partial ledger", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);
  const broken = attempt();
  broken.provenance.sourceInfrastructureCommit = "d".repeat(40);
  await writeFile(join(root, "problems", "Prob-001", "attempts", "ATT-001", "attempt.json"), JSON.stringify(broken, null, 2));

  const index = await buildResearchIndex({ rootDir: root });

  assert.deepEqual(index.records, []);
  assert.equal(index.diagnostics.length, 1);
  assert.match(index.diagnostics[0].relativePath, /attempts\/ATT-001\/attempt\.json/);
});

test("returns every validator diagnostic for a corrupt attempt", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);
  const broken = attempt();
  broken.sequence = 2;
  broken.title = "";
  await writeFile(join(root, "problems", "Prob-001", "attempts", "ATT-001", "attempt.json"), JSON.stringify(broken, null, 2));

  const index = await buildResearchIndex({ rootDir: root });

  assert.deepEqual(index.records, []);
  assert.deepEqual(index.diagnostics.map((item) => item.field), ["id", "title", "provenance.sourceInfrastructureCommit"]);
});

test("repository returns immutable research records and attempts", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);
  const repository = createResearchRepository(await buildResearchIndex({ rootDir: root }));

  const record = repository.getResearchRecord("Prob-001");
  const attemptRecord = repository.getAttempt("Prob-001", "ATT-001");
  record.attempts[0].title = "mutated";
  attemptRecord.title = "mutated";

  assert.equal(repository.getResearchRecord("Prob-001").attempts[0].title, "CSS Distance Proposal 001");
  assert.equal(repository.getAttempt("Prob-001", "ATT-001").title, "CSS Distance Proposal 001");
  assert.equal(repository.getAttempt("Prob-001", "ATT-999"), null);
});
