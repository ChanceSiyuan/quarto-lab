# Zotero Fix Pack B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the v0.10.0 Zotero fixes so region capture targets the invoking Reader, hidden chat surfaces are revealed, stored-thread fallback is safe and transactional, and Visual Edit parity is measured in a real browser.

**Architecture:** Keep the existing source-driven editor, Reader capture pipeline, Workbench managers, and serialized `CodexService` transition queue. Add three narrow seams: an exact `ReaderCaptureTarget` that freezes the Reader instance and page index, one plugin-level visible-surface query, and a typed stored-thread resume operation whose missing/error result is shared by every reopen entry point.

**Tech Stack:** TypeScript 7; Zotero 9 plugin APIs; Vitest 4 with happy-dom; Playwright 1.61 Chromium; Quarto 1.9 with `--no-execute`; KaTeX 0.18.1; esbuild 0.28.

**Spec:** `docs/superpowers/specs/2026-07-31-zotero-fix-pack-b-design.md` (user-approved on 2026-07-31). Implement exactly; the Library Agent, AI Context, and Reading Context are separate later stages.

## Global Constraints

- Work only in `/home/chance/quarto-lab`, as required by `AGENTS.md`. The user explicitly authorized implementation in the current checkout; do not create a second checkout or worktree.
- The current Linux sandbox exposes `.git` read-only. Every task still ends with the intended commit command, but if `index.lock` cannot be created, preserve the working-tree changes, run `git diff --check`, and record the uncommitted range in the SDD ledger. Do not request escalation and do not push.
- Use vertical TDD slices: write one behavior test, run it and observe the expected failure, add the minimum production change, then rerun that focused test before starting the next behavior.
- Agreed public test seams are: the Reader toolbar user-event path; the composer-visible capture result; `CodexService.setPaper`, `switchThread`, `openGlobalThread`, and `openConversationForPaper`; production `QmdVisualEditor` output measured beside Quarto HTML; and Research Action button clicks through the plugin-created view.
- Tests assert user-visible behavior or exported module contracts. Do not add source-text grep tests for implementation details and do not assert only that a mock was called when a visible result can be asserted.
- Run commands from `integrations/zotero` unless a step says otherwise. Focused Vitest: `npx vitest run test/<file>.test.ts`. Linux gates are `npm run check` and `npm test`; attempt `npm run test:visual` and record the current seccomp Chromium-launch blocker without calling it a pass. Its non-skipped execution is deferred to macOS by user instruction.
- `npm run verify` invokes the macOS native toolchain. Its expected Linux stop at missing `xcrun` is not a test success and does not block this pack; never claim an XPI build on Linux.
- Preserve chat `newlineAsBreak: true`, chat KaTeX at `1.04em`, draft KaTeX, the existing Reader-focus/conversation-selection independence contract, and the ten-image cap.
- Do not edit `knowledge/`, `knowledge/_quarto.yml`, `public/knowledge/`, `src/app/page.tsx`, `src/app/globals.css`, or `src/app/layout.tsx`.
- No new dependency, network call, Zotero mutation capability, Library Agent scope, AI Context persistence, or Reading Context behavior.
- Release target is exactly `0.10.1`.

---

### Task 1: Freeze the invoking Reader/page target and replace the glyph icon

**Files:**
- Create: `integrations/zotero/assets/region-capture.svg`
- Modify: `integrations/zotero/src/reader-context.ts`
- Modify: `integrations/zotero/src/plugin.ts:1-35, 648-681, 807-822, 2366-2384, 2413-2418`
- Test: `integrations/zotero/test/reader-context.test.ts`
- Test: `integrations/zotero/test/plugin-state.test.ts:1438-1470`

**Interfaces:**
- Produces: immutable `ReaderCaptureTarget<TReader> = { reader, pageIndex, context }` plus `ReaderContextService.captureTargetFromHook`, strict `getActiveCaptureTarget`, `getCaptureTargetPageViewElement`, and `captureTargetRegionImage`.
- Produces: `ZoteroChatPlugin.acceptReaderCaptureTarget(event): Promise<ReaderCaptureTarget | null>` and `startRegionScreenshot(target: ReaderCaptureTarget): Promise<void>`.
- A capture target calls the adapter with its exact Reader handle and frozen page index; it never re-enters attachment-keyed `ensureSnapshot(context)`.

- [ ] **Step 1: Write the Reader-target regression red.** In `reader-context.test.ts`, accept Reader B at page index 8, retain the returned target, then change the active/cached page for the same attachment to page index 9. Assert target page-element lookup and region rendering still call the adapter with the exact Reader-B object and page index 8. Also assert `getActiveCaptureTarget()` returns `null` when `getActiveReaderHook()` returns `null`; it must not reuse `latestHook`.

- [ ] **Step 2: Run the Reader-target tests red.**

  ```bash
  npx vitest run test/reader-context.test.ts -t "freezes the exact Reader and page for region capture"
  ```

  Expected: missing target API.

- [ ] **Step 3: Add the target API minimally.** Export a readonly target type and construct it with `Object.freeze` after `acceptReaderHook(hook)` succeeds. `getActiveCaptureTarget()` queries `zotero.getActiveReaderHook()` directly and returns `null` without fallback. Exact page lookup/render methods call `getPdfPageElement(target.reader, target.pageIndex)` and `capturePdfPageRegion(target.reader, target.pageIndex, region)` directly. Keep the existing context-based methods for unrelated callers.

- [ ] **Step 4: Make the toolbar A/B regression red.** Mock `acceptReaderCaptureTarget` to return a literal Reader-B target and assert a click passes that exact object to `startRegionScreenshot`. Also assert the button contains an `<img alt="">`, retains title/ARIA text `Capture Region Screenshot (QLab)`, and no longer has `textContent === "⬚"`.

- [ ] **Step 5: Add the safe SVG asset and route both entry points.** Create `assets/region-capture.svg` with a 24×24 dashed selection rectangle and corner marks, no scripts, external references, text, or raster content. The toolbar freezes its event hook through `acceptReaderCaptureTarget`, applies `target.context` without changing conversation selection, then passes the target. The `capture-region` `@` action calls strict `readerContext.getActiveCaptureTarget()`; if null, report `Open a PDF before capturing a region screenshot`. Neither path reads `this.context`, `codex.getActiveReaderContext()`, `latestHook`, or an attachment cache to choose its target.

- [ ] **Step 6: Run focused and related tests green.**

  ```bash
  npx vitest run test/reader-context.test.ts test/plugin-state.test.ts test/region-capture.test.ts
  npm run check
  ```

- [ ] **Step 7: Record/commit the slice.**

  ```bash
  git diff --check
  git add integrations/zotero/assets/region-capture.svg integrations/zotero/src/reader-context.ts integrations/zotero/src/plugin.ts integrations/zotero/test/reader-context.test.ts integrations/zotero/test/plugin-state.test.ts
  git commit -m "fix(zotero): bind region capture to the invoking Reader"
  ```

---

### Task 2: Own one overlay and retain capture provenance

**Files:**
- Modify: `integrations/zotero/src/plugin.ts:200-260, 2366-2400, 3080-3100`
- Modify: `integrations/zotero/src/sidebar.ts:1288-1311`
- Test: `integrations/zotero/test/plugin-state.test.ts` in `Region screenshots (Design 3)`
- Test: `integrations/zotero/test/sidebar.test.ts` context-chip accessibility coverage
- Test: `integrations/zotero/test/region-capture.test.ts` only if disposer behavior needs a regression

**Interfaces:**
- Consumes: Task 1's required `startRegionScreenshot(target)` argument and `startRegionSelection(...): () => void` disposer.
- Produces: one plugin-owned `regionCaptureDispose` handle and a `PendingScreenshot` record with optional `source` provenance.

- [ ] **Step 1: Write the one-overlay failing test.** Start capture twice against the same mounted page and assert the first `.zc-region-overlay` is disconnected while exactly one new overlay remains:

  ```ts
  await plugin.startRegionScreenshot(target);
  const first = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;
  await plugin.startRegionScreenshot(target);
  const second = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;

  expect(first.isConnected).toBe(false);
  expect(second).not.toBe(first);
  expect(pageElement.querySelectorAll(".zc-region-overlay")).toHaveLength(1);
  ```

- [ ] **Step 2: Run it red.**

  ```bash
  npx vitest run test/plugin-state.test.ts -t "keeps only one region-selection overlay"
  ```

  Expected: two overlays remain because the plugin discards the disposer.

- [ ] **Step 3: Store and clear the disposer.** Add:

  ```ts
  private regionCaptureDispose: (() => void) | null = null;
  ```

  At capture start, call and clear the previous disposer. Store the new one.
  Both callbacks clear the handle only when it still identifies that selection:

  ```ts
  this.regionCaptureDispose?.();
  let dispose: (() => void) | null = null;
  dispose = startRegionSelection(pageElement, {
    onCancel: () => {
      if (this.regionCaptureDispose === dispose) this.regionCaptureDispose = null;
    },
    onComplete: (selection) => {
      if (this.regionCaptureDispose === dispose) this.regionCaptureDispose = null;
      void this.captureRegionScreenshot(selection, target);
    },
  });
  this.regionCaptureDispose = dispose;
  ```

  Call and clear it during plugin shutdown as well.

- [ ] **Step 4: Write the provenance test red.** Complete a Reader-B drag and inspect the real composer chip data through `interactionContextChips()`:

  ```ts
  expect(plugin.pendingScreenshots).toEqual([{
    image: "data:image/png;base64,region",
    kind: "region",
    source: {
      paperKey: "1-READER-B",
      paperTitle: "Paper B",
      pageIndex: 8,
      pageNumber: 9,
      pageLabel: "9",
    },
  }]);
  expect(plugin.interactionContextChips()).toEqual(expect.arrayContaining([
    expect.objectContaining({
      label: "Region · Paper B · p. 9",
      detail: "Captured from Paper B, PDF page 9",
    }),
  ]));
  ```

  Run and observe failure because pending screenshots currently contain only
  `{ image, kind }`.

- [ ] **Step 5: Add the narrow pending record and source formatter.** Keep the data URI transport unchanged:

  ```ts
  interface ScreenshotSource {
    paperKey: string;
    paperTitle: string;
    pageIndex: number;
    pageNumber: number;
    pageLabel: string;
  }

  interface PendingScreenshot {
    image: string;
    kind: "page" | "region";
    source?: ScreenshotSource;
  }
  ```

  Region completion derives literals from `target.context`; it does not re-read
  plugin/Codex context or the Reader-context snapshot cache. The chip uses
  `pageLabel || pageNumber` and CSS handles truncation. For removable chips,
  retain the remove action in `aria-label` while including `chip.detail` in the
  title/accessible description so full provenance is inspectable. `sendChat`
  continues mapping only `shot.image`.

- [ ] **Step 6: Run the vertical slice and typecheck.**

  ```bash
  npx vitest run test/plugin-state.test.ts test/region-capture.test.ts
  npm run check
  ```

- [ ] **Step 7: Record/commit the slice.**

  ```bash
  git diff --check
  git add integrations/zotero/src/plugin.ts integrations/zotero/test/plugin-state.test.ts integrations/zotero/test/region-capture.test.ts
  git commit -m "fix(zotero): own region overlays and label their source"
  ```

---

### Task 3: Distinguish visible chat surfaces from retained hidden views

**Files:**
- Modify: `integrations/zotero/src/plugin.ts` capture completion, page observer, float auto-open, Workbench/sidebar lookup, and chat-error helpers
- Test: `integrations/zotero/test/plugin-state.test.ts`
- Test: `integrations/zotero/test/plugin-helpers.test.ts` only if policy terminology changes

**Interfaces:**
- Consumes: exact Workbench tab selection (`Zotero_Tabs.selectedID`), standalone manager `isActive/window/currentView`, float host plus `view.isVisible`, and an actual mounted chat view below the expanded selected Reader sidebar.
- Produces: private discriminated `VisibleChatSurface`, `selectedWorkbenchEntry`, intentional-reuse-only `existingWorkbenchEntry`, `visibleFloatSurface`, and `visibleChatSurface(win?)`; `ensureCaptureChatSurface()` reveals Workbench only when that query returns null.

- [ ] **Step 1: Write the host-predicate matrix red.** Exercise the private query structurally through `plugin-state.test.ts`:

  - connected Workbench host qualifies only when its exact ID is selected;
  - standalone qualifies only when its window is open, document-visible,
    non-minimized when Gecko exposes `windowState`, its known host is connected,
    and a view exists;
  - float qualifies only when its target-window host is connected and
    `isVisible()` is true;
  - Reader sidebar qualifies only when the supplied window's selected tab is a
    Reader, `item-details[data-tab-id]` matches the selected ID, the body and
    mapped `SidebarView` are connected, and `collapsible-section[open]` owns it;
  - an active hidden/minimized standalone excludes the covered/detached Reader
    sidebar; priority is Workbench → standalone → float → sidebar.

- [ ] **Step 2: Run it red.**

  ```bash
  npx vitest run test/plugin-state.test.ts -t "classifies only visible chat surfaces"
  ```

  Expected: missing query or retained-entry fallbacks fail the matrix.

- [ ] **Step 3: Implement the single visibility query.** Use this shape:

  ```ts
  type VisibleChatSurface = {
    kind: "workbench" | "standalone" | "float" | "reader-sidebar";
    focusComposer(text?: string): void;
  };
  ```

  The query implements the matrix above. Wrap `focusComposer` so host view
  methods retain their receiver. Parse Reader type through the supplied
  window's `Zotero_Tabs.parseTabType`, not a global main-window helper. It never
  falls back to the first Workbench entry, a map-resident/disconnected float,
  or the first connected/collapsed/background sidebar. Keep
  `existingWorkbenchEntry()` solely for explicit open/reuse; after an explicit
  open, inspect only the selected entry.

- [ ] **Step 4: Write the hidden-Workbench capture test red.** Retain a
  connected Workbench entry while a Reader ID is selected. The
  `openResearchChat` mock must emulate production by changing `selectedID` to
  the retained Workbench ID before resolving. Assert the view is not focused
  before selection, is focused after reveal/render, and no duplicate entry is
  created. A no-op open mock is invalid because the reveal helper must re-query
  and reject when selection did not change.

- [ ] **Step 5: Route capture success and render error through one reveal helper.** Add:

  ```ts
  private async ensureCaptureChatSurface(): Promise<VisibleChatSurface> {
    const visible = this.visibleChatSurface();
    if (visible) return visible;
    await this.openResearchChat(undefined, false);
    const opened = this.visibleChatSurface();
    if (!opened) throw new Error("Unable to reveal the QLab Workbench");
    return opened;
  }
  ```

  Split data capture from `finishRegionScreenshot`. On success: append/clear
  error, ensure a surface, render, then focus the exact returned surface. On
  crop/null-image failure: append nothing, ensure a surface, route the original
  error through a narrow chat-error reporter even when global pane mode is
  terminal, then focus the same surface. An outer catch handles reveal failure.
  Cancellation never calls this helper.

- [ ] **Step 6: Add success, error, and cancellation tests.** Cover hidden
  Workbench reveal, an already-visible connected float (no Workbench open),
  rejected `captureTargetRegionImage`, and a null image. Error cases leave
  `pendingScreenshots` empty, preserve the original message in `chatError`, and
  focus only after error render. Drive Escape and a too-small drag through the
  real overlay and assert no crop/reveal/render/focus/error path runs.

- [ ] **Step 7: Use the same predicate for other visibility decisions.** The
  page-change observer checks `visibleChatSurface()` rather than retained
  Workbench/map membership. Visibility-sensitive focus paths use the returned
  surface, not `activeChatView()`. Preserve `existingWorkbenchEntry()` only in
  explicit Workbench open/reuse paths. State synchronization may continue to
  render retained views.

- [ ] **Step 8: Use the same predicate for running-turn float decisions.** In
  `maybeAutoOpenFloatForRunningTurn`, pass `hasConnectedViews: true` only when
  `visibleChatSurface(win)` returns a non-float surface; `floatVisible` comes
  from the exact connected-host float predicate. A retained unselected
  Workbench, collapsed/background sidebar, hidden/minimized standalone, or
  disconnected float must not suppress the float. Before `ensureFloatPanelOpen`
  returns/reuses an entry, destroy and delete a disconnected stale float so the
  approved auto-open can actually remount it.

- [ ] **Step 9: Run focused and related suites.**

  ```bash
  npx vitest run test/plugin-state.test.ts test/plugin-helpers.test.ts test/float-panel.test.ts test/workbench-tab.test.ts test/standalone-workbench.test.ts test/region-capture.test.ts
  npm run check
  ```

- [ ] **Step 10: Record/commit the slice.**

  ```bash
  git diff --check
  git add integrations/zotero/src/plugin.ts integrations/zotero/test/plugin-state.test.ts
  git commit -m "fix(zotero): reveal chat only from visible surfaces"
  ```

---

### Task 4: Classify stored-thread resume results at one boundary

**Files:**
- Create: `integrations/zotero/src/stored-conversation-resume.ts`
- Create: `integrations/zotero/test/stored-conversation-resume.test.ts`

**Interfaces:**
- Consumes: `Pick<AgentClient, "threadResume" | "threadRead">`, `ThreadResumeParams`, `CodexRpcError`, `CodexRequestTimeoutError`, and `CodexDisconnectedError`.
- Produces: `StoredConversationResumeResult`, `resumeStoredThread(client, params): Promise<{ kind: "resumed"; threadId: string } | { kind: "missing" }>`, and `isMissingStoredThreadError(error): boolean`.

- [ ] **Step 1: Write classifier tests before the module.** Cover these literal cases:

  ```ts
  const rpcMissing = new CodexRpcError(
    { code: -32602, message: "thread not found" },
    "thread/resume",
    7,
  );
  expect(isMissingStoredThreadError(rpcMissing)).toBe(true);
  expect(isMissingStoredThreadError(new Error("thread not found"))).toBe(true);
  expect(isMissingStoredThreadError(new Error("thread resume failed"))).toBe(false);
  expect(isMissingStoredThreadError(new CodexRequestTimeoutError("thread/resume", 30_000, 8))).toBe(false);
  expect(isMissingStoredThreadError(new CodexDisconnectedError())).toBe(false);
  expect(isMissingStoredThreadError(new CodexRpcError(
    { code: -32603, message: "authentication required" }, "thread/resume", 9,
  ))).toBe(false);
  expect(isMissingStoredThreadError(new CodexRpcError(
    { code: -32602, message: "thread not found" }, "thread/read", 10,
  ))).toBe(false);
  ```

- [ ] **Step 2: Run red.**

  ```bash
  npx vitest run test/stored-conversation-resume.test.ts
  ```

  Expected: module/import missing.

- [ ] **Step 3: Implement a narrow matcher.** The checked-in protocol fixtures
  do not establish a structured missing-thread code/data signature, so do not
  invent one. A `CodexRpcError` requires `method === "thread/resume"` and an
  exact normalized whole message `thread not found` or
  `conversation not found`. The compatibility branch accepts those same exact
  whole messages on a plain `Error`; it does not use substring matching.
  Timeout and disconnect types return false before message matching. Add a data
  tag only if implementation work first adds an observed backend fixture that
  proves that exact signature.

- [ ] **Step 4: Test the async resume boundary.** Add three behavior tests:

  ```ts
  await expect(resumeStoredThread(clientWithMissingResume, params))
    .resolves.toEqual({ kind: "missing" });
  await expect(resumeStoredThread(clientWithTimeout, params)).rejects.toBe(timeout);
  await expect(resumeStoredThread(clientWithReadFailure, params)).rejects.toBe(readFailure);
  ```

  In the success case assert the returned id comes from authoritative
  `threadRead`, and `threadRead` receives the id returned by `threadResume`.

- [ ] **Step 5: Implement the operation with the catch around resume only.**

  ```ts
  export async function resumeStoredThread(
    client: Pick<AgentClient, "threadResume" | "threadRead">,
    params: ThreadResumeParams,
  ): Promise<StoredConversationResumeResult> {
    let resumed: ThreadResumeResponse;
    try {
      resumed = await client.threadResume(params);
    }
    catch (error) {
      if (isMissingStoredThreadError(error)) return { kind: "missing" };
      throw error;
    }
    const read = await client.threadRead(resumed.thread.id, true);
    return { kind: "resumed", threadId: read.thread.id };
  }
  ```

- [ ] **Step 6: Run green and typecheck.**

  ```bash
  npx vitest run test/stored-conversation-resume.test.ts
  npm run check
  ```

- [ ] **Step 7: Record/commit the slice.**

  ```bash
  git diff --check
  git add integrations/zotero/src/stored-conversation-resume.ts integrations/zotero/test/stored-conversation-resume.test.ts
  git commit -m "fix(zotero): classify missing stored conversations narrowly"
  ```

---

### Task 5: Make every stored-conversation entry point transactional

**Files:**
- Modify: `integrations/zotero/src/codex-service.ts:1-25, 552-610, 790-950, 1850-1930`
- Test: `integrations/zotero/test/codex-service.test.ts:1530-1685` and the existing focus/selection contract around `:529-598`

**Interfaces:**
- Consumes: Task 4's `resumeStoredThread`; existing public methods `setPaper`, `switchThread`, `openGlobalThread`, and `openConversationForPaper`.
- Produces: private shared `openStoredConversation`, `commitResumedConversation`, `archiveMissingStoredThread`, and selected/session-state snapshot/rollback helpers. No new public service method. The `AgentClient` may already have ingested resume/read data into `ThreadStore`; that cache, Reader-focus caches, and transient switching flags are outside the rollback promise.

- [ ] **Step 1: Add the operational-failure table test red.** For
  `openConversationForPaper`, run cases for timeout, disconnect, auth RPC,
  generic error, `threadRead` rejection, and `saveSessions` rejection. For each
  case assert the original rejection identity/message, zero `threadStart`
  calls, unchanged `sessions.papers["1-SECOND"]`, unchanged History, and
  unchanged `state.activeThreadId`.

  The save case uses a successful resume/read and:

  ```ts
  internal.saveSessions = vi.fn(async () => {
    throw new Error("profile is read-only");
  });
  await expect(service.openConversationForPaper("1-SECOND"))
    .rejects.toThrow("profile is read-only");
  expect(internal.sessions.papers["1-SECOND"].threadId).toBe("thread-b");
  expect(service.state.activeThreadId).toBeNull();
  ```

- [ ] **Step 2: Run the new table red.**

  ```bash
  npx vitest run test/codex-service.test.ts -t "preserves a stored conversation on operational resume failures"
  ```

  Expected: at least the resume-error cases start `thread-new`, and save/read
  failures leave partial active/session state.

- [ ] **Step 3: Add state staging helpers.** Clone only the conversation-owned
  branches before mutation while preserving unrelated checkpoint/anchor/evidence
  objects:

  ```ts
  function cloneConversationSessions(source: SessionFile): SessionFile {
    return {
      ...source,
      papers: Object.fromEntries(Object.entries(source.papers).map(([key, value]) => [key, { ...value }])),
      history: source.history
        ? Object.fromEntries(Object.entries(source.history).map(([key, records]) => [key, records.map((record) => ({ ...record }))]))
        : undefined,
      openThreads: source.openThreads ? [...source.openThreads] : undefined,
    };
  }
  ```

  Change `saveSessions()` to accept `next: SessionFile = this.sessions`, writing
  the passed value. `commitResumedConversation` builds `next`, deduplicates the
  prior/current History records (including both requested and canonical IDs),
  writes the authoritative `threadRead` ID into the next default, opens that ID
  in `next.openThreads`,
  awaits `saveSessions(next)`, and only then assigns `this.sessions`,
  `activeContext`, `activePaperKey`, `state.activeThreadId`, and
  `threadPaperKeys`.

- [ ] **Step 4: Add rollback around missing→fresh creation.** Snapshot
  `sessions`, active context/key/id, and `threadPaperKeys` before the operation;
  restore those conversation-owned values on any thrown error, then call
  `syncActiveTurnState()` so derived `activeTurnId`/`running` match the restored
  active thread. Do not claim to
  roll back `AgentClient`'s `ThreadStore`, `focusedContext`, `focusedPaperKey`,
  a successfully seeded `paperContexts` entry, or transient switching flags.
  A backend thread started before a local save failure can remain as an
  unselected orphan, but must never become the selected or persisted thread.

  `archiveMissingStoredThread(paperKey, record)` deduplicates the selected
  record into History and deletes `sessions.papers[paperKey]` only when that
  exact thread is the current default. When the missing record came from
  History and a different default exists for the same paper, archive/dedupe
  that default as well before replacing it, so the fresh thread becomes the
  sole default. The helper does not save by itself; the subsequent fresh-thread
  save persists the archive and new pointer atomically.

- [ ] **Step 5: Route every stored-conversation entry point through one helper.**
  `openStoredConversation(paperKey, context, selected, options?)` owns this
  branch shape inside the serialized transition, and all four entry paths call
  it rather than duplicating policy:

  ```ts
  const result = await resumeStoredThread(this.requireClient(), {
    threadId: selected.threadId,
    ...this.threadModeSettings(context),
  });
  if (result.kind === "missing") {
    this.archiveMissingStoredThread(paperKey, selected);
    await this.newThreadInternal(context, paperKey);
    return;
  }
  await this.commitResumedConversation(paperKey, context, selected, result.threadId);
  ```

  `openGlobalThread` first converts its selected History option to the same
  `SessionRecord` shape. Remove its separate resume/read/mutate/save sequence.
  Split it into a public queueing wrapper plus `openGlobalThreadInternal`, in
  the same form as `switchThread`, so it also runs through
  `enqueuePaperTransition`. Its current "keep prior active tab open" mutation
  must be staged in candidate `openThreads` and published only after
  persistence; a timeout must leave open tabs unchanged. No caller—including
  `openConversationForPaperInternal`—catches a thrown operational error and
  converts it to `missing`.

- [ ] **Step 6: Make the explicit-missing tests use method-scoped evidence.**
  Replace the untyped fixture with a `CodexRpcError` carrying the exact message
  `thread not found` from `thread/resume` (no invented data tag). Assert the old
  record remains once in History and exactly one fresh thread is started. Add
  local/global History cases: the missing selected History record is preserved;
  any different current default for that paper is also preserved/deduped in
  History; and the fresh record becomes the sole paper default.

- [ ] **Step 7: Prove all entry points share policy.** Add a table over:

  ```ts
  [
    ["setPaper", () => service.setPaper(reopeningContext())],
    ["switchThread", () => service.switchThread("thread-b")],
    ["openGlobalThread", () => service.openGlobalThread("thread-b")],
    ["openConversationForPaper", () => service.openConversationForPaper("1-SECOND")],
  ] as const
  ```

  Each receives the same timeout fixture and must reject without calling
  `threadStart`, replacing the pointer, or changing `openThreads`. Use the
  complete `AgentClient`-shaped test fixture already established by the suite;
  mock only backend I/O. Add a successful resume whose `threadRead` returns a
  canonical ID different from the requested ID and assert that canonical ID is
  persisted, mapped, opened, and selected.

- [ ] **Step 8: Run focused service tests, then the independence regression.**

  ```bash
  npx vitest run test/codex-service.test.ts
  npm run check
  ```

  Expected: the whole service suite passes, including the unchanged Reader
  focus/conversation selection contract.

- [ ] **Step 9: Record/commit the slice.**

  ```bash
  git diff --check
  git add integrations/zotero/src/codex-service.ts integrations/zotero/test/codex-service.test.ts
  git commit -m "fix(zotero): make stored conversation resume transactional"
  ```

---

### Task 6: Measure Preview and Visual Edit parity in Chromium

**Files:**
- Create: `integrations/zotero/test/fixtures/visual-edit-parity.qmd`
- Modify: `integrations/zotero/test/visual/render-harness.mjs`
- Create: `integrations/zotero/test/visual/draft-parity.test.mjs`
- Modify only if the browser test exposes a real mismatch: `integrations/zotero/src/styles.css` or the existing Visual Edit `newlineAsBreak: false` call sites

**Interfaces:**
- Consumes: production `QmdVisualEditor`, production `styles.css`, bundled KaTeX CSS, and Quarto invoked with `--no-execute`.
- Produces: `renderDraftParity({ source, width }): Promise<{ preview, visual }>` returning independently measured typography, normalized formula boxes, effective text, content width, and line counts.

- [ ] **Step 1: Add the controlled QMD fixture.** Use exactly one soft-wrapped
  paragraph, one long naturally wrapped paragraph, inline math, and display
  math; frontmatter disables execution and selects KaTeX:

  ```qmd
  ---
  title: "Visual parity fixture"
  format:
    html:
      html-math-method: katex
      toc: false
  execute:
    enabled: false
  ---

  A soft-wrapped sentence keeps the transition amplitude $A = \Omega / \Delta$
  on one flowing paragraph even though its source uses a newline.

  This deliberately long paragraph checks that equal content widths produce the same natural wrapping across both draft surfaces without inserting an authored hard break into the prose.

  $$
  P_e = \left(\frac{\Omega}{\Delta}\right)^2.
  $$
  ```

- [ ] **Step 2: Write the browser contract.** The test asserts:

  ```js
  assert.ok(Math.abs(preview.bodyFontSize - visual.bodyFontSize) <= 1);
  assert.ok(Math.abs(preview.lineHeight - visual.lineHeight) <= 1);
  assert.ok(Math.abs(preview.contentWidth - visual.contentWidth) <= 1);
  assert.ok(Math.abs(preview.inlineMathHeight - visual.inlineMathHeight) <= 1);
  assert.ok(Math.abs(preview.displayMathHeight - visual.displayMathHeight) <= 1);
  assert.equal(visual.softBreakContainsBr, false);
  assert.equal(preview.softBreakText, visual.softBreakText);
  assert.equal(preview.softBreakLineCount, visual.softBreakLineCount);
  assert.equal(preview.naturalWrapLineCount, visual.naturalWrapLineCount);
  ```

  Text values are normalized only for whitespace; expected prose comes from
  literal fixture strings, not from the production renderer.

- [ ] **Step 3: Run the test before adding the harness function.**

  ```bash
  node --test test/visual/draft-parity.test.mjs
  ```

  Expected initial failure: `renderDraftParity` is not exported. This is test
  infrastructure red before any browser process starts; no production code
  changes yet. Use the direct file because the package script expands the
  existing visual test too and would obscure this import-contract failure.

- [ ] **Step 4: Implement the production-backed harness.** It must:

  1. create a temporary directory with `mkdtemp`;
  2. invoke `quarto render <fixture> --no-execute --output-dir <temp>` with
     `execFile`/`spawn`, never a shell string;
  3. open the generated HTML in Playwright at a fixed 1200×900 viewport and
     measure its production content column rather than forcing a test width;
  4. intercept every Quarto-emitted KaTeX CDN request and fulfill it from the
     installed KaTeX 0.18.1 package, including stylesheet/script/font assets;
     make no network request;
  5. bundle a tiny in-memory browser entry importing the real
     `QmdVisualEditor` with the installed esbuild API;
  6. serve a second page from a routed virtual HTTPS origin whose linked
     `/plugin.css`, `/katex/katex.min.css`, and `/katex/fonts/*` responses are
     fulfilled from the literal production stylesheet and installed package;
  7. instantiate `QmdVisualEditor`, call `setDocument({ source, revision:
     "fixture" }, false)`, and measure actual DOM ranges;
  8. wait for `.katex` on both surfaces and `document.fonts.ready` before any
     geometry measurement;
  9. count unique rounded top coordinates from non-empty `Range.getClientRects()`
     as text line count;
  10. remove the temporary directory in `finally` and close both pages.

  Never write generated HTML under `public/knowledge/` or commit it.

- [ ] **Step 5: Run the completed browser test.**

  ```bash
  npm run test:visual -- --test-name-pattern="Preview and Visual Edit"
  ```

  If the assertions pass, make no production styling change: v0.10.0 already
  contains the Fix Pack A style implementation and this task adds the missing
  real-browser guard. If a parity assertion fails, keep that observed test red
  and make the minimum change only in `.zc-qmd-visual-editor`,
  `.zc-qmd-visual-block`, or the existing Visual Edit renderer option that
  directly explains the measurement; rerun until green. Do not weaken the
  one-pixel or equal-line-count contract.

- [ ] **Step 6: Re-run unit invariants and the full visual suite.**

  ```bash
  npx vitest run test/markdown.test.ts test/qmd-visual-editor.test.ts test/build-assets.test.ts test/draft-preview-math.test.ts
  npm run test:visual
  npm run check
  ```

  Chromium tests must execute, not skip, before macOS acceptance. In the
  current Linux container, a raw launch first lacks `libatk-1.0.so.0`; with the
  available local browser-library path supplied it reaches the sandbox-host
  seccomp denial. Retain both exact environment diagnostics as deferred
  evidence rather than weakening/skipping the contract or claiming a pass.

- [ ] **Step 7: Record/commit the slice.**

  ```bash
  git diff --check
  git add integrations/zotero/test/fixtures/visual-edit-parity.qmd integrations/zotero/test/visual/render-harness.mjs integrations/zotero/test/visual/draft-parity.test.mjs integrations/zotero/src/styles.css
  git commit -m "test(zotero): measure Visual Edit parity in Chromium"
  ```

  Omit `src/styles.css` from `git add` when no measured production change was
  required.

---

### Task 7: Lock original entry points, document hardening, and release v0.10.1

**Files:**
- Modify: `integrations/zotero/test/plugin-research-actions.test.ts`
- Modify: `integrations/zotero/test/plugin-state.test.ts` only for any missing library/History reopen assertion
- Modify: `integrations/zotero/README.md`
- Modify: `integrations/zotero/CHANGELOG.md`
- Modify: `integrations/zotero/package.json`
- Modify: `integrations/zotero/package-lock.json` (root package metadata only)
- Modify: `integrations/zotero/manifest.json`

**Interfaces:**
- Consumes: plugin-created `SidebarView` callbacks, existing research prompt builders, and public paper-chat open commands.
- Produces: no new runtime API; release metadata is exactly `0.10.1`.

- [ ] **Step 1: Expand the real plugin click regression.** Render three named
  actions and click each actual `.zc-research-action` button. Keep
  `runResearchAction` real; stub only the backend-send boundary and supply a
  literal PDF research object, configured QLab root, active thread, and one
  additional `ConversationPaper` so Compare Papers is valid. Assert each click
  reaches `sendChat` with a non-empty, action-specific prompt and the expected
  read-only option:

  ```ts
  const sent = plugin.sendChat.mock.calls;
  expect(sent).toHaveLength(3);
  expect(sent.map(([prompt]: [string]) => prompt.trim().length > 0))
    .toEqual([true, true, true]);
  expect(sent[0][0]).toContain("Research Loop Action: summarize");
  expect(sent[1][1]).toEqual({ readOnly: true });
  expect(sent[2][0]).toContain("Research Loop Action: compare-papers");
  ```

  Mount a second view through the same `createWorkbenchView` factory in a
  standalone-window document and repeat one click there. The production change
  this catches is removing the callback from the shared factory, which would
  make both surfaces silently no-op.

- [ ] **Step 2: Run the action regression.**

  ```bash
  npx vitest run test/plugin-research-actions.test.ts test/research-actions.test.ts test/sidebar.test.ts
  ```

  It may already pass after Fix Pack A; that is expected for a retained
  capability and requires no manufactured runtime change.

- [ ] **Step 3: Re-run no-open-PDF entry points.** Ensure existing tests cover
  the library item menu, local conversation tab, local History, and global
  History background seeding. Add only the absent public-entry assertion; all
  must verify `openInBackground: true`, unchanged foreground tab selection, and
  visible no-PDF error without state mutation.

  ```bash
  npx vitest run test/plugin-state.test.ts test/codex-service.test.ts
  ```

- [ ] **Step 4: Update user documentation.** In `README.md`, replace the region
  button description with "dashed selection rectangle", state that the chip
  identifies source paper/page, and state that a hidden Workbench is selected
  after success or render error. Keep full-page capture instructions and the
  ten-image/removal semantics.

- [ ] **Step 5: Add the 0.10.1 changelog entry.** Record exactly the four
  externally meaningful changes: exact Reader targeting/provenance, visible
  Workbench reveal, narrow transactional resume fallback, and browser-measured
  Visual Edit parity. Mention that Research Actions and no-open-PDF reopening
  are regression-locked, not new features.

- [ ] **Step 6: Bump every plugin package root to `0.10.1`.** Update
  `package.json`, `manifest.json`, and both root version fields at lines 3 and 9
  of `package-lock.json`. Do not alter dependency versions.

- [ ] **Step 7: Run Linux completion gates.**

  ```bash
  npm run check
  npm test
  npm run test:visual
  ```

  Expected on Linux: TypeScript clean and all Vitest tests pass. Attempt the
  Playwright command without adding a skip; record the current Chromium
  sandbox-host/seccomp launch failure and defer its non-skipped pass to macOS.
  Then run `npm run verify` once to record the expected Linux native toolchain
  stop; do not describe either command as green unless it actually completes.

- [ ] **Step 8: Inspect scope and generated-tree safety.** From repo root:

  ```bash
  git diff --check
  git status --short
  git diff --stat
  git diff -- knowledge knowledge/_quarto.yml public/knowledge src/app/page.tsx src/app/globals.css src/app/layout.tsx
  ```

  Expected: the final command has no output.

- [ ] **Step 9: Record/commit the release slice.**

  ```bash
  git add integrations/zotero/README.md integrations/zotero/CHANGELOG.md integrations/zotero/package.json integrations/zotero/package-lock.json integrations/zotero/manifest.json integrations/zotero/test/plugin-research-actions.test.ts integrations/zotero/test/plugin-state.test.ts
  git commit -m "chore(zotero): release 0.10.1 hardening pack"
  ```

## Final review and handoff

- Run a whole-pack spec/code review against
  `docs/superpowers/specs/2026-07-31-zotero-fix-pack-b-design.md`.
- Fix Critical/Important findings through the same red-green loop and rerun
  their covering suites.
- Report every Linux command and result, the `.git` read-only limitation, and
  the exact files changed.
- Do not claim native completion. Hand off this macOS checklist: full
  `npm run verify`, XPI build/install, Reader A/B capture, Workbench reveal,
  Visual Edit comparison, restart with no PDFs, and reopen from History/item
  menu.
