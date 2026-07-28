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
    assert model["overall"]["winner_label"] is None
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


def test_compare_candidate_runs_rejects_partial_overlap_across_three_runs(
    monkeypatch, tmp_path: Path
) -> None:
    from autoqec_search import compare_candidates

    models = {
        (tmp_path / "run-a").resolve(): _model(
            campaign_id="campaign-a",
            run_id="run-a",
            candidate_id="candidate-a",
            task_id="task-a",
            decoder_id="decoder-a",
            p=0.01,
            ler=0.010,
            ci_low=0.009,
            ci_high=0.011,
        ),
        (tmp_path / "run-b").resolve(): _model(
            campaign_id="campaign-b",
            run_id="run-b",
            candidate_id="candidate-b",
            task_id="task-a",
            decoder_id="decoder-a",
            p=0.01,
            ler=0.020,
            ci_low=0.019,
            ci_high=0.021,
        ),
        (tmp_path / "run-c").resolve(): _model(
            campaign_id="campaign-c",
            run_id="run-c",
            candidate_id="candidate-c",
            task_id="task-b",
            decoder_id="decoder-b",
            p=0.02,
            ler=0.015,
            ci_low=0.014,
            ci_high=0.016,
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
            [tmp_path / "run-a", tmp_path / "run-b", tmp_path / "run-c"],
        )


def test_compare_candidate_runs_distance_delta_uses_max_distance_anchor(
    monkeypatch, tmp_path: Path
) -> None:
    from autoqec_search import compare_candidates

    models = {
        (tmp_path / "run-a").resolve(): _model(
            campaign_id="campaign-a",
            run_id="run-a",
            candidate_id="candidate-a",
            ler=0.010,
            ci_low=0.009,
            ci_high=0.011,
            distance=5,
        ),
        (tmp_path / "run-b").resolve(): _model(
            campaign_id="campaign-b",
            run_id="run-b",
            candidate_id="candidate-b",
            ler=0.020,
            ci_low=0.019,
            ci_high=0.021,
            distance=3,
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

    rows_by_label = {row["run_label"]: row for row in model["comparisons"][0]["rows"]}
    assert rows_by_label["A"]["distance_delta"] == 0
    assert rows_by_label["B"]["distance_delta"] == -2


def test_compare_candidate_runs_keeps_multiple_candidates_per_run(
    monkeypatch, tmp_path: Path
) -> None:
    from autoqec_search import compare_candidates

    model_a = _model(
        campaign_id="campaign-a",
        run_id="run-a",
        candidate_id="candidate-a-fast",
        ler=0.010,
        ci_low=0.009,
        ci_high=0.011,
        distance=3,
    )
    model_a["points"].append(
        {
            "candidate_id": "candidate-a-wide",
            "distance": 5,
            "task_id": "task-a",
            "decoder_id": "decoder-a",
            "decoder_parameters": {},
            "p": 0.01,
            "rounds": 9,
            "shots": 1000,
            "errors": 30,
            "ler": 0.030,
            "ci_low": 0.028,
            "ci_high": 0.032,
            "seconds": 1.0,
        }
    )

    models = {
        (tmp_path / "run-a").resolve(): model_a,
        (tmp_path / "run-b").resolve(): _model(
            campaign_id="campaign-b",
            run_id="run-b",
            candidate_id="candidate-b",
            ler=0.020,
            ci_low=0.019,
            ci_high=0.021,
            distance=3,
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

    rows = model["comparisons"][0]["rows"]
    assert [row["candidate_id"] for row in rows] == [
        "candidate-a-fast",
        "candidate-b",
        "candidate-a-wide",
    ]
    assert {row["run_label"] for row in rows} == {"A", "B"}
    assert model["comparisons"][0]["winner"]["classification"] == "strong"
    assert model["comparisons"][0]["winner"]["winner_candidate_id"] == "candidate-a-fast"


def test_compare_candidate_runs_overall_winner_requires_all_strong_matches(
    monkeypatch, tmp_path: Path
) -> None:
    from autoqec_search import compare_candidates

    model_a = _model(
        campaign_id="campaign-a",
        run_id="run-a",
        candidate_id="candidate-a",
        task_id="task-a",
        p=0.01,
        ler=0.010,
        ci_low=0.009,
        ci_high=0.014,
        distance=3,
    )
    model_b = _model(
        campaign_id="campaign-b",
        run_id="run-b",
        candidate_id="candidate-b",
        task_id="task-a",
        p=0.01,
        ler=0.020,
        ci_low=0.013,
        ci_high=0.018,
        distance=3,
    )
    model_a["points"].append(
        {
            "candidate_id": "candidate-a",
            "distance": 3,
            "task_id": "task-b",
            "decoder_id": "decoder-a",
            "decoder_parameters": {},
            "p": 0.02,
            "rounds": 9,
            "shots": 1000,
            "errors": 1,
            "ler": 0.011,
            "ci_low": 0.010,
            "ci_high": 0.016,
            "seconds": 1.0,
        }
    )
    model_b["points"].append(
        {
            "candidate_id": "candidate-b",
            "distance": 3,
            "task_id": "task-b",
            "decoder_id": "decoder-a",
            "decoder_parameters": {},
            "p": 0.02,
            "rounds": 9,
            "shots": 1000,
            "errors": 2,
            "ler": 0.015,
            "ci_low": 0.013,
            "ci_high": 0.019,
            "seconds": 1.0,
        }
    )

    models = {
        (tmp_path / "run-a").resolve(): model_a,
        (tmp_path / "run-b").resolve(): model_b,
    }

    def fake_build_report_model(root: Path, run_root: Path) -> dict:
        return models[run_root.resolve()]

    monkeypatch.setattr(compare_candidates, "build_report_model", fake_build_report_model)
    model = compare_candidates.compare_candidate_runs(
        tmp_path,
        [tmp_path / "run-a", tmp_path / "run-b"],
        labels=["A", "B"],
    )

    assert len(model["comparisons"]) == 2
    assert all(c["winner"]["classification"] == "tentative" for c in model["comparisons"])
    assert model["overall"]["classification"] == "no-clear-winner"
    assert model["overall"]["winner_label"] is None


def test_compare_candidate_runs_tie_prevents_overall_winner(
    monkeypatch, tmp_path: Path
) -> None:
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
            ler=0.010,
            ci_low=0.009,
            ci_high=0.011,
        ),
    }

    def fake_build_report_model(root: Path, run_root: Path) -> dict:
        return models[run_root.resolve()]

    monkeypatch.setattr(compare_candidates, "build_report_model", fake_build_report_model)
    model = compare_candidates.compare_candidate_runs(
        tmp_path,
        [tmp_path / "run-a", tmp_path / "run-b"],
    )

    assert model["comparisons"][0]["winner"]["classification"] == "tie"
    assert model["overall"]["classification"] == "no-clear-winner"
    assert model["overall"]["winner_label"] is None


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
    assert "Provenance" in html
    assert "strong" in html
    assert "candidate-a" in html
    assert "candidate-b" in html
    assert "http://" not in html
    assert "https://" not in html
    assert written["html"] == tmp_path / "compare.html"
    assert written["json"] == tmp_path / "compare.json"
    assert written["html"].is_file()
    assert written["json"].is_file()


def test_write_compare_candidates_rejects_directory_output(
    monkeypatch, tmp_path: Path
) -> None:
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
    )
    outdir = tmp_path / "outdir"
    outdir.mkdir()

    with pytest.raises(SearchIntegrityError, match="could not write candidate comparison"):
        compare_candidates.write_compare_candidates(model, outdir)


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
