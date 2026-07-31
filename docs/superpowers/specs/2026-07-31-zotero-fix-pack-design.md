# Zotero Plugin Fix Pack A — Design Spec

- **Date:** 2026-07-31
- **Status:** Approved by user, pending implementation plan
- **Target:** `integrations/zotero` — "Research Loop — Local Codex for Zotero", v0.9.0

Unless prefixed otherwise, file references below are relative to
`integrations/zotero/` (e.g. `src/plugin.ts`, `test/sidebar.test.ts`).

## Overview

Fix Pack A is a bundle of four user-approved changes to the Zotero plugin: (1)
fix the dead Research Action chips (Summarize / Evidence QA / Compare Papers),
(2) bring the Visual Edit mode into visual parity with the Website Preview for
normal reading, (3) add region screenshot capture to the AI chat, and (4) allow
opening a paper's stored conversation without that paper's PDF being open.
Each item ships as its own test-first commit. Two related requests are
deliberately out of scope and will be designed later as separate packs: Fix
Pack B (library-level agent) and Fix Pack C (`aicontext` attachment).

## Background & evidence

All evidence comes from code analysis of the current checkout.

**Item 1 — Research Action chips do nothing.** Chips are rendered by
`SidebarView.renderResearchActions` (`src/sidebar.ts:1028-1058`); each button's
click handler calls the optional callback
`this.callbacks.onResearchAction?.(action.id)` (`src/sidebar.ts:1055`,
declared optional at `src/sidebar.ts:225`). The only construction that wires
this callback is `mountChat` (`src/plugin.ts:930-933`), but the item-pane
surface it serves never mounts: `registerSection` (`src/plugin.ts:551-641`)
has no call site — the surface was removed in v0.7.0 (`CHANGELOG.md:31-33`).
Every live chat surface (workbench tab, standalone window) is built by
`createWorkbenchView` (`src/plugin.ts:1238-1341`), which receives
`researchActions` state (`src/plugin.ts:2218, 2232`) — so chips render — but
omits `onResearchAction`, so the optional-chained call is a guaranteed silent
no-op.

**Item 2 — Visual Edit diverges visually from Website Preview.** Visual Edit
is a hand-rolled Markdown renderer plus bundled KaTeX 0.18.1
(`src/markdown.ts`, `src/qmd-visual-editor.ts`); Website Preview is compiled
Quarto HTML in a remote XUL browser, defaulting to MathJax 3 because neither
Quarto config sets `html-math-method` (`drafts/_quarto.yml`,
`knowledge/_quarto.yml`, repo root). The two surfaces share zero CSS rules.
Concrete divergences: the plugin-wide `.katex { font-size: 1.04em }` override
(`src/styles.css:536-537`) tuned for the 12.5px chat font also hits the 16px
editor; every source newline becomes a `<br>` (`src/markdown.ts:376-381`)
where Pandoc renders soft breaks as spaces; the editor's typography is
hard-coded (`src/styles.css:1304-1313, 1326-1328`) rather than matching the
Quarto theme; and the renderer's list grammar (`src/markdown.ts:102-124`) is
narrower than the block splitter's (`src/qmd-source-model.ts:586-593`), so
`+` bullets, `1)` numbering, and continuation lines degrade to
`<br>`-paragraphs.

**Item 3 — No region screenshot.** Only a full-current-page screenshot
exists, reachable solely via the chat composer's "@" Add-Context menu entry
"Screenshot Current Page" (`src/plugin.ts:3048-3053` →
`captureCurrentPageScreenshot` `src/plugin.ts:2302-2314` → `capturePdfPage`
`src/reader-context.ts:3705-3738`, which renders the whole page to a PNG data
URI; max 10 pending; chips labeled "PDF Screenshot N"). No region selection
exists anywhere in `src/`; there is no reader capture button; the feature is
undocumented outside one CHANGELOG line (`CHANGELOG.md:14`).

**Item 4 — Stored conversations unopenable without the paper.**
Conversations are persisted per paper in profile `sessions.json`, keyed
`${libraryID}-${attachmentKey}` (`src/codex-service.ts:1952-1954`), but every
reopen path checks the in-memory `paperContexts` map, which is populated only
by a live Reader capture in the current Zotero run. `switchThreadInternal`
throws "Open this conversation's Zotero paper once, then select the
conversation tab again" (`src/codex-service.ts:855-863`); `openGlobalThread`
throws similarly (`src/codex-service.ts:788-797`). A proven background
pipeline already exists in `chooseWorkbenchPaper`
(`src/plugin.ts:1845-1927`): `selectItemsDialog` → `getBestAttachment` →
`Zotero.Reader.open` with `openInBackground: true` → `acceptReaderHook` retry
loop.

## Design 1 — Research Action chips fix

### Architecture and data flow

1. **Wiring.** Add `onResearchAction` to the callbacks object built in
   `createWorkbenchView` (`src/plugin.ts:1238-1341`), mirroring the existing
   `mountChat` wiring at `src/plugin.ts:930-933`:

   ```ts
   onResearchAction: (actionID) => {
     void this.runResearchAction(view, actionID, win).catch((e) => this.reportError(e));
   },
   ```

   `view` and `win` are already in scope in `createWorkbenchView`. After this
   change, a chip click on any live surface dispatches the full existing chain:
   `runResearchAction` (`src/plugin.ts:3683-3731`) → skill-bound prompt
   (`src/research-actions.ts:165-185`) → `sendChat` → `codex.send` with the
   read-only sandbox for evidence-review actions.

2. **Hardening against re-render click swallowing.**
   `renderResearchActions` currently rebuilds all chips via
   `actionStrip.replaceChildren()` on every `setState`
   (`src/sidebar.ts:1030`); a re-render landing between mousedown and mouseup
   — frequent during streaming turns — destroys the button before its click
   event fires. Change `renderResearchActions` to skip rebuilding when the
   `researchActions` state is unchanged, using a shallow comparison of the
   actions' ids, labels, and disabled flags against the previously rendered
   set. When the comparison matches, the existing buttons are left in place.

### Error handling

No new error paths. Guard failures inside `runResearchAction` and `sendChat`
remain routed through `.catch(reportError)` into the visible status area
(`src/plugin.ts:3761-3770`, `src/sidebar.ts:1020-1025`), exactly as the
`mountChat` wiring does today.

### Tests

- A plugin-level wiring test asserting that a workbench view built by
  `createWorkbenchView` dispatches `runResearchAction` when a chip is
  clicked. This closes the exact gap the existing DOM test cannot cover:
  `test/sidebar.test.ts:119-141` injects its own `vi.fn()` as
  `onResearchAction` and therefore only proves `SidebarView` forwards clicks
  when a callback is supplied — it cannot catch a missing callback in the
  plugin's callback set. `runResearchAction` currently has zero test
  coverage.
- A unit test for the re-render hardening: with unchanged `researchActions`
  state, `setState` does not replace the chip button elements; with changed
  state, it does.

## Design 2 — Visual Edit visual parity with Website Preview

### Goal

Approved bar: **"visually indistinguishable in normal reading"** — not
pixel-identical. Reading a draft in Visual Edit must give the same math
sizing, paragraph flow, list rendering, and overall typography as the
compiled draft preview.

### Components

1. **Math engine unification.** Add `html-math-method: katex` to
   `/home/chance/quarto-lab/drafts/_quarto.yml`. This makes the compiled
   draft preview use KaTeX, the same engine Visual Edit bundles, eliminating
   the KaTeX-vs-MathJax font-metric divergence. The published site config
   `/home/chance/quarto-lab/knowledge/_quarto.yml` is untouched; only draft
   previews are affected.

2. **KaTeX size fix.** The rule
   `.zc-math-inline .katex, .zc-math-display .katex { font-size: 1.04em }`
   (`src/styles.css:536-537`) was tuned for the 12.5px chat font but also
   applies to the 16px editor. Narrow the selector to the chat-entry scope
   (`.zc-entry-content`), covering both inline and display math there. Chat
   rendering is unchanged; the visual editor falls back to KaTeX's stock
   `1.21em` — the same stock stylesheet default that Quarto's KaTeX output
   uses.

3. **Soft line breaks.** `renderMarkdown` converts every `\n` to `<br>`
   (`src/markdown.ts:376-381`). Add a renderer option `newlineAsBreak`:
   - Visual Edit passes `newlineAsBreak: false` — a single newline inside a
     paragraph or blockquote renders as a space, matching Pandoc soft-break
     semantics, so source-hard-wrapped prose flows as one paragraph.
   - All chat surfaces pass (or default to) `newlineAsBreak: true` —
     behavior unchanged.

4. **Typography alignment.** Replace `.zc-qmd-visual-editor`'s hard-coded
   `font: 16px/1.65 system-ui` and `min(900px, calc(100% - 44px))` column
   (`src/styles.css:1304-1313`) and its heading scale (h1 `2.05em` /
   h2 `1.55em` / h3 `1.25em`, `src/styles.css:1326-1328`) with values
   matching the Quarto default HTML theme actually used by the draft
   preview. The concrete values are measured from a compiled draft page
   during implementation and documented in the implementation plan.

5. **List grammar parity.** `renderMarkdown` only parses `[-*]` bullets and
   `\d+\.` ordered items (`src/markdown.ts:102-124`), while the block
   splitter accepts `[-+*]`, `\d+[.)]`, and indented continuation lines
   (`src/qmd-source-model.ts:586-593`). Extend `renderMarkdown`'s list
   parsing to match the splitter's grammar, so `+` bullets, `1)` numbered
   items, and continuation lines render as real list items instead of
   degrading to `<br>`-paragraphs.

### Error handling

No new failure modes: KaTeX error fallback, the sha256 save pipeline, and the
raw-QMD fallback for unknown syntax are unchanged. The `newlineAsBreak`
option defaults to the current behavior so no chat call site changes
semantics accidentally.

### Tests

- Renderer unit tests for `newlineAsBreak` in both settings (newline → space
  vs newline → `<br>`), covering paragraphs and blockquotes.
- Renderer unit tests for the extended list grammar: `+` bullets, `1)`
  ordered items, and indented continuation lines produce list markup.
- CSS scoping assertions where the test harness allows: the narrowed
  `.katex` size rule applies inside chat entries and not inside
  `.zc-qmd-visual-editor`.
- Existing visual-editor tests stay green: `test/qmd-visual-editor.test.ts`,
  `test/qmd-workspace.test.ts`, `test/qmd-source-model.test.ts`.

## Design 3 — Region screenshot to AI

New feature: select a rectangular region of the current PDF page and attach
it to the chat. Approved shape is a reader toolbar button plus a drag
overlay; Zotero's native area-annotation tool is **not** bridged.

### Architecture and data flow

1. **Reader toolbar button.** Inject a new capture button via the existing
   `renderToolbar` hook, alongside the current "Open QLab Local Codex (⌘I)"
   button (`src/plugin.ts:644-666`).
2. **Drag overlay.** Clicking the button places an overlay over the current
   page view with a crosshair cursor. The user drags a rectangle; Escape
   cancels the overlay; mouse-up completes the selection.
3. **Capture and attach.** On completion, reuse `capturePdfPage`'s
   full-page canvas render (`src/reader-context.ts:3705-3738`) and crop it
   to the drag rectangle, converting view/CSS coordinates to canvas device
   pixels. Produce a PNG data URI and push it into the existing
   `pendingScreenshots` pipeline (`src/plugin.ts:226, 2310`); the pending
   chip is labeled "Region Screenshot N" (full-page captures keep "PDF
   Screenshot N"). After attaching, focus the composer; if no chat surface
   is visible, auto-open one per the existing float/workbench behavior.
4. **Add-Context menu entry.** Add a "Screenshot Region" entry to the chat
   "@" Add-Context menu, enabled when a reader is active, next to the
   existing "Screenshot Current Page" entry (`src/plugin.ts:3048-3053`).
   Selecting it starts the same overlay flow. "Screenshot Current Page" is
   kept unchanged.
5. **Documentation.** Add a README section covering both screenshot flows
   (full page and region), fixing the current discoverability hole — today
   the only shipped mention is one CHANGELOG line (`CHANGELOG.md:14`).

### Error handling

- Escape cancels the overlay with no capture and no state change.
- Degenerate drags (below a minimum size) are discarded; the overlay closes
  without attaching.
- Crop rectangles are clamped to the page canvas bounds.
- The existing pending-screenshot cap (max 10, `src/plugin.ts:2303-2305`)
  applies to region captures; at the cap the flow reports the same
  limit-reached state as full-page capture.
- Downstream transport is unchanged: data URIs flow through
  `codex.send(text, model, effort, imageUrls)` with the existing
  data-URI whitelist and 10-image cap (`src/codex-service.ts:1002-1008`).

### Tests

- Pure crop-math unit tests: view/CSS rect → canvas device-pixel rect
  conversion, clamping to page bounds, minimum-size rejection.
- DOM-level overlay interaction test: drag produces a selection rect;
  Escape cancels; mouse-up completes and dispatches the capture.
- Suggestion-menu test: "Screenshot Region" appears in the Add-Context menu
  and is enabled only when a reader is active.

## Design 4 — Open a paper's chat without the paper open

### Architecture and data flow

1. **New service method.** Add
   `CodexService.openConversationForPaper(itemID/paperKey)`: if
   `paperContexts` lacks the key, seed it through a new host hook the plugin
   supplies to the service (Reader access is a plugin-layer capability). The
   plugin implements the hook by factoring the proven background pipeline
   out of `chooseWorkbenchPaper` (`src/plugin.ts:1845-1927`): background PDF
   open via `Zotero.Reader.open(openInBackground: true)` plus the
   `acceptReaderHook` retry loop. Once seeded, the service switches to the
   stored thread `sessions.papers[paperKey].threadId` via the
   `switchThreadInternal` logic (`src/codex-service.ts:855-892`). If no
   thread is stored for the paper, start a fresh thread instead.
2. **Entry point A — conversation tabs and History rail.** Clicking a
   stored conversation whose paper isn't loaded no longer throws the "Open
   this conversation's Zotero paper once…" error
   (`src/codex-service.ts:855-863, 788-797`); it auto-runs the pipeline.
   The PDF opens in a background tab, so the user's current view is not
   disturbed.
3. **Entry point B — library item context menu.** Add a new "Open QLab
   Chat for This Paper" item to `zotero-itemmenu` (label follows the
   product's QLab naming, e.g. "Open QLab Workbench"), injected following
   the `installQLabMenu` pattern (`src/plugin.ts:3772-3804`, which currently
   only touches `menu_ToolsPopup`). It calls
   `openConversationForPaper` for the right-clicked item.
4. **Invariant preserved.** PDF focus and chat selection stay independent:
   focusing another PDF never steals the active conversation. The existing
   contract test at `test/codex-service.test.ts:529-598` must keep passing
   unchanged.

### Error handling

- Items with no PDF attachment (`getBestAttachment` returns nothing) and
  background-reader seeding failures (retry loop exhausted) surface as
  visible status-area errors via the existing `reportError` path; no silent
  failures.
- A stored thread that no longer exists on the Codex backend falls back to
  starting a fresh thread for the paper, matching the "no stored thread"
  branch.

### Tests

- Service-level tests for `openConversationForPaper`:
  - context missing → background pipeline seeds `paperContexts` → stored
    thread switched to;
  - no stored thread for the paper → a new thread is started.
- Menu-injection test for the `zotero-itemmenu` item.
- Regression run of the focus/selection independence contract
  (`test/codex-service.test.ts:529-598`).

## Cross-cutting

- **Test-first commits, one commit per section.** Per
  `/home/chance/quarto-lab/AGENTS.md`: use test-first commits and do not
  combine unrelated tasks. Each of the four design sections above lands as
  its own commit with its tests written first; no commit mixes two
  sections.
- **Release chores land last.** After the four section commits: update
  `CHANGELOG.md` with one entry per item, update `README.md` (including the
  new screenshot section from Design 3), and bump the version in the
  plugin manifest. This is its own final commit.
- **Verification.** `npm run verify` in `integrations/zotero` (or
  `make zotero-plugin-test` from the repo root) must pass at every commit.

## Known retained limitations

- **Theorem-card numbering can drift.** Visual Edit computes
  theorem/lemma/definition card numbers with local per-render counters
  (`src/qmd-visual-editor.ts:33-41`), which can diverge from Quarto's
  crossref numbering in the compiled preview. Out of scope this round.
- **Visual pane stays light-mode.** The visual pane keeps its hard-coded
  light theme (`src/styles.css:1303`) regardless of Zotero's theme.
- Fix Pack B (library-level agent) and Fix Pack C (`aicontext` attachment)
  remain unaddressed by design; they get their own specs.

## Acceptance criteria

**Section 1 — Research Action chips**
- Clicking Summarize, Evidence QA, or Compare Papers in a workbench tab or
  the standalone window dispatches a codex turn (visible streaming reply, or
  a visible status-area error from a legitimate guard such as "Compare
  Papers needs at least one additional paper").
- Clicking a chip while a turn is streaming still registers (chips are not
  rebuilt when their state is unchanged).
- The new plugin-level wiring test fails if `onResearchAction` is removed
  from `createWorkbenchView`'s callbacks.

**Section 2 — Visual Edit parity**
- A hard-wrapped source paragraph renders as one flowing paragraph in Visual
  Edit, matching the compiled draft preview.
- Inline and display formulas in Visual Edit are visually the same size
  relative to body text as in the compiled draft preview (both KaTeX).
- Chat math rendering is unchanged (still 1.04em relative to chat text).
- `+` bullets, `1)` ordered items, and indented continuation lines render as
  proper lists in Visual Edit.
- Headings, body font, and column width in Visual Edit match the compiled
  draft preview in normal reading.
- The published knowledge site's math pipeline is unchanged.

**Section 3 — Region screenshot**
- A capture button is visible in the reader toolbar; clicking it and
  dragging a rectangle attaches a "Region Screenshot N" chip to the
  composer and focuses it; Escape during the drag attaches nothing.
- "Screenshot Region" appears in the "@" Add-Context menu when a reader is
  active; "Screenshot Current Page" still works unchanged.
- Sending a message with a region chip delivers a cropped PNG data URI to
  the codex turn.
- README documents both screenshot flows.

**Section 4 — Conversation reopening**
- After restarting Zotero with no PDFs open, clicking a stored conversation
  tab or History rail entry opens that conversation: the paper's PDF opens
  in a background tab, the current view stays put, and the stored thread
  becomes active. No "Open this conversation's Zotero paper once…" error.
- Right-clicking a library item with a PDF shows "Open QLab Chat for This
  Paper"; selecting it opens the paper's stored conversation (or a fresh
  thread if none is stored).
- The focus/selection independence contract test
  (`test/codex-service.test.ts:529-598`) still passes.
