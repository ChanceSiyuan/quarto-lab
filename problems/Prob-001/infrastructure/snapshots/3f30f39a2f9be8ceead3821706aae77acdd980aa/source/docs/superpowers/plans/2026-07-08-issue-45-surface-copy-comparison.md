# Issue 45 Surface-Copy Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `compare-surface-copy` command that compares completed Tanner block-level LER results against copied single-logical rotated-surface baselines at `p=0.001`.

**Architecture:** Add a dedicated `autoqec_search.surface_copy_comparison` module that loads a completed run, validates Tanner comparison units from completed manifests, chooses the largest odd surface baseline distance under the Tanner physical-qubit budget, builds a JSON model, and renders a self-contained HTML report. Wire the module into `autoqec_search.cli` without changing `compare-candidates`.

**Tech Stack:** Python 3, pytest, JSON run artifacts, existing `autoqec_search.load`, `autoqec_search.baselines`, and existing comparison/report HTML patterns.

## Global Constraints

- Do not extend `compare-candidates`; it remains a same-task/same-decoder/same-p comparator.
- Required CLI shape: `PYTHONPATH=src python3 -m autoqec_search.cli compare-surface-copy --root . --run results/search/<campaign>/<run-id> --baseline benchmarks/baselines/rotated-surface-single-logical-p001.json --out /tmp/quantum-tanner-surface-copy.html`.
- Surface baseline rows must use `p=0.001`; bad baseline rows are fatal `SearchIntegrityError`s.
- Compare Tanner LER points only when `run_metadata.logical_failure_aggregation == "any_logical"`.
- Matching rule is the largest available odd surface distance `d` satisfying `k * d * d <= n`.
- Copied block probability formula is `P_block = 1 - (1 - P_single) ** k`; CI endpoints use the same formula.
- If no baseline row satisfies `k*d*d <= n`, reject that Tanner row with a clear reason.
- If `k <= 0`, reject that Tanner row with a clear reason.
- Output includes a machine-readable JSON file and a reviewer-friendly HTML report.
- Focused verification command must print `8 passed`: `PYTHONPATH=src pytest -q tests/test_search_surface_copy_comparison.py`.
- Full verification must pass: `PYTHONPATH=src python3 -m pytest`.

---

## File Structure

- Create `tests/test_search_surface_copy_comparison.py`: eight fixed-fixture tests for block probability, CI transformation, budget matching, aggregation labels, bad `k`, bad baseline `p`, and no-fit rejection.
- Create `src/autoqec_search/surface_copy_comparison.py`: pure comparison helpers, model builder, HTML renderer, and writer.
- Modify `src/autoqec_search/cli.py`: add `compare-surface-copy` parser and command dispatch.
- Modify `docs/superpowers/plans/2026-07-08-issue-45-surface-copy-comparison.md`: check off completed task steps during execution.

---

### Task 1: Write Failing Surface-Copy Tests

**Files:**
- Create: `tests/test_search_surface_copy_comparison.py`

**Interfaces:**
- Consumes: `autoqec_search.surface_copy_comparison.compare_surface_copy`, `write_surface_copy_comparison`, and `autoqec_search.cli.main` once Task 2 and Task 3 provide them.
- Produces: fixed fixture helper `_fixture_root(tmp_path, candidates, baseline_rows=None) -> tuple[Path, Path, Path]`.

- [x] **Step 1: Create fixture helpers**

Write a pytest file with helpers that create a minimal search workspace:

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "surface-copy-fixture-task-v1"
DECODER_ID = "surface-copy-fixture-decoder-v1"
SUITE_ID = "surface-copy-fixture-suite-v1"
CAMPAIGN_ID = "surface-copy-fixture"
RUN_ID = "surface-copy-run"

def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
```

The helper must copy `benchmarks/schemas` from the repository, write one task, one decoder, one suite, one campaign/search-space pair, one baseline manifest, and one run under `results/search/surface-copy-fixture/surface-copy-run`.

- [x] **Step 2: Write the eight issue-level tests**

Add tests with these exact assertions:

```python
def test_k1_copied_block_ler_equals_single_patch_ler(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [{"candidate_id": "candidate-k1", "n": 9, "k": 1}],
    )
    model = compare_surface_copy(root, run_root, baseline_path)
    row = _row(model, "candidate-k1")
    assert row["status"] == "accepted"
    assert row["surface_block_ler"] == row["surface_single_ler"]

def test_k12_copied_block_ler_uses_elementary_probability(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [{"candidate_id": "candidate-k12", "n": 108, "k": 12}],
    )
    model = compare_surface_copy(root, run_root, baseline_path)
    row = _row(model, "candidate-k12")
    assert row["surface_single_ler"] == 0.001
    assert row["surface_block_ler"] == pytest.approx(
        1 - (1 - 0.001) ** 12,
        abs=1e-15,
    )

def test_copied_ci_endpoints_are_transformed_and_ordered(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [{"candidate_id": "candidate-ci", "n": 108, "k": 12}],
    )
    row = _row(compare_surface_copy(root, run_root, baseline_path), "candidate-ci")
    assert row["surface_block_ci_low"] == pytest.approx(
        1 - (1 - row["surface_single_ci_low"]) ** 12,
        abs=1e-15,
    )
    assert row["surface_block_ci_high"] == pytest.approx(
        1 - (1 - row["surface_single_ci_high"]) ** 12,
        abs=1e-15,
    )
    assert row["surface_block_ci_low"] <= row["surface_block_ler"]
    assert row["surface_block_ler"] <= row["surface_block_ci_high"]

def test_selected_surface_patch_stays_under_physical_budget(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [{"candidate_id": "candidate-budget", "n": 305, "k": 12}],
    )
    row = _row(compare_surface_copy(root, run_root, baseline_path), "candidate-budget")
    assert row["surface_distance"] == 5
    assert row["surface_copied_total_physical"] == 300
    assert row["surface_copied_total_physical"] <= row["n"]
    assert row["unused_physical_budget"] == 5

def test_only_any_logical_tanner_points_are_accepted(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [
            {"candidate_id": "candidate-any", "n": 108, "k": 12},
            {
                "candidate_id": "candidate-per-logical",
                "n": 108,
                "k": 12,
                "logical_failure_aggregation": "per_logical",
            },
        ],
    )
    model = compare_surface_copy(root, run_root, baseline_path)
    assert _row(model, "candidate-any")["status"] == "accepted"
    rejected = _row(model, "candidate-per-logical")
    assert rejected["status"] == "rejected"
    assert "any_logical" in rejected["reason"]

def test_tanner_row_with_nonpositive_k_is_rejected(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [{"candidate_id": "candidate-bad-k", "n": 108, "k": 0}],
    )
    row = _row(compare_surface_copy(root, run_root, baseline_path), "candidate-bad-k")
    assert row["status"] == "rejected"
    assert row["reason"] == "candidate k must be positive"

def test_surface_baseline_with_wrong_p_is_rejected(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [{"candidate_id": "candidate-k12", "n": 108, "k": 12}],
        baseline_rows=[{**_baseline_row(distance=3, failures=10), "p": 0.01}],
    )
    with pytest.raises(SearchIntegrityError, match="p=0.001"):
        compare_surface_copy(root, run_root, baseline_path)

def test_tanner_row_without_fitting_surface_patch_is_rejected(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [{"candidate_id": "candidate-no-fit", "n": 100, "k": 12}],
    )
    row = _row(compare_surface_copy(root, run_root, baseline_path), "candidate-no-fit")
    assert row["status"] == "rejected"
    assert "k*d*d <= n" in row["reason"]
```

Use candidate dictionaries with these fields:

```python
{
    "candidate_id": "candidate-k12",
    "n": 108,
    "k": 12,
    "ler": 0.02,
    "ci_low": 0.015,
    "ci_high": 0.025,
    "logical_failure_aggregation": "any_logical",
}
```

The default baseline row for distance 3 must use `ler: 0.001`, `failures: 10`, and `shots: 10000`, so the expected copied block value is exactly `1 - (1 - 0.001) ** 12`.

- [x] **Step 3: Verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_search_surface_copy_comparison.py
```

Expected: failure because `autoqec_search.surface_copy_comparison` or `compare-surface-copy` is not implemented.

---

### Task 2: Implement Comparison Model

**Files:**
- Create: `src/autoqec_search/surface_copy_comparison.py`

**Interfaces:**
- Produces: `compare_surface_copy(root: Path, run_root: Path, baseline_path: Path) -> dict`.
- Produces: `block_probability(single_probability: float, k: int) -> float`.
- Produces row keys `status`, `candidate_id`, `n`, `k`, `tanner_ler`, `tanner_ci_low`, `tanner_ci_high`, `tanner_logical_failure_aggregation`, `surface_distance`, `surface_physical_per_patch`, `surface_copied_total_physical`, `unused_physical_budget`, `surface_single_ler`, `surface_block_ler`, `surface_block_ci_low`, `surface_block_ci_high`, and `reason`.

- [x] **Step 1: Add core helpers**

Implement helpers for finite numeric validation, block probability, run lookup, JSON loading, and row rejection. `block_probability` must return `single_probability` unchanged when `k == 1`.

- [x] **Step 2: Select surface row**

Implement `_select_surface_row(rows, *, n: int, k: int) -> dict | None` using only odd distances and requiring `k * distance * distance <= n`. Sort by distance descending and return the first row.

- [x] **Step 3: Build comparison rows**

For each completed manifest point in each loaded candidate:

1. Read `structure.json` for `n` and `k`.
2. Read `manifest["run_metadata"]["logical_failure_aggregation"]`.
3. Reject unless `k > 0`.
4. Reject unless aggregation is exactly `any_logical`.
5. Reject unless the point has `p == 0.001`.
6. Reject unless a surface baseline row fits the budget.
7. Otherwise compute copied block LER and CI endpoints and add an accepted row.

- [x] **Step 4: Run focused tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_search_surface_copy_comparison.py
```

Expected: the model assertions pass. If the CLI writer assertion is already in the test file, its failure must be the only remaining failure before Task 3.

---

### Task 3: Add HTML/JSON Writer And CLI

**Files:**
- Modify: `src/autoqec_search/surface_copy_comparison.py`
- Modify: `src/autoqec_search/cli.py`

**Interfaces:**
- Produces: `render_surface_copy_html(model: dict) -> str`.
- Produces: `write_surface_copy_comparison(model: dict, html_path: Path) -> dict[str, Path]`.
- Produces CLI subcommand `compare-surface-copy`.

- [x] **Step 1: Add renderer and writer**

Render a self-contained HTML table with accepted and rejected rows, plus embedded JSON in a `<pre>` block. Write the report to `--out` and the model to the same path with `.json` suffix.

- [x] **Step 2: Add CLI parser**

In `build_parser()`, add:

```python
surface_copy_parser = subparsers.add_parser(
    "compare-surface-copy",
    help="Compare Tanner block LER results against copied surface-code baselines",
)
surface_copy_parser.add_argument("--root", default=".")
surface_copy_parser.add_argument("--run", required=True)
surface_copy_parser.add_argument("--baseline", required=True)
surface_copy_parser.add_argument("--out", required=True)
```

- [x] **Step 3: Add CLI dispatch**

In `main()`, normalize relative `--run` and `--baseline` against `--root`, call `compare_surface_copy`, call `write_surface_copy_comparison`, print `wrote surface-copy comparison to <html>`, and return `0`.

- [x] **Step 4: Verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_search_surface_copy_comparison.py
```

Expected: `8 passed`.

---

### Task 4: Review, Full Verification, And PR

**Files:**
- All touched files.

**Interfaces:**
- Produces: clean branch, pushed PR for issue #45.

- [x] **Step 1: Run focused verification**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_surface_copy_comparison.py
```

Expected: `8 passed`.

- [x] **Step 2: Run full verification**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: all tests pass.

- [x] **Step 3: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output and exit code `0`.

- [x] **Step 4: Request final code review**

Use `superpowers:requesting-code-review` via the subagent-driven-development final review step. Fix Critical and Important findings before proceeding.

- [ ] **Step 5: Commit and open PR**

Commit implementation files, push `agent/issue-45-m4-add-a-surface-copy-comparison-report-for-quan-run-1`, and create a PR against `main` with a body containing:

```markdown
## Summary

- add a `compare-surface-copy` CLI/report for Tanner-vs-copied-surface comparisons
- write HTML plus sibling JSON with accepted and rejected comparison rows
- enforce `any_logical` block-level Tanner aggregation and under-budget odd-distance surface matching

## Tests

- `PYTHONPATH=src pytest -q tests/test_search_surface_copy_comparison.py`
- `PYTHONPATH=src python3 -m pytest`
```

## Self-Review

The plan covers the issue's CLI, machine-readable output, reviewer report, required columns, distance matching, block probability and CI transforms, aggregation guard, bad `k`, bad baseline `p`, no-fit rejection, and required verification commands. No incomplete sections remain. Function names and row keys are consistent across tasks.
