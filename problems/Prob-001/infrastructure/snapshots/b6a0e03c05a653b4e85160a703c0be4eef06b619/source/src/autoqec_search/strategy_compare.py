from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.run_render import FrontierItem
from autoqec_search.strategies import StrategyState, frontier_quality, get_strategy


def compare_strategies(
    *,
    campaign_id: str,
    search_space: dict[str, Any],
    metrics: dict[str, Any],
    strategy_names: list[str],
    budget_candidates: int,
    seed: int,
) -> dict[str, Any]:
    if budget_candidates < 1:
        raise SearchIntegrityError("budget_candidates must be positive")
    if "grid" not in strategy_names or "adaptive" not in strategy_names:
        raise SearchIntegrityError("strategy comparison requires grid and adaptive")

    candidate_specs = search_space.get("candidate_specs")
    if not isinstance(candidate_specs, list) or not candidate_specs:
        raise SearchIntegrityError("strategy comparison requires candidate_specs")

    series = {
        strategy_name: _simulate_strategy(
            strategy_name=strategy_name,
            candidate_specs=candidate_specs,
            metrics=metrics,
            budget_candidates=budget_candidates,
            seed=seed,
        )
        for strategy_name in strategy_names
    }

    grid_final = series["grid"]["final_quality"]
    target_quality = (
        int(grid_final["max_distance"]),
        float(grid_final["negative_ler"]),
    )
    grid_evaluations = _evaluations_to_reach(series["grid"], target_quality)
    adaptive_evaluations = _evaluations_to_reach(series["adaptive"], target_quality)
    passed = (
        grid_evaluations is not None
        and adaptive_evaluations is not None
        and adaptive_evaluations < grid_evaluations
    )

    return {
        "campaign_id": campaign_id,
        "strategy_names": list(strategy_names),
        "budget_candidates": budget_candidates,
        "seed": seed,
        "series": series,
        "assertion": {
            "passed": passed,
            "target_quality": {
                "max_distance": target_quality[0],
                "negative_ler": target_quality[1],
            },
            "grid_evaluations": grid_evaluations,
            "adaptive_evaluations": adaptive_evaluations,
        },
    }


def render_strategy_comparison_svg(model: dict[str, Any]) -> str:
    width = 720
    height = 360
    left = 56
    bottom = 316
    plot_width = 620
    plot_height = 250
    max_evaluations = max(
        [1]
        + [
            int(point["evaluations"])
            for series in model["series"].values()
            for point in series["quality_sequence"]
        ]
    )
    max_distance = max(
        [1]
        + [
            int(point["max_distance"])
            for series in model["series"].values()
            for point in series["quality_sequence"]
        ]
    )
    colors = {"adaptive": "#0f7b4f", "grid": "#3454d1", "random": "#9a5b00"}
    series_svg = []
    for strategy_name, series in model["series"].items():
        points = []
        for point in series["quality_sequence"]:
            x = left + (int(point["evaluations"]) / max_evaluations) * plot_width
            y = bottom - (int(point["max_distance"]) / max_distance) * plot_height
            points.append(f"{x:.1f},{y:.1f}")
        if not points:
            continue
        color = colors.get(strategy_name, "#333333")
        series_svg.append(
            "<polyline "
            f"fill='none' stroke='{color}' stroke-width='3' "
            f"points='{' '.join(points)}'/>"
        )
        label_x, label_y = (float(value) for value in points[-1].split(",", 1))
        series_svg.append(
            "<text "
            f"x='{label_x + 8:.1f}' y='{label_y + 4:.1f}' "
            "font-family='system-ui' font-size='13' "
            f"fill='{color}'>{escape(strategy_name)}</text>"
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="white"/>
  <text x="24" y="32" font-family="system-ui" font-size="20" font-weight="700">Strategy Comparison</text>
  <line x1="{left}" y1="66" x2="{left}" y2="{bottom}" stroke="#333"/>
  <line x1="{left}" y1="{bottom}" x2="{left + plot_width}" y2="{bottom}" stroke="#333"/>
  <text x="18" y="180" font-family="system-ui" font-size="13" transform="rotate(-90 18 180)">best distance</text>
  <text x="300" y="348" font-family="system-ui" font-size="13">evaluations</text>
  {''.join(series_svg)}
</svg>
"""


def render_strategy_comparison_html(model: dict[str, Any], svg: str) -> str:
    inline_svg = svg.replace(' xmlns="http://www.w3.org/2000/svg"', "")
    rows = []
    for strategy_name, series in model["series"].items():
        final_quality = series["final_quality"]
        rows.append(
            "<tr>"
            f"<td>{escape(strategy_name)}</td>"
            f"<td>{escape(', '.join(series['proposal_order']))}</td>"
            f"<td>{escape(str(final_quality['max_distance']))}</td>"
            f"<td>{escape(str(final_quality['negative_ler']))}</td>"
            "</tr>"
        )
    payload = json.dumps(model, indent=2, sort_keys=True).replace("<", "\\u003c")
    assertion_passed = str(model["assertion"]["passed"]).lower()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoQEC Strategy Comparison</title>
  <style>
    body {{ color: #1f2933; font-family: system-ui, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; max-width: 1100px; width: 100%; }}
    th, td {{ border: 1px solid #c7d0d9; padding: 0.4rem 0.55rem; text-align: left; }}
    th {{ background: #eef2f6; }}
    pre {{ background: #f6f8fa; padding: 1rem; overflow: auto; }}
  </style>
</head>
<body>
  <h1>Strategy Comparison</h1>
  {inline_svg}
  <p>Assertion passed: <strong>{escape(assertion_passed)}</strong></p>
  <table>
    <thead>
      <tr><th>Strategy</th><th>Order</th><th>Max distance</th><th>Negative LER</th></tr>
    </thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <h2>Model JSON</h2>
  <pre>{escape(payload)}</pre>
</body>
</html>
"""


def write_strategy_comparison(model: dict[str, Any], html_path: Path) -> dict[str, Path]:
    stem = html_path.with_suffix("")
    json_path = stem.with_suffix(".json")
    svg_path = stem.with_suffix(".svg")
    actual_html_path = stem.with_suffix(".html")

    svg = render_strategy_comparison_svg(model)
    html = render_strategy_comparison_html(model, svg)

    actual_html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    svg_path.write_text(svg)
    actual_html_path.write_text(html)
    return {"json": json_path, "svg": svg_path, "html": actual_html_path}


def _simulate_strategy(
    *,
    strategy_name: str,
    candidate_specs: list[dict[str, Any]],
    metrics: dict[str, Any],
    budget_candidates: int,
    seed: int,
) -> dict[str, Any]:
    frontier: list[FrontierItem] = []
    attempted_candidate_ids: set[str] = set()
    proposal_order: list[str] = []
    quality_sequence: list[dict[str, Any]] = []
    strategy = get_strategy(strategy_name)

    while len(proposal_order) < budget_candidates:
        state = StrategyState(
            candidate_specs=candidate_specs,
            frontier=frontier,
            attempted_candidate_ids=set(attempted_candidate_ids),
            deduped_candidate_ids=set(),
            seed=seed,
            max_candidates=budget_candidates,
            evaluations_completed=len(proposal_order),
        )
        proposals = strategy.propose(state)
        fresh_proposals = [
            proposal
            for proposal in proposals
            if proposal.candidate_id not in attempted_candidate_ids
        ]
        if not fresh_proposals:
            break

        proposal = fresh_proposals[0]
        candidate_id = proposal.candidate_id
        distance, ler = _metric_for(metrics, candidate_id)
        attempted_candidate_ids.add(candidate_id)
        proposal_order.append(candidate_id)
        frontier = _update_synthetic_frontier(
            frontier,
            candidate_id=candidate_id,
            distance=distance,
            ler=ler,
        )
        max_distance, negative_ler = frontier_quality(frontier)
        quality_sequence.append(
            {
                "evaluations": len(proposal_order),
                "candidate_id": candidate_id,
                "max_distance": max_distance,
                "negative_ler": negative_ler,
            }
        )

    max_distance, negative_ler = frontier_quality(frontier)
    return {
        "proposal_order": proposal_order,
        "quality_sequence": quality_sequence,
        "final_quality": {
            "max_distance": max_distance,
            "negative_ler": negative_ler,
        },
    }


def _metric_for(metrics: dict[str, Any], candidate_id: str) -> tuple[int, float]:
    payload = metrics.get(candidate_id)
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"missing strategy metric for {candidate_id}")
    distance = payload.get("distance")
    ler = payload.get("representative_ler")
    if type(distance) is not int or distance <= 0:
        raise SearchIntegrityError(
            f"invalid strategy metric distance for {candidate_id}"
        )
    if isinstance(ler, bool) or not isinstance(ler, (int, float)):
        raise SearchIntegrityError(
            f"invalid strategy metric representative_ler for {candidate_id}"
        )
    ler_float = float(ler)
    if not 0 <= ler_float <= 1:
        raise SearchIntegrityError(
            f"invalid strategy metric representative_ler for {candidate_id}"
        )
    return distance, ler_float


def _update_synthetic_frontier(
    frontier: list[FrontierItem],
    *,
    candidate_id: str,
    distance: int,
    ler: float,
) -> list[FrontierItem]:
    by_distance = {item.distance: item for item in frontier}
    existing = by_distance.get(distance)
    if existing is None or ler < existing.ler:
        by_distance[distance] = FrontierItem(
            candidate_id=candidate_id,
            distance=distance,
            decoder_id="strategy-metric",
            p=0.0,
            ler=ler,
            manifest_path=f"strategy-metrics/{candidate_id}.json",
        )
    return sorted(
        by_distance.values(),
        key=lambda item: (item.distance, item.candidate_id),
    )


def _evaluations_to_reach(
    series: dict[str, Any],
    target_quality: tuple[int, float],
) -> int | None:
    for point in series["quality_sequence"]:
        quality = (int(point["max_distance"]), float(point["negative_ler"]))
        if quality >= target_quality:
            return int(point["evaluations"])
    return None


__all__ = [
    "compare_strategies",
    "render_strategy_comparison_html",
    "render_strategy_comparison_svg",
    "write_strategy_comparison",
]
