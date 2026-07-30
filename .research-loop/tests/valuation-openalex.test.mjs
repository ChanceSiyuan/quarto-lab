import assert from "node:assert/strict";
import test from "node:test";

import { createOpenAlexClient } from "../../src/lib/valuations/openalex-client.mjs";

function work(overrides = {}) {
  return {
    id: "https://openalex.org/W123",
    doi: "https://doi.org/10.1234/example",
    title: "Quantum error correction with neutral atoms",
    publication_year: 2024,
    topics: [{ id: "https://openalex.org/T7" }],
    cited_by_count: 8,
    citation_normalized_percentile: { value: 0.8 },
    fwci: 2.4,
    authorships: [
      {
        author: { id: "https://openalex.org/A1" },
        institutions: [{ id: "https://openalex.org/I1" }],
      },
      {
        author: { id: "https://openalex.org/A2" },
        institutions: [
          { id: "https://openalex.org/I1" },
          { id: "https://openalex.org/I2" },
        ],
      },
    ],
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
  assert.equal(papers[0].fwci, 2.4);
  assert.deepEqual(papers[0].authorIds, ["A1", "A2"]);
  assert.deepEqual(papers[0].institutionIds, ["I1", "I2"]);
  assert.equal(papers[0].matchConfidence, 1);
  assert.deepEqual(papers[0].matchedProblemTokens, ["correction", "error", "quantum"]);
  assert.deepEqual(papers.map((paper) => paper.id), [...papers].map((paper) => paper.id).sort());
  assert.ok(fetchFn.calls.some((call) => call.url.includes("filter=cites%3AW123")));
  assert.ok(fetchFn.calls.some((call) => call.url.includes("filter=topics.id%3AT7")));
});

test("canonicalizes duplicate DOI and normalized-title records", async () => {
  const fetchFn = async (url) => {
    const target = String(url);
    if (target.includes("filter=topics.id%3AT7")) return json({
      results: [
        work({
          id: "https://openalex.org/W810",
          doi: "https://doi.org/10.1000/QEC",
          counts_by_year: [{ year: 2025, cited_by_count: 2 }],
        }),
        work({
          id: "https://openalex.org/W811",
          doi: "https://doi.org/10.1000/qec",
          counts_by_year: [
            { year: 2024, cited_by_count: 2 },
            { year: 2025, cited_by_count: 3 },
          ],
        }),
        work({
          id: "https://openalex.org/W812",
          doi: null,
          title: "Fault-tolerant quantum error correction!",
          cited_by_count: 4,
        }),
        work({
          id: "https://openalex.org/W813",
          doi: null,
          title: "  Fault tolerant   quantum error correction  ",
          cited_by_count: 6,
        }),
      ],
    });
    return json({ results: [] });
  };
  const client = createOpenAlexClient({ fetchFn, apiKey: "test-key", maxWorks: 100 });

  const papers = await client.expand({
    topicIds: ["T7"],
    normalizedProblem: "quantum error correction",
  });

  assert.equal(papers.filter((paper) => paper.doi === "10.1000/qec").length, 1);
  assert.ok(papers.some((paper) => paper.id === "W811"));
  assert.equal(papers.filter((paper) => paper.title.toLowerCase().includes("fault")).length, 1);
  assert.ok(papers.some((paper) => paper.id === "W813"));
});

test("falls back to DOI filtering when a direct DOI work lookup is missing", async () => {
  const calls = [];
  const fetchFn = async (url) => {
    const target = String(url);
    calls.push(target);
    if (target.includes("/works/https%3A%2F%2Fdoi.org%2F10.48550%2Farxiv.2410.05202")) {
      return json({}, { ok: false, status: 404 });
    }
    if (target.includes("filter=doi%3A10.48550%2Farxiv.2410.05202")) {
      return json({ results: [work({
        id: "https://openalex.org/W241005202",
        doi: "https://doi.org/10.48550/arXiv.2410.05202",
        title: "Real-time low-latency quantum error correction",
      })] });
    }
    if (target.includes("filter=cites%3AW241005202")) return json({ results: [] });
    if (target.includes("filter=topics.id%3AT7")) return json({ results: [] });
    return json({ results: [] });
  };
  const client = createOpenAlexClient({ fetchFn, apiKey: "test-key", maxWorks: 100 });

  const papers = await client.expand({
    anchors: ["doi:10.48550/arXiv.2410.05202"],
    topicIds: [],
    normalizedProblem: "real-time decoder tail latency",
  });

  assert.deepEqual(papers.map((paper) => paper.id), ["W241005202"]);
  assert.ok(calls.some((target) => target.includes("filter=doi%3A10.48550%2Farxiv.2410.05202")));
});

test("bounds expansion, supplies abort signals, and reports provider failures", async () => {
  const fetchFn = async (_url, options) => {
    assert.ok(options.signal instanceof AbortSignal);
    return json({ results: Array.from({ length: 101 }, (_, index) => work({
      id: `https://openalex.org/W${index}`,
      doi: `https://doi.org/10.1234/example.${index}`,
      title: `Quantum error correction paper ${index}`,
    })) });
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

test("retains confirmed anchors under the final ceiling and bounds reference requests", async () => {
  const calls = [];
  const fetchFn = async (url) => {
    const target = String(url);
    calls.push(target);
    if (target.includes("/works/W900")) return json(work({
      id: "https://openalex.org/W900",
      referenced_works: Array.from({ length: 101 }, (_, index) => `https://openalex.org/W${1000 + index}`),
    }));
    if (target.includes("filter=cites%3AW900")) return json({
      results: Array.from({ length: 100 }, (_, index) => work({
        id: `https://openalex.org/W${String(index).padStart(3, "0")}`,
        doi: `https://doi.org/10.1234/candidate.${index}`,
        title: `Quantum error correction candidate ${index}`,
      })),
    });
    return json({ results: [] });
  };
  const client = createOpenAlexClient({ fetchFn, apiKey: "test-key", maxWorks: 100 });
  const papers = await client.expand({ anchors: ["W900"], topicIds: [], normalizedProblem: "quantum error correction" });
  assert.equal(papers.length, 100);
  assert.ok(papers.some((paper) => paper.id === "W900"));
  assert.deepEqual(papers.map((paper) => paper.id), [...papers].map((paper) => paper.id).sort());
  assert.ok(calls.filter((target) => /\/works\/W1\d{3}/.test(target)).length <= 100);
});

test("does not expand outgoing references into per-reference requests", async () => {
  const calls = [];
  const fetchFn = async (url) => {
    const target = String(url);
    calls.push(target);
    if (target.includes("/works/W900")) return json(work({
      id: "https://openalex.org/W900",
      referenced_works: Array.from({ length: 100 }, (_, index) => `https://openalex.org/W${1000 + index}`),
    }));
    if (target.includes("filter=cites%3AW900")) return json({ results: [] });
    if (target.includes("filter=topics.id%3AT7")) return json({ results: [] });
    if (/\/works\/W1\d{3}/.test(target)) assert.fail(`Outgoing reference lookup should not be requested: ${target}`);
    return json({ results: [] });
  };
  const client = createOpenAlexClient({ fetchFn, apiKey: "test-key", maxWorks: 100 });

  const papers = await client.expand({ anchors: ["W900"], topicIds: [], normalizedProblem: "quantum error correction" });

  assert.deepEqual(papers.map((paper) => paper.id), ["W900"]);
  assert.equal(papers[0].referencedWorkIds.length, 100);
});

test("aborts a request when its timeout signal fires", async () => {
  const originalSetTimeout = globalThis.setTimeout;
  let aborted = false;
  globalThis.setTimeout = (callback) => originalSetTimeout(callback, 0);
  try {
    const client = createOpenAlexClient({
      apiKey: "test-key",
      fetchFn: async (_url, { signal }) => new Promise((_resolve, reject) => {
        signal.addEventListener("abort", () => {
          aborted = true;
          reject(new Error("fake transport aborted"));
        }, { once: true });
      }),
    });
    await assert.rejects(client.expand({ anchors: [], topicIds: ["T7"] }), (error) => error.code === "OPENALEX_PROVIDER_ERROR");
    assert.equal(aborted, true);
  } finally {
    globalThis.setTimeout = originalSetTimeout;
  }
});
