import { describe, expect, it, vi } from "vitest";

import {
  CitationCandidateRegistry,
  type BibliographicMetadata,
  type CitationCapabilityScope,
  type ResolvedCitation,
} from "../src/library-citations";
import {
  LibraryApplyFailure,
  LOOKUP_CITATIONS_TOOL,
  PROPOSE_LIBRARY_IMPORT_TOOL,
  ReviewedLibraryImportService,
  type BoundLibraryImportPlan,
  type LibraryApplyReceipt,
  type LibraryImportPreflight,
  type LibraryMutationHost,
} from "../src/reviewed-library-import";

const UNSAFE_TEST_TEXT = /[\p{Cc}\p{Cf}\u2028\u2029]/u;

const scope = (threadId = "library-thread", libraryID: number | string = 1): CitationCapabilityScope => ({
  threadId,
  libraryID,
});

const metadata = (title: string): BibliographicMetadata => ({
  itemType: "journalArticle",
  title,
  creators: [{ creatorType: "author", firstName: "Peter", lastName: "Shor" }],
  date: "1995",
  DOI: "10.1103/physreva.52.r2493",
  url: "https://doi.org/10.1103/physreva.52.r2493",
  publicationTitle: "Physical Review A",
  archive: "",
  archiveLocation: "",
});

const candidate = (
  choiceId: string,
  title: string,
  overrides: Partial<ResolvedCitation["candidates"][number]> = {},
): ResolvedCitation["candidates"][number] => ({
  choiceId,
  metadata: metadata(title),
  localItemKey: null,
  localItemVersion: null,
  provenance: "identifier translation",
  ...overrides,
});

const applyReceipt = (
  overrides: Partial<LibraryApplyReceipt> = {},
): LibraryApplyReceipt => ({
  libraryID: 1,
  createdCollectionKey: "COLLECTION-NEW",
  createdItemKeys: ["ITEM-NEW"],
  addedMemberships: [{ itemKey: "ITEM-NEW", collectionKey: "COLLECTION-NEW" }],
  ...overrides,
});

const resolution = (
  clientRef: string,
  overrides: Partial<ResolvedCitation> = {},
): ResolvedCitation => ({
  clientRef,
  status: "create",
  candidates: [candidate(`bound-${clientRef}`, `Paper ${clientRef}`)],
  reason: "Resolved by DOI",
  ...overrides,
});

function defaultPreflight(plan: BoundLibraryImportPlan): LibraryImportPreflight {
  return {
    digest: `preflight-${plan.rows.map((row) => row.rowId).join("-")}`,
    editable: true,
    parentVersion: plan.target.parentCollectionKey ? 7 : null,
    siblingCollectionKey: null,
    dispositions: plan.rows.map((row) => {
      const localChoice = /^bound-local-(\d+)$/u.exec(row.choiceId ?? "");
      const reuse = row.rowId.startsWith("reuse") || localChoice !== null;
      return {
        rowId: row.rowId,
        effect: row.omit ? "omit" : row.choiceId ? (reuse ? "reuse" : "create") : "conflict",
        itemKey: row.rowId.startsWith("reuse") ? "LOCAL-1" : localChoice ? `LOCAL-${localChoice[1]}` : null,
        itemVersion: row.rowId.startsWith("reuse") ? 3 : localChoice ? Number(localChoice[1]) : null,
        membershipExists: false,
      };
    }),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function oneShotGetter<T>(reads: Map<string, number>, name: string, value: T): () => T {
  return () => {
    const count = (reads.get(name) ?? 0) + 1;
    reads.set(name, count);
    if (count > 1) throw new Error(`${name} was read twice`);
    return value;
  };
}

function importServiceHarness(
  results: readonly ResolvedCitation[] = [resolution("shor")],
  preflight: (plan: BoundLibraryImportPlan) => Promise<LibraryImportPreflight> = async (plan) => defaultPreflight(plan),
  onStateCallback: (scope: CitationCapabilityScope) => void = () => {},
) {
  let registrySequence = 0;
  let reviewSequence = 0;
  const registry = new CitationCandidateRegistry({
    resolve: async (_resolverScope, requests) => requests.map((request) => {
      const matched = results.find((entry) => entry.clientRef === request.clientRef);
      if (!matched) throw new Error(`No fixture for ${request.clientRef}`);
      return structuredClone(matched);
    }),
  }, {
    createId: () => `capability-${++registrySequence}`,
  });
  const host: LibraryMutationHost = {
    preflight: vi.fn(preflight),
    apply: vi.fn(async () => applyReceipt()),
    compensate: vi.fn(async () => ({ complete: true, survivors: [] })),
    invalidateLibrary: vi.fn(async () => {}),
  };
  const onState = vi.fn(onStateCallback);
  const service = new ReviewedLibraryImportService(registry, host, { onState }, {
    createId: () => `library-review-${++reviewSequence}`,
  });
  return { service, registry, host, onState };
}

async function lookupCapabilities(
  service: ReviewedLibraryImportService,
  requests: Array<Record<string, unknown>>,
  subject = scope(),
): Promise<string[]> {
  const lookup = await service.invokeTool(LOOKUP_CITATIONS_TOOL, { requests }, subject) as {
    results: Array<{ capability_id: string }>;
  };
  return lookup.results.map((entry) => entry.capability_id);
}

async function propose(
  service: ReviewedLibraryImportService,
  capabilityIds: string[],
  subject = scope(),
  overrides: Record<string, unknown> = {},
) {
  return service.invokeTool(PROPOSE_LIBRARY_IMPORT_TOOL, {
    collection_name: "Cited in draft · Jul 31",
    parent_collection_key: "PARENT",
    capability_ids: capabilityIds,
    ...overrides,
  }, subject);
}

describe("ReviewedLibraryImportService read-only tools", () => {
  it("looks up and proposes without writing Zotero", async () => {
    const { service, registry, host } = importServiceHarness();
    const subject = scope();
    const lookupSpy = vi.spyOn(registry, "lookup");
    const [capabilityID] = await lookupCapabilities(service, [
      { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
    ], subject);

    const proposed = await propose(service, [capabilityID!], subject);

    expect(proposed.status).toBe("awaiting_user_review");
    expect(lookupSpy).toHaveBeenCalledOnce();
    expect(host.preflight).toHaveBeenCalledOnce();
    expect(host.apply).not.toHaveBeenCalled();
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).not.toHaveBeenCalled();
    expect(service.getReviews(subject)[0]?.rows[0]?.disposition).toBe("create");
    expect(vi.mocked(host.preflight).mock.calls[0]?.[0]).toMatchObject({
      scope: subject,
      target: { collectionName: "Cited in draft · Jul 31", parentCollectionKey: "PARENT" },
      rows: [{ rowId: "shor", choiceId: "bound-shor", omit: false }],
    });
  });

  it("requires an explicit candidate or omission for every non-ready row", async () => {
    const results = [
      resolution("ready-1"),
      resolution("ambiguous-1", {
        status: "ambiguous",
        candidates: [
          candidate("bound-local-1", "First local match", { localItemKey: "LOCAL-1", localItemVersion: 1 }),
          candidate("bound-local-2", "Second local match", { localItemKey: "LOCAL-2", localItemVersion: 2 }),
        ],
        reason: "Multiple exact local matches",
      }),
      resolution("unresolved-1", {
        status: "unresolved",
        candidates: [],
        reason: "No exact match",
      }),
    ];
    const { service } = importServiceHarness(results);
    const capabilityIds = await lookupCapabilities(service, results.map((entry) => ({
      client_ref: entry.clientRef,
      title: `Lookup ${entry.clientRef}`,
    })));
    await propose(service, capabilityIds);
    const review = service.getReviews(scope())[0]!;

    expect(review.canApply).toBe(false);
    expect(review.rows.map((row) => row.disposition)).toEqual(["create", "ambiguous", "unresolved"]);
    service.setRowResolution(review.id, "ambiguous-1", { candidateId: "bound-local-1" });
    service.setRowResolution(review.id, "unresolved-1", { omit: true });
    await vi.waitFor(() => expect(service.getReviews(scope())[0]?.canApply).toBe(true));

    const resolved = service.getReviews(scope())[0]!;
    expect(resolved.canApply).toBe(true);
    expect(resolved.rows[1]).toMatchObject({ selectedCandidateId: "bound-local-1", omissionAcknowledged: false });
    expect(resolved.rows[2]).toMatchObject({ selectedCandidateId: null, omissionAcknowledged: true });
  });

  it("publishes closed schemas and rejects model-supplied authority fields at runtime", async () => {
    const { service, host } = importServiceHarness();
    const lookupSpec = service.tools.find((tool) => tool.name === LOOKUP_CITATIONS_TOOL)!;
    const proposalSpec = service.tools.find((tool) => tool.name === PROPOSE_LIBRARY_IMPORT_TOOL)!;

    expect(lookupSpec.inputSchema).toMatchObject({
      type: "object",
      additionalProperties: false,
      required: ["requests"],
      properties: {
        requests: {
          type: "array",
          minItems: 1,
          maxItems: 50,
          items: { type: "object", additionalProperties: false, required: ["client_ref"] },
        },
      },
    });
    expect(proposalSpec.inputSchema).toEqual({
      type: "object",
      additionalProperties: false,
      required: ["collection_name", "capability_ids"],
      properties: {
        collection_name: { type: "string", minLength: 1, maxLength: 1_600 },
        parent_collection_key: { type: "string", minLength: 1, maxLength: 1000 },
        capability_ids: {
          type: "array",
          minItems: 1,
          maxItems: 50,
          uniqueItems: true,
          items: { type: "string", minLength: 1, maxLength: 1000 },
        },
      },
    });

    await expect(service.invokeTool(LOOKUP_CITATIONS_TOOL, {
      requests: [{ client_ref: "shor", doi: "10.1103/physreva.52.r2493", metadata: metadata("Forged") }],
    }, scope())).rejects.toThrow(/unknown|metadata/i);
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
    ]);
    for (const extra of [
      { library_id: 1 },
      { metadata: metadata("Forged") },
      { choice: { choiceId: "bound-shor" } },
      { capability_id: capabilityId },
    ]) {
      await expect(propose(service, [capabilityId!], scope(), extra)).rejects.toThrow(/unknown/i);
    }
    await expect(service.invokeTool(PROPOSE_LIBRARY_IMPORT_TOOL, {
      collection_name: "Target",
    }, scope())).rejects.toThrow(/capability_ids|required/i);
    expect(host.preflight).not.toHaveBeenCalled();
  });

  it("accepts only the exact complete unique capability set from one batch", async () => {
    const results = [resolution("one"), resolution("two"), resolution("three")];
    const { service, host } = importServiceHarness(results);
    const firstBatch = await lookupCapabilities(service, [
      { client_ref: "one", title: "One" },
      { client_ref: "two", title: "Two" },
    ]);
    const secondBatch = await lookupCapabilities(service, [{ client_ref: "three", title: "Three" }]);

    await expect(propose(service, [firstBatch[0]!])).rejects.toThrow(/complete/i);
    await expect(propose(service, [firstBatch[0]!, firstBatch[0]!])).rejects.toThrow(/duplicate|unique/i);
    await expect(propose(service, [firstBatch[0]!, secondBatch[0]!])).rejects.toThrow(/one batch/i);
    await expect(propose(service, [...firstBatch, "forged-capability"])).rejects.toThrow(/unknown/i);
    expect(host.preflight).not.toHaveBeenCalled();
  });

  it("preserves registry-issued capability IDs exactly instead of normalizing authority", async () => {
    const issuedIds = [" batch-id ", " capability-id "];
    const registry = new CitationCandidateRegistry({
      resolve: async () => [resolution("shor")],
    }, {
      createId: () => issuedIds.shift()!,
    });
    const host: LibraryMutationHost = {
      preflight: vi.fn(async (plan) => defaultPreflight(plan)),
      apply: vi.fn(async () => { throw new Error("apply must not run in Task 4"); }),
      compensate: vi.fn(async () => ({ complete: true, survivors: [] })),
      invalidateLibrary: vi.fn(async () => {}),
    };
    const service = new ReviewedLibraryImportService(registry, host, { onState: vi.fn() }, {
      createId: () => "review-exact-id",
    });
    const lookup = await service.invokeTool(LOOKUP_CITATIONS_TOOL, {
      requests: [{ client_ref: "shor", doi: "10.1103/physreva.52.r2493" }],
    }, scope()) as { results: Array<{ capability_id: string }> };

    expect(lookup.results[0]?.capability_id).toBe(" capability-id ");
    await expect(propose(service, [" capability-id "])).resolves.toMatchObject({
      status: "awaiting_user_review",
    });
    expect(host.preflight).toHaveBeenCalledOnce();
  });

  it("normalizes safe collection names and rejects unsafe or path-like targets before preflight", async () => {
    const { service, host } = importServiceHarness();
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
    ]);
    const invalidNames = [
      "",
      "   ",
      ".",
      "..",
      "folder/name",
      "folder\\name",
      "line\nbreak",
      "line\u2028break",
      "unsafe\u202Ename",
      "zero\u200Bwidth",
      "x".repeat(201),
    ];
    for (const collection_name of invalidNames) {
      await expect(propose(service, [capabilityId!], scope(), { collection_name }))
        .rejects.toThrow(/collection|unsafe|path|separator|long|blank/i);
    }
    expect(host.preflight).not.toHaveBeenCalled();

    await propose(service, [capabilityId!], scope(), { collection_name: "  Cafe\u0301 papers  " });
    expect(vi.mocked(host.preflight).mock.calls[0]?.[0].target.collectionName).toBe("Café papers");

    const paddedDecomposed = `${" ".repeat(500)}${"e\u0301".repeat(200)}${" ".repeat(500)}`;
    await propose(service, [capabilityId!], scope(), { collection_name: paddedDecomposed });
    expect(vi.mocked(host.preflight).mock.calls[1]?.[0].target.collectionName).toBe("é".repeat(200));

    await expect(propose(service, [capabilityId!], scope(), {
      collection_name: `${" ".repeat(1_600)}x`,
    })).rejects.toThrow(/collection.*raw|defensive|long/i);
  });

  it("keeps ready, ambiguous, and unresolved rows in one host-bound structured review", async () => {
    const results = [
      resolution("create-1"),
      resolution("reuse-1", {
        status: "reuse",
        candidates: [candidate("bound-reuse-1", "Existing paper", {
          localItemKey: "LOCAL-1",
          localItemVersion: 3,
          provenance: "exact DOI in target library",
        })],
      }),
      resolution("ambiguous-1", {
        status: "ambiguous",
        candidates: [
          candidate("bound-local-1", "First local match", { localItemKey: "LOCAL-1", localItemVersion: 1 }),
          candidate("bound-local-2", "Second local match", { localItemKey: "LOCAL-2", localItemVersion: 2 }),
        ],
      }),
      resolution("unresolved-1", { status: "unresolved", candidates: [], reason: "No exact match" }),
    ];
    const { service, host } = importServiceHarness(results);
    const ids = await lookupCapabilities(service, results.map((entry) => ({
      client_ref: entry.clientRef,
      title: entry.clientRef,
    })));
    await propose(service, ids);

    const review = service.getReviews(scope())[0]!;
    expect(review.rows).toHaveLength(4);
    expect(review.rows.map((row) => ({
      id: row.id,
      disposition: row.disposition,
      selectedCandidateId: row.selectedCandidateId,
      omissionAcknowledged: row.omissionAcknowledged,
    }))).toEqual([
      { id: "create-1", disposition: "create", selectedCandidateId: "bound-create-1", omissionAcknowledged: false },
      { id: "reuse-1", disposition: "reuse", selectedCandidateId: "bound-reuse-1", omissionAcknowledged: false },
      { id: "ambiguous-1", disposition: "ambiguous", selectedCandidateId: null, omissionAcknowledged: false },
      { id: "unresolved-1", disposition: "unresolved", selectedCandidateId: null, omissionAcknowledged: false },
    ]);
    expect(review.rows[2]?.candidates).toEqual([
      { candidateId: "bound-local-1", label: "First local match", provenance: "identifier translation" },
      { candidateId: "bound-local-2", label: "Second local match", provenance: "identifier translation" },
    ]);

    const plan = vi.mocked(host.preflight).mock.calls[0]![0];
    expect(plan.rows.map((row) => ({ rowId: row.rowId, choiceId: row.choiceId, omit: row.omit }))).toEqual([
      { rowId: "create-1", choiceId: "bound-create-1", omit: false },
      { rowId: "reuse-1", choiceId: "bound-reuse-1", omit: false },
      { rowId: "ambiguous-1", choiceId: null, omit: false },
      { rowId: "unresolved-1", choiceId: null, omit: false },
    ]);
    expect(Object.keys(plan.rows[0]!).sort()).toEqual(["choiceId", "omit", "resolverDigest", "rowId"]);
  });

  it("filters reviews by both thread and library and returns defensive deep copies", async () => {
    const { service } = importServiceHarness();
    const subjects = [scope("thread-a", 1), scope("thread-a", 2), scope("thread-b", 1)];
    for (const subject of subjects) {
      const [capabilityId] = await lookupCapabilities(service, [
        { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
      ], subject);
      await propose(service, [capabilityId!], subject);
    }

    expect(service.getReviews(scope("thread-a", 1))).toHaveLength(1);
    expect(service.getReviews(scope("thread-a", 2))).toHaveLength(1);
    expect(service.getReviews(scope("thread-b", 1))).toHaveLength(1);
    expect(service.getReviews(scope("missing", 1))).toEqual([]);

    const returned = service.getReviews(scope("thread-a", 1));
    const mutable = returned[0] as unknown as {
      scope: { threadId: string };
      target: { collectionName: string };
      rows: Array<{ candidates: Array<{ label: string }> }>;
    };
    mutable.scope.threadId = "mutated";
    mutable.target.collectionName = "mutated";
    mutable.rows[0]!.candidates[0]!.label = "mutated";
    mutable.rows.splice(0, 1);

    expect(service.getReviews(scope("thread-a", 1))[0]).toMatchObject({
      scope: { threadId: "thread-a", libraryID: 1 },
      target: { collectionName: "Cited in draft · Jul 31" },
      rows: [{ candidates: [{ label: "Paper shor" }] }],
    });
  });

  it("allows only a bound candidate ID or an explicit omission on non-ready pending rows", async () => {
    const results = [
      resolution("ready-1"),
      resolution("ambiguous-1", {
        status: "ambiguous",
        candidates: [candidate("bound-local-1", "Local match")],
      }),
      resolution("unresolved-1", { status: "unresolved", candidates: [], reason: "No match" }),
    ];
    const { service } = importServiceHarness(results);
    const ids = await lookupCapabilities(service, results.map((entry) => ({ client_ref: entry.clientRef, title: entry.clientRef })));
    await propose(service, ids);
    const reviewId = service.getReviews(scope())[0]!.id;

    expect(() => service.setRowResolution(reviewId, "ambiguous-1", { candidateId: "forged" })).toThrow(/candidate/i);
    expect(() => service.setRowResolution(reviewId, "ambiguous-1", { candidateId: "bound-local-1", omit: true })).toThrow(/exactly one/i);
    expect(() => service.setRowResolution(reviewId, "ambiguous-1", { omit: false })).toThrow(/omit.*true|exactly one/i);
    expect(() => service.setRowResolution(reviewId, "ready-1", { omit: true })).toThrow(/ready|create|reuse/i);
    expect(() => service.setRowResolution(reviewId, "missing", { omit: true })).toThrow(/row/i);
    expect(() => service.setRowResolution("missing-review", "ambiguous-1", { omit: true })).toThrow(/review/i);
    expect(() => service.setRowResolution(reviewId, "ambiguous-1", {
      candidateId: "bound-local-1",
      metadata: metadata("Forged"),
    } as never)).toThrow(/unknown/i);
  });

  it("rejects terminally with zero writes", async () => {
    const { service, host, onState } = importServiceHarness();
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
    ]);
    await propose(service, [capabilityId!]);
    const reviewId = service.getReviews(scope())[0]!.id;

    await expect(service.resolveReview(reviewId, "reject")).resolves.toEqual({
      decision: "rejected",
      reviewId,
      receipt: null,
    });
    expect(service.getReviews(scope())[0]).toMatchObject({ state: "rejected", canApply: false });
    await expect(service.resolveReview(reviewId, "reject")).rejects.toThrow(/already resolved/i);
    expect(host.apply).not.toHaveBeenCalled();
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).not.toHaveBeenCalled();
    expect(onState).toHaveBeenLastCalledWith(scope());
  });

  it("claims Apply synchronously, validates the exact final plan, and writes exactly once", async () => {
    const { service, host } = importServiceHarness();
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
    ]);
    await propose(service, [capabilityId!]);
    const reviewId = service.getReviews(scope())[0]!.id;

    const accepting = service.resolveReview(reviewId, "accept");
    expect(service.getReviews(scope())[0]?.state).toBe("resolving");
    await expect(service.resolveReview(reviewId, "accept")).rejects.toThrow(/already resolved|being applied/i);
    await expect(accepting).resolves.toEqual({
      decision: "accepted",
      reviewId,
      receipt: applyReceipt(),
    });
    expect(host.preflight).toHaveBeenCalledTimes(2);
    expect(vi.mocked(host.preflight).mock.calls[1]?.[0]).toEqual(
      vi.mocked(host.preflight).mock.calls[0]?.[0],
    );
    expect(vi.mocked(host.preflight).mock.calls[1]?.[0]).not.toBe(
      vi.mocked(host.preflight).mock.calls[0]?.[0],
    );
    expect(host.apply).toHaveBeenCalledOnce();
    expect(vi.mocked(host.apply).mock.calls[0]?.[0]).toEqual({
      ...vi.mocked(host.preflight).mock.calls[1]?.[0],
      preflight: defaultPreflight(vi.mocked(host.preflight).mock.calls[1]![0]),
    });
    expect(host.invalidateLibrary).toHaveBeenCalledOnce();
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
    expect(service.getReviews(scope())[0]).toMatchObject({ state: "accepted", canApply: false });
    expect(host.compensate).not.toHaveBeenCalled();
  });

  it("keeps a successful review resolving until invalidation settles before advancing the queue", async () => {
    const firstInvalidation = deferred<void>();
    const results = [resolution("first"), resolution("second")];
    const { service, host } = importServiceHarness(results);
    vi.mocked(host.apply)
      .mockResolvedValueOnce(applyReceipt())
      .mockResolvedValueOnce(applyReceipt({
        createdCollectionKey: "COLLECTION-SECOND",
        createdItemKeys: ["ITEM-SECOND"],
        addedMemberships: [{ itemKey: "ITEM-SECOND", collectionKey: "COLLECTION-SECOND" }],
      }));
    const [firstCapability] = await lookupCapabilities(service, [{ client_ref: "first", title: "First" }]);
    await propose(service, [firstCapability!]);
    const [secondCapability] = await lookupCapabilities(service, [{ client_ref: "second", title: "Second" }]);
    await propose(service, [secondCapability!], scope(), { collection_name: "Second target" });
    const [firstReview, secondReview] = service.getReviews(scope());
    vi.mocked(host.preflight).mockClear();
    vi.mocked(host.invalidateLibrary)
      .mockImplementationOnce(async () => firstInvalidation.promise)
      .mockResolvedValueOnce();

    const first = service.resolveReview(firstReview!.id, "accept");
    const second = service.resolveReview(secondReview!.id, "accept");

    await vi.waitFor(() => expect(host.invalidateLibrary).toHaveBeenCalledOnce());
    expect(service.getReviews(scope()).map((review) => review.state)).toEqual(["resolving", "resolving"]);
    expect(vi.mocked(host.preflight).mock.calls.map(([plan]) => plan.rows[0]?.rowId)).toEqual(["first"]);
    expect(vi.mocked(host.apply).mock.calls.map(([plan]) => plan.rows[0]?.rowId)).toEqual(["first"]);

    firstInvalidation.resolve();
    await expect(first).resolves.toMatchObject({ decision: "accepted", reviewId: firstReview!.id });
    await expect(second).resolves.toMatchObject({ decision: "accepted", reviewId: secondReview!.id });

    expect(vi.mocked(host.preflight).mock.calls.map(([plan]) => plan.rows[0]?.rowId)).toEqual(["first", "second"]);
    expect(vi.mocked(host.apply).mock.calls.map(([plan]) => plan.rows[0]?.rowId)).toEqual(["first", "second"]);
    expect(service.getReviews(scope()).map((review) => review.state)).toEqual(["accepted", "accepted"]);
    expect(service.getReviews(scope())[0]?.statusMessage).toBe("The library import was applied successfully.");
  });

  it("keeps a rejected invalidation inside the Apply queue before publishing accepted with a warning", async () => {
    const firstInvalidation = deferred<void>();
    const events: string[] = [];
    const results = [resolution("first"), resolution("second")];
    const { service, host } = importServiceHarness(results);
    vi.mocked(host.apply)
      .mockImplementationOnce(async (plan) => {
        events.push(`apply:${plan.rows[0]?.rowId}`);
        return applyReceipt();
      })
      .mockImplementationOnce(async (plan) => {
        events.push(`apply:${plan.rows[0]?.rowId}`);
        return applyReceipt({
        createdCollectionKey: "COLLECTION-SECOND",
        createdItemKeys: ["ITEM-SECOND"],
        addedMemberships: [{ itemKey: "ITEM-SECOND", collectionKey: "COLLECTION-SECOND" }],
        });
      });
    const [firstCapability] = await lookupCapabilities(service, [{ client_ref: "first", title: "First" }]);
    await propose(service, [firstCapability!]);
    const [secondCapability] = await lookupCapabilities(service, [{ client_ref: "second", title: "Second" }]);
    await propose(service, [secondCapability!], scope(), { collection_name: "Second target" });
    const [firstReview, secondReview] = service.getReviews(scope());
    vi.mocked(host.preflight).mockImplementation(async (plan) => {
      events.push(`preflight:${plan.rows[0]?.rowId}`);
      return defaultPreflight(plan);
    });
    vi.mocked(host.invalidateLibrary)
      .mockImplementationOnce(async () => {
        events.push("invalidate:first");
        return firstInvalidation.promise;
      })
      .mockImplementationOnce(async () => {
        events.push("invalidate:second");
      });

    const first = service.resolveReview(firstReview!.id, "accept");
    const second = service.resolveReview(secondReview!.id, "accept");
    await expect(service.resolveReview(secondReview!.id, "reject"))
      .rejects.toThrow(/already resolved|being applied/i);

    await vi.waitFor(() => expect(events).toEqual([
      "preflight:first",
      "apply:first",
      "invalidate:first",
    ]));
    expect(host.preflight).toHaveBeenCalledTimes(3);
    expect(service.getReviews(scope()).map((review) => review.state)).toEqual(["resolving", "resolving"]);

    firstInvalidation.reject(new Error("first invalidation failed"));
    await expect(first).resolves.toMatchObject({ decision: "accepted", reviewId: firstReview!.id });
    expect(service.getReviews(scope())[0]).toMatchObject({
      state: "accepted",
      statusMessage: expect.stringMatching(/snapshot.*reload/i),
    });
    await expect(second).resolves.toMatchObject({ decision: "accepted", reviewId: secondReview!.id });
    expect(events).toEqual([
      "preflight:first",
      "apply:first",
      "invalidate:first",
      "preflight:second",
      "apply:second",
      "invalidate:second",
    ]);
    expect(host.apply).toHaveBeenCalledTimes(2);
    expect(vi.mocked(host.apply).mock.calls.map(([plan]) => plan.rows[0]?.rowId)).toEqual(["first", "second"]);
    expect(service.getReviews(scope())[0]?.statusMessage).toMatch(/snapshot.*reload/i);
  });

  it.each([
    ["editable", (preflight: LibraryImportPreflight) => ({ ...preflight, editable: false })],
    ["parent version", (preflight: LibraryImportPreflight) => ({ ...preflight, parentVersion: 8 })],
    ["sibling collection key", (preflight: LibraryImportPreflight) => ({ ...preflight, siblingCollectionKey: "COLLECTION-OTHER" })],
    ["digest", (preflight: LibraryImportPreflight) => ({ ...preflight, digest: `${preflight.digest}-changed` })],
    ["disposition row ID", (preflight: LibraryImportPreflight) => ({
      ...preflight,
      dispositions: preflight.dispositions.map((entry) => ({ ...entry, rowId: ` ${entry.rowId} ` })),
    })],
    ["disposition effect", (preflight: LibraryImportPreflight) => ({
      ...preflight,
      dispositions: preflight.dispositions.map((entry) => ({
        ...entry,
        effect: "conflict" as const,
        itemKey: null,
        itemVersion: null,
        membershipExists: false,
      })),
    })],
    ["item key", (preflight: LibraryImportPreflight) => ({
      ...preflight,
      dispositions: preflight.dispositions.map((entry) => ({ ...entry, itemKey: "LOCAL-OTHER" })),
    })],
    ["item version", (preflight: LibraryImportPreflight) => ({
      ...preflight,
      dispositions: preflight.dispositions.map((entry) => ({ ...entry, itemVersion: 4 })),
    })],
    ["membership", (preflight: LibraryImportPreflight) => ({
      ...preflight,
      dispositions: preflight.dispositions.map((entry) => ({ ...entry, membershipExists: true })),
    })],
  ])("marks a changed %s stale before the first write", async (_field, change) => {
    const reuse = resolution("reuse-1", {
      status: "reuse",
      candidates: [candidate("bound-reuse-1", "Existing", {
        localItemKey: "LOCAL-1",
        localItemVersion: 3,
      })],
    });
    const { service, host } = importServiceHarness([reuse], async (plan) => ({
      ...defaultPreflight(plan),
      siblingCollectionKey: "COLLECTION-TARGET",
    }));
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "reuse-1", title: "Existing" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;
    const proposalPreflight = {
      ...defaultPreflight(vi.mocked(host.preflight).mock.calls[0]![0]),
      siblingCollectionKey: "COLLECTION-TARGET",
    };
    vi.mocked(host.preflight).mockResolvedValueOnce(change(proposalPreflight));

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/stale/i);

    expect(service.getReviews(scope())[0]).toMatchObject({ state: "stale", canApply: false });
    expect(host.apply).not.toHaveBeenCalled();
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).not.toHaveBeenCalled();
  });

  it.each([
    ["reordered dispositions", (preflight: LibraryImportPreflight) => ({
      ...preflight,
      dispositions: [...preflight.dispositions].reverse(),
    })],
    ["short disposition list", (preflight: LibraryImportPreflight) => ({
      ...preflight,
      dispositions: preflight.dispositions.slice(0, 1),
    })],
    ["malformed top-level response", (_preflight: LibraryImportPreflight) => new Proxy(
      { digest: "hostile" },
      { getPrototypeOf() { throw new Error("hostile final preflight"); } },
    )],
  ])("marks a final preflight with %s stale before Apply", async (_label, change) => {
    const results = [resolution("first"), resolution("second")];
    const { service, host } = importServiceHarness(results);
    const capabilityIds = await lookupCapabilities(service, [
      { client_ref: "first", title: "First" },
      { client_ref: "second", title: "Second" },
    ]);
    await propose(service, capabilityIds);
    const review = service.getReviews(scope())[0]!;
    const proposalPreflight = defaultPreflight(vi.mocked(host.preflight).mock.calls[0]![0]);
    vi.mocked(host.preflight).mockResolvedValueOnce(change(proposalPreflight) as LibraryImportPreflight);

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/stale/i);

    expect(service.getReviews(scope())[0]).toMatchObject({ state: "stale", canApply: false });
    expect(host.apply).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).not.toHaveBeenCalled();
  });

  it("accepts with a retained receipt clone and isolates state callback failures", async () => {
    let notificationsFail = false;
    const { service, host } = importServiceHarness(
      [resolution("shor")],
      async (plan) => defaultPreflight(plan),
      () => {
        if (notificationsFail) throw new Error("UI callback failed");
      },
    );
    const receipt = applyReceipt();
    vi.mocked(host.apply).mockResolvedValueOnce(receipt);
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;
    notificationsFail = true;

    const accepted = await service.resolveReview(review.id, "accept");
    (accepted.receipt!.createdItemKeys as string[])[0] = "MUTATED-RETURN";
    (receipt.createdItemKeys as string[])[0] = "MUTATED-HOST";
    const internal = service as unknown as {
      pending: Map<string, { receipt: LibraryApplyReceipt | null }>;
    };

    expect(internal.pending.get(review.id)?.receipt).toEqual(applyReceipt());
    expect(service.getReviews(scope())[0]).toMatchObject({ state: "accepted" });
  });

  it("accepts one membership effect when two rows reuse the same existing item", async () => {
    const results = ["reuse-first", "reuse-second"].map((clientRef) => resolution(clientRef, {
      status: "reuse",
      candidates: [candidate(`bound-${clientRef}`, "Existing paper", {
        localItemKey: "LOCAL-1",
        localItemVersion: 3,
      })],
    }));
    const { service, host } = importServiceHarness(results, async (plan) => ({
      ...defaultPreflight(plan),
      siblingCollectionKey: "COLLECTION-TARGET",
    }));
    vi.mocked(host.apply).mockResolvedValueOnce({
      libraryID: 1,
      createdCollectionKey: null,
      createdItemKeys: [],
      addedMemberships: [{ itemKey: "LOCAL-1", collectionKey: "COLLECTION-TARGET" }],
    });
    const capabilityIds = await lookupCapabilities(service, results.map(({ clientRef }) => ({
      client_ref: clientRef,
      title: "Existing paper",
    })));
    await propose(service, capabilityIds);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).resolves.toMatchObject({
      decision: "accepted",
      receipt: {
        addedMemberships: [{ itemKey: "LOCAL-1", collectionKey: "COLLECTION-TARGET" }],
      },
    });
    expect(host.compensate).not.toHaveBeenCalled();
  });

  it.each([
    ["extra field", { ...applyReceipt(), authority: "forged" }],
    ["duplicate created item", applyReceipt({ createdItemKeys: ["ITEM-NEW", "ITEM-NEW"] })],
    ["duplicate membership", applyReceipt({
      addedMemberships: [
        { itemKey: "ITEM-NEW", collectionKey: "COLLECTION-NEW" },
        { itemKey: "ITEM-NEW", collectionKey: "COLLECTION-NEW" },
      ],
    })],
    ["unsafe key", applyReceipt({ createdItemKeys: ["ITEM\nNEW"] })],
    ["wrong library", applyReceipt({ libraryID: 2 })],
    ["created collection collides with parent", applyReceipt({
      createdCollectionKey: "PARENT",
      addedMemberships: [{ itemKey: "ITEM-NEW", collectionKey: "PARENT" }],
    })],
    ["missing created collection", applyReceipt({ createdCollectionKey: null })],
    ["missing created item", applyReceipt({ createdItemKeys: [] })],
    ["missing membership", applyReceipt({ addedMemberships: [] })],
  ])("fails terminally on a malformed or incoherent Apply receipt: %s", async (_label, rawReceipt) => {
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockResolvedValueOnce(rawReceipt as LibraryApplyReceipt);
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/failed.*manual inspection/i);

    expect(service.getReviews(scope())[0]).toMatchObject({
      state: "failed",
      canApply: false,
      statusMessage: expect.stringMatching(/manual inspection/i),
    });
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
  });

  it("rejects a success receipt that claims a reused item was newly created", async () => {
    const reuse = resolution("reuse-existing", {
      status: "reuse",
      candidates: [candidate("bound-reuse-existing", "Existing paper", {
        localItemKey: "LOCAL-1",
        localItemVersion: 3,
      })],
    });
    const { service, host } = importServiceHarness([resolution("create-new"), reuse]);
    vi.mocked(host.apply).mockResolvedValueOnce(applyReceipt({
      createdItemKeys: ["LOCAL-1"],
      addedMemberships: [{ itemKey: "LOCAL-1", collectionKey: "COLLECTION-NEW" }],
    }));
    const capabilityIds = await lookupCapabilities(service, [
      { client_ref: "create-new", title: "New paper" },
      { client_ref: "reuse-existing", title: "Existing paper" },
    ]);
    await propose(service, capabilityIds);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/manual inspection/i);

    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
    expect(service.getReviews(scope())[0]?.state).toBe("failed");
  });

  it("fails terminally on a hostile Apply receipt and heals the queue", async () => {
    const hostileReceipt = new Proxy(applyReceipt() as object, {
      getPrototypeOf() { throw new Error("hostile receipt prototype"); },
    });
    const results = [resolution("first"), resolution("second")];
    const { service, host } = importServiceHarness(results);
    vi.mocked(host.apply)
      .mockResolvedValueOnce(hostileReceipt as LibraryApplyReceipt)
      .mockResolvedValueOnce(applyReceipt({
        createdCollectionKey: "COLLECTION-SECOND",
        createdItemKeys: ["ITEM-SECOND"],
        addedMemberships: [{ itemKey: "ITEM-SECOND", collectionKey: "COLLECTION-SECOND" }],
      }));
    const [firstCapability] = await lookupCapabilities(service, [{ client_ref: "first", title: "First" }]);
    await propose(service, [firstCapability!]);
    const [secondCapability] = await lookupCapabilities(service, [{ client_ref: "second", title: "Second" }]);
    await propose(service, [secondCapability!], scope(), { collection_name: "Second target" });
    const [firstReview, secondReview] = service.getReviews(scope());

    const first = service.resolveReview(firstReview!.id, "accept");
    const second = service.resolveReview(secondReview!.id, "accept");

    await expect(first).rejects.toThrow(/failed.*manual inspection/i);
    await expect(second).resolves.toMatchObject({ decision: "accepted", reviewId: secondReview!.id });
    expect(service.getReviews(scope()).map((review) => review.state)).toEqual(["failed", "accepted"]);
    expect(service.getReviews(scope())[0]?.statusMessage).toMatch(/manual inspection/i);
    expect(host.compensate).not.toHaveBeenCalled();
  });

  it("samples stateful Apply receipt fields once into an immutable accepted snapshot", async () => {
    const reads = new Map<string, number>();
    const once = <T>(name: string, value: T) => oneShotGetter(reads, name, value);
    const createdItemKeys = ["ITEM-NEW"];
    Object.defineProperty(createdItemKeys, "0", {
      configurable: true,
      enumerable: true,
      get: once("createdItemKeys[0]", "ITEM-NEW"),
    });
    const membership = Object.create(null) as Record<string, unknown>;
    Object.defineProperties(membership, {
      itemKey: { enumerable: true, get: once("membership.itemKey", "ITEM-NEW") },
      collectionKey: { enumerable: true, get: once("membership.collectionKey", "COLLECTION-NEW") },
    });
    const addedMemberships = [membership];
    Object.defineProperty(addedMemberships, "0", {
      configurable: true,
      enumerable: true,
      get: once("addedMemberships[0]", membership),
    });
    const rawReceipt = Object.create(null) as Record<string, unknown>;
    for (const [name, value] of Object.entries({
      libraryID: 1,
      createdCollectionKey: "COLLECTION-NEW",
      createdItemKeys,
      addedMemberships,
    })) {
      Object.defineProperty(rawReceipt, name, {
        configurable: true,
        enumerable: true,
        get: once(name, value),
      });
    }
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockResolvedValueOnce(rawReceipt as unknown as LibraryApplyReceipt);
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    const accepted = await service.resolveReview(review.id, "accept");

    expect(accepted).toEqual({ decision: "accepted", reviewId: review.id, receipt: applyReceipt() });
    expect(Object.fromEntries(reads)).toEqual({
      libraryID: 1,
      createdCollectionKey: 1,
      createdItemKeys: 1,
      addedMemberships: 1,
      "createdItemKeys[0]": 1,
      "addedMemberships[0]": 1,
      "membership.itemKey": 1,
      "membership.collectionKey": 1,
    });
    expect(service.getReviews(scope())[0]?.state).toBe("accepted");
  });

  it("isolates an Apply receipt from host mutation while invalidation is pending", async () => {
    const invalidation = deferred<void>();
    const rawReceipt = applyReceipt();
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockResolvedValueOnce(rawReceipt);
    vi.mocked(host.invalidateLibrary).mockImplementationOnce(async () => invalidation.promise);
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    const accepting = service.resolveReview(review.id, "accept");
    await vi.waitFor(() => expect(host.invalidateLibrary).toHaveBeenCalledOnce());
    (rawReceipt.createdItemKeys as string[])[0] = "MUTATED-ITEM";
    (rawReceipt.addedMemberships as Array<{ itemKey: string; collectionKey: string }>)[0] = {
      itemKey: "MUTATED-ITEM",
      collectionKey: "MUTATED-COLLECTION",
    };
    invalidation.resolve();

    await expect(accepting).resolves.toEqual({
      decision: "accepted",
      reviewId: review.id,
      receipt: applyReceipt(),
    });
    expect(service.getReviews(scope())[0]?.state).toBe("accepted");
  });

  it("keeps a successful Apply accepted when snapshot invalidation fails", async () => {
    const { service, host } = importServiceHarness();
    vi.mocked(host.invalidateLibrary).mockRejectedValueOnce(new Error("snapshot cache unavailable"));
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).resolves.toEqual({
      decision: "accepted",
      reviewId: review.id,
      receipt: applyReceipt(),
    });

    expect(service.getReviews(scope())[0]).toMatchObject({
      state: "accepted",
      statusMessage: expect.stringMatching(/applied.*snapshot|reload/i),
    });
    expect(host.compensate).not.toHaveBeenCalled();
    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/already resolved/i);
  });

  it("fails terminally without compensation for a generic Apply error", async () => {
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockRejectedValueOnce(new Error("save failed without receipt"));
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/failed.*save failed without receipt/i);

    expect(service.getReviews(scope())[0]).toMatchObject({ state: "failed", canApply: false });
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/already resolved/i);
    expect(host.apply).toHaveBeenCalledOnce();
  });

  it("totally rejects a hostile failure proxy as generic and heals the queue", async () => {
    const hostileFailure = new Proxy(Object.create(null) as object, {
      getPrototypeOf() { throw new Error("hostile prototype trap"); },
    });
    const results = [resolution("first"), resolution("second")];
    const { service, host } = importServiceHarness(results);
    vi.mocked(host.apply)
      .mockRejectedValueOnce(hostileFailure)
      .mockResolvedValueOnce(applyReceipt({
        createdCollectionKey: "COLLECTION-SECOND",
        createdItemKeys: ["ITEM-SECOND"],
        addedMemberships: [{ itemKey: "ITEM-SECOND", collectionKey: "COLLECTION-SECOND" }],
      }));
    const [firstCapability] = await lookupCapabilities(service, [{ client_ref: "first", title: "First" }]);
    await propose(service, [firstCapability!]);
    const [secondCapability] = await lookupCapabilities(service, [{ client_ref: "second", title: "Second" }]);
    await propose(service, [secondCapability!], scope(), { collection_name: "Second target" });
    const [firstReview, secondReview] = service.getReviews(scope());

    const first = service.resolveReview(firstReview!.id, "accept");
    const second = service.resolveReview(secondReview!.id, "accept");

    await expect(first).rejects.toThrow(/failed.*without a partial receipt/i);
    await expect(second).resolves.toMatchObject({ decision: "accepted", reviewId: secondReview!.id });
    expect(service.getReviews(scope()).map((review) => review.state)).toEqual(["failed", "accepted"]);
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["prototype spoof", Object.assign(Object.create(LibraryApplyFailure.prototype) as object, {
      message: "spoofed failure",
      receipt: applyReceipt(),
    })],
    ["foreign module copy", new class ForeignLibraryApplyFailure extends Error {
      readonly receipt = applyReceipt();
    }("foreign failure")],
    ["Proxy wrapper", new Proxy(new LibraryApplyFailure("wrapped failure", applyReceipt()), {})],
  ])("does not compensate a %s", async (_label, failure) => {
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockRejectedValueOnce(failure);
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/without a partial receipt/i);

    expect(service.getReviews(scope())[0]?.state).toBe("failed");
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
  });

  it("refuses to construct a trusted partial failure from a malformed receipt", () => {
    expect(() => new LibraryApplyFailure("partial write", applyReceipt({
      createdItemKeys: ["ITEM-NEW", "ITEM-NEW"],
    }))).toThrow(/duplicate created item/i);
  });

  it("trusts a same-module subclass but compensates its constructor receipt, not a replaced public receipt", async () => {
    class TrustedApplyFailure extends LibraryApplyFailure {}
    const trustedReceipt = applyReceipt();
    const forgedReceipt = applyReceipt({
      libraryID: 99,
      createdCollectionKey: "FORGED-COLLECTION",
      createdItemKeys: ["FORGED-ITEM"],
      addedMemberships: [{ itemKey: "FORGED-ITEM", collectionKey: "FORGED-COLLECTION" }],
    });
    const failure = new TrustedApplyFailure("partial write", trustedReceipt);
    Object.defineProperty(failure, "receipt", { configurable: true, value: forgedReceipt });
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockRejectedValueOnce(failure);
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/rolled back/i);

    expect(host.compensate).toHaveBeenCalledOnce();
    expect(host.compensate).toHaveBeenCalledWith(trustedReceipt);
    expect(host.compensate).not.toHaveBeenCalledWith(forgedReceipt);
    expect(service.getReviews(scope())[0]?.state).toBe("failed");
  });

  it.each([
    ["wrong library", applyReceipt({ libraryID: 2 })],
    ["created collection collides with parent", applyReceipt({
      createdCollectionKey: "PARENT",
      addedMemberships: [{ itemKey: "ITEM-NEW", collectionKey: "PARENT" }],
    })],
    ["too many created items", applyReceipt({
      createdItemKeys: ["ITEM-NEW", "ITEM-OTHER"],
      addedMemberships: [
        { itemKey: "ITEM-NEW", collectionKey: "COLLECTION-NEW" },
        { itemKey: "ITEM-OTHER", collectionKey: "COLLECTION-NEW" },
      ],
    })],
    ["unowned membership", applyReceipt({
      addedMemberships: [{ itemKey: "ITEM-OTHER", collectionKey: "COLLECTION-NEW" }],
    })],
  ])("does not compensate a trusted but plan-incoherent partial receipt: %s", async (_label, receipt) => {
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockRejectedValueOnce(new LibraryApplyFailure("partial write", receipt));
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/manual inspection/i);

    expect(service.getReviews(scope())[0]?.state).toBe("failed");
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
  });

  it("does not compensate a partial receipt that claims a reused item was newly created", async () => {
    const reuse = resolution("reuse-existing", {
      status: "reuse",
      candidates: [candidate("bound-reuse-existing", "Existing paper", {
        localItemKey: "LOCAL-1",
        localItemVersion: 3,
      })],
    });
    const { service, host } = importServiceHarness([resolution("create-new"), reuse]);
    const receipt = applyReceipt({
      createdItemKeys: ["LOCAL-1"],
      addedMemberships: [{ itemKey: "LOCAL-1", collectionKey: "COLLECTION-NEW" }],
    });
    vi.mocked(host.apply).mockRejectedValueOnce(new LibraryApplyFailure("partial write", receipt));
    const capabilityIds = await lookupCapabilities(service, [
      { client_ref: "create-new", title: "New paper" },
      { client_ref: "reuse-existing", title: "Existing paper" },
    ]);
    await propose(service, capabilityIds);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/manual inspection/i);

    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
    expect(service.getReviews(scope())[0]?.state).toBe("failed");
  });

  it("compensates a partial Apply receipt and reports complete rollback", async () => {
    const { service, host } = importServiceHarness();
    const receipt = applyReceipt();
    vi.mocked(host.apply).mockRejectedValueOnce(new LibraryApplyFailure("item save failed", receipt));
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/rolled back/i);

    expect(host.compensate).toHaveBeenCalledOnce();
    expect(host.compensate).toHaveBeenCalledWith(receipt);
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
    expect(service.getReviews(scope())[0]).toMatchObject({
      state: "failed",
      statusMessage: expect.stringMatching(/rolled back/i),
    });
  });

  it.each([
    ["non-boolean complete", { complete: "yes", survivors: [] }],
    ["complete with survivors", {
      complete: true,
      survivors: [{ kind: "created-item", itemKey: "ITEM-NEW", error: "still present" }],
    }],
    ["incomplete without survivors", { complete: false, survivors: [] }],
    ["survivor with extra field", {
      complete: false,
      survivors: [{ kind: "created-item", itemKey: "ITEM-NEW", error: "still present", extra: true }],
    }],
    ["unsafe survivor key", {
      complete: false,
      survivors: [{ kind: "created-item", itemKey: "ITEM\nNEW", error: "still present" }],
    }],
    ["unknown survivor kind", {
      complete: false,
      survivors: [{ kind: "item", itemKey: "ITEM-NEW", error: "still present" }],
    }],
    ["duplicate survivor", {
      complete: false,
      survivors: [
        { kind: "created-item", itemKey: "ITEM-NEW", error: "first" },
        { kind: "created-item", itemKey: "ITEM-NEW", error: "second" },
      ],
    }],
    ["survivor absent from receipt", {
      complete: false,
      survivors: [{ kind: "created-item", itemKey: "ITEM-OTHER", error: "still present" }],
    }],
  ])("treats a malformed rollback result as compensation failure: %s", async (_label, rollback) => {
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockRejectedValueOnce(new LibraryApplyFailure("partial write", applyReceipt()));
    vi.mocked(host.compensate).mockResolvedValueOnce(rollback as never);
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept"))
      .rejects.toThrow(/rollback failed.*manual inspection/i);

    expect(service.getReviews(scope())[0]).toMatchObject({
      state: "failed",
      statusMessage: expect.stringMatching(/rollback failed.*manual inspection/i),
    });
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
  });

  it("treats a hostile rollback result as compensation failure without stranding", async () => {
    const hostileRollback = new Proxy({ complete: true, survivors: [] } as object, {
      getPrototypeOf() { throw new Error("hostile rollback prototype"); },
    });
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockRejectedValueOnce(new LibraryApplyFailure("partial write", applyReceipt()));
    vi.mocked(host.compensate).mockResolvedValueOnce(hostileRollback as never);
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept"))
      .rejects.toThrow(/rollback failed.*manual inspection/i);

    expect(service.getReviews(scope())[0]?.state).toBe("failed");
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
  });

  it("samples a rollback result once and retains its plain survivor snapshot", async () => {
    const reads = new Map<string, number>();
    const once = <T>(name: string, value: T) => oneShotGetter(reads, name, value);
    const survivor = Object.create(null) as Record<string, unknown>;
    for (const [name, value] of Object.entries({
      kind: "created-item",
      itemKey: "ITEM-NEW",
      error: `${"erase failure ".repeat(40)}\u202E`,
    })) {
      Object.defineProperty(survivor, name, { enumerable: true, get: once(`survivor.${name}`, value) });
    }
    const survivors = [survivor];
    Object.defineProperty(survivors, "0", {
      configurable: true,
      enumerable: true,
      get: once("survivors[0]", survivor),
    });
    const rollback = Object.create(null) as Record<string, unknown>;
    Object.defineProperties(rollback, {
      complete: { enumerable: true, get: once("complete", false) },
      survivors: { enumerable: true, get: once("survivors", survivors) },
    });
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockRejectedValueOnce(new LibraryApplyFailure("partial write", applyReceipt()));
    vi.mocked(host.compensate).mockResolvedValueOnce(rollback as unknown as never);
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/rollback.*incomplete/i);

    expect(Object.fromEntries(reads)).toEqual({
      complete: 1,
      survivors: 1,
      "survivors[0]": 1,
      "survivor.kind": 1,
      "survivor.itemKey": 1,
      "survivor.error": 1,
    });
    const status = service.getReviews(scope())[0]!.statusMessage;
    expect(status).toContain("ITEM-NEW");
    expect(UNSAFE_TEST_TEXT.test(status)).toBe(false);
    expect([...status].length).toBeLessThanOrEqual(280);
  });

  it("isolates rollback survivors from host mutation while invalidation is pending", async () => {
    const invalidation = deferred<void>();
    const survivor = { kind: "created-item" as const, itemKey: "ITEM-NEW", error: "erase failed" };
    const rollback = { complete: false, survivors: [survivor] };
    const { service, host } = importServiceHarness();
    vi.mocked(host.apply).mockRejectedValueOnce(new LibraryApplyFailure("partial write", applyReceipt()));
    vi.mocked(host.compensate).mockResolvedValueOnce(rollback);
    vi.mocked(host.invalidateLibrary).mockImplementationOnce(async () => invalidation.promise);
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    const resolving = service.resolveReview(review.id, "accept");
    const rejected = expect(resolving).rejects.toThrow(/rollback.*incomplete/i);
    await vi.waitFor(() => expect(host.invalidateLibrary).toHaveBeenCalledOnce());
    survivor.itemKey = "MUTATED-ITEM";
    invalidation.resolve();
    await rejected;

    const status = service.getReviews(scope())[0]!.statusMessage;
    expect(status).toContain("ITEM-NEW");
    expect(status).not.toContain("MUTATED-ITEM");
    expect(service.getReviews(scope())[0]?.state).toBe("failed");
  });

  it("reports exact bounded survivor keys after incomplete rollback", async () => {
    const { service, host } = importServiceHarness();
    const receipt = applyReceipt({
      createdCollectionKey: "COLLECTION-SURVIVOR",
      createdItemKeys: ["ITEM-SURVIVOR"],
      addedMemberships: [{ itemKey: "ITEM-SURVIVOR", collectionKey: "COLLECTION-SURVIVOR" }],
    });
    vi.mocked(host.apply).mockRejectedValueOnce(new LibraryApplyFailure("item save failed", receipt));
    vi.mocked(host.compensate).mockResolvedValueOnce({
      complete: false,
      survivors: [
        { kind: "membership", itemKey: "ITEM-SURVIVOR", collectionKey: "COLLECTION-SURVIVOR", error: "remove failed" },
        { kind: "created-item", itemKey: "ITEM-SURVIVOR", error: "erase failed" },
        { kind: "collection", collectionKey: "COLLECTION-SURVIVOR", error: "erase failed" },
      ],
    });
    const [capabilityId] = await lookupCapabilities(service, [{ client_ref: "shor", title: "Shor" }]);
    await propose(service, [capabilityId!]);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/rollback.*incomplete/i);

    const failed = service.getReviews(scope())[0]!;
    expect(failed.state).toBe("failed");
    expect(failed.statusMessage).toContain("ITEM-SURVIVOR");
    expect(failed.statusMessage).toContain("COLLECTION-SURVIVOR");
    expect([...failed.statusMessage].length).toBeLessThanOrEqual(280);
    expect(host.invalidateLibrary).toHaveBeenCalledWith(1);
    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/already resolved/i);
    expect(host.apply).toHaveBeenCalledOnce();
  });

  it("never truncates a displayed survivor key and reports the bounded omission count", async () => {
    const results = Array.from({ length: 20 }, (_, index) => resolution(`create-${index}`));
    const itemKeys = results.map((_, index) => `ITEM-${index.toString().padStart(3, "0")}`);
    const receipt = applyReceipt({
      createdItemKeys: itemKeys,
      addedMemberships: itemKeys.map((itemKey) => ({ itemKey, collectionKey: "COLLECTION-NEW" })),
    });
    const { service, host } = importServiceHarness(results);
    vi.mocked(host.apply).mockRejectedValueOnce(
      new LibraryApplyFailure("item save failed", receipt),
    );
    vi.mocked(host.compensate).mockResolvedValueOnce({
      complete: false,
      survivors: itemKeys.map((itemKey) => ({
        kind: "created-item" as const,
        itemKey,
        error: "erase failed",
      })),
    });
    vi.mocked(host.invalidateLibrary).mockRejectedValueOnce(new Error("cache unavailable"));
    const capabilityIds = await lookupCapabilities(
      service,
      results.map((entry) => ({ client_ref: entry.clientRef, title: entry.clientRef })),
    );
    await propose(service, capabilityIds);
    const review = service.getReviews(scope())[0]!;

    await expect(service.resolveReview(review.id, "accept")).rejects.toThrow(/rollback.*incomplete/i);

    const status = service.getReviews(scope())[0]!.statusMessage;
    expect([...status].length).toBeLessThanOrEqual(280);
    expect(status).toMatch(/\d+ survivors omitted/i);
    expect(status).toMatch(/snapshot.*reload/i);
    expect(status.match(/ITEM-\d+/gu)?.every((key) => /^ITEM-\d{3}$/u.test(key))).toBe(true);
    expect(status).not.toMatch(/ITEM-\d{0,2} Snapshot/u);
  });

  it("preserves the primary partial-failure result when compensation or invalidation fails", async () => {
    const compensationFailure = importServiceHarness();
    vi.mocked(compensationFailure.host.apply).mockRejectedValueOnce(
      new LibraryApplyFailure("item save failed", applyReceipt()),
    );
    vi.mocked(compensationFailure.host.compensate).mockRejectedValueOnce(new Error("rollback host unavailable"));
    const [compensationCapability] = await lookupCapabilities(
      compensationFailure.service,
      [{ client_ref: "shor", title: "Shor" }],
    );
    await propose(compensationFailure.service, [compensationCapability!]);
    const compensationReview = compensationFailure.service.getReviews(scope())[0]!;

    await expect(compensationFailure.service.resolveReview(compensationReview.id, "accept"))
      .rejects.toThrow(/rollback failed.*rollback host unavailable/i);
    expect(compensationFailure.service.getReviews(scope())[0]).toMatchObject({ state: "failed" });
    expect(compensationFailure.host.invalidateLibrary).toHaveBeenCalledWith(1);

    const invalidationFailure = importServiceHarness();
    vi.mocked(invalidationFailure.host.apply).mockRejectedValueOnce(
      new LibraryApplyFailure("item save failed", applyReceipt()),
    );
    vi.mocked(invalidationFailure.host.invalidateLibrary).mockRejectedValueOnce(new Error("cache unavailable"));
    const [invalidationCapability] = await lookupCapabilities(
      invalidationFailure.service,
      [{ client_ref: "shor", title: "Shor" }],
    );
    await propose(invalidationFailure.service, [invalidationCapability!]);
    const invalidationReview = invalidationFailure.service.getReviews(scope())[0]!;

    await expect(invalidationFailure.service.resolveReview(invalidationReview.id, "accept"))
      .rejects.toThrow(/rolled back/i);
    expect(invalidationFailure.service.getReviews(scope())[0]).toMatchObject({
      state: "failed",
      statusMessage: expect.stringMatching(/rolled back.*snapshot|rolled back.*reload/i),
    });
  });

  it("recovers the exclusive queue after failure without retrying the failed review", async () => {
    const results = [resolution("first"), resolution("second")];
    const { service, host } = importServiceHarness(results);
    vi.mocked(host.apply)
      .mockRejectedValueOnce(new Error("first apply failed"))
      .mockResolvedValueOnce(applyReceipt({
        createdCollectionKey: "COLLECTION-SECOND",
        createdItemKeys: ["ITEM-SECOND"],
        addedMemberships: [{ itemKey: "ITEM-SECOND", collectionKey: "COLLECTION-SECOND" }],
      }));
    const [firstCapability] = await lookupCapabilities(service, [{ client_ref: "first", title: "First" }]);
    await propose(service, [firstCapability!]);
    const [secondCapability] = await lookupCapabilities(service, [{ client_ref: "second", title: "Second" }]);
    await propose(service, [secondCapability!]);
    const [firstReview, secondReview] = service.getReviews(scope());

    const first = service.resolveReview(firstReview!.id, "accept");
    const second = service.resolveReview(secondReview!.id, "accept");

    await expect(first).rejects.toThrow(/first apply failed/i);
    await expect(second).resolves.toMatchObject({ decision: "accepted", reviewId: secondReview!.id });
    await expect(service.resolveReview(firstReview!.id, "accept")).rejects.toThrow(/already resolved/i);
    expect(host.apply).toHaveBeenCalledTimes(2);
    expect(service.getReviews(scope()).map((review) => review.state)).toEqual(["failed", "accepted"]);
  });

  it("does not retain a review when host preflight fails or returns incomplete row coverage", async () => {
    const failed = importServiceHarness([resolution("shor")], async () => { throw new Error("host read failed"); });
    const [failedId] = await lookupCapabilities(failed.service, [
      { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
    ]);
    await expect(propose(failed.service, [failedId!])).rejects.toThrow(/host read failed/i);
    expect(failed.service.getReviews(scope())).toEqual([]);
    expect(failed.onState).not.toHaveBeenCalled();

    const incomplete = importServiceHarness([resolution("shor")], async (plan) => ({
      ...defaultPreflight(plan),
      dispositions: [],
    }));
    const [incompleteId] = await lookupCapabilities(incomplete.service, [
      { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
    ]);
    await expect(propose(incomplete.service, [incompleteId!])).rejects.toThrow(/preflight.*rows|complete/i);
    expect(incomplete.service.getReviews(scope())).toEqual([]);
  });

  it("preserves an exact padded preflight digest for later stale comparison", async () => {
    const { service } = importServiceHarness([resolution("shor")], async (plan) => ({
      ...defaultPreflight(plan),
      digest: " digest-v1 ",
    }));
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
    ]);
    await propose(service, [capabilityId!]);
    const reviewId = service.getReviews(scope())[0]!.id;
    const internal = service as unknown as {
      pending: Map<string, { proposalPreflight: LibraryImportPreflight }>;
    };

    expect(internal.pending.get(reviewId)?.proposalPreflight.digest).toBe(" digest-v1 ");
  });

  it("rejects a padded host row ID instead of normalizing it onto a bound row", async () => {
    const { service } = importServiceHarness([resolution("shor")], async (plan) => {
      const preflight = defaultPreflight(plan);
      return {
        ...preflight,
        dispositions: preflight.dispositions.map((entry) => ({ ...entry, rowId: ` ${entry.rowId} ` })),
      };
    });
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
    ]);

    await expect(propose(service, [capabilityId!])).rejects.toThrow(/exact.*rows|complete.*rows/i);
    expect(service.getReviews(scope())).toEqual([]);
  });

  it("rejects preflight effects that do not match the host-bound final plan", async () => {
    const createAsReuse = importServiceHarness([resolution("create-1")], async (plan) => {
      const preflight = defaultPreflight(plan);
      return {
        ...preflight,
        dispositions: preflight.dispositions.map((entry) => ({
          ...entry,
          effect: "reuse" as const,
          itemKey: "LOCAL-1",
          itemVersion: 3,
        })),
      };
    });
    const [createId] = await lookupCapabilities(createAsReuse.service, [
      { client_ref: "create-1", title: "Create" },
    ]);
    await expect(propose(createAsReuse.service, [createId!])).rejects.toThrow(/create.*effect|coherent/i);

    const reuseResult = resolution("reuse-1", {
      status: "reuse",
      candidates: [candidate("bound-reuse-1", "Existing", {
        localItemKey: "LOCAL-1",
        localItemVersion: 3,
      })],
    });
    const reuseAsCreate = importServiceHarness([reuseResult], async (plan) => {
      const preflight = defaultPreflight(plan);
      return {
        ...preflight,
        dispositions: preflight.dispositions.map((entry) => ({
          ...entry,
          effect: "create" as const,
          itemKey: null,
          itemVersion: null,
        })),
      };
    });
    const [reuseId] = await lookupCapabilities(reuseAsCreate.service, [
      { client_ref: "reuse-1", title: "Reuse" },
    ]);
    await expect(propose(reuseAsCreate.service, [reuseId!])).rejects.toThrow(/reuse.*effect|coherent/i);

    const unresolvedAsOmit = importServiceHarness([
      resolution("unresolved-1", { status: "unresolved", candidates: [], reason: "No match" }),
    ], async (plan) => {
      const preflight = defaultPreflight(plan);
      return {
        ...preflight,
        dispositions: preflight.dispositions.map((entry) => ({ ...entry, effect: "omit" as const })),
      };
    });
    const [unresolvedId] = await lookupCapabilities(unresolvedAsOmit.service, [
      { client_ref: "unresolved-1", title: "Unknown" },
    ]);
    await expect(propose(unresolvedAsOmit.service, [unresolvedId!])).rejects.toThrow(/conflict.*effect|coherent/i);
  });

  it("requires exact local identity and version for reuse preflight effects", async () => {
    const reuseResult = resolution("reuse-1", {
      status: "reuse",
      candidates: [candidate("bound-reuse-1", "Existing", {
        localItemKey: "LOCAL-1",
        localItemVersion: 3,
      })],
    });
    for (const fields of [
      { itemKey: null, itemVersion: 3 },
      { itemKey: "LOCAL-1", itemVersion: null },
      { itemKey: "OTHER", itemVersion: 3 },
      { itemKey: "LOCAL-1", itemVersion: 4 },
    ]) {
      const instance = importServiceHarness([reuseResult], async (plan) => {
        const preflight = defaultPreflight(plan);
        return {
          ...preflight,
          dispositions: preflight.dispositions.map((entry) => ({ ...entry, ...fields })),
        };
      });
      const [capabilityId] = await lookupCapabilities(instance.service, [
        { client_ref: "reuse-1", title: "Reuse" },
      ]);
      await expect(propose(instance.service, [capabilityId!]))
        .rejects.toThrow(/reuse.*item|identity|version|coherent/i);
      expect(instance.service.getReviews(scope())).toEqual([]);
    }
  });

  it("keeps a coherent host conflict review disabled", async () => {
    const { service } = importServiceHarness([resolution("create-1")], async (plan) => {
      const preflight = defaultPreflight(plan);
      return {
        ...preflight,
        dispositions: preflight.dispositions.map((entry) => ({
          ...entry,
          effect: "conflict" as const,
          itemKey: null,
          itemVersion: null,
          membershipExists: false,
        })),
      };
    });
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "create-1", title: "Create" },
    ]);
    await propose(service, [capabilityId!]);

    expect(service.getReviews(scope())[0]).toMatchObject({
      canApply: false,
      rows: [{ effectLabel: "Choose a candidate or acknowledge omission" }],
    });
  });

  it("rejects an already-member claim when the target collection does not exist", async () => {
    const reuseResult = resolution("reuse-1", {
      status: "reuse",
      candidates: [candidate("bound-reuse-1", "Existing", {
        localItemKey: "LOCAL-1",
        localItemVersion: 3,
      })],
    });
    const { service } = importServiceHarness([reuseResult], async (plan) => {
      const preflight = defaultPreflight(plan);
      return {
        ...preflight,
        siblingCollectionKey: null,
        dispositions: preflight.dispositions.map((entry) => ({ ...entry, membershipExists: true })),
      };
    });
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "reuse-1", title: "Existing" },
    ]);

    await expect(propose(service, [capabilityId!]))
      .rejects.toThrow(/membership.*target|collection.*exist|absent.*collection/i);
    expect(service.getReviews(scope())).toEqual([]);
  });

  it("counts collection creation and coherent row effects from the exact final plan", async () => {
    const reuseResult = resolution("reuse-1", {
      status: "reuse",
      candidates: [candidate("bound-reuse-1", "Existing", {
        localItemKey: "LOCAL-1",
        localItemVersion: 3,
      })],
    });
    const absentReuse = importServiceHarness([reuseResult]);
    const [absentReuseId] = await lookupCapabilities(absentReuse.service, [
      { client_ref: "reuse-1", title: "Existing" },
    ]);
    await propose(absentReuse.service, [absentReuseId!]);
    expect(absentReuse.service.getReviews(scope())[0]).toMatchObject({
      effectCount: 2,
      canApply: true,
      rows: [{ effectLabel: "Reuse an existing item and add it to the target collection" }],
    });

    const existingMember = importServiceHarness([reuseResult], async (plan) => {
      const preflight = defaultPreflight(plan);
      return {
        ...preflight,
        siblingCollectionKey: "TARGET-COLLECTION",
        dispositions: preflight.dispositions.map((entry) => ({ ...entry, membershipExists: true })),
      };
    });
    const [existingMemberId] = await lookupCapabilities(existingMember.service, [
      { client_ref: "reuse-1", title: "Existing" },
    ]);
    await propose(existingMember.service, [existingMemberId!]);
    expect(existingMember.service.getReviews(scope())[0]).toMatchObject({
      effectCount: 0,
      canApply: true,
      rows: [{ effectLabel: "Reuse an item already in the target collection" }],
    });

    const absentCreate = importServiceHarness([resolution("create-1")]);
    const [absentCreateId] = await lookupCapabilities(absentCreate.service, [
      { client_ref: "create-1", title: "Create" },
    ]);
    await propose(absentCreate.service, [absentCreateId!]);
    expect(absentCreate.service.getReviews(scope())[0]).toMatchObject({
      effectCount: 2,
      rows: [{ effectLabel: "Create a new Zotero item" }],
    });

    const existingCreate = importServiceHarness([resolution("create-1")], async (plan) => ({
      ...defaultPreflight(plan),
      siblingCollectionKey: "TARGET-COLLECTION",
    }));
    const [existingCreateId] = await lookupCapabilities(existingCreate.service, [
      { client_ref: "create-1", title: "Create" },
    ]);
    await propose(existingCreate.service, [existingCreateId!]);
    expect(existingCreate.service.getReviews(scope())[0]).toMatchObject({
      effectCount: 1,
      rows: [{ effectLabel: "Create a new Zotero item" }],
    });
  });

  it("adds no row effect for omission or conflict while retaining collection creation", async () => {
    const unresolved = resolution("unresolved-1", {
      status: "unresolved",
      candidates: [],
      reason: "No exact match",
    });
    const { service, host } = importServiceHarness([unresolved]);
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "unresolved-1", title: "Unknown" },
    ]);
    await propose(service, [capabilityId!]);
    const reviewId = service.getReviews(scope())[0]!.id;

    expect(service.getReviews(scope())[0]).toMatchObject({
      effectCount: 1,
      canApply: false,
      rows: [{ effectLabel: "Choose a candidate or acknowledge omission" }],
    });
    service.setRowResolution(reviewId, "unresolved-1", { omit: true });
    await vi.waitFor(() => expect(service.getReviews(scope())[0]?.canApply).toBe(true));
    expect(service.getReviews(scope())[0]).toMatchObject({
      effectCount: 1,
      rows: [{ effectLabel: "Omit this citation" }],
    });
    expect(host.apply).not.toHaveBeenCalled();
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).not.toHaveBeenCalled();
  });

  it("disables Apply while refreshing a row choice and atomically publishes the final-plan effects", async () => {
    const refresh = deferred<LibraryImportPreflight>();
    let calls = 0;
    const ambiguous = resolution("ambiguous-1", {
      status: "ambiguous",
      candidates: [candidate("bound-local-1", "Existing match", {
        localItemKey: "LOCAL-1",
        localItemVersion: 1,
      })],
      reason: "One user-selectable exact match",
    });
    const { service, host } = importServiceHarness([ambiguous], async (plan) => {
      calls += 1;
      if (calls === 1) return defaultPreflight(plan);
      return refresh.promise;
    });
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "ambiguous-1", title: "Existing match" },
    ]);
    await propose(service, [capabilityId!]);
    const reviewId = service.getReviews(scope())[0]!.id;

    service.setRowResolution(reviewId, "ambiguous-1", { candidateId: "bound-local-1" });

    expect(service.getReviews(scope())[0]).toMatchObject({
      canApply: false,
      effectCount: 0,
      statusMessage: expect.stringMatching(/refresh|checking/i),
      rows: [{
        selectedCandidateId: "bound-local-1",
        effectLabel: expect.stringMatching(/refresh|checking/i),
      }],
    });
    const refreshPlan = vi.mocked(host.preflight).mock.calls[1]?.[0];
    expect(refreshPlan?.rows).toMatchObject([{ rowId: "ambiguous-1", choiceId: "bound-local-1", omit: false }]);

    refresh.resolve({
      digest: "refresh-digest-1",
      editable: true,
      parentVersion: 7,
      siblingCollectionKey: null,
      dispositions: [{
        rowId: "ambiguous-1",
        effect: "reuse",
        itemKey: "LOCAL-1",
        itemVersion: 1,
        membershipExists: false,
      }],
    });
    await vi.waitFor(() => expect(service.getReviews(scope())[0]?.canApply).toBe(true));

    expect(service.getReviews(scope())[0]).toMatchObject({
      canApply: true,
      effectCount: 2,
      statusMessage: expect.stringMatching(/ready/i),
      rows: [{ effectLabel: "Reuse an existing item and add it to the target collection" }],
    });
    expect(host.apply).not.toHaveBeenCalled();
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).not.toHaveBeenCalled();
  });

  it("ignores stale out-of-order preflight refreshes for earlier row choices", async () => {
    const first = deferred<LibraryImportPreflight>();
    const second = deferred<LibraryImportPreflight>();
    let calls = 0;
    const ambiguous = resolution("ambiguous-1", {
      status: "ambiguous",
      candidates: [
        candidate("bound-local-1", "First", { localItemKey: "LOCAL-1", localItemVersion: 1 }),
        candidate("bound-local-2", "Second", { localItemKey: "LOCAL-2", localItemVersion: 2 }),
      ],
      reason: "Two exact matches",
    });
    const { service, host } = importServiceHarness([ambiguous], async (plan) => {
      calls += 1;
      if (calls === 1) return defaultPreflight(plan);
      return calls === 2 ? first.promise : second.promise;
    });
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "ambiguous-1", title: "Two exact matches" },
    ]);
    await propose(service, [capabilityId!]);
    const reviewId = service.getReviews(scope())[0]!.id;

    service.setRowResolution(reviewId, "ambiguous-1", { candidateId: "bound-local-1" });
    service.setRowResolution(reviewId, "ambiguous-1", { candidateId: "bound-local-2" });
    second.resolve({
      digest: "second-digest",
      editable: true,
      parentVersion: 7,
      siblingCollectionKey: "TARGET-COLLECTION",
      dispositions: [{
        rowId: "ambiguous-1",
        effect: "reuse",
        itemKey: "LOCAL-2",
        itemVersion: 2,
        membershipExists: true,
      }],
    });
    await vi.waitFor(() => expect(service.getReviews(scope())[0]?.canApply).toBe(true));

    first.resolve({
      digest: "first-stale-digest",
      editable: true,
      parentVersion: 7,
      siblingCollectionKey: null,
      dispositions: [{
        rowId: "ambiguous-1",
        effect: "reuse",
        itemKey: "LOCAL-1",
        itemVersion: 1,
        membershipExists: false,
      }],
    });
    await Promise.resolve();
    await Promise.resolve();

    const review = service.getReviews(scope())[0]!;
    expect(review).toMatchObject({
      canApply: true,
      effectCount: 0,
      rows: [{
        selectedCandidateId: "bound-local-2",
        effectLabel: "Reuse an item already in the target collection",
      }],
    });
    const internal = service as unknown as {
      pending: Map<string, { proposalPreflight: LibraryImportPreflight }>;
    };
    expect(internal.pending.get(reviewId)?.proposalPreflight.digest).toBe("second-digest");
    expect(host.apply).not.toHaveBeenCalled();
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).not.toHaveBeenCalled();
  });

  it("catches refresh failure, bounds its status, and leaves Apply disabled with zero writes", async () => {
    const refresh = deferred<LibraryImportPreflight>();
    let calls = 0;
    const unresolved = resolution("unresolved-1", {
      status: "unresolved",
      candidates: [],
      reason: "No exact match",
    });
    const { service, host } = importServiceHarness([unresolved], async (plan) => {
      calls += 1;
      if (calls === 1) return defaultPreflight(plan);
      return refresh.promise;
    });
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "unresolved-1", title: "Unknown" },
    ]);
    await propose(service, [capabilityId!]);
    const reviewId = service.getReviews(scope())[0]!.id;

    service.setRowResolution(reviewId, "unresolved-1", { omit: true });
    expect(service.getReviews(scope())[0]?.canApply).toBe(false);
    refresh.reject(new Error(`${"host failure ".repeat(100)}\u202E`));
    await vi.waitFor(() => expect(service.getReviews(scope())[0]?.statusMessage).toMatch(/refresh failed/i));

    const review = service.getReviews(scope())[0]!;
    expect(review.canApply).toBe(false);
    expect(review.state).toBe("pending");
    expect([...review.statusMessage].length).toBeLessThanOrEqual(280);
    expect(review.statusMessage).not.toContain("\u202E");
    expect(host.apply).not.toHaveBeenCalled();
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).not.toHaveBeenCalled();
  });

  it("refuses an incoherent refresh for an explicitly omitted row", async () => {
    let calls = 0;
    const unresolved = resolution("unresolved-1", {
      status: "unresolved",
      candidates: [],
      reason: "No exact match",
    });
    const { service } = importServiceHarness([unresolved], async (plan) => {
      calls += 1;
      if (calls === 1) return defaultPreflight(plan);
      return {
        digest: "bad-omit-refresh",
        editable: true,
        parentVersion: 7,
        siblingCollectionKey: null,
        dispositions: [{
          rowId: "unresolved-1",
          effect: "create",
          itemKey: null,
          itemVersion: null,
          membershipExists: false,
        }],
      };
    });
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "unresolved-1", title: "Unknown" },
    ]);
    await propose(service, [capabilityId!]);
    const reviewId = service.getReviews(scope())[0]!.id;

    service.setRowResolution(reviewId, "unresolved-1", { omit: true });
    await vi.waitFor(() => expect(service.getReviews(scope())[0]?.statusMessage).toMatch(/refresh failed/i));
    expect(service.getReviews(scope())[0]?.canApply).toBe(false);
  });

  it("publishes a validated refresh even when immediate and completion notifications throw", async () => {
    const refresh = deferred<LibraryImportPreflight>();
    let calls = 0;
    let throwNotifications = false;
    const ambiguous = resolution("ambiguous-1", {
      status: "ambiguous",
      candidates: [candidate("bound-local-1", "Existing match", {
        localItemKey: "LOCAL-1",
        localItemVersion: 1,
      })],
      reason: "One exact match",
    });
    const { service, host } = importServiceHarness([ambiguous], async (plan) => {
      calls += 1;
      if (calls === 1) return defaultPreflight(plan);
      return refresh.promise;
    }, () => {
      if (throwNotifications) throw new Error("UI callback failed");
    });
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "ambiguous-1", title: "Existing match" },
    ]);
    await propose(service, [capabilityId!]);
    const reviewId = service.getReviews(scope())[0]!.id;
    throwNotifications = true;

    expect(() => service.setRowResolution(reviewId, "ambiguous-1", {
      candidateId: "bound-local-1",
    })).not.toThrow();
    expect(service.getReviews(scope())[0]?.canApply).toBe(false);

    refresh.resolve({
      digest: "validated-despite-callbacks",
      editable: true,
      parentVersion: 7,
      siblingCollectionKey: null,
      dispositions: [{
        rowId: "ambiguous-1",
        effect: "reuse",
        itemKey: "LOCAL-1",
        itemVersion: 1,
        membershipExists: false,
      }],
    });
    await vi.waitFor(() => expect(service.getReviews(scope())[0]?.canApply).toBe(true));

    const internal = service as unknown as {
      pending: Map<string, { proposalPreflight: LibraryImportPreflight }>;
    };
    expect(internal.pending.get(reviewId)?.proposalPreflight.digest).toBe("validated-despite-callbacks");
    expect(service.getReviews(scope())[0]?.statusMessage).toMatch(/ready/i);
    expect(host.apply).not.toHaveBeenCalled();
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).not.toHaveBeenCalled();
  });

  it("totally bounds hostile refresh rejections when failure notification also throws", async () => {
    const hostileCoercion = new Proxy(Object.create(null) as object, {
      get() { throw new Error("hostile get trap"); },
      getPrototypeOf() { throw new Error("hostile prototype trap"); },
    });
    const hostileValues: unknown[] = [Object.create(null), hostileCoercion, Symbol("host failure")];

    for (const hostile of hostileValues) {
      let preflightCalls = 0;
      let notificationCalls = 0;
      const unresolved = resolution("unresolved-1", {
        status: "unresolved",
        candidates: [],
        reason: "No exact match",
      });
      const { service, host } = importServiceHarness([unresolved], async (plan) => {
        preflightCalls += 1;
        if (preflightCalls === 1) return defaultPreflight(plan);
        throw hostile;
      }, () => {
        notificationCalls += 1;
        if (notificationCalls >= 3) throw new Error("failure publication callback failed");
      });
      const [capabilityId] = await lookupCapabilities(service, [
        { client_ref: "unresolved-1", title: "Unknown" },
      ]);
      await propose(service, [capabilityId!]);
      const reviewId = service.getReviews(scope())[0]!.id;

      expect(() => service.setRowResolution(reviewId, "unresolved-1", { omit: true })).not.toThrow();
      await vi.waitFor(() => expect(service.getReviews(scope())[0]?.statusMessage).toMatch(/refresh failed/i));

      const review = service.getReviews(scope())[0]!;
      expect(review.canApply).toBe(false);
      expect(review.state).toBe("pending");
      expect([...review.statusMessage].length).toBeLessThanOrEqual(280);
      expect(UNSAFE_TEST_TEXT.test(review.statusMessage)).toBe(false);
      expect(host.apply).not.toHaveBeenCalled();
      expect(host.compensate).not.toHaveBeenCalled();
      expect(host.invalidateLibrary).not.toHaveBeenCalled();
    }
  });
});
