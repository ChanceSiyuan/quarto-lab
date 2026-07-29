import assert from "node:assert/strict";
import test from "node:test";

import { createValuationJobManager } from "../lib/valuations/job-manager.mjs";
import { validateAtomicEvidence } from "../lib/valuations/contract.mjs";
import { QEC_PORTFOLIO_PROBLEMS } from "../lib/qec-portfolio/catalog.mjs";
import {
  buildApprovedValuationCandidate,
  createQecPortfolioValuationResearcher,
  PROB_001_VALUATION_PROFILE,
} from "../lib/qec-portfolio/valuation-researcher.mjs";

const SCOPE = {
  status: "supported",
  domain: "quantum-computing",
  quantumArea: "error-correction-and-fault-tolerance",
};

async function waitFor(check) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (check()) return;
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  assert.fail("Timed out waiting for valuation manager state.");
}

test("builds one strict approved-evidence candidate for every portfolio problem", async () => {
  const researcher = createQecPortfolioValuationResearcher();
  const records = [
    PROB_001_VALUATION_PROFILE,
    ...QEC_PORTFOLIO_PROBLEMS.map((record) => ({ ...record, technicalAnchors: [record.technicalAnchor] })),
  ];
  for (const record of records) {
    const result = await researcher.run({
      problem: { id: record.id, title: record.title, summary: record.summary },
      quantumScope: SCOPE,
    });
    assert.equal(result.ok, true);
    assert.deepEqual(Object.keys(result.candidate), [
      "schemaVersion", "problemId", "scope", "anchorCandidates", "paperInclusionRules",
      "technicalStages", "classicalBaseline", "marketEvidence", "atomicInputs",
      "materialAssumptions", "warnings",
    ]);
    assert.deepEqual(result.candidate.anchorCandidates.map((item) => item.persistentId), record.technicalAnchors.map((item) => item.persistentId));
    assert.deepEqual(result.candidate.marketEvidence.map((item) => item.id), ["mckinsey-qc-internal-market-2035", "ibm-quantum-investment-floor-2026"]);
    assert.equal(result.candidate.materialAssumptions.find((item) => item.id === "capturable-value")?.proposedValue.state, "unknown");
    assert.equal(result.candidate.materialAssumptions.find((item) => item.id === "capturable-value")?.proposedValue.reason, "No problem-specific pricing, licensing, contract, product-margin, or willingness-to-pay source has been identified.");
    assert.equal(result.candidate.atomicInputs.find((item) => item.id === "technical-success")?.state, "unknown");
    assert.equal(result.candidate.atomicInputs.filter((item) => item.state === "known").every((item) => item.visibility === "public"), true);
    assert.equal(result.candidate.marketEvidence.every((item) => item.visibility === "public"), true);
    assert.equal(result.candidate.warnings.some((warning) => /not trusted knowledge/i.test(warning)), true);
    for (const value of [...result.candidate.marketEvidence, ...result.candidate.atomicInputs, ...result.candidate.materialAssumptions.map((item) => item.proposedValue)]) {
      assert.equal(validateAtomicEvidence(value).ok, true);
    }
    assert.doesNotMatch(JSON.stringify(result.candidate), /\p{Script=Han}/u);
  }
});

test("preserves the explicit Prob-001 citation profile and conservative policy inputs", () => {
  assert.deepEqual(PROB_001_VALUATION_PROFILE.technicalAnchors.map((anchor) => anchor.persistentId), [
    "doi:10.1145/3795877",
    "doi:10.21105/joss.04120",
  ]);
  const candidate = buildApprovedValuationCandidate({
    problem: { id: "Prob-001", title: PROB_001_VALUATION_PROFILE.title, summary: PROB_001_VALUATION_PROFILE.summary },
    quantumScope: SCOPE,
  });
  assert.deepEqual(candidate.atomicInputs.map((item) => [item.id, item.state, item.interval?.base ?? null, item.unit ?? null]), [
    ["attempt-budget", "known", 200, "count"],
    ["wall-clock-budget", "known", 8, "hours"],
    ["allowed-secondary-metric-regression", "known", 0.05, "fraction"],
    ["technical-success", "unknown", null, null],
  ]);
  assert.deepEqual(candidate.technicalStages.map((stage) => stage.id), ["freeze-baseline", "bounded-search", "sealed-evaluation"]);
  assert.equal(candidate.classicalBaseline.description, "The declared implementation and metric reported by the approved technical anchor, frozen before optimization.");
  assert.equal(candidate.materialAssumptions.every((item) => item.confirmationRequired === false), true);
  assert.equal(candidate.marketEvidence.some((item) => item.kind === "broad-enabling-market-proxy"), true);
  assert.equal(candidate.marketEvidence.some((item) => item.kind === "investment-floor"), true);
});

test("rejects every problem outside the approved twenty-one record portfolio", async () => {
  const researcher = createQecPortfolioValuationResearcher();
  const result = await researcher.run({
    problem: { id: "Prob-999", title: "Outside portfolio", summary: "Not approved." },
    quantumScope: SCOPE,
  });
  assert.deepEqual(result, {
    ok: false,
    code: "UNAPPROVED_PORTFOLIO_PROBLEM",
    message: "Prob-999 is not an approved QEC portfolio problem.",
  });
});

test("hands an approved candidate to the valuation manager for exact-anchor confirmation", async () => {
  const researcher = createQecPortfolioValuationResearcher();
  const record = QEC_PORTFOLIO_PROBLEMS[0];
  const manager = createValuationJobManager({
    rootDir: "/tmp/qec-portfolio-valuation-test",
    repository: {
      getProblem: (id) => id === record.id ? {
        id: record.id,
        title: record.title,
        summary: record.summary,
        domain: "quantum-computing",
        quantumArea: "error-correction-and-fault-tolerance",
      } : null,
      readProblemMarkdown: async () => "# Approved QEC draft",
    },
    researcher,
    openAlex: { expand: async () => [] },
    store: {
      readInputs: async () => ({}),
      freeze: async () => assert.fail("confirmation is outside this handoff test"),
      list: async () => [],
    },
  });
  const started = await manager.start(record.id);
  await waitFor(() => manager.getJob(started.runId).status === "needs_confirmation");
  const run = manager.getJob(started.runId);
  assert.deepEqual(run.candidate.anchorCandidates.map((anchor) => anchor.id), [record.technicalAnchor.id]);
  const accepted = await manager.confirm(started.runId, {
    candidateHash: run.candidate.contentHash,
    acceptedAnchorIds: [record.technicalAnchor.id],
    assumptionDecisions: [],
  });
  assert.equal(accepted.accepted, true);
  await manager.shutdown();
});
