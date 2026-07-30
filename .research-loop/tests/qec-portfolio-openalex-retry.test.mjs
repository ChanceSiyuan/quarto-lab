import assert from "node:assert/strict";
import test from "node:test";

import { createRetryingOpenAlexClient } from "../../src/lib/qec-portfolio/openalex-retry.mjs";

test("retries only transient OpenAlex provider failures with exponential delays", async () => {
  let calls = 0;
  const delays = [];
  const client = createRetryingOpenAlexClient({
    client: { expand: async () => {
      calls += 1;
      if (calls < 3) throw Object.assign(new Error("temporary outage"), { code: "OPENALEX_PROVIDER_ERROR" });
      return [{ id: "W1" }];
    }},
    delay: async (milliseconds) => { delays.push(milliseconds); },
  });
  assert.deepEqual(await client.expand({ anchors: ["doi:10.1/example"] }), [{ id: "W1" }]);
  assert.equal(calls, 3);
  assert.deepEqual(delays, [2_000, 4_000]);
});

test("does not retry a missing OpenAlex key", async () => {
  let calls = 0;
  const error = Object.assign(new Error("key required"), { code: "OPENALEX_KEY_REQUIRED" });
  const client = createRetryingOpenAlexClient({
    client: { expand: async () => { calls += 1; throw error; } },
    delay: async () => assert.fail("missing key must not be retried"),
  });
  await assert.rejects(client.expand({}), (caught) => caught === error);
  assert.equal(calls, 1);
});
