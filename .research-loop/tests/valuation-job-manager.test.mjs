import assert from "node:assert/strict";
import { mkdtemp, readFile, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createValuationJobManager } from "../../src/lib/valuations/job-manager.mjs";
import { createValuationSnapshotStore } from "../../src/lib/valuations/snapshot-store.mjs";

const now = () => new Date("2026-07-29T09:10:11Z");

function knownEvidence(id) {
  return {
    id,
    state: "known",
    interval: { low: 1, base: 2, high: 3 },
    unit: "hours",
    visibility: "public",
    evidenceState: "reported",
    evidenceTier: "primary",
    sourceIds: [`${id}-source`],
    sources: [{ id: `${id}-source`, url: `https://example.test/${id}`, locator: "section 1", kind: "contract" }],
  };
}

function candidate(overrides = {}) {
  return {
    schemaVersion: 1,
    problemId: "Prob-007",
    scope: { status: "supported", domain: "quantum-computing", quantumArea: "hardware-and-control" },
    anchorCandidates: [{
      id: "anchor-1",
      persistentId: "W1",
      title: "Relevant quantum evidence",
      relevanceRationale: "It measures the relevant hardware constraint.",
      sourceUrl: "https://openalex.org/W1",
    }],
    paperInclusionRules: { include: ["Directly addresses the problem."], exclude: ["Unrelated platforms."] },
    technicalStages: [],
    classicalBaseline: { description: "A documented classical workflow.", sourceUrl: "https://example.test/baseline" },
    marketEvidence: [knownEvidence("market-1")],
    atomicInputs: [knownEvidence("input-1")],
    materialAssumptions: [{
      id: "assumption-1",
      question: "What is the deployment throughput?",
      proposedValue: { state: "unknown", reason: "No public measurement." },
      sensitivityRank: 1,
      confirmationRequired: true,
    }, {
      id: "assumption-2",
      question: "What is the measured control overhead?",
      proposedValue: knownEvidence("assumption-2-value"),
      sensitivityRank: 9,
      confirmationRequired: false,
    }],
    warnings: [],
    ...overrides,
  };
}

function problem(overrides = {}) {
  return {
    id: "Prob-007",
    title: "Fixture quantum problem",
    summary: "A fixture problem.",
    domain: "quantum-computing",
    quantumArea: "hardware-and-control",
    ...overrides,
  };
}

function fixtureManager({
  problemValue = problem(),
  researchResult = { ok: true, candidate: candidate(), stderr: "" },
  runResearch = null,
  inputs = {},
  expand = async () => [{
    id: "W1",
    relevance: 1,
    citationNormalizedPercentile: 0.8,
    citedByCount: 5,
    countsByYear: [{ year: 2024, citedByCount: 1 }, { year: 2025, citedByCount: 2 }],
  }],
  rootDir = join(tmpdir(), "valuation-job-manager-fixture"),
  store: suppliedStore = null,
} = {}) {
  const snapshots = [];
  const frozen = [];
  const store = suppliedStore ?? {
    readInputs: async () => structuredClone(inputs),
    freeze: async (problemId, snapshot) => {
      const snapshotId = `20260729T091011Z-${String(frozen.length + 1).padStart(12, "0")}`;
      const value = { ...structuredClone(snapshot), manifest: { ...snapshot.manifest, snapshotId } };
      frozen.push({ problemId, value });
      snapshots.push(snapshotId);
      return value;
    },
    list: async () => [...snapshots],
  };
  const manager = createValuationJobManager({
    rootDir: rootDir ?? "/repo",
    repository: {
      getProblem: (problemId) => problemId === problemValue.id ? problemValue : null,
      readProblemMarkdown: async () => "# Fixture quantum problem",
    },
    researcher: { run: async (options) => runResearch ? runResearch(options) : researchResult },
    openAlex: { expand },
    store,
    now,
  });
  return { manager, frozen, store, problemValue };
}

async function waitFor(check) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (check()) return;
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  assert.fail("Timed out waiting for valuation job state.");
}

async function confirmed(manager, started) {
  await waitFor(() => manager.getJob(started.runId).status === "needs_confirmation");
  const run = manager.getJob(started.runId);
  return manager.confirm(started.runId, {
    candidateHash: run.candidate.contentHash,
    acceptedAnchorIds: run.candidate.anchorCandidates.map((item) => item.id),
    assumptionDecisions: run.candidate.materialAssumptions
      .filter((item) => item.confirmationRequired)
      .map((item) => ({ id: item.id, decision: "accept" })),
  });
}

test("freezes only the exact confirmed candidate", async () => {
  const { manager, frozen } = fixtureManager();
  const started = await manager.start("Prob-007");
  await waitFor(() => manager.getJob(started.runId).status === "needs_confirmation");
  const run = manager.getJob(started.runId);

  const rejected = await manager.confirm(started.runId, {
    candidateHash: `${run.candidate.contentHash}altered`,
    acceptedAnchorIds: ["anchor-1"],
    assumptionDecisions: [{ id: "assumption-1", decision: "accept" }],
  });
  assert.deepEqual(rejected, { accepted: false, code: "CANDIDATE_MISMATCH" });

  const result = await confirmed(manager, started);
  assert.equal(result.accepted, true);
  await waitFor(() => manager.getJob(started.runId).status === "ready");
  assert.equal(frozen.length, 1);
  assert.equal(frozen[0].value.manifest.candidateHash, run.candidate.contentHash);
  assert.deepEqual(frozen[0].value.manifest.confirmation.assumptionDecisions, [{ id: "assumption-1", decision: "accept" }, { id: "assumption-2", decision: "accepted_automatically" }]);
});

test("rejects confirmation IDs and decisions not present in the candidate", async () => {
  const { manager, frozen } = fixtureManager();
  const started = await manager.start("Prob-007");
  await waitFor(() => manager.getJob(started.runId).status === "needs_confirmation");
  const run = manager.getJob(started.runId);

  const result = await manager.confirm(started.runId, {
    candidateHash: run.candidate.contentHash,
    acceptedAnchorIds: ["not-an-anchor"],
    assumptionDecisions: [{ id: "assumption-1", decision: "accept" }],
  });
  assert.equal(result.accepted, false);
  assert.equal(result.code, "INVALID_CONFIRMATION");
  assert.equal(frozen.length, 0);
});

test("records an incomplete snapshot when OpenAlex has a provider failure", async () => {
  const { manager, frozen } = fixtureManager({
    expand: async () => { throw Object.assign(new Error("provider down"), { code: "OPENALEX_PROVIDER_ERROR" }); },
  });
  const started = await manager.start("Prob-007");
  await confirmed(manager, started);
  await waitFor(() => manager.getJob(started.runId).status === "ready");

  assert.equal(frozen.length, 1);
  assert.equal(frozen[0].value.manifest.complete, false);
  assert.equal(frozen[0].value.manifest.scientificAttention.state, "unknown");
  assert.equal(frozen[0].value.manifest.providerError.code, "OPENALEX_PROVIDER_ERROR");
});

test("never sends private input values to the public-source research process", async () => {
  let receivedInputs = null;
  const { manager } = fixtureManager({
    inputs: { contract: { visibility: "private", value: 42, interval: { low: 1, base: 2, high: 3 } } },
    runResearch: async ({ currentInputs }) => {
      receivedInputs = currentInputs;
      return { ok: true, candidate: candidate(), stderr: "" };
    },
  });
  const started = await manager.start("Prob-007");
  await waitFor(() => manager.getJob(started.runId).status === "needs_confirmation");

  assert.deepEqual(receivedInputs, { contract: { visibility: "private", redacted: true } });
});

test("freezes the complete confirmed candidate and local private inputs for audit", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "valuation-job-manager-private-"));
  const store = createValuationSnapshotStore({ rootDir, now });
  const publicInputs = { publicCurrent: knownEvidence("public-current") };
  const privateInputs = { privateCurrent: { ...knownEvidence("private-current"), visibility: "private" } };
  await store.writeInputs("Prob-007", publicInputs);
  await writeFile(
    join(rootDir, "problems", "Prob-007", "valuation", "inputs.private.json"),
    JSON.stringify(privateInputs),
  );
  const completeCandidate = candidate({
    technicalStages: [{ id: "stage-1", description: "Prepare the controlled hardware run." }],
    warnings: ["Public estimates remain sparse."],
  });
  const { manager } = fixtureManager({
    rootDir,
    store,
    researchResult: { ok: true, candidate: completeCandidate, stderr: "" },
    expand: async () => [],
  });
  const started = await manager.start("Prob-007");
  await waitFor(() => manager.getJob(started.runId).status === "needs_confirmation");
  const run = manager.getJob(started.runId);

  await confirmed(manager, started);
  await waitFor(() => !["queued", "researching", "needs_confirmation", "confirming"].includes(manager.getJob(started.runId).status));
  assert.equal(manager.getJob(started.runId).status, "ready");
  const snapshot = await store.read("Prob-007", manager.getJob(started.runId).snapshotId);

  assert.equal(snapshot.manifest.visibility, "private");
  assert.deepEqual(snapshot.manifest.currentInputs, { ...publicInputs, ...privateInputs });
  assert.deepEqual(snapshot.manifest.confirmedCandidate, run.candidate);
  assert.deepEqual(snapshot.manifest.confirmedCandidate.technicalStages, completeCandidate.technicalStages);
  assert.deepEqual(snapshot.manifest.confirmedCandidate.classicalBaseline, completeCandidate.classicalBaseline);
  assert.deepEqual(snapshot.manifest.confirmedCandidate.atomicInputs, completeCandidate.atomicInputs);
  assert.deepEqual(snapshot.manifest.confirmedCandidate.materialAssumptions, completeCandidate.materialAssumptions);
  assert.deepEqual(snapshot.manifest.confirmedCandidate.paperInclusionRules, completeCandidate.paperInclusionRules);
  assert.deepEqual(snapshot.manifest.confirmedCandidate.warnings, completeCandidate.warnings);
});

test("freezes citation metrics as atomic evidence with provenance", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "valuation-job-manager-citation-"));
  const store = createValuationSnapshotStore({ rootDir, now });
  const { manager } = fixtureManager({
    rootDir,
    store,
    expand: async () => [{
      id: "W1",
      doi: "10.1234/fixture.one",
      relevance: 1,
      citationNormalizedPercentile: 0.9,
      citedByCount: 12,
      countsByYear: [{ year: 2024, citedByCount: 3 }, { year: 2025, citedByCount: 8 }],
    }, {
      id: "W2",
      doi: "10.1234/fixture.two",
      relevance: 1,
      citationNormalizedPercentile: 0.7,
      citedByCount: 9,
      countsByYear: [{ year: 2024, citedByCount: 2 }, { year: 2025, citedByCount: 5 }],
    }],
  });
  const started = await manager.start("Prob-007");

  await confirmed(manager, started);
  await waitFor(() => !["queued", "researching", "needs_confirmation", "confirming"].includes(manager.getJob(started.runId).status));
  assert.equal(manager.getJob(started.runId).status, "ready", JSON.stringify(manager.getJob(started.runId)));
  const snapshot = await store.read("Prob-007", manager.getJob(started.runId).snapshotId);

  assert.equal(snapshot.manifest.scientificAttention.id, "scientific-attention");
  assert.equal(snapshot.manifest.scientificAttention.unit, "score-100");
  assert.equal(snapshot.manifest.scientificAttention.estimateKind, "scientific-demand-model");
  assert.equal(snapshot.manifest.scientificAttention.evidenceTier, "authoritative-secondary");
  assert.deepEqual(snapshot.manifest.scientificAttention.sourceIds, ["citation-W1", "citation-W2"]);
  assert.equal(snapshot.manifest.citation.formulaId, "qec-scientific-demand-v1");
  assert.equal(snapshot.manifest.citation.evidenceConfidence, "low");
  assert.equal(snapshot.manifest.citation.paperCount, 2);
  assert.equal(snapshot.manifest.citation.components.influence.weight, 0.45);
  assert.equal(snapshot.manifest.citation.momentum.id, "citation-momentum");
  assert.equal(snapshot.manifest.citation.momentum.unit, "fraction");
});

test("discovers the latest ready snapshot from the immutable store after restart", async () => {
  const store = {
    readInputs: async () => ({}),
    freeze: async () => assert.fail("restart discovery should not freeze a new snapshot"),
    list: async (problemId) => problemId === "Prob-007"
      ? ["20260728T010203Z-aaaaaaaaaaaa", "20260729T010203Z-bbbbbbbbbbbb"]
      : [],
  };
  const { manager } = fixtureManager({ store });

  const state = await manager.getProblemState("Prob-007");

  assert.equal(state.readySnapshotId, "20260729T010203Z-bbbbbbbbbbbb");
  assert.deepEqual(state.jobs, []);
});

test("does not research unsupported or ambiguous legacy problems", async () => {
  let researchCalls = 0;
  const unsupported = fixtureManager({ problemValue: problem({ domain: "biology", quantumArea: undefined }) });
  unsupported.manager = createValuationJobManager({
    rootDir: "/repo",
    repository: { getProblem: () => problem({ domain: "biology", quantumArea: undefined }), readProblemMarkdown: async () => "# Biology" },
    researcher: { run: async () => { researchCalls += 1; return { ok: true, candidate: candidate() }; } },
    openAlex: { expand: async () => [] },
    store: unsupported.store,
    now,
  });
  const unsupportedResult = await unsupported.manager.start("Prob-007");
  assert.deepEqual(unsupportedResult, { accepted: false, code: "UNSUPPORTED_DOMAIN" });

  const legacyProblem = problem();
  delete legacyProblem.domain;
  delete legacyProblem.quantumArea;
  const legacy = fixtureManager({ problemValue: legacyProblem });
  const needed = await legacy.manager.start("Prob-007");
  assert.equal(needed.status, "needs_input");
  assert.deepEqual(needed.supportedAreas, [
    "algorithms-and-applications", "error-correction-and-fault-tolerance", "compilation-and-architecture",
    "hardware-and-control", "resource-estimation-and-benchmarks", "classical-simulation-and-verification",
  ]);
  assert.equal(researchCalls, 0);
});

test("records a legacy scope override only in the candidate and frozen snapshot", async () => {
  const legacyProblem = problem();
  delete legacyProblem.domain;
  delete legacyProblem.quantumArea;
  const { manager, frozen, problemValue } = fixtureManager({ problemValue: legacyProblem });
  const started = await manager.start("Prob-007", { scopeOverride: "hardware-and-control" });
  await waitFor(() => manager.getJob(started.runId).status === "needs_confirmation");
  assert.equal(manager.getJob(started.runId).candidate.scope.source, "legacy");
  await confirmed(manager, started);
  await waitFor(() => manager.getJob(started.runId).status === "ready");
  assert.equal(frozen[0].value.manifest.scope.source, "legacy");
  assert.equal(Object.hasOwn(problemValue, "domain"), false);
});

test("deduplicates active jobs and preserves the last ready snapshot when research fails", async () => {
  let researchResult = { ok: true, candidate: candidate(), stderr: "" };
  const { manager } = fixtureManager({ runResearch: async () => researchResult });
  const first = await manager.start("Prob-007");
  const duplicate = await manager.start("Prob-007");
  assert.equal(duplicate.runId, first.runId);
  await confirmed(manager, first);
  await waitFor(() => manager.getJob(first.runId).status === "ready");
  const previous = (await manager.getProblemState("Prob-007")).readySnapshotId;

  researchResult = { ok: false, code: "CODEX_EXIT", message: "failed" };
  const failedStart = await manager.start("Prob-007");
  await waitFor(() => manager.getJob(failedStart.runId).status === "research_failed");
  assert.equal((await manager.getProblemState("Prob-007")).readySnapshotId, previous);
});

test("creates a local staging directory and shuts queued work down", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "valuation-job-manager-"));
  let release;
  const { manager } = fixtureManager({
    rootDir,
    researchResult: new Promise((resolve) => { release = resolve; }),
  });
  const started = await manager.start("Prob-007");
  await waitFor(() => manager.getJob(started.runId).status === "researching");
  const stagingDir = join(rootDir, ".generated", "valuation-runs", started.runId);
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      await stat(stagingDir);
      break;
    } catch (error) {
      if (error.code !== "ENOENT" || attempt === 99) throw error;
      await new Promise((resolve) => setTimeout(resolve, 5));
    }
  }
  await manager.shutdown();
  release({ ok: false, code: "CODEX_EXIT", message: "stopped" });
  await waitFor(() => manager.getJob(started.runId).status === "research_failed");
  await assert.rejects(readFile(join(rootDir, "problems", "Prob-007", "problem.json")), /ENOENT/);
});
