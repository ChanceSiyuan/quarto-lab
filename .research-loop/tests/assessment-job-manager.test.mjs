import assert from "node:assert/strict";
import test from "node:test";

import { validateAssessmentEnvelope } from "../../src/lib/assessments/contract.mjs";
import { createAssessmentJobManager } from "../../src/lib/assessments/job-manager.mjs";

function fakeRepository(problemValue = { id: "Prob-001", title: "Fixture", summary: "Summary" }) {
  return {
    getProblem(id) {
      return id === problemValue.id
        ? structuredClone(problemValue)
        : null;
    },
    async readProblemMarkdown(id) {
      return `# ${id}\n\nProblem body.`;
    },
  };
}

function quantumProblem(overrides = {}) {
  return {
    id: "Prob-001",
    title: "Quantum fixture",
    summary: "A quantum fixture.",
    domain: "quantum-computing",
    quantumArea: "hardware-and-control",
    ...overrides,
  };
}

function valuationSnapshot(overrides = {}) {
  return {
    manifest: {
      snapshotId: "20260729T010203Z-0123456789ab",
      contentHash: "a".repeat(64),
      createdAt: "2026-07-29T01:02:03Z",
      scope: { status: "supported", domain: "quantum-computing", quantumArea: "hardware-and-control" },
    },
    recalculationInputs: { technicalStages: [] },
    papers: [],
    marketEvidence: [],
    ...overrides,
  };
}

const EXTERNAL_VALUATION_SELECTION = Object.freeze({
  page: "__external__/valuation-snapshot",
  topic: "external-valuation",
  title: "Continue with external valuation evidence only",
  matchKind: "external-valuation",
});

function fakeStore() {
  const runs = [];
  return {
    runs,
    async createAcceptedRun({ problemId, parentRunId = null }) {
      const run = { schemaVersion: 1, runId: `20260728T01020${runs.length}Z-a1b2c3`, problemId, parentRunId, status: "queued", stagingDir: `/tmp/${runs.length}` };
      runs.push(run);
      return run;
    },
    async appendEvent() {},
    async writeTerminalArtifacts(run, artifacts) {
      run.status = artifacts.status;
      run.error = artifacts.error ?? null;
      run.summary = artifacts.summary ?? null;
      run.artifacts = artifacts;
      return run;
    },
    async listRuns(problemId) {
      return runs.filter((run) => run.problemId === problemId);
    },
    async findRun(runId) {
      return runs.find((run) => run.runId === runId) ?? null;
    },
    async readClarification(problemId, runId) {
      return runs.find((run) => run.problemId === problemId && run.runId === runId)?.artifacts?.clarification ?? null;
    },
    async readInput(problemId, runId) {
      return runs.find((run) => run.problemId === problemId && run.runId === runId)?.artifacts?.input ?? null;
    },
  };
}

function dimension({ id, label, weight }) {
  return {
    id,
    label,
    weight,
    score: { min: 4, estimate: 4, max: 4 },
    evidenceState: "supported",
    rationale: `${label} is supported in the fixture.`,
    evidenceRefs: ["p1"],
  };
}

function completedCodexResult() {
  const envelope = {
    outcome: "assessment",
    language: "en",
    knowledgeResolution: {
      query: "Fixture",
      status: "match",
      topic: "knowledge/topic.qmd",
      orderedFiles: ["knowledge/topic.qmd"],
    },
    assessment: {
      schemaVersion: 1,
      normalizedProblem: "Fixture problem.",
      verdict: { label: "DO_NOW", provisional: false, possibleLabels: ["DO_NOW"] },
      recommendation: "proceed",
      scores: {
        researchValue: { min: 80, estimate: 80, max: 80 },
        autoresearchSuitability: { min: 80, estimate: 80, max: 80 },
        combined: { min: 80, estimate: 80, max: 80 },
      },
      confidence: { level: "medium", rationale: "Fixture confidence." },
      dimensions: {
        researchValue: [
          { id: "importance", label: "Importance", weight: 20 },
          { id: "gap_and_novelty", label: "Gap and novelty", weight: 20 },
          { id: "plausibility", label: "Plausibility", weight: 15 },
          { id: "learning_from_failure", label: "Learning from failure", weight: 15 },
          { id: "generality_and_publication", label: "Generality and publication potential", weight: 15 },
          { id: "expected_value_relative_to_cost", label: "Expected value relative to cost", weight: 15 },
        ].map(dimension),
        autoresearchSuitability: [
          { id: "modifiable_search_object", label: "Modifiable search object", weight: 20 },
          { id: "executable_objective", label: "Executable objective", weight: 20 },
          { id: "correctness_and_anti_gaming", label: "Correctness and anti-gaming", weight: 15 },
          { id: "incremental_feedback", label: "Incremental feedback", weight: 15 },
          { id: "fresh_evaluation", label: "Fresh evaluation", weight: 10 },
          { id: "reproducibility_and_auditability", label: "Reproducibility and auditability", weight: 10 },
          { id: "attempt_runtime", label: "Attempt runtime", weight: 10 },
        ].map(dimension),
      },
      largestBottleneck: "No bottleneck in the fixture.",
      recommendedReframe: { kind: "none", text: "No reframe needed." },
      informationGaps: ["None in fixture."],
      evidence: [{ id: "p1", kind: "problem", path: "problems/Prob-001/problem.md", locator: null, summary: "Fixture problem." }],
    },
    clarification: null,
  };
  const validation = validateAssessmentEnvelope(envelope);
  assert.equal(validation.ok, true, validation.errors?.join("\n"));
  return {
    ok: true,
    envelope: validation.value,
    computed: validation.computed,
    eventsText: '{"type":"complete"}\n',
    stderr: "",
  };
}

function completedQuantumCodexResult() {
  const result = completedCodexResult();
  const source = {
    id: "citation-source",
    url: "https://openalex.org/W1",
    locator: "OpenAlex work W1",
    kind: "citation-index",
  };
  result.envelope.assessment = {
    ...result.envelope.assessment,
    schemaVersion: 2,
    visibility: "public",
    quantitativeEvidence: {
      domain: "quantum-computing",
      quantumArea: "hardware-and-control",
      snapshot: {
        snapshotId: "20260729T010203Z-0123456789ab",
        contentHash: "a".repeat(64),
        createdAt: "2026-07-29T01:02:03.000Z",
        freshness: "fresh",
        visibility: "public",
      },
      scientificAttention: {
        value: {
          id: "scientific-attention",
          state: "known",
          interval: { low: 9, base: 9, high: 9 },
          unit: "count",
          visibility: "public",
          evidenceState: "reported",
          evidenceTier: "authoritative-secondary",
          sourceIds: [source.id],
          sources: [source],
        },
        momentum: { state: "unknown", reason: "No complete-year comparison." },
        coverage: 1,
        concentration: 1,
        warnings: [],
      },
      technicalFeasibility: { state: "unknown", reason: "No measured sealed gate." },
      socialValue: { state: "unknown", reason: "No problem-specific social model." },
      capturableValue: { state: "unknown", reason: "No problem-specific capture model." },
      informationValue: { state: "unknown", reason: "No information-value model." },
      scoreAnchors: [],
      sensitivity: [],
      assumptions: [],
      warnings: [],
    },
  };
  const validation = validateAssessmentEnvelope(result.envelope);
  assert.equal(validation.ok, true, validation.errors?.join("\n"));
  result.envelope = validation.value;
  result.computed = validation.computed;
  return result;
}

test("rejects unknown problem IDs before accepting a run", async () => {
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store: fakeStore(),
    codex: { preflight: async () => ({ ok: true }), run: async () => ({ ok: true }) },
  });
  const result = await manager.start("Prob-999");
  assert.equal(result.accepted, false);
  assert.equal(result.code, "UNKNOWN_PROBLEM");
});

test("requires a ready valuation snapshot before starting a quantum assessment", async () => {
  let preflightCalls = 0;
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(quantumProblem()),
    store,
    codex: {
      preflight: async () => { preflightCalls += 1; return { ok: true }; },
      run: async () => assert.fail("Codex must not run before valuation is ready."),
    },
    valuationStore: {
      list: async () => [],
      verify: async () => assert.fail("No snapshot should be verified when the list is empty."),
    },
    valuationManager: {
      getProblemState: async () => ({ problemId: "Prob-001", activeJob: null, readySnapshotId: null, jobs: [] }),
    },
  });

  const result = await manager.start("Prob-001");

  assert.equal(result.accepted, false);
  assert.equal(result.code, "VALUATION_REQUIRED");
  assert.equal(preflightCalls, 0);
  assert.equal(store.runs.length, 0);
});

test("reports pending valuation confirmation before starting a quantum assessment", async () => {
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(quantumProblem()),
    store: fakeStore(),
    codex: {
      preflight: async () => assert.fail("Codex preflight must wait for valuation confirmation."),
      run: async () => assert.fail("Codex must not run before valuation confirmation."),
    },
    valuationStore: {
      list: async () => [],
      verify: async () => assert.fail("No snapshot should be verified before confirmation."),
    },
    valuationManager: {
      getProblemState: async () => ({
        problemId: "Prob-001",
        activeJob: { runId: "20260729T010203Z-a1b2c3", status: "needs_confirmation" },
        readySnapshotId: null,
        jobs: [],
      }),
    },
  });

  const result = await manager.start("Prob-001");

  assert.equal(result.accepted, false);
  assert.equal(result.code, "VALUATION_NEEDS_CONFIRMATION");
});

test("rejects a tampered valuation snapshot before starting Codex", async () => {
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(quantumProblem()),
    store: fakeStore(),
    codex: {
      preflight: async () => assert.fail("Codex preflight must not run for a tampered snapshot."),
      run: async () => assert.fail("Codex must not run for a tampered snapshot."),
    },
    valuationStore: {
      list: async () => ["20260729T010203Z-0123456789ab"],
      verify: async () => { throw new Error("Snapshot hash mismatch."); },
    },
  });

  const result = await manager.start("Prob-001");

  assert.equal(result.accepted, false);
  assert.equal(result.code, "VALUATION_TAMPERED");
  assert.match(result.message, /hash mismatch/i);
});

test("passes the verified frozen valuation packet to quantum Codex scoring", async () => {
  let receivedValuation = null;
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(quantumProblem()),
    store: fakeStore(),
    codex: {
      preflight: async () => ({ ok: true }),
      run: async ({ valuationInput }) => {
        receivedValuation = valuationInput;
        return { ok: false, code: "CODEX_EXIT", message: "stop after capture", eventsText: "", stderr: "" };
      },
    },
    valuationStore: {
      list: async () => ["20260729T010203Z-0123456789ab"],
      verify: async () => valuationSnapshot(),
    },
  });

  const result = await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(result.accepted, true);
  assert.equal(receivedValuation.snapshotId, "20260729T010203Z-0123456789ab");
  assert.equal(receivedValuation.contentHash, "a".repeat(64));
  assert.deepEqual(receivedValuation.recalculationInputs, { technicalStages: [] });
});

test("persists completed quantum summaries with derived point estimates", async () => {
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(quantumProblem()),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async () => completedQuantumCodexResult(),
    },
    valuationStore: {
      list: async () => ["20260729T010203Z-0123456789ab"],
      verify: async () => valuationSnapshot(),
    },
    snapshot: {
      build: async () => ({
        schemaVersion: 2,
        problemId: "Prob-001",
        resolver: { query: "Fixture", status: "match", topic: "knowledge/topic.qmd", orderedFiles: ["knowledge/topic.qmd"] },
        valuation: {
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
              },
            },
            papers: [{ id: "W1", citedByCount: 9, citationNormalizedPercentile: 0.8, relevance: 1 }],
          },
        },
      }),
    },
    reportRenderer: { render: () => "<!doctype html><title>Assessment</title>" },
    resolveKnowledge: async () => ({
      schemaVersion: 1,
      query: "Fixture",
      status: "match",
      bundle: { topic: "knowledge/topic.qmd", orderedFiles: ["knowledge/topic.qmd"] },
      alternatives: [],
    }),
  });

  await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(store.runs[0].status, "completed");
  assert.equal(store.runs[0].summary.quantitative.scientificAttention.interval.base, 68.4);
  assert.equal(store.runs[0].summary.quantitative.scientificAttention.estimateKind, "scientific-demand-model");
  assert.equal(store.runs[0].summary.quantitative.technicalSuccess.interval.base, 80);
  assert.equal(store.runs[0].summary.quantitative.technicalSuccessMethod.formulaId, "qec-technical-success-v1");
});

test("returns the active run for duplicate starts", async () => {
  let release;
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async () => new Promise((resolve) => { release = () => resolve({ ok: false, code: "CODEX_EXIT", message: "done", eventsText: "", stderr: "" }); }),
    },
  });
  const first = await manager.start("Prob-001");
  const second = await manager.start("Prob-001");
  assert.equal(second.runId, first.runId);
  release();
});

test("problem state exposes public active job fields only", async () => {
  let release;
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async ({ onChild }) => {
        onChild?.({ kill() {}, spawnargs: ["codex", "exec", "secret prompt"] });
        return new Promise((resolve) => {
          release = () => resolve({ ok: false, code: "CODEX_EXIT", message: "done", eventsText: "", stderr: "" });
        });
      },
    },
  });

  const accepted = await manager.start("Prob-001");
  const state = await manager.getProblemState("Prob-001");

  assert.equal(state.activeJob.runId, accepted.runId);
  assert.equal(state.activeJob.status, "running");
  assert.equal("run" in state.activeJob, false);
  assert.equal("child" in state.activeJob, false);
  assert.equal("stagingDir" in state.activeJob, false);
  assert.equal(JSON.stringify(state).includes("secret prompt"), false);
  release();
});

test("runs jobs one at a time in FIFO order", async () => {
  const order = [];
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async ({ problem }) => {
        order.push(problem.id);
        return { ok: false, code: "CODEX_EXIT", message: "forced failure", eventsText: "", stderr: "" };
      },
    },
  });
  await manager.start("Prob-001");
  await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.deepEqual(order, ["Prob-001"]);
  assert.equal(store.runs.length, 1);
});

test("selection consumes a clarification run and records the selected alternative", async () => {
  const alternative = { page: "knowledge/topic.qmd", topic: "topic", title: "Topic", matchKind: "title" };
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async ({ selectedAlternative }) => selectedAlternative
        ? { ok: false, code: "CODEX_EXIT", message: "done", eventsText: "", stderr: "" }
        : { ok: true, envelope: { outcome: "needs_input", clarification: { alternatives: [alternative] } }, stderr: "" },
    },
  });

  const parent = await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal((await manager.select(parent.runId, { ...alternative, title: "Wrong" })).code, "INVALID_SELECTION");
  const child = await manager.select(parent.runId, alternative);
  const repeated = await manager.select(parent.runId, alternative);
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(repeated.runId, child.runId);
  assert.equal(store.runs.length, 2);
  assert.deepEqual(store.runs[1].artifacts.selection, alternative);
  assert.equal((await manager.getProblemState("Prob-001")).activeJob, null);
});

test("valuation-backed ambiguity can continue with explicit external evidence only", async () => {
  const trusted = { page: "knowledge/topic.qmd", topic: "topic", title: "Topic", matchKind: "title" };
  let childTrustedResolution = null;
  let childSelection = null;
  let childValuationInput = null;
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(quantumProblem()),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async ({ selectedAlternative, trustedResolution, valuationInput }) => {
        if (!selectedAlternative) {
          return {
            ok: true,
            envelope: {
              outcome: "needs_input",
              language: "en",
              knowledgeResolution: { query: "Quantum fixture", status: "ambiguous", topic: null, orderedFiles: [] },
              assessment: null,
              clarification: { query: "Quantum fixture", reason: "Choose one.", alternatives: [trusted] },
            },
            stderr: "",
          };
        }
        childSelection = selectedAlternative;
        childTrustedResolution = trustedResolution;
        childValuationInput = valuationInput;
        return { ok: false, code: "STOP_AFTER_SELECTION", message: "selected", eventsText: "", stderr: "" };
      },
    },
    valuationStore: {
      list: async () => ["20260729T010203Z-0123456789ab"],
      verify: async () => valuationSnapshot(),
    },
  });

  const parent = await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));

  const state = await manager.getProblemState("Prob-001");
  const external = state.activeJob.clarification.alternatives.find((alternative) => alternative.matchKind === "external-valuation");
  assert.equal(external.title, "Continue with external valuation evidence only");

  await manager.select(parent.runId, external);
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(childSelection.matchKind, "external-valuation");
  assert.equal(childTrustedResolution.status, "no-match");
  assert.deepEqual(childTrustedResolution.bundle, null);
  assert.equal(childValuationInput.snapshotId, "20260729T010203Z-0123456789ab");
  assert.deepEqual(store.runs[1].artifacts.selection, external);
});

test("valuation-backed starts can explicitly force external evidence only", async () => {
  let childTrustedResolution = null;
  let childSelection = null;
  let resolverCalls = 0;
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(quantumProblem({ title: "Quantum fixture" })),
    store: fakeStore(),
    codex: {
      preflight: async () => ({ ok: true }),
      run: async ({ selectedAlternative, trustedResolution }) => {
        childSelection = selectedAlternative;
        childTrustedResolution = trustedResolution;
        return { ok: false, code: "STOP_AFTER_SELECTION", message: "selected", eventsText: "", stderr: "" };
      },
    },
    resolveKnowledge: async () => {
      resolverCalls += 1;
      return {
        schemaVersion: 1,
        query: "Quantum fixture",
        status: "match",
        bundle: { topic: "knowledge/topic.qmd", orderedFiles: ["knowledge/topic.qmd"] },
        alternatives: [],
      };
    },
    valuationStore: {
      list: async () => ["20260729T010203Z-0123456789ab"],
      verify: async () => valuationSnapshot(),
    },
  });

  await manager.start("Prob-001", {
    valuationSnapshotId: "20260729T010203Z-0123456789ab",
    selectedAlternative: EXTERNAL_VALUATION_SELECTION,
  });
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.deepEqual(childSelection, EXTERNAL_VALUATION_SELECTION);
  assert.equal(childTrustedResolution.status, "no-match");
  assert.equal(childTrustedResolution.query, "Quantum fixture");
  assert.deepEqual(childTrustedResolution.bundle, null);
  assert.equal(resolverCalls, 0);
});

test("host ambiguity is materialized before Codex runs when valuation evidence is ready", async () => {
  const trusted = { page: "knowledge/topic.qmd", topic: "topic", title: "Topic", matchKind: "body-term" };
  let preflightCalls = 0;
  let resolvedQuery = null;
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(quantumProblem()),
    store,
    codex: {
      preflight: async () => { preflightCalls += 1; return { ok: true }; },
      run: async () => assert.fail("Codex must not run until the host ambiguity is explicitly selected."),
    },
    resolveKnowledge: async (query) => {
      resolvedQuery = query;
      return {
        schemaVersion: 1,
        query,
        status: "ambiguous",
        bundle: null,
        alternatives: [{ ...trusted, tier: 5, matchedTerms: 1 }],
      };
    },
    valuationStore: {
      list: async () => ["20260729T010203Z-0123456789ab"],
      verify: async () => valuationSnapshot(),
    },
  });

  const accepted = await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));
  const state = await manager.getProblemState("Prob-001");
  const alternatives = state.activeJob.clarification.alternatives;

  assert.equal(accepted.accepted, true);
  assert.equal(preflightCalls, 1);
  assert.equal(resolvedQuery, "Quantum fixture");
  assert.equal(store.runs[0].status, "needs-input");
  assert.equal(state.activeJob.runId, accepted.runId);
  assert.deepEqual(alternatives[0], trusted);
  assert.equal(alternatives.at(-1).matchKind, "external-valuation");
  assert.equal(store.runs[0].artifacts.input.valuation.snapshotId, "20260729T010203Z-0123456789ab");
});

test("selection supplies the exact host bundle and rejects a child query change", async () => {
  const selected = { page: "knowledge/a.qmd", topic: "knowledge/a/index.qmd", title: "A", matchKind: "exact-title" };
  const other = { page: "knowledge/b.qmd", topic: "knowledge/b/index.qmd", title: "B", matchKind: "exact-title" };
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async ({ selectedAlternative, trustedResolution }) => {
        if (!selectedAlternative) {
          return {
            ok: true,
            envelope: {
              outcome: "needs_input",
              language: "en",
              knowledgeResolution: { query: "Fixture", status: "ambiguous", topic: null, orderedFiles: [] },
              assessment: null,
              clarification: { query: "Fixture", reason: "Choose one.", alternatives: [selected, other] },
            },
            stderr: "",
          };
        }
        if (trustedResolution?.bundle?.orderedFiles.at(-1) !== selected.page) {
          return { ok: false, code: "MISSING_TRUSTED_SELECTION", message: "selected bundle was not supplied", stderr: "" };
        }
        const completed = completedCodexResult();
        completed.envelope.knowledgeResolution = {
          query: "Forged child query",
          status: "match",
          topic: selected.topic,
          orderedFiles: ["knowledge/index.qmd", selected.topic, selected.page],
        };
        return completed;
      },
    },
    resolveKnowledge: async (_query, options) => options?.selectedPage
      ? {
          schemaVersion: 1,
          query: "Fixture",
          status: "match",
          bundle: {
            topic: selected.topic,
            ancestorIndexes: ["knowledge/index.qmd", selected.topic],
            contentPages: [selected.page],
            orderedFiles: ["knowledge/index.qmd", selected.topic, selected.page],
          },
          alternatives: [],
        }
      : {
          schemaVersion: 1,
          query: "Fixture",
          status: "ambiguous",
          bundle: null,
          alternatives: [
            { ...selected, tier: 0, matchedTerms: 1 },
            { ...other, tier: 0, matchedTerms: 1 },
          ],
        },
    snapshot: { build: async () => ({ schemaVersion: 1, problemId: "Prob-001" }) },
    reportRenderer: { render: () => "<!doctype html><title>Assessment</title>" },
  });

  const parent = await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));
  const child = await manager.select(parent.runId, selected);
  await new Promise((resolve) => setTimeout(resolve, 20));

  const childRun = store.runs.find((run) => run.runId === child.runId);
  assert.equal(childRun?.status, "failed");
  assert.equal(childRun?.artifacts.error.code, "KNOWLEDGE_RESOLUTION_MISMATCH");
  assert.equal(childRun?.artifacts.assessment, undefined);
});

test("hydrates a persisted clarification after restart for deduplication and selection", async () => {
  const alternative = { page: "knowledge/topic.qmd", topic: "topic", title: "Topic", matchKind: "title" };
  const store = fakeStore();
  const codex = {
    preflight: async () => ({ ok: true }),
    run: async ({ selectedAlternative }) => selectedAlternative
      ? { ok: false, code: "CODEX_EXIT", message: "done", eventsText: "", stderr: "" }
      : { ok: true, envelope: { outcome: "needs_input", clarification: { alternatives: [alternative] } }, stderr: "" },
  };
  const firstManager = createAssessmentJobManager({ rootDir: "/repo", repository: fakeRepository(), store, codex });
  const parent = await firstManager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));

  const restartedManager = createAssessmentJobManager({ rootDir: "/repo", repository: fakeRepository(), store, codex });
  const state = await restartedManager.getProblemState("Prob-001");
  const duplicate = await restartedManager.start("Prob-001");
  const child = await restartedManager.select(parent.runId, alternative);
  await new Promise((resolve) => setTimeout(resolve, 20));
  const retriedSelection = await createAssessmentJobManager({ rootDir: "/repo", repository: fakeRepository(), store, codex })
    .select(parent.runId, alternative);

  assert.equal(state.activeJob.runId, parent.runId);
  assert.deepEqual(state.activeJob.clarification.alternatives, [alternative]);
  assert.equal(duplicate.runId, parent.runId);
  assert.equal(child.accepted, true);
  assert.equal(retriedSelection.runId, child.runId);
  assert.equal(store.runs.length, 2);
  assert.equal(store.runs[1].parentRunId, parent.runId);
});

test("persists completed run summaries for problem page polling", async () => {
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async () => completedCodexResult(),
    },
    snapshot: {
      build: async () => ({ schemaVersion: 1, problemId: "Prob-001" }),
    },
    reportRenderer: {
      render: () => "<!doctype html><title>Assessment</title>",
    },
  });

  await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));
  const state = await manager.getProblemState("Prob-001");
  const run = state.runs.find((item) => item.status === "completed");

  assert.equal(run.summary.verdict, "DO_NOW");
  assert.equal(run.summary.recommendation, "proceed");
  assert.equal(run.summary.lifecycleMutation, false);
  assert.equal(run.summary.reportHref, `/__local/assessments/reports/Prob-001/${run.runId}`);
  assert.equal("stagingDir" in run, false);
  assert.equal("artifacts" in run, false);
  assert.equal(store.runs[0].artifacts.assessment.envelope.assessment.normalizedProblem, "Fixture problem.");
  assert.equal(store.runs[0].artifacts.eventsText, '{"type":"complete"}\n');
});

test("retains Codex events when assessment post-processing fails", async () => {
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async () => completedCodexResult(),
    },
    snapshot: {
      build: async () => { throw new Error("snapshot failed"); },
    },
  });

  await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(store.runs[0].status, "failed");
  assert.equal(store.runs[0].artifacts.error.message, "snapshot failed");
  assert.equal(store.runs[0].artifacts.eventsText, '{"type":"complete"}\n');
});

test("rejects a completed assessment when the host resolver disagrees with the model", async () => {
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async () => completedCodexResult(),
    },
    resolveKnowledge: async () => ({
      schemaVersion: 1,
      query: "Fixture",
      status: "no-match",
      bundle: null,
      alternatives: [],
    }),
    snapshot: {
      build: async () => {
        throw new Error("a mismatched assessment must not build a trusted snapshot");
      },
    },
  });

  await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(store.runs[0].status, "failed");
  assert.deepEqual(store.runs[0].artifacts.error, {
    code: "KNOWLEDGE_RESOLUTION_MISMATCH",
    message: "Codex knowledge resolution does not match the trusted host resolver.",
  });
  assert.equal(store.runs[0].artifacts.assessment, undefined);
  assert.equal(store.runs[0].artifacts.reportHtml, undefined);
});

test("materializes host ambiguity before Codex can supply altered alternatives", async () => {
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async () => assert.fail("Codex must not supply ambiguity alternatives once the host resolver is ambiguous."),
    },
    resolveKnowledge: async () => ({
      schemaVersion: 1,
      query: "Fixture",
      status: "ambiguous",
      bundle: null,
      alternatives: [
        { page: "knowledge/a.qmd", topic: "knowledge/a/index.qmd", title: "A", matchKind: "exact-title", tier: 0, matchedTerms: 1 },
        { page: "knowledge/b.qmd", topic: "knowledge/b/index.qmd", title: "B", matchKind: "exact-title", tier: 0, matchedTerms: 1 },
      ],
    }),
  });

  await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(store.runs[0].status, "needs-input");
  assert.deepEqual(store.runs[0].artifacts.clarification.clarification.alternatives, [
    { page: "knowledge/a.qmd", topic: "knowledge/a/index.qmd", title: "A", matchKind: "exact-title" },
    { page: "knowledge/b.qmd", topic: "knowledge/b/index.qmd", title: "B", matchKind: "exact-title" },
  ]);
  assert.equal("error" in store.runs[0].artifacts, false);
});

test("problem state surfaces stale latest summaries", async () => {
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async () => completedCodexResult(),
    },
    snapshot: {
      build: async () => ({
        schemaVersion: 1,
        problemId: "Prob-001",
        resolver: { query: "Fixture", status: "match", topic: "knowledge/topic.qmd", orderedFiles: ["knowledge/topic.qmd"] },
      }),
    },
    reportRenderer: {
      render: () => "<!doctype html><title>Assessment</title>",
    },
    resolveKnowledge: async () => ({
      schemaVersion: 1,
      query: "Fixture",
      status: "match",
      bundle: { topic: "knowledge/topic.qmd", orderedFiles: ["knowledge/topic.qmd"] },
      alternatives: [],
    }),
    staleness: {
      evaluate: async ({ input, resolveKnowledge }) => {
        await resolveKnowledge(input.resolver.query);
        return { stale: true, reasons: ["problemMdHash changed"] };
      },
    },
  });

  await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));
  const state = await manager.getProblemState("Prob-001");

  assert.equal(state.latest.verdict, "DO_NOW");
  assert.equal(state.stale, true);
  assert.deepEqual(state.staleReasons, ["problemMdHash changed"]);
});

test("problem state chooses the completed summary with the latest update time", async () => {
  const store = fakeStore();
  store.runs.push(
    {
      schemaVersion: 1,
      runId: "20260729T112500Z-aaaaaa",
      problemId: "Prob-001",
      status: "completed",
      createdAt: "2026-07-29T11:25:00.000Z",
      updatedAt: "2026-07-29T11:25:00.000Z",
      summary: { runId: "20260729T112500Z-aaaaaa" },
    },
    {
      schemaVersion: 1,
      runId: "20260729T112114Z-bbbbbb",
      problemId: "Prob-001",
      status: "completed",
      createdAt: "2026-07-29T11:21:14.000Z",
      updatedAt: "2026-07-29T11:26:36.000Z",
      summary: { runId: "20260729T112114Z-bbbbbb" },
    },
  );
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async () => assert.fail("No assessment run should start."),
    },
  });

  const state = await manager.getProblemState("Prob-001");
  assert.equal(state.latest.runId, "20260729T112114Z-bbbbbb");
});
