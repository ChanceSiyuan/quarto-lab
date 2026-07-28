# Issue 58 Quantum Tanner Materialization Design

Issue: #58, "[M3] Materialize generated quantum Tanner instances through the existing distance-ladder exporter"

## Context

Issue #57 added `src/autoqec_search/quantum_tanner_generator.py` support for
writing toric quantum Tanner spec files and a generated distance-ladder
manifest. That manifest already has the shape consumed by the Rust
`autoqec-distance-ladder export` command.

The Rust distance-ladder exporter in `src/distance_ladder.rs` owns the matrix
materialization contract: it invokes `qec-code`, validates sparse-row matrix
widths, computes CSS dimension `k`, checks a manifest-provided `k` when
present, and writes `instance.json`, `hx.json`, and `hz.json`. The generator
should delegate to that exporter instead of rebuilding the qec-code command
surface in Python.

## Non-Interactive Decisions

This Agent Desk run is non-interactive, so the standing policy resolves choices
from the issue text and repository context.

1. Invoke an explicit exporter executable from Python, defaulting to
   `autoqec-distance-ladder`, instead of duplicating qec-code matrix commands.
2. Keep materialization in `src/autoqec_search/quantum_tanner_generator.py`,
   beside the generated manifest planner and writer it consumes.
3. Add `distance_ladder_exporter_bin` to the sweep config with a default of
   `autoqec-distance-ladder`, while keeping `qec_code_bin` explicit and
   validated.
4. Add a `materialize` flag to `generate_quantum_tanner_sweep`. The existing
   default remains spec/manifest generation only; callers opt into exporter
   materialization.
5. Pass `--force` only when the caller explicitly opts in through a new
   `force` argument. This mirrors the Rust exporter overwrite semantics.
6. Treat exporter failure as a failed generation step: raise
   `SearchIntegrityError`, include the exporter command, stdout, and stderr,
   and do not return a successful generation plan.
7. Add CLI flags to `generate-quantum-tanner-sweep`: `--materialize`,
   `--distance-ladder-exporter-bin`, and `--force`.
8. Do not emit `fixture_catalog.json` or `search_space.json`; those artifacts
   remain outside issue #58.

## Approaches Considered

Recommended: extend the existing Python generation flow with an optional
materialization step that shells out to `autoqec-distance-ladder export` using
the generated manifest path, explicit qec-code binary, and explicit overwrite
policy. This reuses Rust validation and keeps Python tests independent by
pointing the exporter flag at a test-built binary.

Alternative: call the Rust `export_distance_ladder` library directly from a new
Rust command or Python extension. That avoids a subprocess boundary but adds
integration complexity that the repository does not currently use.

Alternative: implement qec-code calls directly in Python. That would duplicate
the exporter command construction, matrix validation, `k` checks, artifact
shape, and failure reporting already maintained in Rust.

## Contract

The normalized `QuantumTannerSweepConfig` gains:

```json
{
  "distance_ladder_exporter_bin": "autoqec-distance-ladder"
}
```

The field is optional. When omitted, the generator uses
`autoqec-distance-ladder`. The existing `qec_code_bin` field remains the path
passed through to the exporter.

`generate_quantum_tanner_sweep(repo_root, config, dry_run=False,
materialize=True, force=True)` performs these steps:

1. Validate all planned output paths and candidate ids.
2. Write quantum Tanner spec files and the distance-ladder manifest.
3. Invoke:

```bash
<distance_ladder_exporter_bin> export --manifest <manifest> --qec-code-bin <qec_code_bin> [--force]
```

4. Return a plan that records the exporter command, stdout, stderr, and the
   candidate instance directories only after the exporter succeeds.

Dry-run never writes specs, manifests, or instances, even when `materialize` is
requested.

## CLI Behavior

`validate-quantum-tanner-sweep` prints the configured exporter path in the same
summary as the qec-code path.

`generate-quantum-tanner-sweep --config <path> [--root <repo>] [--dry-run]
[--materialize] [--distance-ladder-exporter-bin <path>] [--force]` keeps the
existing default behavior unless `--materialize` is present. When materializing,
the command writes the specs and manifest, invokes the exporter, and prints a
summary that includes the exporter command and instance artifact count.

Failures exit nonzero through the existing `SearchIntegrityError` path. Exporter
failures include stdout and stderr so width mismatches from fake qec-code tests
are visible to CI logs and callers.

## Testing

Extend `tests/test_search_quantum_tanner_generator.py` with tests that:

1. materialize a two-distance sweep through a real `autoqec-distance-ladder`
   binary and a fake `qec-code` executable;
2. assert each candidate directory contains `instance.json`, `hx.json`, and
   `hz.json`;
3. assert `instance.json` records `qec_code_spec` and `quantum_tanner_spec`
   provenance;
4. configure fake qec-code to return an `hx.json` with the wrong `num_cols`,
   assert materialization fails, assert the error mentions the exporter step,
   stdout, and stderr, and assert no successful generation result is returned;
5. cover CLI `--materialize`, `--distance-ladder-exporter-bin`, and `--force`.

Required verification:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
cargo test distance_ladder --quiet
PYTHONPATH=src python3 -m pytest
```

## Self-Review

No placeholders remain. The design only materializes matrix artifacts from a
generated ladder manifest. It does not emit fixture catalogs, search spaces, or
new curated Zoo records.
