# Static Research Example Design

Date: 2026-07-27
Status: Approved in conversation; awaiting written-spec review

## Purpose

Add one lightweight, repository-backed example that demonstrates how Research
Loop presents an automated research campaign. The example is for researchers
who already understand experimentation and want to scan each attempt's core
method, outcome, metrics, and audit evidence quickly.

The example borrows the record shape and research stages observed in the local
AutoQEC repository, but every method result, metric, commit, and conclusion in
Research Loop is synthetic demonstration data. It is not a scientific result.

## Scope

This pass adds only a static display example:

- one CSS code-distance problem visible on the existing problem homepage;
- five synthetic attempts forming a continuous research story;
- a dense problem research page with a clickable attempt ledger;
- one audit-style detail page for every attempt;
- explicit `Example data` labeling on both page levels; and
- focused fixture, lookup, route, and rendered-HTML tests.

This pass does not run an algorithm, create a Git worktree, start an agent,
import AutoQEC data, read a private benchmark, stream logs, compare selected
attempts, render charts, or build a reusable AutoQEC importer.

## Prior-art takeaways

Karpathy's autoresearch records a compact experiment ledger containing a commit,
primary metric, memory, keep/discard/crash status, and short description. MLflow
and Weights & Biases add searchable and sortable run tables plus separate run
detail views. Research Loop follows the same list-to-detail hierarchy while
adding research-specific gate, containment, learning, and provenance fields.

References:

- <https://github.com/karpathy/autoresearch/blob/master/program.md>
- <https://mlflow.org/docs/latest/tracking>
- <https://docs.wandb.ai/guides/runs/filter-runs>

## Information architecture

The existing homepage remains the problem library. Its new `QMB-001` row links
to the problem research page:

```text
Problems homepage
  -> /problems/QMB-001
       -> /problems/QMB-001/attempts/ATT-001
       -> /problems/QMB-001/attempts/ATT-002
       -> /problems/QMB-001/attempts/ATT-003
       -> /problems/QMB-001/attempts/ATT-004
       -> /problems/QMB-001/attempts/ATT-005
```

Non-example problems keep the existing detail placeholder. Unknown problem and
attempt IDs return the existing 404 page.

## Repository content

The problem remains valid under the existing problem manifest contract:

```text
problems/QMB-001/
  problem.json
  problem.md
  example.json
  generation/
    initial-prompt.md
    transcript.md
    decision.md
  attempts/
    ATT-001/
      attempt.json
      LOG.md
    ATT-002/
      attempt.json
      LOG.md
    ATT-003/
      attempt.json
      LOG.md
    ATT-004/
      attempt.json
      LOG.md
    ATT-005/
      attempt.json
      LOG.md
```

`problem.json` uses status `solving`, gate type `python-benchmark`, and gate
readiness `executable`. `problem.md` contains all headings required by the
existing validator. The generation records clearly say that the problem and
results are a static example.

`example.json` contains the page-level disclaimer and the synthetic comparison
baseline:

```json
{
  "schemaVersion": 1,
  "kind": "static-research-example",
  "disclaimer": "Example data — synthetic results for interface demonstration only.",
  "baseline": {
    "label": "Synthetic SOTA baseline",
    "suiteRuntimeSeconds": 1820.4
  }
}
```

Each `attempt.json` uses this stable display shape:

```json
{
  "schemaVersion": 1,
  "problemId": "QMB-001",
  "id": "ATT-001",
  "sequence": 1,
  "title": "Exact meet-in-the-middle baseline",
  "summary": "Establish a correctness-first baseline under the hard timeout.",
  "stage": "development",
  "decision": "rejected",
  "promoted": false,
  "gate": {
    "publicSmoke": "passed",
    "containment": "passed",
    "development": "failed"
  },
  "method": {
    "hypothesis": "Synthetic hypothesis text.",
    "changes": ["Synthetic method change."],
    "learnedFrom": null
  },
  "metrics": {
    "runs": 24,
    "verifiedWitnesses": 18,
    "targetHits": 11,
    "timeouts": 6,
    "crashes": 0,
    "invalidClaims": 0,
    "normalizedQuality": 0.54,
    "runtimeSeconds": 1820.4,
    "medianSeconds": 38.4,
    "p95Seconds": 298.7,
    "speedup": 1.0
  },
  "interpretation": "Synthetic result interpretation.",
  "learnings": ["Synthetic lesson for the next attempt."],
  "provenance": {
    "branch": "example/css-distance/att-001",
    "commit": "e100001",
    "worktreeState": "example",
    "model": "example-agent"
  },
  "artifacts": ["attempt.json", "LOG.md"],
  "createdAt": "2026-07-27T01:00:00.000Z"
}
```

The implementation uses a small, explicit fixture module that imports these
five known JSON files and exposes problem and attempt lookup functions. It does
not scan arbitrary worktrees, validate real research runs, or introduce a new
runtime data service. `LOG.md` files exist to demonstrate the intended durable
audit shape; the pages display their repository paths rather than parsing them.

## Five-attempt story

All values below are synthetic and appear with the page disclaimer.

| Attempt | Method and lesson | Decision | Verified | Hits | Quality | Runtime | P95 | Speedup |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `ATT-001` | Exact meet-in-the-middle baseline; correct but timeout-heavy | rejected | 18/24 | 11 | 0.540 | 1820.4 s | 298.7 s | 1.0x |
| `ATT-002` | Random kernel sampling; fast but returns invalid witnesses | rejected | 15/24 | 12 | 0.500 | 42.6 s | 2.9 s | 42.7x |
| `ATT-003` | Verified quotient-coset descent; restores correctness | accepted | 24/24 | 19 | 0.900 | 183.2 s | 21.8 s | 9.9x |
| `ATT-004` | Residual-seeded local search; improves initialization and speed | accepted | 24/24 | 22 | 0.970 | 39.8 s | 3.8 s | 45.7x |
| `ATT-005` | Adaptive verified portfolio; combines earlier lessons | accepted, promoted | 24/24 | 24 | 1.000 | 15.4 s | 1.24 s | 118.2x |

`ATT-002` points to `ATT-001` through `method.learnedFrom`; each later attempt
points to its immediate predecessor. The narrative demonstrates that a faster
attempt can still be rejected for invalid evidence and that promotion requires
both verified output and competitive metrics.

## Problem research page

`/problems/QMB-001` replaces the generic placeholder only for the static
example. It uses the approved dense experiment-ledger layout:

1. Breadcrumb back to the problem library.
2. Compact problem identity, objective, `Solving`, `Example data`, blind
   evaluation, and `300 s / run` badges.
3. Four aggregate cards: five attempts, three accepted, best target hits
   `24/24`, and best synthetic speedup `118.2x`.
4. A semantic table ordered by attempt sequence with columns:
   attempt, method, stage, decision, gate, verified, target hits, quality,
   runtime, P95, speedup, and open.
5. Whole-row navigation affordance plus a normal link to each attempt route.

With only five fixture rows, search, filtering, grouping, column customization,
and multi-run comparison are intentionally absent.

On narrow screens, each table row becomes a stacked attempt card in the same
field order. The page remains English to match the existing console.

## Attempt detail page

`/problems/QMB-001/attempts/<attemptId>` uses the approved audit-dossier layout:

1. Breadcrumbs back to the problem research page.
2. Attempt title, summary, decision, stage, and persistent example disclaimer.
3. Metric strip for verified witnesses, target hits, normalized quality,
   runtime, P95, and speedup.
4. Main column:
   - hypothesis and method changes;
   - containment -> public smoke -> development -> decision evaluation path;
   - result interpretation; and
   - lessons carried to the next attempt.
5. Audit column:
   - synthetic branch and commit;
   - example worktree state and agent label;
   - creation timestamp; and
   - repository-relative `attempt.json` and `LOG.md` artifact paths.

No value is presented as a real benchmark measurement or publication claim.

## Components and data flow

The implementation stays intentionally small:

- problem and attempt files are durable example content;
- one fixture module statically imports the five attempt manifests and returns
  immutable copies;
- the problem route asks the fixture module whether the current problem is the
  static example and otherwise renders the existing placeholder;
- the attempt route resolves the problem and attempt IDs or calls `notFound()`;
- focused presentation helpers derive aggregate cards and display formatting;
  and
- existing CSS is extended with the ledger, responsive cards, and audit layout.

```text
static repository files
  -> explicit fixture imports
  -> immutable lookup + presentation helpers
  -> problem ledger / attempt audit routes
```

There is no database, network request, algorithm process, worktree process, or
AutoQEC runtime dependency.

## Error handling

- A missing homepage problem remains an index diagnostic under the existing
  problem indexer rules.
- An unknown example problem or attempt ID returns 404.
- The fixture module rejects a mismatched `problemId`, duplicate attempt ID, or
  non-contiguous sequence during module initialization so broken committed
  example content fails tests and builds visibly.
- Non-example problem detail routes retain their existing placeholder instead
  of failing because they have no attempts.
- Artifact paths are repository-relative text, so no absolute local path or
  inaccessible browser file URL is exposed.

## Testing

Focused automated coverage verifies:

- the existing problem index accepts and lists `QMB-001`;
- the fixture module returns five ordered immutable attempts;
- every attempt belongs to `QMB-001`, has a unique ID, and forms the declared
  predecessor chain;
- aggregate cards use the five synthetic attempts;
- the problem route renders the example disclaimer, core table columns, five
  detail links, and synthetic metrics;
- every attempt detail route renders its title, metrics, method, learnings, and
  relative artifact paths;
- unknown attempt IDs return 404;
- a non-example problem still renders the existing placeholder; and
- lint, the focused Node tests, and the production build pass.

## Completion criteria

- The homepage contains one valid `QMB-001` example problem.
- Clicking that row opens the dense research ledger.
- The ledger shows five synthetic, sequential attempts and their core metrics.
- Clicking any attempt opens its audit-dossier page.
- Every result surface says that the data is synthetic example data.
- No algorithm, agent, worktree, private dataset, or AutoQEC importer is run or
  added.
- Existing problem-console behavior remains intact.

