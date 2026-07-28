# Issue 11 Search Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `autoqec-search report` and automatic autoresearch `report.html` generation for self-contained visual search-run reports.

**Architecture:** Add a focused `autoqec_search.report` module that loads existing run artifacts, normalizes them into a deterministic report model, renders inline SVG plots and offline-safe HTML, and writes `report.html`. Wire that module into the CLI for explicit regeneration and into `run_loop.py` finalization for automatic autoresearch reports.

**Tech Stack:** Python 3.11 standard library (`csv`, `json`, `math`, `html`, `pathlib`, dataclasses), existing `jsonschema` loader path, `pytest`, fake `rsinter` CLI fixtures, inline SVG/HTML.

---

## File Structure

| File | Responsibility |
|---|---|
| `benchmarks/schemas/run-spec.schema.json` | Allow empty `candidate_ids` so issue #11's zero-candidate report fixture validates. |
| `src/autoqec_search/report.py` | Load run artifacts, build deterministic report model, estimate thresholds, render inline SVG/HTML, and write reports. |
| `src/autoqec_search/cli.py` | Add `autoqec-search report --root . --run <path> [--out <path>]`. |
| `src/autoqec_search/run_loop.py` | Write `report.html` automatically before the final autoresearch commit. |
| `tests/test_search_report.py` | Pure report-model, renderer, self-containment, zero-result, data-driven, and CLI tests. |
| `tests/test_search_run_cli.py` | Integration assertion that autoresearch finalization writes and commits `report.html`. |
| `tests/test_search_docs.py` | Documentation coverage for explicit and automatic report behavior. |
| `README.md` | User-facing command and artifact documentation. |
| `CLAUDE.md` | Agent-facing workflow notes for report generation. |

---

### Task 1: Allow Empty Search Runs For Report Fixtures

**Files:**
- Modify: `tests/test_search_eval_schemas.py`
- Modify: `benchmarks/schemas/run-spec.schema.json`

- [ ] **Step 1: Write the failing schema test**

Append this test to `tests/test_search_eval_schemas.py`:

```python
def test_run_spec_schema_accepts_empty_candidate_report_fixture() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "run-spec.schema.json")
    run_spec = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "empty-run",
        "suite_id": "rotated-surface-baseline-v1",
        "task_ids": ["rotated-memory-x-cdep-v1"],
        "decoder_ids": ["rmatching-default-v1"],
        "candidate_ids": [],
        "created_at": "2026-06-14T00:00:00Z",
        "mode": "eval",
    }

    Draft202012Validator(schema).validate(run_spec)
```

- [ ] **Step 2: Run the schema test and verify it fails**

Run:

```bash
python3 -m pytest tests/test_search_eval_schemas.py::test_run_spec_schema_accepts_empty_candidate_report_fixture -q
```

Expected: FAIL with a validation error for `candidate_ids` because the schema currently requires at least one item.

- [ ] **Step 3: Relax `candidate_ids`**

In `benchmarks/schemas/run-spec.schema.json`, change:

```json
    "candidate_ids": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string", "minLength": 1 }
    },
```

to:

```json
    "candidate_ids": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    },
```

- [ ] **Step 4: Run schema and loader regression tests**

Run:

```bash
python3 -m pytest tests/test_search_eval_schemas.py::test_run_spec_schema_accepts_empty_candidate_report_fixture tests/test_search_load.py::test_load_search_workspace_collects_example_run -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add benchmarks/schemas/run-spec.schema.json tests/test_search_eval_schemas.py
git commit -m "test: allow empty search run report fixtures"
```

---

### Task 2: Build The Report Model Loader

**Files:**
- Create: `tests/test_search_report.py`
- Create: `src/autoqec_search/report.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_search_report.py` with:

```python
from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path

from autoqec_search.load import load_search_workspace
from autoqec_search.report import build_report_model


REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_search_tree(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    return work_root


def _example_run_root(work_root: Path) -> Path:
    return (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[list[object]]) -> None:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(rows)
    path.write_text(output.getvalue())


def _make_completed_eval_run(work_root: Path) -> Path:
    run_root = _example_run_root(work_root)
    expected = _load_json(work_root / "benchmarks" / "fixtures" / "rotated-d3" / "expected.json")
    run_spec_path = run_root / "run_spec.json"
    run_spec = _load_json(run_spec_path)
    run_spec["mode"] = "eval"
    _write_json(run_spec_path, run_spec)

    candidate_root = run_root / "candidates" / "rotated-surface-d3-example"
    candidate_path = candidate_root / "candidate.json"
    candidate = _load_json(candidate_path)
    candidate["status"] = "evaluated"
    _write_json(candidate_path, candidate)

    manifest = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "2026-06-09-example",
        "candidate_id": "rotated-surface-d3-example",
        "task_id": "rotated-memory-x-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "completed",
        "created_at": "2026-06-13T10:20:39Z",
        "tool_revisions": {
            "autoqec_search": "0.1.0",
            "rsinter": "rsinter git main abc123",
        },
        "points": [
            {
                "p": expected["p"],
                "rounds": expected["rounds"],
                "shots": expected["shots"],
                "errors": expected["errors"],
                "ler": expected["logical_error_rate"],
                "ci_low": expected["binomial_ci_95"]["lower"],
                "ci_high": expected["binomial_ci_95"]["upper"],
                "seconds": 0.022230764,
            }
        ],
    }
    _write_json(
        candidate_root
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json",
        manifest,
    )
    _write_csv(
        run_root / "leaderboard.csv",
        [
            [
                "candidate_id",
                "task_id",
                "decoder_id",
                "p",
                "shots",
                "errors",
                "ler",
                "ci_low",
                "ci_high",
                "status",
            ],
            [
                "rotated-surface-d3-example",
                "rotated-memory-x-cdep-v1",
                "rmatching-default-v1",
                expected["p"],
                expected["shots"],
                expected["errors"],
                expected["logical_error_rate"],
                expected["binomial_ci_95"]["lower"],
                expected["binomial_ci_95"]["upper"],
                "completed",
            ],
        ],
    )
    return run_root


def _make_empty_run(work_root: Path) -> Path:
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "empty-run"
    run_root.mkdir(parents=True)
    (run_root / "candidates").mkdir()
    _write_json(
        run_root / "run_spec.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "empty-run",
            "suite_id": "rotated-surface-baseline-v1",
            "task_ids": ["rotated-memory-x-cdep-v1"],
            "decoder_ids": [
                "rmatching-default-v1",
                "rbposd-default-v1",
                "rilpqec-default-v1",
            ],
            "candidate_ids": [],
            "created_at": "2026-06-14T00:00:00Z",
            "mode": "eval",
        },
    )
    _write_json(
        run_root / "env.json",
        {
            "tool": "autoqec-search",
            "version": "0.1.0",
            "generated_at": "2026-06-14T00:00:00Z",
            "mode": "eval",
        },
    )
    _write_json(
        run_root / "frontier.json",
        {"campaign_id": "rotated-surface-baseline", "run_id": "empty-run", "items": []},
    )
    (run_root / "leaderboard.csv").write_text(
        "candidate_id,task_id,decoder_id,p,shots,errors,ler,ci_low,ci_high,status\n"
    )
    (run_root / "summary.md").write_text("# Empty Run\n")
    return run_root


def test_build_report_model_collects_completed_eval_points(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    expected = _load_json(work_root / "benchmarks" / "fixtures" / "rotated-d3" / "expected.json")

    model = build_report_model(work_root, run_root)

    assert model["provenance"]["campaign_id"] == "rotated-surface-baseline"
    assert model["provenance"]["run_id"] == "2026-06-09-example"
    assert model["counts"]["candidates"] == 1
    assert model["counts"]["completed"] == 1
    assert model["counts"]["placeholder"] == 2
    assert model["points"][0]["candidate_id"] == "rotated-surface-d3-example"
    assert model["points"][0]["ler"] == expected["logical_error_rate"]
    assert model["leaderboard"][0]["status"] == "completed"


def test_build_report_model_accepts_empty_run(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_empty_run(work_root)

    workspace = load_search_workspace(work_root)
    model = build_report_model(work_root, run_root)

    assert "rotated-surface-baseline/empty-run" in workspace.runs
    assert model["counts"]["candidates"] == 0
    assert model["counts"]["points"] == 0
    assert model["points"] == []
```

- [ ] **Step 2: Run model tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_report.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autoqec_search.report'`.

- [ ] **Step 3: Create `src/autoqec_search/report.py` with the model loader**

Add:

```python
from __future__ import annotations

import csv
import json
from math import isfinite
from pathlib import Path
from typing import Any

from autoqec_search.load import SearchIntegrityError, load_search_workspace


REPORT_SCHEMA_VERSION = 1


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing report artifact: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"report artifact must be an object: {path}")
    return payload


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing report CSV artifact: {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        return [dict(row) for row in reader]


def _finite_float(value: Any, *, label: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise SearchIntegrityError(f"{label} must be a finite number")
    numeric = float(value)
    if not isfinite(numeric):
        raise SearchIntegrityError(f"{label} must be a finite number")
    return numeric


def _optional_distance(path: Path) -> int | None:
    payload = _load_json(path)
    value = payload.get("distance")
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise SearchIntegrityError(f"invalid report distance in {path}")
    return value


def _manifest_status_counts(manifests: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "completed": sum(1 for manifest in manifests if manifest.get("status") == "completed"),
        "crash": sum(1 for manifest in manifests if manifest.get("status") == "crash"),
        "placeholder": sum(1 for manifest in manifests if manifest.get("status") == "placeholder"),
    }


def _point_payload(manifest: dict[str, Any], point: dict[str, Any], distance: int | None) -> dict[str, Any]:
    return {
        "candidate_id": manifest["candidate_id"],
        "distance": distance,
        "task_id": manifest["task_id"],
        "decoder_id": manifest["decoder_id"],
        "p": _finite_float(point.get("p"), label="point p"),
        "rounds": int(point["rounds"]),
        "shots": int(point["shots"]),
        "errors": int(point["errors"]),
        "ler": _finite_float(point.get("ler"), label="point ler"),
        "ci_low": _finite_float(point.get("ci_low"), label="point ci_low"),
        "ci_high": _finite_float(point.get("ci_high"), label="point ci_high"),
        "seconds": _finite_float(point.get("seconds"), label="point seconds"),
    }


def build_report_model(root: Path, run_root: Path) -> dict[str, Any]:
    root = root.resolve()
    run_root = run_root.resolve()
    if not run_root.is_dir():
        raise SearchIntegrityError(f"run root does not exist: {run_root}")

    run_spec = _load_json(run_root / "run_spec.json")
    campaign_id = str(run_spec["campaign_id"])
    run_id = str(run_spec["run_id"])
    workspace = load_search_workspace(root)
    loaded_run = workspace.runs.get(f"{campaign_id}/{run_id}")
    if loaded_run is None:
        raise SearchIntegrityError(f"run is not part of search workspace: {run_root}")
    if loaded_run.root.resolve() != run_root:
        raise SearchIntegrityError(f"run path mismatch: {run_root}")

    env = _load_json(run_root / "env.json")
    frontier = _load_json(run_root / "frontier.json")
    leaderboard_rows = _read_csv_rows(run_root / "leaderboard.csv")
    verdict_rows = (
        _read_csv_rows(run_root / "experiment-log.tsv")
        if (run_root / "experiment-log.tsv").is_file()
        else []
    )

    candidates: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    for candidate_id, loaded_candidate in sorted(loaded_run.candidates.items()):
        candidate_root = run_root / "candidates" / candidate_id
        distance = _optional_distance(candidate_root / "distance.json")
        structure = _load_json(candidate_root / "structure.json")
        candidates.append(
            {
                "candidate_id": candidate_id,
                "distance": distance,
                "status": loaded_candidate.payload.get("status"),
                "n": structure.get("n"),
                "k": structure.get("k"),
                "css_commute": structure.get("css_commute"),
            }
        )
        for (task_id, decoder_id), manifest in sorted(loaded_candidate.manifests.items()):
            manifests.append(
                {
                    "candidate_id": candidate_id,
                    "task_id": task_id,
                    "decoder_id": decoder_id,
                    "status": manifest.get("status"),
                }
            )
            if manifest.get("status") != "completed":
                continue
            for raw_point in manifest.get("points", []):
                if not isinstance(raw_point, dict):
                    raise SearchIntegrityError(f"manifest point must be an object: {candidate_id}")
                points.append(_point_payload(manifest, raw_point, distance))

    points = sorted(
        points,
        key=lambda point: (
            str(point["task_id"]),
            str(point["decoder_id"]),
            str(point["candidate_id"]),
            int(point["distance"] or 0),
            float(point["p"]),
        ),
    )
    counts = _manifest_status_counts(manifests)
    counts["candidates"] = len(candidates)
    counts["frontier"] = len(frontier.get("items", []))
    counts["points"] = len(points)

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "provenance": {
            "campaign_id": campaign_id,
            "run_id": run_id,
            "mode": run_spec.get("mode"),
            "generated_at": env.get("generated_at"),
            "autoqec_version": env.get("version"),
            "git_sha": env.get("git_sha"),
            "branch": env.get("branch"),
            "rsinter": env.get("rsinter"),
            "seed": env.get("seed", run_spec.get("seed")),
            "wall_clock_seconds": env.get("wall_clock_seconds", run_spec.get("wall_clock_seconds")),
        },
        "counts": counts,
        "candidates": candidates,
        "manifests": manifests,
        "points": points,
        "leaderboard": leaderboard_rows,
        "frontier": frontier.get("items", []),
        "verdicts": verdict_rows,
    }
```

- [ ] **Step 4: Run model tests**

Run:

```bash
python3 -m pytest tests/test_search_report.py::test_build_report_model_collects_completed_eval_points tests/test_search_report.py::test_build_report_model_accepts_empty_run -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/report.py tests/test_search_report.py
git commit -m "feat: load search report model"
```

---

### Task 3: Render Thresholds, SVG, HTML, And Report Files

**Files:**
- Modify: `tests/test_search_report.py`
- Modify: `src/autoqec_search/report.py`

- [ ] **Step 1: Add failing renderer tests**

Add these imports to `tests/test_search_report.py`:

```python
import pytest

from autoqec_search.report import estimate_threshold, render_report_html, write_report_html
```

Append these tests:

```python
def test_render_report_html_contains_golden_ler_and_inline_svg(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    expected = _load_json(work_root / "benchmarks" / "fixtures" / "rotated-d3" / "expected.json")

    html = render_report_html(work_root, run_root)

    assert "<!doctype html>" in html
    assert "AutoQEC Search Report" in html
    assert "<svg" in html
    assert "rmatching-default-v1" in html
    assert "rotated-surface-d3-example" in html
    assert str(expected["logical_error_rate"]) in html
    assert "application/json" in html
    assert "http://" not in html
    assert "https://" not in html


def test_render_empty_run_report_has_no_results_and_no_nan(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_empty_run(work_root)

    html = render_report_html(work_root, run_root)

    assert "No results" in html
    assert "<svg" not in html
    assert "NaN" not in html
    assert "candidate_count" in html


def test_report_is_data_driven_by_manifest_and_leaderboard(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    before = render_report_html(work_root, run_root)
    manifest_path = (
        run_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    manifest = _load_json(manifest_path)
    manifest["points"][0]["ler"] = 0.021
    manifest["points"][0]["ci_low"] = 0.02
    manifest["points"][0]["ci_high"] = 0.022
    _write_json(manifest_path, manifest)

    _write_csv(
        run_root / "leaderboard.csv",
        [
            [
                "candidate_id",
                "task_id",
                "decoder_id",
                "p",
                "shots",
                "errors",
                "ler",
                "ci_low",
                "ci_high",
                "status",
            ],
            [
                "rotated-surface-d3-example",
                "rotated-memory-x-cdep-v1",
                "rmatching-default-v1",
                0.005,
                76533,
                1000,
                0.021,
                0.02,
                0.022,
                "completed",
            ],
        ],
    )
    after = render_report_html(work_root, run_root)

    assert before != after
    assert "0.021" in after
    assert "0.013066258999385886" in before
    assert "0.013066258999385886" not in after


def test_threshold_estimate_detects_crossing() -> None:
    model = {
        "points": [
            {"task_id": "task", "decoder_id": "decoder", "distance": 3, "p": 0.004, "ler": 0.010},
            {"task_id": "task", "decoder_id": "decoder", "distance": 3, "p": 0.006, "ler": 0.020},
            {"task_id": "task", "decoder_id": "decoder", "distance": 5, "p": 0.004, "ler": 0.006},
            {"task_id": "task", "decoder_id": "decoder", "distance": 5, "p": 0.006, "ler": 0.024},
        ]
    }

    estimate = estimate_threshold(model)

    assert estimate["status"] == "estimated"
    assert estimate["task_id"] == "task"
    assert estimate["decoder_id"] == "decoder"
    assert estimate["p_estimate"] == pytest.approx(0.005)
    assert "coarse crossing" in estimate["method"]


def test_write_report_html_writes_default_and_custom_paths(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    default_path = write_report_html(work_root, run_root)
    custom_path = write_report_html(work_root, run_root, tmp_path / "custom-report.html")

    assert default_path == run_root / "report.html"
    assert default_path.is_file()
    assert custom_path.is_file()
    assert "AutoQEC Search Report" in custom_path.read_text()
```

- [ ] **Step 2: Run renderer tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_report.py::test_render_report_html_contains_golden_ler_and_inline_svg tests/test_search_report.py::test_render_empty_run_report_has_no_results_and_no_nan tests/test_search_report.py::test_threshold_estimate_detects_crossing -q
```

Expected: FAIL because `estimate_threshold`, `render_report_html`, and `write_report_html` do not exist.

- [ ] **Step 3: Add rendering functions**

Append this code to `src/autoqec_search/report.py`:

```python
from html import escape
from math import log10


LOG_RATE_FLOOR = 1e-12
WIDTH = 980
HEIGHT = 560
MARGIN_LEFT = 82
MARGIN_RIGHT = 44
MARGIN_TOP = 58
MARGIN_BOTTOM = 92
PLOT_WIDTH = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
PLOT_HEIGHT = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
SERIES_COLORS = ("#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2")


def _format_float(value: float) -> str:
    return format(value, ".12g")


def _format_coord(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _plot_rate(value: float) -> float:
    return max(value, LOG_RATE_FLOOR)


def _domain(values: list[float]) -> tuple[float, float]:
    low = min(values)
    high = max(values)
    if low == high:
        return low / 2, high * 2
    pad = 10 ** ((log10(high) - log10(low)) * 0.04)
    return low / pad, high * pad


def _scale_log(value: float, domain: tuple[float, float], start: float, end: float) -> float:
    low, high = domain
    position = (log10(value) - log10(low)) / (log10(high) - log10(low))
    return start + position * (end - start)


def estimate_threshold(model: dict[str, Any]) -> dict[str, Any]:
    by_task_decoder: dict[tuple[str, str], dict[int, list[dict[str, Any]]]] = {}
    for point in model.get("points", []):
        distance = point.get("distance")
        if type(distance) is not int:
            continue
        key = (str(point["task_id"]), str(point["decoder_id"]))
        by_task_decoder.setdefault(key, {}).setdefault(distance, []).append(point)
    for (task_id, decoder_id), by_distance in sorted(by_task_decoder.items()):
        distances = sorted(by_distance)
        if len(distances) < 2:
            continue
        low_distance = distances[0]
        high_distance = distances[-1]
        low_points = {float(point["p"]): float(point["ler"]) for point in by_distance[low_distance]}
        high_points = {float(point["p"]): float(point["ler"]) for point in by_distance[high_distance]}
        shared = sorted(set(low_points) & set(high_points))
        if len(shared) < 2:
            continue
        previous_p = shared[0]
        previous_delta = high_points[previous_p] - low_points[previous_p]
        for current_p in shared[1:]:
            current_delta = high_points[current_p] - low_points[current_p]
            if previous_delta == 0:
                estimate = previous_p
            elif current_delta == 0:
                estimate = current_p
            elif (previous_delta < 0 < current_delta) or (previous_delta > 0 > current_delta):
                fraction = abs(previous_delta) / (abs(previous_delta) + abs(current_delta))
                estimate = previous_p + (current_p - previous_p) * fraction
            else:
                previous_p = current_p
                previous_delta = current_delta
                continue
            return {
                "status": "estimated",
                "task_id": task_id,
                "decoder_id": decoder_id,
                "distance_pair": [low_distance, high_distance],
                "p_estimate": estimate,
                "method": "coarse crossing estimate from shared p values",
            }
    return {
        "status": "not_enough_data",
        "method": "requires at least two distances with shared p values for one task and decoder",
    }


def render_ler_svg(model: dict[str, Any]) -> str:
    points = list(model.get("points", []))
    if not points:
        return ""
    p_values = sorted({float(point["p"]) for point in points})
    y_values = [_plot_rate(float(point[key])) for point in points for key in ("ci_low", "ler", "ci_high")]
    x_domain = _domain(p_values)
    y_domain = (max(_domain(y_values)[0], LOG_RATE_FLOOR), min(_domain(y_values)[1], 1.0))
    plot_bottom = MARGIN_TOP + PLOT_HEIGHT
    plot_right = MARGIN_LEFT + PLOT_WIDTH
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for point in points:
        distance = point.get("distance")
        label = f"{point['candidate_id']} d={distance}" if isinstance(distance, int) else str(point["candidate_id"])
        grouped.setdefault((str(point["task_id"]), str(point["decoder_id"]), label), []).append(point)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Logical error rate plot">',
        "<style>",
        ".plot-bg{fill:#ffffff}",
        ".axis{stroke:#20242a;stroke-width:1.2}",
        ".grid{stroke:#d9dee7;stroke-width:1;stroke-dasharray:3 4}",
        ".tick,.axis-label,.legend{font-family:Arial,sans-serif;fill:#20242a}",
        ".tick{font-size:11px}",
        ".axis-label{font-size:13px;font-weight:700}",
        ".legend{font-size:11px}",
        ".series{fill:none;stroke-width:2.3;stroke-linejoin:round;stroke-linecap:round}",
        ".ci{stroke-width:1.7;stroke-linecap:round;opacity:.82}",
        ".marker{stroke:#ffffff;stroke-width:1.4}",
        "</style>",
        f'<rect class="plot-bg" x="0" y="0" width="{WIDTH}" height="{HEIGHT}"/>',
        f'<text class="axis-label" x="{MARGIN_LEFT}" y="30">Logical error rate vs physical error rate</text>',
        f'<line class="axis" x1="{MARGIN_LEFT}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}"/>',
        f'<line class="axis" x1="{MARGIN_LEFT}" y1="{MARGIN_TOP}" x2="{MARGIN_LEFT}" y2="{plot_bottom}"/>',
    ]
    for p in p_values:
        x = _format_coord(_scale_log(p, x_domain, MARGIN_LEFT, plot_right))
        lines.append(f'<line class="grid" x1="{x}" y1="{MARGIN_TOP}" x2="{x}" y2="{plot_bottom}"/>')
        lines.append(f'<text class="tick" x="{x}" y="{plot_bottom + 20}" text-anchor="middle">p={escape(_format_float(p))}</text>')
    y_ticks = sorted({y_domain[0], y_domain[1], *(_plot_rate(float(point["ler"])) for point in points)})
    for value in y_ticks:
        y = _format_coord(_scale_log(value, y_domain, plot_bottom, MARGIN_TOP))
        lines.append(f'<line class="grid" x1="{MARGIN_LEFT}" y1="{y}" x2="{plot_right}" y2="{y}"/>')
        lines.append(f'<text class="tick" x="{MARGIN_LEFT - 9}" y="{y}" text-anchor="end" dominant-baseline="middle">{escape(_format_float(value))}</text>')
    for index, (key, series_points) in enumerate(sorted(grouped.items())):
        color = SERIES_COLORS[index % len(SERIES_COLORS)]
        label = " / ".join(key)
        ordered = sorted(series_points, key=lambda point: float(point["p"]))
        coords = []
        for point in ordered:
            x = _scale_log(float(point["p"]), x_domain, MARGIN_LEFT, plot_right)
            y = _scale_log(_plot_rate(float(point["ler"])), y_domain, plot_bottom, MARGIN_TOP)
            coords.append(f"{_format_coord(x)},{_format_coord(y)}")
        lines.append(f'<polyline class="series" points="{" ".join(coords)}" stroke="{color}"/>')
        for point in ordered:
            x = _format_coord(_scale_log(float(point["p"]), x_domain, MARGIN_LEFT, plot_right))
            y = _format_coord(_scale_log(_plot_rate(float(point["ler"])), y_domain, plot_bottom, MARGIN_TOP))
            y_low = _format_coord(_scale_log(_plot_rate(float(point["ci_low"])), y_domain, plot_bottom, MARGIN_TOP))
            y_high = _format_coord(_scale_log(_plot_rate(float(point["ci_high"])), y_domain, plot_bottom, MARGIN_TOP))
            title = f"{point['candidate_id']} {point['decoder_id']}: p={_format_float(float(point['p']))}, LER={_format_float(float(point['ler']))}, CI=[{_format_float(float(point['ci_low']))}, {_format_float(float(point['ci_high']))}]"
            lines.append(f'<line class="ci" x1="{x}" y1="{y_low}" x2="{x}" y2="{y_high}" stroke="{color}"/>')
            lines.append(f'<circle class="marker" cx="{x}" cy="{y}" r="4.2" fill="{color}"><title>{escape(title)}</title></circle>')
        legend_y = MARGIN_TOP + 18 + index * 16
        lines.append(f'<text class="legend" x="{MARGIN_LEFT + 12}" y="{legend_y}" dominant-baseline="middle">{escape(label)}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _html_cell(value: Any) -> str:
    return "" if value is None else escape(str(value))


def _render_table(rows: list[dict[str, Any]], *, empty: str) -> str:
    if not rows:
        return f"<p class='empty'>{escape(empty)}</p>"
    columns = sorted({key for row in rows for key in row})
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{_html_cell(row.get(column))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def _key_value_table(values: dict[str, Any]) -> str:
    rows = "".join(
        f"<tr><th>{escape(str(key))}</th><td>{_html_cell(value)}</td></tr>"
        for key, value in values.items()
        if value is not None
    )
    return f"<table><tbody>{rows}</tbody></table>"


def _threshold_html(threshold: dict[str, Any]) -> str:
    if threshold["status"] == "estimated":
        return (
            f"<p>Estimated threshold p = <strong>{escape(_format_float(float(threshold['p_estimate'])))}</strong>.</p>"
            f"<p class='note'>{escape(str(threshold['method']))}; labelled as an estimate.</p>"
        )
    return f"<p><strong>Not enough data</strong></p><p class='note'>{escape(str(threshold['method']))}.</p>"


def render_report_html(root: Path, run_root: Path) -> str:
    model = build_report_model(root, run_root)
    threshold = estimate_threshold(model)
    svg = render_ler_svg(model)
    embedded = json.dumps({**model, "threshold": threshold}, indent=2, sort_keys=True)
    counts = model["counts"]
    chart = svg if svg else "<section class='no-results'><h2>No results</h2><p>No completed manifest points were found for this run.</p></section>"
    count_table = _key_value_table(
        {
            "candidate_count": counts["candidates"],
            "completed_manifests": counts["completed"],
            "crash_manifests": counts["crash"],
            "placeholder_manifests": counts["placeholder"],
            "frontier_size": counts["frontier"],
            "point_count": counts["points"],
        }
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoQEC Search Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #172033; background: #ffffff; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 1.5rem; font-size: 0.92rem; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 0.45rem 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; }}
    .empty, .note {{ color: #4b5563; }}
    .no-results {{ border: 1px solid #d5dde8; padding: 1rem; border-radius: 6px; background: #f8fafc; }}
    pre {{ white-space: pre-wrap; background: #f8fafc; border: 1px solid #d5dde8; padding: 1rem; overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>AutoQEC Search Report</h1>
  <h2>Provenance</h2>
  {_key_value_table(model["provenance"])}
  <h2>Status</h2>
  {count_table}
  <h2>LER vs p</h2>
  {chart}
  <h2>Threshold Estimate</h2>
  {_threshold_html(threshold)}
  <h2>Frontier</h2>
  {_render_table(model["frontier"], empty="No frontier entries.")}
  <h2>Leaderboard</h2>
  {_render_table(model["leaderboard"], empty="No leaderboard rows.")}
  <h2>Results</h2>
  {_render_table(model["points"], empty="No results")}
  <h2>Embedded Report Data</h2>
  <script type="application/json" id="autoqec-report-data">{escape(embedded)}</script>
  <pre>{escape(embedded)}</pre>
</body>
</html>
"""


def write_report_html(root: Path, run_root: Path, output_path: Path | None = None) -> Path:
    target = output_path if output_path is not None else run_root / "report.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_report_html(root, run_root))
    return target
```

- [ ] **Step 4: Run renderer tests**

Run:

```bash
python3 -m pytest tests/test_search_report.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/report.py tests/test_search_report.py
git commit -m "feat: render self-contained search report"
```

---

### Task 4: Wire The Explicit `autoqec-search report` Command

**Files:**
- Modify: `tests/test_search_report.py`
- Modify: `src/autoqec_search/cli.py`

- [ ] **Step 1: Add failing CLI test**

Add these imports to `tests/test_search_report.py`:

```python
import subprocess
import sys
```

Append:

```python
def _run_report_cli(work_root: Path, run_root: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "report",
            "--root",
            str(work_root),
            "--run",
            str(run_root),
            "--out",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src")},
    )


def test_report_cli_writes_requested_output(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    output_path = tmp_path / "report.html"

    result = _run_report_cli(work_root, run_root, output_path)

    assert result.returncode == 0, result.stderr
    assert str(output_path) in result.stdout
    assert output_path.is_file()
    assert "AutoQEC Search Report" in output_path.read_text()
```

- [ ] **Step 2: Run CLI test and verify it fails**

Run:

```bash
python3 -m pytest tests/test_search_report.py::test_report_cli_writes_requested_output -q
```

Expected: FAIL because the CLI has no `report` subcommand.

- [ ] **Step 3: Import report writer**

In `src/autoqec_search/cli.py`, add:

```python
from autoqec_search.report import write_report_html
```

- [ ] **Step 4: Add parser entry**

In `build_parser()`, after the `run` parser and before `show`, add:

```python
    report_parser = subparsers.add_parser(
        "report", help="Render a self-contained HTML report for one run"
    )
    report_parser.add_argument("--root", default=".")
    report_parser.add_argument("--run", required=True)
    report_parser.add_argument("--out", default=None)
```

- [ ] **Step 5: Add command dispatch**

In `main()`, after the `run` command branch and before the `show` branch, add:

```python
        if args.command == "report":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            run_root = Path(args.run)
            if not run_root.exists():
                parser.error(f"run root does not exist: {run_root}")
            output_path = write_report_html(
                root,
                run_root,
                Path(args.out) if args.out is not None else None,
            )
            print(f"wrote search report to {output_path}")
            return 0
```

- [ ] **Step 6: Run CLI and smoke tests**

Run:

```bash
python3 -m pytest tests/test_search_report.py tests/test_search_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/autoqec_search/cli.py tests/test_search_report.py
git commit -m "feat: add search report cli"
```

---

### Task 5: Generate `report.html` During Autoresearch Finalization

**Files:**
- Modify: `tests/test_search_run_cli.py`
- Modify: `src/autoqec_search/run_loop.py`

- [ ] **Step 1: Add failing autoresearch assertions**

In `tests/test_search_run_cli.py`, update `_assert_lab_notebook()` by adding these assertions after the existing `run-summary.html` assertion:

```python
    assert (run_root / "report.html").is_file()
    report = (run_root / "report.html").read_text()
    assert "AutoQEC Search Report" in report
    assert "rotated-surface-d3-example" in report
    assert "0.013" in report
    assert "http://" not in report
    assert "https://" not in report
```

In `test_run_cleanup_reports_branch_without_stale_worktree_path`, add this branch-content assertion after the existing `run_status` assertion:

```python
    report_html = subprocess.run(
        [
            "git",
            "show",
            "autoresearch/cleanup-check:"
            "results/search/rotated-surface-baseline/cleanup-check/report.html",
        ],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "AutoQEC Search Report" in report_html
```

- [ ] **Step 2: Run autoresearch test and verify it fails**

Run:

```bash
python3 -m pytest tests/test_search_run_cli.py::test_run_creates_worktree_branch_and_lab_notebook -q
```

Expected: FAIL because `report.html` is not written during finalization.

- [ ] **Step 3: Import report writer**

In `src/autoqec_search/run_loop.py`, add:

```python
from autoqec_search.report import write_report_html
```

- [ ] **Step 4: Write the final report before the final commit**

In `run_autoresearch()`, replace:

```python
    write_aggregates(run_root, config, rows, frontier)
    write_final_status(run_root, config, rows, frontier, utc_now())
    git_commit_all(worktree_root, f"finalize autoresearch run {actual_run_id}")
```

with:

```python
    write_aggregates(run_root, config, rows, frontier)
    write_final_status(run_root, config, rows, frontier, utc_now())
    write_report_html(worktree_root, run_root)
    git_commit_all(worktree_root, f"finalize autoresearch run {actual_run_id}")
```

- [ ] **Step 5: Run autoresearch integration tests**

Run:

```bash
python3 -m pytest tests/test_search_run_cli.py::test_run_creates_worktree_branch_and_lab_notebook tests/test_search_run_cli.py::test_run_cleanup_reports_branch_without_stale_worktree_path -q
```

Expected: PASS.

- [ ] **Step 6: Run run-loop regression tests**

Run:

```bash
python3 -m pytest tests/test_search_run_cli.py tests/test_search_run_loop.py tests/test_search_run_render.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/autoqec_search/run_loop.py tests/test_search_run_cli.py
git commit -m "feat: write report for autoresearch runs"
```

---

### Task 6: Update Documentation

**Files:**
- Modify: `tests/test_search_docs.py`
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add failing docs coverage**

Append this test to `tests/test_search_docs.py`:

```python
def test_docs_mention_search_report_command() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "autoqec-search report" in readme
    assert "report.html" in readme
    assert "self-contained" in readme
    assert "offline" in readme

    assert "autoqec-search report" in claude
    assert "report.html" in claude
    assert "run-summary.html" in claude
    assert "offline" in claude
```

- [ ] **Step 2: Run docs test and verify it fails**

Run:

```bash
python3 -m pytest tests/test_search_docs.py::test_docs_mention_search_report_command -q
```

Expected: FAIL because docs do not mention the new command.

- [ ] **Step 3: Update README**

In `README.md`, after the `autoqec-search run` documentation paragraph, add:

````markdown
Render a self-contained visual report for any completed search run with:

```bash
python3 -m autoqec_search.cli report --root . --run results/search/rotated-surface-baseline/<run-id>
```

The installed form is `autoqec-search report`. By default the command writes
`report.html` inside the run directory; pass `--out /tmp/report.html` to write
elsewhere. The report is a single offline HTML file with inline CSS/SVG and
embedded JSON, so it can be opened directly from a committed branch with no
network access. Autoresearch runs also write `report.html` automatically during
finalization. `run-summary.html` remains the compact lab notebook summary, while
`report.html` is the visual verification surface with plots, leaderboard rows,
frontier highlights, threshold estimate notes, and provenance.
````

- [ ] **Step 4: Update CLAUDE**

In `CLAUDE.md`, after the issue `#10` command block, add:

````markdown
For issue `#11` and visual run verification, use:

```sh
python3 -m autoqec_search.cli report --root . --run results/search/<campaign>/<run-id>
```

The installed form is `autoqec-search report`. The default output is
`<run>/report.html`; `--out` can write a copy elsewhere. The file is
self-contained and offline-safe: inline CSS/SVG plus embedded JSON, with no
network assets. Autoresearch finalization writes `report.html` automatically
alongside `run-summary.html`; use `run-summary.html` for the compact lab
notebook and `report.html` for visual verification.
````

- [ ] **Step 5: Run docs tests**

Run:

```bash
python3 -m pytest tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md tests/test_search_docs.py
git commit -m "docs: document search report workflow"
```

---

### Task 7: Full Verification

**Files:**
- No source edits expected.

- [ ] **Step 1: Run targeted report suite**

Run:

```bash
python3 -m pytest tests/test_search_report.py tests/test_search_run_cli.py tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 2: Run broader search-layer suite**

Run:

```bash
python3 -m pytest tests/test_search_*.py -q
```

Expected: PASS.

- [ ] **Step 3: Run workspace validation**

Run:

```bash
python3 -m autoqec_search.cli validate --root .
```

Expected output includes:

```text
validated search workspace under .:
```

- [ ] **Step 4: Generate a fixture report manually**

Run:

```bash
python3 -m autoqec_search.cli report --root . --run results/search/rotated-surface-baseline/2026-06-09-example --out /tmp/autoqec-issue11-report.html
```

Expected output includes:

```text
wrote search report to /tmp/autoqec-issue11-report.html
```

Then run:

```bash
grep -E 'https?://' /tmp/autoqec-issue11-report.html
```

Expected: no output and exit code `1`.

- [ ] **Step 5: Check git status**

Run:

```bash
git status --short
```

Expected: clean, unless the implementation-plan file is intentionally left uncommitted in the current planning session.
