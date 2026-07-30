import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import * as viewModel from "../lib/assessments/view-model.mjs";

const CJK_RE = /[\u3400-\u9fff]/;

const {
  assessmentStatusCopy,
  assessmentScoreMetrics,
  evidenceStateCopy,
  formatKnownInterval,
  formatCommercialInvestmentProxy,
  formatIndustrySocialProxy,
  formatMoneyInterval,
  formatScientificAttention,
  formatScoreInterval,
  formatTechnicalSuccessEstimate,
  isLocalAssessmentUnavailable,
  latestAssessmentSummary,
  valuationStatusCopy,
} = viewModel;

test("formats assessment scores as one point value", () => {
  assert.equal(formatScoreInterval({ min: 52, estimate: 72.5, max: 88.75 }), "72.5");
});

test("names assessment score tracks with explicit labels", () => {
  assert.deepEqual(assessmentScoreMetrics.map((item) => [item.key, item.label, item.shortLabel]), [
    ["researchValue", "Research Value", "V"],
    ["autoresearchSuitability", "Autoresearch Fit", "A"],
    ["combined", "Combined Priority", "S"],
  ]);
  assert.equal(assessmentScoreMetrics.every((item) => item.description.length > 20), true);
  assert.equal(assessmentScoreMetrics.every((item) => !CJK_RE.test(`${item.label} ${item.description}`)), true);
});

test("assessment panel does not render bare VAS labels", async () => {
  const source = await readFile(new URL("../app/problems/[id]/assessment-panel.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(source, /<dt>V<\/dt>/);
  assert.doesNotMatch(source, /<dt>A<\/dt>/);
  assert.doesNotMatch(source, /<dt>S<\/dt>/);
  assert.match(source, /assessmentScoreMetrics/);
  assert.match(source, /Commercial investment proxy/);
  assert.doesNotMatch(source, /Capturable value/);
});

test("labels evidence states by actionability rather than raw unknown", () => {
  assert.equal(evidenceStateCopy("supported", "importance"), "Supported");
  assert.equal(evidenceStateCopy("inferred", "importance"), "Inferred");
  assert.equal(evidenceStateCopy("unknown", "gap_and_novelty"), "Needs evidence");
  assert.equal(evidenceStateCopy("unknown", "generality_and_publication"), "Needs preregistration");
  assert.equal(evidenceStateCopy("unknown", "expected_value_relative_to_cost"), "Needs valuation model");
  assert.equal([
    evidenceStateCopy("supported", "importance"),
    evidenceStateCopy("inferred", "importance"),
    evidenceStateCopy("unknown", "gap_and_novelty"),
    evidenceStateCopy("unknown", "generality_and_publication"),
    evidenceStateCopy("unknown", "expected_value_relative_to_cost"),
  ].every((copy) => !CJK_RE.test(copy)), true);
});

test("formats unknown and private quantitative values without fake zeroes", () => {
  assert.equal(formatKnownInterval({ state: "unknown", reason: "No comparable papers." }), "Evidence gap — No comparable papers.");
  assert.equal(formatMoneyInterval({ state: "unknown", reason: "No pricing model." }), "Evidence gap — No pricing model.");
  assert.equal(formatMoneyInterval({ visibility: "private", redacted: true }), "Private");
});

test("formats Scientific Demand Score, probability, and money as point values", () => {
  assert.equal(formatKnownInterval({
    state: "known",
    interval: { low: 72, base: 80, high: 91 },
    unit: "percent",
  }), "80%");
  assert.equal(formatKnownInterval({
    state: "known",
    interval: { low: 0.2, base: 0.35, high: 0.5 },
    unit: "fraction",
  }), "35%");
  assert.equal(formatScientificAttention({
    state: "known",
    interval: { low: 68.4, base: 68.4, high: 68.4 },
    unit: "score-100",
    evidenceConfidence: "high",
  }), "68.4 / 100 · High evidence confidence");
  assert.equal(formatScientificAttention({
    state: "known",
    interval: { low: 0, base: 0, high: 0 },
    unit: "count",
  }), "No matched citations");
  assert.equal(formatMoneyInterval({
    state: "known",
    interval: { low: 1_000_000, base: 2_500_000, high: 4_000_000 },
    unit: "USD_2026",
    currency: "USD",
    priceBaseYear: 2026,
  }), "$2.5M · USD 2026");
});

test("formats modeled technical success and economic proxies as point values", () => {
  assert.equal(
    formatTechnicalSuccessEstimate({
      state: "known",
      interval: { low: 64.8, base: 64.8, high: 64.8 },
      unit: "percent",
      estimateKind: "model",
    }),
    "64.8% · Model estimate",
  );
  assert.equal(formatTechnicalSuccessEstimate({ state: "unknown", reason: "No model." }), "—");
  assert.equal(formatIndustrySocialProxy({ state: "unknown", reason: "No model." }), "$57B · USD 2035");
  assert.equal(formatCommercialInvestmentProxy({ state: "unknown", reason: "No pricing model." }), "$10B · USD 2026");
});

test("provides copy for valuation workflow states", () => {
  assert.equal(valuationStatusCopy({ kind: "no_evidence" }).actionLabel, "Research evidence");
  assert.equal(valuationStatusCopy({ kind: "researching" }).actionLabel, null);
  assert.equal(valuationStatusCopy({ kind: "needs_confirmation" }).actionLabel, "Review assumptions");
  assert.equal(valuationStatusCopy({ kind: "ready" }).actionLabel, "Run assessment");
  assert.equal(valuationStatusCopy({ kind: "stale" }).actionLabel, "Refresh evidence");
  assert.equal(valuationStatusCopy({ kind: "research_failed" }).actionLabel, "Retry research");
});

test("provides copy for every panel state", () => {
  assert.equal(assessmentStatusCopy({ kind: "never" }).actionLabel, "Run assessment");
  assert.equal(assessmentStatusCopy({ kind: "queued", queuePosition: 2 }).heading, "Assessment queued");
  assert.equal(assessmentStatusCopy({ kind: "running", elapsedSeconds: 42 }).heading, "Assessment running");
  assert.equal(assessmentStatusCopy({ kind: "needs-input" }).heading, "Knowledge match needs input");
  assert.equal(assessmentStatusCopy({ kind: "completed" }).heading, "Assessment complete");
  assert.equal(assessmentStatusCopy({ kind: "failed" }).actionLabel, "Retry");
  assert.equal(assessmentStatusCopy({ kind: "stale" }).actionLabel, "Run new assessment");
  assert.equal(assessmentStatusCopy({ kind: "unavailable" }).heading, "Local assessment unavailable");
});

test("selects latest completed summary without mutating lifecycle", () => {
  const summary = latestAssessmentSummary({
    runs: [
      { runId: "20260728T010203Z-a1b2c3", status: "failed" },
      { runId: "20260728T010204Z-a1b2c3", status: "completed", summary: { verdict: "DEFER", lifecycleMutation: false } },
    ],
  });
  assert.equal(summary.verdict, "DEFER");
  assert.equal(summary.lifecycleMutation, false);
});

test("a newer failed rerun takes precedence over an older completed summary", () => {
  assert.equal(typeof viewModel.assessmentStateFromProblemResponse, "function");
  const state = viewModel.assessmentStateFromProblemResponse({
    latest: { verdict: "DO_NOW", reportHref: "/older-report" },
    runs: [
      { runId: "20260728T010204Z-a1b2c3", status: "failed", error: { message: "Codex exited." } },
      { runId: "20260728T010203Z-a1b2c3", status: "completed", summary: { verdict: "DO_NOW" } },
    ],
  });

  assert.equal(state.kind, "failed");
  assert.equal(state.reason, "Codex exited.");
  assert.equal(state.latest.verdict, "DO_NOW");
});

test("treats 404 and fetch failure as local-unavailable for static output", () => {
  assert.equal(isLocalAssessmentUnavailable({ status: 404 }), true);
  assert.equal(isLocalAssessmentUnavailable(new TypeError("fetch failed")), true);
});

test("surfaces the local service code and actionable message", async () => {
  assert.equal(typeof viewModel.assessmentServiceFailure, "function");
  const state = await viewModel.assessmentServiceFailure(new Response(JSON.stringify({
    code: "CODEX_PREFLIGHT",
    message: "Run codex login before starting an assessment.",
  }), {
    status: 400,
    headers: { "content-type": "application/json" },
  }));

  assert.deepEqual(state, {
    kind: "failed",
    reason: "Run codex login before starting an assessment. (CODEX_PREFLIGHT)",
  });
});
