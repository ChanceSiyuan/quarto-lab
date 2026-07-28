# AutoQEC CSS-Distance 200-Trial Import Design

Date: 2026-07-28
Status: Approach A approved; hardening amendment awaiting written-spec review

## Purpose

Import the completed 200-trial AutoQEC CSS-distance autoresearch record into
Research Loop as the first real repository-backed research problem. The import
must preserve every trial, its actual generated candidate when one exists, and
every distinct execution-infrastructure revision used across the two report
cohorts. The copied record must be self-contained inside this repository:
viewing, indexing, and building Research Loop must not access
`/Users/nzy/AutoQEC` or any other external checkout.

The imported problem is an experimental audit record, not trusted learned
knowledge. It belongs under `problems/`, never under `knowledge/`, and is not a
source for `make knowledge-resolve`.

## Approved decisions

- The real record is `Prob-001`.
- `/problems/Prob-001` displays all 200 trials in one ledger. Every row opens a
  dedicated attempt page.
- AutoQEC files are copied as regular files. The import creates no symlink,
  hardlink, submodule, or runtime reference to AutoQEC.
- Every trial preserves its existing `LOG.md`, `REPORT.md`, `candidate.py`, and
  `METHOD.txt` when those files exist in the source trial.
- A failed proposal that never produced `candidate.py` remains a valid visible
  attempt. Research Loop does not invent a candidate or method file for it.
- Research Loop generates one normalized `attempt.json` per trial without
  rewriting the copied source artifacts.
- Trials remain grouped into two logical report cohorts, 001–100 and 101–200,
  because their report contracts differ. Execution infrastructure is frozen
  separately by the actual first-parent commit of each trial ref. This produces
  six physical source snapshots rather than assuming one snapshot per cohort.
- Private blind-evaluation material, selection secrets, salts, answer keys,
  case-level results, and credentials are not imported.
- The GitHub Pages showcase remains synthetic and continues to publish only
  `Prob-000`.

## Trust and publication boundary

`Prob-001` is a local problem and experiment record. It may contain executable
source files, but no Research Loop build, test, route, preview, or index command
executes them. Markdown copied from AutoQEC is stored as an artifact and is not
rendered as trusted HTML. Candidate code is displayed only through normalized
metadata and repository-relative artifact paths.

The imported record does not change any of the existing content authorities:

| Tree | Role after this import |
|---|---|
| `knowledge/` | Reviewed, trusted research knowledge; unchanged. |
| `drafts/` | Untrusted notes; unchanged. |
| `literature/` | External evidence; unchanged. |
| `problems/Prob-001/` | Imported problem, experiment, code, and provenance record; never an answer source. |
| `examples/showcase/problems/Prob-000/` | Synthetic public example; unchanged. |

Ordinary local problem indexing includes `Prob-001`. `pages:build` continues
to build its explicit synthetic fixture and must not copy `Prob-001`, its
candidates, or its infrastructure snapshots into the public Pages artifact.

## Repository layout

```text
problems/Prob-001/
  problem.json
  problem.md
  research.json
  import-manifest.json
  generation/
    initial-prompt.md
    transcript.md
    decision.md
  infrastructure/
    cohorts/
      cohort-001-100.json
      cohort-101-200.json
    snapshots/
      c4533f982ece376c5f299a13edfabff0f489182c/
        source-manifest.json
        source/...
      3e61f5ac8143e4848e5e814188c83683c74dfe4c/
        source-manifest.json
        source/...
      12a8f794f68d63f07303df0cc38fa244c1ab1248/
        source-manifest.json
        source/...
      87f0972ca2551074546c723cf48053d569b9bf59/
        source-manifest.json
        source/...
      3f30f39a2f9be8ceead3821706aae77acdd980aa/
        source-manifest.json
        source/...
      b6a0e03c05a653b4e85160a703c0be4eef06b619/
        source-manifest.json
        source/...
  attempts/
    ATT-001/
      attempt.json
      LOG.md
      REPORT.md
      candidate.py
    ...
    ATT-101/
      attempt.json
      LOG.md
      REPORT.md
    ...
    ATT-200/
      attempt.json
      LOG.md
      REPORT.md
      candidate.py
      METHOD.txt
```

The attempt directory is the durable unit shown by the UI. Copied candidate
and method files are flattened from AutoQEC's `proposal-workspace/` into that
unit; `import-manifest.json` retains each original relative path, so this
layout change does not erase provenance.

## Problem and research manifests

`problem.json` uses the existing problem schema. It records `Prob-001` with
status `solved`, gate type `repository-import`, and gate readiness `passed`.
That gate describes record integrity, not a scientific claim or publication
decision. `problem.md` contains the existing required headings and clearly
labels imported findings as untrusted experiment history.

`research.json` identifies the real research ledger:

```json
{
  "schemaVersion": 1,
  "kind": "imported-research-record",
  "problemId": "Prob-001",
  "attemptCount": 200,
  "attemptIdRange": ["ATT-001", "ATT-200"],
  "disclaimer": "Imported experimental record — not reviewed knowledge.",
  "cohorts": [
    { "id": "cohort-001-100", "first": 1, "last": 100 },
    { "id": "cohort-101-200", "first": 101, "last": 200 }
  ]
}
```

The generation records explain that the problem was imported from an existing
AutoQEC experiment rather than authored or executed by Research Loop.

## Normalized attempt contract

Each `attempt.json` is generated from the copied report, log, Git ref, and file
metadata. It contains only fields that can be traced to those sources. Missing
legacy statistics remain `null`; the importer never derives or fabricates
unrecorded values.

The stable shape is:

```json
{
  "schemaVersion": 1,
  "problemId": "Prob-001",
  "id": "ATT-200",
  "sequence": 200,
  "cohort": "cohort-101-200",
  "title": "CSS Distance Proposal 200",
  "summary": "Imported AutoQEC trial record.",
  "stage": "development",
  "decision": "rejected",
  "gate": {
    "containment": "passed",
    "publicContract": "passed",
    "development": "failed"
  },
  "method": {
    "description": "Source-derived method description.",
    "learnedFrom": null
  },
  "metrics": {
    "runs": 24,
    "verifiedWitnesses": 13,
    "targetHits": 13,
    "timeouts": 0,
    "crashes": 0,
    "invalidClaims": 11,
    "weightedTargetHits": 13,
    "normalizedQuality": 0.541666666666667,
    "runtimeSeconds": 85.7838381199399,
    "averageSeconds": 3.574326588330829,
    "medianSeconds": 2.232983041496482,
    "p95Seconds": 9.437287125037983,
    "timingStatus": "recorded",
    "speedup": null
  },
  "provenance": {
    "sourceRepository": "AutoQEC",
    "sourceBranch": "autoresearch/css-distance/run200-proposal-200",
    "sourceCommit": "705563faed99c094534394e5ca8774f3d74863aa",
    "sourceInfrastructureCommit": "b6a0e03c05a653b4e85160a703c0be4eef06b619",
    "sourceCohort": "cohort-101-200",
    "model": null
  },
  "candidate": {
    "status": "present",
    "path": "candidate.py"
  },
  "artifacts": [
    {
      "path": "LOG.md",
      "sha256": "e28b7dffb8945e10907df9c136e95a5c57ee6a75fb9cb2237316bc6fcbb41a91",
      "sourcePath": "LOG.md"
    },
    {
      "path": "REPORT.md",
      "sha256": "48fc9413bfa907579039c51a1a6c8f3b24e92b570f6ddb724b961ecde6104dfe",
      "sourcePath": "REPORT.md"
    },
    {
      "path": "candidate.py",
      "sha256": "2fb483016f9e8894da309d3079e35c598d412c0c377a84454efae5bfe5322bac",
      "sourcePath": "proposal-workspace/candidate.py"
    }
  ]
}
```

The implementation substitutes actual source values for the illustrative
values above. `timingStatus` is exactly one of `recorded`,
`legacy-not-recorded`, or `not-run`. A missing candidate uses
`candidate.status: "not-generated"`, omits `candidate.path`, and is permitted
only when the copied report records a proposal or public-contract failure.

Gate values use `passed`, `failed`, or `not-recorded`. A field absent from the
source becomes `not-recorded`, never `passed`. `method.learnedFrom` remains
`null` unless a copied source artifact names a specific predecessor.

## Frozen execution infrastructure

The infrastructure under `Prob-001` is problem-specific experimental
provenance. Research Loop's reusable indexing and presentation infrastructure
continues to live in `lib/problems/`, `app/problems/`, and `scripts/`.

The two report cohorts and the physical infrastructure snapshots are separate
concepts. Audit of the 200 trial refs produces this exact mapping:

| Attempts | Report cohort | Infrastructure commit |
|---|---|---|
| `ATT-001` | `cohort-001-100` | `c4533f982ece376c5f299a13edfabff0f489182c` |
| `ATT-002`–`ATT-100` | `cohort-001-100` | `3e61f5ac8143e4848e5e814188c83683c74dfe4c` |
| `ATT-101`–`ATT-104` | `cohort-101-200` | `12a8f794f68d63f07303df0cc38fa244c1ab1248` |
| `ATT-105`–`ATT-107` | `cohort-101-200` | `87f0972ca2551074546c723cf48053d569b9bf59` |
| `ATT-108` | `cohort-101-200` | `3f30f39a2f9be8ceead3821706aae77acdd980aa` |
| `ATT-109`–`ATT-200` | `cohort-101-200` | `b6a0e03c05a653b4e85160a703c0be4eef06b619` |

Each distinct snapshot preserves the exact versions at its commit of:

- the CSS-distance batch controller and its transitive local Python import
  closure;
- proposal-workspace validation, Codex/Docker invocation, containment canary,
  and cleanup logic;
- candidate container entrypoint and evaluator container definition;
- independent CSS witness validation and aggregate metric code;
- result-report and standalone page generation;
- the public campaign brief, prompt, and pinned source metadata;
- dependency manifests required to understand the frozen environment; and
- focused contract tests and fixtures that contain no private evaluation data.

For every trial ref, the importer resolves the trial commit and its first
parent. The trial commit is recorded as `sourceCommit`; the first parent is
recorded as `sourceInfrastructureCommit`. Trials with the same infrastructure
commit share one copied snapshot. The importer rejects a trial whose resolved
mapping differs from the exact table above.

The importer determines the local Python import closure from each frozen source
tree, copies each regular file while preserving its relative path, and then
verifies that every local import made by a copied entry point resolves within
the snapshot. It rejects a snapshot with an unresolved local import. It does
not copy unrelated AutoQEC code merely because it shares the same package.

Each snapshot's `source-manifest.json` records:

- full source commit and source ref;
- every attempt range that uses the snapshot;
- entry-point paths;
- every copied relative path, byte size, executable bit, and SHA-256;
- intentionally excluded private path classes; and
- the fact that the snapshot preserves execution code but cannot reproduce the
  withheld blind dataset.

Each `infrastructure/cohorts/*.json` manifest records its logical cohort and an
ordered list of inclusive attempt ranges mapped to full infrastructure commit
IDs. This keeps cohort/report parsing explicit while avoiding duplicate copies
of the same execution source.

The snapshot contains no Git directory. Nothing in it is imported or executed
by Research Loop's JavaScript or TypeScript runtime.

### PR #5 hardening amendment

The infrastructure snapshot is an execution closure, not a repository mirror.
For each pinned infrastructure commit, the importer starts from the approved
CSS-distance execution entry points and copies only:

- those entry points and their recursively resolved local Python imports;
- the exact container definitions, public campaign prompt, dependency
  manifests, and focused public contract fixtures needed to understand those
  entry points; and
- no article corpus, code-zoo checkout, generated site bundle or index,
  unrelated application source, or other file merely because it is present in
  the same Git tree.

Snapshot discovery fails closed. Every selected path must be justified by the
closure or the explicit allowlist, and every local import from selected Python
files must resolve inside the selected set. The six snapshots remain separate,
but repeated unrelated trees are not copied into each snapshot.

Committed-record verification compares the complete on-disk problem tree with
`import-manifest.json`. Excluding only `import-manifest.json` itself, the two
path sets must be identical; missing, extra, symlink, and other non-regular
entries are errors before hashes are accepted.

Research indexing compares the discovered attempt IDs with the exact IDs
declared by `research.json`. For `Prob-001`, this is exactly `ATT-001` through
`ATT-200`. A missing, extra, malformed, or duplicate attempt produces a
problem-level diagnostic and prevents a partial ledger from being emitted.

The corrected import is regenerated from the pinned read-only AutoQEC commits.
The existing broad snapshots and their old `import-manifest.json` are replaced
as one test-verified data change; they are not edited by hand.

## Import command and data flow

The repository adds a single explicit Make target:

```bash
make problem-import-autoqec-css-distance SOURCE=/Users/nzy/AutoQEC
```

The command implements this sequence:

1. Require a readable AutoQEC Git repository and resolve the exact coordinator
   and trial refs without switching or modifying that repository.
2. Require exactly 200 unique source trial refs and map proposal number `NNN`
   to `ATT-NNN`.
3. Read each source artifact with no symlink following and accept only regular,
   single-link files under the allowed relative paths.
4. Parse the cohort-specific report and log contracts.
5. Copy every existing source artifact byte-for-byte into a temporary
   `Prob-001` tree and generate normalized JSON beside it.
6. Resolve each trial's first parent, require the exact six-range mapping above,
   and freeze each of the six distinct infrastructure commits once.
7. Generate `import-manifest.json`, including hashes for every copied and
   generated file other than the manifest itself, plus the original relative
   paths.
8. Validate the complete temporary tree: IDs are contiguous, all JSON schemas
   pass, artifact hashes match, cohort assignments are exact, and missing
   optional artifacts agree with report state.
9. Install the temporary tree as `problems/Prob-001` only if that destination
   does not already exist.

The source repository is read-only migration input. The command never checks
out a ref, creates a worktree, writes a branch, or edits a source file.

A separate verification target reads only the imported tree:

```bash
make problem-import-verify ID=Prob-001
```

Verification recomputes hashes and schemas without contacting AutoQEC. There is
no automatic overwrite or refresh mode. A future re-import is a distinct,
explicit migration that must first preserve or remove the existing destination
through a user-authorized operation.

## Research Loop components and data flow

The current static-example module is split into a reusable research-record
contract and an example adapter. The problem index build scans real attempt
manifests and emits a generated research index alongside the existing problem
index. Routes read generated data, not arbitrary request-provided filesystem
paths.

```text
problems/Prob-001 files
  -> research schema and integrity validation
  -> generated problem + research indexes
  -> repository lookup and presentation helpers
  -> 200-row problem ledger and attempt dossier routes
```

Responsibilities remain separated:

- the importer owns source discovery, copying, normalization, and provenance;
- the research validator owns committed record integrity;
- the indexer owns deterministic build-time discovery and ordering;
- presentation helpers own display formatting only; and
- routes resolve known problem and attempt IDs or return `notFound()`.

The generated index contains normalized attempt records and safe
repository-relative artifact metadata. It does not embed candidate source or
raw Markdown content.

## Problem ledger

`/problems/Prob-001` uses the existing research-ledger visual language without
changing the preserved homepage design. It renders all 200 attempts in
sequence and does not paginate away any row.

The page contains:

- breadcrumbs and the real problem identity;
- a persistent `Imported experimental record — not reviewed knowledge` label;
- aggregate cards derived from the 200 normalized attempts;
- columns for attempt, method, decision, public contract, runs, verified
  witnesses, target hits, normalized quality, total runtime, P95, candidate
  presence, and open; and
- a responsive attempt-card representation in the same sequence.

Legacy unavailable timing is shown as `legacy not recorded`; a proposal that
did not run is shown as `not run`. Neither state is formatted as zero. Failed
attempts remain visible and navigable.

## Attempt dossier

`/problems/Prob-001/attempts/ATT-NNN` uses the existing audit-dossier structure
with real-record labels. It shows:

- sequence, cohort, method, stage, decision, and candidate presence;
- recorded metrics without synthetic defaults;
- containment, public-contract, and development gate states;
- source branch, full trial commit, full infrastructure commit, report cohort,
  and recorded model when known;
- copied artifact paths and SHA-256 values; and
- an explicit `Candidate code was not generated` message when appropriate.

The route does not execute or syntax-highlight imported Python, render imported
Markdown, or expose an absolute source-machine path. Repository users can open
the preserved files directly from the problem tree.

## Error handling

The importer fails without installing a partial destination when it encounters:

- an absent or non-Git source root;
- a missing, duplicate, or out-of-range trial ref;
- a missing `LOG.md` or `REPORT.md`;
- a symlink, hardlink, special file, path escape, oversized artifact, or file
  that changes while being copied;
- malformed or contradictory report fields;
- a candidate-presence state inconsistent with the report;
- an unresolved local infrastructure import;
- private marker, secret, credential, or blind case-level material in the
  proposed copy set;
- a hash mismatch; or
- an existing `problems/Prob-001` destination.

Committed-record validation is all-or-nothing. If a later edit corrupts one
attempt, the problem remains present in the homepage index with an integrity
diagnostic, while its detail route displays the diagnostic instead of a
plausibly complete 199-row ledger.

Unknown problem or attempt IDs return 404. An optional candidate or method file
may be absent only under the explicit normalized rules above.

## Testing

Test-first implementation covers these layers:

### Import fixtures

- parse representative 001–100 and 101–200 report formats;
- preserve copied bytes and executable bits;
- normalize recorded, legacy-unrecorded, and not-run timing;
- accept an expected missing candidate and reject an unexplained one;
- reject duplicate IDs, gaps, traversal, symlinks, hardlinks, mutation during
  copy, private markers, and hash mismatches;
- derive infrastructure commits from trial first parents, deduplicate shared
  commits, preserve multiple commits inside one report cohort, and reject
  unresolved imports; and
- install only a complete 200-attempt temporary tree.

Tests use small synthetic source repositories and must not depend on the real
`/Users/nzy/AutoQEC` checkout.

### Research contracts and indexing

- validate the generic imported-research and attempt schemas;
- require exactly `ATT-001` through `ATT-200` for this record;
- enforce cohort boundaries and candidate/report consistency;
- verify the complete import manifest offline;
- reject any file missing from or added outside the import manifest, including
  symlinks and other non-regular entries;
- verify the exact six infrastructure snapshots and their cohort range maps;
- generate deterministic problem and research indexes; and
- surface one corrupt attempt as a problem-level integrity diagnostic rather
  than a partial ledger.

### Presentation and routes

- derive real aggregate cards without inventing missing metrics;
- render 200 ordered attempt links on the problem page;
- render recorded, legacy-not-recorded, and not-run values distinctly;
- render failed attempts and the missing-candidate message;
- render provenance and repository-relative artifact metadata;
- return 404 for unknown attempts; and
- keep the existing `Prob-000` synthetic routes unchanged.

### Publication and regression gates

- prove `pages:build` includes only the explicit synthetic `Prob-000` problem;
- prove candidate and infrastructure files are absent from the Pages artifact;
- run focused problem/import tests, `make build`, and `make test`; and
- report unrelated failures from pre-existing worktree changes without
  silently repairing them.

## Completion criteria

- `problems/Prob-001` contains a valid problem, research manifest, import
  manifest, generation record, two logical cohort maps, six infrastructure
  snapshots, and exactly 200 ordered attempt directories.
- Every source `LOG.md`, `REPORT.md`, `candidate.py`, and `METHOD.txt` that is
  expected and present is copied byte-for-byte with traceable provenance.
- No copied file is a symlink, hardlink, Git metadata file, credential, or
  private blind-evaluation artifact.
- Offline verification passes without reading AutoQEC.
- Offline verification rejects a missing listed file, an unlisted extra file,
  and a symlink even when its target bytes match a listed hash.
- Research indexing refuses to emit `Prob-001` when any ID from `ATT-001`
  through `ATT-200` is missing or when any unexpected attempt directory exists.
- The homepage lists `Prob-001`; its detail route shows all 200 attempts; every
  attempt route opens; and expected missing candidates are labeled explicitly.
- The six frozen infrastructure snapshots record the exact commits above, every
  attempt points to the correct snapshot, and all manifest/import-closure checks
  pass.
- The six snapshots contain only the approved execution closure and explicit
  supporting allowlist; external article corpora, code-zoo mirrors, generated
  site assets, and unrelated source trees are absent.
- No imported code runs during import verification, indexing, building,
  testing, previewing, or page rendering.
- `knowledge/`, `drafts/`, `literature/`, the dashboard appearance, and the
  synthetic Pages showcase retain their existing boundaries and behavior.
