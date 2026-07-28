# Issue #19 Benchmark Skills And Compare-Candidates Design

## Goal

Complete AutoQEC issue #19 by adding the full issue #5 benchmark skill series
and a review-oriented candidate comparison workflow.

The work should deliver:

- `skills/benchmark-code/`
- `skills/bench-runner-distance/`
- `skills/bench-runner-mc-ler/`
- `skills/compare-candidates/`
- a first-class `autoqec-search compare-candidates` command
- a self-contained comparison report that ranks comparable candidates and names
  a winner when the data supports one

The central design choice is to keep the benchmark skills thin. They should
drive the existing M1/M2 search layer rather than reimplementing evaluation,
distance, rsinter dispatch, report rendering, or promotion.

## Context Read

Issue #19 builds on:

- #3 search architecture: campaigns, benchmark contracts, runtime results, and
  Zoo promotion are separate layers.
- #5 benchmark skill proposal: `benchmark-code` orchestrates intake, preflight,
  dispatch, and render; per-benchmark runner skills own the run stage.
- #9 through #13 M1 pipeline: preflight, eval, run, report, promotion, and
  `search-campaign` are already implemented.
- #14 through #18 M2 pipeline: strategy, distance method contract, decoder
  registry, general CSS adapter, and BB72 qLDPC smoke campaign are already
  available.
- PR #36: the BB72 AutoQEC-side campaign path is committed as an OSD1 smoke run;
  strict published BB72 OSD10/reference-curve reproduction is now tracked on
  the rstim side, not as a blocker for issue #19.

The repository already has reusable machinery in:

- `autoqec-search preflight`
- `autoqec-search eval`
- `autoqec-search run`
- `autoqec-search report`
- `autoqec-search promote`
- `autoqec_search.report.build_report_model`

Issue #19 should add the missing conversation and review surfaces around those
capabilities, plus the real missing comparison module.

## Scope

In scope:

- Add four project skills under `skills/`.
- Add concise examples or transcripts where useful to show approval gates and
  negative paths.
- Add `src/autoqec_search/compare_candidates.py`.
- Add CLI command:

  ```bash
  PYTHONPATH=src python3 -m autoqec_search.cli compare-candidates \
    --root . \
    --run results/search/<campaign-a>/<run-a> \
    --run results/search/<campaign-b>/<run-b> \
    --out /tmp/autoqec-candidates.html
  ```

- Write sibling comparison artifacts:
  - `<out>.html`
  - `<out>.json`
- Compare completed run points by shared task, decoder, and physical error
  rate.
- Render an offline-safe HTML table/report with embedded JSON and no network
  assets.
- Fail clearly for incomparable runs.
- Add tests for skill documents, comparison model behavior, CLI behavior, and
  offline report rendering.
- Update README and CLAUDE documentation with the new skill/CLI entry points.

Out of scope:

- A new benchmark execution abstraction below `autoqec-search eval/run`.
- A replacement for rsinter dispatch.
- New decoder backends.
- Full BB72 published-reference reproduction.
- Cross-task scientific normalization such as surface-vs-BB ranking across
  different benchmark tasks.
- Cryochamber or message-surface delivery.
- Automatic Zoo promotion decisions from comparison reports.

## Main Decision

Use a thin-skill plus focused-core-module design.

The benchmark skills should be conversation-first wrappers over existing CLI
commands. They should collect intent, run preflight, summarize the execution
plan, require explicit approval, and then dispatch to existing commands.

The comparison workflow should be a real Python module because it has durable
logic that should be testable outside an agent transcript:

- loading and normalizing multiple run directories
- deciding whether runs are comparable
- computing LER and distance deltas
- interpreting confidence interval overlap
- choosing strong or tentative winners
- rendering comparison artifacts

This keeps issue #19 small enough to implement safely while giving it concrete
verification teeth.

## Skill Series

### `benchmark-code`

`benchmark-code` is the top-level orchestrator skill.

It handles:

- natural-language intake
- target resolution at the level of campaign, run, candidate, or Zoo instance
- benchmark type selection: `distance` or `mc-ler`
- preflight routing
- execution summary
- explicit approval before running or writing run artifacts
- dispatch to `bench-runner-distance` or `bench-runner-mc-ler`
- final pointer to generated run/report paths

It does not:

- implement distance algorithms
- call rsinter directly
- parse manifests itself
- promote results into the Zoo without a separate user decision

The approval gate should follow the existing `search-campaign` style. Phrases
such as "approved", "looks good", or "run it" count as approval. Phrases such
as "wait", "not yet", "show me first", or "do not write yet" do not.

### `bench-runner-distance`

`bench-runner-distance` is the deterministic distance benchmark runner.

It supports two common paths:

1. Inspect an existing run/candidate directory and report `distance.json`.
2. Dispatch an existing campaign candidate through `autoqec-search eval`, which
   writes structure and distance artifacts as part of the standard candidate
   evaluation path.

Rules:

- Exact distance results must have `bound_type: "exact"` when the field is
  present.
- Upper-bound or unavailable distances may be summarized, but must not be
  presented as exact or promotion-safe.
- Rotated surface `d=3` should report exact distance `3`.
- Missing backend or missing instance data should stop with a precise message.
- The skill should not overwrite curated Zoo distance data.

### `bench-runner-mc-ler`

`bench-runner-mc-ler` is the Monte Carlo logical-error-rate runner.

It supports:

- single-candidate runs through `autoqec-search eval`
- campaign sweeps through `autoqec-search run`
- report generation through `autoqec-search report`
- decoder and p-value filters already supported by the eval path

Rules:

- Run `autoqec-search preflight` before proposing execution.
- Summarize selected campaign, suite, task, decoders, p-list, run id, and
  budget before asking for approval.
- If rsinter or general CSS support is absent, stop at preflight and preserve
  the precise missing-dependency message.
- Do not imply that the BB72 OSD1 smoke run satisfies the deferred OSD10
  published-reference criterion.
- Use committed or fixture-backed M1 data for fast verification; real rsinter
  smoke tests can remain optional.

### `compare-candidates`

`compare-candidates` is the review skill.

It should guide a user through selecting two or more run directories, explain
what comparability means, call `autoqec-search compare-candidates`, and present
the generated report path. It should refuse to summarize incomparable runs as a
ranked comparison.

This skill is the human-facing front door for the new core comparison command.

## Compare-Candidates Data Model

The command loads each run with:

```python
build_report_model(root, run_root)
```

The comparison model should contain:

- input run paths
- run provenance from each report model
- skipped/placeholder/crash counts
- comparable keys
- per-key candidate rows
- winner assessment per key
- overall winner when all comparable keys agree
- explicit incomparable reason when no shared keys exist

The default comparability key is:

```text
(task_id, decoder_id, p)
```

Only completed manifest points participate in ranking. Placeholder and crash
manifests are reported as skipped counts, not silently treated as poor
performance.

For each shared key, each run contributes its best point by lowest LER. The row
includes:

- run label
- run path
- campaign id
- run id
- candidate id
- task id
- decoder id
- decoder parameters
- distance
- physical error rate `p`
- rounds
- shots
- errors
- LER
- confidence interval low/high
- distance delta relative to the best-distance row
- LER delta relative to the lowest-LER row

Winner classification:

- `strong`: the lowest-LER point's CI upper bound is below every other
  completed point's CI lower bound for that key.
- `tentative`: the lowest-LER point is lower by point estimate, but at least
  one CI overlaps.
- `tie`: equal point estimates within exact floating comparison or all CIs
  overlap without a unique lower-LER point.
- `incomparable`: fewer than two runs have a completed point for that key.

For multiple shared keys, the overall winner is strong only if the same run is
the strong winner for every comparable key. If winners disagree or only
tentative winners exist, the overall result should say that no single clear
winner is established, while still showing per-key rankings.

## CLI Behavior

Add a parser subcommand:

```bash
autoqec-search compare-candidates \
  --root . \
  --run <run-a> \
  --run <run-b> \
  [--run <run-c> ...] \
  [--label <label-a> --label <label-b> ...] \
  --out <path>
```

Rules:

- Require at least two `--run` values.
- Relative run paths resolve under `--root`, matching the existing `report`
  command.
- If labels are supplied, their count must match the run count.
- If `--out` has any extension, write normalized sibling files by replacing the
  suffix with `.html` and `.json`.
- Write artifacts before returning success.
- For incomparable runs, return nonzero and do not claim a winner. It is
  acceptable to write a diagnostic HTML/JSON artifact if the model clearly says
  `status: "incomparable"`.

The initial command should not have `--allow-cross-task`. Cross-task ranking is
a research-design decision and should be handled by a later issue when there is
a principled normalization rule.

## Report Rendering

The HTML report should be self-contained and static:

- inline CSS
- inline table markup
- embedded JSON model in a `<script type="application/json">` or escaped `<pre>`
- no external fonts
- no external JavaScript
- no `http://` or `https://`

Sections:

1. title and provenance
2. comparison status
3. overall winner or no-clear-winner note
4. per-key ranking table
5. skipped run/manifests summary
6. embedded comparison JSON

The report should avoid plotting in the first implementation. A ranked table
with CI intervals is enough for issue #19 and is easier to verify robustly.
Plots can be added later if repeated comparisons need visual trend inspection.

## Error Handling

Clear failures:

- fewer than two runs
- run directory missing
- run not part of the search workspace
- malformed run artifacts
- no completed points in any run
- no shared `(task_id, decoder_id, p)` key across at least two runs
- label count mismatch
- invalid output path

The most important negative control is:

```text
incomparable runs: no shared task/decoder/p grid
```

This guards against the tempting but misleading surface-vs-BB ranking when the
benchmark tasks differ.

## Testing

Add skill-document tests, either in `tests/test_search_e2e.py` or a focused
`tests/test_benchmark_skills.py`, checking that all four skills exist and
document:

- explicit approval gates
- preflight before execution
- distance and MC-LER dispatch
- missing-backend blocking
- compare-candidates run directory input
- incomparable-run refusal

Add `tests/test_search_compare_candidates.py` covering:

- comparable synthetic runs with the same task, decoder, and p value
- strong winner when confidence intervals do not overlap
- tentative winner when confidence intervals overlap
- no overall clear winner when per-key winners disagree
- distance and LER deltas in the model
- incomparable error for disjoint task/decoder/p grids
- HTML contains comparison status, winner wording, table data, and embedded JSON
- HTML contains no `http://` or `https://`
- CLI writes `.html` and `.json`
- CLI returns nonzero for incomparable runs

Regression commands:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_compare_candidates.py \
  tests/test_search_e2e.py \
  tests/test_search_cli.py \
  -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

A broader final verification may use:

```bash
PYTHONPATH=src python3 -m pytest -q
```

## Documentation

Update README and CLAUDE with:

- the benchmark skill series
- when to use `benchmark-code`
- when to use each runner skill directly
- the `compare-candidates` command
- the fact that comparison requires shared task/decoder/p grids
- a warning that BB72 OSD1 smoke artifacts are AutoQEC orchestration proof, not
  the deferred published OSD10 reference validation

## Acceptance Criteria

Issue #19 is complete when:

- all four skills exist and pass source tests
- `autoqec-search compare-candidates` exists
- comparable runs produce a JSON and offline HTML comparison report
- the report names a strong winner when lower LER has non-overlapping CIs
- overlapping CIs produce a tentative winner rather than an overstated claim
- different-task runs fail with a clear incomparable-runs error
- distance runner documentation verifies rotated surface `d=3` distance `3`
- MC-LER runner documentation routes through existing eval/run/report workflow
- preflight/missing-backend behavior is documented and tested
- search workspace validation still passes

## Implementation Notes

The implementation should prefer reusing existing report and loader functions.
If `compare_candidates.py` needs a small helper to load report models, keep it
inside that module rather than broadening `report.py`.

The comparison renderer can mirror the style of `strategy_compare.py`: build a
plain Python model, render deterministic HTML, and write sibling JSON/HTML
artifacts. That pattern is already tested and familiar in this codebase.

No implementation should run expensive real rsinter benchmarks as part of the
default test suite. Use committed artifacts or synthetic run directories for
fast CI; optional real-backend smoke commands can be documented separately.
