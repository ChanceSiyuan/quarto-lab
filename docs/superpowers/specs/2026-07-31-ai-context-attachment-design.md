# AI Context Attachment Design

**Issue:** [#8 — 核心功能：aicontext attachment](https://github.com/ChanceSiyuan/quarto-lab/issues/8)

**Base:** `fix/zotero-fix-pack-b` at `170fb2d5`

**Target branch:** `feat/issue-8-aicontext-attachment`

## Goal

Add an AI Context as a first-class Research Loop record: one untrusted Quarto
Draft under `drafts/ai-contexts/`, projected into Zotero as one or more linked
file attachments. A user can save or update a paper conversation, share one
context across several papers, create a planned multi-paper Reading Context,
and reopen the Draft with a dedicated resumable chat.

The Draft is the authority. Zotero attachments are handles that point to it;
they never become a second copy of the context.

## Product contract

### Conversation AI Context

- A visible `Save / Update AI Context` action is available after a completed
  live Codex conversation.
- The first explicit click creates a Draft and recognizable attachment title:
  `AI Context · <short context title>`.
- A paper conversation creates one linked attachment under its regular Zotero
  parent. A multi-paper conversation creates one attachment record under each
  regular parent, with every record pointing to the same `.qmd` path.
- Clicking again updates the same logical record. It never creates a second
  Draft or a duplicate attachment under the same parent.
- The complete visible user/assistant transcript is preserved, while a compact
  memory, progress summary, and next step are regenerated for later sessions.

### Opening and resuming

- Opening a valid AI Context attachment in Zotero opens the QLab Workbench,
  shows that Draft in the existing right-hand QMD editor, and selects or
  resumes a dedicated conversation for that AI Context on the left.
- The dedicated conversation is keyed by the AI Context record ID. The thread
  from which the context was first captured is provenance only; it is not
  aliased to the dedicated context conversation.
- The compressed memory and reading plan are injected into Codex as
  `untrusted` context. Application context states only the selected repository,
  safe relative path, record identity, and write rules. Raw transcript content
  is not injected automatically.
- Reopening never writes. A later explicit `Save / Update AI Context` action is
  required to persist new learning progress.

### Reading Context

- The Zotero item menu offers `Create Shared Reading Context` for selected
  local-library papers. Sending the exact command `create a reading context`
  routes to the same explicit operation when the library selection is
  available.
- One to fifty selected records are accepted; duplicate selections collapse to
  one paper. PDF children resolve to their regular parent. Every target must be
  in the local user library.
- The result is one Draft and one linked attachment per parent, all pointing to
  the same path. Its title begins `Reading Context ·`.
- The generated plan orders every selected paper exactly once, explains each
  transition, gives per-paper reading guidance, records progress and the next
  step, and supplies compressed memory for resuming later.
- The context remains a Draft throughout the workflow. Marking the synthesis
  `complete` changes only its progress text; it does not promote or publish it.

### Standalone context

- `Create Standalone AI Context` creates a top-level linked file attachment in
  the local user library, with no `parentItemID`.
- It uses the same Draft schema, dedicated conversation, update path, opening
  rules, and trust boundary as attached contexts.

## Chosen approach

Three implementation shapes were considered:

1. A prompt-only extension of `capture-chat-draft`. It would add little code,
   but the plugin could not reliably discover the created path, attach it to
   every parent, enforce idempotency, or resume after partial failure.
2. A dedicated `AIContextService` with an injected Zotero/filesystem host.
   This provides a stable record schema, compare-and-swap updates, testable
   projections, and one orchestration seam for all three user flows.
3. A custom Zotero item type or native Note. This would be more Zotero-native,
   but it would not be a linked local attachment and would introduce unsupported
   schema and synchronization behavior.

Approach 2 is selected. It matches the issue literally while keeping the
Research Loop trust boundary physical and testable.

## Components

### `ai-context.ts`

This module owns the domain model and update state machine. It contains no
global Zotero calls.

Its public types are:

```ts
type AIContextKind = "conversation" | "reading";
type AIContextStatus = "active" | "complete";
type AIContextCategory = "theory" | "experiment" | "codes";

interface AIContextPaper {
  libraryID: string;
  itemKey: string;
  title: string;
  attachmentKey?: string;
  creators?: string[];
  year?: string;
  abstract?: string;
}

interface AIContextMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

interface AIContextManifest {
  schemaVersion: 1;
  id: string;
  contextKey: string;
  kind: AIContextKind;
  sourceThreadId: string | null;
  createdAt: string;
  updatedAt: string;
  status: AIContextStatus;
  papers: AIContextPaper[];
  projection: {
    mode: "attached" | "standalone";
    targets: Array<{ libraryID: string; itemKey: string }>;
  };
  capturedEntryIds: string[];
}

interface AIContextSynthesis {
  title: string;
  description: string;
  category: AIContextCategory;
  status: AIContextStatus;
  memoryMarkdown: string;
  progressMarkdown: string;
  nextStepMarkdown: string;
  readingPlan: Array<{
    itemKey: string;
    rationale: string;
    guidance: string;
  }>;
}
```

The service locates a record by `contextKey`. Zero matches creates a record;
one match updates it; more than one match is a hard error. The active AI
Context path takes precedence over the current Codex thread when deciding an
update key, so continuation turns update the record already open in Workbench.
Conversation captures use `conversation:<sourceThreadId>`, Reading Contexts use
`reading:<recordId>`, and standalone contexts use `standalone:<recordId>`.
Record IDs are generated before the first synthesis, making retry keys stable.

### `ai-context-zotero.ts`

This module implements the fakeable host boundary:

- enumerate and read `drafts/ai-contexts/*.qmd`;
- return a source snapshot with a SHA-256 revision;
- compare-and-swap one complete source using a temporary file and atomic move;
- preflight all projection targets;
- create or update linked file attachment projections; and
- resolve and validate an attachment selected for opening.

Before synthesis or file creation, every parent must be a regular item whose
`libraryID` exactly equals `Zotero.Libraries.userLibraryID`. Zotero does not
allow linked files in group libraries. A standalone context also uses the user
library. Mixed, remote, group, missing, non-regular, or non-editable targets
fail before any utility turn or write.

For each parent the host scans existing child attachments by canonical file
path. It reuses and retitles a matching projection or calls
`Zotero.Attachments.linkFromFile({ file, parentItemID })`. A standalone handle
uses `linkFromFile({ file })`. Different parents intentionally receive
different Zotero attachment records for the same path.

All targets are preflighted before writing. If projection creation later fails
partway, the Draft and successful links remain intact; no user item is deleted.
The host throws a structured `AIContextProjectionError` containing the
committed record ID, relative path, successful targets, and incomplete targets.
The plugin sets that committed record as the active context and opens its Draft
before reporting the projection error, even when zero links succeeded. A later
`Save / Update` or `Repair AI Context Attachments` action fills only missing
projections without resynthesizing or replacing user content.

Projection intent is persisted in the strict manifest as `projection.mode` and
stable `(libraryID, itemKey)` targets. The repair command scans valid AI Context
Drafts, compares their intended projections with current Zotero attachments,
and lists records with missing handles. It repairs the only selected record or
requires an explicit record choice when several qualify; it never chooses
silently. This makes zero-link and partial-link failures recoverable after a
plugin or Zotero restart, including standalone records whose intended target is
a top-level local-user-library attachment.

### `ai-context-open-handler.ts`

Zotero 9 has no public cancellable attachment-open hook. Its common open path
for double-click, View File, and `zotero://attachment` calls the internal
`Zotero.FileHandlers.open()` method. The plugin therefore installs a narrow,
reversible wrapper:

- only a linked-file attachment with a `.qmd` path and an `AI Context ·` or
  `Reading Context ·` title is considered a candidate;
- all non-candidates preserve the original `this`, arguments, return value, and
  rejection behavior;
- candidates are handed to the plugin for selected-root canonical containment,
  strict manifest validation, and Workbench opening;
- startup degrades safely when `FileHandlers.open` is unavailable; the explicit
  `Open AI Context in QLab` item-menu action remains available; and
- the wrapper owns an internal active flag. Shutdown always marks it inactive,
  making every later invocation delegate directly to the captured original and
  never touch plugin state; shutdown restores the global method only if the
  installed function is still this plugin's wrapper.

This is deliberately isolated because it is an internal Zotero seam. Tests pin
its delegation and cleanup behavior, and release notes call out the native
Zotero smoke test.

### `codex-service.ts`

`openWorkspaceObjectConversation(object)` complements `setWorkspaceObject`.
It constructs the existing workspace-object Reader context, assigns the stable
synthetic identity derived from the AI Context record ID, and always selects or
resumes that identity's persisted thread. It does not leave an unrelated active
paper thread selected merely because one already exists.

The existing session store and `openStoredConversation` flow remain the source
of thread persistence. No second conversation registry is introduced.

### `plugin.ts` and `sidebar.ts`

The plugin remains the orchestration layer:

- collect the active primary paper, conversation-scoped secondary papers, and
  visible user/assistant entries;
- collect and normalize selected Zotero items for Reading Context creation;
- call the domain service only after an explicit user action;
- open or resume the dedicated context conversation;
- keep the active context path and bounded untrusted memory in interaction
  state; and
- open the existing `QmdWorkspaceView` for the returned relative path.

The existing unused `onCaptureChatDraft` callback becomes the visible
`Save / Update AI Context` action rather than adding another parallel action
system. Item-menu commands cover create, open, and standalone flows.

## Draft format

Every file is a promotion-ready Draft with exactly the existing allowlisted
frontmatter fields, in order:

~~~~qmd
---
title: "Reading Context · Fault-tolerant decoding"
description: "A resumable reading chain and discussion memory for the selected papers."
categories: [codes]
---

<!-- qlab-ai-context-managed:start -->
<!-- qlab-ai-context-manifest:v1:<BASE64URL_UTF8_JSON> -->

## Compressed memory

...

## Reading plan

...

## Progress

...

## Next step

...

## Conversation log

### User

`````text
complete original message
`````

<!-- qlab-ai-context-managed:end -->

## Personal notes

Add handwritten observations here. This section is never replaced by an AI
Context update.
~~~~

The manifest JSON is UTF-8 encoded as strict unpadded base64url before entering
the HTML comment, so values cannot inject `-->` or raw HTML. Exactly one
manifest marker, one start marker, and one end marker must exist in the required
order. Unknown schema versions, invalid base64url, invalid JSON, unsafe paths,
duplicate markers, or malformed managed regions fail closed.

Transcript messages use a text fence longer than the longest backtick run in
that message. This preserves every character as inert preview text. Synthesized
Markdown escapes raw HTML delimiters before rendering. On update, only the
managed block is replaced; frontmatter and every byte outside the block are
preserved.

## Concurrency and size limits

The service reads a `(source, revision)` snapshot before synthesis. After the
utility turn it reads again and calls compare-and-swap with the expected
revision. A mismatch discards no file content: the complete synthesis is rerun
once against the latest source. A second mismatch raises
`AIContextConflictError` and performs no write or projection change.
Creation uses an expected absent revision; if the generated path appears before
the compare-and-swap, it follows the same single-retry rule instead of
overwriting the newly appeared file.

Limits are explicit and fail before writing:

- complete UTF-8 QMD source: at most `2_000_000` bytes;
- one utility synthesis input batch: at most `80_000` characters;
- one utility synthesis output: at most `64_000` characters; and
- memory plus reading plan injected on reopen: at most `32_000` characters.

Uncaptured messages are folded through ordered utility batches, so every new
user/assistant message contributes to compressed memory. The persisted
transcript is never silently truncated. Exceeding the total QMD budget asks the
user to finish or manually archive the current note before starting another
context.

## Synthesis contract

A hidden `runUtilityTurn` receives fixed instructions plus untrusted paper,
prior-memory, and conversation envelopes. It returns one strict JSON object
matching `AIContextSynthesis`; fenced prose or extra keys are rejected.

For Reading Contexts, normalization ensures:

- each selected paper occurs exactly once;
- unknown or duplicate item keys are rejected;
- omitted papers are appended in stable selection order with explicit
  evidence-limited guidance; and
- title, description, category, status, memory, progress, and next step satisfy
  bounded non-empty string rules.

The synthesized `title` is a short semantic title without a product prefix.
Creation renders it as `AI Context · <title>` for conversation and standalone
records, or `Reading Context · <title>` for reading records, in both
frontmatter and attachment titles. It uses the synthesized description and
category unchanged. Updates preserve the existing user-visible frontmatter and
attachment title, and only refresh the managed block. A synthesis failure,
invalid result, conflict, or target preflight failure leaves both the Draft and
Zotero untouched.

## Trust and security boundary

- AI Contexts are always under `drafts/`; they are untrusted and never
  published by the knowledge build.
- The feature never reads from or writes to `knowledge/`, `literature/`,
  `public/knowledge/`, dashboard source, repository configuration, or a source
  PDF.
- Paper metadata, chat text, synthesized memory, the Draft source, and reopened
  memory are evidence/data, never authorization.
- Every open and write uses the currently selected Research Loop root, a
  canonical path beneath `drafts/ai-contexts/`, and symlink-aware containment.
- Quarto preview continues to use the repository's existing `--no-execute`
  render path.
- No automatic background save is introduced. Every write begins with a
  visible user action.

## Error behavior

- No repository selected: offer the existing root chooser, then stop if it is
  cancelled.
- Running Codex turn: refuse save until the visible response completes.
- No completed conversation for a conversation capture: explain that at least
  one assistant response is required.
- Invalid/missing/group-library parent: fail before synthesis and name it.
- Duplicate logical records or malformed Draft: fail closed and name every
  conflicting path; never choose one silently.
- Concurrent edit: retry synthesis once, then show a conflict without writing.
- Partial attachment projection: retain the Draft and completed projections;
  activate the retained record and report missing parents so Save/Update or the
  explicit repair command can finish the idempotent projection.
- Unsupported Zotero file-handler seam: retain the explicit Open menu action
  and report the compatibility limitation in diagnostics, without breaking
  other attachment types.

## Testing

Test-first tasks cover four seams:

1. Domain tests: safe path/name generation, strict manifest round-trip,
   malformed/duplicate fail-closed behavior, dynamic transcript fences,
   complete transcript preservation, ordered synthesis batching, Reading
   Context normalization, idempotent updates, preserved personal notes, CAS
   retry/conflict, and every size limit.
2. Zotero host tests: local-user-library preflight, group/mixed rejection,
   top-level link, shared same-path projections, per-parent deduplication,
   canonical/symlink containment, and recoverable partial projection failure.
3. Open-handler and Codex tests: candidate interception, exact delegation,
   missing API degradation, identity-safe restore, inactive delegation under a
   later plugin wrapper, reload behavior, dedicated workspace thread
   creation/resume/switch, and untrusted context boundaries.
4. Plugin/sidebar tests: visible Save/Update control, single/multi capture,
   selected-item Reading Context, exact phrase routing, standalone creation,
   item-menu Open fallback, QMD workspace opening, zero-link/partial-link active
   recovery, restart repair for reading and standalone records, ambiguous repair
   selection, and bounded untrusted memory injection.

Focused tests run during each red-green cycle. The final Linux gates are
TypeScript, the full Zotero Vitest suite, the build, and the repository suite.
A real Zotero 9 smoke test must cover double-click, View File, menu fallback,
shared attachments, and restart/resume; when the Linux worker cannot launch
native Zotero, that manual gate is reported as outstanding rather than called a
pass.

## Release and delivery

The feature releases as Zotero integration `0.11.0`. `README.md`,
`CHANGELOG.md`, `manifest.json`, `package.json`, and lockfile stay in sync in a
final release commit. No Sites deployment is performed.

The completed branch is pushed as
`origin/feat/issue-8-aicontext-attachment`. It is not merged to `main`; the
user decides that later. The final issue comment links the branch, summarizes
the three flows and trust guarantees, lists exact verification evidence, and
states any native Zotero/manual limitation.
