# Search Benchmarks

This directory stores reusable benchmark contracts for the search layer.

## Contents

- `tasks/`: benchmark task definitions
- `decoders/`: decoder configuration records
- `suites/`: reusable task + decoder groupings
- `fixtures/`: small known-answer records consumed by `autoqec-search preflight`
- `baselines/`: raw comparison baseline manifests, kept separate from final comparison output
- `schemas/`: JSON Schemas used by `autoqec-search`

These records are reusable across campaigns.

## Decoder Registry

Each file in `decoders/` is a decoder configuration identity. Multiple records
may share one backend implementation when their tunable parameters differ. For
example, `rbposd-default-v1`, `rbposd-osd0-v1`, and `rbposd-osd10-v1` all use
the `rsinter` `rbposd` implementation, but the `osd0` and `osd10` records carry
explicit scalar `parameters`.

Decoder fields have the following roles:

- `id`: stable search-layer identity used in suites, run specs, manifests, and artifacts
- `backend`: runner family such as `rsinter`
- `impl_key`: backend implementation name passed to the runner
- `language`: implementation language metadata
- `parameters`: optional scalar JSON values appended to `[runner.params]`
- `execution_status`: whether the backend is real or placeholder-like

Completed result manifests preserve the backend-echoed `decoder_parameters`.
Leaderboard rows, candidate plots, and reports display them with stable sorted
JSON so parameterized decoders remain distinguishable. Historical run specs are
allowed to contain a subset of the current suite decoder list, but unknown or
duplicate run decoder ids are invalid.

The current parameterized-registry checks are scoped to the rotated-surface d=3
eval path and its checked-in fixtures. Broader CSS-family adapters should be
added as separate benchmark tasks or suites rather than folded into this
baseline registry.
