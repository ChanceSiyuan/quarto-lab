# Zotero Library Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent, Apple-like Floating Palette to Zotero's ordinary library view, backed by one isolated conversation per library and a review-gated citation-import workflow.

**Architecture:** Keep `CodexService` as the single app-server and `ThreadStore` owner, but add subject-indexed library threads that never mutate the active paper thread. A dedicated DOM palette and controller consume immutable library state. Citation lookup and Zotero writes live behind `CitationCandidateRegistry`, `ReviewedLibraryImportService`, and a native adapter; only an explicit Apply callback can write.

**Tech Stack:** TypeScript 7, Zotero 9 privileged APIs, Codex app-server RPC, Happy DOM, Vitest 4, esbuild, CSS/XUL-compatible DOM.

## Global Constraints

- Work only on `fix/zotero-fix-pack-b`; never commit this feature to `main`.
- Develop and run deterministic tests on Linux; native Zotero/macOS visual and translator verification remains explicitly deferred.
- Mount only in a normal Zotero main window while `Zotero_Tabs.selectedID === "zotero-pane"`; never mount in Reader, Workbench-only, or standalone windows.
- Workbench remains PDF/Draft chat and loses the misleading `Library Chat` scope switch.
- Use one durable subject key `library:<libraryID>` and at most one running turn for that subject, even when two windows show the same library.
- Library turns use `profilePath()` as `cwd`, no runtime workspace roots, a read-only sandbox, and `networkAccess: false`.
- Capture at most 50 selected items and 50 citation requests; report the omitted count.
- Candidate capabilities expire after 30 minutes and are bound to lookup batch, library, thread, and metadata digest.
- Collection names allow at most 200 Unicode code points and reject empty, path-like, or control-character content.
- V1 writes only one child collection, new top-level bibliographic items from bound metadata, and reviewed collection memberships for exact existing items.
- Never delete, merge, or edit existing item metadata; never create tags, Notes, annotations, attachments, or download PDFs.
- Never write Research Loop `knowledge/`, `drafts/`, `literature/`, or `public/knowledge/`.
- Use the real `chrome://zotkit/content/icons/icon.svg`, the existing system-font stack and color tokens, and no external fonts or decorative gradients.
- Every source change begins with a failing test and ends with a focused commit.

---

## File structure

### New focused modules

- `integrations/zotero/src/library-conversation.ts` — library subject identity, immutable message context, and synthetic no-PDF context.
- `integrations/zotero/src/library-citations.ts` — citation query normalization, metadata allowlist, opaque candidate binding, expiry, and digesting.
- `integrations/zotero/src/reviewed-library-import.ts` — model tools, structured review state, row resolution, Apply serialization, stale checks, and compensation coordination.
- `integrations/zotero/src/zotero-library-import.ts` — Zotero identifier resolver and native collection/item/membership adapter.
- `integrations/zotero/src/library-agent-context.ts` — pure conversion from Zotero selection snapshots into bounded Library Agent context.
- `integrations/zotero/src/library-agent-palette.ts` — DOM-only Floating Palette view.
- `integrations/zotero/src/library-agent-controller.ts` — per-window lifecycle, visibility, state composition, and semantic callbacks.

### Existing integration seams

- `integrations/zotero/src/codex-service.ts` — persistent library sessions, per-subject sends/stops/state, read-only settings, and tool routing.
- `integrations/zotero/src/reader-context.ts` — explicit invalidation of one library snapshot after a native mutation.
- `integrations/zotero/src/plugin.ts` — construct shared services; mount/unmount controllers; route notifications; no business logic in the palette.
- `integrations/zotero/src/sidebar.ts` — remove the Workbench scope switch and `ResearchScope` callback/state.
- `integrations/zotero/src/styles.css` — `zc-library-agent-*` geometry, material, responsive, accessibility, and reduced-effect rules.
- `integrations/zotero/README.md`, `CHANGELOG.md`, `manifest.json`, `package.json`, `package-lock.json` — document and version the feature as `0.11.0`.

---

### Task 1: Persistent library conversation identity and resume

**Files:**
- Create: `integrations/zotero/src/library-conversation.ts`
- Modify: `integrations/zotero/src/codex-service.ts`
- Test: `integrations/zotero/test/library-conversation.test.ts`

**Interfaces:**
- Produces: `LibraryConversationSubject`, `LibraryMessageContext`, `LibraryConversationState`, `librarySubjectKey()`, `libraryReaderContext()`.
- Produces on `CodexService`: `openLibraryConversation()` and `getLibraryConversationState()`.
- Preserves: existing `SessionFile.version === 1` and every `papers`, `history`, and `openThreads` record.

- [ ] **Step 1: Write failing identity and persistence tests**

```ts
it("uses one stable subject per library without selecting it in Workbench", async () => {
  const { service, client, saved } = libraryServiceHarness({ activePaperThread: "paper-thread" });
  const subject = { libraryID: 1, libraryName: "My Library" };

  const state = await service.openLibraryConversation(subject);

  expect(state.subject.key).toBe("library:1");
  expect(state.threadId).toBe("library-thread");
  expect(service.state.activeThreadId).toBe("paper-thread");
  expect(client.threadStart).toHaveBeenCalledOnce();
  expect(saved.at(-1)?.libraries?.["library:1"]?.threadId).toBe("library-thread");
  expect(saved.at(-1)?.papers?.["1-ATTACH"]?.threadId).toBe("paper-thread");
});

it("resumes the stored library thread and preserves operational failures", async () => {
  const { service, client } = libraryServiceHarness({ storedLibraryThread: "stored-library" });
  client.threadResume.mockRejectedValueOnce(new CodexDisconnectedError("offline"));

  await expect(service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" }))
    .rejects.toThrow("offline");
  expect(client.threadStart).not.toHaveBeenCalled();
  expect(service.getLibraryConversationState({ libraryID: 1, libraryName: "My Library" }).error)
    .toContain("offline");
});
```

- [ ] **Step 2: Run the focused test and verify the missing API failure**

Run: `cd integrations/zotero && npx vitest run test/library-conversation.test.ts`

Expected: FAIL because `library-conversation.ts` and `openLibraryConversation()` do not exist.

- [ ] **Step 3: Add the subject contracts and backward-compatible session map**

```ts
export type LibrarySubjectKey = `library:${string}`;

export interface LibraryConversationSubjectInput {
  libraryID: number | string;
  libraryName: string;
}

export interface LibraryConversationSubject extends LibraryConversationSubjectInput {
  key: LibrarySubjectKey;
}

export interface LibraryContextItem {
  key: string;
  itemType: string;
  title: string;
  creators: string;
  year: string;
  doi: string;
}

export interface LibraryMessageContext {
  libraryID: number | string;
  libraryName: string;
  collection: { key: string; path: string } | null;
  selectedItems: readonly LibraryContextItem[];
  omittedItemCount: number;
}

export interface LibraryConversationState {
  subject: LibraryConversationSubject;
  threadId: string | null;
  entries: readonly ChatEntry[];
  opening: boolean;
  running: boolean;
  activeTurnId: string | null;
  error: string | null;
}
```

Add `libraries?: Record<LibrarySubjectKey, LibrarySessionRecord>` to `SessionFile`, deep-copy it in `cloneConversationSessions()`, and keep `version: 1`. Add `libraryRuntimes` and `threadLibrarySubjects` maps. `openLibraryConversation()` must serialize through the renamed `enqueueConversationTransition()`, reuse `resumeStoredThread()`, create a replacement only for its explicit `missing` result, save the canonical resumed ID transactionally, and never assign any paper-active field.

Filter every library thread ID out of `refreshGlobalHistory()` and reject it in `openGlobalThreadInternal()` so Workbench cannot select a library transcript.

- [ ] **Step 4: Run identity, resume, and existing conversation tests**

Run: `cd integrations/zotero && npx vitest run test/library-conversation.test.ts test/stored-conversation-resume.test.ts test/codex-service.test.ts`

Expected: PASS, including missing-thread replacement and timeout/disconnect preservation.

- [ ] **Step 5: Commit the conversation identity slice**

```bash
git add integrations/zotero/src/library-conversation.ts integrations/zotero/src/codex-service.ts integrations/zotero/test/library-conversation.test.ts
git commit -m "feat(zotero): persist isolated library conversations"
```

### Task 2: Per-library send, stop, events, and tool isolation

**Files:**
- Modify: `integrations/zotero/src/library-conversation.ts`
- Modify: `integrations/zotero/src/codex-service.ts`
- Modify: `integrations/zotero/test/library-conversation.test.ts`
- Test: `integrations/zotero/test/codex-service.test.ts`

**Interfaces:**
- Consumes: `LibraryConversationSubject`, `LibraryMessageContext`, and the persisted runtime from Task 1.
- Produces on `CodexService`: `sendLibraryMessage()`, `stopLibraryTurn()`, `setLibraryToolProvider()`.
- Produces: `CodexLibraryToolProvider`, whose tools are never exposed to paper or Draft threads.

- [ ] **Step 1: Write failing send and routing tests**

```ts
it("starts a read-only library turn without changing the running paper", async () => {
  const { service, client } = libraryServiceHarness({ activePaperThread: "paper-thread" });
  const context = libraryMessageContext({ selectedCount: 2 });

  await service.sendLibraryMessage(
    { libraryID: 1, libraryName: "My Library" },
    { text: "Find these citations", model: "gpt-5.6-codex", effort: "medium" },
    context,
  );

  expect(client.turnStart).toHaveBeenCalledWith(expect.objectContaining({
    threadId: "library-thread",
    cwd: expect.stringContaining("zotkit"),
    runtimeWorkspaceRoots: [],
    sandboxPolicy: { type: "readOnly", networkAccess: false },
  }));
  expect(service.state.activeThreadId).toBe("paper-thread");
  expect(service.state.running).toBe(false);
  expect(service.getLibraryConversationState({ libraryID: 1, libraryName: "My Library" }).running)
    .toBe(true);
});

it("routes a library dynamic tool only to the library provider", async () => {
  const { service, libraryTools, paperTools } = libraryServiceHarness();
  await service.openLibraryConversation({ libraryID: 1, libraryName: "My Library" });

  const result = await (service as any).handleDynamicTool({
    threadId: "library-thread",
    turnId: "library-turn",
    tool: "zotero_lookup_citations",
    arguments: { requests: [{ client_ref: "r1", doi: "10.1000/example" }] },
  });

  expect(result.success).toBe(true);
  expect(libraryTools.invokeTool).toHaveBeenCalledOnce();
  expect(paperTools.invokeTool).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run and verify the new methods and provider are absent**

Run: `cd integrations/zotero && npx vitest run test/library-conversation.test.ts test/codex-service.test.ts`

Expected: FAIL on missing `sendLibraryMessage`, `stopLibraryTurn`, and `setLibraryToolProvider`.

- [ ] **Step 3: Implement immutable message snapshots and subject-scoped state**

```ts
export interface CodexLibraryToolProvider {
  readonly tools: readonly CodexDynamicToolSpec[];
  invokeTool(
    name: string,
    argumentsValue: Record<string, unknown>,
    context: LibraryMessageContext,
    call: { threadId: string; turnId: string },
  ): Promise<unknown>;
}

sendLibraryMessage(
  subject: LibraryConversationSubjectInput,
  message: { text: string; model: string; effort: string },
  context: LibraryMessageContext,
): Promise<void>;

stopLibraryTurn(subject: LibraryConversationSubjectInput): Promise<void>;
```

Copy and freeze the bounded context at the public call boundary. Store it under the exact `(threadId, turnId)` before a dynamic call can arrive. Library thread-start settings use only the safe reader-tool subset plus `CodexLibraryToolProvider.tools`; library turn settings are read-only and never call `configuredQLabRoot()`, `contextRoots()`, or `qlabWritableRoots()`.

Route completion/failure notifications through `threadLibrarySubjects`, clear that subject's running state, and call `callbacks.onState({ kind: "library", key })`. A callback without a subject remains the existing account/connection/Workbench signal.

- [ ] **Step 4: Run focused and full Codex service tests**

Run: `cd integrations/zotero && npx vitest run test/library-conversation.test.ts test/codex-service.test.ts`

Expected: PASS for concurrent same-library open/send, immutable selection, stop, tool allowlist, event routing, and paper-state isolation.

- [ ] **Step 5: Commit the library turn slice**

```bash
git add integrations/zotero/src/library-conversation.ts integrations/zotero/src/codex-service.ts integrations/zotero/test/library-conversation.test.ts integrations/zotero/test/codex-service.test.ts
git commit -m "feat(zotero): route library turns independently"
```

### Task 3: Citation normalization and opaque candidate capabilities

**Files:**
- Create: `integrations/zotero/src/library-citations.ts`
- Test: `integrations/zotero/test/library-citations.test.ts`

**Interfaces:**
- Produces: `CitationQuery`, `BibliographicMetadata`, `CitationResolver`, `CitationCandidateRegistry`, `BoundCitationCapability`.
- Produces: `canonicalDOI()`, `canonicalArxivID()`, `bibliographicDigest()`.
- Enforces: maximum 50 requests, 30-minute expiry, strict metadata/item-type/creator fields, and subject-bound opaque IDs.

- [ ] **Step 1: Write failing normalization and capability tests**

```ts
it("normalizes identifiers without accepting DOI URLs as different papers", () => {
  expect(canonicalDOI("https://doi.org/10.1000/ABC.")).toBe("10.1000/abc");
  expect(canonicalArxivID("arXiv:2306.13123v2.pdf")).toBe("2306.13123");
});

it("binds candidates to one thread and expires them after 30 minutes", async () => {
  const registry = candidateRegistryHarness({ now: "2026-07-31T10:00:00Z" });
  const batch = await registry.lookup(scope("thread-a", 1), [{ clientRef: "r1", doi: "10.1000/abc" }]);
  const capabilityID = batch.results[0]!.capabilityId;

  expect(() => registry.resolveCapability(scope("thread-b", 1), capabilityID)).toThrow(/thread/);
  registry.setNow("2026-07-31T10:31:00Z");
  expect(() => registry.resolveCapability(scope("thread-a", 1), capabilityID)).toThrow(/expired/);
});
```

- [ ] **Step 2: Run and verify the new module is missing**

Run: `cd integrations/zotero && npx vitest run test/library-citations.test.ts`

Expected: FAIL because `library-citations.ts` is absent.

- [ ] **Step 3: Implement strict resolver contracts and the registry**

```ts
export type SupportedBibliographicItemType =
  | "journalArticle" | "conferencePaper" | "book" | "bookSection"
  | "report" | "thesis" | "preprint";

export interface CitationQuery {
  clientRef: string;
  citation?: string;
  doi?: string;
  arxiv?: string;
  title?: string;
  year?: number;
  creators?: readonly string[];
}

export interface BibliographicMetadata {
  itemType: SupportedBibliographicItemType;
  title: string;
  creators: readonly Readonly<{
    creatorType: "author";
    firstName?: string;
    lastName?: string;
    name?: string;
  }>[];
  date: string;
  DOI: string;
  url: string;
  publicationTitle: string;
  archive: string;
  archiveLocation: string;
}

export interface CitationResolver {
  resolve(
    scope: { libraryID: number | string },
    requests: readonly CitationQuery[],
  ): Promise<readonly ResolvedCitation[]>;
}

export interface ResolvedCitation {
  clientRef: string;
  status: "create" | "reuse" | "ambiguous" | "unresolved";
  candidates: readonly Readonly<{
    choiceId: string;
    metadata: BibliographicMetadata | null;
    localItemKey: string | null;
    localItemVersion: number | null;
    provenance: string;
  }>[];
  reason: string;
}

export interface BoundCitationCapability {
  capabilityId: string;
  batchId: string;
  requestIndex: number;
  libraryID: number | string;
  threadId: string;
  resolverDigest: string;
  expiresAtMs: number;
  resolution: ResolvedCitation;
}

export interface CitationCapabilityScope {
  threadId: string;
  libraryID: number | string;
}

export interface CitationLookupBatch {
  batchId: string;
  scope: CitationCapabilityScope;
  results: readonly Readonly<{
    clientRef: string;
    capabilityId: string;
    resolution: ResolvedCitation;
  }>[];
  expiresAtMs: number;
}

export interface CitationRegistryOptions {
  nowMs?: () => number;
  createId?: () => string;
  ttlMs?: number;
  maxRequests?: number;
}

export class CitationCandidateRegistry {
  constructor(resolver: CitationResolver, options?: CitationRegistryOptions);
  lookup(scope: CitationCapabilityScope, requests: readonly CitationQuery[]): Promise<CitationLookupBatch>;
  resolveCapability(scope: CitationCapabilityScope, capabilityId: string): BoundCitationCapability;
  resolveCompleteBatch(scope: CitationCapabilityScope, capabilityIds: readonly string[]): readonly BoundCitationCapability[];
}
```

Reject unknown keys, creators other than authors, unsupported item types, blank titles, control/bidi/zero-width text, and overlong values before digesting. Generate one opaque capability ID for every request, including ambiguous and unresolved requests; the capability contains its host-bound candidate choices. Never encode raw metadata into the ID. Keep registry batches in memory only, and require later proposal calls to present the complete capability set from exactly one batch.

- [ ] **Step 4: Run the citation contract tests**

Run: `cd integrations/zotero && npx vitest run test/library-citations.test.ts`

Expected: PASS for normalization, bounds, strict fields, digest stability, forged ID, cross-library/thread, and expiry cases.

- [ ] **Step 5: Commit the capability slice**

```bash
git add integrations/zotero/src/library-citations.ts integrations/zotero/test/library-citations.test.ts
git commit -m "feat(zotero): bind citation candidates safely"
```

### Task 4: Read-only lookup/proposal tools and structured review

**Files:**
- Create: `integrations/zotero/src/reviewed-library-import.ts`
- Test: `integrations/zotero/test/reviewed-library-import.test.ts`

**Interfaces:**
- Consumes: `CitationCandidateRegistry` from Task 3.
- Produces: `ReviewedLibraryImportService`, `LOOKUP_CITATIONS_TOOL`, `PROPOSE_LIBRARY_IMPORT_TOOL`.
- Produces: immutable `LibraryImportReview`, `LibraryImportReviewRow`, `LibraryMutationHost`, and `setRowResolution()` for ambiguous/unresolved choices.

- [ ] **Step 1: Write failing zero-write proposal tests**

```ts
it("looks up and proposes without writing Zotero", async () => {
  const { service, host } = importServiceHarness();
  const scope = { threadId: "library-thread", libraryID: 1 };
  const lookup = await service.invokeTool(LOOKUP_CITATIONS_TOOL, {
    requests: [{ client_ref: "shor", doi: "10.1103/physreva.52.r2493" }],
  }, scope);
  const capabilityID = lookup.results[0].capability_id;

  const proposed = await service.invokeTool(PROPOSE_LIBRARY_IMPORT_TOOL, {
    collection_name: "Cited in draft · Jul 31",
    parent_collection_key: "PARENT",
    capability_ids: [capabilityID],
  }, scope);

  expect(proposed.status).toBe("awaiting_user_review");
  expect(host.preflight).toHaveBeenCalledOnce();
  expect(host.apply).not.toHaveBeenCalled();
  expect(host.compensate).not.toHaveBeenCalled();
  expect(service.getReviews(scope)[0]?.rows[0]?.disposition).toBe("create");
});

it("requires an explicit candidate or omission for every non-ready row", async () => {
  const { service, review } = ambiguousImportReviewHarness();
  expect(review.canApply).toBe(false);
  service.setRowResolution(review.id, "ambiguous-1", { candidateId: "bound-local-1" });
  service.setRowResolution(review.id, "unresolved-1", { omit: true });
  expect(service.getReviews(review.scope)[0]?.canApply).toBe(true);
});
```

- [ ] **Step 2: Run and verify the reviewed service is absent**

Run: `cd integrations/zotero && npx vitest run test/reviewed-library-import.test.ts`

Expected: FAIL on missing service and tool constants.

- [ ] **Step 3: Implement the read-only tools and review state machine**

```ts
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
}

export class ReviewedLibraryImportService {
  readonly tools: readonly CodexDynamicToolSpec[];
  constructor(
    registry: CitationCandidateRegistry,
    host: LibraryMutationHost,
    callbacks: { onState(scope: CitationCapabilityScope): void },
    options?: ReviewedLibraryImportOptions,
  );
  invokeTool(name: string, args: Record<string, unknown>, scope: CitationCapabilityScope): Promise<Record<string, unknown>>;
  getReviews(scope: CitationCapabilityScope): LibraryImportReview[];
  setRowResolution(reviewId: string, rowId: string, resolution: { candidateId?: string; omit?: boolean }): void;
  resolveReview(reviewId: string, decision: "accept" | "reject"): Promise<LibraryImportResolution>;
}
```

`zotero_lookup_citations` delegates only to the registry. `zotero_propose_library_import` accepts only the complete, unique capability ID set from one registry batch, validates the collection target, obtains a read-only host preflight, and creates one in-memory review. It rejects missing unresolved rows, extra IDs, mixed batches, raw metadata, and an explicit library ID in proposal arguments. Normalize the collection name to NFC, trim it, and reject path separators, dot-path values, control/bidi/zero-width/format/newline characters, and more than 200 Unicode code points. It returns no raw mutable plan. Filter `getReviews()` by both thread and library and deep-clone every nested row/choice. `reject` marks the review rejected and makes zero host writes.

- [ ] **Step 4: Run proposal, schema, and review tests**

Run: `cd integrations/zotero && npx vitest run test/library-citations.test.ts test/reviewed-library-import.test.ts`

Expected: PASS for strict schemas, zero-write lookup/proposal/reject, complete row coverage, explicit ambiguity/omission choices, and subject filtering.

- [ ] **Step 5: Commit the review proposal slice**

```bash
git add integrations/zotero/src/reviewed-library-import.ts integrations/zotero/test/reviewed-library-import.test.ts
git commit -m "feat(zotero): review library imports before writes"
```

### Task 5: Apply serialization, stale preflight, and compensation

**Files:**
- Modify: `integrations/zotero/src/reviewed-library-import.ts`
- Modify: `integrations/zotero/test/reviewed-library-import.test.ts`

**Interfaces:**
- Consumes: pending review and bound plan from Task 4.
- Implements the already-defined `resolveReview()` accept path without adding a second mutation interface.
- Guarantees: synchronous claim, one exclusive queue, complete preflight before first write, reverse compensation, no automatic retry.

- [ ] **Step 1: Write failing Apply and rollback tests**

```ts
it("claims Apply synchronously and writes exactly once", async () => {
  const { service, host, review } = readyImportReviewHarness();
  const first = service.resolveReview(review.id, "accept");
  expect(service.getReviews(review.scope)[0]?.state).toBe("resolving");

  await expect(service.resolveReview(review.id, "accept"))
    .rejects.toThrow(/already resolved|being applied/);
  await first;
  expect(host.apply).toHaveBeenCalledOnce();
});

it("stops stale work before the first write and compensates partial work in reverse", async () => {
  const stale = readyImportReviewHarness();
  stale.host.preflight.mockResolvedValueOnce({ ...stale.proposalPreflight, digest: "changed" });
  await expect(stale.service.resolveReview(stale.review.id, "accept")).rejects.toThrow(/stale/);
  expect(stale.host.apply).not.toHaveBeenCalled();

  const partial = readyImportReviewHarness();
  partial.host.apply.mockRejectedValueOnce(new LibraryApplyFailure("save failed", partial.receipt));
  await expect(partial.service.resolveReview(partial.review.id, "accept")).rejects.toThrow(/rolled back/);
  expect(partial.host.compensate).toHaveBeenCalledWith(partial.receipt);
  expect(partial.host.invalidateLibrary).toHaveBeenCalledWith(1);
});
```

- [ ] **Step 2: Run and verify Apply behavior is missing**

Run: `cd integrations/zotero && npx vitest run test/reviewed-library-import.test.ts`

Expected: FAIL because accept, exclusive queue, receipt, and compensation are not implemented.

- [ ] **Step 3: Implement the host boundary and terminal states**

```ts
private runExclusive<T>(operation: () => Promise<T>): Promise<T>;
private runResolveReview(
  review: PendingLibraryImportReview,
  decision: "accept" | "reject",
): Promise<LibraryImportResolution>;
```

Flip `pending -> resolving` before the first await, then enter one service-wide promise queue. Re-run preflight and compare library editability, parent key/version, same-name sibling absence, candidate digests, duplicate dispositions, item versions, and memberships. On a `LibraryApplyFailure`, compensate its partial receipt, invalidate the library snapshot after success or failure, and leave exact survivor keys in a terminal failed review if rollback is incomplete.

- [ ] **Step 4: Run the complete service matrix**

Run: `cd integrations/zotero && npx vitest run test/reviewed-library-import.test.ts`

Expected: PASS for double click, two-review serialization, stale parent/sibling/candidate/duplicate cases, exact one-time Apply, reverse compensation, incomplete rollback, and no automatic retry.

- [ ] **Step 5: Commit the mutation coordinator slice**

```bash
git add integrations/zotero/src/reviewed-library-import.ts integrations/zotero/test/reviewed-library-import.test.ts
git commit -m "feat(zotero): apply reviewed library imports safely"
```

### Task 6: Zotero citation resolver and native mutation adapter

**Files:**
- Create: `integrations/zotero/src/zotero-library-import.ts`
- Modify: `integrations/zotero/src/reader-context.ts`
- Test: `integrations/zotero/test/zotero-library-import.test.ts`
- Test: `integrations/zotero/test/reader-context.test.ts`

**Interfaces:**
- Implements: `CitationResolver` and `LibraryMutationHost` from Tasks 3–5.
- Produces: `createZoteroCitationResolver()` and `createZoteroLibraryMutationHost()`.
- Produces on `ReaderContextService`: `invalidateZotkitLibrarySnapshot(libraryID)`.

- [ ] **Step 1: Write failing native-adapter contract tests with fake Zotero objects**

```ts
it("resolves exact local DOI before using the identifier translator", async () => {
  const { resolver, zotero } = zoteroResolverHarness({ existingDOI: "10.1000/abc" });
  const result = await resolver.resolve({ libraryID: 1 }, [{ clientRef: "r1", doi: "10.1000/ABC" }]);
  expect(result[0]?.candidates[0]?.localItemKey).toBe("EXISTING1");
  expect(zotero.Translate.Search).not.toHaveBeenCalled();
});

it("uses identifier translation as metadata only and never imports during lookup", async () => {
  const { resolver, translate } = zoteroResolverHarness({ translatedTitle: "A resolved paper" });
  const result = await resolver.resolve({ libraryID: 1 }, [{ clientRef: "r1", doi: "10.1000/new" }]);
  expect(translate.translate).toHaveBeenCalledWith(expect.objectContaining({
    libraryID: false,
    saveAttachments: false,
  }));
  expect(result[0]?.candidates[0]?.metadata.title).toBe("A resolved paper");
});

it("compensates only objects and memberships created by its receipt", async () => {
  const { host, existingItem, collection } = zoteroMutationHostHarness();
  const receipt = await host.apply(validatedPlan());
  await host.compensate(receipt);
  expect(existingItem.eraseTx).not.toHaveBeenCalled();
  expect(collection.removeItem).toHaveBeenCalledWith(existingItem.id);
});
```

- [ ] **Step 2: Run and verify the Zotero adapter is absent**

Run: `cd integrations/zotero && npx vitest run test/zotero-library-import.test.ts test/reader-context.test.ts`

Expected: FAIL on missing factories and snapshot invalidation API.

- [ ] **Step 3: Implement fail-closed native adapters**

The resolver order is exact local DOI, exact local arXiv/stable identifier, Zotero identifier translation, normalized local title/year/creator candidates, then explicit unresolved. Construct `new Zotero.Translate.Search()`, call `setIdentifier({ DOI: canonicalDoi })` or the equivalent arXiv object, select returned translators, and call `translate({ libraryID: false, saveAttachments: false })`; never call item `saveTx()` during lookup.

The mutation adapter must:

```ts
const collection = new zotero.Collection();
collection.libraryID = plan.libraryID;
collection.name = plan.collectionName;
collection.parentID = parent?.id ?? null;
await collection.saveTx();

const item = new zotero.Item(candidate.metadata.itemType);
item.libraryID = plan.libraryID;
item.setField("title", candidate.metadata.title);
item.setCreators(candidate.metadata.creators);
await item.saveTx();
await collection.addItem(item.id);
```

Before writing, positively verify editability. If the host cannot expose it, allow only `Zotero.Libraries.userLibraryID`. Use the complete native item enumeration and loaded collection/version data as Apply-time duplicate authority; a bounded Reader snapshot may assist lookup but may not justify `CREATE`. Record every created key and added membership immediately. Compensation removes added membership from pre-existing items, erases created items, then erases the created collection. It never erases a reused item or a membership that existed before Apply.

- [ ] **Step 4: Run adapter, resolver, and service tests**

Run: `cd integrations/zotero && npx vitest run test/zotero-library-import.test.ts test/reader-context.test.ts test/reviewed-library-import.test.ts`

Expected: PASS for editability, parent/sibling validation, item mapping, translator no-write behavior, save failure at every phase, receipts, compensation, and invalidation.

- [ ] **Step 5: Commit the native adapter slice**

```bash
git add integrations/zotero/src/zotero-library-import.ts integrations/zotero/src/reader-context.ts integrations/zotero/test/zotero-library-import.test.ts integrations/zotero/test/reader-context.test.ts
git commit -m "feat(zotero): adapt reviewed imports to Zotero"
```

### Task 7: Floating Palette view and Apple-like material

**Files:**
- Create: `integrations/zotero/src/library-agent-palette.ts`
- Modify: `integrations/zotero/src/styles.css`
- Test: `integrations/zotero/test/library-agent-palette.test.ts`
- Test: `integrations/zotero/test/build-assets.test.ts`

**Interfaces:**
- Consumes: `LibraryConversationState` and `LibraryImportReview`.
- Produces: `LibraryAgentPalette`, `LibraryAgentPaletteState`, `LibraryAgentPaletteCallbacks`.
- Emits semantic callbacks only; it never reads Zotero globals or invokes a mutation host.

- [ ] **Step 1: Write failing DOM, accessibility, and CSS-contract tests**

```ts
it("starts as a 46px dock and expands to the approved review palette", () => {
  const { host, view } = paletteHarness();
  view.setState(paletteState({ collapsed: true, reviewCount: 1 }));
  expect(host.querySelector(".zc-library-agent-palette")?.getAttribute("aria-expanded")).toBe("false");
  expect(host.querySelector(".zc-library-agent-transcript")).toBeNull();

  host.querySelector<HTMLButtonElement>(".zc-library-agent-expand")!.click();
  view.setState(paletteState({ collapsed: false, review: readyReview() }));
  expect(host.textContent).toContain("Mutation Proposal");
  expect(host.textContent).toContain("Apply 9 changes");
  expect(host.querySelector(".zc-library-agent-resize")?.getAttribute("role")).toBe("separator");
});

it("keeps Apply disabled until ambiguity and omission choices are explicit", () => {
  const { host, view } = paletteHarness();
  view.setState(paletteState({ collapsed: false, review: blockedReview() }));
  expect(host.querySelector<HTMLButtonElement>(".zc-library-agent-apply")!.disabled).toBe(true);
  expect(host.querySelector("select[aria-label='Resolve ambiguous citation']")).not.toBeNull();
  expect(host.querySelector("input[aria-label='Leave unresolved citation out']")).not.toBeNull();
});
```

- [ ] **Step 2: Run and verify the palette and CSS rules are missing**

Run: `cd integrations/zotero && npx vitest run test/library-agent-palette.test.ts test/build-assets.test.ts`

Expected: FAIL because the view and `zc-library-agent-*` rules do not exist.

- [ ] **Step 3: Build the DOM-only palette and exact geometry**

```ts
export interface LibraryAgentPaletteCallbacks {
  onExpandedChange(expanded: boolean): void;
  onHeightChange(height: number): void;
  onSend(text: string): void;
  onStop(): void;
  onModelChange(model: string): void;
  onEffortChange(effort: string): void;
  onReviewDecision(reviewId: string, decision: "accept" | "reject"): void;
  onRowResolution(reviewId: string, rowId: string, resolution: { candidateId?: string; omit?: boolean }): void;
}

export interface LibraryAgentPaletteState {
  collapsed: boolean;
  height: number;
  subjectLabel: string;
  connectionLabel: string;
  contextLabel: string;
  omittedItemCount: number;
  entries: readonly ChatEntry[];
  running: boolean;
  error: string | null;
  model: string;
  effort: string;
  composerText: string;
  sendDisabledReason: string | null;
  reviews: readonly LibraryImportReview[];
  activeReviewId: string | null;
}
```

Use a custom pointer/keyboard vertical grip and clamp height to 300–540px. The host is fixed and pointer-transparent; the palette child is interactive. CSS uses `width: min(1180px, calc(100vw - 40px))`, `bottom: 42px`, `border-radius: 22px`, translucent existing-token material, opaque review/composer capsules, `@media (prefers-reduced-transparency: reduce)`, `@media (prefers-reduced-motion: reduce)`, and an opaque fallback under `@supports not (backdrop-filter: blur(1px))`.

Render transcript Markdown through the existing safe renderer. Use the real product icon. Keep disposition text in addition to color, preserve focus, and clean document-level resize listeners in `destroy()`.

- [ ] **Step 4: Run palette and bundled-style tests**

Run: `cd integrations/zotero && npx vitest run test/library-agent-palette.test.ts test/build-assets.test.ts`

Expected: PASS for dock/expanded states, real callbacks, structured rows, keyboard/ARIA, resize cleanup, focus, responsive rules, exact geometry, and reduced effects.

- [ ] **Step 5: Commit the visual surface**

```bash
git add integrations/zotero/src/library-agent-palette.ts integrations/zotero/src/styles.css integrations/zotero/test/library-agent-palette.test.ts integrations/zotero/test/build-assets.test.ts
git commit -m "feat(zotero): add floating Library Agent palette"
```

### Task 8: Selection context adapter and per-window controller

**Files:**
- Create: `integrations/zotero/src/library-agent-context.ts`
- Create: `integrations/zotero/src/library-agent-controller.ts`
- Test: `integrations/zotero/test/library-agent-context.test.ts`
- Test: `integrations/zotero/test/library-agent-controller.test.ts`

**Interfaces:**
- Consumes: palette, Codex library methods, and reviewed import service.
- Produces: `readLibraryAgentContext()`, `ZoteroLibraryAgentContextAdapter`, and `LibraryAgentController`.
- Owns: one mounted host and exact listener cleanup per normal Zotero window.

- [ ] **Step 1: Write failing selection and lifecycle tests**

```ts
it("reads the current collection-tree row and caps top-level items at 50", () => {
  const snapshot = readLibraryAgentContext(zoteroSelectionFixture({ selectedItems: 53 }));
  expect(snapshot.subject.key).toBe("library:1");
  expect(snapshot.collection).toEqual({ key: "COLL1", path: "Research / Quantum" });
  expect(snapshot.selectedItems).toHaveLength(50);
  expect(snapshot.omittedItemCount).toBe(3);
});

it("never calls Zotero methods removed from the current library pane", () => {
  const fixture = zoteroSelectionFixture();
  fixture.pane.getSelectedCollection = vi.fn(() => { throw new Error("removed API"); });
  fixture.pane.getSelectedLibraryID = vi.fn(() => { throw new Error("removed API"); });
  expect(() => readLibraryAgentContext(fixture)).not.toThrow();
});

it("mounts one controller per window and shows it only on zotero-pane", () => {
  const { controller, win } = controllerHarness({ selectedID: "zotero-pane" });
  controller.mountWindow(win);
  expect(win.document.querySelectorAll(".zc-library-agent-host")).toHaveLength(1);
  win.Zotero_Tabs.selectedID = "reader-1";
  controller.syncVisibility(win);
  expect(win.document.querySelector<HTMLElement>(".zc-library-agent-host")!.hidden).toBe(true);
  controller.destroy();
  expect(win.document.querySelector(".zc-library-agent-host")).toBeNull();
});
```

- [ ] **Step 2: Run and verify the adapter/controller are missing**

Run: `cd integrations/zotero && npx vitest run test/library-agent-context.test.ts test/library-agent-controller.test.ts`

Expected: FAIL on missing modules.

- [ ] **Step 3: Implement current Zotero selection APIs and controller callbacks**

Read the focused tree row from `pane.collectionsView.selectedTreeRow.ref`, library metadata from `Zotero.Libraries.get()`, selected items from `pane.getSelectedItems(false, { libraryTabOnly: true })`, and collection ancestry from `Zotero.Collections.get(parentID)`. Do not call removed `getSelectedCollection()` or `getSelectedLibraryID()`.

Attach to `itemsView.onSelect`, `itemsView.onRefresh`, and `collectionsView.onSelect`; retain the exact listener functions and remove them on unmount. If the views are still loading, retry a bounded number of times and cancel those timers on destroy. Mixed-library selection and multiple selected collection rows produce an explicit context error and disable Send/Apply.

Controller callbacks call only:

```ts
codex.openLibraryConversation(subject)
codex.sendLibraryMessage(subject, message, immutableContext)
codex.stopLibraryTurn(subject)
imports.resolveReview(reviewId, decision)
imports.setRowResolution(reviewId, rowId, resolution)
```

New windows start collapsed. Keep expanded/collapsed state per window, persist only the height with `prefInt/setPrefInt`, expand on a user send/new review/Apply conflict, and never expand for a background state tick.

- [ ] **Step 4: Run pure context and controller tests**

Run: `cd integrations/zotero && npx vitest run test/library-agent-context.test.ts test/library-agent-controller.test.ts test/library-agent-palette.test.ts`

Expected: PASS for zero/one/many collection rows, mixed library, missing views, listener cleanup, duplicate mount, dedicated-window exclusion, subject switches, Send, Stop, review decisions, and idempotent destroy.

- [ ] **Step 5: Commit the controller slice**

```bash
git add integrations/zotero/src/library-agent-context.ts integrations/zotero/src/library-agent-controller.ts integrations/zotero/test/library-agent-context.test.ts integrations/zotero/test/library-agent-controller.test.ts
git commit -m "feat(zotero): control the library palette per window"
```

### Task 9: Plugin wiring and Workbench scope cleanup

**Files:**
- Modify: `integrations/zotero/src/plugin.ts`
- Modify: `integrations/zotero/src/sidebar.ts`
- Modify: `integrations/zotero/src/styles.css`
- Test: `integrations/zotero/test/plugin-state.test.ts`
- Test: `integrations/zotero/test/sidebar.test.ts`
- Test: `integrations/zotero/test/runtime-compat.test.ts`

**Interfaces:**
- Consumes: all services and controller from Tasks 1–8.
- Produces: one shared import service/tool provider and one controller entry per Zotero main window.
- Removes: `ResearchScope`, plugin `researchScope`, `setResearchScope()`, `onScopeChange`, and `.zc-scope-switch`.

- [ ] **Step 1: Write failing plugin-lifecycle and Workbench-boundary tests**

```ts
it("mounts the Library Agent in a normal library window and removes it on unload", async () => {
  const { plugin, win } = pluginHarness({ selectedID: "zotero-pane" });
  await plugin.onMainWindowLoad(win);
  expect(win.document.querySelector(".zc-library-agent-host")).not.toBeNull();
  await plugin.onMainWindowUnload(win);
  expect(win.document.querySelector(".zc-library-agent-host")).toBeNull();
});

it("keeps the palette out of dedicated and standalone Workbench windows", async () => {
  const { plugin, dedicated, standalone } = pluginWindowHarnesses();
  await plugin.onMainWindowLoad(dedicated);
  await plugin.onMainWindowLoad(standalone);
  expect(dedicated.document.querySelector(".zc-library-agent-host")).toBeNull();
  expect(standalone.document.querySelector(".zc-library-agent-host")).toBeNull();
});

it("contains no Workbench Library Chat switch", () => {
  const { body } = workbenchSidebarHarness();
  expect(body.textContent).not.toContain("Library Chat");
  expect(body.querySelector(".zc-scope-switch")).toBeNull();
});
```

- [ ] **Step 2: Run and verify lifecycle and scope tests fail**

Run: `cd integrations/zotero && npx vitest run test/plugin-state.test.ts test/sidebar.test.ts test/runtime-compat.test.ts`

Expected: FAIL because the plugin does not construct/mount the controller and Workbench still renders `Library Chat`.

- [ ] **Step 3: Wire the shared services and remove the fake scope**

Construct `CitationCandidateRegistry`, Zotero resolver/host, and `ReviewedLibraryImportService` before constructing `CodexService`. After Codex construction, call `setLibraryToolProvider()` with only lookup/propose. Construct `LibraryAgentController` once and let it mount each normal window.

Lifecycle order:

```ts
onMainWindowLoad(win) {
  this.injectWindowAssets(win);
  this.libraryAgent.mountWindow(win);
  this.workbenchTabs.install(win);
  this.installQLabMenu(win);
  this.installShortcutHandler(win);
}

onMainWindowUnload(win) {
  this.libraryAgent.unmountWindow(win);
  // existing float, Workbench, menu, and asset cleanup follows
}
```

In the controller's own Notifier observer, handle `tab select/load` before any Codex-connected early return and refresh data on `item`, `collection`, and `collection-item` notifications. `prepareDedicatedWorkbenchWindow()` must unmount the palette after marking the window dedicated because that path initially runs normal window setup.

Remove scope state/callback/render code from Sidebar and plugin. Keep the explicit `Zotero Library` add-context suggestion in paper chat; it is read-only evidence, not a library conversation.

- [ ] **Step 4: Run plugin, Sidebar, conversation, and import integration tests**

Run: `cd integrations/zotero && npx vitest run test/plugin-state.test.ts test/sidebar.test.ts test/runtime-compat.test.ts test/library-agent-controller.test.ts test/library-conversation.test.ts test/reviewed-library-import.test.ts`

Expected: PASS with no PDF/Reader/QLab-root access during a library send, no review leakage between surfaces, exact window cleanup, and no `Library Chat` control.

- [ ] **Step 5: Commit the integrated feature**

```bash
git add integrations/zotero/src/plugin.ts integrations/zotero/src/sidebar.ts integrations/zotero/src/styles.css integrations/zotero/test/plugin-state.test.ts integrations/zotero/test/sidebar.test.ts integrations/zotero/test/runtime-compat.test.ts
git commit -m "feat(zotero): integrate the Library Agent"
```

### Task 10: Release contract, verification, push, and issue handoff

**Files:**
- Modify: `integrations/zotero/README.md`
- Modify: `integrations/zotero/CHANGELOG.md`
- Modify: `integrations/zotero/manifest.json`
- Modify: `integrations/zotero/package.json`
- Modify: `integrations/zotero/package-lock.json`
- Modify: `integrations/zotero/test/manifest.test.ts`
- Modify: `docs/superpowers/specs/2026-07-31-zotero-library-agent-design.md` only if implementation reveals a factual mismatch.
- Modify: `docs/superpowers/plans/2026-07-31-zotero-library-agent.md` to check completed boxes.

**Interfaces:**
- Produces: v0.11.0 documentation and manifest/package agreement.
- Produces: verified commits on `fix/zotero-fix-pack-b`, pushed to `publish`.
- Produces: one completion comment on GitHub issue #9 after push succeeds.

- [ ] **Step 1: Write the failing v0.11.0 manifest assertion**

```ts
expect(manifest.version).toBe("0.11.0");
```

Document the ordinary-library Floating Palette, one-thread-per-library rule, context chips, review gate, safe v1 effects, exact identifier limitation, and macOS checklist. Add the release entry above v0.10.1.

- [ ] **Step 2: Run the manifest test and verify the old version failure**

Run: `cd integrations/zotero && npx vitest run test/manifest.test.ts`

Expected: FAIL with received version `0.10.1`.

- [ ] **Step 3: Update manifest, package metadata, README, and changelog**

Set `manifest.json`, `package.json`, and both root package records in `package-lock.json` to `0.11.0`. Do not change Zotero compatibility floors or the update URL.

- [ ] **Step 4: Run the complete Linux gate**

Run:

```bash
cd integrations/zotero
npm run check
npm test
```

Expected: TypeScript succeeds and the entire Vitest suite passes. Then run `npm run build` once. On Linux, the expected native-helper blocker is the existing `xcrun`/universal-macOS build requirement; record that exact output without claiming an XPI build passed. Run `npm run test:visual` once; if Chromium sandboxing blocks it, record that exact blocker and retain deterministic DOM/CSS coverage.

- [ ] **Step 5: Request code review and fix only in-scope findings**

Use `superpowers:requesting-code-review` against the design spec and the merge base `170fb2d5`. Re-run the focused tests for every accepted correction, then re-run `npm run check && npm test`.

- [ ] **Step 6: Commit release documentation**

```bash
git add integrations/zotero/README.md integrations/zotero/CHANGELOG.md integrations/zotero/manifest.json integrations/zotero/package.json integrations/zotero/package-lock.json integrations/zotero/test/manifest.test.ts docs/superpowers/specs/2026-07-31-zotero-library-agent-design.md docs/superpowers/plans/2026-07-31-zotero-library-agent.md
git commit -m "docs(zotero): release Library Agent 0.11.0"
```

- [ ] **Step 7: Push the completed fix branch**

Run: `git push publish fix/zotero-fix-pack-b`

Expected: remote `fix/zotero-fix-pack-b` advances to the verified release commit; `main` remains untouched.

- [ ] **Step 8: Comment on GitHub issue #9 after the push**

Post one comment to `ChanceSiyuan/quarto-lab#9` containing:

- the branch name and final commit SHA;
- the Floating Palette preview link;
- implemented conversation, context, and reviewed-mutation behavior;
- Linux TypeScript/Vitest totals and any build/browser blockers;
- the explicit remaining macOS/Zotero translator, visual, dark-mode, resize, editability, and compensation checklist.

Verify the comment URL before reporting completion.
