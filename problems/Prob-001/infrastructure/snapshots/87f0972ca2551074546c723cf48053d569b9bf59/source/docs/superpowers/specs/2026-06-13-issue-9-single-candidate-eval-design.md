# Issue #9 Single-Candidate Evaluation Design

## Goal

Add a real `autoqec-search eval` workflow for evaluating one rotated-surface candidate end-to-end. The command creates a fresh search run, resolves one candidate, checks its CSS structure, copies its known distance from the Zoo when available, invokes `rsinter` for logical-error-rate sampling, writes real per-decoder manifests, renders a per-candidate LER-vs-p SVG plot, and prints a concise human-readable summary.

This is the issue #9 / M1-2 step after the Phase 1 search-layer contracts and preflight fixture work. It should not implement the multi-candidate loop, aggregate report, or promotion workflow.

## Scope

In scope:

- `autoqec-search eval`
- one candidate per command invocation
- fresh run creation under `results/search/<campaign>/<run-id>/`
- campaign-derived rotated-surface candidates selected by `--campaign ... --distance ...`
- external candidate directories selected by `--candidate <dir>`
- reuse of matching Zoo finite-instance artifacts when available
- strict `rsinter` execution through the real backend
- CLI filters for selected decoders and selected physical error rates
- real completed result manifests with pointwise LER data
- standalone SVG plotting for the evaluated candidate
- deterministic unit and CLI tests using a fake `rsinter`

Out of scope:

- multi-candidate orchestration
- campaign-wide aggregation
- HTML reports
- promotion into `zoo/`
- non-rotated-surface candidate generation beyond reusing existing artifacts
- fixture-results or offline eval mode in the production CLI

## Architecture

`autoqec-search eval` should be a real single-candidate evaluator rather than an extension of the placeholder `init-run` path. It creates a fresh run and writes the same high-level run artifacts as existing search runs, but with `mode: "eval"` and completed candidate outputs.

The evaluator has two candidate sources:

1. Campaign-derived source: `--campaign rotated-surface-baseline --distance 3` selects the candidate from the campaign/search-space context or builds an equivalent rotated-surface candidate spec.
2. Directory source: `--candidate <dir>` reads a preexisting candidate directory containing at least `candidate.json`.

Both sources normalize into one internal candidate object with `candidate_id`, `campaign_id`, `code_family`, `parameters`, and provenance before structure, distance, decoding, or plotting begins.

The campaign still selects the benchmark suite. The suite selects tasks and decoders; each task supplies `p_list`, collection budget, and rounds policy; each decoder config supplies the `rsinter` `impl_key` and language.

`rsinter` is a hard dependency. If it is missing, `rsinter --version` times out,
returns no version text, or exits nonzero, `eval` exits nonzero and does not
produce a successful manifest or plot. AutoQEC does not pin a release number;
compatibility is enforced by the benchmark spec and `BenchmarkResultRow`
contract checks.

## Candidate Artifact Resolution

For campaign-derived rotated-surface candidates, the evaluator should first search the existing Zoo instances for a finite CSS instance whose:

- `code_id` matches `rotated-surface-code`
- `parameters.distance` matches the requested distance
- `parameters.layout` matches `rotated`

For issue #9's expected d=3 path, this reuses:

```text
zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/
```

When a matching Zoo instance exists, the evaluator copies `instance.json`, `hx.json`, and `hz.json` into the fresh run under the candidate's `artifacts/` directory. If no matching Zoo instance exists for a supported rotated-surface candidate, the implementation may call the existing TensorQEC generator path to create those artifacts, but issue #9 still copies distance rather than computing it. That generated-missing path can proceed to decoding only if the candidate source supplies a recorded distance; otherwise it fails before `rsinter`.

For `--candidate <dir>`, the command accepts an existing candidate directory. If it contains `artifacts/instance.json`, `artifacts/hx.json`, and `artifacts/hz.json`, those artifacts are copied into the fresh run. If artifacts are absent, the evaluator resolves the candidate against matching Zoo instances by `code_family` and `parameters`, using the same rules as the campaign path.

Distance is copied, not recomputed. If the source `instance.json` has `derived_properties.distance`, `distance.json` records that value with `method: "copied-from-zoo-instance"` and source metadata. If no recorded distance is available, the first issue #9 implementation should fail clearly rather than computing or omitting distance.

## Run Layout

The fresh run layout should be:

```text
results/search/<campaign>/<run-id>/
  run_spec.json
  env.json
  leaderboard.csv
  summary.md
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
      out/<runner>/test-run/results.jsonl
    evaluations/<task-id>/<decoder-id>/manifest.json
    candidate-plot.svg
```

`candidate.json` records an evaluated candidate with `status: "evaluated"` and the same identity fields as placeholder candidates.

`structure.json` records:

- `status`
- `n`
- `k`
- `rank_hx`
- `rank_hz`
- `mx`
- `mz`
- `css_commute`

The structure stage computes GF(2) rank and verifies `Hx * Hz^T = 0 mod 2`. It computes `k = n - rank_hx - rank_hz`. If commutation fails, the command writes failing structure details, skips decoding and plotting, and exits nonzero.

`distance.json` records:

- `status`
- `distance`
- `method`
- `source_instance_id`
- `source_instance_path`

For reused d=3, the expected distance is `3`.

## Result Manifests

The result-manifest schema should evolve from placeholder-only records to accept completed evaluation records. Placeholder manifests must remain valid for existing Phase 1 example runs.

A completed manifest should contain top-level identity and execution fields:

- `campaign_id`
- `run_id`
- `candidate_id`
- `task_id`
- `decoder_id`
- `status: "completed"`
- `created_at`
- `tool_revisions`
- `points`

`points` is the authoritative pointwise evaluation data. Each point records:

- `p`
- `rounds`
- `shots`
- `errors`
- `ler`
- `ci_low`
- `ci_high`
- `seconds`

The evaluator computes `ler = errors / shots` and Wilson 95% confidence intervals locally. It rejects records where `shots <= 0`, `errors < 0`, or `errors > shots`.

`leaderboard.csv` may summarize one representative row per decoder, but it is not the source of truth. The pointwise data in `manifest.json` drives the plot and downstream checks.

## CLI

Add these forms:

```bash
autoqec-search eval --root . --campaign rotated-surface-baseline --distance 3
autoqec-search eval --root . --campaign rotated-surface-baseline --distance 3 --decoder rmatching-default-v1 --p 0.005
autoqec-search eval --root . --candidate path/to/candidate-dir --campaign rotated-surface-baseline
```

`--campaign` determines the suite and is required for both the campaign-derived and `--candidate` forms in issue #9. A future command can infer campaign from an existing run candidate, but this design keeps suite selection explicit.

`--distance` selects a rotated-surface candidate for the campaign-derived path.

`--candidate` accepts a directory containing at least `candidate.json`. The directory may contain artifacts, or it may rely on Zoo resolution.

Filters:

- `--decoder` may be repeated or comma-separated.
- `--p` may be repeated.
- selected decoders must be in the suite's decoder list.
- selected `p` values must be a subset of the task's `p_list`.
- with no filters, the command evaluates all suite decoders and all task `p_list` values.

Fresh run id defaults to a UTC timestamp plus an eval suffix, for example `2026-06-13T102039Z-eval`. `--run-id` supports deterministic tests. Existing run ids are rejected unless `--force` is supplied; `--force` only replaces that exact run directory.

## rsinter Adapter

Add a narrow adapter that:

1. writes `rsinter/spec.toml`;
2. creates one runner per selected decoder;
3. maps search-layer decoder ids to `impl_key`;
4. uses task settings for `p`, `max_shots`, and `max_errors`;
5. sets `distance=[d]`;
6. computes rounds from the task's `rounds_policy`.

For the existing `distance-scaled` policy with multiplier `1` and minimum `3`, d=3 uses rounds `3`.

The adapter runs:

```bash
rsinter bench run --spec <spec.toml> --language rust --out <out-dir>
```

The parser reads each `<out>/<runner>/test-run/results.jsonl`. It requires explicit `shots`, `errors`, `p`, and decoder identity. It rejects malformed JSONL, missing fields, empty output, partial runner output, unexpected decoder/task/p, and records whose errors exceed shots.

## Plotting

`candidate-plot.svg` is standalone and deterministic. It should:

- use log-log axes;
- draw one series per decoder;
- show visible point markers;
- include vertical CI intervals or bands;
- label selected physical error rates;
- include candidate id, distance, task id, and generated timestamp in a small footer;
- avoid network assets and browser-only rendering.

The SVG renderer should consume completed manifests, not raw `rsinter` output.

## Error Handling

The command fails with clear messages for:

- missing or invalid repository root;
- unknown campaign;
- missing suite/task/decoder references;
- invalid `--decoder` or `--p` filters;
- missing `rsinter`;
- unsupported or failing `rsinter`;
- candidate artifact resolution failure;
- missing copied distance;
- matrix shape or binary-format errors;
- CSS commutation failure;
- malformed or incomplete `results.jsonl`;
- missing plot inputs after decoding.

CSS commutation failure is a structured candidate failure: write `structure.json`, do not decode, do not plot, and exit nonzero.

## Testing

Use test-first coverage around the new boundaries.

Unit tests:

- GF(2) rank and commutation checks;
- `k = n - rank_hx - rank_hz`;
- campaign `--distance 3` reuses the checked-in Zoo instance;
- `--candidate <dir>` copies artifacts when present;
- missing recorded distance fails clearly;
- valid `results.jsonl` becomes manifest points;
- malformed JSONL, missing fields, unexpected p/decoder, empty output, and `errors > shots` fail specifically;
- SVG renderer emits one series per decoder and includes CI data.

CLI tests:

- fake `rsinter` executable writes deterministic `results.jsonl`;
- `eval --campaign rotated-surface-baseline --distance 3 --decoder rmatching-default-v1 --p 0.005 --run-id test-eval` exits 0 and writes all expected artifacts;
- missing `rsinter` fails before producing completed manifests or a plot;
- invalid decoder and p filters fail before invoking `rsinter`.

Slow/local verification with real `rsinter`:

```bash
autoqec-search eval \
  --campaign rotated-surface-baseline \
  --distance 3 \
  --decoder rmatching-default-v1 \
  --p 0.005 \
  --run-id local-rotated-d3-eval
```

Expected verification facts:

- command exits 0;
- `structure.json` reports `n=9`, `k=1`, and `css_commute=true`;
- `distance.json` reports distance `3` copied from the Zoo instance;
- `manifest.json` records completed point data;
- `candidate-plot.svg` opens as a valid standalone SVG;
- the LER at `p=0.005` lies inside the golden fixture CI band in `benchmarks/fixtures/rotated-d3/expected.json`.

## Open Decisions Resolved

- Fresh run, not enrichment of the placeholder example run.
- Reuse matching Zoo instances when present.
- Copy recorded distance from the Zoo instance; do not recompute in issue #9.
- Strictly fail when `rsinter` is unavailable; no production fixture-results mode.
- Support `--decoder` and `--p` filters from the start.
- Support `--candidate <dir>` from the start.
