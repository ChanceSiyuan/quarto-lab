from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError

from autoqec_search.baselines import load_surface_single_logical_baseline
from autoqec_search.load import SearchIntegrityError, load_search_workspace


SURFACE_COPY_COMPARISON_SCHEMA_VERSION = 1
TARGET_P = 0.001
ROW_SUPPORT_FIELDS = {
    "surface_single_ci_low": (
        "Support field for copied CI provenance: single-patch lower endpoint "
        "before the copied-block transform."
    ),
    "surface_single_ci_high": (
        "Support field for copied CI provenance: single-patch upper endpoint "
        "before the copied-block transform."
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(f"invalid JSON at {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"expected JSON object at {path}")
    return payload


def _finite_float(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SearchIntegrityError(f"{label} must be a finite number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise SearchIntegrityError(f"{label} must be a finite number")
    return numeric


def _plain_int(value: Any, *, label: str) -> int:
    if type(value) is not int:
        raise SearchIntegrityError(f"{label} must be an integer")
    return value


def _normalize_under_root(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _normalize_row(
    *,
    candidate_id: str,
    n: int,
    k: int,
    aggregation: str | None,
    point: dict[str, Any],
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "n": n,
        "k": k,
        "tanner_ler": _finite_float(point["ler"], label=f"{candidate_id} tanner ler"),
        "tanner_ci_low": _finite_float(
            point["ci_low"], label=f"{candidate_id} tanner ci_low"
        ),
        "tanner_ci_high": _finite_float(
            point["ci_high"], label=f"{candidate_id} tanner ci_high"
        ),
        "tanner_logical_failure_aggregation": aggregation,
        "surface_distance": None,
        "surface_physical_per_patch": None,
        "surface_copied_total_physical": None,
        "unused_physical_budget": None,
        "surface_single_ler": None,
        "surface_single_ci_low": None,
        "surface_single_ci_high": None,
        "surface_block_ler": None,
        "surface_block_ci_low": None,
        "surface_block_ci_high": None,
        "reason": None,
    }


def _rejected_row(
    *,
    candidate_id: str,
    n: int,
    k: int,
    aggregation: str | None,
    point: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    row = _normalize_row(
        candidate_id=candidate_id,
        n=n,
        k=k,
        aggregation=aggregation,
        point=point,
    )
    row["status"] = "rejected"
    row["reason"] = reason
    return row


def _accepted_row(
    *,
    candidate_id: str,
    n: int,
    k: int,
    aggregation: str,
    point: dict[str, Any],
    surface_row: dict[str, Any],
) -> dict[str, Any]:
    row = _normalize_row(
        candidate_id=candidate_id,
        n=n,
        k=k,
        aggregation=aggregation,
        point=point,
    )
    single_ler = _finite_float(
        surface_row["ler"], label=f"{candidate_id} surface single ler"
    )
    single_ci_low = _finite_float(
        surface_row["ci_low"], label=f"{candidate_id} surface single ci_low"
    )
    single_ci_high = _finite_float(
        surface_row["ci_high"], label=f"{candidate_id} surface single ci_high"
    )
    surface_distance = _plain_int(
        surface_row["distance"], label=f"{candidate_id} surface distance"
    )
    physical_per_patch = _plain_int(
        surface_row["physical_qubits"],
        label=f"{candidate_id} surface physical_qubits",
    )
    copied_total = k * physical_per_patch

    row.update(
        {
            "status": "accepted",
            "surface_distance": surface_distance,
            "surface_physical_per_patch": physical_per_patch,
            "surface_copied_total_physical": copied_total,
            "unused_physical_budget": n - copied_total,
            "surface_single_ler": single_ler,
            "surface_single_ci_low": single_ci_low,
            "surface_single_ci_high": single_ci_high,
            "surface_block_ler": block_probability(single_ler, k),
            "surface_block_ci_low": block_probability(single_ci_low, k),
            "surface_block_ci_high": block_probability(single_ci_high, k),
            "reason": None,
        }
    )
    return row


def _select_surface_row(rows: list[dict[str, Any]], *, n: int, k: int) -> dict[str, Any] | None:
    fitting_rows = [
        row
        for row in rows
        if type(row.get("distance")) is int
        and row["distance"] % 2 == 1
        and k * row["distance"] * row["distance"] <= n
    ]
    if not fitting_rows:
        return None
    fitting_rows.sort(key=lambda row: int(row["distance"]), reverse=True)
    return fitting_rows[0]


def _find_loaded_run(root: Path, run_root: Path):
    try:
        workspace = load_search_workspace(root)
    except SearchIntegrityError as exc:
        raise SearchIntegrityError(
            f"invalid search workspace for surface-copy comparison: {exc}"
        ) from exc
    except ValidationError as exc:
        raise SearchIntegrityError(
            f"invalid search workspace for surface-copy comparison: {exc.message}"
        ) from exc
    for loaded_run in workspace.runs.values():
        if loaded_run.root.resolve() == run_root.resolve():
            return loaded_run
    raise SearchIntegrityError(f"unknown search run for surface-copy comparison: {run_root}")


def block_probability(single_probability: float, k: int) -> float:
    probability = _finite_float(single_probability, label="single_probability")
    if probability < 0.0 or probability > 1.0:
        raise SearchIntegrityError("single_probability must be in [0, 1]")
    if type(k) is not int or k <= 0:
        raise SearchIntegrityError("k must be a positive integer")
    if k == 1:
        return probability
    return 1.0 - (1.0 - probability) ** k


def compare_surface_copy(root: Path, run_root: Path, baseline_path: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    run_root = _normalize_under_root(root, Path(run_root)).resolve()
    baseline_path = _normalize_under_root(root, Path(baseline_path)).resolve()

    loaded_run = _find_loaded_run(root, run_root)
    baseline = load_surface_single_logical_baseline(baseline_path)
    baseline_rows = baseline["rows"]

    rows: list[dict[str, Any]] = []
    candidate_ids = list(loaded_run.candidates)
    for candidate_id in candidate_ids:
        candidate_root = run_root / "candidates" / candidate_id
        manifests = [
            manifest
            for manifest in loaded_run.candidates[candidate_id].manifests.values()
            if manifest.get("status") == "completed"
        ]
        if not manifests:
            continue
        structure = _load_json(candidate_root / "structure.json")
        n = _plain_int(structure.get("n"), label=f"{candidate_id} structure n")
        k = _plain_int(structure.get("k"), label=f"{candidate_id} structure k")

        for manifest in manifests:
            metadata = manifest.get("run_metadata")
            aggregation = metadata.get("logical_failure_aggregation") if isinstance(metadata, dict) else None
            points = manifest.get("points")
            if not isinstance(points, list):
                raise SearchIntegrityError(
                    f"completed manifest points must be a list: {candidate_root}"
                )
            for point in points:
                if not isinstance(point, dict):
                    raise SearchIntegrityError(
                        f"completed manifest point must be an object: {candidate_root}"
                    )
                if k <= 0:
                    rows.append(
                        _rejected_row(
                            candidate_id=candidate_id,
                            n=n,
                            k=k,
                            aggregation=aggregation,
                            point=point,
                            reason="candidate k must be positive",
                        )
                    )
                    continue
                if aggregation != "any_logical":
                    rows.append(
                        _rejected_row(
                            candidate_id=candidate_id,
                            n=n,
                            k=k,
                            aggregation=aggregation,
                            point=point,
                            reason=(
                                "logical_failure_aggregation must be exactly "
                                "any_logical"
                            ),
                        )
                    )
                    continue
                point_p = _finite_float(point["p"], label=f"{candidate_id} point p")
                if not math.isclose(point_p, TARGET_P, rel_tol=0.0, abs_tol=1e-15):
                    rows.append(
                        _rejected_row(
                            candidate_id=candidate_id,
                            n=n,
                            k=k,
                            aggregation=aggregation,
                            point=point,
                            reason="only p=0.001 points are comparable",
                        )
                    )
                    continue
                surface_row = _select_surface_row(baseline_rows, n=n, k=k)
                if surface_row is None:
                    rows.append(
                        _rejected_row(
                            candidate_id=candidate_id,
                            n=n,
                            k=k,
                            aggregation=aggregation,
                            point=point,
                            reason=(
                                "no odd rotated-surface baseline satisfies "
                                "k*d*d <= n"
                            ),
                        )
                    )
                    continue
                rows.append(
                    _accepted_row(
                        candidate_id=candidate_id,
                        n=n,
                        k=k,
                        aggregation=aggregation,
                        point=point,
                        surface_row=surface_row,
                    )
                )

    accepted = sum(1 for row in rows if row["status"] == "accepted")
    rejected = len(rows) - accepted
    return {
        "schema_version": SURFACE_COPY_COMPARISON_SCHEMA_VERSION,
        "status": "ok",
        "root": str(root),
        "run_root": str(run_root),
        "baseline_path": str(baseline_path),
        "row_contract": {
            "status": "accepted rows compare Tanner logical failure to copied rotated-surface logical failure; rejected rows carry Tanner metrics plus a rejection reason",
            "support_fields": ROW_SUPPORT_FIELDS,
        },
        "rows": rows,
        "counts": {
            "rows": len(rows),
            "accepted": accepted,
            "rejected": rejected,
        },
    }


def _html_cell(value: Any) -> str:
    if value is None:
        return ""
    return escape(str(value), quote=True)


def _html_probability(value: Any) -> str:
    if value is None:
        return ""
    return f"{_finite_float(value, label='html value'):.6g}"


def _html_ci(low: Any, high: Any) -> str:
    if low is None or high is None:
        return ""
    return f"[{_html_probability(low)}, {_html_probability(high)}]"


def render_surface_copy_comparison_html(model: dict[str, Any]) -> str:
    payload = json.dumps(model, indent=2, sort_keys=True)
    row_lines: list[str] = []
    for row in model.get("rows", []):
        reason = row.get("reason")
        status_reason = row.get("status", "")
        if reason:
            status_reason = f"{status_reason}: {reason}"
        row_lines.append(
            "<tr>"
            f"<td>{_html_cell(row.get('candidate_id'))}</td>"
            f"<td>{_html_cell(row.get('n'))}</td>"
            f"<td>{_html_cell(row.get('k'))}</td>"
            f"<td>{_html_probability(row.get('tanner_ler'))} {_html_ci(row.get('tanner_ci_low'), row.get('tanner_ci_high'))}</td>"
            f"<td>{_html_cell(row.get('tanner_logical_failure_aggregation'))}</td>"
            f"<td>{_html_cell(row.get('surface_distance'))}</td>"
            f"<td>{_html_cell(row.get('surface_physical_per_patch'))}</td>"
            f"<td>{_html_cell(row.get('surface_copied_total_physical'))}</td>"
            f"<td>{_html_cell(row.get('unused_physical_budget'))}</td>"
            f"<td>{_html_probability(row.get('surface_single_ler'))}</td>"
            f"<td>{_html_probability(row.get('surface_block_ler'))}</td>"
            f"<td>{_html_ci(row.get('surface_block_ci_low'), row.get('surface_block_ci_high'))}</td>"
            f"<td>{_html_cell(status_reason)}</td>"
            "</tr>"
        )
    body_rows = "".join(row_lines)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoQEC Surface Copy Comparison</title>
  <style>
    body {{ color: #1f2933; font-family: system-ui, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0 2rem; width: 100%; }}
    th, td {{ border: 1px solid #c7d0d9; padding: 0.4rem 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f6; }}
    code, pre {{ background: #f6f8fa; }}
    pre {{ padding: 1rem; overflow: auto; }}
  </style>
</head>
<body>
  <h1>AutoQEC Surface Copy Comparison</h1>
  <p>Status: <strong>{_html_cell(model.get('status'))}</strong></p>
  <p>Rows: <strong>{_html_cell(model.get('counts', {}).get('rows'))}</strong>;
     accepted: <strong>{_html_cell(model.get('counts', {}).get('accepted'))}</strong>;
     rejected: <strong>{_html_cell(model.get('counts', {}).get('rejected'))}</strong></p>
  <table>
    <thead>
      <tr>
        <th>Candidate ID</th>
        <th>n</th>
        <th>k</th>
        <th>Tanner LER+CI</th>
        <th>Aggregation</th>
        <th>Surface Distance</th>
        <th>d^2</th>
        <th>Copied Physical</th>
        <th>Unused Budget</th>
        <th>Single-Patch Surface LER</th>
        <th>Copied Block Surface LER</th>
        <th>Copied Block CI</th>
        <th>Status/Reason</th>
      </tr>
    </thead>
    <tbody>{body_rows}</tbody>
  </table>
  <h2>Comparison JSON</h2>
  <script type="application/json" id="surface-copy-comparison-data">{escape(payload)}</script>
  <pre>{escape(payload)}</pre>
</body>
</html>
"""


def write_surface_copy_comparison(
    model: dict[str, Any], out_path: Path
) -> dict[str, Path]:
    out_path = Path(out_path)
    json_path = out_path.with_suffix(".json")
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_surface_copy_comparison_html(model))
        json_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        raise SearchIntegrityError(
            f"could not write surface copy comparison to {out_path}: {exc}"
        ) from exc
    return {"html": out_path, "json": json_path}
