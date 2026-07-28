# Issue 45 Surface-Copy Comparison Design

Issue: #45, "[M4] Add a surface-copy comparison report for quantum Tanner runs"

## Context

The repository already has the dependencies this issue needs:

- #41 added `benchmarks/baselines/rotated-surface-single-logical-p001.json`
  and `autoqec_search.baselines.load_surface_single_logical_baseline`.
- #44 added the `quantum-tanner-autoresearch` run path, screened Tanner
  candidates, and completed result manifests that record
  `run_metadata.logical_failure_aggregation: "any_logical"` for explicit
  logical observables.

What is missing is the cross-family comparison layer that turns one
single-logical surface patch result into a `k`-logical copied block failure
probability without running `k` independent surface simulations.

## Non-Interactive Decisions

This Agent Desk run is non-interactive, so the standing policy resolves
choices from the issue text and repository context.

1. Add a new `compare-surface-copy` CLI and module instead of extending
   `compare-candidates`. The existing command remains a same-task,
   same-decoder, same-p comparator.
2. Write a reviewer-friendly HTML report and a sibling machine-readable JSON
   file, matching the existing comparison command pattern.
3. Read completed Tanner manifests directly when enforcing comparison units.
   The report model exposes result points, but it does not expose
   `run_metadata`, which is the source of the `any_logical` aggregation label.
4. Reject invalid comparison rows in the JSON model with a per-candidate
   `status: "rejected"` and clear `reason`, while keeping valid rows in the
   same report. Fatal input corruption such as a bad surface baseline remains a
   `SearchIntegrityError`.
5. Use the issue's matching rule exactly: choose the largest available odd
   surface distance `d` whose baseline row satisfies `k * d * d <= n`.

## Approaches Considered

Recommended: add `autoqec_search.surface_copy_comparison` with pure helpers
for candidate extraction, surface distance matching, block probability
conversion, JSON model construction, and HTML rendering. The CLI calls this
module and writes HTML plus JSON. This keeps the scientific normalization in a
dedicated boundary and makes the behavior easy to test with fixture data.

Alternative: extend `compare-candidates`. That would reuse an existing CLI
surface, but it would mix different scientific units into a command whose
contract is explicitly limited to same-task, same-decoder, same-p comparisons.

Alternative: implement a standalone script outside `src/`. That would be
quick, but it would bypass the repository's CLI, validation, and test patterns.

## Architecture

Create `src/autoqec_search/surface_copy_comparison.py` with these public
functions:

- `compare_surface_copy(root: Path, run_root: Path, baseline_path: Path) -> dict`
- `render_surface_copy_html(model: dict) -> str`
- `write_surface_copy_comparison(model: dict, html_path: Path) -> dict[str, Path]`

The model contains:

- `schema_version`
- `status`
- `root`, `run`, and `baseline` provenance
- `rows`, one row per completed Tanner point considered

Each accepted row includes the issue-required columns:

- Tanner candidate id
- `n`
- `k`
- Tanner LER and CI
- Tanner logical failure aggregation
- chosen surface patch distance `d`
- surface physical qubits per patch `d^2`
- copied surface total physical `k*d^2`
- unused physical budget `n-k*d^2`
- single-patch surface LER
- copied block surface LER
- copied block CI

Rejected rows include `candidate_id`, `n`, `k`, `tanner_ler` when available,
`logical_failure_aggregation` when available, `status: "rejected"`, and a
clear `reason`.

## Data Flow

1. The CLI normalizes `--root`, `--run`, `--baseline`, and `--out`.
2. The module loads the p=0.001 surface baseline with
   `load_surface_single_logical_baseline`.
3. The module loads the run with `load_search_workspace` so candidate
   `structure.json` and completed evaluation manifests are available.
4. For each completed Tanner result point, the module finds the candidate's
   `n` and `k`, validates `k > 0`, reads the manifest `run_metadata`, and
   requires `logical_failure_aggregation == "any_logical"`.
5. It filters baseline rows to odd distances at `p=0.001`, then chooses the
   largest row satisfying `k * distance ** 2 <= n`.
6. It computes copied block probabilities with
   `1 - (1 - p_single) ** k` for the point estimate and both CI endpoints.
7. It writes a self-contained HTML report and a sibling JSON file.

## Error Handling

Surface baseline schema or p-value drift is fatal and raises
`SearchIntegrityError`, reusing #41's loader.

Rows with missing or invalid Tanner dimensions are rejected in the comparison
output. `k <= 0` uses reason `candidate k must be positive`.

Rows without block-level aggregation are rejected in the comparison output.
The accepted aggregation value is exactly `any_logical`.

Rows for which no surface patch fits under the physical-qubit budget are
rejected with a reason that names the budget constraint.

## Testing

Add `tests/test_search_surface_copy_comparison.py` with eight fixed-fixture
tests:

1. For `k=1`, copied block LER equals the single-patch surface LER.
2. For `k=12` and `P_single=0.001`, copied block LER equals
   `1 - (1 - 0.001) ** 12` within `1e-15`.
3. CI endpoints are transformed with the same monotone formula and remain
   ordered.
4. The selected surface patch satisfies `k*d*d <= n`.
5. Tanner LER is accepted only when `logical_failure_aggregation` is
   `any_logical`.
6. A Tanner row with `k <= 0` is rejected.
7. A surface baseline row with `p != 0.001` is rejected.
8. A Tanner row for which no surface patch fits under budget is rejected with
   a clear reason.

Required verification:

```bash
PYTHONPATH=src pytest -q tests/test_search_surface_copy_comparison.py
PYTHONPATH=src python3 -m pytest
```

## Out of Scope

Do not extend `compare-candidates` for cross-task normalization. Do not run
multi-patch surface simulations. Do not change the quantum Tanner run gate or
baseline manifest semantics.
