import assert from "node:assert/strict";
import test from "node:test";

import {
  parseAssessmentFinalMessage,
  summarizeCompletedAssessment,
  validateAssessmentEnvelope,
} from "../lib/assessments/contract.mjs";

function dimension(id, weight, estimate, evidenceState = "supported") {
  return {
    id,
    label: id,
    weight,
    score: { min: estimate, estimate, max: estimate },
    evidenceState,
    rationale: `${id} rationale`,
    evidenceRefs: evidenceState === "unknown" ? [] : ["k1"],
  };
}

function validEnvelope(overrides = {}) {
  return {
    outcome: "assessment",
    language: "en",
    knowledgeResolution: {
      query: "fresh evaluation for a solver problem",
      status: "match",
      topic: "knowledge/example/index.qmd",
      orderedFiles: ["knowledge/index.qmd", "knowledge/example/index.qmd"],
    },
    assessment: {
      schemaVersion: 1,
      normalizedProblem: "Find a fresh, executable benchmark for the solver.",
      verdict: { label: "DO_NOW", provisional: false, possibleLabels: ["DO_NOW"] },
      recommendation: "proceed",
      scores: {
        researchValue: { min: 80, estimate: 80, max: 80 },
        autoresearchSuitability: { min: 80, estimate: 80, max: 80 },
        combined: { min: 80, estimate: 80, max: 80 },
      },
      confidence: { level: "high", rationale: "Every key claim cites trusted knowledge." },
      dimensions: {
        researchValue: [
          dimension("importance", 20, 4),
          dimension("gap_and_novelty", 20, 4),
          dimension("plausibility", 15, 4),
          dimension("learning_from_failure", 15, 4),
          dimension("generality_and_publication", 15, 4),
          dimension("expected_value_relative_to_cost", 15, 4),
        ],
        autoresearchSuitability: [
          dimension("modifiable_search_object", 20, 4),
          dimension("executable_objective", 20, 4),
          dimension("correctness_and_anti_gaming", 15, 4),
          dimension("incremental_feedback", 15, 4),
          dimension("fresh_evaluation", 10, 4),
          dimension("reproducibility_and_auditability", 10, 4),
          dimension("attempt_runtime", 10, 4),
        ],
      },
      largestBottleneck: "The anti-gaming gate needs careful fixture separation.",
      recommendedReframe: { kind: "none", text: "No bounded reframe is needed." },
      informationGaps: [],
      evidence: [{
        id: "k1",
        kind: "knowledge",
        path: "knowledge/example/index.qmd",
        locator: "section: Fresh Evaluation Plan",
        summary: "Trusted page describes the gate.",
      }],
    },
    clarification: null,
    ...overrides,
  };
}

function quantitativeEvidence(overrides = {}) {
  return {
    domain: "quantum-computing",
    quantumArea: "algorithms-and-applications",
    snapshot: {
      snapshotId: "20260729T010203Z-0123456789ab",
      contentHash: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      createdAt: "2026-07-29T01:02:03.000Z",
      freshness: "fresh",
      visibility: "public",
    },
    scientificAttention: {
      value: { state: "known", interval: { low: 80, base: 80, high: 80 }, unit: "percent", visibility: "public", evidenceState: "reported", evidenceTier: "primary", sourceIds: ["citation-source"], sources: [{ id: "citation-source", url: "https://example.test/citations", locator: "table 1", kind: "citation-index" }] },
      momentum: { state: "known", interval: { low: 0.1, base: 0.1, high: 0.1 }, unit: "fraction", visibility: "public", evidenceState: "reported", evidenceTier: "primary", sourceIds: ["citation-source"], sources: [{ id: "citation-source", url: "https://example.test/citations", locator: "table 1", kind: "citation-index" }] },
      coverage: 0.9,
      concentration: 0.2,
      warnings: [],
    },
    technicalFeasibility: { state: "unknown", reason: "No confirmed feasibility model." },
    socialValue: { state: "unknown", reason: "No confirmed social value model." },
    capturableValue: { state: "unknown", reason: "No confirmed capturable value model." },
    informationValue: { state: "unknown", reason: "No confirmed information value model." },
    scoreAnchors: [{
      dimensionId: "importance",
      recommended: { min: 4, estimate: 4, max: 4 },
      evidenceIds: ["scientific-attention"],
      override: null,
    }],
    sensitivity: [{ id: "success", label: "Technical success", swing: 10 }],
    assumptions: [],
    warnings: [],
    ...overrides,
  };
}

function validQuantumEnvelopeV2(overrides = {}) {
  const envelope = validEnvelope();
  envelope.assessment = {
    ...envelope.assessment,
    schemaVersion: 2,
    visibility: "public",
    quantitativeEvidence: quantitativeEvidence(),
  };
  return { ...envelope, ...overrides };
}

test("accepts a valid assessment and recomputes scores", () => {
  const result = validateAssessmentEnvelope(validEnvelope());
  assert.equal(result.ok, true);
  assert.deepEqual(result.computed.scores.combined, { min: 80, estimate: 80, max: 80 });
  assert.equal(result.computed.verdict.label, "DO_NOW");
});

test("accepts v1 unchanged and a snapshot-bound v2 quantum assessment", () => {
  assert.equal(validateAssessmentEnvelope(validEnvelope()).ok, true);
  const result = validateAssessmentEnvelope(validQuantumEnvelopeV2());
  assert.equal(result.ok, true);
  assert.equal(result.value.assessment.quantitativeEvidence.snapshot.contentHash.length, 64);
  assert.deepEqual(result.computed.scores.combined, { min: 80, estimate: 80, max: 80 });
});

test("rejects v2 quantitative evidence without a frozen snapshot hash", () => {
  const envelope = validQuantumEnvelopeV2();
  delete envelope.assessment.quantitativeEvidence.snapshot.contentHash;
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /snapshot/i);
});

test("rejects unknown-as-zero quantitative evidence", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.quantitativeEvidence.technicalFeasibility = { state: "unknown", reason: "No model.", interval: { low: 0, base: 0, high: 0 } };
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /quantitative/i);
});

test("rejects private quantitative evidence without private assessment visibility", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.quantitativeEvidence.snapshot.visibility = "private";
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /private assessment visibility/i);
});

test("rejects raw citation addition to aggregate scoring", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.quantitativeEvidence.scientificAttention.rawCitationTotal = 100000;
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /quantitativeEvidence/i);
});

test("rejects coverage as a score bonus", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.quantitativeEvidence.scoreAnchors[0].evidenceIds = ["coverage"];
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /coverage is confidence-only/i);
});

test("rejects a score outside its anchor without an override", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.dimensions.researchValue[0].score = { min: 3, estimate: 3, max: 3 };
  envelope.assessment.scores.researchValue = { min: 76, estimate: 76, max: 76 };
  envelope.assessment.scores.combined = { min: 77.84, estimate: 77.84, max: 77.84 };
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /anchor/i);
});

test("rejects momentum or citation evidence anchored to novelty", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.quantitativeEvidence.scoreAnchors[0].dimensionId = "gap_and_novelty";
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /novelty/i);
});

test("rejects opaque quantitative evidence IDs used to bypass anchor restrictions", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.quantitativeEvidence.scoreAnchors[0].dimensionId = "gap_and_novelty";
  envelope.assessment.quantitativeEvidence.scoreAnchors[0].evidenceIds = ["opaque-1"];
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /known quantitative outputs|novelty/i);
});

test("rejects a momentum movement greater than a quarter point", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.quantitativeEvidence.scoreAnchors[0].momentumAdjustment = 0.26;
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /momentum/i);
});

test("rejects quantitative evidence with unresolved source provenance", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.quantitativeEvidence.scientificAttention.value.sourceIds = ["missing-source"];
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /source/i);
});

test("rejects non-ISO quantitative snapshot timestamps", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.quantitativeEvidence.snapshot.createdAt = "July 29, 2026";
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /snapshot/i);
});

test("rejects envelopes that contain both assessment and clarification", () => {
  const result = validateAssessmentEnvelope(validEnvelope({
    clarification: { query: "x", reason: "ambiguous", alternatives: [] },
  }));
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /exactly one/);
});

test("accepts resolver ambiguity only as needs_input", () => {
  const result = validateAssessmentEnvelope({
    outcome: "needs_input",
    language: "en",
    knowledgeResolution: {
      query: "Hamiltonian benchmark",
      status: "ambiguous",
      topic: null,
      orderedFiles: [],
    },
    assessment: null,
    clarification: {
      query: "Hamiltonian benchmark",
      reason: "Resolver returned multiple candidates.",
      alternatives: [
        { page: "knowledge/a/index.qmd", topic: "a", title: "A", matchKind: "title" },
        { page: "knowledge/b/index.qmd", topic: "b", title: "B", matchKind: "title" },
      ],
    },
  });
  assert.equal(result.ok, true);
});

test("keeps no-match assessment dimensions evidence-dependent unknown", () => {
  const envelope = validEnvelope({
    knowledgeResolution: {
      query: "unknown candidate",
      status: "no-match",
      topic: null,
      orderedFiles: [],
    },
  });
  envelope.assessment.dimensions.researchValue[1] = dimension("gap_and_novelty", 20, 2, "unknown");
  envelope.assessment.scores.researchValue = { min: 72, estimate: 76, max: 80 };
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /model arithmetic/);
});

test("rejects missing aggregate score intervals without throwing", () => {
  const envelope = validEnvelope();
  delete envelope.assessment.scores.combined;
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /score intervals are invalid/);
});

test("rejects evidence that labels drafts as trusted knowledge", () => {
  const envelope = validEnvelope();
  envelope.assessment.evidence[0].path = "drafts/unreviewed.qmd";
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /trusted knowledge path/);
});

test("rejects resolver topic and ordered files outside trusted knowledge", () => {
  const envelope = validEnvelope();
  envelope.knowledgeResolution.topic = "literature/external.qmd";
  envelope.knowledgeResolution.orderedFiles = ["knowledge/index.qmd", "drafts/unreviewed.qmd"];
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /trusted knowledge path/);
});

test("requires both envelope branch fields even when one is null", () => {
  const envelope = validEnvelope();
  delete envelope.clarification;
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /assessment and clarification fields/);
});

test("requires possible verdict labels to include the selected verdict", () => {
  const envelope = validEnvelope();
  envelope.assessment.verdict.possibleLabels = ["REFRAME"];
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /verdict is invalid/);
});

test("parses Codex final message as the same strict envelope", () => {
  const result = parseAssessmentFinalMessage(JSON.stringify(validEnvelope()));
  assert.equal(result.ok, true);
});

test("summary exposes advisory verdict fields without lifecycle mutation", () => {
  const validation = validateAssessmentEnvelope(validEnvelope());
  const summary = summarizeCompletedAssessment({
    run: { runId: "20260728T010203Z-a1b2c3", problemId: "Prob-001", createdAt: "2026-07-28T01:02:03.000Z" },
    envelope: validation.value,
    computed: validation.computed,
  });
  assert.equal(summary.runId, "20260728T010203Z-a1b2c3");
  assert.equal(summary.verdict, "DO_NOW");
  assert.equal(summary.recommendation, "proceed");
  assert.equal(summary.lifecycleMutation, false);
  assert.equal("quantitative" in summary, false);
});

test("v2 summary exposes headline quantitative metrics and private visibility", () => {
  const envelope = validQuantumEnvelopeV2();
  envelope.assessment.quantitativeEvidence.snapshot.visibility = "private";
  envelope.assessment.visibility = "private";
  const validation = validateAssessmentEnvelope(envelope);
  assert.equal(validation.ok, true);
  const summary = summarizeCompletedAssessment({
    run: { runId: "20260729T010203Z-a1b2c3", problemId: "Prob-001", createdAt: "2026-07-29T01:02:03.000Z" },
    envelope: validation.value,
    computed: validation.computed,
  });
  assert.equal(summary.visibility, "private");
  assert.deepEqual(summary.quantitative, {
    scientificAttention: envelope.assessment.quantitativeEvidence.scientificAttention.value,
    technicalSuccess: envelope.assessment.quantitativeEvidence.technicalFeasibility,
    socialValue: envelope.assessment.quantitativeEvidence.socialValue,
    capturableValue: envelope.assessment.quantitativeEvidence.capturableValue,
    largestSensitivity: envelope.assessment.quantitativeEvidence.sensitivity[0],
    snapshotId: "20260729T010203Z-0123456789ab",
    freshness: "fresh",
  });
});
