# Issue #17 General CSS Adapter Design

## Goal

Integrate the upstream rstim general CSS codegen into AutoQEC so
`autoqec-search eval` can benchmark a candidate from its stored `hx/hz`
artifacts through the code-family-agnostic CSS path. The implementation should
prove the new path by re-evaluating the rotated-surface d=3 candidate through
the general CSS adapter and checking that its logical error rate remains inside
the committed M1 golden fixture confidence band. The committed fixture is
`rotated-memory-x-cdep-v1` at `p = 0.005`, so the reproduction path must use a
fixture-compatible task instead of comparing the current z-basis baseline point
against an x-basis fixture.

This is the AutoQEC-side consumer of upstream `nzy1997/rstim#46`, implemented
in rstim PR #51. AutoQEC should not reimplement syndrome-extraction circuit
generation. It should translate candidate artifacts into the `rsinter`
`input_type = "css"` benchmark contract, run the backend, and preserve the
existing result-manifest, leaderboard, report, and promotion contracts.

## Context

M1 can evaluate rotated surface codes because the current AutoQEC adapter writes
an `rsinter` spec with `distance`, `rounds`, and `p`, and `rsinter` builds the
surface circuit internally. That path is useful as a baseline, but it cannot
benchmark arbitrary finite CSS instances stored as `hx.json` and `hz.json`.

rstim PR #51 adds the missing upstream path. `rsinter` runner params can now
include:

- `input_type = "css"`
- `code_id`
- `hx`
- `hz`
- `basis`
- `schedule`
- optional `observables`
- `rounds`
- `p`
- collection controls such as `max_shots`, `max_errors`, and `batch_size`

The `hx`, `hz`, and optional `observables` fields are paths relative to the
spec file directory unless absolute. The CSS matrix JSON wrapper accepted by
rstim uses formats such as `{"format":"dense","rows":[...]}` or
`{"format":"sparse_rows","num_cols":N,"rows":[...]}`.

AutoQEC currently stores finite instances as dense binary JSON:

```json
{
  "format": "dense_binary_matrix",
  "n_rows": 4,
  "n_cols": 9,
  "data": [[0, 1]]
}
```

Issue #17 bridges these two contracts.

## Scope

In scope:

- a general CSS eval mode for `autoqec-search eval`
- conversion from AutoQEC dense matrix artifacts to rstim CSS matrix wrappers
- `rsinter` TOML generation for `input_type = "css"`
- surface d=3 verification through the general CSS path
- a narrow fixture-compatible task, suite, and campaign for the golden d=3
  reproduction point
- clear failure when the installed `rsinter` lacks upstream general CSS support
- negative control for noncommuting `hx/hz`
- compatibility with existing completed manifest, plot, leaderboard, report,
  and promotion consumers
- README and CLAUDE documentation for the new eval path

Out of scope:

- the BB qLDPC campaign and published BB reference-point verification
- generating new BB instances
- new distance-method registry work
- decoder registry or decoder-parameter changes from issue #16
- changing the existing surface-specific eval path into the default path
- changing the current `rotated-surface-baseline` campaign or z-basis task
  into an x-basis fixture campaign
- implementing CSS circuit generation inside AutoQEC

## Main Decision

Use an explicit general CSS adapter mode instead of silently replacing the
current surface path.

The existing surface adapter remains available and continues to write
surface-style `rsinter` specs. The new mode, exposed through a clear CLI option
such as `--general-css`, uses the same candidate-resolution, structure,
distance, backend-run, manifest, and plot pipeline, but writes CSS inputs and
CSS `rsinter` runner params.

This keeps M1 behavior stable, makes issue #17 verification unambiguous, and
gives issue #18 a concrete path to reuse for BB/qLDPC campaigns.

## Architecture

`src/autoqec_search/rsinter.py` owns the AutoQEC-to-rsinter translation. It
should grow a small adapter boundary rather than a broad new abstraction.

Recommended helper responsibilities:

- `write_surface_spec_toml(...)`: the current `distance`-based behavior,
  either extracted from or kept behind `write_spec_toml(...)`.
- `write_css_spec_toml(...)`: writes complete `rsinter` benchmark specs using
  `input_type = "css"`.
- `write_css_matrix_wrapper(...)`: converts AutoQEC `dense_binary_matrix`
  payloads into rstim CSS matrix wrapper files.
- `select_eval_adapter(...)` or equivalent orchestration logic: chooses surface
  or CSS mode from the explicit eval option.

`src/autoqec_search/eval_run.py` remains the single-candidate orchestration
layer. It should resolve the candidate exactly as it does today, run CSS
structure checks, copy artifacts, select the adapter, call `rsinter`, parse
results, and write the existing output artifacts.

No downstream artifact contract should fork for CSS mode. Completed
`manifest.json` records should keep the same `points` shape, and
`candidate-plot.svg`, `leaderboard.csv`, `summary.md`, `report.html`, and
promotion should continue to consume those manifests.

## Data Flow

For a general CSS eval run:

1. Resolve the candidate from the campaign or `--candidate` directory.
2. Copy `instance.json`, `hx.json`, and `hz.json` into
   `candidates/<candidate-id>/artifacts/`.
3. Compute `structure.json` with the existing `summarize_css_structure()`.
4. If `css_commute` is false, write the failing structure artifact when
   possible, skip backend execution, and exit nonzero.
5. Copy `distance.json` from the source instance exactly as the current eval
   path does.
6. Convert copied `artifacts/hx.json` and `artifacts/hz.json` into rstim CSS
   matrix wrapper files under `candidates/<candidate-id>/rsinter/input/`.
7. Write `candidates/<candidate-id>/rsinter/spec.toml` with relative paths from
   the spec directory to the CSS wrapper files.
8. Run `rsinter bench run --spec <spec.toml> --language rust --out <out-dir>`.
9. Parse each selected decoder's
   `rsinter/out/<decoder-id>/test-run/results.jsonl`.
10. Write completed or placeholder manifests in the existing
    `evaluations/<task-id>/<decoder-id>/manifest.json` layout.
11. Write `candidate-plot.svg`, `leaderboard.csv`, `summary.md`, `frontier.json`,
    `env.json`, and `run_spec.json` as today.

The run layout remains the same except for the additional
`rsinter/input/*.json` CSS wrapper files and CSS-specific params in
`spec.toml`.

## CSS Matrix Wrapper Contract

AutoQEC should use the rstim dense wrapper first:

```json
{
  "format": "dense",
  "rows": [[0, 1, 0]]
}
```

Conversion rules:

- source payload must be an object with `format = "dense_binary_matrix"`;
- `n_rows`, `n_cols`, and `data` must already pass the existing matrix
  validation used by `structure.py`;
- output rows preserve the source row order exactly;
- output paths should live under `rsinter/input/`, not under `artifacts/`, so
  original source artifacts remain unchanged;
- generated wrapper filenames should be stable, for example `hx.css.json` and
  `hz.css.json`.

The adapter should not require observables in issue #17. If no observables file
is supplied, rstim #51 uses canonical fallback. A future issue can add explicit
logical-observable artifacts if the BB campaign needs them.

## Rsinter Spec

The CSS spec should remain a complete current `rsinter` benchmark spec:

```toml
name = "autoqec-rotated-memory-z-cdep-v1"
version = 1
mode = "independent"

[[runner]]
name = "rmatching-default-v1"
language = "rust"
impl_key = "rmatching"

[runner.params]
input_type = "css"
code_id = "rotated-surface-code"
hx = "input/hx.css.json"
hz = "input/hz.css.json"
basis = "z"
schedule = "greedy"
rounds = [9]
p = [0.008]
max_shots = 100000
max_errors = 1000
batch_size = 256

[plot]
title = "AutoQEC rotated-memory-z-cdep-v1"
```

The `basis` should derive from the task observable:

- `logical_x` maps to `basis = "x"`;
- `logical_z` maps to `basis = "z"`;
- any other observable value fails clearly until intentionally supported.

The default CSS `schedule` should be `greedy`, matching rstim #51 defaults and
fixtures. If a future task adds an explicit schedule setting, it can override
this without changing the adapter boundary.

CSS mode should not write `distance = [...]` into runner params. The copied
`distance.json` remains AutoQEC's distance source for summaries, plots, reports,
and promotion.

## Result Parsing

`parse_results_jsonl()` already accepts real `BenchmarkResultRow` records and
treats `params.distance` as optional. That behavior should stay:

- surface rows may include `params.distance`;
- CSS rows may omit it;
- `params.p`, `params.rounds`, `metrics.shots_used`,
  `metrics.logical_errors`, and optional `metrics.logical_error_rate` remain
  required or validated as they are today.

The completed manifest builder does not need a CSS-specific branch.

## Error Handling

General CSS mode should fail before producing misleading completed manifests.

Expected failures:

- malformed `hx/hz`: fail during matrix validation;
- noncommuting `hx/hz`: write failing `structure.json` when possible, skip
  `rsinter`, exit nonzero;
- unsupported task observable: fail before writing a backend spec;
- missing or empty `rsinter --version`: reuse current backend discovery errors;
- installed `rsinter` too old or lacking CSS support: normalize known backend
  failures such as unknown `input_type`, missing CSS file fields, or unknown CSS
  basis into a clear message that upstream rstim general CSS support from #46
  / #51 is required;
- malformed, empty, partial, or failed `results.jsonl`: reuse the strict parser
  errors with path and line context.

Do not add a broad global preflight requirement for CSS in this issue. The eval
mode itself is the integration point and should fail clearly when the backend is
too old.

## CLI

Add an explicit switch to the existing eval command:

```sh
autoqec-search eval \
  --root . \
  --campaign rotated-surface-baseline \
  --distance 3 \
  --decoder rmatching-default-v1 \
  --p 0.008 \
  --general-css
```

The default without `--general-css` remains the existing surface-specific path.

The `--candidate <dir>` form should also accept `--general-css`, as long as the
candidate resolves to valid `artifacts/{instance,hx,hz}.json`.

For golden-fixture reproduction, add a narrow checked-in benchmark entry point,
for example:

- `benchmarks/tasks/rotated-memory-x-cdep-v1.json` with
  `observable = "logical_x"`, `noise_model = "circuit_depolarizing"`,
  `input_type = "stim-detector-error-model"`, `p_list = [0.005]`,
  `rounds_policy.multiplier = 1`, `rounds_policy.minimum = 3`, and collection
  settings matching `benchmarks/fixtures/rotated-d3`;
- `benchmarks/suites/rotated-surface-css-fixture-v1.json` selecting only that
  task and `rmatching-default-v1`;
- `campaigns/examples/rotated-surface-css-fixture/` selecting the existing
  rotated-surface d=3 candidate.

That gives the issue #17 acceptance command a precise target:

```sh
autoqec-search eval \
  --root . \
  --campaign rotated-surface-css-fixture \
  --distance 3 \
  --decoder rmatching-default-v1 \
  --p 0.005 \
  --general-css
```

The existing `rotated-surface-baseline` campaign remains the daily z-basis
baseline and should not be repurposed for fixture reproduction.

## Verification

Unit tests:

- AutoQEC dense matrix payloads convert to rstim CSS dense wrapper files.
- Invalid matrix payloads fail before spec generation.
- CSS `spec.toml` contains `input_type = "css"`, `code_id`, relative `hx` and
  `hz` paths, `basis`, `schedule`, `rounds`, `p`, and collection fields.
- CSS `spec.toml` does not contain `distance = [...]`.
- task `observable` maps to CSS basis correctly and rejects unsupported values.
- `parse_results_jsonl()` accepts CSS result rows that omit `params.distance`.

CLI tests with fake `rsinter`:

- `autoqec-search eval --general-css` for the main rotated-surface baseline
  completes with a manifest and plot.
- `autoqec-search eval --general-css --campaign rotated-surface-css-fixture
  --distance 3 --decoder rmatching-default-v1 --p 0.005` completes through the
  CSS adapter.
- The fake backend reads the generated CSS runner params rather than the legacy
  surface `distance` param.
- The completed fixture-campaign point at `p = 0.005` lies inside
  `benchmarks/fixtures/rotated-d3/expected.json`'s Wilson CI band.
- A noncommuting candidate fails before invoking fake `rsinter`.
- A fake old backend error is normalized to the upstream-required message.

Local real-backend smoke:

```sh
PYTHONPATH=src python3 -m autoqec_search.cli eval \
  --root . \
  --campaign rotated-surface-css-fixture \
  --distance 3 \
  --decoder rmatching-default-v1 \
  --p 0.005 \
  --run-id local-general-css-d3 \
  --general-css
```

The run should write `structure.json`, `distance.json`, a completed
`rmatching-default-v1` manifest, and `candidate-plot.svg`. Its LER at the
fixture point should lie inside the committed golden CI band.

If real-backend numeric equivalence differs because the current M1 committed
fixture uses the surface-specific circuit path, the fake-backend contract tests
remain the CI proof and the real smoke should be reported as a local compatibility
check rather than silently weakening the test.

## Documentation

Update README and CLAUDE search-layer guidance to describe:

- the existing surface path remains the default;
- `--general-css` runs through `hx/hz -> rstim CSS -> DEM -> decoder`;
- upstream rstim #46/#51 support is required;
- malformed or noncommuting `hx/hz` fail before backend execution;
- BB/qLDPC campaigns are still handled by issue #18.

## Implementation Notes

Keep the implementation narrow:

- do not modify curated Zoo source artifacts during eval;
- do not rewrite historical runs;
- do not add BB campaign files;
- do not couple this to decoder-registry parameter changes;
- keep result manifests as the durable downstream contract;
- prefer focused helpers in `rsinter.py` and `eval_run.py` over a new class
  hierarchy.
