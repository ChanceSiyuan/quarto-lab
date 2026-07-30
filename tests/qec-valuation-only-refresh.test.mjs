import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createArtifactStore } from "../lib/assessments/artifact-store.mjs";
import {
  ensureQecScientificDemandSnapshot,
  refreshQecValuationOnlyPortfolio,
} from "../scripts/refresh-qec-valuation-only.mjs";
import {
  createValuationOnlyDerivation,
  createValuationOnlyEnvelope,
  refreshValuationOnlyProblem,
  sourceAssessmentQualifies,
  VALUATION_ONLY_NOTICE,
} from "../lib/qec-portfolio/valuation-only-refresh.mjs";
import { validateAssessmentEnvelope } from "../lib/assessments/contract.mjs";
import {
  AUTORESEARCH_DIMENSIONS,
  RESEARCH_VALUE_DIMENSIONS,
} from "../lib/assessments/policy.mjs";
import { SCIENTIFIC_DEMAND_FORMULA_ID } from "../lib/valuations/citations.mjs";

function pointScore(value) {
  return { min: value, estimate: value, max: value };
}

function dimension(policy) {
  return {
    ...policy,
    score: pointScore(4),
    evidenceState: "supported",
    rationale: `${policy.label} is supported by the source assessment fixture.`,
    evidenceRefs: ["problem-source"],
  };
}

function sourceEnvelope() {
  return {
    outcome: "assessment",
    language: "en",
    knowledgeResolution: {
      query: "QEC fixture",
      status: "no-match",
      topic: null,
      orderedFiles: [],
    },
    assessment: {
      schemaVersion: 2,
      visibility: "public",
      normalizedProblem: "Evaluate a bounded quantum error-correction fixture.",
      verdict: { label: "DO_NOW", provisional: false, possibleLabels: ["DO_NOW"] },
      recommendation: "proceed",
      scores: {
        researchValue: pointScore(80),
        autoresearchSuitability: pointScore(80),
        combined: pointScore(80),
      },
      confidence: { level: "medium", rationale: "The source run is a completed public English assessment." },
      dimensions: {
        researchValue: RESEARCH_VALUE_DIMENSIONS.map(dimension),
        autoresearchSuitability: AUTORESEARCH_DIMENSIONS.map(dimension),
      },
      largestBottleneck: "The benchmark still needs an independently frozen holdout.",
      recommendedReframe: { kind: "none", text: "No reframe is required for this fixture." },
      informationGaps: ["Record the exact sealed benchmark composition before execution."],
      evidence: [{
        id: "problem-source",
        kind: "problem",
        path: "problems/Prob-001/problem.md",
        locator: "fixture",
        summary: "Fixture source evidence.",
      }],
      quantitativeEvidence: {
        domain: "quantum-computing",
        quantumArea: "error-correction-and-fault-tolerance",
        snapshot: {
          snapshotId: "20260729T010203Z-111111111111",
          contentHash: "1".repeat(64),
          createdAt: "2026-07-29T01:02:03.000Z",
          freshness: "fresh",
          visibility: "public",
        },
        scientificAttention: {
          value: {
            id: "old-scientific-demand",
            state: "known",
            interval: { low: 51.5, base: 51.5, high: 51.5 },
            unit: "score-100",
            visibility: "public",
            evidenceState: "inferred",
            evidenceTier: "authoritative-secondary",
            sourceIds: ["citation-WOLD"],
            sources: [{ id: "citation-WOLD", url: "https://openalex.org/WOLD", locator: "OpenAlex work WOLD", kind: "citation-index" }],
            estimateKind: "scientific-demand-model",
            derivation: { formulaId: SCIENTIFIC_DEMAND_FORMULA_ID, inputIds: ["citation-WOLD"] },
          },
          momentum: {
            id: "old-citation-momentum",
            state: "known",
            interval: { low: 0.1, base: 0.1, high: 0.1 },
            unit: "fraction",
            visibility: "public",
            evidenceState: "reported",
            evidenceTier: "authoritative-secondary",
            sourceIds: ["citation-WOLD"],
            sources: [{ id: "citation-WOLD", url: "https://openalex.org/WOLD", locator: "OpenAlex work WOLD", kind: "citation-index" }],
          },
          coverage: 0.7,
          concentration: null,
          warnings: [],
          formulaId: SCIENTIFIC_DEMAND_FORMULA_ID,
          components: {
            influence: { availability: "known", value: 0.5, weight: 0.45, unit: "fraction" },
            momentum: { availability: "known", value: 0.1, weight: 0.30, unit: "fraction" },
            breadth: { availability: "known", value: 0.4, weight: 0.15, unit: "fraction" },
            network: { availability: "reserved", weight: 0.10 },
          },
          evidenceConfidence: "medium",
          paperCount: 2,
        },
        technicalFeasibility: { state: "unknown", reason: "No sealed gate has been measured." },
        socialValue: { state: "unknown", reason: "No source-specific social value model has been identified." },
        capturableValue: { state: "unknown", reason: "No source-specific capturable value model has been identified." },
        informationValue: { state: "unknown", reason: "No source-specific information value model has been identified." },
        scoreAnchors: [],
        sensitivity: [],
        assumptions: [],
        warnings: [],
      },
    },
    clarification: null,
  };
}

function citationSource(id = "W222") {
  return {
    id: `citation-${id}`,
    url: `https://openalex.org/${id}`,
    locator: `OpenAlex work ${id}`,
    kind: "citation-index",
  };
}

function knownCitationValue({ id, unit, value, inferred }) {
  const source = citationSource();
  return {
    id,
    state: "known",
    interval: { low: value, base: value, high: value },
    unit,
    visibility: "public",
    evidenceState: inferred ? "inferred" : "reported",
    evidenceTier: "authoritative-secondary",
    sourceIds: [source.id],
    sources: [source],
    ...(inferred ? {
      estimateKind: "scientific-demand-model",
      derivation: { formulaId: SCIENTIFIC_DEMAND_FORMULA_ID, inputIds: [source.id] },
    } : {}),
  };
}

function valuationSnapshot(overrides = {}) {
  const citation = {
    formulaId: SCIENTIFIC_DEMAND_FORMULA_ID,
    scientificDemand: knownCitationValue({ id: "scientific-demand-score", unit: "score-100", value: 73.2, inferred: true }),
    scientificAttention: knownCitationValue({ id: "scientific-demand-score", unit: "score-100", value: 73.2, inferred: true }),
    momentum: knownCitationValue({ id: "citation-momentum", unit: "fraction", value: 0.24, inferred: false }),
    components: {
      influence: { availability: "known", value: 0.74, weight: 0.45, unit: "fraction" },
      momentum: { availability: "known", value: 0.24, weight: 0.30, unit: "fraction" },
      breadth: { availability: "known", value: 0.63, weight: 0.15, unit: "fraction", paperBreadth: 5, institutionBreadth: 4 },
      network: { availability: "reserved", weight: 0.10 },
    },
    evidenceConfidence: "high",
    coverage: 0.91,
    concentration: 0.3,
    warnings: ["Citation counts measure attention, not feasibility."],
    paperCount: 6,
  };
  return {
    manifest: {
      schemaVersion: 1,
      problemId: "Prob-001",
      snapshotId: "20260730T010203Z-222222222222",
      contentHash: "2".repeat(64),
      createdAt: "2026-07-30T01:02:03.000Z",
      complete: true,
      citation,
      feasibility: { state: "unknown", reason: "No sealed gate has been measured." },
      value: { state: "unknown", reason: "No problem-specific capturable value model has been identified." },
      confirmedCandidate: { warnings: ["External valuation evidence is advisory."] },
      ...overrides,
    },
    papers: [],
    marketEvidence: [],
  };
}

function sourceInput() {
  return {
    schemaVersion: 2,
    policyVersion: 2,
    problemId: "Prob-001",
    problemTitle: "QEC fixture",
    problemSummary: "A bounded QEC fixture.",
    problemJsonHash: "a".repeat(64),
    problemMdHash: "b".repeat(64),
    skillPath: "skills/assess-research-problem/SKILL.md",
    skillHash: "c".repeat(64),
    schemaPath: "schemas/research-problem-assessment.schema.json",
    schemaHash: "d".repeat(64),
    resolver: {
      query: "QEC fixture",
      status: "no-match",
      topic: null,
      orderedFiles: [],
    },
    bundle: [],
    valuation: {
      snapshotId: "20260729T010203Z-111111111111",
      contentHash: "1".repeat(64),
      snapshotHash: "e".repeat(64),
      visibility: "public",
      freshness: { advisory: false, staleClasses: [], details: {} },
      recalculationInputs: {
        manifest: valuationSnapshot({
          snapshotId: "20260729T010203Z-111111111111",
          contentHash: "1".repeat(64),
        }).manifest,
        papers: [],
        marketEvidence: [],
      },
    },
  };
}

async function writeJson(path, value) {
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
}

async function writeSourceRun(rootDir, { runId = "20260729T010203Z-abcdef" } = {}) {
  const runDir = join(rootDir, "problems", "Prob-001", "assessments", runId);
  await mkdir(runDir, { recursive: true });
  const run = {
    schemaVersion: 1,
    runId,
    problemId: "Prob-001",
    parentRunId: null,
    status: "completed",
    createdAt: "2026-07-29T01:02:03.000Z",
    updatedAt: "2026-07-29T01:05:00.000Z",
    error: null,
    summary: { runId, problemId: "Prob-001", verdict: "DO_NOW" },
  };
  await writeJson(join(runDir, "run.json"), run);
  await writeJson(join(runDir, "input.json"), sourceInput());
  await writeJson(join(runDir, "assessment.json"), {
    envelope: sourceEnvelope(),
    computed: {
      scores: {
        researchValue: pointScore(80),
        autoresearchSuitability: pointScore(80),
        combined: pointScore(80),
      },
      verdict: { label: "DO_NOW" },
    },
  });
  await writeFile(join(runDir, "report.html"), "<!doctype html><html lang=\"en\"><body>Completed English source report</body></html>");
  return runDir;
}

async function writeProblem(rootDir) {
  const problemDir = join(rootDir, "problems", "Prob-001");
  await mkdir(problemDir, { recursive: true });
  await writeJson(join(problemDir, "problem.json"), {
    id: "Prob-001",
    title: "QEC fixture",
    summary: "A bounded QEC fixture.",
    status: "active",
    domain: "quantum-computing",
    quantumArea: "error-correction-and-fault-tolerance",
  });
  await writeFile(join(problemDir, "problem.md"), "# QEC fixture\n\nA bounded QEC fixture.\n");
}

function repository() {
  const problem = {
    id: "Prob-001",
    title: "QEC fixture",
    summary: "A bounded QEC fixture.",
    status: "active",
    domain: "quantum-computing",
    quantumArea: "error-correction-and-fault-tolerance",
  };
  return {
    getProblem(id) {
      return id === problem.id ? problem : null;
    },
  };
}

test("derives a valid envelope that retains qualitative fields and replaces quantitative evidence", () => {
  const source = sourceEnvelope();
  assert.equal(validateAssessmentEnvelope(source).ok, true);

  const derived = createValuationOnlyEnvelope({
    sourceEnvelope: source,
    valuationSnapshot: valuationSnapshot(),
  });
  const validation = validateAssessmentEnvelope(derived);

  assert.equal(validation.ok, true, validation.errors?.join("\n"));
  assert.equal(derived.assessment.normalizedProblem, source.assessment.normalizedProblem);
  assert.deepEqual(derived.assessment.dimensions, source.assessment.dimensions);
  assert.deepEqual(derived.assessment.evidence, source.assessment.evidence);
  assert.equal(derived.assessment.quantitativeEvidence.snapshot.snapshotId, "20260730T010203Z-222222222222");
  assert.equal(derived.assessment.quantitativeEvidence.scientificAttention.value.interval.base, 73.2);
  assert.equal(derived.assessment.quantitativeEvidence.scientificAttention.formulaId, SCIENTIFIC_DEMAND_FORMULA_ID);
  assert.deepEqual(derived.assessment.quantitativeEvidence.scoreAnchors, []);
  assert.deepEqual(source.assessment.quantitativeEvidence.snapshot.snapshotId, "20260729T010203Z-111111111111");
});

test("rejects incomplete or wrong-formula snapshots instead of converting missing citations to zero", () => {
  const source = sourceEnvelope();

  assert.throws(
    () => createValuationOnlyEnvelope({
      sourceEnvelope: source,
      valuationSnapshot: valuationSnapshot({ complete: false }),
    }),
    /complete verified qec-scientific-demand-v1/,
  );
  assert.throws(
    () => createValuationOnlyEnvelope({
      sourceEnvelope: source,
      valuationSnapshot: valuationSnapshot({ citation: { formulaId: "old-formula" } }),
    }),
    /complete verified qec-scientific-demand-v1/,
  );
});

test("qualifies only completed public English source assessments", () => {
  const run = { status: "completed", summary: { verdict: "DO_NOW" } };
  const input = { schemaVersion: 2, valuation: { snapshotId: "20260729T010203Z-111111111111" } };
  const assessment = { envelope: sourceEnvelope() };

  assert.equal(sourceAssessmentQualifies({ run, input, assessment, report: "<html>English</html>" }), true);
  assert.equal(sourceAssessmentQualifies({
    run,
    input,
    assessment: { envelope: { ...assessment.envelope, language: "zh" } },
    report: "<html>English</html>",
  }), false);
  assert.equal(sourceAssessmentQualifies({
    run,
    input,
    assessment,
    report: "<html>中文</html>",
  }), false);
});

test("creates provenance for a valuation-only derived run", () => {
  const derivation = createValuationOnlyDerivation({
    problemId: "Prob-001",
    run: { runId: "20260730T020304Z-derived", createdAt: "2026-07-30T02:03:04.000Z" },
    sourceRun: { runId: "20260729T010203Z-source1" },
    sourceInput: { valuation: { snapshotId: "20260729T010203Z-111111111111" } },
    valuationSnapshot: valuationSnapshot(),
  });

  assert.deepEqual(derivation, {
    schemaVersion: 1,
    kind: "qec-valuation-only-refresh",
    problemId: "Prob-001",
    runId: "20260730T020304Z-derived",
    sourceRunId: "20260729T010203Z-source1",
    sourceSnapshotId: "20260729T010203Z-111111111111",
    refreshedSnapshotId: "20260730T010203Z-222222222222",
    notice: VALUATION_ONLY_NOTICE,
    createdAt: "2026-07-30T02:03:04.000Z",
  });
});

test("publishes a valuation-only run while preserving the source artifacts", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "qec-valuation-only-"));
  await writeProblem(rootDir);
  const sourceRunDir = await writeSourceRun(rootDir);
  const before = await Promise.all(["run.json", "input.json", "assessment.json", "report.html"]
    .map((name) => readFile(join(sourceRunDir, name), "utf8")));
  const store = createArtifactStore({
    rootDir,
    now: () => new Date("2026-07-30T02:03:04.000Z"),
    randomBytes: () => Buffer.from("123abc", "hex"),
  });

  const result = await refreshValuationOnlyProblem({
    rootDir,
    repository: repository(),
    store,
    problemId: "Prob-001",
    snapshot: valuationSnapshot(),
  });

  assert.equal(result.status, "completed");
  assert.equal(result.sourceRunId, "20260729T010203Z-abcdef");
  const finalDir = join(rootDir, "problems", "Prob-001", "assessments", result.runId);
  const derivation = JSON.parse(await readFile(join(finalDir, "derivation.json"), "utf8"));
  assert.equal(derivation.sourceRunId, "20260729T010203Z-abcdef");
  assert.equal(derivation.refreshedSnapshotId, "20260730T010203Z-222222222222");
  const run = JSON.parse(await readFile(join(finalDir, "run.json"), "utf8"));
  assert.equal(run.status, "completed");
  assert.equal(run.summary.quantitative.snapshotId, "20260730T010203Z-222222222222");
  assert.equal(run.summary.quantitative.scientificAttention.interval.base, 73.2);
  assert.equal(run.summary.quantitative.technicalSuccess.interval.low, run.summary.quantitative.technicalSuccess.interval.base);
  assert.equal(run.summary.quantitative.technicalSuccess.interval.high, run.summary.quantitative.technicalSuccess.interval.base);
  assert.match(await readFile(join(finalDir, "report.html"), "utf8"), /Qualitative assessment retained/);
  assert.deepEqual(
    await Promise.all(["run.json", "input.json", "assessment.json", "report.html"]
      .map((name) => readFile(join(sourceRunDir, name), "utf8"))),
    before,
  );
});

test("reuses an existing valuation-only run for the same source run and snapshot", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "qec-valuation-only-idempotent-"));
  await writeProblem(rootDir);
  await writeSourceRun(rootDir);
  const store = createArtifactStore({
    rootDir,
    now: () => new Date("2026-07-30T02:03:04.000Z"),
    randomBytes: () => Buffer.from("123abc", "hex"),
  });
  const first = await refreshValuationOnlyProblem({
    rootDir,
    repository: repository(),
    store,
    problemId: "Prob-001",
    snapshot: valuationSnapshot(),
  });

  const second = await refreshValuationOnlyProblem({
    rootDir,
    repository: repository(),
    store,
    problemId: "Prob-001",
    snapshot: valuationSnapshot(),
  });

  assert.deepEqual(second, {
    status: "verified-existing",
    problemId: "Prob-001",
    runId: first.runId,
    sourceRunId: "20260729T010203Z-abcdef",
    snapshotId: "20260730T010203Z-222222222222",
  });
});

test("refreshes a supplied portfolio ID list from verified current-formula snapshots", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "qec-valuation-only-portfolio-"));
  await writeProblem(rootDir);
  await writeSourceRun(rootDir);
  const store = createArtifactStore({
    rootDir,
    now: () => new Date("2026-07-30T02:03:04.000Z"),
    randomBytes: () => Buffer.from("123abc", "hex"),
  });
  const valuationStore = {
    list: async (id) => id === "Prob-001" ? ["20260730T010203Z-222222222222"] : [],
    verify: async (id, snapshotId) => {
      assert.equal(id, "Prob-001");
      assert.equal(snapshotId, "20260730T010203Z-222222222222");
      return valuationSnapshot();
    },
  };

  const result = await refreshQecValuationOnlyPortfolio({
    rootDir,
    repository: repository(),
    store,
    valuationStore,
    problemIds: ["Prob-001"],
  });

  assert.equal(result.status, "complete");
  assert.deepEqual(result.errors, []);
  assert.equal(result.problems[0].status, "completed");
  assert.equal(result.problems[0].snapshotId, "20260730T010203Z-222222222222");
});

test("ensures a missing current-formula snapshot without invoking qualitative assessment", async () => {
  const calls = { start: [], confirm: [] };
  const statuses = new Map([["valuation-Prob-001", "needs_confirmation"]]);
  const valuationManager = {
    start: async (problemId) => {
      calls.start.push(problemId);
      return { accepted: true, runId: `valuation-${problemId}` };
    },
    getJob: async (runId) => ({
      status: statuses.get(runId),
      candidate: {
        contentHash: "f".repeat(64),
        anchorCandidates: [{ id: "anchor-1" }, { id: "anchor-2" }],
        materialAssumptions: [],
      },
    }),
    confirm: async (runId, confirmation) => {
      calls.confirm.push({ runId, confirmation });
      statuses.set(runId, "ready");
      return { accepted: true, runId };
    },
    getProblemState: async () => ({ readySnapshotId: "20260730T010203Z-222222222222" }),
  };
  const valuationStore = {
    list: async () => [],
    verify: async (problemId, snapshotId) => {
      assert.equal(problemId, "Prob-001");
      assert.equal(snapshotId, "20260730T010203Z-222222222222");
      return valuationSnapshot();
    },
  };

  const result = await ensureQecScientificDemandSnapshot({
    valuationManager,
    valuationStore,
    problemId: "Prob-001",
    delay: async () => {},
    pollIntervalMs: 0,
  });

  assert.equal(result.status, "completed");
  assert.equal(result.snapshot.manifest.snapshotId, "20260730T010203Z-222222222222");
  assert.deepEqual(calls.start, ["Prob-001"]);
  assert.deepEqual(calls.confirm, [{
    runId: "valuation-Prob-001",
    confirmation: {
      candidateHash: "f".repeat(64),
      acceptedAnchorIds: ["anchor-1", "anchor-2"],
      assumptionDecisions: [],
    },
  }]);
});

test("snapshot ensure reuses an existing current-formula snapshot", async () => {
  const valuationStore = {
    list: async () => ["20260730T010203Z-222222222222"],
    verify: async () => valuationSnapshot(),
  };
  const valuationManager = {
    start: async () => {
      throw new Error("start should not be called");
    },
  };

  const result = await ensureQecScientificDemandSnapshot({
    valuationManager,
    valuationStore,
    problemId: "Prob-001",
  });

  assert.equal(result.status, "verified-existing");
  assert.equal(result.snapshot.manifest.snapshotId, "20260730T010203Z-222222222222");
});
