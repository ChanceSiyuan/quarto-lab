# Zotero Library Agent — Floating Palette Design Spec

- **Date:** 2026-07-31
- **Status:** Approved by user
- **Target:** `integrations/zotero`
- **Design baseline:** [Library Agent · Floating Palette](https://p.superdesign.dev/draft/a1849f74-77d4-4373-b5c9-ed91199bed03)
- **Development host:** Linux; native Zotero and macOS visual verification are deferred to macOS

## Outcome

The ordinary Zotero library view gains a persistent Library Agent. It appears as
a collapsible floating palette above the status bar rather than a sidebar or a
Workbench tab. A user can converse with one durable agent for the current
library, include the current collection and selected items as message context,
and ask it to prepare changes such as creating a child collection and importing
the papers cited by a passage.

The model never writes Zotero data directly. It may search and prepare a bound
proposal, but every mutation is shown as a review card. Only the palette's
explicit Apply control may cross the write boundary.

The existing Workbench is narrowed to PDF chat and chat-while-writing a Quarto
Draft. Its current `Library Chat` scope switch is removed. The two surfaces may
share the Codex connection, account, model catalogue, and read-only Zotero
capabilities, but they do not share a selected thread or silently copy history.

## Goals

1. Make AI available from Zotero's ordinary library/item-list view without
   requiring an open PDF or a QLab repository.
2. Keep the agent discoverable without permanently covering the library.
3. Persist exactly one resumable conversation per Zotero library.
4. Treat collection and item selection as explicit message context, not as new
   conversations.
5. Support a safe first mutation workflow: resolve citations, create one child
   collection, create or reuse bibliographic items, and add them to that
   collection after review.
6. Make all proposed writes inspectable, stale-safe, serialized, and
   compensatable.
7. Preserve the Research Loop trust boundary. The Library Agent cannot write
   `knowledge/`, `drafts/`, `literature/`, or generated site output.

## Non-goals

- No Library Agent sidebar and no second Workbench-like tab.
- No library conversation inside the PDF/Draft Workbench.
- No implicit transfer of full chat history between Library Agent and
  Workbench.
- No delete, merge, metadata edit of an existing item, tag edit, Note or
  annotation mutation, attachment creation, or PDF download in v1.
- No arbitrary model-authored Zotero metadata. Created metadata must come from
  a resolver candidate bound by the host.
- No title-only remote bibliographic search claim on Linux. Exact identifiers
  and local matches are the reliable v1 path; unresolved citations remain
  visible for user action.
- No group-library writes unless the Zotero host positively reports that the
  selected library is editable.
- No AI Context attachment or Reading Context lifecycle in this slice. Those
  remain separate follow-up features.

## Product surface

### Visibility and mounting

The plugin mounts one `LibraryAgentPalette` at the main Zotero window root. It
is visible only while the selected Zotero tab is the ordinary library pane
(`zotero-pane`). It is hidden, without destroying its conversation, in a PDF
Reader, a QLab Workbench, or a standalone Workbench window.

The palette follows the selected library. Switching to another library selects
or resumes that library's own `library:<libraryID>` conversation. Switching
collections or selected rows updates context indicators only.

### Floating Palette geometry

The approved expanded review state uses:

- centered width `min(1180px, calc(100% - 40px))`;
- an 18px gap above Zotero's status bar;
- 22px continuous corners;
- a restrained multi-layer shadow and one-pixel border/inner highlight;
- a translucent shell based on existing Zotero/QLab color tokens;
- opaque proposal and composer surfaces for text legibility;
- a centered vertical resize grip;
- a review-state height of `clamp(300px, 42vh, 540px)`; user resizing remains
  inside the same minimum and maximum so the library table stays usable.

The palette never introduces a right or left sidebar. It does not use external
fonts, decorative gradients, Apple assets, or traffic-light decoration. It
uses the existing system font stack, system blue accent, and the real ZotKit
icon at `chrome://zotkit/content/icons/icon.svg`.

When reduced transparency is requested or `backdrop-filter` is unavailable,
the shell becomes an opaque raised surface without changing layout or contrast.

### Collapsed dock

Collapse turns the palette into a 46px floating dock at the same horizontal
position. The dock contains the product identity, current library label,
pending/running status, review count, and expand control. It does not show a
textarea or transcript.

The palette defaults to the last state held by that Zotero window; a newly
created window starts collapsed. A user send, an Apply-time conflict, or a new
review created from that user's request expands it. Background turns alone do
not steal focus.

### Expanded layout

The expanded palette has four vertical regions:

1. **Header:** icon, `Library Agent`, current library/collection label, context
   pills, review count, history, and collapse control.
2. **Transcript:** the durable library conversation. Messages are readable but
   compact enough to keep the library visible.
3. **Review layer:** a structured mutation card, when pending, showing the
   target collection path and one disposition per requested citation.
4. **Composer:** removable context chips, text input, model, effort, and send or
   stop control.

The composer and review card are visual capsules inside the translucent shell;
they do not become separate side panels.

## Conversation ownership

### Stable subject

Library Agent uses the subject key `library:<libraryID>`. The session store adds
a library-session map while retaining the existing paper-session records
unchanged. Restart resumes the last thread for that library when the backend
still contains it; operational resume failures remain visible and do not
silently create a replacement.

There is one active Library Agent subject per main Zotero window and one stored
thread per library. Different windows showing the same library observe the same
subject state, and the service serializes sends so that subject has at most one
running turn. Different libraries never share a thread.

### Context snapshots

The following context is captured when the user sends a message:

- library ID and human-readable library name;
- selected collection key and path, when present;
- at most 50 selected top-level bibliographic item keys and compact metadata;
- a bounded library summary used by existing read-only tools.

Changing selection after Send does not mutate the already-sent turn. Context
chips show exactly what the next message will include. Selection above 50 items
is represented by the first 50 stable keys plus an explicit omitted count;
attachment content is not silently included.

### Workbench relationship

Workbench remains the full surface for PDF chat and chat alongside a Quarto
Draft. The `Library Chat` scope toggle is removed because it currently changes
presentation context without owning a library thread.

Library Agent and Workbench share one lower Codex app-server connection and the
same account/model catalogue. They keep independent selected thread IDs,
running-turn state, pending reviews, and visible errors. A Reader focus change
cannot replace or interrupt the library turn.

An explicit handoff may open selected papers in Workbench as context. The
handoff transfers only the selected item identities and a user-visible summary,
never the hidden Library Agent transcript.

## Module design

### `LibraryAgentController`

Owns one palette per Zotero main window. It observes selected-tab, library,
collection, and item-selection changes; chooses the library subject; captures
message context; exposes render state; and delegates chat and review commands.
It contains no Zotero write logic.

### Library conversation API

The existing `CodexService` remains the single owner of the app-server
connection. It gains library-subject operations that do not mutate the active
paper conversation:

```ts
openLibraryConversation(subject): Promise<LibraryConversationState>
sendLibraryMessage(subject, message, context): Promise<void>
stopLibraryTurn(subject): Promise<void>
getLibraryConversationState(subject): LibraryConversationState
```

Library turns use the existing no-PDF, library-safe tool allowlist. They do not
require a QLab root and reject active-PDF tools. State-change notifications
include a subject so the palette and Workbench render only their own events.

### `LibraryAgentPalette`

Renders the collapsed dock, expanded transcript, structured review, and
composer. It accepts immutable view state and emits semantic callbacks. It
does not query Zotero globals and does not apply mutations itself.

### `ReviewedLibraryImportService`

This is the only module allowed to compile a citation request into a pending
library mutation and the only module that may call the mutation host after an
Apply decision. Its public flow is:

```ts
zotero_lookup_citations(requests) -> bound opaque candidate IDs
zotero_propose_library_import(candidate IDs, target) -> immutable review
resolveReview(reviewId, "accept" | "reject") -> terminal result
```

Both model-facing tools are read-only with respect to Zotero. A lookup accepts
at most 50 citation requests. Candidate IDs are bound to the lookup batch,
library, thread, resolver digest, and a 30-minute expiry. The proposal tool
rejects raw item metadata and forged, expired, or cross-library IDs.

### `CitationResolver`

The resolver is an interface with deterministic test and Zotero-host adapters.
The v1 host adapter resolves, in order:

1. exact canonical DOI match in the local library;
2. exact canonical arXiv or other stable identifier match locally;
3. exact DOI/arXiv metadata through Zotero's identifier translation facility
   when that facility is available;
4. normalized local title, year, and creator candidates;
5. an explicit unresolved or ambiguous result.

Title-only remote search remains behind this interface and is not required for
the Linux completion claim. The UI never hides unresolved citations.

### `LibraryMutationHost`

The Zotero adapter owns editability checks, collection and item snapshots,
duplicate classification, writes, compensation, and cache invalidation. Model
code never receives raw Zotero constructors or numeric database IDs.

## Review and write boundary

### Safe v1 effects

One approved batch may contain only:

1. create one child collection under the reviewed parent or library root;
2. create top-level bibliographic items from bound candidates;
3. reuse exact existing items and add only the new collection membership.

The collection name is rejected if empty, path-like, longer than 200 Unicode
code points, or contains control characters. A same-name sibling that appears
before Apply makes the review stale.

### Duplicate policy

- One canonical DOI or stable-identifier match is `REUSE`.
- One normalized title/year/creator match is `AMBIGUOUS` until the user chooses.
- Multiple exact matches are a conflict.
- No match with bound resolver metadata is `CREATE`.
- Missing metadata is `UNRESOLVED` and cannot silently disappear.

The review groups rows as Ready, Reuse, Ambiguous, and Unresolved. Each row
states the exact effect. Apply is disabled until every ambiguous row is
resolved and every unresolved omission is explicitly acknowledged. The Apply
label counts concrete effects, not citations.

### Apply protocol

Apply runs in one exclusive service queue:

1. synchronously claim `pending -> resolving` so a double click cannot race;
2. re-read library editability, parent identity, sibling name, candidate
   digests, duplicates, item versions, and memberships;
3. complete preflight before the first write;
4. create the collection;
5. create new items and their memberships;
6. add reviewed memberships to reused items;
7. refresh the bounded library snapshot and mark the review accepted.

If a write fails, compensate in reverse: remove only memberships added to
pre-existing items, erase newly created items, then erase the new collection.
The terminal failed review lists any surviving keys when compensation is
incomplete and never retries automatically.

Reject performs no write. Pending reviews are in-memory capabilities and
expire on restart rather than being auto-applied.

## Error and empty states

- Authentication, connection, and operational thread-resume failures remain
  visible in the palette; they do not replace history.
- A read-only or unknown library disables Apply and explains why.
- No selection is a valid library-level context, not an error.
- A stale proposal stays visible with a Regenerate action and no partial write.
- Resolver ambiguity or failure appears per citation and does not become
  invented metadata.
- A hidden palette may show a compact error/review badge but expands only for a
  user-initiated operation or an Apply conflict.
- Closing/unloading the plugin cancels observers, detaches the palette, stops
  window-owned work, and leaves persistent chat records consistent.

## Accessibility and interaction

- Header, resize grip, dock, transcript, review rows, and composer are keyboard
  reachable with visible focus.
- Collapse/expand and resize expose appropriate ARIA state and labels.
- Status is not communicated by color alone; every mutation disposition has a
  text label.
- Review text sanitizes control, bidi, zero-width, newline, and overlong input
  so display cannot disguise the bytes bound for write.
- The palette respects reduced motion and reduced transparency.
- At narrow widths, context pills may scroll or collapse into a summary; Apply
  and Reject remain visible without horizontal page scrolling.

## Test strategy

All implementation changes are test-first.

### Pure and service tests on Linux

- library subject identity, session persistence, missing-thread versus
  operational failure, and isolation from active paper threads;
- exact message-context snapshotting and bounded selection;
- lookup/proposal schemas, opaque candidate binding, expiry, and
  cross-library/thread rejection;
- DOI/arXiv normalization and duplicate dispositions;
- propose and reject perform zero writes;
- Apply once, synchronous double-click rejection, review serialization, and
  stale-precondition failure before first write;
- reverse compensation and exact survivor reporting;
- no attachment, PDF, Reader, or Research Loop filesystem calls;
- palette visibility across library, Reader, and Workbench tabs;
- collapse/expand, review rendering, disabled Apply, context chips, keyboard
  labels, and reduced-transparency classes;
- removal of the Workbench `Library Chat` toggle.

### Linux integration gate

Run the Zotero integration's formatting, lint, typecheck, unit suite, and
deterministic render/markup tests through its existing `npm run check` gate.
Browser or native-render tests blocked by the Linux Chromium sandbox are
reported separately and are not described as passing.

### Deferred macOS/Zotero verification

- actual mounting above the native status bar at supported window sizes;
- blur, shadow, continuous corners, resize, reduced transparency, and dark
  mode in Zotero;
- Zotero identifier translator behavior for exact DOI/arXiv requests;
- item-type field validation, creator mapping, collection membership removal,
  notifications, and editability reporting;
- complete and incomplete compensation with native Zotero objects;
- persistence and focus behavior across Library, Reader, Workbench, and app
  restart.

## Acceptance criteria

1. Opening Zotero to a library shows the collapsed floating dock without an
   open PDF; expanding it resumes that library's conversation.
2. The expanded review palette matches the approved Floating Palette geometry
   and leaves the library table and status bar usable.
3. Collection and selection changes update the next-message context without
   creating or stealing a thread.
4. Workbench has no `Library Chat` switch and continues to serve PDF/Draft
   conversations.
5. A citation-import request can produce a structured, host-bound review with
   Create, Reuse, Ambiguous, and Unresolved outcomes.
6. Before Apply, no Zotero collection, item, or membership has changed.
7. Reject writes nothing; Apply writes the reviewed safe effects once; stale
   state writes nothing; failure compensates and reports any survivors.
8. Reader focus, Workbench use, and Library Agent turns do not interrupt or
   replace one another.
9. Linux checks pass, and every native-only claim is explicitly left for the
   macOS checklist.
