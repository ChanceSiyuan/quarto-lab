import { describe, expect, it, vi } from "vitest";

import {
  CitationCandidateRegistry,
  type BibliographicMetadata,
  type CitationCapabilityScope,
  type ResolvedCitation,
} from "../src/library-citations";
import {
  LOOKUP_CITATIONS_TOOL,
  PROPOSE_LIBRARY_IMPORT_TOOL,
  ReviewedLibraryImportService,
  type BoundLibraryImportPlan,
  type LibraryImportPreflight,
  type LibraryMutationHost,
} from "../src/reviewed-library-import";

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

function importServiceHarness(
  results: readonly ResolvedCitation[] = [resolution("shor")],
  preflight: (plan: BoundLibraryImportPlan) => Promise<LibraryImportPreflight> = async (plan) => defaultPreflight(plan),
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
    apply: vi.fn(async () => { throw new Error("apply must not run in Task 4"); }),
    compensate: vi.fn(async () => ({ complete: true, survivors: [] })),
    invalidateLibrary: vi.fn(async () => {}),
  };
  const onState = vi.fn();
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

  it("claims an eligible acceptance synchronously but leaves Task 5 writes unavailable", async () => {
    const { service, host } = importServiceHarness();
    const [capabilityId] = await lookupCapabilities(service, [
      { client_ref: "shor", doi: "10.1103/physreva.52.r2493" },
    ]);
    await propose(service, [capabilityId!]);
    const reviewId = service.getReviews(scope())[0]!.id;

    const accepting = service.resolveReview(reviewId, "accept");
    expect(service.getReviews(scope())[0]?.state).toBe("resolving");
    await expect(service.resolveReview(reviewId, "accept")).rejects.toThrow(/already resolved|being applied/i);
    await expect(accepting).rejects.toThrow(/Task 5|not available|read-only/i);
    expect(host.apply).not.toHaveBeenCalled();
    expect(host.compensate).not.toHaveBeenCalled();
    expect(host.invalidateLibrary).not.toHaveBeenCalled();
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
      effectCount: 1,
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
      siblingCollectionKey: null,
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
});
