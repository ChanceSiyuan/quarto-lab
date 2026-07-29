import assert from "node:assert/strict";
import test from "node:test";

import { buildTrialRef, parseAutoqecReport } from "../../src/lib/problems/autoqec-css-distance/reports.mjs";

const report001 = `# CSS Distance Proposal 001 Report

## Overview

- Proposal: \`001\` of \`100\`
- Branch: \`autoresearch/css-distance/run100-proposal-001\`
- Candidate: \`proposal-workspace/candidate.py\`
- Objective: randomized CSS logical-operator witness search for an upper-bound certificate.
- Per-process hard timeout: \`300s\`

## Method

The assigned exploration direction was **randomized kernel sampling with stabilizer-coset descent**.

## Public Contract Check

Status: **passed**.

## Blinded Development Screening

| Metric | Value |
| --- | ---: |
| Decision | rejected |
| Runs | 24 |
| Verified witnesses | 12 |
| Target hits | 12 |
| Timeouts | 0 |
| Crashes | 0 |
| Invalid claims | 12 |
| Weighted target hits | 12 |
| Normalized quality | 0.5 |
| Runtime seconds | 4.705462539917789 |
`;

const report101 = `# CSS Distance Proposal 101 Report

## Method

The assigned exploration direction was **Proposal contract failure**.

## Public Contract

| Field | Value |
| --- | ---: |
| Proposal total | 200 |
| Branch | autoresearch/css-distance/run200-proposal-101 |
| Public contract status | failed |
| Timeout seconds | 300 |
| Proposal image ID | sha256:3892c207c48f8e5a7c1953b127e59b4d9fd7203a4ccd412f3b59290362c73d53 |
| Evaluator image ID | sha256:bf017fcb8296dedb434117714c4f43ee01f74ab5c349dd6488d6ea0ceaa1f62c |

## Blinded Development Screening

| Metric | Value |
| --- | ---: |
| Decision | rejected |
| Runs | 0 |
| Verified witnesses | 0 |
| Target hits | 0 |
| Timeouts | 0 |
| Crashes | 0 |
| Invalid claims | 1 |
| Weighted target hits | 0 |
| Normalized quality | 0.000000000000000 |
| Runtime seconds | 0.000000000000000 |
| Average seconds | not run |
| Median seconds | not run |
| P95 seconds | not run |
`;

const report200 = report101
  .replaceAll("101", "200")
  .replace("Proposal contract failure", "Randomized CSS kernel-combination search")
  .replace("failed", "passed")
  .replace("| Runs | 0 |", "| Runs | 24 |")
  .replace("| Verified witnesses | 0 |", "| Verified witnesses | 13 |")
  .replace("| Target hits | 0 |", "| Target hits | 13 |")
  .replace("| Invalid claims | 1 |", "| Invalid claims | 11 |")
  .replace("| Weighted target hits | 0 |", "| Weighted target hits | 13 |")
  .replace("| Normalized quality | 0.000000000000000 |", "| Normalized quality | 0.541666666666667 |")
  .replace("| Runtime seconds | 0.000000000000000 |", "| Runtime seconds | 85.783838119939901 |")
  .replace("| Average seconds | not run |", "| Average seconds | 3.574326588330829 |")
  .replace("| Median seconds | not run |", "| Median seconds | 2.232983041496482 |")
  .replace("| P95 seconds | not run |", "| P95 seconds | 9.437287125037983 |");

const report063 = report001
  .replace("001", "063")
  .replace("run100-proposal-001", "run100-proposal-063")
  .replace("**passed**", "**not-run**");

test("maps proposal numbers to the exact AutoQEC trial refs", () => {
  assert.equal(buildTrialRef(1), "autoresearch/css-distance/run100-proposal-001");
  assert.equal(buildTrialRef(100), "autoresearch/css-distance/run100-proposal-100");
  assert.equal(buildTrialRef(101), "autoresearch/css-distance/run200-proposal-101");
  assert.equal(buildTrialRef(200), "autoresearch/css-distance/run200-proposal-200");
});

test("parses legacy 001-100 reports with legacy timing", () => {
  const parsed = parseAutoqecReport(report001, { proposalNumber: 1 });

  assert.equal(parsed.branch, "autoresearch/css-distance/run100-proposal-001");
  assert.equal(parsed.candidateSourcePath, "proposal-workspace/candidate.py");
  assert.equal(parsed.publicContract, "passed");
  assert.equal(parsed.methodDescription, "randomized kernel sampling with stabilizer-coset descent");
  assert.equal(parsed.metrics.runs, 24);
  assert.equal(parsed.metrics.runtimeSeconds, 4.705462539917789);
  assert.equal(parsed.metrics.averageSeconds, null);
  assert.equal(parsed.metrics.timingStatus, "legacy-not-recorded");
});

test("parses failed public-contract reports as not-run missing-candidate attempts", () => {
  const parsed = parseAutoqecReport(report101, { proposalNumber: 101 });

  assert.equal(parsed.branch, "autoresearch/css-distance/run200-proposal-101");
  assert.equal(parsed.publicContract, "failed");
  assert.equal(parsed.candidateSourcePath, null);
  assert.equal(parsed.metrics.runs, 0);
  assert.equal(parsed.metrics.runtimeSeconds, null);
  assert.equal(parsed.metrics.timingStatus, "not-run");
});

test("parses the real not-run public-contract status", () => {
  const parsed = parseAutoqecReport(report063, { proposalNumber: 63 });

  assert.equal(parsed.branch, "autoresearch/css-distance/run100-proposal-063");
  assert.equal(parsed.publicContract, "not-run");
});

test("parses recorded timing in 101-200 reports", () => {
  const parsed = parseAutoqecReport(report200, { proposalNumber: 200 });

  assert.equal(parsed.publicContract, "passed");
  assert.equal(parsed.metrics.runs, 24);
  assert.equal(parsed.metrics.verifiedWitnesses, 13);
  assert.equal(parsed.metrics.averageSeconds, 3.574326588330829);
  assert.equal(parsed.metrics.medianSeconds, 2.232983041496482);
  assert.equal(parsed.metrics.p95Seconds, 9.437287125037983);
  assert.equal(parsed.metrics.timingStatus, "recorded");
});
