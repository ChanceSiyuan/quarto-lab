import assert from "node:assert/strict";
import test from "node:test";

import {
  assessmentStatusCopy,
  formatScoreInterval,
  isLocalAssessmentUnavailable,
  latestAssessmentSummary,
} from "../lib/assessments/view-model.mjs";

test("formats score intervals compactly", () => {
  assert.equal(formatScoreInterval({ min: 60, estimate: 72.5, max: 80 }), "72.5 (60-80)");
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

test("treats 404 and fetch failure as local-unavailable for static output", () => {
  assert.equal(isLocalAssessmentUnavailable({ status: 404 }), true);
  assert.equal(isLocalAssessmentUnavailable(new TypeError("fetch failed")), true);
});
