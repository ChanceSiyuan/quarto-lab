# Issue 40 Quantum Tanner RBP-OSD p=0.001 Benchmark Design

Issue: #40, "[M1] Add a p=0.001 rbposd benchmark suite for quantum Tanner candidates"

## Context

Issue #39 added a pinned quantum Tanner fixture catalog under
`campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json` and a
catalog adapter that resolves the sparse-row `hx.json`/`hz.json` artifacts into
general CSS `ResolvedCandidate` payloads. The benchmark layer already has CSS
memory task support in `bb-css-memory-x-cdep-v1.json`, rbposd decoder configs
under `benchmarks/decoders/`, and suites that bind tasks to decoders.

The new M1 contract should pin one physical error rate, `p=0.001`, and one
existing rbposd decoder id. It should not add a new decoder implementation,
predict-zero comparison, campaign run, or high-budget result artifact.

## Clarifying Decisions

Because this Agent Desk run is non-interactive, these decisions are resolved
from the issue text and repository context.

1. Add a standalone benchmark task and suite rather than changing BB72 or
   rotated-surface contracts.
2. Pin `rbposd-osd10-v1`, the issue's recommended existing decoder id.
3. Set `css_memory.observables` to `optional`, because the #39 quantum Tanner
   catalog provides plain `hx`/`hz` CSS fixtures without explicit logical
   observable artifacts.
4. Keep shots and error limits conservative for smoke tests.
5. Add a focused four-test contract file named
   `tests/test_search_quantum_tanner_benchmark_contracts.py`.
6. Do not add a campaign or search-space file in this issue; #40's requested
   output is the benchmark task and suite contract.

## Approaches Considered

Recommended: add `quantum-tanner-css-memory-x-rbposd-p001-v1.json` and
`quantum-tanner-rbposd-p001-v1.json` as standalone benchmark records. This is
the smallest durable contract, reuses the general CSS task shape, and keeps the
decoder choice explicit.

Alternative: update `bb72-qldpc-campaign-v1.json` or
`decoder-registry-css-bb-smoke-v1.json`. This would mix quantum Tanner
requirements into BB-specific smoke fixtures and risk carrying BB-only
observables assumptions.

Alternative: add a full quantum Tanner campaign plus search space now. That may
be useful later, but it is broader than the issue output and would require a
separate decision about how catalog entries become campaign candidates.

## Architecture

Create a new benchmark task at
`benchmarks/tasks/quantum-tanner-css-memory-x-rbposd-p001-v1.json` with:

- `input_type: "css"` so evaluation uses the general CSS memory path.
- `p_list: [0.001]` exactly.
- `css_memory.basis: "x"`, `schedule: "greedy"`, and
  `observables: "optional"`.
- fixed, small collection defaults suitable for smoke testing.
- `rounds_policy.kind: "fixed"` with a conservative round count.

Create a new suite at
`benchmarks/suites/quantum-tanner-rbposd-p001-v1.json` with:

- one task id: `quantum-tanner-css-memory-x-rbposd-p001-v1`.
- one decoder id: `rbposd-osd10-v1`.
- shared runner `rsinter`.

No decoder config changes are required.

## Data Flow

1. The suite resolves to the new CSS memory task and existing
   `rbposd-osd10-v1` decoder through `load_search_workspace`.
2. The task's `input_type: "css"` and `css_memory` fields route through
   `write_css_spec_toml` and the general CSS evaluation path.
3. The #39 catalog adapter provides `ResolvedCandidate` objects with dense CSS
   `hx` and `hz` matrices. Because observables are optional, those candidates
   do not need `observables_x.json`.
4. Evaluation uses only `p=0.001` unless a caller supplies an invalid filter,
   which existing `validate_selected_p_values` rejects.

## Error Handling

The contract tests will reject copied bad task or suite records that add
`0.01`, add a non-rbposd decoder, include `predict-zero-v1`, lose CSS input
compatibility, or require explicit observables for the current quantum Tanner
fixtures.

## Testing

Add `tests/test_search_quantum_tanner_benchmark_contracts.py` with exactly four
tests:

1. The suite's selected task contains exactly one physical error rate,
   `0.001`, and a copied bad task containing `0.01` is rejected.
2. The suite resolves to exactly one decoder, `rbposd-osd10-v1`, whose
   `impl_key` is `rbposd`; a copied bad suite containing `predict-zero-v1` or
   another non-rbposd decoder is rejected.
3. The task is CSS-compatible, uses optional observables, and can be paired
   with a catalog-resolved quantum Tanner candidate through the general CSS
   spec writer without explicit observables.
4. Workspace validation sees the new benchmark records.

Verification commands:

```bash
PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_benchmark_contracts.py
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m pytest
```

## Out of Scope

Do not run the full quantum Tanner campaign. Do not add SOGRAND, LEAD, or any
other decoder. Do not create benchmark result artifacts or large-budget run
defaults.
