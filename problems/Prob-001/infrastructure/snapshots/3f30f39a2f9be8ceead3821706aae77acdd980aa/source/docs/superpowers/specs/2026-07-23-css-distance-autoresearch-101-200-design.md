# CSS Distance Autoresearch Trials 101–200 Design

## Goal

Continue the blinded randomized CSS-distance upper-bound campaign with exactly
100 new proposal trials numbered 101 through 200.  Each completed trial must
update the existing local aggregate webpage, retain a sanitized `LOG.md` in its
own Git worktree, and record enough aggregate timing information to display
average, median, and P95 runtime without exposing case-level data.

## Fixed boundaries

- Trials use only the 24-case blinded development split.  The 12-case sealed
  final holdout is not loaded, evaluated, or used for ranking.
- Every candidate invocation has a hard 300-second timeout.  Timeout durations
  count as exactly 300 seconds in total, average, median, and P95 statistics.
- Proposal agents receive the public research brief, pinned open-source source
  metadata, the public candidate contract, and sanitized aggregate history.
  They do not receive matrices, case identifiers, targets, seeds, paths,
  vectors, or per-case results.
- Each trial has branch `autoresearch/css-distance/run200-proposal-NNN`,
  worktree `.worktrees/css-distance-run200-proposal-NNN`, and a committed
  sanitized `LOG.md`, `REPORT.md`, and generated `proposal-workspace/candidate.py`
  when proposal generation succeeds.
- Results are verified logical-operator upper bounds only.  They are never
  labelled exact or promotion-safe.

## Architecture

### Aggregate trial statistics

A focused development-trial module runs one candidate over the 24 development
cases through the existing networkless evaluator container.  Cases may run in
parallel, but results are restored to manifest order before aggregation.  The
module keeps case identifiers and seeds in memory only, then emits a fixed safe
aggregate containing counts, normalized quality, total seconds, average
seconds, median seconds, and nearest-rank P95 seconds.

For a timeout, the statistical duration is the fixed 300-second limit.  For a
completed, crash, or invalid result, the measured nonnegative runtime is used.
Nearest-rank P95 is `sorted(durations)[ceil(0.95 * n) - 1]`.  A proposal that
does not reach private evaluation has no timing distribution; the report and
webpage show `not run`, not a fabricated numeric value.

### Proposal loop

The batch controller processes trials sequentially so sanitized results from a
finished trial can inform the next proposal.  For each number it:

1. creates the dedicated Git worktree and sanitized log header;
2. creates an otherwise empty `proposal-workspace/`;
3. runs the live host-path/network containment canary;
4. asks the pinned proposal image for one randomized upper-bound
   `candidate.py`, using only the public brief and sanitized history;
5. runs an independently verified public CSS contract smoke test;
6. evaluates the candidate on the 24-case blinded development split when the
   public contract passes;
7. writes aggregate-only log/report data and commits the trial worktree;
8. atomically regenerates the aggregate webpage.

The controller is resumable.  A worktree with a valid committed report is
skipped; a partially created worktree is resumed from the first missing stage.
No stage reads the sealed-final manifest.

### Sanitized learning history

The prompt includes a bounded aggregate history: the current leaders and the
most recent completed trials.  Each entry contains only proposal number,
public method description, decision, counts, normalized quality, and aggregate
timings.  The history is produced from the same validated report parser used by
the webpage and is checked by the publication privacy guard before being sent
to a proposal container.

### Live results webpage

The existing local artifact remains at
`results/css-distance-autoresearch-100/index.html` so the already-open file URL
continues to work.  Its content expands to a 200-trial campaign:

- proposals 001–100 remain mandatory legacy rows;
- proposals 101–200 appear contiguously as they finish;
- the heading and counter show completed rows out of 200;
- while fewer than 200 rows exist, the document reloads itself every 15
  seconds; the final 200-row document does not reload;
- legacy rows display `legacy not recorded` for unavailable Median/P95;
- new evaluated rows display numeric Median/P95; new non-evaluated rows display
  `not run`;
- proposal 020 remains the only highlighted legacy row;
- exactly one completed accepted row from 101–200 is highlighted as the current
  batch leader, ordered by target hits, normalized quality, verified count,
  then lower total runtime; if it is a faster perfect result than proposal 020,
  its badge identifies it as the overall leader.

All writes remain atomic and the final HTML remains standalone, offline-safe,
sortable, searchable, and free of network assets.

## Failure handling and durability

- Proposal timeout, canary failure, missing candidate, invalid public contract,
  evaluator crash, invalid claim, and evaluation timeout all become explicit
  sanitized trial outcomes.
- The controller force-removes named Docker containers after success, failure,
  or timeout.
- A failed trial still receives a report and commit so the next proposal can
  learn the public failure category.
- Page regeneration happens only from validated reports.  A malformed or
  privacy-unsafe report stops publication without deleting the last valid
  page.
- Trial branches/worktrees are retained after the batch, preserving the
  experiment notebook required by the campaign.

## Verification

Tests cover timeout-inclusive median/P95, nearest-rank P95, safe aggregate
serialization, legacy/new report parsing, live partial ranges, 200-row final
validation, auto-refresh removal at completion, dynamic leader selection,
privacy rejection, resume behavior, 300-second enforcement, and page refresh
after each trial.  Before launch, focused tests, compilation, Git diff checks,
Docker image-label checks, the proposal containment canary, and a public
candidate smoke test must pass.  Completion requires 100 committed trial
worktrees, a 200-row page, nonempty Median/P95 for every privately evaluated
new trial, no sealed-final access, no leaked private details, and zero leftover
CSS-distance containers.
