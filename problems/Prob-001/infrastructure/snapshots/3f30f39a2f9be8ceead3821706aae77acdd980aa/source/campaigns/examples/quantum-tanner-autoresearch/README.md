# Quantum Tanner Autoresearch Workflow

## Scope

This page is the local operating loop for the quantum Tanner autoresearch
campaign. It explains how to start, inspect, resume, and review a Codex CLI run
whose durable state lives in files, commits, run logs, and reports.

This is not a SLURM or cluster execution design. Keep cluster execution on the
separate tracking issue, GitHub issue #20.

## Long-Running AI Autoresearch

Run the launcher from the repository root after confirming Codex authentication:

```bash
codex login status

QEC_CODE_BIN=/Users/nzy/rcode/rstim/target/release/qec-code \
RSINTER_BIN=/Users/nzy/rcode/rstim/target/release/rsinter \
scripts/run_quantum_tanner_autoresearch.sh \
  --work-root /tmp/autoqec-qt-long \
  --rounds 20 \
  --proposals-per-round 4 \
  --max-group-order 64 \
  --max-physical-qubits 512 \
  --run-wall-clock 30m
```

Each round uses `codex exec --ephemeral` in a fresh Codex context. Each Codex
proposal-generation invocation can consume Codex/model tokens. Only cumulative
structured feedback crosses rounds. The later local qec-code/rsinter backend
wait time does not consume additional Codex tokens. Ctrl-C stops the current
attempt after recording its interruption.

Before any resume, the caller checkout's `HEAD` must exactly equal
`state.json.source_commit`. Inspect the pinned commit and switch the source
checkout to it before rerunning `--resume`:

```bash
PINNED_COMMIT="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["source_commit"])' \
  /tmp/autoqec-qt-long/state.json)"
git switch --detach "$PINNED_COMMIT"
# Equivalent for older Git: git checkout "$PINNED_COMMIT"
```

After switching to that commit, resume the same work root with the exact
command below. Advancing HEAD to another commit means
resume fails before Codex, qec-code, or rsinter; it does not silently run tools
from a different source revision.

```bash
QEC_CODE_BIN=/Users/nzy/rcode/rstim/target/release/qec-code \
RSINTER_BIN=/Users/nzy/rcode/rstim/target/release/rsinter \
scripts/run_quantum_tanner_autoresearch.sh \
  --work-root /tmp/autoqec-qt-long \
  --rounds 20 \
  --proposals-per-round 4 \
  --max-group-order 64 \
  --max-physical-qubits 512 \
  --run-wall-clock 30m \
  --resume
```

The durable work root contains `state.json` and
`cumulative-feedback.json`; per-attempt files follow
`rounds/round-NNNN/attempt-NNN`, including each attempt's `status.json`.
Each numerical-round `status.json` contains an absolute `run_root` field. To
find the artifact directory for a selected attempt, print that field with
Python 3:

```bash
python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["run_root"])' \
  /tmp/autoqec-qt-long/rounds/round-0001/attempt-001/status.json
```

The cross-round aggregate lives directly under the work root:

- `<work-root>/aggregate/report.html`
- `<work-root>/aggregate/results.jsonl`

The aggregate table is append-ordered with one finite code per row. It includes
accepted terminal candidates with `evaluated, skipped, failed, and interrupted`
statuses; preaccept rejections stay out of the aggregate. The launcher runs before the next Codex proposal,
the launcher feeds the aggregate history back into the prompt and
also applies a hard fingerprint guard, so clearing `state.json` or
`cumulative-feedback.json` does not make an old accepted code look new. If the
source `HEAD` still matches the pinned commit, `--resume` rebuilds a missing
`aggregate/report.html` and `aggregate/results.jsonl` from terminal attempts
without repeating Codex, qec-code, rsinter, or numerical work.

The finalized `report.html`, `construction-definitions.html`,
`surface-copy-comparison.html`, and `quantum-tanner-ai-feedback.html` files are
under that `run_root`. `report.html` is the English human-readable main report:
it starts with summary cards and a master table containing one attempted finite
code per row, including screening-skipped candidates. Base-group and local-code
cells link to `construction-definitions.html`, which records the generator
indices and complete local parity-check matrices. The workflow treats
upper-bound screening evidence as screening evidence only.

## Inputs

The workflow uses the committed local fixtures and contracts:

- `campaigns/examples/quantum-tanner-autoresearch/campaign.json`
- `campaigns/examples/quantum-tanner-autoresearch/search_space.json`
- `campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json`
- `campaigns/examples/quantum-tanner-autoresearch/witnesses/`
- `benchmarks/tasks/quantum-tanner-css-memory-x-rbposd-p001-v1.json`
- `benchmarks/suites/quantum-tanner-rbposd-p001-v1.json`
- `benchmarks/baselines/rotated-surface-single-logical-p001.json`

The benchmark is fixed at `p=0.001`. The surface baseline is a single-logical
rotated surface patch table; copied surface multi-logical results are computed
from that single-logical patch with `1 - (1 - P_single)^k`.

## Command Form

The installed entry point is `autoqec-search`, so an installed checkout can use
commands such as `autoqec-search preflight --root .`. The blocks below use the
source-checkout form so they run before installation.

Installed command examples for the full quantum Tanner path:

- `autoqec-search generate-quantum-tanner-candidates --root . --config campaigns/examples/quantum-tanner-autoresearch/generator.json --dry-run`
- `autoqec-search find-upper-bound-witness --hx <hx.json> --hz <hz.json> --basis x --out <witness.json> --qec-code-bin /path/to/qec-code --iterations 1000 --restarts 8 --seed 12345 --timeout-seconds 300`
- `autoqec-search attach-quantum-tanner-witnesses --root . --campaign quantum-tanner-autoresearch --fixture-catalog campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json --witness-dir campaigns/examples/quantum-tanner-autoresearch/witnesses --basis x --qec-code-bin /path/to/qec-code`
- `autoqec-search validate --root .`
- `autoqec-search run --root . --campaign quantum-tanner-autoresearch --wall-clock 90s --run-id local-qt-p001 --distance-method random-window-upper-bound`
- `autoqec-search report --root .worktrees/local-qt-p001 --run results/search/quantum-tanner-autoresearch/local-qt-p001`
- `autoqec-search compare-surface-copy --root .worktrees/local-qt-p001 --run results/search/quantum-tanner-autoresearch/local-qt-p001 --baseline benchmarks/baselines/rotated-surface-single-logical-p001.json --out /tmp/quantum-tanner-surface-copy.html`

## Repeatable Smoke Demo

From a clean checkout with `qec-code`, `rsinter`, Python dependencies, and the
Rust distance-ladder binary available or buildable:

```bash
QEC_CODE_BIN=$(command -v qec-code) RSINTER_BIN=$(command -v rsinter) scripts/smoke_quantum_tanner_autoresearch.sh --work-root /tmp/autoqec-qt-smoke
```

The smoke script clones the checkout into `/tmp/autoqec-qt-smoke/checkout`,
generates only the d4/d6 quantum Tanner candidates from `generator.json`,
attaches X-basis upper-bound witnesses, runs the p=0.001 rbposd OSD10 suite
with 64 shots and seed 12345, and writes the surface-copy comparison beside the
run artifacts.

Expected PASS summary includes:

```text
frontier_size=2
crashes=0
quantum-tanner-toric-d4 p=0.001 ler=0
quantum-tanner-toric-d6 p=0.001 ler=0
surface_copy_status=ok
surface_copy_rows=2
surface_copy_accepted=1
surface_copy_rejected=1
```

The run artifacts are under
`/tmp/autoqec-qt-smoke/checkout/.worktrees/qt-smoke/results/search/quantum-tanner-autoresearch/qt-smoke/`.
The comparison files are written there as `surface-copy-comparison.json` and
`surface-copy-comparison.html`.

Negative control:

```bash
QEC_CODE_BIN=$(command -v qec-code) RSINTER_BIN=$(command -v rsinter) scripts/smoke_quantum_tanner_autoresearch.sh --work-root /tmp/autoqec-qt-smoke-bad --check-bad-observables
```

This intentionally supplies one explicit X observable row for a k=2 Tanner
candidate and requires:

```text
explicit X observables define 1 rows, expected k = 2
```

## 1. Generate Candidate Inputs

The committed fixture files are review fixtures. To regenerate the quantum
Tanner autoresearch inputs from the sweep config, first preview the exact
candidate ids and output paths:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli generate-quantum-tanner-candidates --root . --config campaigns/examples/quantum-tanner-autoresearch/generator.json --dry-run
```

The dry run prints the planned `[4, 6]` distance ladder candidates and does not write specs, matrix artifacts, the distance-ladder manifest, the fixture catalog, or the search space.

After reviewing the preview, run the materializing command with an explicit
`qec-code` executable:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli generate-quantum-tanner-candidates --root . --config campaigns/examples/quantum-tanner-autoresearch/generator.json --qec-code-bin /path/to/qec-code --force
```

This writes generated toric specs, the distance-ladder manifest, finite CSS
instance artifacts, `generated_fixture_catalog.json`, and the campaign
`search_space.json`.

The generator does not find or install upper-bound witnesses; witness finding is a separate later step.
Candidate generation only creates finite CSS inputs. Attach witnesses before
running autoresearch.

## 2. Attach Upper-Bound Witnesses

After candidate generation, run the witness attachment command against the
generated fixture catalog and the campaign search space:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli attach-quantum-tanner-witnesses --root . --campaign quantum-tanner-autoresearch --fixture-catalog campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json --witness-dir campaigns/examples/quantum-tanner-autoresearch/witnesses --basis x --qec-code-bin /path/to/qec-code
```

For a single candidate, find the witness directly before batch attachment:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli find-upper-bound-witness --hx benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d4/hx.json --hz benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d4/hz.json --basis x --out campaigns/examples/quantum-tanner-autoresearch/witnesses/quantum-tanner-toric-d4-upper-bound-witness.json --qec-code-bin /path/to/qec-code --iterations 1000 --restarts 8 --seed 12345 --timeout-seconds 300
```

The witness finder is running in the memory-X screening path. It requires generated witnesses to be X-like. Z-like witnesses can remain valid generic CSS witnesses, but they are incompatible with this memory-X screening task.

If a batch run needs to carry the same search budget across every candidate, use
the source-checkout form with explicit batch parameters:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli attach-quantum-tanner-witnesses --root . --campaign quantum-tanner-autoresearch --fixture-catalog campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json --witness-dir campaigns/examples/quantum-tanner-autoresearch/witnesses --basis x --qec-code-bin /path/to/qec-code --iterations 1000 --restarts 8 --seed 12345 --timeout-seconds 300
```

This updates `campaigns/examples/quantum-tanner-autoresearch/search_space.json`
in place and writes deterministic witness files under
`campaigns/examples/quantum-tanner-autoresearch/witnesses/`, such as:

- `campaigns/examples/quantum-tanner-autoresearch/witnesses/quantum-tanner-toric-d4-upper-bound-witness.json`
- `campaigns/examples/quantum-tanner-autoresearch/witnesses/quantum-tanner-toric-d6-upper-bound-witness.json`

The default mode is partial-success summary mode. The command prints counts like
`attached=2 skipped=0 failed=0`, writes the updated search space, and records
the batch result at the deterministic summary path
`campaigns/examples/quantum-tanner-autoresearch/witnesses/witness_finder_summary.json`.
If a candidate already has `upper_bound_witness_path`, or if the witness file is
already present and `--force` is not set, that candidate is reported as
`skipped` and preserved.

When some candidates are skipped or fail, inspect
`campaigns/examples/quantum-tanner-autoresearch/witnesses/witness_finder_summary.json`
immediately for counts, candidate ids, and reasons. After running
autoresearch/screening, inspect each candidate's run-tree
`screening.json` under
`.worktrees/<run-id>/results/search/quantum-tanner-autoresearch/<run-id>/candidates/<candidate-id>/screening.json`
for the detailed outcome.

Use strict mode when the operator wants a nonzero exit on incomplete witness
coverage. `--require-all` exits with status 1 if any candidate is skipped or
failed. `--fail-on-skipped` exits with status 1 when any candidate is skipped,
even if none failed. In both strict modes, the command still writes the summary
JSON and any requested output search-space file before exiting nonzero.

Strict mode examples:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli attach-quantum-tanner-witnesses --root . --campaign quantum-tanner-autoresearch --fixture-catalog campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json --witness-dir campaigns/examples/quantum-tanner-autoresearch/witnesses --basis x --qec-code-bin /path/to/qec-code --require-all
```

```bash
PYTHONPATH=src python3 -m autoqec_search.cli attach-quantum-tanner-witnesses --root . --campaign quantum-tanner-autoresearch --fixture-catalog campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json --witness-dir campaigns/examples/quantum-tanner-autoresearch/witnesses --basis x --qec-code-bin /path/to/qec-code --fail-on-skipped
```

These witness JSON files are upper-bound screening inputs for
`random-window-upper-bound`, not exact distance evidence. They are used to
screen candidates before spending decoder time, and they must not be treated as
exact Zoo distance data. These upper-bound witnesses are screening evidence only
and must not be promoted as exact Zoo distance evidence.

After witness attachment, validate the workspace before any run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

## 3. Preflight

Run preflight before spending decoder time. This checks the workspace
contracts, fixture records, and local `rsinter` availability, and writes an HTML
doctor page for review.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root . --html /tmp/autoqec-qt-preflight.html
```

Approval gate: open `/tmp/autoqec-qt-preflight.html` or read the terminal table.
Do not continue to a run until the failures are understood. A missing `rsinter`
backend is a local setup problem, not something to hide in chat.

## 4. Validate the Campaign Workspace

Validate the campaign, benchmark suite, fixture catalog, and any committed run
artifacts. This is the static contract check for the workflow inputs.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Review these files before approving a run:

- `campaigns/examples/quantum-tanner-autoresearch/search_space.json`
- `campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json`
- `benchmarks/suites/quantum-tanner-rbposd-p001-v1.json`
- `benchmarks/tasks/quantum-tanner-css-memory-x-rbposd-p001-v1.json`
- `benchmarks/baselines/rotated-surface-single-logical-p001.json`

## 5. Start a Local Smoke Run

Use a fresh run id. The example run id is `local-qt-p001`; change it only if
that branch or worktree already exists. The command creates branch
`autoresearch/local-qt-p001` and linked worktree `.worktrees/local-qt-p001/`.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign quantum-tanner-autoresearch --wall-clock 90s --run-id local-qt-p001 --distance-method random-window-upper-bound
```

Expected run root:
`.worktrees/local-qt-p001/results/search/quantum-tanner-autoresearch/local-qt-p001/`.

Expected run-level artifacts:

- `run_spec.json`
- `env.json`
- `experiment-log.tsv`
- `leaderboard.csv`
- `frontier.json`
- `strategy_trace.json`
- `summary.md`
- `run-summary.html`
- `report.html`
- `construction-definitions.html`
- `run_status.json`
- `promotion_summary.json`

After the generated `[4, 6]` workflow above, expected candidate artifacts live
under `candidates/quantum-tanner-toric-d4/` and
`candidates/quantum-tanner-toric-d6/`. Inspect `screening.json` first.

In the committed smoke search space, `quantum-tanner-toric-d8` is also present:
d4 is admitted by a valid upper-bound witness, d6 is skipped because it has no
upper-bound payload, and d8 fails because its witness is invalid.

Upper-bound distances are screening evidence only. The rule is that
upper-bound distances must not be promoted as exact Zoo distances, and
`promotion_summary.json` must be read with that rule in mind.

## 6. Resume Instead of Restarting

If the run stops on wall-clock budget or local interruption, resume the same
run id. Resume uses the existing `autoresearch/local-qt-p001` branch and
`.worktrees/local-qt-p001/` worktree.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign quantum-tanner-autoresearch --wall-clock 15m --run-id local-qt-p001 --resume
```

Approval gate: review the latest `experiment-log.tsv`, `run_status.json`,
`screening.json` files, and git commits on `autoresearch/local-qt-p001` before
deciding to resume.

## 7. Regenerate the Run Report

Autoresearch finalization writes `report.html` automatically. Re-run the report
command after manual inspection or after checking out the autoresearch branch.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli report --root .worktrees/local-qt-p001 --run results/search/quantum-tanner-autoresearch/local-qt-p001
```

Review
`.worktrees/local-qt-p001/results/search/quantum-tanner-autoresearch/local-qt-p001/report.html`
and the compact
`.worktrees/local-qt-p001/results/search/quantum-tanner-autoresearch/local-qt-p001/run-summary.html`.

Codex CLI can wait on shell commands without spending tokens on wall-clock
time. The operator should summarize command outcomes into the run artifacts and
review notes instead of streaming long decoder logs into chat.

## 8. Build the Surface-Copy Comparison

Run the comparison from the original checkout root after the Tanner run exists
in `.worktrees/local-qt-p001/`.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-surface-copy --root .worktrees/local-qt-p001 --run results/search/quantum-tanner-autoresearch/local-qt-p001 --baseline benchmarks/baselines/rotated-surface-single-logical-p001.json --out /tmp/quantum-tanner-surface-copy.html
```

This writes `/tmp/quantum-tanner-surface-copy.html` and
`/tmp/quantum-tanner-surface-copy.json`. The comparison uses only Tanner points
whose manifest records `logical_failure_aggregation: "any_logical"`. It chooses
the largest odd surface distance `d` satisfying `k*d*d <= n`, then computes the
copied block surface logical failure probability from the single patch with
`1 - (1 - P_single)^k`.

Approval gate: compare the HTML and JSON with the Tanner `report.html` before
copying conclusions into a report or PR. Rejected comparison rows are evidence
of incompatible units or budgets, not losses.

## 9. Final Review Checklist

- Preflight output was reviewed before running.
- Witnesses were attached after candidate generation and before the run.
- `validate --root .` passed before running.
- The run id and wall-clock budget were chosen by a human operator.
- Every candidate has a visible `screening.json`.
- Admitted Tanner points use `p=0.001`.
- Surface-copy comparison used
  `benchmarks/baselines/rotated-surface-single-logical-p001.json`.
- Upper-bound distances were not treated as exact Zoo-promotion evidence.
- Cluster execution was deferred to GitHub issue #20.
