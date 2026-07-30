import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { backfillQecPointEstimates } from "../tooling/scripts/backfill-qec-point-estimates.mjs";

function score(estimate) {
  return { min: estimate, estimate, max: estimate };
}

function dimension(id, label, estimate = 4) {
  return {
    id,
    label,
    weight: 10,
    score: score(estimate),
    evidenceState: "inferred",
    rationale: `${label} fixture rationale.`,
    evidenceRefs: [],
  };
}

function assessmentArtifact({ omitAttemptRuntime = false } = {}) {
  const autoresearch = [
    dimension("executable_objective", "Executable objective", 3),
    dimension("correctness_and_anti_gaming", "Correctness and anti-gaming", 2.5),
    dimension("incremental_feedback", "Incremental feedback", 3.5),
    dimension("attempt_runtime", "Attempt runtime", 3),
  ];
  if (omitAttemptRuntime) autoresearch.pop();
  return {
    envelope: {
      language: "en",
      assessment: {
        schemaVersion: 2,
        visibility: "public",
        normalizedProblem: "Backfill the QEC fixture.",
        verdict: { label: "REFRAME", provisional: true, possibleLabels: ["REFRAME"] },
        recommendation: "reframe",
        confidence: { level: "low", rationale: "Fixture confidence." },
        dimensions: {
          researchValue: [dimension("plausibility", "Plausibility", 3.75)],
          autoresearchSuitability: autoresearch,
        },
        largestBottleneck: "Fixture bottleneck.",
        recommendedReframe: { kind: "bounded", text: "Use a frozen fixture." },
        informationGaps: [],
        evidence: [],
        quantitativeEvidence: {
          snapshot: { snapshotId: "snapshot-1", contentHash: "a".repeat(64), freshness: "fresh", visibility: "public" },
          scientificAttention: {
            value: { state: "unknown", reason: "No comparable percentile." },
            momentum: { state: "unknown", reason: "No momentum." },
            coverage: 1,
            concentration: 1,
            warnings: [],
          },
          technicalFeasibility: { state: "unknown", reason: "No sealed gate." },
          socialValue: { state: "unknown", reason: "No social model." },
          capturableValue: { state: "unknown", reason: "No capture model." },
          informationValue: { state: "unknown", reason: "No information model." },
          scoreAnchors: [],
          sensitivity: [],
          assumptions: [],
          warnings: [],
        },
      },
    },
    computed: {
      scores: {
        researchValue: { min: 52, estimate: 72.5, max: 88.75 },
        autoresearchSuitability: { min: 47, estimate: 67, max: 87 },
        combined: { min: 49.37, estimate: 69.64, max: 87.87 },
      },
      verdict: { label: "REFRAME" },
    },
  };
}

function inputArtifact() {
  return {
    schemaVersion: 2,
    policyVersion: 2,
    problemId: "Prob-001",
    problemTitle: "Backfill fixture",
    problemJsonHash: "a".repeat(64),
    problemMdHash: "b".repeat(64),
    skillHash: "c".repeat(64),
    schemaHash: "d".repeat(64),
    resolver: { query: "Fixture", status: "no-match", topic: null, orderedFiles: [] },
    bundle: [],
    valuation: {
      snapshotId: "snapshot-1",
      contentHash: "a".repeat(64),
      snapshotHash: "e".repeat(64),
      visibility: "public",
      freshness: { advisory: true, staleClasses: [], details: {} },
      recalculationInputs: {
        manifest: {
          createdAt: "2026-07-29T01:02:03.000Z",
          citation: {
            formulaId: "qec-scientific-demand-v1",
            scientificDemand: { state: "known", interval: { low: 68.4, base: 68.4, high: 68.4 }, unit: "score-100", visibility: "public" },
            components: {},
            evidenceConfidence: "medium",
            coverage: 0.75,
            paperCount: 3,
            rawCitationTotal: 3,
          },
          confirmedCandidate: {
            technicalStages: [],
            materialAssumptions: [],
            atomicInputs: [],
          },
        },
        papers: [{ id: "W1", title: "Fixture anchor", citedByCount: 3, sourceUrl: "https://openalex.org/W1" }],
        marketEvidence: [],
      },
    },
  };
}

async function writeFixture(rootDir, options = {}) {
  const runDir = join(rootDir, "problems", "Prob-001", "assessments", "run-1");
  await mkdir(runDir, { recursive: true });
  const run = {
    schemaVersion: 1,
    runId: "run-1",
    problemId: "Prob-001",
    parentRunId: null,
    status: "completed",
    createdAt: "2026-07-29T01:02:03.000Z",
    updatedAt: "2026-07-29T01:05:00.000Z",
    error: null,
    summary: { quantitative: { technicalSuccess: { state: "unknown" } } },
  };
  await writeFile(join(runDir, "run.json"), `${JSON.stringify(run, null, 2)}\n`);
  await writeFile(join(runDir, "input.json"), `${JSON.stringify(inputArtifact(), null, 2)}\n`);
  await writeFile(join(runDir, "assessment.json"), `${JSON.stringify(assessmentArtifact(options), null, 2)}\n`);
  await writeFile(join(runDir, "report.html"), "<p>Pending sealed evaluation</p>");
  return runDir;
}

test("audits a completed QEC run without mutating immutable artifacts", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "qec-point-backfill-"));
  const runDir = await writeFixture(rootDir);
  const runBefore = await readFile(join(runDir, "run.json"));
  const reportBefore = await readFile(join(runDir, "report.html"));

  const result = await backfillQecPointEstimates({ rootDir, problemIds: ["Prob-001"] });

  assert.deepEqual(result.updated, []);
  assert.deepEqual(result.ready, ["Prob-001"]);
  assert.deepEqual(result.errors, []);
  assert.deepEqual(await readFile(join(runDir, "run.json")), runBefore);
  assert.deepEqual(await readFile(join(runDir, "report.html")), reportBefore);
});

test("dry run validates without changing artifact bytes", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "qec-point-backfill-dry-"));
  const runDir = await writeFixture(rootDir);
  const runBefore = await readFile(join(runDir, "run.json"));
  const reportBefore = await readFile(join(runDir, "report.html"));

  const result = await backfillQecPointEstimates({ rootDir, problemIds: ["Prob-001"], dryRun: true });

  assert.deepEqual(result.ready, ["Prob-001"]);
  assert.deepEqual(await readFile(join(runDir, "run.json")), runBefore);
  assert.deepEqual(await readFile(join(runDir, "report.html")), reportBefore);
});

test("a derivation failure preserves both original artifacts", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "qec-point-backfill-fail-"));
  const runDir = await writeFixture(rootDir, { omitAttemptRuntime: true });
  const runBefore = await readFile(join(runDir, "run.json"));
  const reportBefore = await readFile(join(runDir, "report.html"));

  const result = await backfillQecPointEstimates({ rootDir, problemIds: ["Prob-001"] });

  assert.equal(result.updated.length, 0);
  assert.equal(result.errors.length, 1);
  assert.match(result.errors[0].message, /attempt_runtime/);
  assert.deepEqual(await readFile(join(runDir, "run.json")), runBefore);
  assert.deepEqual(await readFile(join(runDir, "report.html")), reportBefore);
});
