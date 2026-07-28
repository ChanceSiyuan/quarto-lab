from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError, load_search_workspace
from autoqec_search.report import (
    build_report_model,
    estimate_threshold,
    render_ler_svg,
    render_report_html,
    write_report_html,
)


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


def _write_tsv(path: Path, rows: list[list[object]]) -> None:
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerows(rows)
    path.write_text(output.getvalue())


def _make_completed_eval_run(work_root: Path) -> Path:
    run_root = _example_run_root(work_root)
    expected = _load_json(
        work_root / "benchmarks" / "fixtures" / "rotated-d3" / "expected.json"
    )
    run_spec_path = run_root / "run_spec.json"
    run_spec = _load_json(run_spec_path)
    run_spec["mode"] = "eval"
    _write_json(run_spec_path, run_spec)

    candidate_root = run_root / "candidates" / "rotated-surface-d3-example"
    candidate_path = candidate_root / "candidate.json"
    candidate = _load_json(candidate_path)
    candidate["status"] = "evaluated"
    _write_json(candidate_path, candidate)
    _write_json(candidate_root / "distance.json", {"distance": 3, "status": "computed"})
    _write_json(
        candidate_root / "structure.json",
        {"css_commute": True, "k": 1, "n": 9, "status": "computed"},
    )

    manifest = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "2026-06-09-example",
        "candidate_id": "rotated-surface-d3-example",
        "task_id": "rotated-memory-z-cdep-v1",
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
        / "rotated-memory-z-cdep-v1"
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
                "rotated-memory-z-cdep-v1",
                "rmatching-default-v1",
                expected["p"],
                expected["shots"],
                expected["errors"],
                expected["logical_error_rate"],
                expected["binomial_ci_95"]["lower"],
                expected["binomial_ci_95"]["upper"],
                "completed,verified",
            ],
        ],
    )
    _write_tsv(
        run_root / "experiment-log.tsv",
        [
            ["candidate", "ler", "status", "description"],
            [
                "rotated-surface-d3-example",
                "0.0125",
                "keep",
                "kept after\treport review",
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
            "task_ids": ["rotated-memory-z-cdep-v1"],
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
    expected = _load_json(
        work_root / "benchmarks" / "fixtures" / "rotated-d3" / "expected.json"
    )

    model = build_report_model(work_root, run_root)

    assert set(model) == {
        "schema_version",
        "provenance",
        "counts",
        "candidates",
        "manifests",
        "points",
        "leaderboard",
        "frontier",
        "verdicts",
        "reference_check",
    }
    assert model["provenance"]["campaign_id"] == "rotated-surface-baseline"
    assert model["provenance"]["run_id"] == "2026-06-09-example"
    assert model["counts"]["candidates"] == 1
    assert model["counts"]["completed"] == 1
    assert model["counts"]["placeholder"] == 2
    assert model["candidates"][0]["candidate_id"] == "rotated-surface-d3-example"
    assert model["candidates"][0]["distance"] == 3
    assert model["candidates"][0]["n"] == 9
    assert model["candidates"][0]["k"] == 1
    assert model["candidates"][0]["css_commute"] is True
    assert model["points"][0] == {
        "candidate_id": "rotated-surface-d3-example",
        "distance": 3,
        "task_id": "rotated-memory-z-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "decoder_parameters": {},
        "p": expected["p"],
        "rounds": expected["rounds"],
        "shots": expected["shots"],
        "errors": expected["errors"],
        "ler": expected["logical_error_rate"],
        "ci_low": expected["binomial_ci_95"]["lower"],
        "ci_high": expected["binomial_ci_95"]["upper"],
        "seconds": 0.022230764,
    }
    assert model["leaderboard"][0]["status"] == "completed,verified"
    assert model["verdicts"][0]["status"] == "keep"
    assert model["verdicts"][0]["description"] == "kept after\treport review"
    assert model["reference_check"] is None


def test_build_report_model_exposes_distance_method_and_bound_type(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    _write_json(
        run_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "distance.json",
        {
            "status": "completed",
            "distance": 3,
            "method": "copied-zoo-exact",
            "bound_type": "exact",
            "options": {
                "method": "copied-zoo-exact",
                "qec_code_bin": "qec-code",
            },
            "provenance": {
                "source": "zoo-instance",
                "source_instance_id": "rotated-surface-code-d3",
                "source_instance_path": (
                    "zoo/codes/rotated-surface-code/instances/"
                    "rotated-surface-code-d3"
                ),
            },
        },
    )

    model = build_report_model(work_root, run_root)
    candidate = model["candidates"][0]

    assert candidate["distance"] == 3
    assert candidate["distance_method"] == "copied-zoo-exact"
    assert candidate["distance_bound_type"] == "exact"


def test_build_report_model_rejects_randomized_payload_without_bound_type(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    _write_json(
        run_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "distance.json",
        {
            "status": "completed",
            "distance": 3,
            "upper_bound": 3,
            "method": "randomized-upper-bound",
        },
    )

    with pytest.raises(
        SearchIntegrityError,
        match="randomized-upper-bound.*bound_type upper",
    ):
        build_report_model(work_root, run_root)


def test_build_report_model_accepts_empty_run(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_empty_run(work_root)

    workspace = load_search_workspace(work_root)
    model = build_report_model(work_root, run_root)

    assert "rotated-surface-baseline/empty-run" in workspace.runs
    assert model["counts"]["candidates"] == 0
    assert model["counts"]["points"] == 0
    assert model["points"] == []
    assert model["frontier"] == []
    assert model["verdicts"] == []
    assert model["leaderboard"] == []


def test_report_model_includes_reference_check_status(tmp_path: Path) -> None:
    from autoqec_search.report import build_report_model

    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    _write_json(
        run_root / "reference_check.json",
        {
            "status": "pass",
            "candidate_id": "rotated-surface-d3-example",
            "task_id": "rotated-memory-z-cdep-v1",
            "decoder_id": "rmatching-default-v1",
            "points": [{"p": 0.01, "status": "pass"}],
        },
    )

    model = build_report_model(work_root, run_root)
    html = render_report_html(work_root, run_root)

    assert model["reference_check"]["status"] == "pass"
    assert model["reference_check"]["points"][0]["status"] == "pass"
    assert "Reference check" in html
    assert ">pass</td>" in html


def test_build_report_model_rejects_untracked_malformed_run_without_keyerror(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = tmp_path / "outside-run"
    run_root.mkdir()
    _write_json(run_root / "run_spec.json", {"mode": "eval"})

    with pytest.raises(SearchIntegrityError, match="run is not part of search workspace"):
        build_report_model(work_root, run_root)


def test_build_report_model_rejects_frontier_identity_mismatch(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    _write_json(
        run_root / "frontier.json",
        {
            "campaign_id": "other-campaign",
            "run_id": "2026-06-09-example",
            "items": [],
        },
    )

    with pytest.raises(SearchIntegrityError, match="frontier identity mismatch"):
        build_report_model(work_root, run_root)


def test_build_report_model_rejects_frontier_items_that_are_not_a_list(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    _write_json(
        run_root / "frontier.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "2026-06-09-example",
            "items": {},
        },
    )

    with pytest.raises(SearchIntegrityError, match="frontier items must be a list"):
        build_report_model(work_root, run_root)


def test_build_report_model_accepts_completed_points_without_distance(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    _write_json(
        run_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "distance.json",
        {"distance": None, "status": "not-computed"},
    )

    model = build_report_model(work_root, run_root)
    estimate = estimate_threshold(model)

    assert model["candidates"][0]["distance"] is None
    assert model["points"][0]["distance"] is None
    assert estimate["status"] == "not_enough_data"


def test_render_report_html_contains_golden_ler_and_inline_svg(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    expected = _load_json(
        work_root / "benchmarks" / "fixtures" / "rotated-d3" / "expected.json"
    )

    html = render_report_html(work_root, run_root)

    assert "<!doctype html>" in html
    assert "AutoQEC Search Report" in html
    assert "<svg" in html
    assert "Per-round logical error rate" in html
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


def test_report_is_data_driven_by_manifest_leaderboard_and_frontier(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    before = render_report_html(work_root, run_root)
    manifest_path = (
        run_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "evaluations"
        / "rotated-memory-z-cdep-v1"
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
                "rotated-memory-z-cdep-v1",
                "rmatching-default-v1",
                0.005,
                76533,
                1000,
                0.034,
                0.02,
                0.022,
                "leaderboard-sentinel",
            ],
        ],
    )
    frontier_item = {
        "candidate_id": "frontier-candidate-sentinel",
        "code_id": "frontier-code-sentinel",
        "rate": 0.271828,
        "note": "frontier-row-sentinel",
    }
    _write_json(
        run_root / "frontier.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "2026-06-09-example",
            "items": [frontier_item],
        },
    )
    after = render_report_html(work_root, run_root)
    report_json = after.split(
        '<script type="application/json" id="autoqec-report-data">', 1
    )[1].split("</script>", 1)[0]
    report_data = json.loads(report_json)

    assert before != after
    assert "0.021" in after
    assert "0.034" in after
    assert "leaderboard-sentinel" in after
    assert "frontier-candidate-sentinel" in after
    assert "frontier-code-sentinel" in after
    assert "0.271828" in after
    assert report_data["points"][0]["ler"] == 0.021
    assert report_data["leaderboard"][0]["ler"] == "0.034"
    assert report_data["leaderboard"][0]["status"] == "leaderboard-sentinel"
    assert report_data["frontier"] == [frontier_item]
    assert "0.013066258999385886" in before
    assert "0.013066258999385886" not in after


def test_threshold_estimate_detects_crossing() -> None:
    model = {
        "points": [
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 3,
                "p": 0.004,
                "ler": 0.010,
            },
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 3,
                "p": 0.006,
                "ler": 0.020,
            },
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 5,
                "p": 0.004,
                "ler": 0.006,
            },
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 5,
                "p": 0.006,
                "ler": 0.024,
            },
        ]
    }

    estimate = estimate_threshold(model)

    assert estimate["status"] == "estimated"
    assert estimate["task_id"] == "task"
    assert estimate["decoder_id"] == "decoder"
    assert estimate["p_estimate"] == pytest.approx(0.005)
    assert "coarse crossing" in estimate["method"]


def test_threshold_estimate_treats_all_zero_curves_as_inconclusive() -> None:
    model = {
        "points": [
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 3,
                "p": 0.004,
                "ler": 0.0,
            },
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 3,
                "p": 0.006,
                "ler": 0.0,
            },
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 5,
                "p": 0.004,
                "ler": 0.0,
            },
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 5,
                "p": 0.006,
                "ler": 0.0,
            },
        ]
    }

    estimate = estimate_threshold(model)

    assert estimate["status"] == "not_enough_data"
    assert "positive" in estimate["method"]


def test_threshold_estimate_reports_no_crossing_when_samples_are_comparable() -> None:
    model = {
        "points": [
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 3,
                "p": 0.004,
                "ler": 0.010,
            },
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 3,
                "p": 0.006,
                "ler": 0.020,
            },
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 5,
                "p": 0.004,
                "ler": 0.006,
            },
            {
                "task_id": "task",
                "decoder_id": "decoder",
                "distance": 5,
                "p": 0.006,
                "ler": 0.014,
            },
        ]
    }

    estimate = estimate_threshold(model)

    assert estimate["status"] == "not_enough_data"
    assert estimate["task_id"] == "task"
    assert estimate["decoder_id"] == "decoder"
    assert "no crossing in sampled p range" in estimate["method"]


def test_render_report_html_escapes_hostile_provenance_and_leaderboard(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    env_path = run_root / "env.json"
    env = _load_json(env_path)
    env["branch"] = "</script><svg/onload=alert(1)>"
    _write_json(env_path, env)
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
                "rotated-memory-z-cdep-v1",
                "rmatching-default-v1",
                0.005,
                76533,
                1000,
                0.013,
                0.012,
                0.014,
                'leaderboard & "quoted" <svg/onload=alert(2)>',
            ],
        ],
    )

    html = render_report_html(work_root, run_root)

    assert "</script><svg/onload=alert(1)>" not in html
    assert "<svg/onload=alert(2)>" not in html
    assert "&lt;/script&gt;&lt;svg/onload=alert(1)&gt;" in html
    assert "leaderboard &amp; &quot;quoted&quot; &lt;svg/onload=alert(2)&gt;" in html
    assert "\\u003c/script\\u003e\\u003csvg/onload=alert(1)\\u003e" in html


def test_render_ler_svg_escapes_hostile_series_labels() -> None:
    model = {
        "points": [
            {
                "candidate_id": "candidate</title><script>alert(1)</script>",
                "task_id": 'task & "quoted" <svg/onload=alert(2)>',
                "decoder_id": "decoder<script>alert(3)</script>",
                "distance": 3,
                "p": 0.005,
                "shots": 1000,
                "errors": 1,
                "ler": 0.001,
                "ci_low": 0.0005,
                "ci_high": 0.002,
            }
        ]
    }

    svg = render_ler_svg(model)

    assert "</title><script>" not in svg
    assert "<svg/onload=alert(2)>" not in svg
    assert "<script>alert(3)</script>" not in svg
    assert "candidate&lt;/title&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in svg
    assert "task &amp; &quot;quoted&quot; &lt;svg/onload=alert(2)&gt;" in svg
    assert "decoder&lt;script&gt;alert(3)&lt;/script&gt;" in svg


def _shot_error_rate_to_round_error_rate(
    shot_error_rate: float, rounds: int | float
) -> float:
    if rounds == 1:
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


def _test_log_bounds(values: list[float], floor: float) -> tuple[float, float]:
    logs = [math.log10(max(value, floor)) for value in values if math.isfinite(value)]
    low = min(logs)
    high = max(logs)
    if low == high:
        return low - 0.5, high + 0.5
    padding = (high - low) * 0.08
    return low - padding, high + padding


def test_render_ler_svg_plots_per_round_logical_error_rate() -> None:
    points = [
        {
            "candidate_id": "candidate",
            "task_id": "task",
            "decoder_id": "decoder",
            "distance": 3,
            "p": 0.005,
            "rounds": 10,
            "shots": 1000,
            "errors": 100,
            "ler": 0.1,
            "ci_low": 0.08,
            "ci_high": 0.12,
        },
        {
            "candidate_id": "candidate",
            "task_id": "task",
            "decoder_id": "decoder",
            "distance": 3,
            "p": 0.01,
            "rounds": 10,
            "shots": 1000,
            "errors": 200,
            "ler": 0.2,
            "ci_low": 0.16,
            "ci_high": 0.24,
        },
    ]

    svg = render_ler_svg({"points": points})

    round_rates = [
        _shot_error_rate_to_round_error_rate(point[key], point["rounds"])
        for point in points
        for key in ("ler", "ci_low", "ci_high")
    ]
    rate_floor = min(round_rates) / 10
    y_low, y_high = _test_log_bounds(round_rates, rate_floor)
    first_round_ler = _shot_error_rate_to_round_error_rate(0.1, 10)
    expected_y = 36 + (
        y_high - math.log10(max(first_round_ler, rate_floor))
    ) / (y_high - y_low) * (394 - 36)
    match = re.search(
        r'<circle cx="[^"]+" cy="(?P<cy>[^"]+)".*?'
        r"<title>task / decoder / candidate / d=3; p=0\.005;",
        svg,
    )

    assert match is not None
    assert float(match.group("cy")) == pytest.approx(expected_y, abs=1e-3)
    assert "per_round_ler=" in svg
    assert "shot_ler=0.1" in svg


def test_render_ler_svg_uses_compact_visible_legend_labels() -> None:
    model = {
        "points": [
            {
                "candidate_id": "rotated-surface-d7-example",
                "task_id": "rotated-memory-z-cdep-v1",
                "decoder_id": "rmatching-default-v1",
                "distance": 7,
                "p": 0.005,
                "shots": 99188,
                "errors": 1000,
                "ler": 0.010081864741702626,
                "ci_low": 0.009478838857910349,
                "ci_high": 0.010722838696183982,
            }
        ]
    }

    svg = render_ler_svg(model)

    full_label = (
        "rotated-memory-z-cdep-v1 / rmatching-default-v1 / "
        "rotated-surface-d7-example / d=7"
    )
    assert f">{full_label}</text>" not in svg
    assert ">d=7: rotated-surface-d7-example</text>" in svg
    assert f"<title>{full_label}; p=0.005;" in svg


def test_write_report_html_writes_default_and_custom_paths(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    default_path = write_report_html(work_root, run_root)
    custom_path = write_report_html(work_root, run_root, tmp_path / "custom-report.html")

    assert default_path == run_root / "report.html"
    assert default_path.is_file()
    assert custom_path.is_file()
    assert "AutoQEC Search Report" in custom_path.read_text()


def test_report_cli_writes_custom_report_path(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    output_path = tmp_path / "search-report.html"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
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
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert str(output_path) in result.stdout
    assert output_path.is_file()
    assert "AutoQEC Search Report" in output_path.read_text()


def test_report_cli_resolves_relative_run_path_from_root(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    outside_cwd = tmp_path / "outside"
    outside_cwd.mkdir()
    output_path = tmp_path / "root-relative-report.html"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "report",
            "--root",
            str(work_root),
            "--run",
            str(run_root.relative_to(work_root)),
            "--out",
            str(output_path),
        ],
        cwd=outside_cwd,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert str(output_path) in result.stdout
    assert output_path.is_file()
    assert "AutoQEC Search Report" in output_path.read_text()
