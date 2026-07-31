import { describe, expect, it } from "vitest";

import {
  CitationCandidateRegistry,
  bibliographicDigest,
  canonicalArxivID,
  canonicalDOI,
  type BibliographicMetadata,
  type CitationCapabilityScope,
  type CitationResolver,
  type ResolvedCitation,
} from "../src/library-citations";

const scope = (threadId = "thread-a", libraryID: number | string = 1): CitationCapabilityScope => ({
  threadId,
  libraryID,
});

const metadata = (overrides: Partial<BibliographicMetadata> = {}): BibliographicMetadata => ({
  itemType: "journalArticle",
  title: "A resolved paper",
  creators: [{ creatorType: "author", firstName: "Ada", lastName: "Lovelace" }],
  date: "2026-07-31",
  DOI: "10.1000/abc",
  url: "https://doi.org/10.1000/abc",
  publicationTitle: "Journal of Tests",
  archive: "arXiv",
  archiveLocation: "2306.13123",
  ...overrides,
});

const resolution = (clientRef: string, overrides: Partial<ResolvedCitation> = {}): ResolvedCitation => ({
  clientRef,
  status: "create",
  candidates: [{
    choiceId: `choice-${clientRef}`,
    metadata: metadata(),
    localItemKey: null,
    localItemVersion: null,
    provenance: "identifier translation",
  }],
  reason: "Resolved by DOI",
  ...overrides,
});

function harness(results: readonly ResolvedCitation[] = [resolution("r1")]) {
  let nowMs = Date.parse("2026-07-31T10:00:00Z");
  let sequence = 0;
  const resolver: CitationResolver = {
    resolve: async () => results,
  };
  const registry = new CitationCandidateRegistry(resolver, {
    nowMs: () => nowMs,
    createId: () => `opaque-${++sequence}`,
  });
  return {
    registry,
    setNow(value: string) { nowMs = Date.parse(value); },
  };
}

describe("citation identifiers", () => {
  it("normalizes DOI and arXiv URL, prefix, punctuation, version, and PDF variants", () => {
    expect(canonicalDOI("https://doi.org/10.1000/ABC.")).toBe("10.1000/abc");
    expect(canonicalDOI("doi:10.1103/PhysRevA.52.R2493;")).toBe("10.1103/physreva.52.r2493");
    expect(canonicalDOI("http://dx.doi.org/10.1000/ABC?utm_source=test")).toBe("10.1000/abc");
    expect(canonicalDOI("doi.org/10.1000/ABC")).toBe("10.1000/abc");
    expect(canonicalDOI("not a doi")).toBeNull();

    expect(canonicalArxivID("arXiv:2306.13123v2.pdf")).toBe("2306.13123");
    expect(canonicalArxivID("https://arxiv.org/pdf/hep-th/9901001v3.pdf")).toBe("hep-th/9901001");
    expect(canonicalArxivID("arxiv.org/abs/2306.13123v2")).toBe("2306.13123");
    expect(canonicalArxivID("not an arxiv id")).toBeNull();
  });
});

describe("CitationCandidateRegistry", () => {
  it("binds candidates to one thread and expires them after 30 minutes", async () => {
    const { registry, setNow } = harness();
    const batch = await registry.lookup(scope("thread-a", 1), [{ clientRef: "r1", doi: "10.1000/abc" }]);
    const capabilityId = batch.results[0]!.capabilityId;

    expect(() => registry.resolveCapability(scope("thread-b", 1), capabilityId)).toThrow(/thread/i);
    expect(() => registry.resolveCapability(scope("thread-a", 2), capabilityId)).toThrow(/library/i);
    setNow("2026-07-31T10:30:00Z");
    expect(() => registry.resolveCapability(scope("thread-a", 1), capabilityId)).toThrow(/expired/i);
  });

  it("sweeps an expired batch and its capabilities before opaque IDs are reused", async () => {
    let nowMs = Date.parse("2026-07-31T10:00:00Z");
    const ids = ["batch", "capability", "batch", "capability"];
    const registry = new CitationCandidateRegistry({
      resolve: async (_scope, requests) => requests.map((request) => resolution(request.clientRef)),
    }, {
      nowMs: () => nowMs,
      createId: () => ids.shift() ?? "unexpected",
    });
    const first = await registry.lookup(scope(), [{ clientRef: "r1", doi: "10.1000/a" }]);

    nowMs += 30 * 60 * 1_000;
    expect(() => registry.resolveCapability(scope(), first.results[0]!.capabilityId)).toThrow(/expired/i);
    await expect(registry.lookup(scope(), [{ clientRef: "r2", doi: "10.1000/b" }]))
      .resolves.toMatchObject({ batchId: "batch" });
  });

  it("does not retain a partial capability when opaque ID generation throws", async () => {
    let idCalls = 0;
    const registry = new CitationCandidateRegistry({
      resolve: async (_scope, requests) => requests.map((request) => resolution(request.clientRef)),
    }, {
      createId: () => {
        idCalls += 1;
        if (idCalls === 1) return "batch";
        if (idCalls === 2) return "first-capability";
        throw new Error("secure entropy failed");
      },
    });

    await expect(registry.lookup(scope(), [
      { clientRef: "r1", doi: "10.1000/a" },
      { clientRef: "r2", doi: "10.1000/b" },
    ])).rejects.toThrow(/entropy failed/i);
    expect(() => registry.resolveCapability(scope(), "first-capability")).toThrow(/unknown/i);
  });

  it("does not retain a partial capability when generated IDs repeat", async () => {
    let idCalls = 0;
    const registry = new CitationCandidateRegistry({
      resolve: async (_scope, requests) => requests.map((request) => resolution(request.clientRef)),
    }, {
      createId: () => {
        idCalls += 1;
        return idCalls === 1 ? "batch" : "first-capability";
      },
    });

    await expect(registry.lookup(scope(), [
      { clientRef: "r1", doi: "10.1000/a" },
      { clientRef: "r2", doi: "10.1000/b" },
    ])).rejects.toThrow(/duplicate/i);
    expect(() => registry.resolveCapability(scope(), "first-capability")).toThrow(/unknown/i);
  });

  it("starts capability expiry from resolver completion time", async () => {
    const startedAt = Date.parse("2026-07-31T10:00:00Z");
    const completedAt = Date.parse("2026-07-31T10:31:00Z");
    let nowMs = startedAt;
    let idCalls = 0;
    const registry = new CitationCandidateRegistry({
      resolve: async () => {
        nowMs = completedAt;
        return [resolution("r1")];
      },
    }, {
      nowMs: () => nowMs,
      createId: () => `opaque-${++idCalls}`,
    });

    const batch = await registry.lookup(scope(), [{ clientRef: "r1", doi: "10.1000/a" }]);
    expect(batch.expiresAtMs).toBe(completedAt + 30 * 60 * 1_000);
    expect(registry.resolveCapability(scope(), batch.results[0]!.capabilityId).resolution.clientRef).toBe("r1");
  });

  it("makes capability IDs opaque and rejects forged IDs", async () => {
    const { registry } = harness();
    const batch = await registry.lookup(scope(), [{ clientRef: "r1", doi: "10.1000/secret-paper" }]);
    const capabilityId = batch.results[0]!.capabilityId;

    expect(capabilityId).not.toContain("secret");
    expect(capabilityId).not.toContain("thread-a");
    expect(() => registry.resolveCapability(scope(), "forged-capability")).toThrow(/unknown/i);
  });

  it("requires the exact unique complete set from one batch", async () => {
    const { registry } = harness([resolution("r1"), resolution("r2", {
      status: "unresolved",
      candidates: [],
      reason: "No match",
    })]);
    const batch = await registry.lookup(scope(), [
      { clientRef: "r1", doi: "10.1000/a" },
      { clientRef: "r2", arxiv: "2306.13123" },
    ]);
    const ids = batch.results.map((result) => result.capabilityId);

    expect(() => registry.resolveCompleteBatch(scope(), [ids[0]!])).toThrow(/complete/i);
    expect(() => registry.resolveCompleteBatch(scope(), [ids[0]!, ids[0]!])).toThrow(/duplicate/i);
    expect(registry.resolveCompleteBatch(scope(), [...ids].reverse()).map((entry) => entry.requestIndex))
      .toEqual([0, 1]);
  });

  it("does not combine capability IDs from different batches", async () => {
    const registry = new CitationCandidateRegistry({
      resolve: async (_scope, requests) => requests.map((request) => resolution(request.clientRef)),
    }, {
      createId: (() => {
        let sequence = 0;
        return () => `opaque-${++sequence}`;
      })(),
    });
    const first = await registry.lookup(scope(), [{ clientRef: "r1", doi: "10.1000/a" }]);
    const second = await registry.lookup(scope(), [{ clientRef: "r2", doi: "10.1000/b" }]);

    expect(() => registry.resolveCompleteBatch(scope(), [
      first.results[0]!.capabilityId,
      second.results[0]!.capabilityId,
    ])).toThrow(/one batch/i);
  });

  it("preserves ambiguous results in their own bound capabilities", async () => {
    const { registry } = harness([resolution("r1", {
      status: "ambiguous",
      candidates: [
        resolution("r1").candidates[0]!,
        { ...resolution("r1").candidates[0]!, choiceId: "choice-r1-alternative" },
      ],
      reason: "Two exact local matches",
    })]);
    const batch = await registry.lookup(scope(), [{ clientRef: "r1", title: "A resolved paper" }]);

    expect(registry.resolveCapability(scope(), batch.results[0]!.capabilityId).resolution)
      .toMatchObject({ status: "ambiguous", candidates: [{ choiceId: "choice-r1" }, { choiceId: "choice-r1-alternative" }] });
  });

  it("returns deep copies rather than registry-owned records", async () => {
    const { registry } = harness();
    const batch = await registry.lookup(scope(), [{ clientRef: "r1", doi: "10.1000/abc" }]);
    const returned = batch.results[0]!.resolution;
    (returned.candidates[0]!.metadata as BibliographicMetadata).title = "Mutated by caller";

    expect(registry.resolveCapability(scope(), batch.results[0]!.capabilityId)
      .resolution.candidates[0]!.metadata?.title).toBe("A resolved paper");

    const capability = registry.resolveCapability(scope(), batch.results[0]!.capabilityId);
    (capability.resolution.candidates[0]!.metadata as BibliographicMetadata).title = "Mutated twice";
    expect(registry.resolveCapability(scope(), batch.results[0]!.capabilityId)
      .resolution.candidates[0]!.metadata?.title).toBe("A resolved paper");
  });

  it("copies resolver output before a resolver-owned object can change", async () => {
    const resolverOutput = resolution("r1");
    const { registry } = harness([resolverOutput]);
    const batch = await registry.lookup(scope(), [{ clientRef: "r1", doi: "10.1000/abc" }]);
    (resolverOutput.candidates[0]!.metadata as BibliographicMetadata).title = "Resolver mutation";

    expect(registry.resolveCapability(scope(), batch.results[0]!.capabilityId)
      .resolution.candidates[0]!.metadata?.title).toBe("A resolved paper");
  });

  it("caps batches at 50 requests before calling the resolver", async () => {
    let calls = 0;
    const registry = new CitationCandidateRegistry({
      resolve: async () => {
        calls += 1;
        return [];
      },
    }, { createId: () => "opaque" });

    await expect(registry.lookup(scope(), Array.from({ length: 51 }, (_, index) => ({
      clientRef: `r${index}`,
      title: "A title",
    })))).rejects.toThrow(/50/);
    expect(calls).toBe(0);
  });

  it("rejects an empty batch before calling the resolver", async () => {
    let calls = 0;
    const registry = new CitationCandidateRegistry({
      resolve: async () => {
        calls += 1;
        return [];
      },
    }, { createId: () => "opaque" });

    await expect(registry.lookup(scope(), [])).rejects.toThrow(/at least 1/i);
    expect(calls).toBe(0);
  });

  it("rejects unknown, unsafe, and overlong query values before resolution", async () => {
    let calls = 0;
    const registry = new CitationCandidateRegistry({
      resolve: async () => {
        calls += 1;
        return [resolution("r1")];
      },
    }, { createId: () => "opaque" });

    await expect(registry.lookup(scope(), [{ clientRef: "r1", title: "A title", extra: true }] as never))
      .rejects.toThrow(/unknown/i);
    await expect(registry.lookup(scope(), [{ clientRef: "r1\u202E", title: "A title" }]))
      .rejects.toThrow(/unsafe/i);
    await expect(registry.lookup(scope(), [{ clientRef: "r1", citation: "x".repeat(20_001) }]))
      .rejects.toThrow(/too long/i);
    expect(calls).toBe(0);
  });

  it("rejects unsafe metadata, unsupported types, unknown fields, and non-author creators before digesting", async () => {
    const badMetadata = [
      metadata({ itemType: "webpage" as never }),
      metadata({ title: "   " }),
      metadata({ title: "Unsafe\u200B title" }),
      { ...metadata(), unsupported: "field" },
      metadata({ creators: [{ creatorType: "editor" as never, name: "Editor" }] }),
    ];

    for (const value of badMetadata) {
      const { registry } = harness([resolution("r1", {
        candidates: [{
          choiceId: "choice-r1",
          metadata: value as BibliographicMetadata,
          localItemKey: null,
          localItemVersion: null,
          provenance: "test",
        }],
      })]);
      await expect(registry.lookup(scope(), [{ clientRef: "r1", doi: "10.1000/abc" }]))
        .rejects.toThrow(/metadata|item type|title|unsafe|creator|unknown/i);
    }
  });

  it("rejects unsafe and overlong optional metadata before blank normalization", () => {
    expect(() => bibliographicDigest(metadata({ date: " \n " }))).toThrow(/unsafe/i);
    expect(() => bibliographicDigest(metadata({ url: " ".repeat(20_001) }))).toThrow(/too long/i);
    expect(() => bibliographicDigest(metadata({ archive: "\u00AD" }))).toThrow(/unsafe/i);
    expect(() => bibliographicDigest(metadata({ publicationTitle: "\u2060" }))).toThrow(/unsafe/i);
  });

  it("fails closed if a default registry cannot obtain cryptographic entropy", async () => {
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, "crypto");
    Object.defineProperty(globalThis, "crypto", { configurable: true, value: undefined });
    try {
      const registry = new CitationCandidateRegistry({
        resolve: async () => [resolution("r1")],
      });

      await expect(registry.lookup(scope(), [{ clientRef: "r1", doi: "10.1000/abc" }]))
        .rejects.toThrow(/secure random/i);
      expect(() => registry.resolveCapability(scope(), "uncreated-capability")).toThrow(/unknown/i);
    }
    finally {
      if (descriptor) Object.defineProperty(globalThis, "crypto", descriptor);
      else delete (globalThis as { crypto?: Crypto }).crypto;
    }
  });

  it("uses an ordered allowlist to create stable bibliographic digests", () => {
    const first = metadata();
    const sameValuesDifferentPropertyOrder: BibliographicMetadata = {
      archiveLocation: "2306.13123",
      archive: "arXiv",
      publicationTitle: "Journal of Tests",
      url: "https://doi.org/10.1000/abc",
      DOI: "10.1000/abc",
      date: "2026-07-31",
      creators: [{ lastName: "Lovelace", firstName: "Ada", creatorType: "author" }],
      title: "A resolved paper",
      itemType: "journalArticle",
    };

    expect(bibliographicDigest(first)).toBe("fc39622624a851812391a975507b4a3f08fd5bc131397defada8be023e74b603");
    expect(bibliographicDigest(sameValuesDifferentPropertyOrder)).toBe(bibliographicDigest(first));
  });
});
