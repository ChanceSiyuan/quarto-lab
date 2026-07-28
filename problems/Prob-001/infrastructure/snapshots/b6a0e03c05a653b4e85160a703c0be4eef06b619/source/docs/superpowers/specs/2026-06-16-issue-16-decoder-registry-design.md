# Issue #16 Decoder Registry Design

## Goal

Add the M2 decoder-registry layer for `autoqec-search eval` and
`autoqec-search run`: decoder configs become concrete, parameterized registry
entries; AutoQEC passes those parameters to `rsinter`; and completed outputs
record the exact parameterization used.

This builds on issue #8 real benchmark contracts, issue #9 single-candidate
evaluation, and upstream `nzy1997/rstim#47`, which exposes decoder-specific
runner parameters in the `rsinter` benchmark spec. This issue intentionally
stays independent of the general CSS adapter work in issue #17. Verification
uses the existing rotated-surface d=3 path, not the BB `[[72,12,6]]` path.

## Scope

In scope:

- backend-aware validation for `benchmarks/decoders/*.json`
- parameterized concrete decoder configs, including at least one additional
  `rbposd` configuration
- passing decoder `parameters` into each generated `rsinter` runner spec
- parsing normalized decoder parameters from `rsinter` result rows
- recording `decoder_parameters` in completed result manifests
- exposing decoder parameters in `leaderboard.csv`, `candidate-plot.svg`, and
  `report.html`
- tests that distinguish `rbposd` configurations by `osd_order`
- negative tests for unknown decoder parameter keys
- README and CLAUDE documentation for configuring decoder parameters

Out of scope:

- the general CSS to circuit/DEM adapter for arbitrary `hx`/`hz`
- the BB qLDPC campaign and BB verification plot
- adding external Python decoders outside `rsinter`
- suite-level parameter overrides
- sweep syntax such as `osd_order: [0, 10]` inside one decoder config
- changing candidate generation, distance computation, promotion, or strategy
  selection

## Main Decision

Use concrete decoder-config records as the registry entries.

Each file under `benchmarks/decoders/` represents one selectable decoder
configuration:

```json
{
  "id": "rbposd-osd10-v1",
  "title": "RBP-OSD OSD Order 10 via rsinter",
  "backend": "rsinter",
  "impl_key": "rbposd",
  "language": "rust",
  "parameters": {
    "bp_iters": 50,
    "early_stop": true,
    "osd_order": 10
  },
  "execution_status": "real"
}
```

Suites continue to select decoder IDs:

```json
{
  "decoder_ids": [
    "rmatching-default-v1",
    "rbposd-osd0-v1",
    "rbposd-osd10-v1",
    "rilpqec-default-v1"
  ]
}
```

This keeps `decoder_id` stable and reproducible. A run can still be filtered
with the existing `--decoder` CLI option, while the manifest and leaderboard
carry both the stable ID and the exact parameters observed in the backend
result row.

## Decoder Config Contract

`benchmarks/schemas/decoder-config.schema.json` becomes backend-aware for the
currently supported `rsinter` runner implementations.

Allowed parameters:

- `rmatching`: no decoder-specific parameters
- `rbposd`:
  - `bp_iters`: integer, minimum 0
  - `max_bp_iterations`: integer, minimum 0
  - `early_stop`: boolean
  - `osd_order`: integer, minimum 0
- `rilpqec`:
  - `backend`: one of `auto`, `highs`, `gurobi`
  - `time_limit_s`: number greater than 0
  - `mip_gap`: number with `0 <= mip_gap < 1`
  - `threads`: integer greater than 0
  - `verbose`: boolean

Validation rejects unknown parameter keys. It also rejects `rbposd` configs
that set both `bp_iters` and `max_bp_iterations`, because upstream treats them
as aliases for the same knob.

The existing default decoder configs should be updated away from the current
`{"profile": "default"}` placeholder, because `profile` is not an upstream
runner parameter. Default configs may use `{}` when the backend default is
intended.

## Rsinter Spec Generation

`src/autoqec_search/rsinter.py` owns the AutoQEC to `rsinter` translation.

`write_spec_toml()` should continue to write the generic run-point parameters:

- `distance`
- `rounds`
- `p`
- `max_shots`
- `max_errors`
- `batch_size`

It then appends each selected decoder config's `parameters` into that runner's
`[runner.params]` block as scalar TOML values. Only JSON scalar values allowed
by the schema are serialized, so generated TOML remains deterministic and easy
to inspect.

Example generated runner:

```toml
[[runner]]
name = "rbposd-osd10-v1"
language = "rust"
impl_key = "rbposd"

[runner.params]
distance = [3]
rounds = [3]
p = [0.01]
max_shots = 1000
max_errors = 50
batch_size = 256
bp_iters = 50
early_stop = true
osd_order = 10
```

AutoQEC should not try to normalize or reinterpret backend defaults after the
run. The durable completed manifest records the parameters `rsinter` reports
in each row. This lets upstream default changes be visible instead of hidden.

## Result Manifests

Completed result manifests produced after this change gain a
`decoder_parameters` object:

```json
{
  "decoder_id": "rbposd-osd10-v1",
  "decoder_parameters": {
    "bp_iters": 50,
    "early_stop": true,
    "osd_order": 10
  },
  "status": "completed",
  "points": []
}
```

The parser should split row `params` into:

- generic point fields consumed by AutoQEC: `p`, `rounds`, optional `distance`
- decoder-specific fields preserved as `decoder_parameters`

Completed manifests for unparameterized decoders use
`"decoder_parameters": {}`.

Historical completed manifests, placeholder manifests, and crash manifests
remain compatible when they omit `decoder_parameters`. This avoids rewriting
committed run artifacts that predate the registry while ensuring new eval and
run outputs carry the field.

The completed manifest schema accepts `decoder_parameters` when present and
rejects non-scalar values or unknown extra top-level fields. The manifest
builder and new-run tests require new completed manifests to include the field.

## Leaderboards, Plots, And Reports

`leaderboard.csv` gains a `decoder_parameters` column containing sorted JSON.
Rows remain CSV-safe through the existing `csv.writer` path.

`candidate-plot.svg` keeps one series per `decoder_id`, but the legend and
point tooltips include the parameter JSON when non-empty. This makes
`rbposd-osd0-v1` and `rbposd-osd10-v1` visually distinct even if a human reads
only the SVG.

`report.html` includes decoder parameters in the embedded report model, the
points table, and the leaderboard table. Existing threshold/frontier logic can
continue grouping by `decoder_id`; no algorithmic report behavior changes are
required.

## CLI And Run Loop Behavior

The existing `--decoder` filter remains ID-based. Selecting
`--decoder rbposd-osd10-v1` runs exactly that concrete configuration.

`autoqec-search eval` and `autoqec-search run` both consume the same workspace
decoder registry, so the run loop receives the behavior through
`evaluate_resolved_candidate_into_run()` without a separate path.

Run specs continue to record `decoder_ids`. They do not need a separate
parameter map because decoder IDs resolve through committed registry files, and
completed manifests preserve the backend-observed parameterization.

## Error Handling

Validation should catch malformed decoder configs before `rsinter` is invoked:

- unknown parameter key
- wrong parameter type
- invalid numeric domain
- `rbposd` alias conflict between `bp_iters` and `max_bp_iterations`
- parameters supplied for `rmatching`

Runtime parsing should catch backend drift:

- selected result row has an unexpected runner name
- result row omits expected `p` values
- result row has invalid shots/errors/LER fields
- a parameterized decoder row omits a configured parameter key after canonical
  alias normalization

For defaulted backend parameters, missing keys are acceptable only when the
AutoQEC config did not set that key. If a config set `osd_order`, the parsed
manifest must record `osd_order`. If a config uses the upstream
`max_bp_iterations` alias, AutoQEC treats the backend-normalized `bp_iters`
field as the canonical recorded key.

## Verification

Schema tests:

- accept valid `rmatching`, `rbposd`, and `rilpqec` configs
- reject unknown keys such as `rbposd.bogus`
- reject `rmatching` configs that set `osd_order`
- reject `rbposd` configs that set both `bp_iters` and
  `max_bp_iterations`
- reject invalid domains such as negative `osd_order` or nonpositive
  `time_limit_s`

Unit tests:

- generated TOML includes decoder-specific parameters
- scalar TOML serialization remains escaped and type-preserving
- result parsing returns point metrics plus `decoder_parameters`
- completed manifest builder writes `decoder_parameters`
- completed manifest schema accepts `decoder_parameters` while staying
  compatible with historical completed manifests that omit it
- `render_eval_leaderboard()` emits a stable sorted JSON parameter column
- `render_candidate_plot()` accepts parameterized manifests and renders
  parameters in labels/tooltips

CLI and run tests with fake `rsinter`:

- run rotated-surface d=3 with `rbposd-osd0-v1` and `rbposd-osd10-v1`
- fake `rsinter` reads runner params and writes result rows that include the
  same `osd_order`
- fake LER for `osd_order=10` is lower than fake LER for `osd_order=0`
- completed manifests record different `decoder_parameters`
- `leaderboard.csv` records both `osd_order` values
- `candidate-plot.svg` and `report.html` expose the parameterization

This deterministic fake-backend route is the CI teeth for issue #16. A local
real-`rsinter` smoke run may also be performed, but it is not the only proof of
correctness.

## Documentation

Update README and CLAUDE search-layer sections to explain:

- decoder configs are concrete registry entries
- backend parameters live in `benchmarks/decoders/*.json`
- suite selection remains by decoder ID
- completed manifests and leaderboards record decoder parameters
- issue #16 is rotated-surface verified and leaves BB/general CSS work to
  issues #17 and #18

## Implementation Notes

Keep the implementation narrow:

- prefer small helper functions in `rsinter.py` over a new abstraction layer
- do not introduce suite-level overrides
- do not rewrite historical run artifacts solely to add `decoder_parameters`
- keep report grouping keyed by `decoder_id`
- make schema failures crisp enough that `autoqec-search validate --root .`
  and `autoqec-search preflight --root .` are useful negative controls
