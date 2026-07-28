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


def _points_by_key(
    *,
    run_index: int,
    label: str,
    run_root: Path,
    model: dict[str, Any],
) -> dict[tuple[str, str, float], list[dict[str, Any]]]:
    points = model.get("points", [])
    if not isinstance(points, list):
        raise SearchIntegrityError(f"report points must be a list: {run_root}")
    grouped: dict[tuple[str, str, float], list[dict[str, Any]]] = defaultdict(list)
    provenance = model.get("provenance", {})
    for point in points:
        if not isinstance(point, dict):
            raise SearchIntegrityError(f"report point must be an object: {run_root}")
        key = _point_key(point)
        grouped[key].append(
            {
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
        )
    return dict(grouped)


def _distance_delta(row: dict[str, Any], best_distance: int | None) -> int | None:
    # In AutoQEC, larger code distance is preferred, so deltas are centered on
    # the highest observed distance in the comparison key.
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
    run_count = len(run_roots)
    loaded_runs: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, float], list[dict[str, Any]]] = defaultdict(list)
    for index, raw_run_root in enumerate(run_roots):
        run_root = _normalize_run_path(root, raw_run_root).resolve()
        label = _label_for(index, run_root, labels)
        model = build_report_model(root, run_root)
        loaded_runs.append(
            _run_entry(root=root, run_root=run_root, label=label, model=model)
        )
        for key, rows in _points_by_key(
            run_index=index,
            label=label,
            run_root=run_root,
            model=model,
        ).items():
            by_key[key].extend(rows)

    comparable_keys = sorted(
        key
        for key, rows in by_key.items()
        if len({row["run_index"] for row in rows}) == run_count
    )
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


def _provenance_rows_html(model: dict[str, Any]) -> str:
    rows: list[str] = []
    for run in model["runs"]:
        provenance = run.get("provenance", {})
        rows.append(
            "<tr>"
            f"<td>{_html(run['label'])}</td>"
            f"<td>{_html(run['campaign_id'])}</td>"
            f"<td>{_html(run['run_id'])}</td>"
            f"<td>{_html(run['mode'])}</td>"
            f"<td>{_html(provenance.get('git_sha'))}</td>"
            f"<td>{_html(provenance.get('rsinter'))}</td>"
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
  <h2>Provenance</h2>
  <table>
    <thead>
      <tr><th>Label</th><th>Campaign</th><th>Run</th><th>Mode</th><th>Git SHA</th><th>rsinter</th></tr>
    </thead>
    <tbody>{_provenance_rows_html(model)}</tbody>
  </table>
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
    json_path = html_path.with_suffix(".json")
    try:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_compare_candidates_html(model))
        json_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        raise SearchIntegrityError(
            f"could not write candidate comparison to {html_path}: {exc}"
        ) from exc
    return {"html": html_path, "json": json_path}
