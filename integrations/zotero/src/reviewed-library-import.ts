import type { CodexDynamicToolSpec } from "./codex-service";
import {
  CitationCandidateRegistry,
  type BoundCitationCapability,
  type CitationCapabilityScope,
  type CitationQuery,
  type ResolvedCitation,
} from "./library-citations";

export const LOOKUP_CITATIONS_TOOL = "zotero_lookup_citations" as const;
export const PROPOSE_LIBRARY_IMPORT_TOOL = "zotero_propose_library_import" as const;

const MAX_CAPABILITIES = 50;
const MAX_OPAQUE_ID_CODE_POINTS = 1_000;
const MAX_COLLECTION_NAME_CODE_POINTS = 200;
const MAX_RAW_COLLECTION_NAME_CODE_POINTS = 1_600;
const UNSAFE_TEXT = /[\p{Cc}\p{Cf}\u2028\u2029]/u;
const UNSAFE_TEXT_GLOBAL = /[\p{Cc}\p{Cf}\u2028\u2029]/gu;

type UnknownRecord = Record<string, unknown>;

export type LibraryImportDisposition = "create" | "reuse" | "ambiguous" | "unresolved";

export interface LibraryImportReviewRow {
  id: string;
  clientRef: string;
  citationLabel: string;
  disposition: LibraryImportDisposition;
  effectLabel: string;
  candidates: readonly Readonly<{ candidateId: string; label: string; provenance: string }>[];
  selectedCandidateId: string | null;
  omissionAcknowledged: boolean;
}

export interface LibraryImportReview {
  id: string;
  scope: { threadId: string; libraryID: number | string };
  target: { parentCollectionKey: string | null; collectionName: string; collectionPath: string };
  rows: readonly LibraryImportReviewRow[];
  effectCount: number;
  canApply: boolean;
  state: "pending" | "resolving" | "accepted" | "rejected" | "failed" | "stale";
  statusMessage: string;
}

export interface BoundLibraryImportPlan {
  scope: CitationCapabilityScope;
  target: { parentCollectionKey: string | null; collectionName: string };
  rows: readonly Readonly<{
    rowId: string;
    choiceId: string | null;
    omit: boolean;
    resolverDigest: string;
  }>[];
}

export interface LibraryImportPreflight {
  digest: string;
  editable: boolean;
  parentVersion: number | null;
  siblingCollectionKey: string | null;
  dispositions: readonly Readonly<{
    rowId: string;
    effect: "create" | "reuse" | "omit" | "conflict";
    itemKey: string | null;
    itemVersion: number | null;
    membershipExists: boolean;
  }>[];
}

export interface ValidatedLibraryImportPlan extends BoundLibraryImportPlan {
  preflight: LibraryImportPreflight;
}

export interface LibraryApplyReceipt {
  libraryID: number | string;
  createdCollectionKey: string | null;
  createdItemKeys: readonly string[];
  addedMemberships: readonly Readonly<{ itemKey: string; collectionKey: string }>[];
}

export type LibraryMutationSurvivor =
  | { kind: "membership"; itemKey: string; collectionKey: string; error: string }
  | { kind: "created-item"; itemKey: string; error: string }
  | { kind: "collection"; collectionKey: string; error: string };

export interface LibraryRollbackResult {
  complete: boolean;
  survivors: readonly LibraryMutationSurvivor[];
}

export interface LibraryMutationHost {
  preflight(plan: BoundLibraryImportPlan): Promise<LibraryImportPreflight>;
  apply(plan: ValidatedLibraryImportPlan): Promise<LibraryApplyReceipt>;
  compensate(receipt: LibraryApplyReceipt): Promise<LibraryRollbackResult>;
  invalidateLibrary(libraryID: number | string): Promise<void>;
}

export class LibraryApplyFailure extends Error {
  constructor(message: string, readonly receipt: LibraryApplyReceipt) {
    super(message);
    this.name = "LibraryApplyFailure";
  }
}

export interface LibraryImportResolution {
  decision: "accepted" | "rejected";
  reviewId: string;
  receipt: LibraryApplyReceipt | null;
}

export interface ReviewedLibraryImportOptions {
  createId?: () => string;
}

interface PendingLibraryImportReview {
  publicReview: LibraryImportReview;
  boundPlan: BoundLibraryImportPlan;
  proposalPreflight: LibraryImportPreflight;
  candidateBindings: BoundCandidateIndex;
  revision: number;
}

interface BoundCandidateEffect {
  effect: "create" | "reuse";
  itemKey: string | null;
  itemVersion: number | null;
}

type BoundCandidateIndex = ReadonlyMap<string, ReadonlyMap<string, BoundCandidateEffect>>;

const LOOKUP_CITATIONS_TOOL_SPEC: CodexDynamicToolSpec = {
  name: LOOKUP_CITATIONS_TOOL,
  description: "Resolve cited works into short-lived, subject-bound citation capability IDs. The result performs no Zotero writes.",
  inputSchema: {
    type: "object",
    additionalProperties: false,
    required: ["requests"],
    properties: {
      requests: {
        type: "array",
        minItems: 1,
        maxItems: MAX_CAPABILITIES,
        items: {
          type: "object",
          additionalProperties: false,
          required: ["client_ref"],
          properties: {
            client_ref: { type: "string", minLength: 1, maxLength: MAX_OPAQUE_ID_CODE_POINTS },
            citation: { type: "string", minLength: 1, maxLength: 20_000 },
            doi: { type: "string", minLength: 1, maxLength: MAX_OPAQUE_ID_CODE_POINTS },
            arxiv: { type: "string", minLength: 1, maxLength: MAX_OPAQUE_ID_CODE_POINTS },
            title: { type: "string", minLength: 1, maxLength: 10_000 },
            year: { type: "integer", minimum: 1_000, maximum: 9_999 },
            creators: {
              type: "array",
              maxItems: 50,
              items: { type: "string", minLength: 1, maxLength: MAX_OPAQUE_ID_CODE_POINTS },
            },
          },
          anyOf: [
            { required: ["citation"] },
            { required: ["doi"] },
            { required: ["arxiv"] },
            { required: ["title"] },
          ],
        },
      },
    },
  },
};

const PROPOSE_LIBRARY_IMPORT_TOOL_SPEC: CodexDynamicToolSpec = {
  name: PROPOSE_LIBRARY_IMPORT_TOOL,
  description: "Prepare a read-only Zotero library-import review from one complete citation capability batch. Applying requires a separate user action.",
  inputSchema: {
    type: "object",
    additionalProperties: false,
    required: ["collection_name", "capability_ids"],
    properties: {
      collection_name: { type: "string", minLength: 1, maxLength: MAX_RAW_COLLECTION_NAME_CODE_POINTS },
      parent_collection_key: { type: "string", minLength: 1, maxLength: MAX_OPAQUE_ID_CODE_POINTS },
      capability_ids: {
        type: "array",
        minItems: 1,
        maxItems: MAX_CAPABILITIES,
        uniqueItems: true,
        items: { type: "string", minLength: 1, maxLength: MAX_OPAQUE_ID_CODE_POINTS },
      },
    },
  },
};

/**
 * Read-only citation lookup and import-review coordinator.
 *
 * Proposal arguments can only carry registry-issued capability IDs. Candidate
 * data and resolver digests are recovered from the registry, bound into a
 * host preflight plan, and retained only in memory for a later user decision.
 */
export class ReviewedLibraryImportService {
  readonly tools: readonly CodexDynamicToolSpec[] = [
    LOOKUP_CITATIONS_TOOL_SPEC,
    PROPOSE_LIBRARY_IMPORT_TOOL_SPEC,
  ];

  private readonly pending = new Map<string, PendingLibraryImportReview>();
  private readonly createId: () => string;

  constructor(
    private readonly registry: CitationCandidateRegistry,
    private readonly host: LibraryMutationHost,
    private readonly callbacks: { onState(scope: CitationCapabilityScope): void },
    options: ReviewedLibraryImportOptions = {},
  ) {
    this.createId = options.createId ?? defaultOpaqueId;
  }

  async invokeTool(
    name: string,
    args: Record<string, unknown>,
    scope: CitationCapabilityScope,
  ): Promise<Record<string, unknown>> {
    if (name === LOOKUP_CITATIONS_TOOL) return this.lookupCitations(args, scope);
    if (name === PROPOSE_LIBRARY_IMPORT_TOOL) return this.proposeLibraryImport(args, scope);
    throw new Error(`Unknown Zotero library-import tool: ${name}`);
  }

  getReviews(scope: CitationCapabilityScope): LibraryImportReview[] {
    const normalizedScope = normalizeScope(scope);
    return [...this.pending.values()]
      .filter(({ publicReview }) => sameScope(publicReview.scope, normalizedScope))
      .map(({ publicReview }) => cloneReview(publicReview));
  }

  setRowResolution(
    reviewId: string,
    rowId: string,
    resolution: { candidateId?: string; omit?: boolean },
  ): void {
    const pending = this.requireReview(reviewId);
    if (pending.publicReview.state !== "pending") {
      throw new Error("This library import review was already resolved or is being applied");
    }
    const parsed = parseRowResolution(resolution);
    const row = pending.publicReview.rows.find((entry) => entry.id === rowId);
    if (!row) throw new Error("Unknown library import review row");
    if (row.disposition === "create" || row.disposition === "reuse") {
      throw new Error("A ready create or reuse row cannot be replaced or omitted");
    }
    if (parsed.candidateId !== null && !row.candidates.some((entry) => entry.candidateId === parsed.candidateId)) {
      throw new Error("The selected candidate is not bound to this review row");
    }

    const rows = pending.publicReview.rows.map((entry) => entry.id === rowId
      ? {
          ...entry,
          selectedCandidateId: parsed.candidateId,
          omissionAcknowledged: parsed.omit,
        }
      : cloneReviewRow(entry));
    const boundRows = pending.boundPlan.rows.map((entry) => entry.rowId === rowId
      ? { ...entry, choiceId: parsed.candidateId, omit: parsed.omit }
      : { ...entry });
    const revision = pending.revision + 1;
    pending.revision = revision;
    pending.boundPlan = { ...clonePlan(pending.boundPlan), rows: boundRows };
    pending.publicReview = {
      ...cloneReview(pending.publicReview),
      rows: rows.map((entry) => ({
        ...cloneReviewRow(entry),
        effectLabel: "Checking the latest Zotero effect…",
      })),
      effectCount: 0,
      canApply: false,
      statusMessage: "Refreshing Zotero preflight for the latest row choices…",
    };
    this.safeNotify(pending.publicReview.scope);
    const plan = clonePlan(pending.boundPlan);
    void this.refreshPreflight(pending, revision, plan).catch(() => {
      // Detached refreshes are a read-only UI enhancement. Their own handler
      // should be total, but this final boundary prevents any future defect
      // from surfacing as an unhandled promise rejection.
    });
  }

  async resolveReview(
    reviewId: string,
    decision: "accept" | "reject",
  ): Promise<LibraryImportResolution> {
    const pending = this.requireReview(reviewId);
    if (pending.publicReview.state !== "pending") {
      throw new Error("This library import review was already resolved or is being applied");
    }
    if (decision !== "accept" && decision !== "reject") {
      throw new Error("Unknown library import review decision");
    }

    if (decision === "reject") {
      pending.publicReview = {
        ...cloneReview(pending.publicReview),
        canApply: false,
        state: "rejected",
        statusMessage: "The library import was rejected. Zotero was not changed.",
      };
      this.safeNotify(pending.publicReview.scope);
      return { decision: "rejected", reviewId, receipt: null };
    }

    if (!pending.publicReview.canApply) {
      throw new Error("Every ambiguous or unresolved citation needs a bound candidate or an explicit omission before Apply");
    }
    // Claim synchronously before returning the rejected promise. Task 5 owns
    // re-preflight, apply, compensation, and terminal acceptance semantics.
    pending.publicReview = {
      ...cloneReview(pending.publicReview),
      canApply: false,
      state: "resolving",
      statusMessage: "The library import is reserved for Apply.",
    };
    this.safeNotify(pending.publicReview.scope);
    throw new Error("Library import Apply is not available until Task 5; this read-only review performed no writes");
  }

  private async lookupCitations(
    rawArguments: Record<string, unknown>,
    scope: CitationCapabilityScope,
  ): Promise<Record<string, unknown>> {
    const requests = parseLookupArguments(rawArguments);
    const batch = await this.registry.lookup(scope, requests);
    return {
      batch_id: batch.batchId,
      expires_at_ms: batch.expiresAtMs,
      results: batch.results.map((entry) => ({
        client_ref: entry.clientRef,
        capability_id: entry.capabilityId,
        status: entry.resolution.status,
        reason: entry.resolution.reason,
        candidates: entry.resolution.candidates.map((candidate, index) => ({
          candidate_id: candidate.choiceId,
          label: candidateLabel(candidate, index),
          provenance: candidate.provenance,
        })),
      })),
    };
  }

  private async proposeLibraryImport(
    rawArguments: Record<string, unknown>,
    scope: CitationCapabilityScope,
  ): Promise<Record<string, unknown>> {
    const target = parseProposalArguments(rawArguments);
    const capabilities = this.registry.resolveCompleteBatch(scope, target.capabilityIds);
    const rows = bindCapabilityRows(capabilities);
    const candidateBindings = buildCandidateBindings(capabilities);
    const boundPlan: BoundLibraryImportPlan = {
      scope: normalizeScope(scope),
      target: {
        parentCollectionKey: target.parentCollectionKey,
        collectionName: target.collectionName,
      },
      rows,
    };
    const proposalPreflight = normalizePreflight(
      await this.host.preflight(clonePlan(boundPlan)),
      boundPlan,
      candidateBindings,
    );
    const reviewId = this.nextReviewId();
    const publicRows = capabilities.map((capability) => buildReviewRow(
      capability,
      proposalPreflight.dispositions.find((entry) => entry.rowId === capability.resolution.clientRef)!,
    ));
    const publicReview: LibraryImportReview = {
      id: reviewId,
      scope: cloneScope(boundPlan.scope),
      target: {
        parentCollectionKey: target.parentCollectionKey,
        collectionName: target.collectionName,
        collectionPath: target.parentCollectionKey
          ? `${target.parentCollectionKey} › ${target.collectionName}`
          : target.collectionName,
      },
      rows: publicRows,
      effectCount: countEffects(proposalPreflight),
      canApply: canApplyRows(publicRows, proposalPreflight),
      state: "pending",
      statusMessage: statusMessage(publicRows, proposalPreflight),
    };
    this.pending.set(reviewId, {
      publicReview: cloneReview(publicReview),
      boundPlan: clonePlan(boundPlan),
      proposalPreflight: clonePreflight(proposalPreflight),
      candidateBindings,
      revision: 0,
    });
    this.safeNotify(publicReview.scope);
    return {
      status: "awaiting_user_review",
      review_id: reviewId,
      effect_count: publicReview.effectCount,
      can_apply: publicReview.canApply,
      message: "The import is visible for structured review. Nothing has been written to Zotero.",
    };
  }

  private requireReview(reviewId: string): PendingLibraryImportReview {
    const normalized = normalizeOpaqueText(reviewId, "review ID");
    const pending = this.pending.get(normalized);
    if (!pending) throw new Error("This library import review has expired or is unknown");
    return pending;
  }

  private nextReviewId(): string {
    for (let attempts = 0; attempts < 100; attempts += 1) {
      const id = normalizeOpaqueText(this.createId(), "library import review ID");
      if (!this.pending.has(id)) return id;
    }
    throw new Error("Library import review ID factory produced duplicate IDs");
  }

  private safeNotify(scope: CitationCapabilityScope): void {
    try {
      this.callbacks.onState(cloneScope(scope));
    }
    catch {
      // State is authoritative. A UI notification failure must not affect it.
    }
  }

  private async refreshPreflight(
    pending: PendingLibraryImportReview,
    revision: number,
    plan: BoundLibraryImportPlan,
  ): Promise<void> {
    try {
      const refreshed = normalizePreflight(
        await this.host.preflight(clonePlan(plan)),
        plan,
        pending.candidateBindings,
      );
      if (!this.isCurrentRefresh(pending, revision)) return;
      const rows = pending.publicReview.rows.map((row) => ({
        ...cloneReviewRow(row),
        effectLabel: effectLabel(refreshed.dispositions.find((entry) => entry.rowId === row.id)!),
      }));
      pending.proposalPreflight = clonePreflight(refreshed);
      pending.publicReview = {
        ...cloneReview(pending.publicReview),
        rows,
        effectCount: countEffects(refreshed),
        canApply: canApplyRows(rows, refreshed),
        statusMessage: statusMessage(rows, refreshed),
      };
      this.safeNotify(pending.publicReview.scope);
    }
    catch (error) {
      if (!this.isCurrentRefresh(pending, revision)) return;
      pending.publicReview = {
        ...cloneReview(pending.publicReview),
        rows: pending.publicReview.rows.map((row) => ({
          ...cloneReviewRow(row),
          effectLabel: "Zotero preflight refresh failed",
        })),
        effectCount: 0,
        canApply: false,
        statusMessage: `Zotero preflight refresh failed: ${boundedErrorMessage(error)}`,
      };
      this.safeNotify(pending.publicReview.scope);
    }
  }

  private isCurrentRefresh(pending: PendingLibraryImportReview, revision: number): boolean {
    return pending.publicReview.state === "pending"
      && pending.revision === revision
      && this.pending.get(pending.publicReview.id) === pending;
  }
}

function parseLookupArguments(raw: unknown): CitationQuery[] {
  if (!isPlainRecord(raw)) throw new TypeError("Citation lookup arguments must be an object");
  requireExactKeys(raw, ["requests"], "Citation lookup arguments");
  requireRequiredKeys(raw, ["requests"], "Citation lookup arguments");
  if (!Array.isArray(raw.requests)) throw new TypeError("Citation lookup requests must be an array");
  return raw.requests.map((value, index) => {
    if (!isPlainRecord(value)) throw new TypeError(`Citation lookup request ${index} must be an object`);
    requireExactKeys(
      value,
      ["client_ref", "citation", "doi", "arxiv", "title", "year", "creators"],
      `Citation lookup request ${index}`,
    );
    requireRequiredKeys(value, ["client_ref"], `Citation lookup request ${index}`);
    return {
      clientRef: value.client_ref as string,
      ...(value.citation === undefined ? {} : { citation: value.citation as string }),
      ...(value.doi === undefined ? {} : { doi: value.doi as string }),
      ...(value.arxiv === undefined ? {} : { arxiv: value.arxiv as string }),
      ...(value.title === undefined ? {} : { title: value.title as string }),
      ...(value.year === undefined ? {} : { year: value.year as number }),
      ...(value.creators === undefined ? {} : { creators: value.creators as string[] }),
    };
  });
}

function parseProposalArguments(raw: unknown): {
  collectionName: string;
  parentCollectionKey: string | null;
  capabilityIds: string[];
} {
  if (!isPlainRecord(raw)) throw new TypeError("Library import proposal arguments must be an object");
  requireExactKeys(
    raw,
    ["collection_name", "parent_collection_key", "capability_ids"],
    "Library import proposal arguments",
  );
  requireRequiredKeys(raw, ["collection_name", "capability_ids"], "Library import proposal arguments");
  const collectionName = normalizeCollectionName(raw.collection_name);
  const parentCollectionKey = raw.parent_collection_key === undefined
    ? null
    : normalizeOpaqueText(raw.parent_collection_key, "parent collection key");
  if (!Array.isArray(raw.capability_ids)) throw new TypeError("capability_ids must be an array");
  if (raw.capability_ids.length === 0 || raw.capability_ids.length > MAX_CAPABILITIES) {
    throw new RangeError(`capability_ids must contain 1 to ${MAX_CAPABILITIES} IDs`);
  }
  // Capability IDs are pure authority. Validate their envelope, but never
  // trim or normalize the registry-issued bytes before exact batch lookup.
  const capabilityIds = raw.capability_ids.map((value) => readExactOpaqueText(value, "citation capability ID"));
  if (new Set(capabilityIds).size !== capabilityIds.length) {
    throw new Error("citation capability IDs must be unique; duplicate IDs are not allowed");
  }
  return { collectionName, parentCollectionKey, capabilityIds };
}

function bindCapabilityRows(capabilities: readonly BoundCitationCapability[]): BoundLibraryImportPlan["rows"] {
  const rowIds = capabilities.map((capability) => capability.resolution.clientRef);
  if (new Set(rowIds).size !== rowIds.length) {
    throw new Error("Citation client_ref values must be unique within an import review");
  }
  return capabilities.map((capability) => {
    const { resolution } = capability;
    const candidateIds = resolution.candidates.map((candidate) => candidate.choiceId);
    if (new Set(candidateIds).size !== candidateIds.length) {
      throw new Error(`Citation row ${resolution.clientRef} has duplicate bound candidate IDs`);
    }
    const ready = resolution.status === "create" || resolution.status === "reuse";
    if (ready && resolution.candidates.length !== 1) {
      throw new Error(`Ready citation row ${resolution.clientRef} must have exactly one bound candidate`);
    }
    if (resolution.status === "create" && resolution.candidates[0]?.metadata === null) {
      throw new Error(`Create citation row ${resolution.clientRef} has no bound bibliographic metadata`);
    }
    if (resolution.status === "reuse" && resolution.candidates[0]?.localItemKey === null) {
      throw new Error(`Reuse citation row ${resolution.clientRef} has no bound local item`);
    }
    return {
      rowId: resolution.clientRef,
      choiceId: ready ? resolution.candidates[0]!.choiceId : null,
      omit: false,
      resolverDigest: capability.resolverDigest,
    };
  });
}

function buildCandidateBindings(capabilities: readonly BoundCitationCapability[]): BoundCandidateIndex {
  return new Map(capabilities.map((capability) => [
    capability.resolution.clientRef,
    new Map<string, BoundCandidateEffect>(capability.resolution.candidates.map((candidate) => {
      if (candidate.localItemKey !== null) {
        return [candidate.choiceId, {
          effect: "reuse" as const,
          itemKey: candidate.localItemKey,
          itemVersion: candidate.localItemVersion,
        }];
      }
      if (candidate.metadata !== null) {
        return [candidate.choiceId, {
          effect: "create" as const,
          itemKey: null,
          itemVersion: null,
        }];
      }
      throw new Error(`Citation row ${capability.resolution.clientRef} has an unusable bound candidate`);
    })),
  ]));
}

function buildReviewRow(
  capability: BoundCitationCapability,
  disposition: LibraryImportPreflight["dispositions"][number],
): LibraryImportReviewRow {
  const resolution = capability.resolution;
  const ready = resolution.status === "create" || resolution.status === "reuse";
  return {
    id: resolution.clientRef,
    clientRef: resolution.clientRef,
    citationLabel: citationLabel(resolution),
    disposition: resolution.status,
    effectLabel: effectLabel(disposition),
    candidates: resolution.candidates.map((entry, index) => ({
      candidateId: entry.choiceId,
      label: candidateLabel(entry, index),
      provenance: entry.provenance,
    })),
    selectedCandidateId: ready ? resolution.candidates[0]!.choiceId : null,
    omissionAcknowledged: false,
  };
}

function normalizePreflight(
  raw: unknown,
  plan: BoundLibraryImportPlan,
  candidateBindings: BoundCandidateIndex,
): LibraryImportPreflight {
  if (!isPlainRecord(raw)) throw new TypeError("Library import preflight must be an object");
  requireExactKeys(
    raw,
    ["digest", "editable", "parentVersion", "siblingCollectionKey", "dispositions"],
    "Library import preflight",
  );
  requireRequiredKeys(
    raw,
    ["digest", "editable", "parentVersion", "siblingCollectionKey", "dispositions"],
    "Library import preflight",
  );
  const digest = readExactOpaqueText(raw.digest, "library import preflight digest");
  if (typeof raw.editable !== "boolean") throw new TypeError("Library import preflight editable must be boolean");
  const parentVersion = normalizeVersion(raw.parentVersion, "library import parent version");
  const siblingCollectionKey = raw.siblingCollectionKey === null
    ? null
    : readExactOpaqueText(raw.siblingCollectionKey, "sibling collection key");
  if (!Array.isArray(raw.dispositions)) throw new TypeError("Library import preflight dispositions must be an array");
  const dispositions = raw.dispositions.map((value, index) => normalizePreflightDisposition(value, index));
  const actualRowIds = dispositions.map((entry) => entry.rowId);
  const expectedRowIds = plan.rows.map((row) => row.rowId);
  if (new Set(actualRowIds).size !== actualRowIds.length
    || actualRowIds.length !== expectedRowIds.length
    || expectedRowIds.some((rowId) => !actualRowIds.includes(rowId))) {
    throw new Error("Library import preflight must cover the exact complete set of review rows");
  }
  if (siblingCollectionKey === null && dispositions.some((entry) => entry.membershipExists)) {
    throw new Error("Library import preflight cannot claim target membership when the collection does not exist");
  }
  for (const row of plan.rows) {
    validatePreflightCoherence(
      row,
      dispositions.find((entry) => entry.rowId === row.rowId)!,
      candidateBindings.get(row.rowId),
    );
  }
  return { digest, editable: raw.editable, parentVersion, siblingCollectionKey, dispositions };
}

function normalizePreflightDisposition(
  raw: unknown,
  index: number,
): LibraryImportPreflight["dispositions"][number] {
  const label = `Library import preflight disposition ${index}`;
  if (!isPlainRecord(raw)) throw new TypeError(`${label} must be an object`);
  requireExactKeys(raw, ["rowId", "effect", "itemKey", "itemVersion", "membershipExists"], label);
  requireRequiredKeys(raw, ["rowId", "effect", "itemKey", "itemVersion", "membershipExists"], label);
  if (raw.effect !== "create" && raw.effect !== "reuse" && raw.effect !== "omit" && raw.effect !== "conflict") {
    throw new TypeError(`${label} has an unsupported effect`);
  }
  const itemKey = raw.itemKey === null ? null : readExactOpaqueText(raw.itemKey, `${label} item key`);
  const itemVersion = normalizeVersion(raw.itemVersion, `${label} item version`);
  if (typeof raw.membershipExists !== "boolean") throw new TypeError(`${label} membershipExists must be boolean`);
  return {
    rowId: readExactOpaqueText(raw.rowId, `${label} row ID`),
    effect: raw.effect,
    itemKey,
    itemVersion,
    membershipExists: raw.membershipExists,
  };
}

function validatePreflightCoherence(
  row: BoundLibraryImportPlan["rows"][number],
  disposition: LibraryImportPreflight["dispositions"][number],
  candidates: ReadonlyMap<string, BoundCandidateEffect> | undefined,
): void {
  if (disposition.effect === "conflict") {
    requireNoHostItemEffect(disposition, "conflict");
    return;
  }
  if (row.omit) {
    if (disposition.effect !== "omit") {
      throw new Error(`Preflight row ${row.rowId} must have an omit effect for the final bound plan`);
    }
    requireNoHostItemEffect(disposition, "omit");
    return;
  }
  if (row.choiceId === null) {
    throw new Error(`Preflight row ${row.rowId} must have a conflict effect until a candidate or omission is bound`);
  }
  const candidate = candidates?.get(row.choiceId);
  if (!candidate) throw new Error(`Preflight row ${row.rowId} references an unbound candidate`);
  if (disposition.effect !== candidate.effect) {
    throw new Error(`Preflight row ${row.rowId} must have a ${candidate.effect} effect for the final bound plan`);
  }
  if (candidate.effect === "create") {
    requireNoHostItemEffect(disposition, "create");
    return;
  }
  if (candidate.itemKey === null || candidate.itemVersion === null) {
    throw new Error(`Preflight reuse row ${row.rowId} lacks a valid bound item identity and version`);
  }
  if (disposition.itemKey !== candidate.itemKey || disposition.itemVersion !== candidate.itemVersion) {
    throw new Error(`Preflight reuse row ${row.rowId} does not match the bound item identity and version`);
  }
}

function requireNoHostItemEffect(
  disposition: LibraryImportPreflight["dispositions"][number],
  effect: "create" | "omit" | "conflict",
): void {
  if (disposition.itemKey !== null || disposition.itemVersion !== null || disposition.membershipExists) {
    throw new Error(`Preflight ${effect} effect must not contain item identity, version, or membership data`);
  }
}

function parseRowResolution(raw: unknown): { candidateId: string | null; omit: boolean } {
  if (!isPlainRecord(raw)) throw new TypeError("Library import row resolution must be an object");
  requireExactKeys(raw, ["candidateId", "omit"], "Library import row resolution");
  const hasCandidate = raw.candidateId !== undefined;
  const hasOmission = raw.omit !== undefined;
  if (hasCandidate === hasOmission) {
    throw new Error("Provide exactly one bound candidate ID or an explicit omission");
  }
  if (hasCandidate) {
    return { candidateId: normalizeOpaqueText(raw.candidateId, "candidate ID"), omit: false };
  }
  if (raw.omit !== true) throw new Error("An omission acknowledgment must set omit to true");
  return { candidateId: null, omit: true };
}

function normalizeCollectionName(raw: unknown): string {
  if (typeof raw !== "string") throw new TypeError("collection_name must be a string");
  if (UNSAFE_TEXT.test(raw)) {
    throw new TypeError("collection_name contains unsafe control, directional, zero-width, or newline text");
  }
  if ([...raw].length > MAX_RAW_COLLECTION_NAME_CODE_POINTS) {
    throw new RangeError("collection_name exceeds the defensive raw input limit");
  }
  const normalized = raw.normalize("NFC").trim();
  const length = [...normalized].length;
  if (length === 0) throw new TypeError("collection_name must not be blank");
  if (length > MAX_COLLECTION_NAME_CODE_POINTS) {
    throw new RangeError(`collection_name must be at most ${MAX_COLLECTION_NAME_CODE_POINTS} Unicode code points`);
  }
  if (normalized === "." || normalized === ".." || /[\\/]/u.test(normalized)) {
    throw new TypeError("collection_name must not contain path-like dot values or path separators");
  }
  return normalized;
}

function normalizeOpaqueText(raw: unknown, label: string): string {
  if (typeof raw !== "string") throw new TypeError(`${label} must be a string`);
  if (UNSAFE_TEXT.test(raw)) throw new TypeError(`${label} contains unsafe text`);
  const normalized = raw.normalize("NFC").trim();
  if (!normalized) throw new TypeError(`${label} must not be blank`);
  if ([...normalized].length > MAX_OPAQUE_ID_CODE_POINTS) throw new RangeError(`${label} is too long`);
  return normalized;
}

function readExactOpaqueText(raw: unknown, label: string): string {
  if (typeof raw !== "string") throw new TypeError(`${label} must be a string`);
  if (UNSAFE_TEXT.test(raw)) throw new TypeError(`${label} contains unsafe text`);
  if (!raw.trim()) throw new TypeError(`${label} must not be blank`);
  if ([...raw].length > MAX_OPAQUE_ID_CODE_POINTS) throw new RangeError(`${label} is too long`);
  return raw;
}

function normalizeVersion(raw: unknown, label: string): number | null {
  if (raw === null) return null;
  if (typeof raw !== "number" || !Number.isSafeInteger(raw) || raw < 0) {
    throw new TypeError(`${label} must be a non-negative safe integer or null`);
  }
  return raw;
}

function normalizeScope(raw: unknown): CitationCapabilityScope {
  if (!isPlainRecord(raw)) throw new TypeError("Citation capability scope must be an object");
  requireExactKeys(raw, ["threadId", "libraryID"], "Citation capability scope");
  requireRequiredKeys(raw, ["threadId", "libraryID"], "Citation capability scope");
  const threadId = normalizeOpaqueText(raw.threadId, "scope.threadId");
  const libraryID = raw.libraryID;
  if (typeof libraryID === "string") {
    return { threadId, libraryID: normalizeOpaqueText(libraryID, "scope.libraryID") };
  }
  if (typeof libraryID !== "number" || !Number.isSafeInteger(libraryID)) {
    throw new TypeError("scope.libraryID must be a string or safe integer");
  }
  return { threadId, libraryID };
}

function canApplyRows(
  rows: readonly LibraryImportReviewRow[],
  preflight: LibraryImportPreflight,
): boolean {
  if (!preflight.editable) return false;
  if (preflight.dispositions.some((entry) => entry.effect === "conflict")) return false;
  return rows.every((row) => {
    if (row.disposition === "create" || row.disposition === "reuse") {
      const hostDisposition = preflight.dispositions.find((entry) => entry.rowId === row.id);
      return row.selectedCandidateId !== null && hostDisposition?.effect !== "conflict";
    }
    return row.selectedCandidateId !== null || row.omissionAcknowledged;
  });
}

function statusMessage(
  rows: readonly LibraryImportReviewRow[],
  preflight: LibraryImportPreflight,
): string {
  if (!preflight.editable) return "The target Zotero library or collection is not editable.";
  if (preflight.dispositions.some((entry) => entry.effect === "conflict")
    && rows.every((row) => row.disposition === "create" || row.disposition === "reuse"
      || row.selectedCandidateId !== null || row.omissionAcknowledged)) {
    return "Zotero preflight reported a conflict. Apply remains disabled.";
  }
  if (canApplyRows(rows, preflight)) return "All citation rows are resolved and ready for user approval.";
  return "Choose a bound candidate or explicitly omit every ambiguous or unresolved citation.";
}

function boundedErrorMessage(error: unknown): string {
  const fallback = "The host did not provide a readable error message";
  let raw = "";
  if ((typeof error === "object" && error !== null) || typeof error === "function") {
    try {
      const message = (error as { message?: unknown }).message;
      if (message !== undefined) raw = safelyCoerceErrorText(message);
    }
    catch {
      // A host object may expose a throwing message getter.
    }
  }
  if (!raw) raw = safelyCoerceErrorText(error);
  if (!raw) return fallback;
  try {
    const safe = raw.replace(UNSAFE_TEXT_GLOBAL, "�").normalize("NFC").trim();
    const bounded = [...safe].slice(0, 240).join("");
    return bounded || fallback;
  }
  catch {
    return fallback;
  }
}

function safelyCoerceErrorText(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return String(value);
  }
  catch {
    return "";
  }
}

function countEffects(preflight: LibraryImportPreflight): number {
  const collectionCreation = preflight.siblingCollectionKey === null ? 1 : 0;
  const rowEffects = preflight.dispositions.filter((entry) => (
    entry.effect === "create" || (entry.effect === "reuse" && !entry.membershipExists)
  )).length;
  return collectionCreation + rowEffects;
}

function citationLabel(resolution: ResolvedCitation): string {
  return resolution.candidates.find((candidate) => candidate.metadata?.title)?.metadata?.title
    ?? resolution.clientRef;
}

function candidateLabel(candidate: ResolvedCitation["candidates"][number], index: number): string {
  return candidate.metadata?.title
    ?? (candidate.localItemKey ? `Existing Zotero item ${candidate.localItemKey}` : `Candidate ${index + 1}`);
}

function effectLabel(disposition: LibraryImportPreflight["dispositions"][number]): string {
  if (disposition.effect === "create") return "Create a new Zotero item";
  if (disposition.effect === "reuse") {
    return disposition.membershipExists
      ? "Reuse an item already in the target collection"
      : "Reuse an existing item and add it to the target collection";
  }
  if (disposition.effect === "omit") return "Omit this citation";
  return "Choose a candidate or acknowledge omission";
}

function cloneScope(scope: CitationCapabilityScope): CitationCapabilityScope {
  return { threadId: scope.threadId, libraryID: scope.libraryID };
}

function clonePlan(plan: BoundLibraryImportPlan): BoundLibraryImportPlan {
  return {
    scope: cloneScope(plan.scope),
    target: { ...plan.target },
    rows: plan.rows.map((row) => ({ ...row })),
  };
}

function clonePreflight(preflight: LibraryImportPreflight): LibraryImportPreflight {
  return {
    ...preflight,
    dispositions: preflight.dispositions.map((entry) => ({ ...entry })),
  };
}

function cloneReviewRow(row: LibraryImportReviewRow): LibraryImportReviewRow {
  return {
    ...row,
    candidates: row.candidates.map((candidate) => ({ ...candidate })),
  };
}

function cloneReview(review: LibraryImportReview): LibraryImportReview {
  return {
    ...review,
    scope: { ...review.scope },
    target: { ...review.target },
    rows: review.rows.map(cloneReviewRow),
  };
}

function sameScope(left: CitationCapabilityScope, right: CitationCapabilityScope): boolean {
  return left.threadId === right.threadId && left.libraryID === right.libraryID;
}

function requireExactKeys(raw: UnknownRecord, allowed: readonly string[], label: string): void {
  for (const key of Object.keys(raw)) {
    if (!allowed.includes(key)) throw new TypeError(`${label} contains unknown field ${key}`);
  }
}

function requireRequiredKeys(raw: UnknownRecord, required: readonly string[], label: string): void {
  for (const key of required) {
    if (!(key in raw)) throw new TypeError(`${label} is missing required field ${key}`);
  }
}

function isPlainRecord(raw: unknown): raw is UnknownRecord {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return false;
  const prototype = Object.getPrototypeOf(raw);
  return prototype === Object.prototype || prototype === null;
}

function defaultOpaqueId(): string {
  const cryptoValue = globalThis.crypto;
  if (!cryptoValue || typeof cryptoValue.getRandomValues !== "function") {
    throw new Error("Secure random generation is unavailable for a library import review ID");
  }
  const bytes = new Uint8Array(18);
  cryptoValue.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}
