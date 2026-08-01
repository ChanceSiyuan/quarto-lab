# QLab Remote Draft Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a root-locked `QLabRepository` broker so a selected SSH repository supports the same QMD list/read/create/edit/working-copy/preview/Keep workflow as local Drafts, while trusted Knowledge stays read-only and generic remote execution remains impossible.

**Architecture:** This is Slice 3 and extends the target, SSH master, helper envelope, bootstrap, and `AgentConnection` delivered by the Remote Chat plan. `QmdWorkspaceView`, plugin Draft actions, and the Note/Draft bridge depend only on a closed `QLabRepository`; `LocalQLabRepository` preserves current Gecko behavior, while `SshQLabRepository` uses a separate root-bound helper channel with an exhaustive RPC union, cursor-based invalidation, revision CAS, and a durable idempotency journal.

**Tech Stack:** TypeScript 7, Vitest 4, Zotero 9/Gecko, C17/POSIX descriptor-relative I/O, OpenSSH multiplexed channels, UTF-8 JSONL, Python `unittest`.

## Global Constraints

- Complete `docs/superpowers/plans/2026-07-31-qlab-local-target-switching.md` and all Remote Chat tasks first. Consume the landed `RepositoryTargetSnapshot`, `RepositoryTargetController`, staged `TargetSwitchRuntime`, fixed `SshMaster` channels, common bound helper envelopes, persisted host/repository identity, verified helper bootstrap, and target epochs; do not create parallel target, transport, activation, or transition types.
- There is exactly one repository interface and exactly one exhaustive remote method union. Slice 3 contains no `runCommand`, `exec`, argv, shell, Quarto, terminal, preview-server, or Main Site method. Those process operations belong to Slice 4.
- The broker accepts normalized repository-relative paths only. Reject NUL, backslash, absolute paths, empty/`.`/`..` segments, hidden escape components, every symlink component, non-regular QMD files, and descriptor/symlink swaps. Hold the canonical root descriptor for the channel lifetime.
- Reads are limited to `knowledge/**/*.qmd`, `drafts/**/*.qmd`, the selected Draft's `work/qlab-zotero/draft-changes/<identity>/draft.qmd`, and its bounded `.qlab-preview-*.qmd`. Generic writes never target `knowledge/**`, `literature/**`, arbitrary `work/**`, repository metadata, or files outside those four path brands.
- `knowledge/**/*.qmd` remains trusted and read-only. Slice 3 does not initialize a remote repository and does not enable remote promotion or External Editor.
- Every RPC response and watch event is accepted only when protocol version, helper version, target ID, target epoch, host instance ID, and repository ID match the adapter's captured identity. A target switch makes old callbacks, reviews, operations, and manifests stale even when the relative path is identical.
- A mutation is retryable only with the same operation ID and byte-identical request digest. After a complete frame is accepted, disconnect means outcome unknown until `mutation.status` resolves it; never manufacture a second operation ID.
- Slice-1 Task 0's PATH-resolved archive and Linux PTY portability changes are prerequisites. Linux gates may run `npm run native:test` after that task, plus the static remote helper, but not signed universal/XPI assembly. Final XPI gates run on macOS after explicit `native:remote:stage`; never reintroduce `/usr/bin/zip` as application logic.

---

### Task 1: Define the complete `QLabRepository` contract and preserve local behavior

**Files:**
- Create: `integrations/zotero/src/qlab-repository.ts`
- Create: `integrations/zotero/src/local-qlab-repository.ts`
- Create: `integrations/zotero/test/local-qlab-repository.test.ts`
- Modify: `integrations/zotero/src/qmd-index.ts`
- Modify: `integrations/zotero/test/qmd-index.test.ts`
- Modify: `integrations/zotero/src/qmd-workspace.ts`
- Modify: `integrations/zotero/test/qmd-workspace.test.ts`

**Interfaces:**
- Produces disjoint brands `KnowledgeQmdPath`, `DraftQmdPath`, `WorkingCopyQmdPath`, and `PreviewQmdPath`; `ReadableQmdPath` is their union and `WritableQmdPath` is `DraftQmdPath | WorkingCopyQmdPath | PreviewQmdPath`. It also produces `KnowledgeDirectoryPath`, `DraftDirectoryPath`, and `ListedDirectoryPath`. Only validating constructors may create a branded path.
- Produces `RepositoryAdapterIdentity = Readonly<{ targetId:string; targetEpoch:number; hostInstanceId:string|null; repositoryId:string }>` and `QLabRepositoryAdapterState = Readonly<{ status:"connecting"|"ready"|"disconnected"|"error"; identity:RepositoryAdapterIdentity; error:string|null }>`; the longer name deliberately avoids collision with the existing repository-shape `QLabRepositoryState` exported by `qlab-workspace.ts` and used by Fix Pack B Main Site/sidebar callbacks.
- Produces an explicit tree snapshot. A directory row is not synthesized from a file row, so an empty `drafts/topic/` survives the adapter boundary.
- Produces all local and remote operations needed by the existing workspace. No process method is present.

```ts
export type Revision = string & { readonly __revision: unique symbol };
export type QmdCursor = string & { readonly __qmdCursor: unique symbol };
export type RepositoryOperationId = string & { readonly __operationId: unique symbol };

export type QmdListEntry =
  | Readonly<{ kind: "directory"; path: ListedDirectoryPath; tree: "knowledge" | "drafts" }>
  | Readonly<{ kind: "qmd"; path: KnowledgeQmdPath | DraftQmdPath; tree: "knowledge" | "drafts"; revision: Revision }>;
export type QmdListSnapshot = Readonly<{ entries: readonly QmdListEntry[]; cursor: QmdCursor }>;
export type RevisionedQmd<P extends ReadableQmdPath = ReadableQmdPath> =
  Readonly<{ path: P; source: string; revision: Revision }>;

export type QmdWatchEvent =
  | Readonly<{ identity:RepositoryAdapterIdentity; cursor:QmdCursor; kind:"changed"; path:KnowledgeQmdPath|DraftQmdPath; change:"created"|"modified"|"deleted" }>
  | Readonly<{ identity:RepositoryAdapterIdentity; cursor:QmdCursor; kind:"overflow"; firstUnavailableCursor:QmdCursor }>
  | Readonly<{ identity:RepositoryAdapterIdentity; cursor:QmdCursor; kind:"restart"; helperInstanceId:string }>;
export interface QmdSubscription { close(): Promise<void>; }

export type MutationIdentity = Readonly<{ identity:RepositoryAdapterIdentity; operationId:RepositoryOperationId }>;
export type CreateDraftFile = MutationIdentity & Readonly<{ path:DraftQmdPath; source:string; expected:"absent" }>;
export type CreateDraftDirectory = MutationIdentity & Readonly<{ path:DraftDirectoryPath; expected:"absent" }>;
export type WriteIfRevision<P extends WritableQmdPath = WritableQmdPath> = MutationIdentity & Readonly<{ path:P; expectedRevision:Revision; source:string }>;
export type PrepareDraftChange = MutationIdentity & Readonly<{ originalPath:DraftQmdPath; expectedOriginalRevision:Revision }>;
export type PreparedDraftChange = Readonly<{
  original:RevisionedQmd<DraftQmdPath>;
  workingCopy:RevisionedQmd<WorkingCopyQmdPath>;
  previewPath:PreviewQmdPath;
}>;
export type RefreshPreview = MutationIdentity & Readonly<{
  originalPath:DraftQmdPath; workingCopyPath:WorkingCopyQmdPath; previewPath:PreviewQmdPath;
  expectedWorkingCopyRevision:Revision;
}>;
export type KeepDraftChange = MutationIdentity & Readonly<{
  originalPath:DraftQmdPath; workingCopyPath:WorkingCopyQmdPath; previewPath:PreviewQmdPath;
  expectedOriginalRevision:Revision; expectedWorkingCopyRevision:Revision;
}>;
export type RemovePreview = MutationIdentity & Readonly<{ path:PreviewQmdPath; expectedRevision:Revision|null }>;

export type RepositoryMutationMethod =
  | "draft.createFile" | "draft.createDirectory" | "draft.writeIfRevision"
  | "draft.prepareChange" | "draft.refreshPreview" | "draft.keepChange" | "draft.removePreview";
export type RepositoryMutationError =
  | Readonly<{ code:"ALREADY_EXISTS"|"NOT_FOUND"|"MUTATION_MISMATCH"|"PATH_REJECTED"; message:string }>
  | Readonly<{ code:"REVISION_CONFLICT"; message:string; currentRevisions:readonly Readonly<{ path:ReadableQmdPath; revision:Revision }>[] }>;
export interface MutationSuccessByMethod {
  "draft.createFile": RevisionedQmd<DraftQmdPath>;
  "draft.createDirectory": { path:DraftDirectoryPath; cursor:QmdCursor };
  "draft.writeIfRevision": RevisionedQmd<WritableQmdPath>;
  "draft.prepareChange": PreparedDraftChange;
  "draft.refreshPreview": RevisionedQmd<PreviewQmdPath>;
  "draft.keepChange": { original:RevisionedQmd<DraftQmdPath>; workingCopyRemoved:boolean; previewRemoved:boolean };
  "draft.removePreview": { removed:boolean };
}
export type MutationCallResult<M extends RepositoryMutationMethod> =
  | Readonly<{ state:"applied"; operationId:RepositoryOperationId; result:MutationSuccessByMethod[M] }>
  | Readonly<{ state:"rejected"; operationId:RepositoryOperationId; error:RepositoryMutationError }>
  | Readonly<{ state:"outcome-unknown"; operationId:RepositoryOperationId }>;

export interface QLabRepository {
  state(): QLabRepositoryAdapterState;
  listQmd(): Promise<QmdListSnapshot>;
  subscribeQmd(cursor: QmdCursor, listener: (event: QmdWatchEvent) => void): Promise<QmdSubscription>;
  read<P extends ReadableQmdPath>(path: P): Promise<RevisionedQmd<P>>;
  createDraftFile(request: CreateDraftFile): Promise<MutationCallResult<"draft.createFile">>;
  createDraftDirectory(request: CreateDraftDirectory): Promise<MutationCallResult<"draft.createDirectory">>;
  writeIfRevision(request: WriteIfRevision): Promise<MutationCallResult<"draft.writeIfRevision">>;
  prepareDraftChange(request: PrepareDraftChange): Promise<MutationCallResult<"draft.prepareChange">>;
  refreshPreview(request: RefreshPreview): Promise<MutationCallResult<"draft.refreshPreview">>;
  keepDraftChange(request: KeepDraftChange): Promise<MutationCallResult<"draft.keepChange">>;
  removePreview(request: RemovePreview): Promise<MutationCallResult<"draft.removePreview">>;
  mutationStatus(operationId: RepositoryOperationId): Promise<MutationStatus>;
  close(): Promise<void>;
}
```

Define `MutationStatus` with Task 4's typed public-status union in this same file before compiling Task 1; Task 4 implements persistence. Every mutator uses the same `MutationCallResult`, so a disconnect after a complete frame can preserve the original operation ID as `outcome-unknown`. No request/result member may be `unknown`, `Record<string, unknown>`, `any`, optional identity, or naked path string.

- [ ] **Step 1: Add a behavioral red test to the existing index scanner**

```ts
it("retains an explicit empty Draft directory", async () => {
  scanner.set("/repo/drafts", [{ name: "empty", directory: true }]);
  scanner.set("/repo/drafts/empty", []);
  expect(await buildQmdIndex(scanner, "/repo")).toContainEqual({
    kind: "directory", relativePath: "drafts/empty", treeId: "drafts",
  });
});
```

Run: `cd integrations/zotero && npx vitest run test/qmd-index.test.ts`

Expected: FAIL because today's `buildQmdIndex()` emits only QMD leaves and loses empty directories.

- [ ] **Step 2: Add contract and local-adapter tests covering every path brand and method**

`local-qlab-repository.test.ts` must call `state`, `listQmd`, `subscribeQmd`, `read` once for each of Knowledge/Draft/working-copy/preview, both create methods, revision-matched and revision-conflicting `writeIfRevision`, `prepareDraftChange`, `refreshPreview`, `keepDraftChange`, `removePreview`, and `mutationStatus`. It must assert Knowledge write rejection at the brand constructor and runtime adapter boundary, and compile-time `@ts-expect-error` checks must prove a Knowledge path cannot enter any write request.

Run: `cd integrations/zotero && npx vitest run test/local-qlab-repository.test.ts test/qmd-index.test.ts`

Expected: FAIL because `qlab-repository.ts`/`local-qlab-repository.ts` do not exist and the index still omits directory records; no Slice-1 import is missing.

- [ ] **Step 3: Implement the closed contract, explicit index rows, and local delegation**

Move the current safe path, revision hash, Draft working-copy manifest, preview copy, atomic replacement, and pending-change behavior out of plugin callbacks into `LocalQLabRepository`. The adapter must delegate Gecko I/O and preserve current filenames and user-visible behavior. `QmdWorkspaceOptions` becomes `{ repository: QLabRepository; ...presentation callbacks... }`; remove its individual filesystem callbacks only after the adapter test covers each one.

- [ ] **Step 4: Run local adapter/workspace tests green**

Run: `cd integrations/zotero && npx vitest run test/qmd-index.test.ts test/local-qlab-repository.test.ts test/qmd-workspace.test.ts && npm run check`

Expected: PASS; empty directories are visible, Knowledge is readable but never writable, and current local Draft/working-copy/preview behavior is unchanged.

- [ ] **Step 5: Run the full TypeScript regression gate**

Run: `cd integrations/zotero && npm run check && npm test`

Expected: PASS.

- [ ] **Step 6: Commit the repository seam**

```bash
git add integrations/zotero/src/qlab-repository.ts integrations/zotero/src/local-qlab-repository.ts integrations/zotero/src/qmd-index.ts integrations/zotero/src/qmd-workspace.ts integrations/zotero/test/local-qlab-repository.test.ts integrations/zotero/test/qmd-index.test.ts integrations/zotero/test/qmd-workspace.test.ts
git commit -m "feat(zotero): close QLab repository access behind an adapter"
```

### Task 2: Extend the common helper envelope with one exhaustive repository RPC union

**Files:**
- Create: `integrations/zotero/src/remote-repository-protocol.ts`
- Create: `integrations/zotero/test/remote-repository-protocol.test.ts`
- Modify: `integrations/zotero/src/remote-helper-protocol.ts`
- Modify: `integrations/zotero/test/remote-helper-protocol.test.ts`
- Modify: `integrations/zotero/src/ssh-target-transport.ts`
- Modify: `integrations/zotero/test/ssh-target-transport.test.ts`
- Modify: `integrations/zotero/native/include/qlab_remote_protocol.h`
- Modify: `integrations/zotero/native/src/qlab_remote_helper.c`
- Modify: `integrations/zotero/native/tests/test_remote_helper.py`
- Modify: `integrations/zotero/native/Makefile`

**Interfaces:**
- Reuses the Slice-2 `HelperRequest`, `HelperResponse`, and `HelperEvent` envelopes after a bound repository hello. Every repository frame echoes `{ protocolVersion:1, helperVersion, targetId, targetEpoch, hostInstanceId, repositoryId, capabilities }`; request/response IDs remain bounded and a response contains exactly one typed result or typed error.
- Produces exactly this method map; `RepositoryRequest` and `RepositoryResponse` are mapped discriminated unions, not a `{ method:string; params:unknown }` public type.

```ts
export interface RepositoryRpcMap {
  "repository.state": { params: Record<string, never>; result: QLabRepositoryAdapterState };
  "qmd.list": { params: Record<string, never>; result: QmdListSnapshot };
  "qmd.subscribe": { params: { cursor: QmdCursor }; result: { subscriptionId: string; cursor: QmdCursor } };
  "qmd.read": { params: { path: ReadableQmdPath }; result: RevisionedQmd };
  "draft.createFile": { params: CreateDraftFile; result: MutationSuccessByMethod["draft.createFile"] };
  "draft.createDirectory": { params: CreateDraftDirectory; result: MutationSuccessByMethod["draft.createDirectory"] };
  "draft.writeIfRevision": { params: WriteIfRevision; result: MutationSuccessByMethod["draft.writeIfRevision"] };
  "draft.prepareChange": { params: PrepareDraftChange; result: MutationSuccessByMethod["draft.prepareChange"] };
  "draft.refreshPreview": { params: RefreshPreview; result: MutationSuccessByMethod["draft.refreshPreview"] };
  "draft.keepChange": { params: KeepDraftChange; result: MutationSuccessByMethod["draft.keepChange"] };
  "draft.removePreview": { params: RemovePreview; result: MutationSuccessByMethod["draft.removePreview"] };
  "mutation.status": { params: { operationId: RepositoryOperationId }; result: MutationStatus };
}
export type RepositoryMethod = keyof RepositoryRpcMap;
export type RepositoryRequest = {
  [M in RepositoryMethod]: HelperRequest & { method: M; params: RepositoryRpcMap[M]["params"] }
}[RepositoryMethod];
export type RepositoryResponse = {
  [M in RepositoryMethod]:
    | (HelperResponse & { method:M; result:RepositoryRpcMap[M]["result"]; error?:never })
    | (HelperResponse & { method:M; result?:never; error:{ code:RepositoryErrorCode; message:string } })
}[RepositoryMethod];

export type RepositoryEvent =
  | (HelperEvent & { event: "qmd.changed"; cursor: QmdCursor; params: { subscriptionId:string; path:KnowledgeQmdPath|DraftQmdPath; change:"created"|"modified"|"deleted" } })
  | (HelperEvent & { event: "qmd.overflow"; cursor: QmdCursor; params: { subscriptionId:string; firstUnavailableCursor:QmdCursor } })
  | (HelperEvent & { event: "qmd.restart"; cursor: QmdCursor; params: { subscriptionId:string; helperInstanceId:string } });
```

`qmd.subscribe` owns a dedicated fixed `openRepository(snapshot)` helper channel added to `SshMaster`; closing that channel is unsubscribe. It is the only Slice-3 transport addition and takes a bound snapshot, not a mode/argv. Its `BoundClientHello` carries the snapshot's canonical root and expected host/raw repository UUID/opaque repository ID; the helper performs Remote Chat's no-follow root/UUID validation and returns root/raw UUID, after which the client recomputes fingerprint-bound endpoint/repository/target identity before accepting the channel. No unsubscribe RPC and no general command are needed. The C dispatcher has an explicit branch for all twelve methods and a final `METHOD_NOT_ALLOWED`; its parser rejects missing or extra method parameters. `RepositoryErrorCode` is a closed union covering protocol/identity/path/not-found/already-exists/revision-conflict/cursor-gap/mutation-mismatch/internal failures. `SshQLabRepository` maps a typed mutation error response to public `MutationCallResult.state:"rejected"`; only a transport disconnect after the complete request may have reached the helper maps to `state:"outcome-unknown"`, retaining the original operation ID for `mutation.status`.

- [ ] **Step 1: Write codec exhaustiveness and real-helper security tests**

The TypeScript test must round-trip one request/result for every key of `RepositoryRpcMap`, round-trip all three event variants, reject unknown/missing methods and parameters, and use an `assertNever()` switch so adding a method fails compilation until codecs/tests are updated. Python starts the actual helper against a temporary Git repository and tests `/etc/passwd`, `drafts/../knowledge/a.qmd`, backslashes, NUL, `drafts/link/a.qmd`, a final-component symlink, a symlink swapped after validation, Knowledge/literature writes, unrelated `work/`, and a fabricated preview path. Assert fixture bytes and mtimes are unchanged.

- [ ] **Step 2: Run the protocol/native tests and verify the concrete red state**

Run: `cd integrations/zotero && npx vitest run test/remote-helper-protocol.test.ts test/remote-repository-protocol.test.ts && make -C native remote-test`

Expected: the TypeScript repository codec is absent and the current helper returns `METHOD_NOT_ALLOWED` for `qmd.list`; Slice-2 hello/identity tests remain green.

- [ ] **Step 3: Implement strict codecs and descriptor-relative C dispatch**

Open the canonical repository root once. Walk every component with `openat(..., O_DIRECTORY|O_NOFOLLOW)`, open final regular files with `O_NOFOLLOW`, compare `fstat` device/inode where a later rename depends on prior validation, create sibling temporaries with `O_CREAT|O_EXCL` and mode `0600`, fsync file and parent, and use descriptor-relative `renameat`. Directory creation walks only beneath `drafts/`. Never pass user text to `system`, `popen`, `/bin/sh`, `exec*`, or an argv builder.

- [ ] **Step 4: Run protocol and native security tests green**

Run: `cd integrations/zotero && npx vitest run test/remote-helper-protocol.test.ts test/remote-repository-protocol.test.ts && make -C native remote-test`

Expected: PASS for all twelve methods, every event, fragmented UTF-8, 8 MiB limit, duplicate/unknown IDs, malformed/extra parameters, and every path/race rejection.

- [ ] **Step 5: Prove the method surface has no process escape hatch**

Run: `cd integrations/zotero && ! rg -n 'runCommand|run_command|repository\.exec|method: "exec"|system\(|popen\(|/bin/sh' src/remote-repository-protocol.ts native/src/qlab_remote_helper.c test/remote-repository-protocol.test.ts native/tests/test_remote_helper.py`

Expected: no matches.

- [ ] **Step 6: Commit the closed repository wire contract**

```bash
git add integrations/zotero/src/remote-helper-protocol.ts integrations/zotero/src/remote-repository-protocol.ts integrations/zotero/src/ssh-target-transport.ts integrations/zotero/test/remote-helper-protocol.test.ts integrations/zotero/test/remote-repository-protocol.test.ts integrations/zotero/test/ssh-target-transport.test.ts integrations/zotero/native/include/qlab_remote_protocol.h integrations/zotero/native/src/qlab_remote_helper.c integrations/zotero/native/tests/test_remote_helper.py integrations/zotero/native/Makefile
git commit -m "feat(zotero): add a closed remote repository protocol"
```

### Task 3: Implement identity-bound snapshots, subscriptions, and exact cursor recovery

**Files:**
- Create: `integrations/zotero/src/ssh-qlab-repository.ts`
- Create: `integrations/zotero/test/ssh-qlab-repository.test.ts`
- Modify: `integrations/zotero/src/qmd-workspace.ts`
- Modify: `integrations/zotero/test/qmd-workspace.test.ts`
- Modify: `integrations/zotero/native/src/qlab_remote_helper.c`
- Modify: `integrations/zotero/native/tests/test_remote_helper.py`

**Interfaces:**
- Produces `SshQLabRepository(snapshot, channelFactory)` implementing every Task-1 method. It reads expected host/repository IDs from the resolved snapshot; duplicate constructor identity parameters are forbidden. Task 3 implements state/list/subscribe/read fully; mutation methods call Task-4 typed RPCs, never local I/O.
- Each response/event contains and is checked against `{ targetId, targetEpoch, hostInstanceId, repositoryId }`. An event missing any member is a protocol error, not a refresh hint.
- Produces an atomic snapshot cursor contract: the helper starts the watcher and event ledger before scanning, captures cursor `start`, scans explicit directories/files and revisions, applies all buffered events `(start, end]` to that snapshot, and returns the resulting entries with cursor `end`. Thus the entries represent the tree through the returned cursor.
- `QmdCursor` wire values are canonical unsigned decimal 64-bit sequence strings, so the client detects a missing successor without lexical comparison. `qmd.subscribe(cursor)` replays ledger events strictly after the cursor, then streams live events. A cursor older than the ring's first retained value returns `CURSOR_GAP`; native watcher overflow emits `qmd.overflow`; reopening only the repository channel on the same live master generation and observing a new bound `helperInstanceId` produces one local `restart` recovery signal. Master loss is not adapter-local reconnect: Remote Chat's single reconnect coordinator replaces the whole target graph at a newer master generation and target epoch, while this old adapter becomes permanently stale.

- [ ] **Step 1: Write snapshot atomicity and identity rejection tests**

```ts
it("returns entries reflecting every change through its cursor", async () => {
  helper.pauseScanAfter("drafts/a.qmd");
  const pending = repository.listQmd();
  helper.write("drafts/b.qmd", "B");
  helper.resumeScan();
  const snapshot = await pending;
  expect(snapshot.entries).toContainEqual(expect.objectContaining({ path: "drafts/b.qmd" }));
  expect(snapshot.cursor).toBe(helper.cursorAfter("drafts/b.qmd"));
});

it("drops an event from the disposed old channel before workspace listeners", async () => {
  const listener = vi.fn();
  await repository.subscribeQmd(cursor("40"), listener);
  oldChannel.emit(changedEvent({ targetEpoch: snapshot.targetEpoch - 1, cursor: "41" }));
  expect(listener).not.toHaveBeenCalled();
  expect(repository.state().status).toBe("ready");
});
```

Add a separate current-channel wrong-identity test that transitions the adapter to protocol error. Real-helper tests mutate during enumeration, verify returned snapshot/cursor, then subscribe at that cursor and prove no change is lost or delivered twice.

- [ ] **Step 2: Run focused TypeScript/native tests red**

Run: `cd integrations/zotero && npx vitest run test/ssh-qlab-repository.test.ts test/qmd-workspace.test.ts && make -C native remote-test`

Expected: the SSH adapter is absent and the helper has no watcher ledger; current local workspace tests remain green.

- [ ] **Step 3: Implement one pending map, monotonic cursors, and coalesced reconciliation**

Use one pending RPC map keyed by bounded request ID, one accepted cursor, and one `reconcilePromise`. On `CURSOR_GAP`, `qmd.overflow`, same-master `qmd.restart`/repository-channel reopen, or non-contiguous cursor, atomically replace the cached snapshot with exactly one `listQmd()` result and open one new subscription at its cursor. Concurrent signals join the same promise. Master loss instead rejects all pending requests, marks this adapter disconnected, and emits no further listener calls; the newly staged adapter performs its own initial list/subscription after Remote Chat publishes the replacement epoch. A normal remote event updates cached rows directly; remote repositories never use the local two-second filesystem poll.

- [ ] **Step 4: Test every recovery trigger and reconnect boundary**

`ssh-qlab-repository.test.ts` must separately cover contiguous replay, cursor gap, overflow, same-master helper/channel restart, duplicated event, skipped cursor, old target ID, old epoch, wrong host, and wrong repository. For each in-adapter recovery trigger assert one list request, one replacement subscription, and no duplicate listener delivery. A separate master-loss/new-generation test asserts zero reopen/list requests on the old adapter, permanent old-listener fencing, and one initial list/subscription from the replacement adapter at the controller-published newer epoch.

Run: `cd integrations/zotero && npx vitest run test/ssh-qlab-repository.test.ts test/qmd-workspace.test.ts && make -C native remote-test`

Expected: PASS.

- [ ] **Step 5: Preserve local polling only behind `LocalQLabRepository`**

Run: `cd integrations/zotero && ! rg -n 'setInterval|2000|2_000' src/qmd-workspace.ts src/ssh-qlab-repository.ts && npm run check && npm test`

Expected: no polling match in either remote adapter or workspace; any retained local coalescing is owned by `local-qlab-repository.ts`; TypeScript gate passes.

- [ ] **Step 6: Commit remote read/watch behavior**

```bash
git add integrations/zotero/src/ssh-qlab-repository.ts integrations/zotero/src/qmd-workspace.ts integrations/zotero/test/ssh-qlab-repository.test.ts integrations/zotero/test/qmd-workspace.test.ts integrations/zotero/native/src/qlab_remote_helper.c integrations/zotero/native/tests/test_remote_helper.py
git commit -m "feat(zotero): reconcile remote QMD snapshots by cursor"
```

### Task 4: Make every Draft mutation revision-safe, idempotent, and restart-recoverable

**Files:**
- Modify: `integrations/zotero/src/qlab-repository.ts`
- Modify: `integrations/zotero/src/local-qlab-repository.ts`
- Modify: `integrations/zotero/src/ssh-qlab-repository.ts`
- Create: `integrations/zotero/test/remote-draft-mutations.test.ts`
- Modify: `integrations/zotero/test/local-qlab-repository.test.ts`
- Modify: `integrations/zotero/native/include/qlab_remote_protocol.h`
- Modify: `integrations/zotero/native/src/qlab_remote_helper.c`
- Modify: `integrations/zotero/native/tests/test_remote_helper.py`

**Interfaces:**
- Produces a private journal at `~/.qlab/state/repositories/<repositoryId>/mutations/<operationId>.json`, directory mode `0700`, record mode `0600`. Journal filenames derive only from validated operation IDs.
- The durable record is a method-discriminated recovery union. Its request payload contains every semantic path/revision plus a verified staged artifact descriptor wherever bytes will be committed; `mutation.status` is a separate, safe projection and never exposes private artifact locations:

```ts
export type StagedMutationArtifact = Readonly<{
  /** Validated basename under this operation's private journal directory; never an arbitrary path. */
  name:`${RepositoryOperationId}.stage`; byteLength:number; sha256:string;
}>;
export interface PreparedMutationByMethod {
  "draft.createFile": { path:DraftQmdPath; expected:"absent"; source:StagedMutationArtifact };
  "draft.createDirectory": { path:DraftDirectoryPath; expected:"absent" };
  "draft.writeIfRevision": { path:WritableQmdPath; expectedRevision:Revision; source:StagedMutationArtifact };
  "draft.prepareChange": { originalPath:DraftQmdPath; workingCopyPath:WorkingCopyQmdPath; previewPath:PreviewQmdPath; expectedOriginalRevision:Revision; source:StagedMutationArtifact };
  "draft.refreshPreview": { originalPath:DraftQmdPath; workingCopyPath:WorkingCopyQmdPath; previewPath:PreviewQmdPath; expectedWorkingCopyRevision:Revision; source:StagedMutationArtifact };
  "draft.keepChange": { originalPath:DraftQmdPath; workingCopyPath:WorkingCopyQmdPath; previewPath:PreviewQmdPath; expectedOriginalRevision:Revision; expectedWorkingCopyRevision:Revision; source:StagedMutationArtifact };
  "draft.removePreview": { path:PreviewQmdPath; expectedRevision:Revision|null };
}
export type MutationOutcome<M extends RepositoryMutationMethod> =
  | Readonly<{ ok:true; result:MutationSuccessByMethod[M] }>
  | Readonly<{ ok:false; error:RepositoryMutationError }>;
export type MutationRecord = { [M in RepositoryMutationMethod]: Readonly<{
  schemaVersion:1; operationId:RepositoryOperationId; requestDigest:string;
  targetId:string; repositoryId:string; method:M; request:PreparedMutationByMethod[M];
  resultRevision:Revision|null;
  resultContentSha256:string|null; outcome:MutationOutcome<M>|null;
  state:"prepared"|"applied"; createdAt:string; updatedAt:string;
}> }[RepositoryMutationMethod];
export type MutationStatus =
  | Readonly<{ state:"absent"; operationId:RepositoryOperationId; targetId:string; repositoryId:string }>
  | { [M in RepositoryMutationMethod]: Readonly<{
      state:"prepared"; operationId:RepositoryOperationId; requestDigest:string;
      targetId:string; repositoryId:string; method:M;
    }> }[RepositoryMutationMethod]
  | { [M in RepositoryMutationMethod]: Readonly<{
      state:"applied"; operationId:RepositoryOperationId; requestDigest:string;
      targetId:string; repositoryId:string; method:M; outcome:MutationOutcome<M>;
    }> }[RepositoryMutationMethod];
```

The on-disk encoder/decoder switches exhaustively on `method`; it never casts a generic JSON result. JSON is canonicalized before SHA-256. The request digest includes method, identity, every path/revision, staged-source digest, and every semantic parameter, but excludes transport request ID. Before writing `prepared`, the helper resolves deterministic working-copy/preview paths, captures the exact bytes that will be committed for prepare/refresh/Keep, fsyncs them under the operation's private journal directory, and records the validated artifact basename, length, and digest. `resultContentSha256` is non-null only when the typed outcome publishes file bytes. Recovery opens artifacts descriptor-relatively beneath the journal directory with `O_NOFOLLOW`, verifies type/ownership/mode/length/digest, and never reconstructs a request from one path, an unordered revisions array, or timestamps.
- Frame boundary: no journal work starts until one newline-terminated frame passes UTF-8, size, JSON, identity, method, and parameter validation. Prepare boundary: fsync the staged content and `prepared` journal record plus both parent directories before changing the target. Commit boundary: descriptor-relative atomic rename plus target-parent fsync. Applied boundary: persist `resultRevision`/typed result and fsync the `applied` record before responding.
- On startup, resolve every `prepared` entry before accepting a repository hello: if the target already has the recorded result digest, mark applied; if expected revisions still match and staged bytes verify, finish the commit and mark applied; otherwise mark applied with a typed conflict/error outcome without overwriting current content. Never guess based on timestamps.

- [ ] **Step 1: Add deterministic native failpoints and end-to-end breakpoint tests**

Compile failpoints only into the native test binary. For every one of the seven methods—and explicitly for prepare, refresh, and Keep with all original/working-copy/preview paths—tests kill the helper at all boundaries:

1. Before a complete frame: status is `absent`, destination unchanged.
2. After complete frame validation but before durable prepare: status is `absent`, destination unchanged.
3. After durable prepare but before commit: status is `prepared`; restart recovery either completes the verified request once or returns its typed conflict.
4. After target rename/fsync but before applied marker: restart recognizes result bytes/revision and marks `applied` without a second write.
5. After applied marker but before response: reconnect plus `mutation.status` returns `applied` and the original result revision.

Run: `cd integrations/zotero && npx vitest run test/remote-draft-mutations.test.ts && make -C native remote-test`

Expected: FAIL because the helper has neither journal nor failpoint recovery and the SSH adapter cannot resolve outcome-unknown.

- [ ] **Step 2: Cover every mutator, deduplication, and identity partition**

For create file/directory, write, prepare, refresh preview, Keep, and remove preview, test success, revision conflict, same operation ID/same digest replay, same ID/different digest rejection, and lost response. Assert each public mutator returns only `applied`, `rejected`, or `outcome-unknown`; after the latter, the client retains that exact operation ID and maps `mutation.status` back to the same method's typed result/error without issuing a second mutation. Also prove an operation from target A cannot be queried/replayed under target B, and an operation for repository A cannot be queried/replayed for repository B even when operation ID/path match.

- [ ] **Step 3: Implement prepare/commit/applied journaling and startup recovery**

Use stable operation IDs generated once by the UI intent. `SshQLabRepository` returns `outcome-unknown` only after a complete request may have reached the helper and never silently retries with a new ID. A same-master repository-channel reopen queries status on that adapter; after master loss, the replacement adapter published by Remote Chat's reconnect transaction queries the same operation ID under the same target/repository identity. The disposed old adapter never reopens a channel. `LocalQLabRepository` exposes the same result/status unions so workspace code does not branch on transport kind.

- [ ] **Step 4: Run mutation, workspace, and real-helper tests green**

Run: `cd integrations/zotero && npx vitest run test/remote-draft-mutations.test.ts test/local-qlab-repository.test.ts test/ssh-qlab-repository.test.ts test/qmd-workspace.test.ts && make -C native remote-test`

Expected: PASS for all five breakpoints, all seven mutators, restart recovery, deduplication, cross-target/repository rejection, CAS conflict, and lost-response resolution.

- [ ] **Step 5: Refactor duplicated result handling and run the full supported Linux gate**

Run: `cd integrations/zotero && command -v zip && npm run check && npm test && npm run native:test && make -C native remote-test`

Expected: PASS on Linux after Slice-1 Task 0's PATH archive lookup and portable PTY changes. Do not run signed universal/XPI assembly in this step.

- [ ] **Step 6: Commit durable remote Draft mutations**

```bash
git add integrations/zotero/src/qlab-repository.ts integrations/zotero/src/local-qlab-repository.ts integrations/zotero/src/ssh-qlab-repository.ts integrations/zotero/test/local-qlab-repository.test.ts integrations/zotero/test/remote-draft-mutations.test.ts integrations/zotero/native/include/qlab_remote_protocol.h integrations/zotero/native/src/qlab_remote_helper.c integrations/zotero/native/tests/test_remote_helper.py
git commit -m "feat(zotero): journal remote Draft mutations"
```

### Task 5: Bind plugin, workspace, manifests, and Note reviews to adapter identity

**Files:**
- Modify: `integrations/zotero/src/repository-target.ts`
- Modify: `integrations/zotero/test/repository-target.test.ts`
- Modify: `integrations/zotero/src/repository-target-controller.ts`
- Modify: `integrations/zotero/test/repository-target-controller.test.ts`
- Modify: `integrations/zotero/src/plugin.ts`
- Modify: `integrations/zotero/src/qmd-workspace.ts`
- Modify: `integrations/zotero/src/note-draft-bridge.ts`
- Modify: `integrations/zotero/src/codex-service.ts`
- Modify: `integrations/zotero/src/research-actions.ts`
- Modify: `integrations/zotero/src/sidebar.ts`
- Modify: `integrations/zotero/test/plugin-state.test.ts`
- Modify: `integrations/zotero/test/qmd-workspace.test.ts`
- Modify: `integrations/zotero/test/note-draft-bridge.test.ts`
- Modify: `integrations/zotero/test/codex-service.test.ts`
- Modify: `integrations/zotero/test/research-actions.test.ts`

**Interfaces:**
- Slice-3 SSH capabilities become `{ chat:true, qmdRead:true, qmdWrite:true, terminal:false, preview:false, mainSiteSupported:false, externalEditor:false, promoteDraft:false }` only after `TargetSwitchRuntime.stage` opens B's bound repository adapter and its helper advertises the complete Task-2 method set/identity. A missing method makes stage fail. Stage also acquires and returns the held Note barrier alongside Remote Chat's held Codex barrier; it does not mutate or close A. The controller order is exactly `stage → persist → synchronous publish → disposeOld`: publication atomically swaps the target, Agent client, repository adapter, capability/sidebar state, and identity-bearing Codex context, then releases both barriers; only the post-publication `disposeOld` closes A. Any prepublication failure calls `disposeStaged`, which aborts/releases B's barriers and closes only B's repository/Agent/master graph. Do not add `prepareForPublish` or `rollbackPrepared` hooks.
- Plugin Draft/QMD code receives the active `QLabRepository`; no Draft-path `IOUtils`, `PathUtils`, Gecko scanner, or local working-copy callback remains in `plugin.ts`, `qmd-workspace.ts`, or `note-draft-bridge.ts`.
- The local profile manifest filename is `sha256(targetId + "\0" + repositoryId + "\0" + originalDraftPath) + ".json"`. Its payload stores `{ schemaVersion, targetId, repositoryId, originalPath, originalRevision, workingCopyPath, workingCopyRevision, previewPath, operationId }`; it never stores remote source text, local repository root as remote identity, credentials, or helper paths.
- Every pending Note proposal captures `adapterIdentity`, QMD path, and QMD revision at proposal time:

```ts
interface PendingNoteExport {
  // existing review/note fields
  adapterIdentity: RepositoryAdapterIdentity;
  qmdPath: DraftQmdPath;
  qmdRevision: Revision;
}
```

Before `resolveReview(..., "accept")`, re-read `activeRepository.state()` and the QMD revision; require exact target ID, epoch, host instance, repository ID, path, and revision. Reject a stale tool completion or review without writing a Note, link, Draft, manifest, or repository file.

Preserve Fix Pack B's serialized boundaries. `NoteDraftBridgeService.resolveQueue` remains the only Note-review queue: target stage enqueues barrier acquisition behind every already-running review and returns the held barrier in the staged target graph; later Note operations remain queued while it is held. Synchronous publish swaps the active repository identity and releases the barrier; `disposeStaged` aborts/releases it. Proposal creation captures identity before QMD read and rechecks immediately before adding `pending`; accepted review revalidation occurs inside `runResolveReview`, after it reaches `resolveQueue`, not before enqueue. A review queued behind publication therefore rejects stale before any Note/link write.

Make Codex context APIs identity-bearing without bypassing Fix Pack B's `paperTransition`: `setActiveDocument({ repositoryIdentity, relativePath, editablePath })` validates branded paths and the currently bound target; `CodexWorkspaceObject` gains `repositoryIdentity`, and `setWorkspaceObject` captures/rechecks it in its queued transition. Remote context contains canonical remote paths only. Target publication clears the old active document/workspace object before releasing the Codex barrier; an old queued context callback cannot attach A's Draft to B's resumed conversation.

- [ ] **Step 1: Write stale callback, manifest partition, and capability red tests**

Tests must cover: same relative path on two targets; same alias reconnected with a new epoch; same host with two repository IDs; delayed tool proposal after switch; proposal switching between read and pending insertion; accepted review queued behind target publication; stage waiting for an already-resolving review; QMD revision changed while review is open; manifest lookup under the wrong target/repository; stale `setActiveDocument`; stale `setWorkspaceObject` behind Fix Pack B's `paperTransition`; SSH External Editor and promotion clicks. Add controller transaction cases for repository-stage failure, persistence failure after both barriers are held, synchronous publication, staged disposal, and old-resource close failure. Assert exact `stage.resolve, persist.resolve, publish.sync, disposeOld` order; prepublication failure retains all of A and closes only B, while post-publication failure leaves B active/degraded and never resurrects A. Assert all stale cases throw a typed stale-adapter error and invoke zero Note/link/repository/local-fallback writes.

Run: `cd integrations/zotero && npx vitest run test/repository-target.test.ts test/repository-target-controller.test.ts test/plugin-state.test.ts test/qmd-workspace.test.ts test/note-draft-bridge.test.ts test/codex-service.test.ts test/research-actions.test.ts`

Expected: FAIL because Slice-2 capabilities still disable QMD, manifests are keyed by local root/path, and pending Note exports do not retain adapter identity/revision.

- [ ] **Step 2: Route every Draft operation through the captured repository adapter**

Replace the direct I/O block in `plugin.ts` with Task-1 calls. Workspace open/save/create/Visual Edit/prepare/preview-copy/Keep/remove must retain the adapter captured when the action began and validate `repository.state().identity` before applying results. Use Remote Chat's `SidebarState.repositoryTarget`, `onChooseRepositoryTarget`, lazy `attachWorkspace`, and `setWorkspaceOpen`; do not reintroduce Fix Pack B's removed root-only callback. Cached rows may remain visible while disconnected, but mutating controls remain disabled until the same identity returns ready.

- [ ] **Step 3: Partition manifests and harden Note/Draft proposals**

Migrate a version-1 local manifest only when its local target/repository/path can be proven from active Slice-1 identity; otherwise leave it inert and explain that it belongs to an unverified target. Do not reinterpret a legacy local manifest for SSH. Capture adapter identity/revision before generating a Note proposal and revalidate at pending insertion and inside the serialized accept closure. Register the held Note transition barrier in target stage so identity cannot change during an accepted write/compensation sequence.

- [ ] **Step 4: Run all Slice-3 integration tests green**

Run: `cd integrations/zotero && npx vitest run test/repository-target.test.ts test/repository-target-controller.test.ts test/plugin-state.test.ts test/qmd-workspace.test.ts test/note-draft-bridge.test.ts test/codex-service.test.ts test/research-actions.test.ts test/sidebar.test.ts`

Expected: PASS; remote QMD/Draft controls work through the broker, stale callbacks are inert, and remote promotion/External Editor stay visibly disabled.

- [ ] **Step 5: Run type/placeholder/security scans and platform-correct final gates**

Run on Linux:

```bash
cd integrations/zotero
! rg -n '\b(TODO|TBD|FIXME|placeholder)\b|as any|Record<string, unknown>' src/qlab-repository.ts src/local-qlab-repository.ts src/ssh-qlab-repository.ts src/remote-repository-protocol.ts
! rg -n 'IOUtils|PathUtils|geckoScanner' src/qmd-workspace.ts src/note-draft-bridge.ts
! rg -n 'prepareForPublish|rollbackPrepared|onChooseQLabRoot' src test
command -v zip
npm run check
npm test
npm run native:test
make -C native remote-test
```

Expected: all three `rg` commands return no matches; all supported Linux gates pass after Slice-1 Task 0. Do not run signed universal/XPI assembly on Linux.

Run on macOS after staging both verified Slice-2 remote artifacts:

```bash
cd integrations/zotero
test "$(uname -s)" = Darwin
command -v zip
npm run native:remote:stage -- --x86 "$RUNNER_TEMP/remote-x86" --arm64 "$RUNNER_TEMP/remote-arm64"
npm run native:test
npm run build
```

Expected: PASS; staging verifies both Slice-2 tuple artifacts before the macOS-only signed universal/XPI assembly, and the XPI contains both helpers plus their generated provenance manifest.

- [ ] **Step 6: Commit Slice-3 integration**

```bash
git add integrations/zotero/src/repository-target.ts integrations/zotero/src/repository-target-controller.ts integrations/zotero/src/plugin.ts integrations/zotero/src/qmd-workspace.ts integrations/zotero/src/note-draft-bridge.ts integrations/zotero/src/codex-service.ts integrations/zotero/src/research-actions.ts integrations/zotero/src/sidebar.ts integrations/zotero/test/repository-target.test.ts integrations/zotero/test/repository-target-controller.test.ts integrations/zotero/test/plugin-state.test.ts integrations/zotero/test/qmd-workspace.test.ts integrations/zotero/test/note-draft-bridge.test.ts integrations/zotero/test/codex-service.test.ts integrations/zotero/test/research-actions.test.ts integrations/zotero/test/sidebar.test.ts
git commit -m "feat(zotero): bind remote Draft workflows to repository identity"
```

## Spec Coverage Review

- Task 1 closes the adapter around state, explicit list/cursor, subscribe, all four read path brands, write/create/prepare/preview/Keep/remove/status, and deliberately omits process execution.
- Task 2 supplies one exhaustive per-method params/results/event union and matching C dispatch with no command escape hatch.
- Task 3 defines snapshot/cursor atomicity and exact gap, overflow, same-master restart, whole-target reconnect replacement, duplicate, and identity recovery behavior without remote polling or an adapter-local master reconnect.
- Task 4 records request digest, target/repository identity, result revision, and typed result across complete-frame/prepare/commit/applied boundaries, including restart, deduplication, and cross-identity tests.
- Task 5 partitions manifests by target+repository+path, captures Note proposal adapter identity/revision, preserves Fix Pack B's Note/Codex queues, rejects stale tool/review/context completions, and publishes only Slice-3 QMD capabilities in the exact controller transaction order.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-31-qlab-remote-draft-repository.md`. Execute only after Slice 1 and Remote Chat, using Subagent-Driven Development (recommended) or `superpowers:executing-plans`.
