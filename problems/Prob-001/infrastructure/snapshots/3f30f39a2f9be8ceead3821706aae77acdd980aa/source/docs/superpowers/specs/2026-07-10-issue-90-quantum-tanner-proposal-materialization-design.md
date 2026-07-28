# Issue 90: Quantum Tanner Proposal Materialization Design

## Goal

Add an offline bridge that turns validator-passing quantum Tanner proposal JSON
files into deterministic proposal-derived finite CSS instance bundles. The
bundle is a search artifact, not a curated Zoo fact, and it must keep exact
distance unknown unless a real exact-distance method is run elsewhere.

## Scope

The CLI accepts one or more proposal JSON files, an output root, and a required
explicit `--qec-code-bin` path. Each proposal is validated with the issue 89
deterministic validator before any backend call. On success, the command writes
one completed candidate directory under the output root containing
`instance.json`, `hx.json`, `hz.json`, the normalized qec-code quantum Tanner
spec, and `materialization_manifest.json`.

The bridge does not import candidates into a campaign, update search-space
schemas, run rbposd, compute logical observables, call live models, or promote
records into the curated Zoo.

## Approach

Use a new focused Python module,
`src/autoqec_search/quantum_tanner_proposal_materialization.py`, rather than
extending the existing generated-sweep distance-ladder path. The generated-sweep
path is tied to distance-ladder manifests with positive expected distances; this
issue needs proposal-derived bundles whose exact distance is intentionally
`null`. Directly invoking `qec-code code css quantum-tanner --spec <spec> hx|hz`
keeps the new contract explicit and avoids encoding an upper bound as an exact
distance.

The module exposes a small public API:

- `materialize_quantum_tanner_proposal_file(...)` validates and materializes one
  proposal.
- `materialize_quantum_tanner_proposal_files(...)` materializes a sequence and
  returns a summary with counts and output directories.
- Helper dataclasses describe the materialized bundle, backend command records,
  and summary.

`autoqec_search.cli` gets a
`materialize-quantum-tanner-proposals` subcommand with `--root`, repeated
`--proposal`, `--out-root`, required `--qec-code-bin`, `--max-group-order`, and
`--force`.

## Data Flow

1. Load and validate the proposal through
   `validate_quantum_tanner_proposal_file`.
2. Normalize only the construction fields consumed by qec-code into
   `qec_code_quantum_tanner_spec.json`.
3. Create a staging directory beside the final candidate directory.
4. Run qec-code twice, once for `hx` and once for `hz`.
5. Parse and validate the returned sparse-row matrices: format, positive
   `num_cols`, row shape, integer supports, duplicate supports, bounds, matching
   widths, and CSS commutation.
6. Compute CSS dimension from GF(2) ranks for provenance.
7. Write staged `hx.json`, `hz.json`, `instance.json`,
   `qec_code_quantum_tanner_spec.json`, and `materialization_manifest.json`.
8. Hash all staged outputs, then atomically replace the completed candidate
   directory. If any step fails, delete staging and leave no completed candidate
   directory for that proposal.

## Instance Contract

`instance.json` identifies the proposal-derived code and references `hx.json`
and `hz.json`. It preserves the original proposal provenance, validator
version/fingerprint, qec-code commands, qec-code version if discoverable, the
normalized spec path, and manifest path. It records:

- `parameters.distance: null`
- `derived_properties.distance: null`
- computed `n`, `k`, `mx`, and `mz`

No upper-bound or target-distance value is copied into an exact-distance field.
The instance is intentionally not forced through
`zoo/schemas/code-instance.schema.json`; proposal materialization is a local
search-artifact bridge.

## Failure Handling

Validation errors are reported with the typed issue 89 rejection name and stop
before staging. Backend spawn errors, nonzero qec-code exits, malformed matrix
JSON, width mismatches, and noncommuting matrices fail the command, delete the
staging directory, and do not leave a completed candidate directory. Existing
completed candidate directories are overwritten only with `--force`.

## Testing

Add `tests/test_search_quantum_tanner_proposal_materialization.py` with fake
qec-code binaries so CI does not need a real backend. Tests cover:

- valid proposal materialization writes the full bundle and keeps distance
  fields null;
- invalid proposal rejection exits nonzero with the typed validator error and
  leaves no completed candidate directory;
- malformed qec-code matrix output exits nonzero and leaves no partial bundle.

Also run the existing proposal validator tests and the full pytest suite.

## Self-Review

- No placeholders remain.
- The design keeps proposal-derived artifacts separate from curated Zoo records.
- qec-code is invoked through an explicit path and no additional external
  algebra/model dependencies are introduced.
- Exact distance remains null unless a future exact-distance workflow records
  otherwise.
- Atomic staging is required for validator and backend failure paths.
