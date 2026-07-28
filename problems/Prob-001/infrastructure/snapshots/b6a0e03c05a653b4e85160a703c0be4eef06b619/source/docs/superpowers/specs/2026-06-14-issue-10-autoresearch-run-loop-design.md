# Issue #10 Autoresearch Run Loop Design

## Goal

Add `autoqec-search run`: a resumable, time-bounded autoresearch loop that
runs inside an isolated git worktree, evaluates candidates from a campaign,
records keep/discard/crash verdicts, and commits a reviewable lab notebook on
an `autoresearch/<tag>` branch.

This is issue #10, the Phase 2 orchestration layer on top of the issue #9
single-candidate evaluator. It should not implement Zoo promotion, adaptive
search, or the later full HTML report.

## Scope

In scope:

- CLI command `autoqec-search run`
- deterministic candidate enumeration from `search_space.json`
- time budget handling from `--wall-clock` or campaign budget fields
- optional `--seed`, `--run-id`, `--resume`, `--cleanup-worktree`, and
  `--allow-dirty-root`
- git worktree creation under `.worktrees/<tag>`
- branch creation under `autoresearch/<tag>`
- per-candidate keep/discard/crash loop
- aggregate notebook files: `experiment-log.tsv`, `leaderboard.csv`,
  `frontier.json`, `summary.md`, and `run-summary.html`
- per-candidate commits and final summary commit on the autoresearch branch
- resume behavior that skips valid completed candidates and recomputes only
  incomplete candidates
- tests with a fake `rsinter` backend and temporary git repositories
- documentation updates for the new command and local branch/worktree behavior

Out of scope:

- pushing autoresearch branches
- promotion into `zoo/`
- adaptive or non-grid search strategies
- TensorQEC generation for missing rotated-surface instances
- the larger M1-4 `report.html`
- changing the public behavior of `autoqec-search eval`

## Main Decision

Implement `run` as a new orchestration layer over a reusable candidate
evaluation helper extracted from `eval_run.py`.

The issue #9 evaluator already owns candidate resolution, artifact copying,
structure checks, rsinter execution, completed manifests, and candidate plots.
Issue #10 should reuse that path instead of reimplementing it or shelling out
to `autoqec-search eval` and merging separate run directories afterward.

The new orchestration layer owns campaign-loop concerns:

- worktree and branch isolation
- candidate ordering
- wall-clock checks
- keep/discard/crash verdicts
- run-level aggregation
- resume logic
- git commits

This keeps the boundary from issue #3 intact: AutoQEC owns campaign and result
aggregation, while `rsinter` remains the benchmark execution backend.

## CLI

Add:

```bash
autoqec-search run --root . --campaign rotated-surface-baseline --wall-clock 90s
```

Options:

- `--root <path>`: repository root; default `.`
- `--campaign <id>`: required campaign id
- `--wall-clock <duration>`: optional time budget; accepts plain seconds,
  `s`, `m`, and `h` suffixes
- `--seed <int>`: optional seed; defaults to the campaign fixed seed when
  present, then `0`
- `--run-id <id>`: optional deterministic run id; when supplied, the tag is
  exactly this id
- `--resume`: resume an existing autoresearch branch/worktree
- `--cleanup-worktree`: remove `.worktrees/<tag>` after the final commit,
  leaving the branch
- `--allow-dirty-root`: permit creating the worktree when the main checkout has
  unrelated local changes

The effective wall-clock budget is chosen in this order:

1. `--wall-clock`
2. `campaign.budget.wall_clock_seconds`
3. `campaign.stop_conditions.max_wall_clock_seconds`

If none is available, the command fails before creating a run.

## Tag And Worktree Layout

The default tag includes campaign, UTC timestamp, and seed:

```text
<campaign>-<YYYYMMDDTHHMMSSZ>-seed<seed>
```

For example:

```text
rotated-surface-baseline-20260614T031122Z-seed7
```

The branch and worktree are:

```text
autoresearch/<tag>
.worktrees/<tag>
```

`--run-id` overrides the generated run id and tag. When `--run-id fixed-check`
is supplied, the branch is `autoresearch/fixed-check`, the worktree is
`.worktrees/fixed-check`, and the run directory is
`results/search/<campaign>/fixed-check`. The command validates the run id and
tag as single path segments before using them in paths or branch names.

By default, the worktree remains after the run so the user can open
`run-summary.html` or inspect artifacts directly. With `--cleanup-worktree`,
the command removes only the run worktree directory after committing the final
summary. The `autoresearch/<tag>` branch remains for manual review.

## Git Safety

Before creating a new worktree, `run` checks the root checkout with
`git status --porcelain`. If it is dirty, the command fails unless
`--allow-dirty-root` is supplied. This protects the reviewable baseline that the
autoresearch branch starts from.

For a new run:

1. create `.worktrees/<tag>` from the current `HEAD`;
2. create branch `autoresearch/<tag>`;
3. write run skeleton files;
4. commit the skeleton;
5. commit after each candidate;
6. commit a final summary if aggregate files changed after the last candidate.

For `--resume`:

1. locate the branch `autoresearch/<tag>`;
2. reuse an existing `.worktrees/<tag>` when present, or recreate it from the
   branch;
3. validate the existing run skeleton;
4. recompute only incomplete candidates;
5. commit changed artifacts and aggregates.

Nothing is pushed.

## Run Layout

The autoresearch branch contains:

```text
results/search/<campaign>/<run-id>/
  run_spec.json
  env.json
  experiment-log.tsv
  leaderboard.csv
  frontier.json
  summary.md
  run-summary.html
  candidates/<candidate-id>/
    candidate.json
    artifacts/
      instance.json
      hx.json
      hz.json
    structure.json
    distance.json
    rsinter/
      spec.toml
      out/<decoder-id>/test-run/results.jsonl
    evaluations/<task-id>/<decoder-id>/manifest.json
    candidate-plot.svg
```

`run_spec.json` supports `mode: "autoresearch"` and records:

- campaign id
- run id
- tag
- suite id
- task ids
- decoder ids
- ordered candidate ids
- created timestamp
- wall-clock budget seconds
- seed

`env.json` records:

- `autoqec_search` version
- git commit SHA for the starting root
- branch name
- generated timestamp
- hostname
- seed
- wall-clock budget seconds
- rsinter version when it can be queried

## Experiment Log

`experiment-log.tsv` is append-oriented and has exactly these columns:

```text
candidate<TAB>ler<TAB>status<TAB>description
```

Statuses:

- `keep`: candidate evaluated cleanly and entered the frontier
- `discard`: candidate evaluated cleanly and did not improve the frontier
- `crash`: candidate resolution or evaluation failed, but the loop continued

For `crash`, `ler` is empty and `description` contains the concise failure
message. For `keep` and `discard`, `ler` is the representative logical error
rate used by the frontier rule.

## Frontier And Leaderboard

The MVP frontier is deterministic and simple:

- use the single task in the selected suite;
- choose the primary decoder as the first decoder listed in the suite;
- choose the representative physical error rate as the first task `p_list`
  value;
- compute representative LER from that completed manifest point;
- keep the first clean candidate for a distance;
- keep a later clean candidate for the same distance only if its representative
  LER is lower than the current frontier item;
- discard all other clean candidates.

`frontier.json` is the machine-readable record of the current frontier. It
stores one item per frontier distance with candidate id, distance,
representative decoder, representative p, LER, and manifest path.

`leaderboard.csv` contains only `keep` rows. This intentionally satisfies the
issue #10 verification rule that every leaderboard row corresponds to a keep
verdict.

## HTML Summary

`run-summary.html` is a self-contained static page with no network assets. It
contains:

- run identity and budget summary
- keep/discard/crash counts
- candidate timeline in loop order
- one compact row per experiment-log entry
- running leaderboard table
- links as relative paths to candidate artifacts where practical

It is lighter than the later M1-4 `report.html`; it exists so the branch is
reviewable visually as well as through diffs.

## Candidate Enumeration

The rotated-surface MVP uses explicit candidate specs from `search_space.json`
in file order. "Propose next" means the next candidate spec in that ordered
list.

The committed `rotated-surface-baseline` example should be expanded from a
single d=3 candidate into a tiny deterministic loop fixture:

- keep the existing checked-in d=3 candidate backed by the Zoo instance;
- add at least one additional valid candidate with distinct id/provenance for
  discard testing;
- keep invalid-candidate negative controls in tests rather than committing
  broken production search-space records.

Missing artifacts or unsupported future distances are recorded as candidate
`crash` rows. The first issue #10 implementation does not call TensorQEC to
generate missing instances.

## Candidate Evaluation Helper

Refactor `eval_run.py` without changing the public `eval` CLI:

- keep `evaluate_single_candidate(...)` as the public fresh-run entry point;
- extract an internal helper that evaluates one resolved candidate into an
  existing run directory;
- let the helper write the same candidate-level files as issue #9:
  `candidate.json`, copied artifacts, `structure.json`, `distance.json`,
  rsinter spec/output, manifests, and `candidate-plot.svg`;
- let the helper return completed manifests and representative metadata for
  aggregation.

`run_loop.py` catches helper exceptions at candidate granularity and converts
them into `crash` log rows.

## Resume Semantics

On `--resume`, a candidate is complete only when all expected manifest files
exist and validate against the result-manifest schema. Completed candidates are
skipped. If a manifest is missing or invalid, only that candidate is recomputed.

After resume, aggregate files are regenerated from the validated candidate
state and `experiment-log.tsv` entries. Previously completed candidate
artifacts are not rewritten.

## Time Budget Semantics

The loop checks elapsed wall-clock time before starting each candidate. If the
budget is exhausted before the next candidate, it stops cleanly, writes
aggregate files, commits them, and exits 0.

With very small budgets such as `--wall-clock 1s`, the command may evaluate
zero or one candidate depending on startup cost. In both cases it still writes
a valid `summary.md` and `run-summary.html`.

Candidate-level rsinter timeouts are candidate crashes, not run-level aborts.

## Error Handling

Run-level fatal errors exit nonzero before claiming a valid run:

- invalid CLI arguments
- missing repository root
- unknown campaign or suite references
- missing wall-clock budget
- invalid tag or run id
- dirty root without `--allow-dirty-root`
- existing branch without `--resume`
- missing branch on `--resume`
- git worktree or commit failure
- invalid existing run skeleton on resume

Candidate-level errors become `crash` rows and do not abort the loop:

- invalid candidate spec
- unsupported distance
- missing matching Zoo artifacts
- missing recorded distance
- CSS structure failure
- rsinter failure or timeout
- malformed rsinter results
- missing or invalid manifest during recomputation

## Testing

Unit tests:

- duration parsing for seconds, `s`, `m`, and `h`
- tag/run-id validation
- dirty-root detection behavior
- candidate completion detection for resume
- frontier keep/discard updates
- experiment-log TSV rendering
- leaderboard rendering with keep-only rows
- `summary.md` and `run-summary.html` rendering

CLI tests with a fake `rsinter` and temporary git repository:

- `run --campaign rotated-surface-baseline --wall-clock 90s` creates
  `.worktrees/<tag>` and branch `autoresearch/<tag>`
- original root working tree remains clean
- run branch has at least one commit after the skeleton and one per evaluated
  candidate
- `experiment-log.tsv` contains at least one `keep` and one `discard`
- fake invalid candidate becomes `crash` and the loop still completes later
  candidates
- deleting one candidate manifest and rerunning with `--resume` recomputes only
  that candidate
- `--wall-clock 1s` exits 0 and writes valid summary artifacts
- `--cleanup-worktree` removes the worktree directory but leaves the branch

Documentation tests should assert that README and CLAUDE mention
`autoqec-search run`, `--wall-clock`, the autoresearch branch, and local
worktree behavior.

## Verification

Primary automated verification:

```bash
python3 -m pytest tests/test_search_run_loop.py tests/test_search_run_cli.py -q
python3 -m pytest tests/test_search_docs.py tests/test_search_eval_cli.py tests/test_search_load.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Local end-to-end verification with real `rsinter`:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run \
  --root . \
  --campaign rotated-surface-baseline \
  --wall-clock 90s
```

Expected result:

- exits 0 on clean budget or stop-condition completion
- creates branch `autoresearch/<tag>`
- writes the run notebook files
- branch log shows per-candidate commits
- original checkout remains clean
- `experiment-log.tsv` has keep/discard rows
- `leaderboard.csv` rows correspond only to keep rows
- `run-summary.html` opens as a self-contained notebook
