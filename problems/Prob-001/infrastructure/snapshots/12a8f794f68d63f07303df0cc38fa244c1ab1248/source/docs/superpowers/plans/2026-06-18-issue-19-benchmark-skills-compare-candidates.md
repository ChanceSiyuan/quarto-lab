# Issue 19 Benchmark Skills And Compare-Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the issue #19 benchmark skill series and a tested cross-run `compare-candidates` review command.

**Architecture:** Keep the benchmark skills as conversation-first wrappers over existing `autoqec-search` commands. Put durable comparison logic in `src/autoqec_search/compare_candidates.py`, reusing `autoqec_search.report.build_report_model()` for run normalization and mirroring the artifact-writing style of `strategy_compare.py`.

**Tech Stack:** Python 3.14-compatible stdlib, pytest, existing `autoqec_search` package, Markdown project skills, self-contained HTML with inline CSS and embedded escaped JSON.

## Global Constraints

- Do not introduce a new benchmark execution abstraction below `autoqec-search eval/run`.
- Do not replace rsinter dispatch.
- Do not add new decoder backends.
- Do not implement full BB72 published-reference reproduction.
- Do not rank cross-task runs; default comparability is shared `(task_id, decoder_id, p)`.
- Do not add Cryochamber or message-surface delivery.
- Do not make automatic Zoo promotion decisions from comparison reports.
- Default tests must not require expensive real rsinter benchmarks.
- Generated comparison HTML must contain no `http://` or `https://`.
- Incomparable runs must fail clearly with `incomparable runs: no shared task/decoder/p grid`.

---

## File Structure

- Create `src/autoqec_search/compare_candidates.py`: load report models, derive comparable points, classify winners, render offline HTML, and write sibling JSON/HTML artifacts.
- Modify `src/autoqec_search/cli.py`: add `compare-candidates` parser and dispatch.
- Create `tests/test_search_compare_candidates.py`: focused unit and CLI coverage for comparison behavior.
- Create `skills/benchmark-code/SKILL.md`: top-level benchmark orchestrator skill.
- Create `skills/bench-runner-distance/SKILL.md`: distance runner skill.
- Create `skills/bench-runner-mc-ler/SKILL.md`: MC-LER runner skill.
- Create `skills/compare-candidates/SKILL.md`: comparison review skill.
- Create or modify `tests/test_benchmark_skills.py`: source tests for the four skill documents.
- Modify `README.md`: document the benchmark skill series and `compare-candidates` CLI.
- Modify `CLAUDE.md`: add issue #19 operational guidance.
- Modify `tests/test_search_docs.py`: assert the new docs remain present.

---

### Task 1: Build The Compare-Candidates Core

**Files:**
- Create: `src/autoqec_search/compare_candidates.py`
- Test: `tests/test_search_compare_candidates.py`

**Interfaces:**
- Consumes: `autoqec_search.report.build_report_model(root: Path, run_root: Path) -> dict[str, Any]`
- Produces:
  - `ComparisonError(SearchIntegrityError)`
  - `compare_candidate_runs(root: Path, run_roots: list[Path], labels: list[str] | None = None) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for strong, tentative, and incomparable comparisons**

Create `tests/test_search_compare_candidates.py` with helpers that monkeypatch the report model builder. Use synthetic models instead of copying full run trees so the winner logic is isolated and fast.

```python
from __future__ import annotations

from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError


def _model(
    *,
    campaign_id: str,
    run_id: str,
    candidate_id: str,
    task_id: str = "task-a",
    decoder_id: str = "decoder-a",
    p: float = 0.01,
    ler: float = 0.01,
    ci_low: float = 0.009,
    ci_high: float = 0.011,
    distance: int = 3,
) -> dict:
    return {
        "schema_version": 1,
        "provenance": {
            "campaign_id": campaign_id,
            "run_id": run_id,
            "mode": "eval",
            "generated_at": "2026-06-18T00:00:00Z",
            "autoqec_version": "0.1.0",
            "git_sha": "abc123",
            "branch": "main",
            "rsinter": "rsinter fake",
            "seed": 7,
            "wall_clock_seconds": None,
        },
        "counts": {
            "candidates": 1,
            "completed": 1,
            "crash": 0,
            "placeholder": 0,
            "frontier": 1,
            "points": 1,
        },
        "candidates": [
            {
                "candidate_id": candidate_id,
                "distance": distance,
                "distance_method": "copied-zoo-exact",
                "distance_bound_type": "exact",
                "status": "evaluated",
                "n": 9,
                "k": 1,
                "css_commute": True,
            }
        ],
        "manifests": [
            {
                "candidate_id": candidate_id,
                "task_id": task_id,
                "decoder_id": decoder_id,
                "status": "completed",
                "decoder_parameters": {},
            }
        ],
        "points": [
            {
                "candidate_id": candidate_id,
                "distance": distance,
                "task_id": task_id,
                "decoder_id": decoder_id,
                "decoder_parameters": {},
                "p": p,
                "rounds": 9,
                "shots": 1000,
                "errors": int(round(ler * 1000)),
                "ler": ler,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "seconds": 1.0,
            }
        ],
        "leaderboard": [],
        "frontier": [],
        "verdicts": [],
        "reference_check": None,
    }


def test_compare_candidate_runs_names_strong_winner(monkeypatch, tmp_path: Path) -> None:
    from autoqec_search import compare_candidates

    models = {
        (tmp_path / "run-a").resolve(): _model(
            campaign_id="campaign-a",
            run_id="run-a",
            candidate_id="candidate-a",
            ler=0.010,
            ci_low=0.009,
            ci_high=0.011,
        ),
        (tmp_path / "run-b").resolve(): _model(
            campaign_id="campaign-b",
            run_id="run-b",
            candidate_id="candidate-b",
            ler=0.020,
            ci_low=0.019,
            ci_high=0.021,
        ),
    }

    def fake_build_report_model(root: Path, run_root: Path) -> dict:
        return models[run_root.resolve()]

    monkeypatch.setattr(compare_candidates, "build_report_model", fake_build_report_model)
    model = compare_candidates.compare_candidate_runs(
        tmp_path,
        [tmp_path / "run-a", tmp_path / "run-b"],
        labels=["A", "B"],
    )

    assert model["status"] == "comparable"
    assert model["overall"]["classification"] == "strong"
    assert model["overall"]["winner_label"] == "A"
    assert model["comparisons"][0]["winner"]["classification"] == "strong"
    assert model["comparisons"][0]["winner"]["winner_label"] == "A"
    assert model["comparisons"][0]["rows"][0]["ler_delta"] == 0.0
    assert model["comparisons"][0]["rows"][1]["ler_delta"] == pytest.approx(0.01)


def test_compare_candidate_runs_marks_overlapping_ci_as_tentative(
    monkeypatch, tmp_path: Path
) -> None:
    from autoqec_search import compare_candidates

    models = {
        (tmp_path / "run-a").resolve(): _model(
            campaign_id="campaign-a",
            run_id="run-a",
            candidate_id="candidate-a",
            ler=0.010,
            ci_low=0.008,
            ci_high=0.014,
        ),
        (tmp_path / "run-b").resolve(): _model(
            campaign_id="campaign-b",
            run_id="run-b",
            candidate_id="candidate-b",
            ler=0.012,
            ci_low=0.009,
            ci_high=0.015,
        ),
    }

    def fake_build_report_model(root: Path, run_root: Path) -> dict:
        return models[run_root.resolve()]

    monkeypatch.setattr(compare_candidates, "build_report_model", fake_build_report_model)
    model = compare_candidates.compare_candidate_runs(
        tmp_path,
        [tmp_path / "run-a", tmp_path / "run-b"],
    )

    assert model["overall"]["classification"] == "no-clear-winner"
    assert model["comparisons"][0]["winner"]["classification"] == "tentative"


def test_compare_candidate_runs_rejects_incomparable_runs(
    monkeypatch, tmp_path: Path
) -> None:
    from autoqec_search import compare_candidates

    models = {
        (tmp_path / "run-a").resolve(): _model(
            campaign_id="campaign-a",
            run_id="run-a",
            candidate_id="candidate-a",
            task_id="task-a",
        ),
        (tmp_path / "run-b").resolve(): _model(
            campaign_id="campaign-b",
            run_id="run-b",
            candidate_id="candidate-b",
            task_id="task-b",
        ),
    }

    def fake_build_report_model(root: Path, run_root: Path) -> dict:
        return models[run_root.resolve()]

    monkeypatch.setattr(compare_candidates, "build_report_model", fake_build_report_model)

    with pytest.raises(
        SearchIntegrityError,
        match="incomparable runs: no shared task/decoder/p grid",
    ):
        compare_candidates.compare_candidate_runs(
            tmp_path,
            [tmp_path / "run-a", tmp_path / "run-b"],
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_compare_candidates.py -q
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `autoqec_search.compare_candidates`.

- [ ] **Step 3: Implement the comparison model**

Create `src/autoqec_search/compare_candidates.py` with the following implementation skeleton. Keep function names and payload keys exactly as shown because later tasks depend on them.

```python
from __future__ import annotations

import json
from collections import defaultdict
from html import escape
from math import isfinite
from pathlib import Path
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.report import build_report_model


COMPARISON_SCHEMA_VERSION = 1
INCOMPARABLE_MESSAGE = "incomparable runs: no shared task/decoder/p grid"


class ComparisonError(SearchIntegrityError):
    """Raised when candidate comparison inputs cannot produce a ranking."""


def _finite_float(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SearchIntegrityError(f"{label} must be a finite number")
    numeric = float(value)
    if not isfinite(numeric):
        raise SearchIntegrityError(f"{label} must be a finite number")
    return numeric


def _label_for(index: int, run_root: Path, labels: list[str] | None) -> str:
    if labels is not None:
        return labels[index]
    return run_root.name


def _normalize_run_path(root: Path, run_root: Path) -> Path:
    return run_root if run_root.is_absolute() else root / run_root


def _point_key(point: dict[str, Any]) -> tuple[str, str, float]:
    return (
        str(point["task_id"]),
        str(point["decoder_id"]),
        _finite_float(point["p"], label="point p"),
    )


def _run_entry(
    *,
    root: Path,
    run_root: Path,
    label: str,
    model: dict[str, Any],
) -> dict[str, Any]:
    provenance = model.get("provenance", {})
    if not isinstance(provenance, dict):
        raise SearchIntegrityError(f"invalid report provenance for {run_root}")
    counts = model.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    return {
        "label": label,
        "path": str(run_root),
        "campaign_id": provenance.get("campaign_id"),
        "run_id": provenance.get("run_id"),
        "mode": provenance.get("mode"),
        "counts": {
            "candidates": int(counts.get("candidates", 0)),
            "completed": int(counts.get("completed", 0)),
            "crash": int(counts.get("crash", 0)),
            "placeholder": int(counts.get("placeholder", 0)),
            "points": int(counts.get("points", 0)),
        },
        "provenance": provenance,
    }


def _best_points_by_key(
    *,
    run_index: int,
    label: str,
    run_root: Path,
    model: dict[str, Any],
) -> dict[tuple[str, str, float], dict[str, Any]]:
    points = model.get("points", [])
    if not isinstance(points, list):
        raise SearchIntegrityError(f"report points must be a list: {run_root}")
    best: dict[tuple[str, str, float], dict[str, Any]] = {}
    provenance = model.get("provenance", {})
    for point in points:
        if not isinstance(point, dict):
            raise SearchIntegrityError(f"report point must be an object: {run_root}")
        key = _point_key(point)
        row = {
            "run_index": run_index,
            "run_label": label,
            "run_path": str(run_root),
            "campaign_id": provenance.get("campaign_id"),
            "run_id": provenance.get("run_id"),
            "candidate_id": point["candidate_id"],
            "task_id": point["task_id"],
            "decoder_id": point["decoder_id"],
            "decoder_parameters": point.get("decoder_parameters", {}),
            "distance": point.get("distance"),
            "p": _finite_float(point["p"], label="point p"),
            "rounds": int(point["rounds"]),
            "shots": int(point["shots"]),
            "errors": int(point["errors"]),
            "ler": _finite_float(point["ler"], label="point ler"),
            "ci_low": _finite_float(point["ci_low"], label="point ci_low"),
            "ci_high": _finite_float(point["ci_high"], label="point ci_high"),
            "seconds": _finite_float(point["seconds"], label="point seconds"),
        }
        previous = best.get(key)
        if previous is None or row["ler"] < previous["ler"]:
            best[key] = row
    return best


def _distance_delta(row: dict[str, Any], best_distance: int | None) -> int | None:
    distance = row.get("distance")
    if type(distance) is not int or best_distance is None:
        return None
    return distance - best_distance


def _classify_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 2:
        return {"classification": "incomparable", "winner_label": None}
    sorted_rows = sorted(rows, key=lambda row: (float(row["ler"]), str(row["run_label"])))
    best = sorted_rows[0]
    tied = [
        row for row in sorted_rows if float(row["ler"]) == float(best["ler"])
    ]
    if len(tied) > 1:
        return {
            "classification": "tie",
            "winner_label": None,
            "winner_run_index": None,
            "winner_candidate_id": None,
        }
    strong = all(
        float(best["ci_high"]) < float(row["ci_low"]) for row in sorted_rows[1:]
    )
    return {
        "classification": "strong" if strong else "tentative",
        "winner_label": best["run_label"],
        "winner_run_index": best["run_index"],
        "winner_candidate_id": best["candidate_id"],
    }


def _overall_winner(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    if not comparisons:
        return {"classification": "no-clear-winner", "winner_label": None}
    strong_wins = [
        comparison["winner"]
        for comparison in comparisons
        if comparison["winner"]["classification"] == "strong"
    ]
    if len(strong_wins) != len(comparisons):
        return {"classification": "no-clear-winner", "winner_label": None}
    labels = {winner["winner_label"] for winner in strong_wins}
    if len(labels) != 1:
        return {"classification": "no-clear-winner", "winner_label": None}
    return {"classification": "strong", "winner_label": next(iter(labels))}


def compare_candidate_runs(
    root: Path,
    run_roots: list[Path],
    labels: list[str] | None = None,
) -> dict[str, Any]:
    if len(run_roots) < 2:
        raise ComparisonError("compare-candidates requires at least two runs")
    if labels is not None and len(labels) != len(run_roots):
        raise ComparisonError("label count must match run count")

    root = root.resolve()
    loaded_runs: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, float], list[dict[str, Any]]] = defaultdict(list)
    for index, raw_run_root in enumerate(run_roots):
        run_root = _normalize_run_path(root, raw_run_root).resolve()
        label = _label_for(index, run_root, labels)
        model = build_report_model(root, run_root)
        loaded_runs.append(
            _run_entry(root=root, run_root=run_root, label=label, model=model)
        )
        for key, row in _best_points_by_key(
            run_index=index,
            label=label,
            run_root=run_root,
            model=model,
        ).items():
            by_key[key].append(row)

    comparable_keys = sorted(key for key, rows in by_key.items() if len(rows) >= 2)
    if not comparable_keys:
        raise ComparisonError(INCOMPARABLE_MESSAGE)

    comparisons: list[dict[str, Any]] = []
    for task_id, decoder_id, p_value in comparable_keys:
        rows = sorted(
            by_key[(task_id, decoder_id, p_value)],
            key=lambda row: (float(row["ler"]), str(row["run_label"])),
        )
        best_distance = max(
            [row["distance"] for row in rows if type(row.get("distance")) is int],
            default=None,
        )
        best_ler = float(rows[0]["ler"])
        normalized_rows = []
        for row in rows:
            copied = dict(row)
            copied["distance_delta"] = _distance_delta(copied, best_distance)
            copied["ler_delta"] = float(copied["ler"]) - best_ler
            normalized_rows.append(copied)
        comparisons.append(
            {
                "key": {
                    "task_id": task_id,
                    "decoder_id": decoder_id,
                    "p": p_value,
                },
                "winner": _classify_rows(normalized_rows),
                "rows": normalized_rows,
            }
        )

    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "status": "comparable",
        "root": str(root),
        "runs": loaded_runs,
        "comparisons": comparisons,
        "overall": _overall_winner(comparisons),
    }
```

- [ ] **Step 4: Run tests to verify the core passes**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_compare_candidates.py -q
```

Expected: PASS for the three tests added in this task.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/autoqec_search/compare_candidates.py tests/test_search_compare_candidates.py
git commit -m "feat: add candidate comparison model"
```

---

### Task 2: Add Offline HTML/JSON Artifacts And CLI

**Files:**
- Modify: `src/autoqec_search/compare_candidates.py`
- Modify: `src/autoqec_search/cli.py`
- Modify: `tests/test_search_compare_candidates.py`
- Test: `tests/test_search_cli.py`

**Interfaces:**
- Consumes: `compare_candidate_runs(root: Path, run_roots: list[Path], labels: list[str] | None = None) -> dict[str, Any]`
- Produces:
  - `render_compare_candidates_html(model: dict[str, Any]) -> str`
  - `write_compare_candidates(model: dict[str, Any], html_path: Path) -> dict[str, Path]`
  - CLI subcommand `compare-candidates`

- [ ] **Step 1: Add failing tests for HTML writing and CLI dispatch**

Append these tests to `tests/test_search_compare_candidates.py`.

```python
def test_render_compare_candidates_html_is_offline(monkeypatch, tmp_path: Path) -> None:
    from autoqec_search import compare_candidates

    models = {
        (tmp_path / "run-a").resolve(): _model(
            campaign_id="campaign-a",
            run_id="run-a",
            candidate_id="candidate-a",
            ler=0.010,
            ci_low=0.009,
            ci_high=0.011,
        ),
        (tmp_path / "run-b").resolve(): _model(
            campaign_id="campaign-b",
            run_id="run-b",
            candidate_id="candidate-b",
            ler=0.020,
            ci_low=0.019,
            ci_high=0.021,
        ),
    }

    def fake_build_report_model(root: Path, run_root: Path) -> dict:
        return models[run_root.resolve()]

    monkeypatch.setattr(compare_candidates, "build_report_model", fake_build_report_model)
    model = compare_candidates.compare_candidate_runs(
        tmp_path,
        [tmp_path / "run-a", tmp_path / "run-b"],
        labels=["A", "B"],
    )
    html = compare_candidates.render_compare_candidates_html(model)
    written = compare_candidates.write_compare_candidates(model, tmp_path / "compare.html")

    assert "AutoQEC Candidate Comparison" in html
    assert "strong" in html
    assert "candidate-a" in html
    assert "candidate-b" in html
    assert "http://" not in html
    assert "https://" not in html
    assert written["html"] == tmp_path / "compare.html"
    assert written["json"] == tmp_path / "compare.json"
    assert written["html"].is_file()
    assert written["json"].is_file()


def test_compare_candidates_cli_writes_artifacts(monkeypatch, tmp_path: Path) -> None:
    from autoqec_search import compare_candidates
    from autoqec_search.cli import main

    models = {
        (tmp_path / "run-a").resolve(): _model(
            campaign_id="campaign-a",
            run_id="run-a",
            candidate_id="candidate-a",
            ler=0.010,
            ci_low=0.009,
            ci_high=0.011,
        ),
        (tmp_path / "run-b").resolve(): _model(
            campaign_id="campaign-b",
            run_id="run-b",
            candidate_id="candidate-b",
            ler=0.020,
            ci_low=0.019,
            ci_high=0.021,
        ),
    }

    def fake_build_report_model(root: Path, run_root: Path) -> dict:
        return models[run_root.resolve()]

    monkeypatch.setattr(compare_candidates, "build_report_model", fake_build_report_model)
    code = main(
        [
            "compare-candidates",
            "--root",
            str(tmp_path),
            "--run",
            "run-a",
            "--run",
            "run-b",
            "--label",
            "A",
            "--label",
            "B",
            "--out",
            str(tmp_path / "candidate-comparison.html"),
        ]
    )

    assert code == 0
    assert (tmp_path / "candidate-comparison.html").is_file()
    assert (tmp_path / "candidate-comparison.json").is_file()


def test_compare_candidates_cli_returns_one_for_incomparable(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from autoqec_search import compare_candidates
    from autoqec_search.cli import main

    models = {
        (tmp_path / "run-a").resolve(): _model(
            campaign_id="campaign-a",
            run_id="run-a",
            candidate_id="candidate-a",
            task_id="task-a",
        ),
        (tmp_path / "run-b").resolve(): _model(
            campaign_id="campaign-b",
            run_id="run-b",
            candidate_id="candidate-b",
            task_id="task-b",
        ),
    }

    def fake_build_report_model(root: Path, run_root: Path) -> dict:
        return models[run_root.resolve()]

    monkeypatch.setattr(compare_candidates, "build_report_model", fake_build_report_model)
    code = main(
        [
            "compare-candidates",
            "--root",
            str(tmp_path),
            "--run",
            "run-a",
            "--run",
            "run-b",
            "--out",
            str(tmp_path / "candidate-comparison.html"),
        ]
    )
    captured = capsys.readouterr()

    assert code == 1
    assert "incomparable runs: no shared task/decoder/p grid" in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_compare_candidates.py -q
```

Expected: FAIL because `render_compare_candidates_html`, `write_compare_candidates`, and the CLI command are not implemented yet.

- [ ] **Step 3: Implement renderer and writer**

Append these functions to `src/autoqec_search/compare_candidates.py`.

```python
def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _html(value: Any) -> str:
    return escape(_display(value), quote=True)


def _json_for_html(model: dict[str, Any]) -> str:
    return (
        json.dumps(model, indent=2, sort_keys=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _comparison_rows_html(model: dict[str, Any]) -> str:
    rows: list[str] = []
    for comparison in model["comparisons"]:
        key = comparison["key"]
        winner = comparison["winner"]
        for row in comparison["rows"]:
            rows.append(
                "<tr>"
                f"<td>{_html(key['task_id'])}</td>"
                f"<td>{_html(key['decoder_id'])}</td>"
                f"<td>{_html(key['p'])}</td>"
                f"<td>{_html(row['run_label'])}</td>"
                f"<td>{_html(row['candidate_id'])}</td>"
                f"<td>{_html(row['distance'])}</td>"
                f"<td>{_html(row['ler'])}</td>"
                f"<td>[{_html(row['ci_low'])}, {_html(row['ci_high'])}]</td>"
                f"<td>{_html(row['ler_delta'])}</td>"
                f"<td>{_html(row['distance_delta'])}</td>"
                f"<td>{_html(winner['classification'])}</td>"
                f"<td>{_html(winner.get('winner_label'))}</td>"
                "</tr>"
            )
    return "".join(rows)


def _run_summary_rows_html(model: dict[str, Any]) -> str:
    rows: list[str] = []
    for run in model["runs"]:
        counts = run["counts"]
        rows.append(
            "<tr>"
            f"<td>{_html(run['label'])}</td>"
            f"<td>{_html(run['campaign_id'])}</td>"
            f"<td>{_html(run['run_id'])}</td>"
            f"<td>{_html(counts['completed'])}</td>"
            f"<td>{_html(counts['placeholder'])}</td>"
            f"<td>{_html(counts['crash'])}</td>"
            f"<td>{_html(run['path'])}</td>"
            "</tr>"
        )
    return "".join(rows)


def render_compare_candidates_html(model: dict[str, Any]) -> str:
    payload = _json_for_html(model)
    overall = model["overall"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoQEC Candidate Comparison</title>
  <style>
    body {{ color: #1f2933; font-family: system-ui, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0 2rem; width: 100%; }}
    th, td {{ border: 1px solid #c7d0d9; padding: 0.4rem 0.55rem; text-align: left; }}
    th {{ background: #eef2f6; }}
    code, pre {{ background: #f6f8fa; }}
    pre {{ padding: 1rem; overflow: auto; }}
    .status {{ font-weight: 700; }}
  </style>
</head>
<body>
  <h1>AutoQEC Candidate Comparison</h1>
  <p class="status">Status: {_html(model['status'])}</p>
  <p>Overall: <strong>{_html(overall['classification'])}</strong>; winner: <strong>{_html(overall.get('winner_label'))}</strong></p>
  <h2>Per-Key Rankings</h2>
  <table>
    <thead>
      <tr>
        <th>Task</th><th>Decoder</th><th>p</th><th>Run</th><th>Candidate</th>
        <th>Distance</th><th>LER</th><th>CI</th><th>LER Delta</th>
        <th>Distance Delta</th><th>Classification</th><th>Winner</th>
      </tr>
    </thead>
    <tbody>{_comparison_rows_html(model)}</tbody>
  </table>
  <h2>Runs</h2>
  <table>
    <thead>
      <tr><th>Label</th><th>Campaign</th><th>Run</th><th>Completed</th><th>Placeholder</th><th>Crash</th><th>Path</th></tr>
    </thead>
    <tbody>{_run_summary_rows_html(model)}</tbody>
  </table>
  <h2>Comparison JSON</h2>
  <pre>{escape(payload)}</pre>
</body>
</html>
"""


def write_compare_candidates(model: dict[str, Any], html_path: Path) -> dict[str, Path]:
    stem = html_path.with_suffix("")
    actual_html_path = stem.with_suffix(".html")
    json_path = stem.with_suffix(".json")
    actual_html_path.parent.mkdir(parents=True, exist_ok=True)
    actual_html_path.write_text(render_compare_candidates_html(model))
    json_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    return {"html": actual_html_path, "json": json_path}
```

- [ ] **Step 4: Add CLI parser and dispatch**

Modify `src/autoqec_search/cli.py`.

Add this import near the existing imports:

```python
from autoqec_search.compare_candidates import (
    compare_candidate_runs,
    write_compare_candidates,
)
```

Add this parser block after the existing `compare-strategies` parser block:

```python
    compare_candidates_parser = subparsers.add_parser(
        "compare-candidates",
        help="Compare completed candidate points across two or more search runs",
    )
    compare_candidates_parser.add_argument("--root", default=".")
    compare_candidates_parser.add_argument("--run", action="append", required=True)
    compare_candidates_parser.add_argument("--label", action="append", default=None)
    compare_candidates_parser.add_argument("--out", required=True)
```

Add this dispatch block before the final unknown-command handling:

```python
        if args.command == "compare-candidates":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            model = compare_candidate_runs(
                root,
                [Path(run_path) for run_path in args.run],
                labels=args.label,
            )
            written = write_compare_candidates(model, Path(args.out))
            print(f"wrote candidate comparison to {written['html']}")
            return 0
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_compare_candidates.py -q
```

Expected: PASS.

- [ ] **Step 6: Run CLI parser smoke tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_cli.py tests/test_search_compare_candidates.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add src/autoqec_search/compare_candidates.py src/autoqec_search/cli.py tests/test_search_compare_candidates.py
git commit -m "feat: add compare-candidates CLI"
```

---

### Task 3: Add Benchmark Skill Documents

**Files:**
- Create: `skills/benchmark-code/SKILL.md`
- Create: `skills/bench-runner-distance/SKILL.md`
- Create: `skills/bench-runner-mc-ler/SKILL.md`
- Create: `skills/compare-candidates/SKILL.md`
- Create: `tests/test_benchmark_skills.py`

**Interfaces:**
- Consumes: Existing command names `autoqec-search preflight`, `autoqec-search eval`, `autoqec-search run`, `autoqec-search report`, `autoqec-search compare-candidates`.
- Produces: Four discoverable project skills with explicit approval and negative-control instructions.

- [ ] **Step 1: Write failing source tests for skill files**

Create `tests/test_benchmark_skills.py`.

```python
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _skill_text(name: str) -> str:
    return (REPO_ROOT / "skills" / name / "SKILL.md").read_text()


def test_benchmark_code_skill_documents_approval_and_dispatch() -> None:
    text = _skill_text("benchmark-code")

    assert "benchmark-code" in text
    assert "explicit approval" in text
    assert "autoqec-search preflight" in text
    assert "bench-runner-distance" in text
    assert "bench-runner-mc-ler" in text
    assert "must not run" in text
    assert "distance" in text
    assert "mc-ler" in text


def test_bench_runner_distance_skill_documents_exact_distance_contract() -> None:
    text = _skill_text("bench-runner-distance")

    assert "bench-runner-distance" in text
    assert "distance.json" in text
    assert 'bound_type: "exact"' in text
    assert "rotated surface" in text
    assert "distance 3" in text
    assert "not promotion-safe" in text
    assert "missing backend" in text


def test_bench_runner_mc_ler_skill_documents_existing_cli_path() -> None:
    text = _skill_text("bench-runner-mc-ler")

    assert "bench-runner-mc-ler" in text
    assert "autoqec-search eval" in text
    assert "autoqec-search run" in text
    assert "autoqec-search report" in text
    assert "autoqec-search preflight" in text
    assert "BB72 OSD1 smoke" in text
    assert "OSD10" in text
    assert "missing-dependency" in text


def test_compare_candidates_skill_documents_incomparable_refusal() -> None:
    text = _skill_text("compare-candidates")

    assert "compare-candidates" in text
    assert "autoqec-search compare-candidates" in text
    assert "two or more run directories" in text
    assert "task/decoder/p" in text
    assert "incomparable runs" in text
    assert "must not summarize" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_benchmark_skills.py -q
```

Expected: FAIL because the four skill files do not exist.

- [ ] **Step 3: Create `benchmark-code` skill**

Create `skills/benchmark-code/SKILL.md`.

```markdown
---
name: benchmark-code
description: Use when a user wants to benchmark an AutoQEC code or campaign through distance or Monte Carlo LER workflows.
---

# benchmark-code

## Overview

This is the top-level benchmark orchestrator for AutoQEC. It conducts
conversation-first intake, runs preflight, summarizes the proposed execution,
requires explicit approval, and dispatches to `bench-runner-distance` or
`bench-runner-mc-ler`.

It is intentionally thin. It drives the existing `autoqec-search` CLI and does
not implement distance algorithms, rsinter dispatch, manifest parsing, report
rendering, or Zoo promotion.

## Workflow

1. Resolve the target:
   - an existing campaign id,
   - an existing run directory,
   - a candidate directory,
   - or an exact Zoo instance path.
2. Resolve benchmark type:
   - `distance`
   - `mc-ler`
3. Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
```

4. Summarize the execution plan in natural language:
   - target
   - benchmark type
   - suite/task/decoder choices when known
   - p-list or distance method when known
   - run id and output directory when applicable
   - budget or wall-clock limit when applicable
5. Ask for explicit approval.
6. Before approval, you must not run benchmark commands or write run artifacts.
7. After approval, dispatch:
   - distance work to `bench-runner-distance`
   - MC-LER work to `bench-runner-mc-ler`
8. Report generated run and report paths.

## Approval Gate

Accepted approval language includes "approved", "looks good", "run it", and
"continue".

Non-approval language includes "wait", "not yet", "show me first", and "do not
run". In those cases, say that no benchmark command is run and no run artifacts
are written.

## Rules

- Always run or propose `autoqec-search preflight` before execution.
- Stop on a failing preflight unless the user explicitly asks only for a dry
  command summary.
- Do not silently reinterpret a distance upper bound as exact distance.
- Do not promote results into `zoo/`; use the existing promotion workflow only
  after a separate user decision.
- Do not claim BB72 OSD1 smoke data satisfies the deferred published OSD10
  reference validation.
- Missing backend messages must remain precise; do not mask them with generic
  advice.
```

- [ ] **Step 4: Create `bench-runner-distance` skill**

Create `skills/bench-runner-distance/SKILL.md`.

```markdown
---
name: bench-runner-distance
description: Use when running or reviewing deterministic AutoQEC code-distance benchmark results.
---

# bench-runner-distance

## Overview

This skill handles deterministic distance benchmarking for existing AutoQEC
campaign candidates and run artifacts. It is a thin wrapper over existing
`autoqec-search` candidate evaluation and `distance.json` contracts.

## Workflow

1. Resolve the target as one of:
   - a run candidate directory containing `distance.json`,
   - a campaign candidate selectable by `autoqec-search eval`,
   - or an exact Zoo instance path.
2. Run or inspect preflight:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
```

3. For an existing candidate directory, read:
   - `candidate.json`
   - `structure.json`
   - `distance.json`
4. For a campaign candidate, use the existing eval path after approval:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli eval --root . --campaign <campaign-id> --distance <d> --run-id <run-id>
```

5. Report:
   - candidate id
   - code family
   - structure status
   - distance
   - method
   - `bound_type`
   - whether the result is promotion-safe

## Rules

- Exact distance results must be reported as exact only when `bound_type: "exact"`
  is present or the legacy payload is clearly an exact copied Zoo
  distance.
- Upper-bound, unavailable, or malformed distances are not promotion-safe.
- The known rotated surface `d=3` check should report distance 3.
- Stop on missing backend or missing instance artifacts with the exact error
  message.
- Do not overwrite curated Zoo instance files.
- Do not run expensive external distance backends unless the user explicitly
  approves the command.

## Negative Controls

- If `distance.json` has `bound_type: "upper"`, say it is not promotion-safe.
- If the target has no exact recorded distance, stop and say which artifact is
  missing.
- If preflight reports a missing backend, do not write partial run artifacts.
```

- [ ] **Step 5: Create `bench-runner-mc-ler` skill**

Create `skills/bench-runner-mc-ler/SKILL.md`.

```markdown
---
name: bench-runner-mc-ler
description: Use when running or reviewing AutoQEC Monte Carlo logical-error-rate benchmark workflows.
---

# bench-runner-mc-ler

## Overview

This skill handles Monte Carlo logical-error-rate benchmarking through the
existing `autoqec-search eval`, `autoqec-search run`, and `autoqec-search
report` commands.

It does not implement rsinter dispatch directly.

## Workflow

1. Resolve whether the user wants:
   - a single-candidate evaluation, or
   - a campaign sweep.
2. Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
```

3. Summarize:
   - campaign id
   - suite id
   - task ids
   - decoder ids or decoder filters
   - p values or p filters
   - wall-clock budget for campaign runs
   - run id
   - report path
4. Ask for explicit approval before running benchmark commands.
5. For single-candidate work, run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli eval --root . --campaign <campaign-id> --distance <d> --run-id <run-id>
PYTHONPATH=src python3 -m autoqec_search.cli report --root . --run results/search/<campaign-id>/<run-id>
```

6. For campaign sweeps, run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign <campaign-id> --wall-clock <seconds>s --run-id <run-id> --allow-dirty-root
PYTHONPATH=src python3 -m autoqec_search.cli report --root . --run results/search/<campaign-id>/<run-id>
```

## Rules

- Preserve precise missing-dependency messages from preflight and eval.
- Do not write partial or garbage run artifacts after a missing-backend failure.
- Use committed or fixture-backed M1 data for fast verification.
- Real rsinter smoke runs are optional and should be called out as backend
  dependent.
- The BB72 OSD1 smoke artifact proves AutoQEC orchestration, report, and
  promotion flow. It does not satisfy the deferred BB72 OSD10 published
  reference validation tracked on the rstim side.

## Negative Controls

- If preflight cannot find rsinter, stop before eval/run.
- If general CSS support is missing for a CSS task, preserve the upstream
  required-feature message.
- If a manifest is placeholder or crash, report it as skipped rather than a
  completed MC-LER point.
```

- [ ] **Step 6: Create `compare-candidates` skill**

Create `skills/compare-candidates/SKILL.md`.

```markdown
---
name: compare-candidates
description: Use when comparing two or more AutoQEC search runs and ranking candidates by completed LER points.
---

# compare-candidates

## Overview

This is the review skill for cross-run candidate comparison. It calls
`autoqec-search compare-candidates` on two or more run directories and reports
the generated comparison report.

It must not summarize incomparable runs as a ranked comparison.

## Workflow

1. Resolve two or more run directories under `results/search/`.
2. Explain that the default comparability key is shared task/decoder/p.
3. Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-candidates \
  --root . \
  --run <run-a> \
  --run <run-b> \
  --out <output.html>
```

4. If labels are helpful, include:

```bash
--label <label-a> --label <label-b>
```

5. Report:
   - comparison HTML path
   - comparison JSON path
   - overall winner classification
   - overall winner reporting is strong-only
   - whether any winner is tentative because confidence intervals overlap

## Rules

- Require at least two run directories.
- Completed manifest points are the only ranked data.
- Placeholder and crash manifests are skipped and reported.
- Incomparable runs fail with `incomparable runs: no shared task/decoder/p grid`.
- Do not add a cross-task ranking by hand.
- Do not rank surface and BB runs unless they share task, decoder, and p values
  in the model.

## Output

The command writes:

Given `--out /tmp/compare.html`, the command writes:

- `/tmp/compare.html`
- `/tmp/compare.json`

The HTML report is self-contained and safe to open offline.
```

- [ ] **Step 7: Run skill tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_benchmark_skills.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add skills/benchmark-code/SKILL.md skills/bench-runner-distance/SKILL.md skills/bench-runner-mc-ler/SKILL.md skills/compare-candidates/SKILL.md tests/test_benchmark_skills.py
git commit -m "docs: add benchmark workflow skills"
```

---

### Task 4: Document Issue 19 Entry Points

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `tests/test_search_docs.py`

**Interfaces:**
- Consumes: CLI command `autoqec-search compare-candidates`
- Produces: Stable docs text asserted by tests

- [ ] **Step 1: Write failing docs tests**

Open `tests/test_search_docs.py` and add a new test near the existing search-layer docs tests.

```python
def test_issue19_benchmark_skills_and_compare_candidates_are_documented() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    for document in (readme, claude):
        assert "benchmark-code" in document
        assert "bench-runner-distance" in document
        assert "bench-runner-mc-ler" in document
        assert "compare-candidates" in document
        assert "autoqec-search compare-candidates" in document
        assert "task/decoder/p" in document
        assert "BB72 OSD1 smoke" in document
        assert "OSD10" in document
```

- [ ] **Step 2: Run docs test to verify it fails**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py::test_issue19_benchmark_skills_and_compare_candidates_are_documented -q
```

Expected: FAIL because README and CLAUDE do not yet document all new entry points.

- [ ] **Step 3: Update README**

Add this concise section near the search-layer command documentation in `README.md`.

```markdown
### Benchmark skills and candidate comparison

Issue #19 adds the full benchmark skill series:

- `benchmark-code` - conversation-first intake, preflight, approval, and dispatch.
- `bench-runner-distance` - deterministic distance review or eval-backed distance runs.
- `bench-runner-mc-ler` - MC-LER runs through existing `eval`, `run`, and `report` commands.
- `compare-candidates` - review two or more completed run directories.

The direct CLI comparison route is:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-candidates \
  --root . \
  --run results/search/<campaign-a>/<run-a> \
  --run results/search/<campaign-b>/<run-b> \
  --out /tmp/autoqec-candidates.html
```

Comparison requires a shared task/decoder/p grid. Runs with different benchmark
tasks fail as incomparable rather than receiving a misleading ranking.
Overall winner reporting is strong-only. Tentative point winners stay visible,
but the overall field stays `no-clear-winner` unless every shared point has the
same strong winner. The committed BB72 OSD1 smoke artifacts prove the AutoQEC
orchestration path; the deferred BB72 OSD10 published-reference curve remains
an rstim-side validation.
```

- [ ] **Step 4: Update CLAUDE**

Add this operational guidance near the search-layer section in `CLAUDE.md`.

```markdown
For issue `#19`, the benchmark skill series is intentionally thin:

- `benchmark-code` performs conversation-first intake, preflight, approval, and
  dispatch.
- `bench-runner-distance` uses existing distance artifacts and eval-backed
  distance generation.
- `bench-runner-mc-ler` routes through `autoqec-search eval`, `run`, and
  `report`.
- `compare-candidates` calls `autoqec-search compare-candidates` on two or more
  run directories.

Use:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-candidates --root . \
  --run results/search/<campaign-a>/<run-a> \
  --run results/search/<campaign-b>/<run-b> \
  --out /tmp/autoqec-candidates.html
```

Default comparability is shared task/decoder/p. Do not hand-rank runs with
different benchmark tasks. Overall winner reporting is strong-only. Tentative
point winners stay visible, but the overall field stays `no-clear-winner`
unless every shared point has the same strong winner. The BB72 OSD1 smoke run
is AutoQEC orchestration evidence, not the deferred OSD10 published-reference
validation.
```

- [ ] **Step 5: Run docs tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add README.md CLAUDE.md tests/test_search_docs.py
git commit -m "docs: document benchmark comparison workflow"
```

---

### Task 5: Final Validation And Issue 19 Acceptance

**Files:**
- Modify as needed only if validation reveals a defect in files touched by Tasks 1-4.

**Interfaces:**
- Consumes: all interfaces from Tasks 1-4.
- Produces: final verified implementation branch for issue #19.

- [ ] **Step 1: Run focused issue #19 tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_compare_candidates.py \
  tests/test_benchmark_skills.py \
  tests/test_search_cli.py \
  tests/test_search_docs.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run search workspace validation**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: output starts with `validated search workspace under .`.

- [ ] **Step 3: Run full test suite**

Run:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS, with the repository's expected deselected tests count.

- [ ] **Step 4: Run diff hygiene**

Run:

```bash
git diff --check HEAD
```

Expected: no output and exit code 0.

- [ ] **Step 5: Review final status**

Run:

```bash
git status --short
git log --oneline -5
```

Expected: only intentional committed changes are present. If there are unstaged
fixups from validation, return to the task that owns the failing behavior,
apply the fix there, rerun that task's focused tests, and commit the exact file
set listed in that task. Do not use a catch-all staging command.

- [ ] **Step 6: Prepare final summary**

Final summary must mention:

- four benchmark skills added
- `autoqec-search compare-candidates` added
- comparable runs produce offline HTML and JSON
- incomparable runs fail clearly
- validation commands and outcomes

---

## Self-Review Notes

- Spec coverage: Tasks 1-2 implement the Python comparison module, CLI, JSON/HTML artifacts, strong/tentative/incomparable behavior, and offline HTML requirement. Task 3 implements the four skills and approval/preflight/missing-backend documentation. Task 4 implements README/CLAUDE docs. Task 5 verifies the issue acceptance commands.
- Placeholder scan: the plan avoids open-ended markers and every testing task includes concrete test code.
- Type consistency: the plan defines `compare_candidate_runs`, `render_compare_candidates_html`, and `write_compare_candidates` in Task 1/2 and uses the same names in CLI and tests.
