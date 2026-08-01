# Zotero Plugin Fix Pack B — Hardening Design Spec

- **Date:** 2026-07-31
- **Status:** Approved by user; implementation in progress
- **Target:** `integrations/zotero` — "Research Loop — Local Codex for Zotero", v0.10.0 → v0.10.1
- **Development host:** Linux; native Zotero/XPI validation is explicitly deferred to macOS

Unless prefixed otherwise, file references below are relative to
`integrations/zotero/` (for example, `src/plugin.ts`).

## Overview

Fix Pack A is present in the current checkout at v0.10.0. It added the four
requested user-facing capabilities: live Research Action chips, Visual Edit
parity work, region screenshots, and reopening paper conversations without an
already-open PDF. A post-implementation review found three correctness defects
in those paths:

1. A region capture started from Reader B can capture Reader A when A owns the
   selected conversation.
2. A hidden Workbench tab can be treated as a visible chat surface, preventing
   the UI from being revealed after capture.
3. Any stored-thread resume error can be mistaken for a deleted thread, causing
   a timeout, disconnect, authentication failure, read failure, or persistence
   failure to silently create a new conversation.

Fix Pack B closes those defects and turns the user's original four requests
into observable regression contracts. It also replaces the ambiguous region
capture glyph with a discoverable icon and adds a real-browser parity test for
the exact Visual Edit properties promised to the user.

This is a narrow hardening release, not the library-level agent. The Library
Agent, AI Context attachments, and Reading Context workflow remain the next
three separately designed stages.

## Goals

1. Region capture always uses the Reader and page from which the capture was
   invoked, independently of the selected AI conversation.
2. "Visible chat" means a surface the user can actually see. A successful or
   failed region render reveals a native QLab Workbench when none is visible.
3. Only an explicit missing-thread response may replace a stored conversation
   with a fresh one. Operational failures remain visible and preserve state.
4. Visual Edit and HTML Preview have equivalent formula scale, body typography,
   soft-break behavior, and natural wrapping at the same viewport width.
5. Research Action chips and paper-chat reopening remain live through tests of
   their real plugin entry points rather than callback-only unit tests.

## Non-goals

- No library-wide conversation scope or library mutation tools.
- No AI Context attachment, shared attachment projection, reading plan, or
  durable learning-memory model.
- No change to the separation between Reader focus and selected conversation.
- No full-page pixel equality between Visual Edit and HTML Preview.
- No replacement of the source-driven Visual Edit implementation with an
  embedded compiled-HTML editor.
- No change to chat Markdown's explicit newline behavior.
- No change to `knowledge/`, `knowledge/_quarto.yml`, `public/knowledge/`, or
  the repository trust boundary.
- No native XPI build claim from Linux and no push as part of this work.

## Evidence in the v0.10.0 checkout

### Region target can drift

The Reader toolbar handler calls `acceptReaderHook(event)` and then discards
the accepted context before calling `startRegionScreenshot()`
(`src/plugin.ts:676-678`). `startRegionScreenshot()` independently prefers
`codex.getActiveReaderContext()` (`src/plugin.ts:2368-2373`). When the selected
conversation belongs to paper A and the user clicks the toolbar in Reader B,
the capture can therefore target A.

### Hidden Workbench is considered active

`activeWorkbenchEntry()` returns the selected Workbench or falls back to
`entries[0]` (`src/plugin.ts:3267-3272`). `activeChatView()` consumes that
fallback. Consequently, a Workbench that exists but is hidden behind a Reader
can suppress the "open a chat surface" branch in
`captureRegionScreenshot()` (`src/plugin.ts:2396`).

### Resume fallback catches unrelated failures

Both first-paper startup (`setPaperInternal`, `src/codex-service.ts:576-607`)
and explicit paper chat opening (`openConversationForPaperInternal`,
`src/codex-service.ts:883-905`) catch every error from the resume path, archive
the pointer, delete the default record, and create a fresh thread. The error
classes already retain enough structure to distinguish cases:
`CodexRpcError` exposes `method`, `code`, and `data`, while
`CodexRequestTimeoutError` and `CodexDisconnectedError` have distinct types
(`src/codex-app-server.ts`).

### Visual parity is not measured in a browser

Fix Pack A added unit tests for soft breaks and CSS-text assertions for Visual
Edit typography. The existing Playwright harness under `test/visual/` measures
real layout, but currently covers clipping and overflow only. It does not
compare the rendered line boxes or formula scale of the two draft surfaces.

### Discoverability uses a font glyph

The Reader toolbar's region button currently renders the character `⬚`
(`src/plugin.ts:668-678`). Its tooltip is descriptive, but the glyph does not
communicate drag-to-select consistently across fonts and platforms.

## Domain terms used by this pack

- **Capture source:** the exact Reader, paper identity, and PDF page from which
  the user invoked a screenshot.
- **Reader capture target:** an immutable operation token containing the exact
  Reader instance, frozen zero-based page index, and accepted `ReaderContext`.
  A context alone is not a capture target because the Reader-context cache is
  keyed by attachment and may later point at a different page.
- **Conversation context:** the paper and thread currently selected in AI chat.
  It may differ from the capture source.
- **Visible chat surface:** a mounted chat surface that is currently exposed to
  the user, not merely retained in a tab manager.
- **Stored conversation pointer:** the current `sessions.papers[paperKey]`
  record that identifies the preferred backend thread for a paper.
- **Missing stored thread:** a resume request that receives a recognized,
  explicit backend response saying that exact thread does not exist.
- **Operational resume failure:** timeout, disconnect, authentication,
  permission, malformed response, thread-read, or local persistence failure.

These terms describe hardening seams only. They do not establish the domain
model for the later Library Agent or AI Context stages.

## Design 1 — Exact region-capture target

### Capture data flow

1. Add a `ReaderCaptureTarget<TReader>` boundary to `ReaderContextService`.
   Accepting a hook freezes `hook.reader`, the accepted context's page index,
   and the accepted `ReaderContext` in that target. A stale or destroyed
   request returns no capture target; it must not fall through to another
   Reader context.
2. The Reader toolbar passes that exact target to
   `startRegionScreenshot(target)`. The method no longer looks up the selected
   conversation's active Reader context.
3. The `@` menu asks Zotero for the strictly active Reader at the moment the
   command is invoked, freezes a target from that hook, and calls the same
   target-taking method. This path must not fall back to `latestHook`, the
   selected conversation context, or an attachment-keyed cached snapshot.
4. Page-element lookup and region rendering consume the target's exact Reader
   handle and frozen page index directly through the adapter. They never call
   `ensureSnapshot(context)`. Page or conversation changes after drag start
   therefore cannot retarget the crop.
5. The existing PDF.js page render, crop geometry, PNG data URI transport, and
   maximum of ten pending images remain unchanged.

Accepting Reader B may refresh B as focused Reader context, but it must not
select, create, or replace B's conversation when conversation A is already
selected. The resulting screenshot is additional context on the active
conversation, just like choosing another paper as additional context.

### Overlay lifecycle

There may be at most one live region-selection overlay per plugin instance.
Starting another capture first cancels and removes the prior overlay. Escape,
a drag below the existing minimum size, a destroyed Reader/page, or a stale
acceptance attaches nothing.

The overlay retains its own cleanup handle until completion or cancellation.
Every terminal path removes event listeners, DOM, and the stored handle.

### Pending-image provenance

Pending region screenshots retain, alongside their data URI:

- capture kind (`region`);
- source paper identity and a human-readable paper title;
- page index and, when available, the displayed page label.

The composer chip shows a compact source such as `Region · Paper title · p. 4`
and exposes the full source through its accessible label/title. This metadata
is UI/session-local for the pending message; the backend image transport still
receives only the existing data URI array.

### Completion and errors

- On crop success, clear the prior chat error, reveal a QLab Workbench if no
  chat surface is visible, render the pending chip, and focus the composer.
- If PDF rendering/cropping fails after a selection, reveal the Workbench by
  the same rule and display the error there. Do not add a pending image.
- Cancellation and a too-small selection are quiet and do not open Workbench.
- Reaching the ten-image cap uses the existing visible limit error.

## Design 2 — Visible chat surface semantics

### One visibility predicate

Introduce one narrow `visibleChatSurface()` query and use it wherever capture
completion or errors decide whether UI needs to be revealed. It may return
only one of these surfaces:

1. a Workbench whose tab is the selected Zotero tab;
2. an open standalone Workbench window that is neither document-hidden nor
   minimized, to the extent exposed by the host APIs;
3. a float panel for which `view.isVisible()` is true;
4. the chat view in the expanded sidebar of the currently selected Reader tab.

Disconnected DOM, a collapsed sidebar, a sidebar for a background Reader, a
closed/hidden/minimized standalone window, and an unselected Workbench do not
qualify. Native OS occlusion by another application cannot be observed and is
outside this predicate.

The existing `activeWorkbenchEntry()` currently combines two different
questions: "which Workbench is selected?" and "is there a Workbench we can
reuse?" Split those concepts. Visibility-sensitive paths use an exact selected
entry; explicit open/reveal paths may deliberately find and select an existing
entry before creating another one.

The predicate also owns the page-change observer and running-turn float inputs,
so retained map/tab membership cannot become a second definition of visible.
A float must have a connected host as well as `view.isVisible()`. A hidden or
minimized standalone continues to own/detach its embedded Reader view, so that
covered sidebar is not counted as independently visible.

### Reveal behavior

When `visibleChatSurface()` returns none, capture completion calls the existing
native Workbench open path. That path must select an existing Workbench if one
is hidden, or create and select one if none exists. Only after selection does
the flow render and focus its composer.

This rule applies equally to successful crop completion and post-selection
render errors. Capture errors use the chat error channel even if the global
pane mode currently points at Terminal, ensuring the revealed chat surface
actually displays the original failure. It does not auto-open UI for quiet
cancellation.

## Design 3 — Transactional stored-conversation resume

### Unified resume boundary

All stored-conversation entry points use one internal operation with a result
equivalent to:

```ts
type StoredConversationResumeResult =
  | { kind: "resumed"; threadId: string }
  | { kind: "missing" };
```

The operation owns `thread/resume` followed by authoritative `thread/read`.
It returns `resumed` only after both succeed. It returns `missing` only when the
resume call itself fails with a recognized missing-thread response. Every other
error is rethrown.

The following paths share it:

- first paper initialization in `setPaperInternal`;
- conversation-tab/History switching in `switchThreadInternal`;
- global History opening in `openGlobalThread`;
- library item opening through `openConversationForPaper`.

The existing serialized paper-transition queue remains the concurrency
boundary, so two selections cannot commit conversation state out of order.

### Missing-thread classifier

No structured missing-thread code or data tag is present in the checked-in
protocol fixtures, so this pack does not invent one. A `CodexRpcError` is
missing only when `method === "thread/resume"` and its normalized whole message
is exactly a known missing-thread message such as `thread not found` or
`conversation not found`. A narrow compatibility fallback recognizes those
same exact whole messages on a plain `Error`, but only inside the catch around
the resume call.
It must not classify a generic error merely because it contains words such as
"thread", "conversation", "resume", or "failed".

`CodexRequestTimeoutError`, `CodexDisconnectedError`, authentication and
permission errors, and errors from `thread/read` or session persistence are
never classified as missing.

### State transaction

Resume is transactional for conversation selection and persisted session
state:

1. Resolve/seed the paper context without changing the selected conversation.
2. Resume and read the requested backend thread.
3. Stage the next session records, active paper/thread, thread-to-paper map, and
   open-thread list.
4. Persist the session update.
5. Publish the staged active state and render it.

If read or persistence fails, restore the pre-operation conversation snapshot.
The stored pointer, History record, selected conversation, and open tabs remain
as they were before the attempt. `AgentClient.threadResume`/`threadRead` may
ingest remote data into `ThreadStore` immediately; that cache is not claimed to
roll back. Reader-focus caches and transient paper-switch flags are likewise
outside this transaction.

### Result policy

| Outcome | Stored pointer | History | Active conversation | Fresh thread |
|---|---|---|---|---|
| Resume + read + save succeeds | Select resumed record | Preserve/dedupe | Switch after commit | No |
| Explicit thread missing | Remove only stale default pointer | Preserve stale record | Select fresh thread after creation succeeds | Yes |
| Timeout/disconnect/auth/permission | Preserve | Preserve | Preserve | No |
| Thread read fails | Preserve | Preserve | Preserve | No |
| Session save fails | Preserve/roll back | Preserve/roll back | Preserve/roll back | No |

An explicit missing result archives/deduplicates the selected old record in
History, clears it only as the paper's default pointer, and creates a new
conversation for that paper. This also applies when the missing record was
opened from local/global History. If an unrelated current default exists for
that same paper, it is archived/deduplicated before the fresh conversation
becomes the sole default. If fresh-thread creation or local persistence fails,
the old local selection/session state is restored and the error is visible.
A remote thread started before a local save failure may remain as an unselected
backend orphan; it must not become the selected or persisted local thread.

Operational failures propagate through the existing visible error path. They
must never be hidden by a successful fresh-thread response.

## Design 4 — Browser-measured Visual Edit contract

### Authority and scope

Compiled HTML Preview remains the visual authority and default reading mode.
Visual Edit remains source-driven. The promised parity is deliberately limited
to the properties the user identified:

- body font size and line height;
- inline and display formula scale relative to surrounding text;
- Pandoc-style soft breaks (a source newline inside a paragraph behaves like a
  space, not a forced line break);
- natural wrapping and resulting line-box count at an equal content width.

Different editing affordances, selection painting, block controls, raw syntax
cards, and full-page chrome are not pixel-parity requirements.

### Paired real-browser fixture

Extend `test/visual/render-harness.mjs` with a paired draft-surface fixture. The
same small QMD sample is presented through:

1. authoritative Quarto HTML Preview markup and styling; and
2. the actual Visual Edit rendering path with the plugin's real stylesheet and
   bundled KaTeX.

The fixture includes inline math, display math, a source-hard-wrapped paragraph,
and a naturally wrapping long paragraph. It is layout-tested in Chromium at a
fixed viewport and equal content-column width. Any temporary Quarto output is
rendered with `--no-execute` outside `public/knowledge/`; generated preview
output is neither hand-edited nor committed.

The test compares computed body typography, normalized formula bounding boxes,
and text line rectangles. Formula/body measurements may differ by at most one
CSS pixel. Soft-break and wrapping fixtures must produce the same effective
text flow and line count.

The test must instantiate the production renderer/styles rather than duplicate
their implementation in test-only HTML. A CSS-text assertion alone is not an
acceptable substitute for this contract.

Quarto may emit CDN URLs for KaTeX. The harness intercepts those requests and
serves the installed KaTeX 0.18.1 script, stylesheet, and fonts locally, so the
test is deterministic and offline. Measurements wait for both a rendered
`.katex` element and `document.fonts.ready`.

### Preserved behavior

- Chat continues to use `newlineAsBreak: true`; its explicit newlines still
  become `<br>`.
- Draft Visual Edit continues to use `newlineAsBreak: false`.
- The chat-scoped KaTeX `1.04em` adjustment remains unchanged.
- A KaTeX parse failure shows the existing raw formula/error fallback and never
  rewrites source QMD.
- `drafts/_quarto.yml` retains KaTeX; `knowledge/_quarto.yml` is untouched.

## Design 5 — Discoverability and original-request regressions

### Region toolbar icon

Replace the font-dependent `⬚` text with a bundled inline SVG depicting a
dashed selection rectangle/corner handles. Keep the existing descriptive
tooltip and `aria-label`, and keep `Screenshot Region` next to
`Screenshot Current Page` in the `@` menu. The toolbar button must remain
visible under the Reader's resource-origin restrictions, so it uses the same
safe inline/data approach as the existing QLab toolbar icon.

### Research Action chips

Fix Pack A's callback wiring and stable-chip rendering remain. Regression tests
exercise the actual Workbench callback set and user click path for at least:

- Summarize;
- Evidence QA;
- Compare Papers.

A click must either dispatch the expected non-empty AI turn or show a legitimate
visible guard (for example, Compare Papers without a second paper). Explicit
user cancellation of a repository/context picker is also a valid quiet exit.
Regression tests configure the required root/selection and assert a non-empty
send so cancellation cannot mask broken wiring. Tests cover the Workbench and
standalone chat surfaces; they do not merely inject a callback into
`SidebarView`.

### Related paper chat without an open PDF

The library item command, conversation tabs, local History, and global History
continue to seed a paper context through a background Reader without stealing
the user's foreground tab. The transactional resume policy above governs every
one of these entry points. A paper with no readable PDF reports a visible error
and changes no conversation state.

## Test strategy

Implementation is test-first. Each defect begins with a regression test that
fails for the observed reason before production code changes.

### Unit and integration coverage

1. **Exact capture source**
   - conversation A selected, toolbar invoked in Reader B → B/page B captured;
   - changing selected conversation during drag does not retarget capture;
   - repeated start cancels the prior overlay;
   - Escape, too-small drag, destroyed page, render failure, and image cap;
   - pending chip exposes paper/page provenance.
2. **Visibility**
   - a hidden Workbench is not visible;
   - selected Workbench, visible standalone, visible float, and expanded current
     Reader sidebar are visible;
   - success and post-selection render failure reveal/select Workbench and focus
     the composer when none is visible;
   - cancellation does not reveal Workbench.
3. **Resume policy**
   - method-scoped exact missing RPC message and narrow legacy fallback;
   - timeout, disconnect, auth, permission, generic error, read failure, and
     save failure all propagate without a fresh thread;
   - local state is unchanged on every operational failure;
   - all four entry points use identical classification;
   - explicit missing preserves History and creates exactly one fresh thread.
4. **Original request regressions**
   - real plugin click dispatch for all three named Research Actions;
   - background context seeding and chat opening with no PDF initially open;
   - Reader focus/conversation selection independence test remains unchanged.
5. **Discoverability**
   - toolbar button contains the selection SVG and retains tooltip/ARIA text;
   - both screenshot commands remain present in the `@` menu.

### Real-browser coverage

`npm run test:visual` measures the paired Preview/Visual Edit fixture described
above. The current Linux container is allowed to record its layered Chromium
launch blockers: the raw environment lacks one browser shared library, and
supplying the available local browser-library path reaches a host-seccomp
sandbox shutdown denial. A skipped suite is still not evidence of parity. The
non-skipped browser acceptance run is explicitly deferred to the user-approved
macOS validation pass.

### Linux completion gates

Run from `integrations/zotero`:

```bash
npm run check
npm test
npm run test:visual
```

`npm run check` and `npm test` must pass on Linux. Run `npm run test:visual` and
record its exact result; include both the raw missing-library error and the
subsequent sandbox-host/seccomp denial observed with local browser libraries,
so this execution gate is deferred to macOS rather than reported as passing.
`npm run verify` includes the
native build and currently stops because the macOS `xcrun` toolchain is
unavailable. That native failure is recorded but is not a Linux completion
failure and must not be represented as a passing XPI build.

### Deferred macOS checklist

On macOS, before treating v0.10.1 as natively validated:

1. Run the full `npm run verify` and build the XPI.
2. Install the XPI into real Zotero.
3. Confirm the region SVG, drag overlay, Escape, and Reader A/Reader B target.
4. Confirm capture success/error reveals and focuses Workbench as designed.
5. Compare HTML Preview and Visual Edit for the parity fixture.
6. Restart Zotero with no PDFs open and reopen a stored paper conversation from
   both History and the library item menu.

These checks are deliberately deferred; they do not block the Linux design or
implementation work.

## Delivery boundaries

- Release as v0.10.1 after the hardening tests and Linux gates pass.
- Update `CHANGELOG.md` and the screenshot/reopen documentation where behavior
  changed.
- Use small test-first commits; do not mix this pack with Library Agent or AI
  Context work.
- Preserve unrelated user changes and the current dashboard surfaces.
- Do not push. Native macOS verification may be recorded later as a separate
  validation result.

## Acceptance criteria

1. With conversation A selected, invoking region capture in Reader B always
   captures B's selected page and attaches a chip identifying B/page B; the
   selected conversation remains A.
2. Only one capture overlay exists. Cancellation and invalid selection attach
   nothing and do not open UI.
3. A hidden Workbench no longer suppresses reveal. Successful capture and
   post-selection render errors select/open Workbench and focus its composer
   when no chat surface is visible.
4. Summarize, Evidence QA, and Compare Papers clicks cause an observable action
   on every supported chat surface; none silently no-op.
5. A paper chat can be opened from the library or History with no PDF initially
   open, without changing the foreground Zotero tab.
6. Only an explicit missing-thread response creates a replacement thread.
   Timeout, disconnect, auth, permission, read, save, and generic errors retain
   the stored pointer and current conversation and show an error.
7. At equal width, browser measurements show Preview and Visual Edit body
   typography and formula scale within one CSS pixel, with matching soft-break
   semantics and wrapping line count for the controlled fixture.
8. Chat newline behavior, chat math sizing, the Reader-focus/conversation
   independence contract, and the Research Loop trust boundary are unchanged.
9. TypeScript and Vitest pass on Linux. The Playwright contract is implemented
   without a skip, its current Linux seccomp launch blocker is recorded, and
   non-skipped Playwright plus native XPI validation remain outstanding for the
   approved macOS pass.

## Subsequent design sequence

After this written specification is reviewed and Fix Pack B is planned, later
work proceeds as separate designs in this order:

1. Library Agent with an always-available library conversation and reviewed
   Zotero mutation proposals.
2. AI Context as a logical record backed by a Quarto draft and projected into
   Zotero through linked attachment handles.
3. Reading Context as the multi-paper planning, guided-reading, resumable-memory,
   and note-evolution workflow built on AI Context.

No interface or persistence decision for those stages is committed by this
hardening spec.
