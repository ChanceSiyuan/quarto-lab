import { setupLocalAssessmentFixture } from "./local-assessment-fixture";
import { main } from "../../tooling/scripts/dev-problem-index.mjs";
import { startAssessmentService } from "../../tooling/scripts/local-assessment-service.mjs";

function evidence(id: string, unit = "hours", interval = { low: 1, base: 2, high: 3 }) {
  return {
    id,
    state: "known",
    interval,
    unit,
    visibility: "public",
    evidenceState: "reported",
    evidenceTier: "primary",
    sourceIds: [`${id}-source`],
    sources: [{ id: `${id}-source`, url: `https://example.test/${id}`, locator: "fixture", kind: unit.startsWith("USD") ? "business-model" : "contract" }],
    ...(unit.startsWith("USD") ? { currency: "USD", priceBaseYear: 2026, conversionSourceId: `${id}-source` } : {}),
  };
}

const valuationResearcher = {
  async run() {
    return {
      ok: true,
      stderr: "",
      eventsText: "{\"type\":\"fake-valuation\"}\n",
      candidate: {
        schemaVersion: 1,
        problemId: "Prob-903",
        scope: { status: "supported", domain: "quantum-computing", quantumArea: "resource-estimation-and-benchmarks" },
        anchorCandidates: [{
          id: "anchor-paper-1",
          persistentId: "WQ1",
          title: "Quantum resource benchmark anchor",
          relevanceRationale: "Directly measures resource-estimation benchmark attention.",
          sourceUrl: "https://example.test/quantum-anchor-1",
        }, {
          id: "anchor-paper-2",
          persistentId: "WQ2",
          title: "Fault-tolerant benchmark economics",
          relevanceRationale: "Connects resource estimates to economic value.",
          sourceUrl: "https://example.test/quantum-anchor-2",
        }],
        paperInclusionRules: { include: ["Resource-estimation benchmark evidence."], exclude: ["Non-quantum benchmarks."] },
        technicalStages: [
          { id: "stage-1", description: "Define logical workload." },
          { id: "stage-2", description: "Estimate logical resources." },
          { id: "stage-3", description: "Map to physical qubits." },
          { id: "stage-4", description: "Benchmark classical baseline." },
          { id: "stage-5", description: "Audit reproducibility." },
        ],
        classicalBaseline: { description: "GPU tensor-network simulation baseline.", sourceUrl: "https://example.test/classical-baseline" },
        marketEvidence: [evidence("market-input", "USD_2026", { low: 1_000_000, base: 2_000_000, high: 3_000_000 })],
        atomicInputs: [evidence("social-value", "USD_2026", { low: 4_000_000, base: 8_000_000, high: 12_000_000 })],
        materialAssumptions: [{
          id: "adoption-assumption",
          question: "Assume benchmark users can reproduce the resource-estimation workflow?",
          proposedValue: { state: "unknown", reason: "Requires operator confirmation in the browser fixture." },
          sensitivityRank: 1,
          confirmationRequired: true,
        }],
        warnings: ["Fixture valuation evidence is deterministic."],
      },
    };
  },
};

const openAlex = {
  async expand() {
    return [{
      id: "WQ1",
      doi: "10.1234/quantum.fixture.1",
      title: "Quantum resource benchmark anchor",
      publicationYear: 2025,
      relevance: 1,
      citationNormalizedPercentile: 0.92,
      citedByCount: 42,
      countsByYear: [{ year: 2025, citedByCount: 12 }, { year: 2026, citedByCount: 30 }],
      sourceUrl: "https://example.test/quantum-anchor-1",
    }, {
      id: "WQ2",
      doi: "10.1234/quantum.fixture.2",
      title: "Fault-tolerant benchmark economics",
      publicationYear: 2024,
      relevance: 0.9,
      citationNormalizedPercentile: 0.75,
      citedByCount: 27,
      countsByYear: [{ year: 2024, citedByCount: 7 }, { year: 2025, citedByCount: 9 }, { year: 2026, citedByCount: 11 }],
      sourceUrl: "https://example.test/quantum-anchor-2",
    }];
  },
};

await setupLocalAssessmentFixture();
await main({
  vinextDevArgs: process.argv.slice(2),
  startAssessmentServiceFn: (options: Parameters<typeof startAssessmentService>[0]) => startAssessmentService({
    ...options,
    valuationResearcher,
    openAlex,
  }),
});
