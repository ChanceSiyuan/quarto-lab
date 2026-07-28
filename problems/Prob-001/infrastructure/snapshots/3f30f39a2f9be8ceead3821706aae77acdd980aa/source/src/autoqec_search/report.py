from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from html import escape as html_escape
from math import isfinite, log10
from pathlib import Path
from typing import Any

from autoqec_search.decoder_parameters import (
    DecoderParameterError,
    normalize_decoder_parameters,
)
from autoqec_search.distance_methods import LoadedDistancePayload, load_distance_payload
from autoqec_search.load import LoadedRun, SearchIntegrityError, load_search_workspace
from autoqec_search.screening import load_screening_json


REPORT_SCHEMA_VERSION = 1


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing report artifact: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"report artifact must be an object: {path}")
    return payload


def _optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return _load_json(path)


def _read_csv_rows(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing report CSV artifact: {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            return []
        return [dict(row) for row in reader]


def _loaded_run_for_path(root: Path, run_root: Path) -> LoadedRun:
    for workspace_root in (root, *_candidate_workspace_roots(run_root)):
        workspace = load_search_workspace(workspace_root)
        for loaded_run in workspace.runs.values():
            if loaded_run.root.resolve() == run_root:
                return loaded_run
    raise SearchIntegrityError(f"run is not part of search workspace: {run_root}")


def _candidate_workspace_roots(run_root: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    for candidate in run_root.parents:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (
            (candidate / "campaigns").is_dir()
            and (candidate / "benchmarks").is_dir()
            and (candidate / "results" / "search").is_dir()
        ):
            yield candidate


def _frontier_items(
    frontier: dict[str, Any], *, path: Path, campaign_id: str, run_id: str
) -> list[Any]:
    if frontier.get("campaign_id") != campaign_id or frontier.get("run_id") != run_id:
        raise SearchIntegrityError(f"frontier identity mismatch for {path}")
    items = frontier.get("items")
    if not isinstance(items, list):
        raise SearchIntegrityError(f"frontier items must be a list: {path}")
    return items


def _finite_float(value: Any, *, label: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise SearchIntegrityError(f"{label} must be a finite number")
    numeric = float(value)
    if not isfinite(numeric):
        raise SearchIntegrityError(f"{label} must be a finite number")
    return numeric


def _optional_distance(path: Path) -> LoadedDistancePayload:
    return load_distance_payload(path)


def _decoder_parameters(value: Any) -> dict[str, Any]:
    try:
        return normalize_decoder_parameters(value)
    except DecoderParameterError as exc:
        raise SearchIntegrityError(str(exc)) from exc


def _manifest_status_counts(manifests: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "completed": sum(
            1 for manifest in manifests if manifest.get("status") == "completed"
        ),
        "crash": sum(1 for manifest in manifests if manifest.get("status") == "crash"),
        "placeholder": sum(
            1 for manifest in manifests if manifest.get("status") == "placeholder"
        ),
    }


def _point_payload(
    manifest: dict[str, Any], point: dict[str, Any], distance: int | None
) -> dict[str, Any]:
    return {
        "candidate_id": manifest["candidate_id"],
        "distance": distance,
        "task_id": manifest["task_id"],
        "decoder_id": manifest["decoder_id"],
        "decoder_parameters": _decoder_parameters(
            manifest.get("decoder_parameters", {})
        ),
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

    loaded_run = _loaded_run_for_path(root, run_root)
    run_spec = loaded_run.payload
    campaign_id = str(run_spec["campaign_id"])
    run_id = str(run_spec["run_id"])

    env = _load_json(run_root / "env.json")
    frontier_path = run_root / "frontier.json"
    frontier = _load_json(frontier_path)
    frontier_items = _frontier_items(
        frontier, path=frontier_path, campaign_id=campaign_id, run_id=run_id
    )
    leaderboard_rows = _read_csv_rows(run_root / "leaderboard.csv")
    verdict_rows = (
        _read_csv_rows(run_root / "experiment-log.tsv", delimiter="\t")
        if (run_root / "experiment-log.tsv").is_file()
        else []
    )

    candidates: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    for candidate_id, loaded_candidate in sorted(loaded_run.candidates.items()):
        candidate_root = run_root / "candidates" / candidate_id
        distance_payload = _optional_distance(candidate_root / "distance.json")
        distance = distance_payload.distance
        structure = _load_json(candidate_root / "structure.json")
        candidates.append(
            {
                "candidate_id": candidate_id,
                "distance": distance,
                "upper_bound": distance_payload.upper_bound,
                "distance_method": distance_payload.method,
                "distance_bound_type": distance_payload.bound_type,
                "status": loaded_candidate.payload.get("status"),
                "screening": load_screening_json(candidate_root / "screening.json"),
                "n": structure.get("n"),
                "k": structure.get("k"),
                "css_commute": structure.get("css_commute"),
                "parameters": loaded_candidate.payload.get("parameters"),
                "provenance": loaded_candidate.payload.get("provenance"),
            }
        )
        for (task_id, decoder_id), manifest in sorted(loaded_candidate.manifests.items()):
            manifest_summary = {
                "candidate_id": candidate_id,
                "task_id": task_id,
                "decoder_id": decoder_id,
                "status": manifest.get("status"),
            }
            if manifest.get("status") == "completed":
                manifest_summary["decoder_parameters"] = _decoder_parameters(
                    manifest.get("decoder_parameters", {})
                )
            manifests.append(manifest_summary)
            if manifest.get("status") != "completed":
                continue
            raw_points = manifest.get("points", [])
            for raw_point in raw_points:
                if not isinstance(raw_point, dict):
                    raise SearchIntegrityError(
                        f"manifest point must be an object: {candidate_id}"
                    )
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
    counts["frontier"] = len(frontier_items)
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
            "wall_clock_seconds": env.get(
                "wall_clock_seconds", run_spec.get("wall_clock_seconds")
            ),
        },
        "counts": counts,
        "candidates": candidates,
        "manifests": manifests,
        "points": points,
        "leaderboard": leaderboard_rows,
        "frontier": frontier_items,
        "verdicts": verdict_rows,
        "reference_check": _optional_json(run_root / "reference_check.json"),
    }


def _display_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _html_text(value: Any) -> str:
    return html_escape(_display_text(value), quote=True)


def _json_for_script(payload: dict[str, Any]) -> str:
    return (
        json.dumps(payload, indent=2, sort_keys=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    numeric = float(value)
    return numeric if isfinite(numeric) else None


def estimate_threshold(model: dict[str, Any]) -> dict[str, Any]:
    series: dict[tuple[str, str, int], dict[float, float]] = {}
    points = model.get("points", [])
    if not isinstance(points, list):
        points = []

    for point in points:
        if not isinstance(point, dict):
            continue
        distance = point.get("distance")
        p = _numeric(point.get("p"))
        ler = _numeric(point.get("ler"))
        if type(distance) is not int or p is None or ler is None:
            continue
        if p <= 0 or ler <= 0:
            continue
        key = (
            str(point.get("task_id", "")),
            str(point.get("decoder_id", "")),
            distance,
        )
        per_p = series.setdefault(key, {})
        previous = per_p.get(p)
        per_p[p] = ler if previous is None else min(previous, ler)

    grouped: dict[tuple[str, str], dict[int, dict[float, float]]] = {}
    for (task_id, decoder_id, distance), per_p in series.items():
        grouped.setdefault((task_id, decoder_id), {})[distance] = per_p

    no_crossing: dict[str, Any] | None = None
    for (task_id, decoder_id), by_distance in sorted(grouped.items()):
        distances = sorted(by_distance)
        for low_index, low_distance in enumerate(distances):
            for high_distance in distances[low_index + 1 :]:
                low_points = by_distance[low_distance]
                high_points = by_distance[high_distance]
                shared_p = sorted(set(low_points) & set(high_points))
                if len(shared_p) < 2:
                    continue
                no_crossing = {
                    "status": "not_enough_data",
                    "task_id": task_id,
                    "decoder_id": decoder_id,
                    "distance_low": low_distance,
                    "distance_high": high_distance,
                    "p_min": shared_p[0],
                    "p_max": shared_p[-1],
                    "method": "no crossing in sampled p range",
                }

                previous_p = shared_p[0]
                previous_diff = high_points[previous_p] - low_points[previous_p]
                if previous_diff == 0:
                    return {
                        "status": "estimated",
                        "task_id": task_id,
                        "decoder_id": decoder_id,
                        "p_estimate": previous_p,
                        "distance_low": low_distance,
                        "distance_high": high_distance,
                        "bracket_p_low": previous_p,
                        "bracket_p_high": previous_p,
                        "method": "coarse crossing at shared p value",
                    }

                for current_p in shared_p[1:]:
                    current_diff = high_points[current_p] - low_points[current_p]
                    if current_diff == 0:
                        return {
                            "status": "estimated",
                            "task_id": task_id,
                            "decoder_id": decoder_id,
                            "p_estimate": current_p,
                            "distance_low": low_distance,
                            "distance_high": high_distance,
                            "bracket_p_low": current_p,
                            "bracket_p_high": current_p,
                            "method": "coarse crossing at shared p value",
                        }
                    if previous_diff * current_diff < 0:
                        fraction = -previous_diff / (current_diff - previous_diff)
                        p_estimate = previous_p + (current_p - previous_p) * fraction
                        return {
                            "status": "estimated",
                            "task_id": task_id,
                            "decoder_id": decoder_id,
                            "p_estimate": p_estimate,
                            "distance_low": low_distance,
                            "distance_high": high_distance,
                            "bracket_p_low": previous_p,
                            "bracket_p_high": current_p,
                            "method": (
                                "linear interpolation of coarse crossing "
                                "between shared p values"
                            ),
                        }
                    previous_p = current_p
                    previous_diff = current_diff

    if no_crossing is not None:
        return no_crossing

    return {
        "status": "not_enough_data",
        "method": "not enough shared positive p/LER values across distance pairs",
        "point_count": len(points),
    }


def _log_bounds(values: Iterable[float], floor: float) -> tuple[float, float]:
    logs = [log10(max(value, floor)) for value in values if isfinite(value)]
    if not logs:
        logs = [log10(floor)]
    low = min(logs)
    high = max(logs)
    if low == high:
        return low - 0.5, high + 0.5
    padding = (high - low) * 0.08
    return low - padding, high + padding


def _axis_ticks(low: float, high: float) -> list[float]:
    if low == high:
        return [10**low]
    return [10 ** (low + (high - low) * index / 4) for index in range(5)]


def _svg_number(value: float) -> str:
    return f"{value:.6g}"


def _series_label(key: tuple[str, str, str, int]) -> str:
    task_id, decoder_id, candidate_id, distance = key
    return f"{task_id} / {decoder_id} / {candidate_id} / d={distance}"


def _legend_label(key: tuple[str, str, str, int]) -> str:
    _task_id, _decoder_id, candidate_id, distance = key
    return f"d={distance}: {candidate_id}"


def _shot_error_rate_to_round_error_rate(
    shot_error_rate: float, rounds: float
) -> float:
    if rounds <= 0 or rounds == 1:
        return shot_error_rate
    if shot_error_rate > 0.5:
        return 1.0 - _shot_error_rate_to_round_error_rate(
            1.0 - shot_error_rate, rounds
        )
    randomize_rate = 2.0 * shot_error_rate
    round_randomize_rate = 1.0 - (1.0 - randomize_rate) ** (1.0 / rounds)
    round_error_rate = round_randomize_rate / 2.0
    if round_error_rate == 0.0:
        return shot_error_rate / rounds
    return round_error_rate


def _plot_ler_rate(shot_error_rate: float, rounds: float) -> float:
    if 0.0 <= shot_error_rate <= 1.0:
        return _shot_error_rate_to_round_error_rate(shot_error_rate, rounds)
    return shot_error_rate


def render_ler_svg(model: dict[str, Any]) -> str:
    raw_points = model.get("points", [])
    if not isinstance(raw_points, list):
        return ""

    points = [point for point in raw_points if isinstance(point, dict)]
    if not points:
        return ""

    numeric_points: list[dict[str, Any]] = []
    positive_rates: list[float] = []
    for point in points:
        p = _numeric(point.get("p"))
        ler = _numeric(point.get("ler"))
        if p is None or ler is None or p <= 0:
            continue
        rounds = _numeric(point.get("rounds"))
        if rounds is None or rounds <= 0:
            rounds = 1.0
        ci_low = _numeric(point.get("ci_low"))
        ci_high = _numeric(point.get("ci_high"))
        ci_low = ler if ci_low is None else ci_low
        ci_high = ler if ci_high is None else ci_high
        plot_ler = _plot_ler_rate(ler, rounds)
        plot_ci_low = _plot_ler_rate(ci_low, rounds)
        plot_ci_high = _plot_ler_rate(ci_high, rounds)
        for rate in (plot_ler, plot_ci_low, plot_ci_high):
            if rate > 0:
                positive_rates.append(rate)
        numeric_points.append(
            {
                "candidate_id": str(point.get("candidate_id", "")),
                "task_id": str(point.get("task_id", "")),
                "decoder_id": str(point.get("decoder_id", "")),
                "distance": point.get("distance"),
                "p": p,
                "rounds": rounds,
                "ler": ler,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "plot_ler": plot_ler,
                "plot_ci_low": plot_ci_low,
                "plot_ci_high": plot_ci_high,
                "shots": point.get("shots"),
                "errors": point.get("errors"),
            }
        )

    if not numeric_points:
        return ""

    p_floor = 1e-12
    rate_floor = min(positive_rates) / 10 if positive_rates else 1e-12
    p_values = [point["p"] for point in numeric_points]
    rate_values = [
        max(value, rate_floor)
        for point in numeric_points
        for value in (point["plot_ler"], point["plot_ci_low"], point["plot_ci_high"])
    ]
    x_low, x_high = _log_bounds(p_values, p_floor)
    y_low, y_high = _log_bounds(rate_values, rate_floor)

    width = 900
    height = 460
    left = 78
    right = 250
    top = 36
    bottom = 66
    plot_right = width - right
    plot_bottom = height - bottom
    plot_width = plot_right - left
    plot_height = plot_bottom - top

    def x_pos(p: float) -> float:
        return left + (log10(max(p, p_floor)) - x_low) / (x_high - x_low) * plot_width

    def y_pos(rate: float) -> float:
        return top + (y_high - log10(max(rate, rate_floor))) / (
            y_high - y_low
        ) * plot_height

    by_series: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}
    for point in numeric_points:
        distance = point["distance"]
        if type(distance) is not int:
            continue
        key = (
            point["task_id"],
            point["decoder_id"],
            point["candidate_id"],
            distance,
        )
        by_series.setdefault(key, []).append(point)

    palette = [
        "#1f77b4",
        "#d62728",
        "#2ca02c",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#17becf",
    ]
    lines = [
        '<svg role="img" aria-labelledby="ler-title ler-desc" '
        f'viewBox="0 0 {width} {height}">',
        "<title id=\"ler-title\">Per-round logical error rate plot</title>",
        (
            '<desc id="ler-desc">Log-log plot of per-round logical error '
            "rate against physical error rate with confidence intervals.</desc>"
        ),
        '<rect width="900" height="460" fill="#ffffff"/>',
    ]

    for value in _axis_ticks(x_low, x_high):
        x = x_pos(value)
        label = _svg_number(value)
        lines.append(
            f'<line x1="{_svg_number(x)}" y1="{top}" x2="{_svg_number(x)}" '
            f'y2="{plot_bottom}" stroke="#e5e7eb" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{_svg_number(x)}" y="{plot_bottom + 22}" '
            'text-anchor="middle" font-size="11" fill="#374151">'
            f"{html_escape(label)}</text>"
        )
    for value in _axis_ticks(y_low, y_high):
        y = y_pos(value)
        label = _svg_number(value)
        lines.append(
            f'<line x1="{left}" y1="{_svg_number(y)}" x2="{plot_right}" '
            f'y2="{_svg_number(y)}" stroke="#e5e7eb" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{left - 10}" y="{_svg_number(y + 4)}" '
            'text-anchor="end" font-size="11" fill="#374151">'
            f"{html_escape(label)}</text>"
        )

    lines.extend(
        [
            f'<line x1="{left}" y1="{plot_bottom}" x2="{plot_right}" '
            f'y2="{plot_bottom}" stroke="#111827" stroke-width="1.5"/>',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{plot_bottom}" '
            'stroke="#111827" stroke-width="1.5"/>',
            f'<text x="{(left + plot_right) / 2:.6g}" y="{height - 20}" '
            'text-anchor="middle" font-size="13" fill="#111827">'
            "Physical error probability p</text>",
            f'<text x="18" y="{(top + plot_bottom) / 2:.6g}" '
            'text-anchor="middle" transform="rotate(-90 18 '
            f'{(top + plot_bottom) / 2:.6g})" font-size="13" fill="#111827">'
            "Per-round logical error rate</text>",
        ]
    )

    for series_index, (key, series_points) in enumerate(sorted(by_series.items())):
        color = palette[series_index % len(palette)]
        series_points = sorted(series_points, key=lambda point: point["p"])
        polyline_points = " ".join(
            f"{_svg_number(x_pos(point['p']))},{_svg_number(y_pos(point['plot_ler']))}"
            for point in series_points
        )
        if len(series_points) > 1:
            lines.append(
                f'<polyline points="{polyline_points}" fill="none" '
                f'stroke="{color}" stroke-width="2"/>'
            )
        for point in series_points:
            x = x_pos(point["p"])
            y = y_pos(point["plot_ler"])
            ci_low = min(point["plot_ci_low"], point["plot_ci_high"])
            ci_high = max(point["plot_ci_low"], point["plot_ci_high"])
            y_low_ci = y_pos(ci_low)
            y_high_ci = y_pos(ci_high)
            title = (
                f"{_series_label(key)}; p={point['p']}; "
                f"per_round_ler={point['plot_ler']}; "
                f"per_round_ci=[{ci_low}, {ci_high}]; "
                f"shot_ler={point['ler']}; "
                f"shot_ci=[{min(point['ci_low'], point['ci_high'])}, "
                f"{max(point['ci_low'], point['ci_high'])}]; "
                f"rounds={point['rounds']}; shots={point['shots']}; "
                f"errors={point['errors']}"
            )
            lines.extend(
                [
                    f'<line x1="{_svg_number(x)}" y1="{_svg_number(y_low_ci)}" '
                    f'x2="{_svg_number(x)}" y2="{_svg_number(y_high_ci)}" '
                    f'stroke="{color}" stroke-width="1.4"/>',
                    f'<line x1="{_svg_number(x - 5)}" y1="{_svg_number(y_low_ci)}" '
                    f'x2="{_svg_number(x + 5)}" y2="{_svg_number(y_low_ci)}" '
                    f'stroke="{color}" stroke-width="1.4"/>',
                    f'<line x1="{_svg_number(x - 5)}" '
                    f'y1="{_svg_number(y_high_ci)}" '
                    f'x2="{_svg_number(x + 5)}" '
                    f'y2="{_svg_number(y_high_ci)}" '
                    f'stroke="{color}" stroke-width="1.4"/>',
                    f'<circle cx="{_svg_number(x)}" cy="{_svg_number(y)}" r="4.5" '
                    f'fill="{color}" stroke="#ffffff" stroke-width="1.5">'
                    f"<title>{html_escape(title)}</title></circle>",
                ]
            )

        legend_y = top + 18 + series_index * 34
        label = _legend_label(key)
        lines.extend(
            [
                f'<line x1="{plot_right + 22}" y1="{legend_y - 4}" '
                f'x2="{plot_right + 48}" y2="{legend_y - 4}" '
                f'stroke="{color}" stroke-width="2"/>',
                f'<circle cx="{plot_right + 35}" cy="{legend_y - 4}" r="4" '
                f'fill="{color}"/>',
                f'<text x="{plot_right + 58}" y="{legend_y}" '
                'font-size="11" fill="#111827">'
                f"{html_escape(label)}</text>",
            ]
        )

    lines.append("</svg>")
    return "\n".join(lines)


def _row_records(records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        return []
    rows: list[dict[str, Any]] = []
    for record in records:
        if isinstance(record, Mapping):
            rows.append(dict(record))
        else:
            rows.append({"value": record})
    return rows


def _columns(
    rows: list[dict[str, Any]], preferred: Iterable[str] = ()
) -> list[str]:
    columns: list[str] = []
    for column in preferred:
        if any(column in row for row in rows):
            columns.append(column)
    for row in rows:
        for column in row:
            if column not in columns:
                columns.append(column)
    return columns


def _render_table(
    title: str,
    rows: list[dict[str, Any]],
    *,
    preferred_columns: Iterable[str] = (),
    empty_text: str = "No rows",
) -> str:
    if not rows:
        columns = list(preferred_columns) or ["value"]
        header = "".join(f"<th>{html_escape(column)}</th>" for column in columns)
        return (
            f"<section><h2>{html_escape(title)}</h2>"
            f'<p class="empty">{html_escape(empty_text)}</p>'
            f"<table><thead><tr>{header}</tr></thead><tbody></tbody></table>"
            "</section>"
        )
    columns = _columns(rows, preferred_columns)
    header = "".join(f"<th>{html_escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_html_text(row.get(column))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        f"<section><h2>{html_escape(title)}</h2><table>"
        f"<thead><tr>{header}</tr></thead><tbody>"
        f"{''.join(body_rows)}</tbody></table></section>"
    )


def _render_mapping_table(title: str, mapping: dict[str, Any]) -> str:
    rows = [{"field": key, "value": value} for key, value in mapping.items()]
    return _render_table(title, rows, preferred_columns=("field", "value"))


def _status_rows(model: dict[str, Any]) -> list[dict[str, Any]]:
    counts = model.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    return [
        {"metric": "candidate_count", "value": counts.get("candidates", 0)},
        {"metric": "completed_count", "value": counts.get("completed", 0)},
        {"metric": "crash_count", "value": counts.get("crash", 0)},
        {"metric": "placeholder_count", "value": counts.get("placeholder", 0)},
        {"metric": "frontier_count", "value": counts.get("frontier", 0)},
        {"metric": "point_count", "value": counts.get("points", 0)},
    ]


def _reference_check_rows(model: dict[str, Any]) -> list[dict[str, Any]]:
    reference_check = model.get("reference_check")
    if not isinstance(reference_check, dict):
        return [{"field": "status", "value": "not available"}]
    return [{"field": "status", "value": reference_check.get("status", "unknown")}]


def _render_generic_report_html(model: dict[str, Any]) -> str:
    threshold = estimate_threshold(model)
    svg = render_ler_svg(model)
    report_data = {**model, "threshold_estimate": threshold}
    json_payload = _json_for_script(report_data)
    provenance = model.get("provenance", {})
    if not isinstance(provenance, dict):
        provenance = {}

    ler_section = (
        f"<section><h2>LER</h2>{svg}</section>"
        if svg
        else '<section><h2>LER</h2><p class="empty">No results</p></section>'
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoQEC Search Report</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{
      margin: 0;
      padding: 32px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #111827;
      background: #f9fafb;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 32px;
      font-weight: 720;
    }}
    h2 {{
      margin: 28px 0 12px;
      font-size: 19px;
    }}
    .subtitle {{
      margin: 0 0 24px;
      color: #4b5563;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #ffffff;
      border: 1px solid #d1d5db;
    }}
    th, td {{
      padding: 8px 10px;
      border: 1px solid #e5e7eb;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }}
    th {{
      background: #eef2f7;
      font-weight: 650;
    }}
    svg {{
      width: 100%;
      height: auto;
      background: #ffffff;
      border: 1px solid #d1d5db;
    }}
    pre {{
      overflow: auto;
      padding: 12px;
      background: #111827;
      color: #f9fafb;
      font-size: 12px;
      line-height: 1.45;
    }}
    .empty {{
      padding: 12px;
      background: #ffffff;
      border: 1px solid #d1d5db;
      color: #4b5563;
    }}
  </style>
</head>
<body>
<main>
  <h1>AutoQEC Search Report</h1>
  <p class="subtitle">Self-contained report for campaign {_html_text(provenance.get("campaign_id"))} run {_html_text(provenance.get("run_id"))}.</p>
  {_render_mapping_table("Provenance", provenance)}
  {_render_table("Status", _status_rows(model), preferred_columns=("metric", "value"))}
  {_render_table("Reference check", _reference_check_rows(model), preferred_columns=("field", "value"))}
  {ler_section}
  {_render_mapping_table("Threshold", threshold)}
  {_render_table("Frontier", _row_records(model.get("frontier")), empty_text="No frontier entries")}
  {_render_table("Leaderboard", _row_records(model.get("leaderboard")), empty_text="No leaderboard rows")}
  {_render_table(
        "Results",
        _row_records(model.get("points")),
        preferred_columns=(
            "candidate_id",
            "distance",
            "task_id",
            "decoder_id",
            "p",
            "shots",
            "errors",
            "ler",
            "ci_low",
            "ci_high",
        ),
        empty_text="No results",
    )}
  <section>
    <h2>Report Data</h2>
    <script type="application/json" id="autoqec-report-data">{json_payload}</script>
    <pre>{html_escape(json_payload)}</pre>
  </section>
</main>
</body>
</html>
"""
    return html


def _render_report_bundle(
    root: Path,
    run_root: Path,
    *,
    report_filename: str = "report.html",
) -> tuple[str, tuple[str, str] | None]:
    model = build_report_model(root, run_root)
    provenance = model.get("provenance")
    campaign_id = provenance.get("campaign_id") if isinstance(provenance, dict) else None
    if campaign_id != "quantum-tanner-autoresearch":
        return _render_generic_report_html(model), None

    from autoqec_search.quantum_tanner_report import (
        DEFINITIONS_FILENAME,
        build_quantum_tanner_view_model,
        render_quantum_tanner_definitions_html,
        render_quantum_tanner_report_html,
    )

    threshold = estimate_threshold(model)
    view_model = build_quantum_tanner_view_model(root, model)
    report_data = {
        **model,
        "quantum_tanner": view_model,
        "threshold_estimate": threshold,
    }
    report_json = _json_for_script(report_data)
    report_html = render_quantum_tanner_report_html(
        view_model,
        ler_svg=render_ler_svg(model),
        report_json=report_json,
    )
    definitions_html = render_quantum_tanner_definitions_html(
        view_model,
        report_filename=report_filename,
    )
    return report_html, (DEFINITIONS_FILENAME, definitions_html)


def render_report_html(root: Path, run_root: Path) -> str:
    html, _companion = _render_report_bundle(root, run_root)
    return html


def write_report_html(
    root: Path, run_root: Path, output_path: Path | None = None
) -> Path:
    path = run_root / "report.html" if output_path is None else output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    html, companion = _render_report_bundle(
        root,
        run_root,
        report_filename=path.name,
    )
    path.write_text(html, encoding="utf-8")
    if companion is not None:
        companion_filename, companion_html = companion
        (path.parent / companion_filename).write_text(companion_html, encoding="utf-8")
    return path
