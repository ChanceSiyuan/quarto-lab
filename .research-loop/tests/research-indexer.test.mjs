import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { buildResearchIndex } from "../../src/lib/problems/research-indexer.mjs";
import { createResearchRepository } from "../../src/lib/problems/research-repository.mjs";
import { RESEARCH_DISCLAIMER } from "../../src/lib/problems/research-schema.mjs";

const INFRASTRUCTURE_RANGES = [
  { first: 1, last: 1, cohort: "cohort-001-100", commit: "c4533f982ece376c5f299a13edfabff0f489182c" },
  { first: 2, last: 100, cohort: "cohort-001-100", commit: "3e61f5ac8143e4848e5e814188c83683c74dfe4c" },
  { first: 101, last: 104, cohort: "cohort-101-200", commit: "12a8f794f68d63f07303df0cc38fa244c1ab1248" },
  { first: 105, last: 107, cohort: "cohort-101-200", commit: "87f0972ca2551074546c723cf48053d569b9bf59" },
  { first: 108, last: 108, cohort: "cohort-101-200", commit: "3f30f39a2f9be8ceead3821706aae77acdd980aa" },
  { first: 109, last: 200, cohort: "cohort-101-200", commit: "b6a0e03c05a653b4e85160a703c0be4eef06b619" },
];

async function makeRoot() {
  const root = await mkdtemp(join(tmpdir(), "research-loop-research-index-"));
  await mkdir(join(root, "problems", "Prob-001", "attempts", "ATT-001"), { recursive: true });
  await mkdir(join(root, "problems", "Prob-001", "infrastructure", "cohorts"), { recursive: true });
  await mkdir(join(root, "problems", "Prob-001", "infrastructure", "snapshots", "c4533f982ece376c5f299a13edfabff0f489182c"), { recursive: true });
  return root;
}

function attempt(sequence = 1) {
  const infrastructure = INFRASTRUCTURE_RANGES.find((range) => sequence >= range.first && sequence <= range.last);
  return {
    schemaVersion: 1,
    problemId: "Prob-001",
    id: `ATT-${String(sequence).padStart(3, "0")}`,
    sequence,
    cohort: infrastructure.cohort,
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
      sourceCommit: "f".repeat(40), sourceInfrastructureCommit: infrastructure.commit,
      sourceCohort: infrastructure.cohort, model: null,
    },
    candidate: { status: "present", path: "candidate.py" },
    artifacts: [
      { path: "LOG.md", sha256: "a".repeat(64), sourcePath: "LOG.md" },
      { path: "REPORT.md", sha256: "b".repeat(64), sourcePath: "REPORT.md" },
      { path: "candidate.py", sha256: "c".repeat(64), sourcePath: "proposal-workspace/candidate.py" },
    ],
  };
}

async function writeValidResearch(root, sequences = Array.from({ length: 200 }, (_, index) => index + 1)) {
  await writeFile(join(root, "problems", "Prob-001", "research.json"), JSON.stringify({
    schemaVersion: 1, kind: "imported-research-record", problemId: "Prob-001", attemptCount: 200,
    attemptIdRange: ["ATT-001", "ATT-200"], disclaimer: RESEARCH_DISCLAIMER,
    cohorts: [
      { id: "cohort-001-100", first: 1, last: 100 },
      { id: "cohort-101-200", first: 101, last: 200 },
    ],
  }, null, 2));
  for (const sequence of sequences) {
    const id = `ATT-${String(sequence).padStart(3, "0")}`;
    await mkdir(join(root, "problems", "Prob-001", "attempts", id), { recursive: true });
    await writeFile(join(root, "problems", "Prob-001", "attempts", id, "attempt.json"), JSON.stringify(attempt(sequence), null, 2));
  }
}

test("builds a deterministic research index from committed attempts", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);

  const index = await buildResearchIndex({ rootDir: root });

  assert.equal(index.schemaVersion, 1);
  assert.deepEqual(index.records.map((record) => record.problemId), ["Prob-001"]);
  assert.equal(index.records[0].attemptCount, 200);
  assert.equal(index.records[0].attempts.length, 200);
  assert.deepEqual(index.records[0].attempts.slice(0, 3).map((item) => item.id), ["ATT-001", "ATT-002", "ATT-003"]);
  assert.equal(index.records[0].attempts.at(-1).id, "ATT-200");
  assert.deepEqual(index.diagnostics, []);
});

test("does not emit a partial ledger when declared attempts are missing", async () => {
  const root = await makeRoot();
  await writeValidResearch(root, [1]);

  const index = await buildResearchIndex({ rootDir: root });

  assert.deepEqual(index.records, []);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Missing declared attempt directory: ATT-002/);
});

test("rejects unexpected attempt directories before indexing", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);
  await mkdir(join(root, "problems", "Prob-001", "attempts", "ATT-201"), { recursive: true });
  await writeFile(join(root, "problems", "Prob-001", "attempts", "ATT-201", "attempt.json"), "{}\n");

  const index = await buildResearchIndex({ rootDir: root });

  assert.deepEqual(index.records, []);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Unexpected attempt directory: ATT-201/);
});

test("rejects malformed attempt directories before indexing", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);
  await mkdir(join(root, "problems", "Prob-001", "attempts", "trial-001"), { recursive: true });
  await writeFile(join(root, "problems", "Prob-001", "attempts", "trial-001", "attempt.json"), "{}\n");

  const index = await buildResearchIndex({ rootDir: root });

  assert.deepEqual(index.records, []);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Malformed attempt directory: trial-001/);
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
