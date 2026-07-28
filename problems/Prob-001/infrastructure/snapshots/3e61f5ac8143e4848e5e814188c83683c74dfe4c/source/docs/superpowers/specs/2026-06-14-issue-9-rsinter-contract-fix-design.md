# Issue #9 Rsinter Contract Fix Design

## Context

Issue #9 already has a merged implementation in PR #22, but the real end-to-end
check still fails against the current local GitHub/dev `rsinter`. The failing
command is:

```sh
PYTHONPATH=src python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-baseline --distance 3 --decoder rmatching-default-v1 --p 0.005 --run-id codex-issue9-check
```

The failure is a TOML schema mismatch: AutoQEC writes a partial `[[runner]]`
spec, while `rsinter` expects a complete benchmark spec. After fetching the
latest local `rstim` repository, the relevant `rsinter` contract is unchanged:
`BenchmarkSpec` requires top-level `name`, `version`, `mode`, `runner`, and
`plot`; each runner requires `name`, `language`, `impl_key`, and `params`; and
runner params require `batch_size`.

There is a second contract mismatch after TOML parsing: real `rsinter` writes
`BenchmarkResultRow` JSONL records with `runner`, `params`, and `metrics`,
whereas AutoQEC's fake test runner currently emits a flat row with
`decoder_id`, `task_id`, `shots`, and `errors`.

## Scope

This fix is intentionally limited to AutoQEC. It completes issue #9 by making
the existing `autoqec-search eval` command work against the current real
`rsinter` CLI. It does not change `rstim` or `rsinter`, and it does not switch
issue #9 from rotated-surface distance-driven input to the newer `input_type =
"css"` path.

If `rsinter`'s current ergonomics prove awkward, we will file upstream issues
after this AutoQEC adapter is working.

## Chosen Approach

Use a strict current-contract adapter:

- Generate a complete `rsinter` benchmark TOML spec.
- Parse only the real `BenchmarkResultRow` JSONL shape in production paths.
- Keep AutoQEC's internal manifest schema unchanged.
- Update tests so the fake `rsinter` emits the real row shape, preventing this
  integration drift from recurring.

The runner `name` in the generated TOML will be the AutoQEC `decoder_id`
(`rmatching-default-v1`, etc.). This preserves the existing AutoQEC path
expectation:

```text
rsinter/out/<decoder_id>/test-run/results.jsonl
```

The runner `impl_key` remains the actual `rsinter` registry key such as
`rmatching`, `rbposd`, or `rilpqec`.

## Components

### TOML Generation

`src/autoqec_search/rsinter.py::write_spec_toml` will write:

```toml
name = "autoqec-rotated-memory-x-cdep-v1"
version = 1
mode = "independent"

[[runner]]
name = "rmatching-default-v1"
language = "rust"
impl_key = "rmatching"

[runner.params]
distance = [3]
rounds = [3]
p = [0.005]
max_shots = 100000
max_errors = 1000
batch_size = 256

[plot]
title = "AutoQEC rotated-memory-x-cdep-v1"

[plot.x]
field = "params.p"
scale = "log"
label = "Physical Error Rate"

[plot.series]
group_by = ["runner", "params.distance"]
label_template = "{runner} d={params.distance}"

[[plot.panel]]
metric = "metrics.logical_error_rate"
scale = "log"
label = "Logical Error Rate"
```

`batch_size` will be sourced from task collection metadata if present and will
otherwise default to `256`, matching the current `rsinter` examples.

### JSONL Parsing

`parse_results_jsonl` will read real `BenchmarkResultRow` records:

- `runner` must equal the expected AutoQEC decoder id.
- `status` must be `ok`.
- `params.p` must be one of the selected p values.
- `params.rounds` must be a positive integer.
- `params.distance`, when present, must match the copied candidate distance.
- `metrics.shots_used` becomes AutoQEC `shots`.
- `metrics.logical_errors` becomes AutoQEC `errors`.
- `metrics.logical_error_rate` is validated against `errors / shots` when
  shots are positive.
- Wilson confidence intervals continue to be computed by AutoQEC.

Malformed rows, duplicate p values, missing p values, unknown p values,
non-finite metrics, failed statuses, and logical errors exceeding shots will
raise `SearchIntegrityError` with path and line context.

### Eval Orchestration

`eval_run.py` will continue to call `write_spec_toml`, `run_rsinter`, and
`parse_results_jsonl` in the same order. It will pass the copied distance into
the parser for distance validation. The run staging and atomic rename behavior
remain unchanged.

## Testing

Focused tests:

- Update TOML unit tests to assert top-level benchmark fields, runner `name`,
  `impl_key`, `batch_size`, and `[plot]`.
- Update JSONL parser tests to use real `BenchmarkResultRow` fixtures.
- Keep negative parser tests for malformed JSONL, duplicate p values, missing
  p values, unexpected runner, failed status, invalid metrics, and errors
  exceeding shots.
- Update the fake `rsinter` in CLI tests to parse the generated TOML enough to
  emit realistic `BenchmarkResultRow` records under `out/<runner>/test-run/`.

Verification commands:

```sh
python3 -m pytest tests/test_search_rsinter.py tests/test_search_eval_cli.py -q
python3 -m pytest tests/test_search_docs.py tests/test_search_plot.py tests/test_search_eval_schemas.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-baseline --distance 3 --decoder rmatching-default-v1 --p 0.005 --run-id codex-issue9-real-check
```

The real eval verification must create `candidate-plot.svg`,
`distance.json`, `structure.json`, and a completed manifest for
`rmatching-default-v1`.

## Upstream Rsinter Follow-Ups

After AutoQEC works, consider filing upstream `rsinter` issues for:

- `bench run` requiring `[plot]` even when only running benchmarks.
- `batch_size` being mandatory without a documented/default value.
- Ambiguous TOML parse errors such as `missing field name`, which do not say
  whether the missing field is top-level or runner-level.

These are usability improvements, not blockers for completing issue #9.
