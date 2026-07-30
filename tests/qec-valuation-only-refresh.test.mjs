import assert from "node:assert/strict";
import test from "node:test";

import {
  createValuationOnlyDerivation,
  createValuationOnlyEnvelope,
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
