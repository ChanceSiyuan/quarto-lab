# Changelog

## 0.10.0

- Fix Research Action chips (Summarize, Evidence QA, Compare Papers) on Workbench surfaces: clicks now dispatch the action, and chips are no longer rebuilt mid-click during streaming re-renders.
- Align Visual Edit with the compiled draft preview: KaTeX on both sides (draft previews now compile with `html-math-method: katex`), Pandoc-style soft line breaks, matched typography, and full list-grammar support.
- Add region screenshots: a reader toolbar capture button with a crosshair drag overlay, plus a "Screenshot Region" Add-Context entry; cropped regions attach as "Region Screenshot" chips.
- Reopen a paper's stored conversation without its PDF open: conversation tabs and History seed the paper in a background reader tab, and library items gain "Open QLab Chat for This Paper".

## 0.9.0

- Add object-aware Research Actions for PDFs, Notes, Collections, and QMD Drafts, routed through the repository's canonical skills.
- Add one-review batch annotation proposals bound to exact Reader selections, with Apply-time PDF fingerprint checks.
- Add safe Zotero Note ↔ QMD Draft exchange with QMD authority, source-Note binding, content conflict checks, and compensating rollback.
- Enforce a read-only filesystem sandbox for analysis Actions.
- Add structured metadata BM25F and Zotero-indexed full-text Library search, without forcing PDF extraction.

## 0.8.1

- Add a lightweight standalone QLab Workbench window with focus/return controls.
- Add conversation-scoped multi-paper context, Paper/Library chat, and current-page screenshots.
- Add ranked PDF text retrieval, persistent evidence traces, and cross-paper citation navigation.

## 0.8.0

- Changed Terminal from a replacement view into a ChatGPT-style bottom drawer
  inside the native QLab tab. Opening and closing it preserves both the chat
  and the live terminal session.
- Starts the drawer in a real local shell rooted at the selected QLab
  repository, with an in-drawer switch to the local Codex CLI.
- Added **Open PDF** beside **Change Paper**, so the bound attachment opens as
  a normal Zotero PDF tab without leaving the QLab workflow.
- Replaced the native QLab tab's inherited PDF icon with the purple QLab chat
  icon, including restored tabs from earlier versions.

## 0.7.0

- Removed QLab from Zotero's item/Reader sidebar. Reader toolbar actions,
  selection actions, shortcuts, and the Tools menu now open the native QLab
  tab instead.
- Replaced the simplified Workbench surface with the complete local-Codex chat
  application: conversation history, paper context, approvals, checkpoints,
  reading notes, repository state, and the six QLab commands appear once in
  the full document area.
- Added empty QLab tabs. A user can start chatting without a PDF, then use the
  paper card's **Select Paper** action to choose a Zotero item or PDF attachment.
- Expanded the native tab layout into a centered, ChatGPT-like conversation
  surface while keeping the compact floating chat independent.

## 0.6.0

- Moved the full QLab Workbench out of the floating panel and into Zotero's
  native tab deck, beside PDF and note tabs at full content-area size.
- Added PDF-like tab behaviour for the Workbench: native selection, drag
  ordering, close/close-others, show-in-library, duplicate, undo-close,
  session restore, and move-to-new-window support.
- Restored the floating surface to a lightweight `550×514` chat window that
  shows the latest exchange and offers a one-click jump to the Workbench tab.

## 0.5.0

- Replaced the compact Reader-only interaction with a large, draggable and
  resizable QLab Workbench that keeps the full conversation visible.
- Made the QLab repository selector explicit and exposed all six repository
  commands as direct buttons in both the sidebar and Workbench.
- Reassigned the reading-note action to the `capture-chat-draft` skill, which
  summarizes the current paper conversation into `drafts/reading-notes/`.
- Removed the Ask/Agent selector and fixed all conversations to the local,
  approval-gated Agent runtime.

## 0.4.1

- Restored Zotero 9's required `applications.zotero.update_url` manifest
  field and verified installation on Zotero 9.0.6.
- Replaced the remaining visible Zotkit Reader pane title with QLab branding.

## 0.4.0

- Integrated the Zotkit Reader interaction model into QLab's Zotero 9 plugin.
- Restricted chat and the advanced terminal to the locally installed Codex
  CLI; removed Claude, remote SSH, external model-provider, and API-key paths.
- Added a validated, user-selectable QLab repository root.
- Added the six-command QLab palette with editable prompts and active Zotero
  item-key context.
- Enforced the QLab trust boundary: ordinary Agent writes stay in
  `literature/`, `drafts/`, and generated `work/`; Knowledge promotion is a
  reviewed, explicitly approved second step.
- Added local Drafts and Knowledge preview prompts using stable Make targets.
- Ported the QLab literature importer to TypeScript, preserving nested Zotero
  collections and linking existing primary PDF and LaTeX attachments.
- Renamed the package and add-on identity to QLab and added Zotero 9 build and
  test targets at the repository root.
