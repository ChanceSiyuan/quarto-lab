# QLab Workbench Tabs & Split Panes — Design Spec

- **Date:** 2026-08-06
- **Status:** User-approved architecture, pending written-spec review
- **Target:** `integrations/zotero` — QLab Workbench
- **Related specs:**
  [`2026-07-31-qlab-repository-targets-design.md`](./2026-07-31-qlab-repository-targets-design.md)

Unless prefixed otherwise, file references below are relative to
`integrations/zotero/`.

## Overview

The QLab Workbench replaces its fixed "chat on the left, one exclusive right
pane" layout with a VS Code-style tab system. Four tab kinds — **chat**, **qmd
editor**, **Zotero PDF**, and **main site** — become first-class, closable
tabs. The workbench shows either one pane or two side-by-side panes; any tab
can be dragged between panes, and dragging a tab to a screen edge creates the
split.

Two reader-toolbar buttons drive common arrangements:

- **Button A** (existing "Open QLab Local Codex", `⌘I`): arrange the workbench
  as *PDF of the current paper on the left, chat on the right*.
- **Button C** (new, next to A): arrange as *PDF on the left, qmd editor on the
  right*.

The bottom-left main-site button ("button B", `sidebar.ts:606`) is removed; the
main-site browser becomes an ordinary tab instead. The mutually exclusive
right-pane interlock (`setMainSiteOpen` / `setWorkspaceOpen`,
`sidebar.ts:936-1006`) is deleted.

This is a workbench-internal redesign. Larger context: it is phase A of a
three-part effort (A: this spec; B: a canvas topic tree in
`knowledge/index.qmd`; C: `zotero://open-pdf` page-level deep links from the
knowledge site). B and C get their own specs later.

## Goals

1. Chat, qmd editor, Zotero PDF, and main site are independent, closable tabs.
2. At most two panes, split left/right only; any two tabs can sit side by side.
3. Tabs move between panes by drag and drop, VS Code style, with drop-zone
   previews; dragging the last tab out of a pane (or closing it) collapses the
   layout back to a single pane.
4. Button A arranges PDF + chat; new button C arranges PDF + editor. Both are
   idempotent arrangement commands, not tab factories.
5. Reading a PDF inside the workbench uses the **native Zotero reader**
   (annotations, highlights, outline, page sync) — validated by a spike, with a
   bundled-pdf.js read-only fallback if the spike fails.
6. Layout survives Zotero restarts via the existing workbench-tab session
   hooks.

## Non-goals

- No arbitrary grids, vertical splits, or more than two panes.
- No per-file editor tabs: the qmd editor stays a single workspace tab with its
  internal file tree and Cmd/Ctrl+P quick-open. Chat and main site are also
  single-instance. Only PDF tabs multiply (one per attachment).
- The item-pane chat section, reader float panel, and terminal drawer are
  untouched. The standalone workbench window inherits the tab system
  automatically because it hosts the same view; it gets no extra work.
- No changes to the chat backend (Codex app-server), qmd save/diff flow, or the
  Research Loop trust boundary.

## Architecture

### WorkbenchShell

New module `src/workbench-shell.ts`, the single owner of layout state:

```
WorkbenchShell
├─ tabs: TabDescriptor[]            // id, kind, title, payload
├─ panes: { left: PaneState, right?: PaneState }
│         // PaneState = { tabIds: string[], activeTabId: string }
├─ focusedPane: "left" | "right"
├─ splitRatio                        // reuses --zc-split-ratio + handle
└─ ops: openTab / closeTab / moveTab / activateTab / arrange
```

- `TabKind = "chat" | "editor" | "site" | "pdf"`.
- `chat`, `editor`, `site` are singletons: opening again focuses the existing
  tab. `pdf` is per-attachment: `payload = { itemID, attachmentKey, page }`.
- All tabs are closable.

### TabContentProvider

Existing views are wrapped, not rewritten, behind one interface:

```
TabContentProvider = {
  mount(host: HTMLElement): void   // first show only (lazy)
  show(): void / hide(): void
  dispose(): void
  serialize(): unknown             // restore payload
}
```

Providers: the chat column (extracted from `SidebarView`), `QmdWorkspaceView`,
`ResearchLoopSiteView`, and a new `PdfReaderView` (embedded native reader; see
spike).

### No-reparent rule (load-bearing)

Moving a XUL `<browser>` (main-site view, Quarto previews) or an embedded
reader in the DOM reloads it. Therefore every tab's content container is a
sibling under one fixed parent; pane membership and visibility are expressed
purely with CSS grid column assignment and visibility classes. Drag-to-other-
pane never reparents content DOM. Tab-bar entries are lightweight and may be
re-rendered freely. This rule is why an off-the-shelf docking library
(dockview / golden-layout) was rejected: their drag implementations detach and
reattach panels.

### Layout

Root CSS grid: a tab-bar row above a content row; columns are either `1fr`
(single pane) or `minmax(...) var(--zc-split-ratio) | 6px handle | minmax(...)
1fr` (split), reusing the existing `zc-split-handle`, `beginSplitDrag`
(`sidebar.ts:968-986`), and `--zc-split-ratio` plumbing. The
`is-main-site-open` / `is-workspace-open` grid variants
(`styles.css:1044-1135`) are replaced by generic pane classes. The terminal
drawer keeps overlaying whichever pane hosts the chat tab (the focused pane
when the chat tab is closed). The bottom-left
dock keeps account/terminal/popout buttons; `mainSiteButton` is deleted.

## Interactions

### Tab bar and drag

- Pointer-event based drag (capture-phase listeners, same pattern as
  `beginSplitDrag`), not HTML5 drag-and-drop, which is unreliable in XUL
  chrome documents.
- Within a bar: reorder. Onto the other pane's bar or content area: move.
  Single-pane mode: dragging onto the left/right 20% edge of the content area
  splits, with a translucent drop-zone preview during the drag.
- Closing or dragging away a pane's last tab collapses to a single pane;
  `splitRatio` is remembered for the next split.

### Close semantics per kind

- **chat** — the tab leaves the tab bar, but the chat DOM is hidden rather
  than disposed; threads live in `CodexService`, so reopening is instant and
  lossless.
- **editor** — confirm if a visual-edit block is dirty; otherwise close.
- **pdf** — dispose the embedded reader instance; reopening restores
  `payload.page`.
- **site** — dispose the XUL browser (navigation history discarded, like
  closing a VS Code tab); reopening starts at the site home.

### Buttons A and C

`arrange(spec)` is idempotent: ensure the named tabs exist, split if needed,
assign sides, set active tabs, focus. Button A = `arrange(left: pdf(current
item), right: chat)`; `⌘I` uses the same path. Button C = `arrange(left:
pdf(current item), right: editor)`; the editor opens its last document, or the
file tree when none. Pressing A or C while the workbench is already open
re-arranges in place.

### Source button and PDF page links

- The site view's "Source" button (`research-loop-site.ts:420-429`) now opens
  the editor tab in the *other* pane instead of swapping the right pane.
- Chat PDF-page links (`onOpenPdfPage`, `plugin.ts:1955`) prefer focusing an
  open workbench PDF tab at that page, falling back to the native reader tab.

## PDF embed spike (precedes implementation)

Timebox: 1–2 days. Goal: mount a functioning native Zotero reader for a given
attachment inside an arbitrary `div` in the qlab tab.

- Acceptance: page navigation, annotations, and outline work; page-change
  events reach the existing `reader-context` pipeline.
- Candidate paths, in order: Zotero 7's item-pane attachment-preview element;
  manually instantiating a `ReaderInstance` with a custom iframe host.
- Fallback: read-only pdf.js viewer (bundled with Zotero) with page sync; the
  shell architecture is unaffected by which path wins.
- Deliverable: a one-page spike report committed under `docs/superpowers/`.

## State persistence

Layout serializes to one JSON object:

```
{ panes: { left: { tabs, activeId }, right? }, splitRatio, focusedPane }
```

- PDF tabs persist `{ itemID, attachmentKey, page }`.
- Stored through the existing session hooks in `src/workbench-tab.ts`
  (`restoreState` currently round-trips only `qlabMainSiteOpen`; it now
  carries the layout object). `splitRatio` also stays in prefs as the default.
- Lazy mount on restore: only each pane's active tab mounts; background tabs
  mount on first activation, so a restart does not simultaneously start Quarto
  previews, the site browser, and a reader.

## Error handling

- **pdf tab**: missing/moved attachment → in-tab error card with a
  "choose paper" action. Embedded reader crash → tab-level error boundary with
  a reload button; the rest of the workbench keeps working.
- **site tab**: site not running → the former button-B state machine
  (`activateMainSite`, `sidebar.ts:890-934`: detect / deploy / start with
  progress) moves into the site tab's empty state — reused, not deleted.
- **editor**: optimistic-concurrency save conflicts already handled
  (`plugin.ts:2207-2229`); unchanged.
- **restore**: unknown tab kind or payload (version drift) → drop that tab,
  log, restore the rest.

## Implementation deviations (recorded post-implementation)

1. **Spike ships as a runtime strategy chain.** The implementing agent cannot
   run a live Zotero, so the native-reader embed is attempted at runtime and
   falls back to the bundled pdf.js viewer instead of blocking implementation
   on a go/no-go spike. Findings land in
   [`../2026-08-06-pdf-embed-spike.md`](../2026-08-06-pdf-embed-spike.md).
2. **Terminal with the chat tab closed.** The drawer stays inside the chat
   DOM; the dock's terminal button first reopens the chat tab in the focused
   pane, then opens the drawer — same visible result as the spec's "overlay
   the focused pane" wording with far less relocation machinery.
3. **Single-pane left edge reorders instead of splitting left.** The layout
   model dissolves an emptied left pane, so "dragged tab alone on the left,
   everything else on the right" is not expressible; the right 20% edge
   performs the split and the left edge reorders the tab to the front.

## Testing

Gate remains `npm run verify` (tsc + vitest + build) in `integrations/zotero`.

- `test/workbench-shell.test.ts` — pure logic: open/close/move semantics,
  singleton constraints, `arrange()` idempotence, last-tab pane collapse,
  layout JSON serialize↔restore round-trip, unknown-payload tolerance.
- DOM-level tests (happy-dom, modeled on `standalone-workbench.test.ts`): tab
  bar rendering, close buttons, and — critically — that moving a tab between
  panes preserves the identical content DOM node (guarding the no-reparent
  rule).
- Existing `qmd-workspace.test.ts` and sidebar-related tests follow the
  interface changes; behavioral assertions stay.
- The spike produces a report, not tests.

## Implementation order (for the plan)

1. Spike: embedded native reader feasibility → report, go/no-go on reader vs
   pdf.js.
2. `WorkbenchShell` + providers behind the current two-pane look (chat +
   one right tab), old interlock deleted.
3. Tab bars, close, drag/reorder/move, split-by-drag, drop previews.
4. `PdfReaderView` (spike winner) + button C + button A rearrangement + `⌘I`.
5. Session persistence + lazy mount + error states.
6. Test updates and `npm run verify`.
