import assert from "node:assert/strict";
import test from "node:test";

import { createOpenAlexClient } from "../lib/valuations/openalex-client.mjs";

function work(overrides = {}) {
  return {
    id: "https://openalex.org/W123",
    doi: "https://doi.org/10.1234/example",
    title: "Quantum error correction with neutral atoms",
    publication_year: 2024,
    topics: [{ id: "https://openalex.org/T7" }],
    cited_by_count: 8,
    citation_normalized_percentile: { value: 0.8 },
    counts_by_year: [{ year: 2025, cited_by_count: 3 }],
    referenced_works: ["https://openalex.org/W456"],
    abstract_inverted_index: { Quantum: [0], error: [1], correction: [2], atoms: [3] },
    ...overrides,
  };
}

function json(value, { ok = true, status = 200 } = {}) {
  return { ok, status, json: async () => value };
}

function fakeOpenAlexFetch() {
  const calls = [];
  const fetchFn = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    if (String(url).includes("/works/W123")) return json(work());
    if (String(url).includes("/works/https%3A%2F%2Fdoi.org%2F10.1234%2Fexample")) return json(work());
    if (String(url).includes("filter=cites%3AW123")) return json({ results: [work({ id: "https://openalex.org/W456", doi: null, title: "Neighbor paper" })] });
    if (String(url).includes("filter=topics.id%3AT7")) return json({ results: [work(), work({ id: "https://openalex.org/W789", doi: "https://doi.org/10.9999/topic" })] });
    return json({ results: [] });
  };
  fetchFn.calls = calls;
  return fetchFn;
}

test("deduplicates DOI and OpenAlex aliases into one paper", async () => {
  const fetchFn = fakeOpenAlexFetch();
  const client = createOpenAlexClient({ fetchFn, apiKey: "test-key", maxWorks: 100 });
  const papers = await client.expand({
    anchors: ["https://doi.org/10.1234/example", "W123"],
    topicIds: ["T7"],
    normalizedProblem: "quantum error correction",
  });
  assert.equal(papers.filter((paper) => paper.id === "W123").length, 1);
  assert.equal("fullText" in papers[0], false);
  assert.equal("abstract" in papers[0], false);
  assert.equal(papers[0].abstractHash.length, 64);
  assert.deepEqual(papers[0].matchedProblemTokens, ["correction", "error", "quantum"]);
  assert.deepEqual(papers.map((paper) => paper.id), [...papers].map((paper) => paper.id).sort());
  assert.ok(fetchFn.calls.some((call) => call.url.includes("filter=cites%3AW123")));
  assert.ok(fetchFn.calls.some((call) => call.url.includes("filter=topics.id%3AT7")));
});

test("bounds expansion, supplies abort signals, and reports provider failures", async () => {
  const fetchFn = async (_url, options) => {
    assert.ok(options.signal instanceof AbortSignal);
    return json({ results: Array.from({ length: 101 }, (_, index) => work({ id: `https://openalex.org/W${index}` })) });
  };
  const client = createOpenAlexClient({ fetchFn, apiKey: "test-key", maxWorks: 100 });
  const papers = await client.expand({ anchors: [], topicIds: ["T7"], normalizedProblem: "quantum" });
  assert.equal(papers.length, 100);

  const failing = createOpenAlexClient({ fetchFn: async () => json({}, { ok: false, status: 429 }), apiKey: "test-key" });
  await assert.rejects(failing.expand({ anchors: ["W123"], topicIds: [] }), (error) => error.code === "OPENALEX_PROVIDER_ERROR" && error.status === 429);

  const noKey = createOpenAlexClient();
  await assert.rejects(noKey.expand({ anchors: [], topicIds: [] }), (error) => error.code === "OPENALEX_KEY_REQUIRED");

  const fixtureClient = createOpenAlexClient({ fetchFn: async () => json({ results: [work()] }) });
  const fixturePapers = await fixtureClient.expand({ anchors: [], topicIds: ["T7"], normalizedProblem: "quantum" });
  assert.equal(fixturePapers.length, 1);
});
