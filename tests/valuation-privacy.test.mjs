import assert from "node:assert/strict";
import test from "node:test";

import { evaluateValuationFreshness } from "../lib/valuations/freshness.mjs";
import { assertPublicSafeValuation, propagateVisibility, redactPrivate } from "../lib/valuations/privacy.mjs";

test("freshness is advisory and class-specific", () => {
  const result = evaluateValuationFreshness({
    manifest: { createdAt: "2026-01-01T00:00:00Z" },
    evidenceDates: {
      citation: "2026-01-01T00:00:00Z",
      hardware: "2026-06-01T00:00:00Z",
      market: "2026-01-01T00:00:00Z",
    },
  }, new Date("2026-07-01T00:00:00Z"));
  assert.deepEqual(result.staleClasses, ["citation", "market"]);
  assert.equal(result.advisory, true);
});

test("freshness respects government publication schedules and leaves private inputs unexpired", () => {
  const result = evaluateValuationFreshness({
    manifest: { createdAt: "2026-01-01T00:00:00Z" },
    evidenceDates: {
      hardware: { date: "2025-01-01T00:00:00Z", nextPublicationAt: "2026-08-01T00:00:00Z", government: true },
      market: { date: "2025-01-01T00:00:00Z", visibility: "private" },
    },
  }, new Date("2026-07-01T00:00:00Z"));
  assert.deepEqual(result.staleClasses, []);
});

test("private input makes a dependent output private", () => {
  assert.equal(propagateVisibility([
    { visibility: "public" },
    { visibility: "private" },
  ]), "private");
  assert.throws(() => assertPublicSafeValuation({ visibility: "private", value: 42 }), /private/i);
  assert.deepEqual(redactPrivate({ visibility: "private", value: 42 }), {
    visibility: "private",
    redacted: true,
  });
});

test("redaction removes all sensitive fields from every private subtree", () => {
  const redacted = redactPrivate({
    visibility: "public",
    publicValue: 7,
    nested: {
      visibility: "private",
      value: 42,
      interval: { low: 1, base: 2, high: 3 },
      currency: "USD",
      derivation: { formulaId: "secret", inputIds: ["x"] },
      keep: "marker",
    },
  });
  assert.deepEqual(redacted, {
    visibility: "public",
    publicValue: 7,
    nested: { visibility: "private", redacted: true, keep: "marker" },
  });
  assert.doesNotThrow(() => assertPublicSafeValuation(redacted));
});
