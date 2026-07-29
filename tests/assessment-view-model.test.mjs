import assert from "node:assert/strict";
import test from "node:test";

import * as viewModel from "../lib/assessments/view-model.mjs";

const {
  assessmentStatusCopy,
  formatKnownInterval,
  formatMoneyInterval,
  formatScoreInterval,
  isLocalAssessmentUnavailable,
  latestAssessmentSummary,
  valuationStatusCopy,
} = viewModel;

test("formats score intervals compactly", () => {
  assert.equal(formatScoreInterval({ min: 60, estimate: 72.5, max: 80 }), "72.5 (60-80)");
});

test("formats unknown and private quantitative values without fake zeroes", () => {
  assert.equal(formatKnownInterval({ state: "unknown", reason: "No comparable papers." }), "Unknown");
  assert.equal(formatMoneyInterval({ visibility: "private", redacted: true }), "Private");
});

test("formats scientific attention, probability, and money intervals", () => {
  assert.equal(formatKnownInterval({
    state: "known",
    interval: { low: 72, base: 80, high: 91 },
    unit: "percent",
  }), "80% (72-91%)");
  assert.equal(formatKnownInterval({
    state: "known",
    interval: { low: 0.2, base: 0.35, high: 0.5 },
    unit: "fraction",
  }), "35% (20-50%)");
  assert.equal(formatMoneyInterval({
    state: "known",
    interval: { low: 1_000_000, base: 2_500_000, high: 4_000_000 },
    unit: "USD_2026",
    currency: "USD",
    priceBaseYear: 2026,
  }), "$2.5M ($1.0M-$4.0M, USD 2026)");
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
