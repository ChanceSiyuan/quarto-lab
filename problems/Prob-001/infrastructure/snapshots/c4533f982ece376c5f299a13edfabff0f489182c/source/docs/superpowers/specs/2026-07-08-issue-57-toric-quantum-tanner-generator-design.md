# Issue 57 Toric Quantum Tanner Generator Design

Issue: #57, "[M3] Generate toric quantum Tanner spec files and a distance-ladder manifest from a sweep config"

## Context

Issue #56 added `src/autoqec_search/quantum_tanner_generator.py` as the
normalized source contract for quantum Tanner toric sweeps. It already derives
stable candidate ids such as `quantum-tanner-toric-d4`, qec-code specs such as
`quantum_tanner:toric_d4`, and repository-relative spec and instance paths.

The Rust helper `src/bin/autoqec-quantum-tanner-toric-spec.rs` writes one toric
quantum Tanner spec with construction mode `lr_cayley_no_cover_v1`, base group
`Z_d x Z_d`, generator indices `[d, d * (d - 1)]` and `[1, d - 1]`, and local
parity checks `[1, 1]`. The Rust distance-ladder exporter already accepts
manifest entries with `quantum_tanner_spec`; it resolves that field relative to
the manifest file's parent directory.

## Non-Interactive Decisions

This Agent Desk run is non-interactive, so the standing policy resolves choices
from the issue text and repository context.

1. Implement deterministic Python spec construction instead of invoking the
   compiled Rust helper. This keeps pytest independent of a Rust build while
   matching the committed d4/d6/d8 fixture shape.
2. Keep generation in `src/autoqec_search/quantum_tanner_generator.py`, beside
   the sweep config dataclasses it consumes.
3. Add a manifest path to the normalized config, because the issue requires a
   distance-ladder manifest and the #56 config did not yet name one.
4. Write manifest `quantum_tanner_spec` paths relative to the manifest parent,
   because `autoqec-distance-ladder export` resolves relative manifest paths
   from that directory.
5. Use `n = d * d`, `k = 2`, `expected_distance = d`, and
   `expected_bound_type` from the validated sweep config for the toric quantum
   Tanner ladder entries.
6. Provide dry-run behavior through a Python API and a CLI command so reviewers
   can inspect candidate ids and output paths without writing files.
7. Reject unsafe output paths and candidate-id collisions before writing any
   specs or manifests.

## Approaches Considered

Recommended: add a focused planner/writer that consumes the normalized sweep
config, validates all intended outputs up front, then writes spec JSON files and
one distance-ladder manifest. This reuses the existing validated contract and
the existing Rust exporter manifest shape without adding another matrix path.

Alternative: shell out to `autoqec-quantum-tanner-toric-spec` once per
distance. This directly reuses the Rust helper, but it makes Python tests depend
on a compiled binary location and still needs Python-side planning, path safety,
collision checks, dry-run output, and manifest rendering.

Alternative: only generate a manifest and rely on a later step to write specs.
That leaves `autoqec-distance-ladder export` with dangling
`quantum_tanner_spec` paths, so it does not satisfy the issue.

## Contract

The generator consumes the existing normalized
`QuantumTannerSweepConfig`. The JSON input keeps the existing required fields
and also accepts:

```json
{
  "distance_ladder_manifest_path": "benchmarks/distance_ladders/generated-quantum-tanner.json"
}
```

When omitted, the manifest path defaults to
`output_root / "distance_ladder.json"` for compatibility with #56 fixtures.

Dry-run returns a plan containing:

- the distance-ladder manifest path;
- one spec path per distance;
- one manifest entry per distance;
- a list of files that would be written.

Write-run performs the same validation first, then writes:

- `quantum_tanner_specs/toric-d<d>.json` files with fixture ids
  `quantum-tanner-toric-d<d>`;
- a distance-ladder manifest whose entries include `instance_id`, `code_id`,
  `qec_code_spec`, `quantum_tanner_spec`, `n`, `k`, `expected_distance`, and
  `expected_bound_type`.

## CLI Behavior

`validate-quantum-tanner-sweep` remains a validation and summary command.

Add `generate-quantum-tanner-sweep --config <path> [--root <repo>] [--dry-run]`
for artifact generation. `--dry-run` prints planned paths and does not create
files. Without `--dry-run`, the command writes the specs and manifest and
prints a concise summary.

Invalid configs, path escapes, and candidate-id collisions exit nonzero through
the existing `SearchIntegrityError` CLI path. Candidate collisions are detected
before any partial manifest or spec file is written.

## Testing

Extend `tests/test_search_quantum_tanner_generator.py` with tests that:

1. dry-run distances `[4, 6]` and assert planned candidate ids, manifest path,
   and spec paths;
2. write-run the same config in a temporary repository copy and assert two spec
   files, fixture ids `quantum-tanner-toric-d4` and
   `quantum-tanner-toric-d6`, and a manifest with two entries pointing at
   `toric-d4.json` and `toric-d6.json`;
3. reject a spec output path escaping the repository before any manifest write;
4. reject generated candidate-id collisions before any manifest write;
5. cover the CLI dry-run and write-run entry points.

Required verification:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
PYTHONPATH=src python3 -m pytest
```

## Self-Review

No placeholders remain. The design stays inside issue #57 scope: it writes
spec files and a distance-ladder manifest only, and it does not call `qec-code`
or materialize `hx.json` and `hz.json`.
