# Research Loop — Local Codex for Zotero

This Zotero 9 add-on carries the unchanged QLab literature workflow into
Research Loop and combines it with the Reader chat
interface derived from Zotkit Reader. It talks only to the local `codex` CLI;
there are no API-provider, Claude, or remote-SSH controls in the product UI.

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
- Opens Terminal as a bottom drawer in that same tab instead of replacing the
  chat. It starts a real local shell with the selected QLab root as `cwd`, keeps
  its session alive when collapsed, and can switch to the local Codex CLI.
- Shows **Open PDF** beside **Change Paper** for a bound paper and uses the
  purple QLab chat icon for the native Workbench tab.
- Keeps the floating chat lightweight: it shows the latest exchange in a
  compact window and provides a direct jump to the full Workbench tab.
- Lets the user choose a local QLab repository. A valid root contains
  `AGENTS.md`, `qlab`, `literature/`, `drafts/`, and `knowledge/`.
- Shows the selected repository explicitly and offers six direct command
  buttons. Selecting one inserts a complete, editable instruction for Codex:
  `qlab_get_paper`, `qlab_search_literature`, `qlab_propose_patch`,
  `qlab_propose_promotion`, `qlab_validate`, and `qlab_preview`.
- Turns **Organize this chat into a Draft** into a skill-backed capture: Codex separates
  paper-backed claims, user hypotheses, and open questions, then writes a
  reviewable note under `drafts/reading-notes/`.
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

## Build and test

Requires Node.js 20+, Xcode command-line tools on macOS, and a local Codex CLI.

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

## Trust boundary

The add-on exposes only Agent mode. It uses Codex approvals, disables network
access, and restricts ordinary writes to selected QLab roots. `literature/`
remains external evidence, `drafts/` remains untrusted work, and `knowledge/`
remains human-reviewed trusted content. PDF and repository content are always
treated as data, never as authorization.

The add-on contains code derived from `oldantique/zotkit-reader` at commit
`4be362442992c89afc90c825af4a661e37e03588`. See `LICENSE` and
`THIRD_PARTY_NOTICES.txt`.
