from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pytest

from autoqec_search.cli import main
from autoqec_search.load import SearchIntegrityError
from autoqec_search.strategy_compare import (
    compare_strategies,
    render_strategy_comparison_html,
    render_strategy_comparison_svg,
    write_strategy_comparison,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _candidate(candidate_id: str, distance: int) -> dict:
    return {
        "candidate_id": candidate_id,
        "code_family": "rotated-surface-code",
        "parameters": {"distance": distance, "layout": "rotated"},
        "provenance": {"kind": "seed", "label": candidate_id},
    }


def _search_space() -> dict:
    return {
        "campaign_id": "rotated-surface-strategy-fixture",
        "mode": "explicit_list",
        "candidate_specs": [
            _candidate("d3-a", 3),
            _candidate("d3-b", 3),
            _candidate("d5", 5),
            _candidate("d7", 7),
        ],
    }


def _metrics() -> dict:
    return {
        "d3-a": {"distance": 3, "representative_ler": 0.03},
        "d3-b": {"distance": 3, "representative_ler": 0.04},
        "d5": {"distance": 5, "representative_ler": 0.02},
        "d7": {"distance": 7, "representative_ler": 0.01},
    }


def _run_compare_cli(root: Path, output_path: Path, metrics_path: str | Path) -> int:
    return main(
        [
            "compare-strategies",
            "--root",
            str(root),
            "--campaign",
            "rotated-surface-strategy-fixture",
            "--strategies",
            "grid",
            "adaptive",
            "--budget-candidates",
            "3",
            "--metrics",
            str(metrics_path),
            "--out",
            str(output_path),
        ]
    )


def test_compare_strategies_asserts_adaptive_reaches_grid_quality_faster() -> None:
    model = compare_strategies(
        campaign_id="rotated-surface-strategy-fixture",
        search_space=_search_space(),
        metrics=_metrics(),
        strategy_names=["grid", "adaptive"],
        budget_candidates=3,
        seed=7,
    )

    assert model["assertion"]["passed"] is True
    assert (
        model["assertion"]["adaptive_evaluations"]
        < model["assertion"]["grid_evaluations"]
    )
    assert model["series"]["adaptive"]["proposal_order"] == ["d3-a", "d5", "d7"]


def test_compare_strategies_rejects_missing_metrics() -> None:
    metrics = _metrics()
    del metrics["d5"]

    with pytest.raises(SearchIntegrityError, match="missing strategy metric"):
        compare_strategies(
            campaign_id="rotated-surface-strategy-fixture",
            search_space=_search_space(),
            metrics=metrics,
            strategy_names=["grid", "adaptive"],
            budget_candidates=3,
            seed=7,
        )


@pytest.mark.parametrize("distance", [0, 3.5, True])
def test_compare_strategies_rejects_invalid_metric_distance(distance: object) -> None:
    metrics = _metrics()
    metrics["d3-a"] = {"distance": distance, "representative_ler": 0.03}

    with pytest.raises(SearchIntegrityError, match="invalid strategy metric distance"):
        compare_strategies(
            campaign_id="rotated-surface-strategy-fixture",
            search_space=_search_space(),
            metrics=metrics,
            strategy_names=["grid", "adaptive"],
            budget_candidates=3,
            seed=7,
        )


@pytest.mark.parametrize("representative_ler", [True, math.nan, math.inf])
def test_compare_strategies_rejects_invalid_representative_ler(
    representative_ler: object,
) -> None:
    metrics = _metrics()
    metrics["d3-a"] = {"distance": 3, "representative_ler": representative_ler}

    with pytest.raises(
        SearchIntegrityError,
        match="invalid strategy metric representative_ler",
    ):
        compare_strategies(
            campaign_id="rotated-surface-strategy-fixture",
            search_space=_search_space(),
            metrics=metrics,
            strategy_names=["grid", "adaptive"],
            budget_candidates=3,
            seed=7,
        )


def test_render_strategy_comparison_outputs_offline_artifacts() -> None:
    model = compare_strategies(
        campaign_id="rotated-surface-strategy-fixture",
        search_space=_search_space(),
        metrics=_metrics(),
        strategy_names=["grid", "adaptive"],
        budget_candidates=3,
        seed=7,
    )

    svg = render_strategy_comparison_svg(model)
    html = render_strategy_comparison_html(model, svg)

    assert "<svg" in svg
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert "Strategy Comparison" in html
    assert "http://" not in html
    assert "https://" not in html


def test_write_strategy_comparison_writes_sibling_artifacts(tmp_path: Path) -> None:
    model = compare_strategies(
        campaign_id="rotated-surface-strategy-fixture",
        search_space=_search_space(),
        metrics=_metrics(),
        strategy_names=["grid", "adaptive"],
        budget_candidates=3,
        seed=7,
    )

    written = write_strategy_comparison(model, tmp_path / "strategies.html")

    assert written["json"].name == "strategies.json"
    assert written["svg"].name == "strategies.svg"
    assert written["html"].name == "strategies.html"
    assert written["json"].parent == tmp_path
    assert written["svg"].parent == tmp_path
    assert written["html"].parent == tmp_path
    assert json.loads(written["json"].read_text())["assertion"]["passed"] is True


def test_compare_strategies_cli_writes_artifacts(tmp_path: Path) -> None:
    output_path = tmp_path / "strategies.html"

    return_code = _run_compare_cli(
        REPO_ROOT,
        output_path,
        "benchmarks/fixtures/strategy-comparison/rotated-surface.json",
    )

    assert return_code == 0
    assert output_path.exists()
    assert output_path.with_suffix(".json").exists()
    assert output_path.with_suffix(".svg").exists()


def test_compare_strategies_cli_ignores_unrelated_broken_run(
    tmp_path: Path,
) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
        / "env.json"
    ).unlink()
    output_path = tmp_path / "strategies.html"

    return_code = _run_compare_cli(
        work_root,
        output_path,
        "benchmarks/fixtures/strategy-comparison/rotated-surface.json",
    )

    assert return_code == 0
    assert output_path.exists()
    assert output_path.with_suffix(".json").exists()
    assert output_path.with_suffix(".svg").exists()


def test_compare_strategies_cli_writes_artifacts_before_assertion_failure(
    tmp_path: Path,
) -> None:
    metrics_path = tmp_path / "flat-metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "strategy-d3-a": {"distance": 3, "representative_ler": 0.03},
                "strategy-d3-b": {"distance": 3, "representative_ler": 0.03},
                "strategy-d5": {"distance": 3, "representative_ler": 0.03},
                "strategy-d7": {"distance": 3, "representative_ler": 0.03},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    output_path = tmp_path / "strategies.html"

    return_code = _run_compare_cli(REPO_ROOT, output_path, metrics_path)

    assert return_code == 1
    assert output_path.exists()
    assert output_path.with_suffix(".json").exists()
    assert output_path.with_suffix(".svg").exists()
