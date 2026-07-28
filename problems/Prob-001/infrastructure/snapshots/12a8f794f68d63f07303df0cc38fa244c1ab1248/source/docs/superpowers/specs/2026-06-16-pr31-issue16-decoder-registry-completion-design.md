# PR31 Issue #16 Decoder Registry Completion Design

## Context

PR #31 implements the first decoder-registry layer for issue #16: decoder
configs are selected by ID, `rsinter` receives decoder parameters, completed
manifests preserve observed decoder parameters, and reports/plots can display
parameterized decoders.

The review found two gaps before the PR can honestly close issue #16:

- Decoder-parameter aliases are accepted inconsistently. In particular,
  `max_bp_iterations` is allowed as an `rbposd` alias, while AutoQEC's parser
  expects the canonical `bp_iters` key in result rows.
- Verification is still based on a rotated-surface smoke path. Issue #16 asks
  for a real fixed-code multi-decoder validation, including a BB/CSS instance,
  numeric evidence that `osd_order=10` improves over `osd_order=0`, result rows
  that record `osd_order`, and a predict-zeros negative control.

Local `rsinter` already supports `input_type = "css"` with `hx`, `hz`, optional
`observables`, `basis`, `schedule`, `rounds`, and `p`. It does not currently
expose its internal always-zero `VacuousDecoder` as a bench runner.

## Goal

Turn PR #31 from a parameterized rotated-surface registry smoke test into a
complete issue #16 implementation with:

- canonical decoder parameter handling across config, spec generation, parsing,
  manifests, leaderboards, plots, and reports
- a real CSS/BB evaluation path that passes committed Zoo instance matrices to
  `rsinter`
- a fixed multi-decoder BB validation artifact and CI coverage
- a real predict-zero decoder runner exposed by `rsinter` and consumed by
  AutoQEC as a negative control

## Non-Goals

This design does not add general BB parameter search over `m`, `n`, `vc`, or
`hd`. It adds the minimum explicit-instance path needed to evaluate a committed
CSS instance and validate decoder registry behavior.

This design does not add suite-level decoder parameter sweeps. Each concrete
decoder configuration remains a committed registry file under
`benchmarks/decoders/`.

This design does not require AutoQEC to own decoder implementations. Decoder
behavior remains in `rsinter`; AutoQEC owns registry, orchestration, artifacts,
and validation.

## Completion Criteria

PR #31 may keep `Closes #16` only when all of these are true:

- `autoqec-search validate --root .` and `autoqec-search preflight --root .`
  pass against the updated workspace.
- A real `rsinter` run evaluates one fixed BB/CSS instance with
  `rbposd-osd0-v1`, `rbposd-osd10-v1`, and `predict-zero-v1`.
- Result rows and completed manifests record canonical decoder parameters,
  including `osd_order` for both `rbposd` configurations.
- The submitted artifact or CI check proves
  `LER(rbposd-osd10-v1) < LER(rbposd-osd0-v1)` at the fixed validation point.
- The predict-zero run records a logical error rate in a wide control window,
  such as `0.35 <= LER <= 0.65`, on the same fixed task.
- Unknown decoder parameters fail validation or preflight before `rsinter` is
  invoked.
- The README and PR body describe the fixed instance and validation commands
  accurately. If the exact BB `[[72,12,6]]` provenance cannot be established,
  the PR must not claim that exact instance was used.

If the `rsinter` predict-zero companion change is not available, PR #31 should
drop `Closes #16` and describe itself as a partial decoder-registry
implementation.

## Design 1: Decoder Parameter Canonicalization

Add a small canonicalization layer for decoder parameters, shared by loading,
validation, preflight, TOML generation, and result parsing.

The external config contract remains compatible:

- `rbposd` accepts `bp_iters` as the canonical key.
- `rbposd` accepts `max_bp_iterations` as an input alias.
- A config that sets both keys is invalid.
- Unknown keys remain invalid.

The internal and artifact contract becomes canonical:

- AutoQEC writes `bp_iters` into generated `rsinter` TOML, even when the config
  used `max_bp_iterations`.
- Completed manifests, leaderboard rows, plot labels, report tables, and parser
  expectations use `bp_iters`.
- Result-row comparison canonicalizes observed backend params before checking
  them against expected decoder params.

This removes drift between legal config input and durable artifact output. It
also prevents the same decoder configuration from appearing as two distinct
series because one path used `bp_iters` and another used `max_bp_iterations`.

## Design 2: CSS/BB Evaluation Path

Extend AutoQEC's candidate resolution and `rsinter` spec generation to support
explicit Zoo instance candidates without assuming that every candidate has a
scalar `distance` parameter.

### Explicit Instance Candidates

Add an explicit-instance candidate path that points directly at a committed Zoo
instance directory:

```json
{
  "candidate_id": "bivariate-bicycle-code-m6-n6",
  "campaign_id": "decoder-registry-css-bb-smoke",
  "code_family": "bivariate-bicycle-code",
  "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
  "provenance": {
    "kind": "zoo-instance",
    "label": "fixed BB CSS decoder-registry validation instance"
  }
}
```

This path loads `instance.json`, `hx.json`, and `hz.json` from the instance
directory, validates that `instance.code_id` matches `code_family`, validates
that the CSS checks commute, and records the loaded instance parameters in
`candidate.json`.

The existing search-space and directory-candidate paths continue to require a
positive scalar `distance`. They are not widened to support array/object BB
generator parameters in this PR.

### Task Contract

Add a CSS memory task that is explicit about the input shape:

```json
{
  "id": "bb-css-memory-x-cdep-v1",
  "title": "BB CSS Memory X under circuit depolarizing noise",
  "observable": "logical_x",
  "noise_model": "circuit_depolarizing",
  "input_type": "css",
  "p_list": [0.01],
  "rounds_policy": {
    "kind": "fixed",
    "rounds": 3
  },
  "collection": {
    "max_shots": 2000,
    "max_errors": 200,
    "batch_size": 256
  },
  "css_memory": {
    "basis": "x",
    "schedule": "greedy"
  },
  "result_metrics": ["logical_error_rate"],
  "execution_status": "real"
}
```

The existing `distance-scaled` rounds policy remains valid for rotated-surface
tasks. CSS explicit-instance tasks use a fixed rounds policy because BB
instances do not currently expose a distance scalar through the candidate
contract.

### Rsinter TOML

When `task.input_type == "css"`, `write_spec_toml()` emits the CSS input fields
instead of `distance`:

```toml
[runner.params]
input_type = "css"
code_id = "bivariate-bicycle-code-m6-n6"
hx = "../hx.json"
hz = "../hz.json"
basis = "x"
schedule = "greedy"
rounds = [3]
p = [0.01]
max_shots = 2000
max_errors = 200
batch_size = 256
osd_order = 10
bp_iters = 50
early_stop = true
```

The path values are relative to the generated spec directory so the run remains
portable inside the candidate artifact folder.

When `task.input_type` remains the current rotated-surface shape, TOML
generation keeps emitting `distance = [...]` and existing plot labels continue
to group by distance.

### Fixed BB Instance

Add one committed BB instance under
`zoo/codes/bivariate-bicycle-code/instances/`.

The preferred instance is BB `[[72,12,6]]` if its TensorQEC parameters can be
verified from committed knowledge or source references. If that provenance
cannot be established during implementation, use a smaller generated BB
instance from the existing generator path, record its exact `m`, `n`, `vc`, and
`hd` parameters in `instance.json`, and describe it as the fixed BB CSS
decoder-registry validation instance. Do not label the smaller instance as
`[[72,12,6]]`.

## Design 3: Real Validation Artifacts And Tests

Add a small suite, for example `decoder-registry-css-bb-smoke-v1`, containing
the CSS memory task and these decoders:

- `rbposd-osd0-v1`
- `rbposd-osd10-v1`
- `predict-zero-v1`

Run it once with real `rsinter` and commit the resulting validation artifacts
under `results/search/...`:

- completed manifests for all three decoders
- raw `rsinter/out/<decoder_id>/test-run/results.jsonl` result rows for all
  three decoders
- `candidate.json`
- `structure.json`
- `candidate-plot.svg`
- leaderboard output
- report output

The artifact must be small enough to review and deterministic enough to rerun.
It may use a single `p` value. The seed, shot budget, error budget, rsinter
version, AutoQEC revision, task id, suite id, and decoder ids must be recorded
in the normal manifests.

### Test Layers

Fast tests should cover:

- alias input canonicalizes to `bp_iters` in generated TOML and manifests
- unknown decoder params are rejected
- CSS tasks write `input_type`, `code_id`, `hx`, `hz`, `basis`, `schedule`,
  `rounds`, `p`, budgets, and decoder params into TOML
- result parsing accepts CSS rows without `distance`
- plots/reports/leaderboards keep parameterized decoders distinct

Real e2e tests should cover:

- `autoqec-search eval` can run the fixed BB CSS instance through real
  `rsinter` for the three selected decoders
- rows record `input_type = "css"`, `code_id`, matrix paths, and
  `osd_order`
- `rbposd-osd10-v1` has lower LER than `rbposd-osd0-v1` on the fixed
  validation point
- `predict-zero-v1` lands in the wide LER control window

If the real e2e run is too slow or noisy for every CI invocation, keep a small
real smoke test in CI and assert the numeric ordering against the committed
artifact in a deterministic artifact-validation test. The PR description must
state which layer proves the numeric ordering.

## Design 4: Rsinter Predict-Zero Companion

Add a minimal `rsinter` bench runner that exposes the existing
`VacuousDecoder` as a public runner key, such as `predict-zero`.

The runner should:

- be registered in `build_default_rust_runner_registry()`
- appear in `default_rust_runner_names()`
- accept only generic runner params
- reject decoder-specific params as unknown
- call the shared `run_decoder_point()` path with `VacuousDecoder`

AutoQEC then adds `benchmarks/decoders/predict-zero-v1.json` with:

```json
{
  "id": "predict-zero-v1",
  "title": "Predict Zero via rsinter",
  "backend": "rsinter",
  "impl_key": "predict-zero",
  "language": "rust",
  "parameters": {},
  "execution_status": "real"
}
```

AutoQEC preflight should check that the installed `rsinter` recognizes
`predict-zero`. If not, it should fail with a clear message explaining that
issue #16's negative-control validation requires the companion `rsinter`
runner.

## Data Flow

1. Validation loads decoder configs and canonicalizes decoder parameters.
2. Eval resolves the fixed BB explicit-instance candidate from Zoo.
3. Eval copies `instance.json`, `hx.json`, and `hz.json` into the candidate
   artifact folder and validates CSS commutation.
4. TOML generation emits a complete `rsinter` benchmark spec using
   `input_type = "css"` and relative matrix paths.
5. `rsinter` builds the CSS memory circuit, runs each decoder, and writes
   result rows.
6. AutoQEC parses rows, canonicalizes observed decoder params, validates
   expected params, and writes completed manifests.
7. Leaderboards, plots, and reports use decoder IDs plus canonical parameter
   JSON to keep series distinct.
8. Artifact validation checks numeric ordering and negative-control behavior.

## Error Handling

Validation errors should happen before expensive backend work whenever
possible:

- decoder configs with unknown params fail schema validation or preflight
- configs that set both `bp_iters` and `max_bp_iterations` fail validation
- CSS tasks without `css_memory.basis` fail validation
- explicit-instance candidates with missing `instance.json`, `hx.json`, or
  `hz.json` fail resolution
- non-commuting CSS checks fail before `rsinter`
- `rsinter` rows missing required CSS params fail parsing with file and line
  context
- `predict-zero-v1` fails preflight if `rsinter` lacks the runner key

## Documentation Updates

Update README and CLAUDE docs to say:

- decoder configs are concrete registry entries
- `max_bp_iterations` is accepted only as an input alias; artifacts use
  `bp_iters`
- CSS/BB validation uses explicit Zoo instances and `rsinter`'s `css` input
  path
- `predict-zero-v1` is a negative-control decoder and requires the companion
  `rsinter` runner
- issue #16 is considered complete only when the real BB/CSS validation artifact
  and numeric assertions are present

## Verification Commands

Expected focused verification after implementation:

```sh
PYTHONPATH=src python3 -m pytest tests/test_search_eval_schemas.py tests/test_search_rsinter.py tests/test_search_eval_cli.py -q
PYTHONPATH=src python3 -m pytest tests/test_search_report.py tests/test_search_plot.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
PYTHONPATH=src python3 -m autoqec_search.cli eval --root . --campaign decoder-registry-css-bb-smoke --decoder rbposd-osd0-v1 --decoder rbposd-osd10-v1 --decoder predict-zero-v1 --p 0.01 --run-id issue16-bb-css-validation --force
```

If the real eval command is not kept in the normal CI suite, CI must still run a
deterministic artifact-validation test over the committed
`issue16-bb-css-validation` output.

## Rollout

Implementation should happen in two coordinated branches:

1. Add the `rsinter` `predict-zero` runner and verify it with `rsinter` tests.
2. Update AutoQEC PR #31 to depend on that runner, add CSS/BB explicit-instance
   validation, refresh artifacts, and update the PR body.

The AutoQEC PR should not claim full issue #16 completion until both branches
are available in the developer and CI environment used for verification.
