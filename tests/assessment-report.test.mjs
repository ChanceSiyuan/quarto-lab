import assert from "node:assert/strict";
import test from "node:test";

import { escapeHtml, renderAssessmentReport } from "../lib/assessments/html-report.mjs";

test("escapes HTML-sensitive model text", () => {
  assert.equal(escapeHtml("<script>alert('x')</script>"), "&lt;script&gt;alert(&#39;x&#39;)&lt;/script&gt;");
});

test("renders a standalone report with required audit sections and no scripts", () => {
  const html = renderAssessmentReport({
    run: {
      runId: "20260728T010203Z-a1b2c3",
      problemId: "Prob-001",
      createdAt: "2026-07-28T01:02:03.000Z",
      updatedAt: "2026-07-28T01:05:00.000Z",
    },
    input: {
      policyVersion: 1,
      problemId: "Prob-001",
      problemTitle: "Fixture problem",
      problemJsonHash: "a".repeat(64),
      problemMdHash: "b".repeat(64),
      skillHash: "c".repeat(64),
      schemaHash: "d".repeat(64),
      resolver: { query: "Fixture", status: "match", topic: "knowledge/example/index.qmd", orderedFiles: ["knowledge/example/index.qmd"] },
      bundle: [{ path: "knowledge/example/index.qmd", hash: "e".repeat(64) }],
    },
    envelope: {
      language: "en",
      assessment: {
        normalizedProblem: "Fixture <problem>",
        verdict: { label: "REFRAME", provisional: true, possibleLabels: ["REFRAME", "DEFER"] },
        recommendation: "reframe",
        confidence: { level: "low", rationale: "One input is uncertain." },
        dimensions: {
          researchValue: [{
            id: "importance",
            label: "Importance",
            weight: 20,
            score: { min: 3, estimate: 4, max: 5 },
            evidenceState: "supported",
            rationale: "Important.",
            evidenceRefs: ["k1"],
          }],
          autoresearchSuitability: [{
            id: "attempt_runtime",
            label: "Attempt runtime",
            weight: 10,
            score: { min: 2, estimate: 3, max: 4 },
            evidenceState: "inferred",
            rationale: "Runtime may exceed the target.",
            evidenceRefs: [],
          }],
        },
        largestBottleneck: "Runtime uncertainty.",
        recommendedReframe: { kind: "bounded", text: "Use a smaller benchmark." },
        informationGaps: ["Need one measured run time."],
        evidence: [{
          id: "k1",
          kind: "knowledge",
          path: "knowledge/example/index.qmd",
          locator: "section",
          summary: "Trusted basis.",
        }],
      },
    },
    computed: {
      scores: {
        researchValue: { min: 60, estimate: 80, max: 100 },
        autoresearchSuitability: { min: 40, estimate: 60, max: 80 },
        combined: { min: 48, estimate: 68.57, max: 88.89 },
      },
      verdict: { label: "REFRAME" },
    },
  });
  assert.match(html, /^<!doctype html>/);
  assert.match(html, /Content-Security-Policy/);
  assert.match(html, /Research Value Audit/);
  assert.match(html, /Autoresearch Fit Audit/);
  assert.match(html, /Evidence Appendix/);
  assert.match(html, /Fixture &lt;problem&gt;/);
  assert.match(html, /<strong>Research Value<\/strong><br>80 \(60-100\)<\/div>/);
  assert.match(html, /<strong>Autoresearch Suitability<\/strong><br>60 \(40-80\)<\/div>/);
  assert.match(html, /<strong>Combined<\/strong><br>68\.57 \(48-88\.89\)<\/div>/);
  assert.doesNotMatch(html, /<script/i);
  assert.doesNotMatch(html, /https?:\/\//i);
});

test("renders v2 valuation audit sections with safe links and private redaction", () => {
  const html = renderAssessmentReport({
    run: { runId: "20260729T010203Z-a1b2c3", problemId: "Prob-001" },
    input: {
      schemaVersion: 2,
      policyVersion: 2,
      problemId: "Prob-001",
      problemTitle: "Quantum fixture",
      problemJsonHash: "a".repeat(64),
      problemMdHash: "b".repeat(64),
      skillHash: "c".repeat(64),
      schemaHash: "d".repeat(64),
      resolver: { query: "Fixture", status: "match", topic: "knowledge/example/index.qmd", orderedFiles: ["knowledge/example/index.qmd"] },
      bundle: [{ path: "knowledge/example/index.qmd", hash: "e".repeat(64) }],
      valuation: {
        snapshotId: "20260729T010203Z-0123456789ab",
        contentHash: "f".repeat(64),
        snapshotHash: "1".repeat(64),
        freshness: { advisory: true, staleClasses: ["market"], details: { market: { stale: true } } },
        recalculationInputs: {
          papers: [{
            id: "W1",
            title: "Anchor paper",
            doi: "10.1234/quantum.fixture",
            sourceUrl: "https://example.test/paper",
            citedByCount: 42,
          }],
          manifest: {
            confirmedCandidate: {
              technicalStages: [{ id: "stage-1", description: "Run the benchmark stage." }],
              classicalBaseline: { description: "GPU simulation baseline.", sourceUrl: "https://example.test/baseline" },
              atomicInputs: [{
                id: "throughput",
                state: "known",
                interval: { low: 1, base: 2, high: 3 },
                unit: "hours",
                visibility: "public",
              }],
              materialAssumptions: [{ id: "assumption-1", question: "Will users adopt it?", confirmationRequired: true }],
            },
          },
          marketEvidence: [{
            id: "market-1",
            state: "known",
            interval: { low: 1_000_000, base: 2_000_000, high: 3_000_000 },
            unit: "USD_2026",
            currency: "USD",
            priceBaseYear: 2026,
            visibility: "public",
            sources: [{ id: "src-1", url: "javascript:alert(1)", locator: "bad", kind: "news" }],
          }],
        },
      },
    },
    envelope: {
      language: "en",
      assessment: {
        schemaVersion: 2,
        normalizedProblem: "Quantum fixture",
        verdict: { label: "DO_NOW", provisional: false, possibleLabels: ["DO_NOW"] },
        recommendation: "proceed",
        confidence: { level: "medium", rationale: "Quantitative evidence is snapshot-bound." },
        dimensions: {
          researchValue: [{
            id: "importance",
            label: "Importance",
            weight: 20,
            score: { min: 4, estimate: 4, max: 4 },
            evidenceState: "supported",
            rationale: "Important.",
            evidenceRefs: ["k1"],
          }],
          autoresearchSuitability: [{
            id: "attempt_runtime",
            label: "Attempt runtime",
            weight: 10,
            score: { min: 4, estimate: 4, max: 4 },
            evidenceState: "supported",
            rationale: "Fast enough.",
            evidenceRefs: ["k1"],
          }],
        },
        largestBottleneck: "No bottleneck.",
        recommendedReframe: { kind: "none", text: "No reframe." },
        informationGaps: [],
        evidence: [{ id: "k1", kind: "knowledge", path: "knowledge/example/index.qmd", locator: "section", summary: "Trusted basis." }],
        quantitativeEvidence: {
          snapshot: { snapshotId: "20260729T010203Z-0123456789ab", contentHash: "f".repeat(64), freshness: "fresh", visibility: "private" },
          scientificAttention: {
            value: { state: "known", interval: { low: 72, base: 80, high: 91 }, unit: "percent", visibility: "public" },
            momentum: { state: "known", interval: { low: 0.1, base: 0.2, high: 0.3 }, unit: "fraction", visibility: "public" },
            coverage: 0.8,
            concentration: 0.2,
            warnings: [],
          },
          technicalFeasibility: { state: "known", interval: { low: 0.2, base: 0.35, high: 0.5 }, unit: "fraction", visibility: "public" },
          socialValue: { state: "known", interval: { low: 1_000_000, base: 2_500_000, high: 4_000_000 }, unit: "USD_2026", currency: "USD", priceBaseYear: 2026, visibility: "public" },
          capturableValue: { state: "known", interval: { low: 999_999_999, base: 999_999_999, high: 999_999_999 }, unit: "USD_2026", currency: "USD", priceBaseYear: 2026, visibility: "private" },
          informationValue: { state: "unknown", reason: "No sample-information model." },
          scoreAnchors: [{ dimensionId: "importance", recommended: { min: 4, estimate: 4, max: 4 }, evidenceIds: ["scientific-attention"], override: null }],
          sensitivity: [{ id: "success", label: "Technical success", swing: 12 }],
          assumptions: ["Market conversion is approximate."],
          warnings: ["market evidence may be stale"],
        },
      },
    },
    computed: {
      scores: {
        researchValue: { min: 80, estimate: 80, max: 80 },
        autoresearchSuitability: { min: 80, estimate: 80, max: 80 },
        combined: { min: 80, estimate: 80, max: 80 },
      },
      verdict: { label: "DO_NOW" },
    },
  });

  assert.match(html, /External valuation evidence/);
  assert.match(html, /20260729T010203Z-0123456789ab/);
  assert.match(html, /Snapshot hash/);
  assert.match(html, /Anchor papers/);
  assert.match(html, /href="https:\/\/example\.test\/paper"/);
  assert.match(html, /href="https:\/\/doi\.org\/10\.1234\/quantum\.fixture"/);
  assert.match(html, /Stage tree/);
  assert.match(html, /Classical baseline/);
  assert.match(html, /Atomic assumptions/);
  assert.match(html, /Scenario intervals/);
  assert.match(html, /Score anchors/);
  assert.match(html, /Sensitivity/);
  assert.match(html, /market evidence may be stale/);
  assert.match(html, /Private/);
  assert.doesNotMatch(html, /999999999/);
  assert.doesNotMatch(html, /javascript:/i);
  assert.doesNotMatch(html, /<script/i);
});
