# Quantum Tanner Candidates CLI Design

## Context

Issue #60 adds the operator-facing entry point for the M3 quantum Tanner
candidate generator. Issues #56 through #59 are already merged: the code can
validate sweep configs, generate toric spec files and a distance-ladder
manifest, materialize finite CSS instances through `autoqec-distance-ladder
export`, and emit `fixture_catalog.json` plus `search_space.json` records.

The new work should not duplicate those lower-level paths. It should make the
already-tested generator usable from one stable checkout command.

## Chosen Approach

Add an additive CLI subcommand:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli generate-quantum-tanner-candidates \
  --root . \
  --config campaigns/examples/quantum-tanner-autoresearch/generator.json \
  --qec-code-bin /path/to/qec-code
```

This command loads the existing sweep config, applies CLI overrides, and calls
the existing `generate_quantum_tanner_sweep(..., materialize=True)` path for
non-dry runs. Dry runs call the existing planner without materialization, so the
operator can preview planned outputs without requiring local tool binaries and
without writing specs, manifests, matrices, catalogs, or search spaces.

The older `generate-quantum-tanner-sweep` command remains unchanged as a
lower-level developer command that can write only specs and manifests. The new
command is the operator workflow command with candidate artifacts as the
default outcome.

## CLI Contract

Inputs:

- `--root`: repository root. Defaults to `.`.
- `--config`: sweep config JSON path. Required.
- `--qec-code-bin`: explicit path to the `qec-code` executable for non-dry
  runs. Optional for dry runs. If omitted for a write run, the command fails
  before claiming generation is complete.
- `--dry-run`: print the planned candidates and paths without writing output.
- `--force`: pass overwrite permission through to the distance-ladder exporter.

The command also resolves the existing distance-ladder exporter to an explicit
path before materialization. If the config has an explicit
`distance_ladder_exporter_bin`, use it. Otherwise prefer `PATH`, then the
source-checkout binary at `target/debug/autoqec-distance-ladder`. If no
exporter is found, fail during materialization setup with an actionable error.

Outputs:

- Dry run: terminal summary only. It must list the planned candidate ids,
  `n`, `k`, distance labels, spec paths, instance paths, manifest path,
  catalog path, and search-space path. It must not write matrix artifacts or
  catalog/search-space files.
- Non-dry run: generated toric quantum Tanner specs, distance-ladder manifest,
  materialized `instance.json`, `hx.json`, and `hz.json`, emitted fixture
  catalog and search space, and a terminal summary of the same candidate table
  plus written output paths.

## Error Handling

Config validation errors keep the existing `SearchIntegrityError` behavior.
Materialization failures must fail the command before any completed-generation
message. The visible error must name the failed materialization step through
the existing `distance-ladder exporter failed` message and include command,
stdout, and stderr.

## Documentation

Update `campaigns/examples/quantum-tanner-autoresearch/README.md` with a
generator workflow before the run-loop workflow. The docs should show dry-run,
write-run, validation, and the role of `qec-code`. They should explicitly say
that upper-bound witness finding is a separate later step and is not performed
by candidate generation.

## Testing

Use TDD against `tests/test_search_quantum_tanner_generator.py` and
`tests/test_search_docs.py`.

Required coverage:

- Parser/help exposes `generate-quantum-tanner-candidates`.
- Dry-run command prints exactly the `[4, 6]` planned candidates and writes no
  generated specs, manifest, matrices, catalog, or search-space files.
- Non-dry-run command with the fake `qec-code` and `--force` writes specs,
  manifest, materialized instance artifacts, fixture catalog, and search
  space, and the generated root passes `validate --root`.
- Missing or deliberately broken `qec_code_bin` fails before reporting
  completion and surfaces the materialization failure.
- README contains runnable generator command blocks and states witness finding
  is separate.

## Scope

In scope: CLI wiring, deterministic terminal summary, workflow docs, and tests.

Out of scope: upper-bound witness search, rbposd benchmarking,
surface-copy comparison changes, and any new quantum Tanner matrix generation
logic outside the existing exporter path.
