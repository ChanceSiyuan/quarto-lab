# Research Loop — Local Codex for Zotero

This Zotero 9 add-on carries the unchanged QLab literature workflow into
Research Loop and combines it with the Reader chat
interface derived from Zotkit Reader. Repository-writing work talks only to
the local `codex` CLI; there are no API-provider, Claude, remote-SSH, web
ChatGPT handoff, or clipboard-import controls in the product UI.

## What it does

- Chats with local Codex from the Zotero PDF Reader and supplies the current
  paper, page, selection, annotations, and bounded Zotero context.
- Opens the full **QLab Workbench** as a native Zotero tab beside PDF tabs. It
  occupies the normal document area and supports Zotero tab selection,
  reordering, closing, duplication, reopening, and moving to a new window.
  Window migration waits for Zotero's native tab deck and restores an open
  Main Site split view in the destination window.
- Keeps QLab out of Zotero's item and Reader sidebars. Reader toolbar actions,
  text-selection actions, and shortcuts go directly to the native QLab tab.
- Allows an empty Workbench to be opened before choosing a paper. The paper
  card can then select or replace a Zotero paper/PDF without leaving the chat
  workflow.
- Uses a full chat-application layout in the tab: conversation history,
  complete transcript, optional paper context, approvals, reading notes, and
  the composer share the normal document area.
- Keeps opened conversations in a horizontally scrollable tab strip across
  papers. Switching a tab also switches the visible literature card and its
  Reader context; closing a tab never deletes the conversation, which remains
  available from the collapsible history rail controlled at the top left.
- Shows contextual **Actions** for the visible PDF, Zotero Note, Collection,
  or QMD Draft: Summarize, Evidence QA, Compare Papers, Analyze Figure, and
  Write Draft. The buttons route into the repository's committed skills; the
  extension does not maintain a second prompt system. The four analysis
  Actions also run in a host-enforced read-only filesystem sandbox.
- Searches the Zotero library with structured filters and BM25F-ranked
  metadata, optionally merged with Zotero's existing full-text index. It does
  not force re-indexing or run PDF extraction for library-wide search.
- Lets the Agent prepare a batch of annotations from exact Reader selections.
  No geometry comes from the model, nothing is written before review, and one
  acceptance applies or rolls back the full batch. Apply also rechecks the
  current PDF fingerprint before reusing any stored Reader geometry.
- Exchanges native Zotero Notes with QMD Drafts: Note content is exposed as
  inert QMD source for the existing Draft skill, while QMD-to-Note export is a
  reviewed mirror with revision-and-content conflict checks. A source marker
  binds an imported Draft back to its existing Note without duplicating it;
  the QMD Draft remains the writing authority.
- Opens Terminal as a bottom drawer in that same tab instead of replacing the
  chat. It starts a real local shell with the selected QLab root as `cwd`, keeps
  its session alive when collapsed, and can switch to the local Codex CLI.
- Shows **Open PDF** beside **Change Paper** for a bound paper and uses the
  purple QLab chat icon for the native Workbench tab.
- Keeps the floating chat lightweight: it shows the latest exchange in a
  compact window and provides a direct jump to the full Workbench tab.
- Lets the user choose a local QLab repository. A valid root contains
  `AGENTS.md`, `qlab`, `literature/`, `drafts/`, and `knowledge/`.
- Treats an empty folder, or a content-only folder containing just
  `knowledge/`, `drafts/`, and `literature/`, as safely initializable. The Main
  Site action becomes **Initialize**, adds only missing infrastructure, and
  never replaces existing user files. A non-empty unrelated folder is refused
  and the user is asked to choose an empty folder instead.
- Shows the selected repository explicitly and offers six direct command
  buttons. Selecting one inserts a complete, editable instruction for Codex:
  `qlab_get_paper`, `qlab_search_literature`, `qlab_propose_patch`,
  `qlab_propose_promotion`, `qlab_validate`, and `qlab_preview`.
- Lets the user ask Codex directly to organize a conversation into a Draft;
  Codex separates paper-backed claims, user hypotheses, and open questions,
  then writes a reviewable note under `drafts/reading-notes/`.
- Keeps ordinary Agent writes inside `literature/`, `drafts/`, and generated
  local state under `work/`. A knowledge promotion is review-only in its proposal
  turn and requires later explicit approval plus `make knowledge-check`.
- Imports or refreshes QLab literature through **Tools → Import/Refresh QLab
  Literature**. The importer preserves nested collections and links only the
  primary PDF and LaTeX entrypoint.
- Opens Drafts and Knowledge previews through the repository's existing local
  preview commands. The Workbench also has a **Main Site** button that checks
  the local Research Loop deployment, builds and starts it when needed, then
  loads it beside the chat in Zotero's native browser without publishing
  Drafts or Literature.
- Keeps the Draft Preview toolbar compact: icon controls expose compliance,
  **Add to Knowledge**, **Visual Edit**, external editing, and refresh through
  hover labels. Visual Edit is source-driven: it renders QMD blocks locally,
  saves the authoritative QMD with revision checks, and leaves the compiled
  Quarto website as a separate, unchanged preview mode. Paragraphs and
  headings edit in place; formulas open as LaTeX; theorem, lemma, definition,
  proof, and callout cards keep their rendered appearance until the user opens
  their complete fenced QMD source. Unknown syntax falls back to raw QMD rather
  than being rewritten heuristically.
  Add to Knowledge starts a non-mutating Agent review before any promotion.
  Agent changes remain in one persistent private working copy. The eye switches
  both preview modes between the original and AI version, and **Keep** is the
  only action that promotes the AI version back to the original Draft. Manual
  Visual Edit or Cursor saves use atomic writes and never silently overwrite a
  newer external revision.

## Screenshots to the AI chat

Two capture flows attach rendered PDF images to the next chat message. Both
produce PNG images sent inline with the message, appear as removable chips
above the composer, and share one limit of 10 screenshots per message.

**Full page.** In the chat composer, open the Add-Context menu (click the `@`
button in the chips row, or type `@` in the input) and choose **Screenshot
Current Page**. The currently visible PDF page is rendered and attached as a
"PDF Screenshot N" chip.

**Region.** Click the region-capture button in the Reader toolbar (the dashed
selection rectangle next to the QLab button), or choose **Screenshot Region**
from the same Add-Context menu. The current page view gets a crosshair overlay:
drag a rectangle around the figure, equation, or table you need and release to
attach it as a chip identifying the source paper and PDF page. Press Escape to
cancel; drags smaller than 8 pixels on a side are discarded. When no chat
surface is visible after a successful capture or render error, a hidden
Workbench is selected and its composer is focused so the captured chip or
error is visible.

Both entries require an open PDF. Click any screenshot chip to remove it
before sending; screenshots ride along with the next message only and are
never stored in Zotero.

## AI Context attachments

Select 1–50 local-library papers and choose **Create Shared Reading Context**
to generate one ordered, resumable reading plan. **Create Standalone AI
Context** makes a top-level linked attachment. Opening a valid attachment (or
using **Open AI Context in QLab**) shows its QMD on the right and resumes its
dedicated conversation on the left. The internal Zotero 9 attachment opener is
used when available; the item-menu action remains the fallback.

Opening an AI Context is read-only to Codex. To revise it, click **Edit with
AI**: QLab starts a dedicated conversation and gives Codex a private copy to
edit. Click the eye to compare that copy with the original, then click
**Keep** to replace the original with the AI version. **Visual Edit** and
external editors continue to edit the original directly. Reopening an AI
Context is read-only again, so start another private AI edit by clicking
**Edit with AI** again.

Updates use compare-and-swap protection: a concurrent edit is retried once
against the latest Draft, then reports a conflict without overwriting either
version. If Zotero creates only some attachment handles, the Draft remains
intact. Choose **Repair AI Context Attachments** to recreate only missing
handles; when several records need repair, QLab asks which record to repair.

Native Zotero 9 smoke testing remains required and outstanding for shared
Reading Context and standalone creation, attachment
double-click/open-menu fallback, dedicated resume, conflict handling, and
partial-projection repair.

## Build and test

Building the add-on requires Node.js 20+, Xcode command-line tools on macOS,
and a local Codex CLI. Starting an initialized main site requires Node.js
22.13+ and Quarto; the Workbench reports either missing dependency directly.

```sh
cd integrations/zotero
npm ci
npm run verify
```

Or from the QLab repository root:

```sh
make zotero-plugin-test
make zotero-plugin
```

The built add-on is `integrations/zotero/dist/Research-Loop-Zotero-<version>.xpi`.
Install it from Zotero's Add-ons window, choose the QLab repository from the
Tools menu, and use **Tools → Open QLab Workbench** (or `⌘I` in Reader) to open
the native chat tab. Start without a paper or choose one from the paper card.
Sign in through the local Codex CLI when prompted. Commands typed directly in
the Terminal drawer are explicit user actions and are not Agent-sandboxed.

The Workbench's top-left history control opens a left-hand rail listing
user-facing conversations stored by the local Codex app-server (Codex App,
CLI, and IDE), with search, pagination, Zotero-local pinning, and reopen-as-tab
support. Ordinary ChatGPT web conversations are not exposed or imported.

## Trust boundary

The add-on exposes only Agent mode. It uses Codex approvals, disables network
access, and restricts ordinary writes to selected QLab roots. `literature/`
remains external evidence, `drafts/` remains untrusted work, and `knowledge/`
remains human-reviewed trusted content. PDF and repository content are always
treated as data, never as authorization.

The add-on contains code derived from `oldantique/zotkit-reader` at commit
`4be362442992c89afc90c825af4a661e37e03588`. See `LICENSE` and
`THIRD_PARTY_NOTICES.txt`.
