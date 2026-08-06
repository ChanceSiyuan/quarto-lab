# Embedded Zotero Reader Spike — Status & Live Validation Checklist

- **Date:** 2026-08-06
- **Spec:** [`specs/2026-08-06-workbench-tabs-design.md`](./specs/2026-08-06-workbench-tabs-design.md)
- **Code:** `integrations/zotero/src/pdf-tab.ts` (strategy chain),
  `integrations/zotero/src/plugin.ts` `createNativeReaderEmbed` (the spike attempt)

## What shipped

The PDF tab runs a **runtime strategy chain** instead of a blocking go/no-go
spike (the implementing agent cannot run a live Zotero; the chain makes the
decision at runtime, per the deviation recorded in the spec):

1. **Native embed attempt** — Zotero 7's item-pane `attachment-preview`
   custom element, created in the tab host with `item` assigned and
   `render()` awaited. Page navigation goes through the element's internal
   reader (`preview._reader?.navigate({ pageIndex })`), which is an
   undocumented surface and may be absent. Every step is guarded; any missing
   API logs `pdf-embed spike: …` via `Zotero.debug` and returns null.
2. **Fallback** — a XUL content `browser` at the attachment's `file://` URI:
   Firefox's built-in pdf.js gives read-only paging/zoom/search, and
   `#page=N` fragments handle page jumps.
3. **Error card** — missing attachment file → "Choose Paper" card; a viewer
   crash → "Reload" card that reruns the chain.

## Not yet attempted in code

Manually instantiating a `ReaderInstance` (the second candidate from the
spec) is **not** coded: it has no public constructor path, and wiring it
blind risks shipping dead code. If the live run below shows the
`attachment-preview` element renders but navigation or annotations are
unusable, that is the next avenue — inspect `Zotero.Reader._readers` and the
element's `_reader` field in the live session first.

## Live validation checklist (requires a real Zotero 9 + the built XPI)

Build the XPI on macOS (`npm run build` needs `xcrun` for the native
helper), install it, then:

1. Open any PDF in the native reader; click **button A** (Open QLab Local
   Codex). Expected: the workbench tab opens split — PDF left, chat right.
2. In the PDF tab, note which strategy rendered:
   - Native embed (annotations/outline visible, `pdf-embed spike:
     attachment-preview mounted` in the debug log), or
   - pdf.js fallback (plain viewer toolbar, no Zotero annotations).
3. If native: create a highlight, switch tabs, come back — the highlight
   persists and appears in the native reader tab too.
4. Click a `p. N` page link in a chat reply. Expected: the PDF tab jumps to
   that page.
5. Drag the PDF tab to the left/right pane; confirm the viewer does **not**
   reload (no flash, scroll position kept).
6. Restart Zotero. Expected: the workbench tab restores with the same tabs,
   sides, and the PDF at its last page.
7. Delete/move the attachment file, reopen the PDF tab. Expected: the
   "Choose Paper" error card, not a broken pane.

## Topic tree & deep links (phase B/C) — additional live checks

8. Open the knowledge site in an **external browser** (`npm run start`, visit
   `/knowledge/`): the index shows the draggable topic tree; hovering a node
   shows the two links, grey where absent; clicking a `zotero://` link makes
   the OS hand it to desktop Zotero (open-pdf lands on the page).
9. Drag nodes, reload — the layout persists (localStorage). "Copy layout
   YAML", paste over the block in `knowledge/index.qmd`, run
   `make knowledge-check`, rebuild — the canvas starts from the frozen
   layout. "Reset layout" returns to it after further drags.
10. Inside the workbench **site tab**, click a `zotero://open-pdf` link on a
    knowledge page: expected — no OS dialog; an open workbench PDF tab jumps
    to the page, else the native reader opens there. If an OS protocol prompt
    appears instead, the remote-browser cancel path is unavailable — record
    it here; the fallback is acceptable per the spec.

## Findings (fill in after the live run)

- Strategy that rendered: _(native / fallback)_
- Annotations usable: _(yes / no / n.a.)_
- Page sync into reader-context: _(yes / no)_
- Follow-ups: _(…)_
