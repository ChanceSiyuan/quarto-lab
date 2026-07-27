# Research Loop Local Problem Console Design

Date: 2026-07-27
Status: Approved and implemented on `codex/local-problem-console`

## Background

Research Loop is intended to support the problem-factory workflow described in
QuantumBFS/quantum.harness issue #133: generate research problems, pre-register
an executable gate for each problem, solve the problem, and eventually package
publishable results.

The original local webpage was primarily a marketing/demo page. It showed a
linear Discover → Verify → Solve → Publish story, stored demo state in browser
`localStorage`, and did not manage real repository-backed problems.

This redesign turns the homepage into a local user console. The core object is
the problem. The console reads problem records from repository files, opens
Codex with a prefilled problem-creation prompt, and provides the first usable
loop from local webpage → Codex conversation → repository problem files →
generated index → local console.

## Goals

- Make problems the central object of the local console.
- Show all indexed problems and their lifecycle status on the homepage.
- Replace the introductory page with a compact, filterable problem table.
- Provide an `+ Add problem` action that opens a prefilled Codex task.
- Let Codex create accepted or rejected problem records only after explicit
  user confirmation.
- Preserve accepted, rejected, and archived records as auditable repository
  files.
- Keep repository problem files as the only business source of truth.
- Provide a stable boundary for future detail pages, gate execution, solver
  runs, and report viewing.

## Non-goals

- Do not design or implement the detailed problem workspace in this pass.
- Do not add multi-user accounts, permissions, database sync, or concurrent
  editing.
- Do not let the homepage advance lifecycle state, run solvers, validate gates,
  delete problems, or publish results.
- Do not implement the full problem-factory backend yet.
- Do not make the generated index a second business data source.
- Do not show a fixed problem-count target or `x / N` denominator in the
  console.

## User and runtime model

The first version serves one researcher running the repository locally. The user
manages problem records through the local webpage and performs problem creation
through Codex Desktop. The webpage and Codex share the same repository path.

Problem records and generation logs belong in Git-tracked repository content.
Browser storage is not used for business state.

## Architecture

```text
Homepage "+ Add problem"
       |
       | codex:// deep link with prompt and repository path
       v
Prefilled Codex task
       |
       | user confirmation after rubric review
       v
problems/<id>/ files
       |
       | schema validation and deterministic index build
       v
.generated/problem-index.json
       |
       v
Homepage metrics, filters, diagnostics, and problem table
```

The implementation has four boundaries:

1. `Problem files`: durable problem manifests, Markdown, and generation audit
   records.
2. `Problem indexer`: scans problem directories, validates records, isolates
   diagnostics, and writes a generated read-only index.
3. `ProblemRepository`: exposes stable query methods to the UI without leaking
   mutable index records.
4. `Codex launch`: builds the deep link and fallback prompt for creating the
   next problem.

## Lifecycle model

Problem statuses are:

```text
draft → qualifying → accepted → solving → solved → publishing → published
draft or qualifying → rejected
any non-terminal status → archived
```

The first homepage only reads and displays lifecycle state. It does not perform
state transitions. Rejected problems must include a rejection type and reason.
Rejected and archived records are hidden by default but can be revealed through
filters.

## Problem file contract

Each problem has its own directory:

```text
problems/QMB-001/
  problem.json
  problem.md
  generation/
    initial-prompt.md
    transcript.md
    decision.md
```

The manifest stores only stable fields needed by code:

```json
{
  "schemaVersion": 1,
  "id": "QMB-001",
  "title": "Problem title",
  "summary": "One-line research objective",
  "status": "draft",
  "gate": {
    "type": "python-benchmark",
    "readiness": "specified"
  },
  "provenance": {
    "sourceCount": 12
  },
  "lastActivity": {
    "summary": "Problem draft created by Codex",
    "at": "2026-07-27T10:00:00.000Z"
  },
  "createdAt": "2026-07-27T10:00:00.000Z",
  "updatedAt": "2026-07-27T10:00:00.000Z"
}
```

No unknown top-level fields are allowed except `rejection` on rejected records.
`gate.readiness` can be `missing`, `specified`, `executable`, or `passed`.
Accepted and later active statuses require `executable` or `passed`.

Rejected manifests additionally require:

```json
{
  "rejection": {
    "kind": "human",
    "reason": "The success criterion cannot be expressed as an ungameable executable gate."
  }
}
```

Accepted and later active problems require complete `problem.md` content with
the headings enforced by `lib/problems/schema.mjs`.

The `generation/` records preserve the initial prompt, the relevant creation
conversation, and the rubric decision.

## Problem IDs and indexing

Problem IDs use the `QMB-NNN` format. The indexer derives the next candidate ID
from every existing matching directory and every parseable matching manifest ID,
including damaged or invalid records. This avoids reusing an ID whose directory
or manifest already exists.

The generated index is derived from `problems/*/problem.json`. It is
deterministic, ignored by Git, and safe to rebuild. Sorting defaults to
descending `updatedAt`, then ascending `id`.

The summary contains raw counts:

- total;
- accepted-or-later with runnable gates;
- solved-or-later;
- published;
- rejected;
- archived.

There is no fixed target denominator in the generated index or homepage.

## Codex creation flow

The `+ Add problem` button opens `codex://threads/new` with URL-encoded `prompt`
and absolute `path`. The deep link only pre-fills the composer; the user still
confirms sending the prompt.

The prefilled prompt must:

- mention QuantumBFS/quantum.harness issue #133;
- instruct Codex to create one new problem for the next reserved-safe ID;
- ask one question at a time;
- check literature basis, research value, novelty, executable gate, and fresh
  evaluation before recommending acceptance;
- reject candidates that cannot be expressed as an ungameable executable gate;
- show the final summary, rubric result, and exact file list before writes;
- write only after explicit user confirmation;
- preserve rejected candidates with rejection fields and generation records;
- stage and validate all required files before publishing `problem.json`;
- publish `problem.json` last so the indexer never sees a half-created record;
- run manifest validation and index build after publication.

The page always includes a `Cannot open Codex?` fallback with the same prompt in
a read-only textarea.

## Homepage information architecture

The homepage removes the promotional hero and uses a compact console layout:

- top bar with Research Loop branding, local mode, repository path, index
  health, and generated timestamp;
- heading and short read-only description;
- raw metric strip for total, accepted, solved, published, and rejected counts;
- search by ID, title, or summary;
- lifecycle filter chips;
- default hidden rejected and archived records;
- `+ Add problem` primary action;
- diagnostics region for invalid manifests;
- desktop semantic table;
- narrow-screen list with the same field order.

Each visible problem row links to `/problems/<id>`. The detail route is stable
in this pass and shows identity, title, summary, and an English placeholder that
the detailed workspace will be designed next.

## Page states

- Empty library: explain the creation loop and provide `+ Add first problem`.
- No matching results: keep filters visible and provide `Clear all filters`.
- Diagnostics present: keep valid problems visible and show invalid file
  diagnostics separately.
- Partially damaged records: exclude invalid manifests but keep valid records
  available.

No asynchronous loading skeleton is included because the page imports a
build-time generated JSON index synchronously. A loading state should be added
when index loading becomes asynchronous and testable.

## Accessibility and responsive design

- Interactions are keyboard reachable.
- Status is expressed through text as well as visual styling.
- Desktop uses semantic table markup.
- Narrow screens use whole-card links.
- Search and filter controls have labels.
- Result counts remain visible.

## Testing strategy

Automated coverage includes:

- schema validation for valid and invalid manifests;
- required conditional fields for lifecycle state;
- Markdown completeness checks that ignore fenced code headings;
- deterministic indexing, duplicate IDs, damaged manifests, and reserved ID
  allocation;
- repository filtering and immutable return values;
- Codex launch URL and prompt contract;
- pure filter/default-hidden/clear behavior;
- rendered homepage and detail route checks;
- real filesystem fixture → index build → app build → rendered HTML.

Manual acceptance:

1. Run the local site.
2. Click `+ Add problem`.
3. Confirm Codex opens in the current repository with a prefilled, unsent
   composer.
4. Complete a short accepted-path creation after reviewing the rubric result.
5. Refresh the homepage and confirm the new problem appears.
6. Complete a rejected-path creation and confirm it is saved, hidden by default,
   and visible when the rejected filter is enabled.

## Completion criteria

- Homepage no longer contains the introductory demo hero or simulated pipeline
  controls.
- Homepage reads from real problem files through the generated index.
- Search, filters, diagnostics, empty state, no-results state, and responsive
  views work.
- `+ Add problem` opens a prefilled Codex task and fallback prompt.
- Codex creation contract can produce schema-valid accepted or rejected records.
- No browser `localStorage` is used for problem or pipeline state.
- User-facing console copy is English.
- No fixed problem-count denominator is displayed.
- Lint, build, and automated tests pass.
