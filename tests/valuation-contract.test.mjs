import assert from "node:assert/strict";
import test from "node:test";

import { validateAtomicEvidence, validateQuantitativeEvidence } from "../lib/valuations/contract.mjs";
import { knownInterval, unknownValue } from "../lib/valuations/types.mjs";

function source(id, kind = "contract") {
  return { id, url: `https://example.test/${id}`, locator: "section 2", kind };
}

function knownEvidence(overrides = {}) {
  return {
    id: "cost-1",
    state: "known",
    interval: { low: 0, base: 0, high: 0 },
    unit: "USD_2026",
    visibility: "public",
    evidenceState: "reported",
    evidenceTier: "primary",
    sourceIds: ["src-1"],
    sources: [source("src-1")],
    currency: "USD",
    priceBaseYear: 2026,
    conversionSourceId: "src-1",
    ...overrides,
  };
}

test("distinguishes a known zero from missing evidence", () => {
  assert.equal(validateAtomicEvidence(knownEvidence()).ok, true);
  assert.deepEqual(unknownValue("No public contract price."), {
    state: "unknown",
    reason: "No public contract price.",
  });
});

test("accepts a bounded Scientific Demand Score unit", () => {
  const { currency: _currency, priceBaseYear: _priceBaseYear, conversionSourceId: _conversionSourceId, ...demand } = knownEvidence({
    interval: { low: 56.5, base: 56.5, high: 56.5 },
    unit: "score-100",
  });
  assert.equal(validateAtomicEvidence(demand).ok, true);
});

test("constructs known intervals without dropping private visibility or source IDs", () => {
  assert.deepEqual(knownInterval({
    low: 1,
    base: 2,
    high: 3,
    unit: "hours",
    visibility: "private",
    sourceIds: ["private-contract"],
  }), {
    state: "known",
    interval: { low: 1, base: 2, high: 3 },
    unit: "hours",
    visibility: "private",
    sourceIds: ["private-contract"],
  });
});

test("rejects non-finite or unordered intervals and extra fields", () => {
  for (const value of [
    knownEvidence({ interval: { low: 2, base: 1, high: 3 } }),
    knownEvidence({ interval: { low: 0, base: Number.NaN, high: 3 } }),
    knownEvidence({ unexpected: true }),
  ]) assert.equal(validateAtomicEvidence(value).ok, false);
});

test("requires complete provenance and valid evidence classification", () => {
  for (const value of [
    knownEvidence({ sources: [source("src-1", "contract"), { ...source("src-2"), locator: "" }] }),
    knownEvidence({ sourceIds: ["src-1", "src-1"] }),
    knownEvidence({ evidenceTier: "unverified" }),
    knownEvidence({ evidenceState: "estimated" }),
  ]) assert.equal(validateAtomicEvidence(value).ok, false);
});

test("requires derivation inputs for inferred evidence", () => {
  const invalid = knownEvidence({ evidenceState: "inferred" });
  assert.equal(validateAtomicEvidence(invalid).ok, false);
  assert.equal(validateAtomicEvidence(knownEvidence({
    evidenceState: "inferred",
    derivation: { formulaId: "cost-rollup-v1", inputIds: ["cost-a", "cost-b"] },
  })).ok, true);
});

test("requires currency metadata and evidence-backed capture share", () => {
  assert.equal(validateAtomicEvidence(knownEvidence({ currency: undefined })).ok, false);
  const captureShare = {
    id: "capture-share",
    state: "known",
    unit: "fraction",
    interval: { low: 0.1, base: 0.2, high: 0.3 },
    visibility: "public",
    evidenceState: "reported",
    evidenceTier: "primary",
    sourceIds: ["src-1"],
  };
  assert.equal(validateAtomicEvidence({
    ...captureShare,
    sources: [source("src-1", "news")],
  }).ok, false);
  assert.equal(validateAtomicEvidence({
    ...captureShare,
    sources: [source("src-1", "licensing")],
  }).ok, true);
});

test("validates unique aggregate IDs and all declared cross-references", () => {
  const valid = {
    sources: [source("src-1")],
    inputs: [{
      id: "cost-1",
      state: "known",
      interval: { low: 0, base: 0, high: 0 },
      unit: "hours",
      visibility: "public",
      evidenceState: "reported",
      evidenceTier: "primary",
      sourceIds: ["src-1"],
      sources: [source("src-1")],
    }],
    stages: [{ id: "stage-1", inputIds: ["cost-1"], outputIds: ["out-1"], sourceIds: ["src-1"] }],
    outputs: [{ id: "out-1", inputIds: ["cost-1"], sourceIds: ["src-1"] }],
    assumptions: [{ id: "assumption-1", inputIds: ["cost-1"], sourceIds: ["src-1"] }],
    scoreAnchors: [{ id: "anchor-1", outputIds: ["out-1"], sourceIds: ["src-1"] }],
  };
  assert.equal(validateQuantitativeEvidence(valid).ok, true);
  assert.equal(validateQuantitativeEvidence({ ...valid, sources: [source("src-1"), source("src-1")] }).ok, false);
  assert.equal(validateQuantitativeEvidence({ ...valid, stages: [{ id: "stage-1", inputIds: ["missing"], sourceIds: ["src-1"] }] }).ok, false);
  assert.equal(validateQuantitativeEvidence({ ...valid, scoreAnchors: [{ id: "anchor-1", outputIds: ["missing"], sourceIds: ["src-1"] }] }).ok, false);
});

test("accepts identified unknown inputs without treating them as zero", () => {
  const result = validateQuantitativeEvidence({
    sources: [],
    inputs: [{ id: "unavailable-market-price", ...unknownValue("No public contract price.") }],
    stages: [],
    outputs: [],
    assumptions: [],
    scoreAnchors: [],
  });
  assert.equal(result.ok, true);
  assert.deepEqual(result.value.inputs[0], {
    id: "unavailable-market-price",
    state: "unknown",
    reason: "No public contract price.",
  });
  assert.equal(validateAtomicEvidence({
    id: "unavailable-market-price",
    ...unknownValue("No public contract price."),
    unit: "USD_2026",
  }).ok, false);
});
