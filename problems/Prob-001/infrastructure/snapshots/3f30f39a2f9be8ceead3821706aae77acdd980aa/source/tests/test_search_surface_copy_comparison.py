from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from autoqec_search.cli import main
from autoqec_search.load import SearchIntegrityError
from autoqec_search.surface_copy_comparison import (
    compare_surface_copy,
    write_surface_copy_comparison,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "surface-copy-fixture-task-v1"
DECODER_ID = "surface-copy-fixture-decoder-v1"
SUITE_ID = "surface-copy-fixture-suite-v1"
CAMPAIGN_ID = "surface-copy-fixture"
RUN_ID = "surface-copy-run"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _baseline_row(
    *,
    distance: int,
    failures: int,
    shots: int = 10000,
    ci_low: float | None = None,
    ci_high: float | None = None,
) -> dict:
    ler = failures / shots
    return {
        "p": 0.001,
        "distance": distance,
        "logical_qubits": 1,
        "physical_qubits": distance**2,
        "decoder_id": DECODER_ID,
        "shots": shots,
        "failures": failures,
        "ler": ler,
        "ci_low": ler if ci_low is None else ci_low,
        "ci_high": ler if ci_high is None else ci_high,
    }


def _candidate(
    candidate_id: str,
    *,
    n: int,
    k: int,
    ler: float = 0.02,
    ci_low: float = 0.015,
    ci_high: float = 0.025,
    logical_failure_aggregation: str = "any_logical",
) -> dict:
    return {
        "candidate_id": candidate_id,
        "n": n,
        "k": k,
        "ler": ler,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "logical_failure_aggregation": logical_failure_aggregation,
    }


def _fixture_root(
    tmp_path: Path,
    candidates: list[dict],
    baseline_rows: list[dict] | None = None,
) -> tuple[Path, Path, Path]:
    root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "benchmarks" / "schemas", root / "benchmarks" / "schemas")
    (root / "benchmarks" / "fixtures").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        REPO_ROOT / "benchmarks" / "fixtures" / "manifest.json",
        root / "benchmarks" / "fixtures" / "manifest.json",
    )

    _write_json(
        root / "benchmarks" / "tasks" / f"{TASK_ID}.json",
        {
            "id": TASK_ID,
            "title": "Surface Copy Fixture Task",
            "observable": "logical_x",
            "noise_model": "circuit_depolarizing",
            "input_type": "css",
            "p_list": [0.001],
            "rounds_policy": {"kind": "fixed", "rounds": 9},
            "collection": {"max_shots": 10000, "max_errors": 100},
            "result_metrics": ["logical_error_rate"],
            "execution_status": "real",
        },
    )
    _write_json(
        root / "benchmarks" / "decoders" / f"{DECODER_ID}.json",
        {
            "id": DECODER_ID,
            "title": "Surface Copy Fixture Decoder",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {},
            "execution_status": "real",
        },
    )
    _write_json(
        root / "benchmarks" / "suites" / f"{SUITE_ID}.json",
        {
            "id": SUITE_ID,
            "title": "Surface Copy Fixture Suite",
            "task_ids": [TASK_ID],
            "decoder_ids": [DECODER_ID],
            "shared_settings": {
                "runner": "rsinter",
                "fixture_manifest": "benchmarks/fixtures/manifest.json",
            },
        },
    )

    _write_json(
        root / "campaigns" / "examples" / CAMPAIGN_ID / "campaign.json",
        {
            "id": CAMPAIGN_ID,
            "title": "Surface Copy Fixture Campaign",
            "objective": "Fixture campaign for surface-copy comparison tests.",
            "family_id": "quantum-tanner-code",
            "default_suite_id": SUITE_ID,
            "budget": {"wall_clock_seconds": 3600, "max_candidates": len(candidates)},
            "stop_conditions": {
                "max_candidates": len(candidates),
                "max_wall_clock_seconds": 3600,
            },
            "random_seed_policy": {"mode": "fixed", "seed": 7},
        },
    )
    _write_json(
        root / "campaigns" / "examples" / CAMPAIGN_ID / "search_space.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "mode": "explicit_list",
            "candidate_specs": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "code_family": "quantum-tanner-code",
                    "parameters": {"label": candidate["candidate_id"]},
                    "provenance": {"kind": "fixture", "label": candidate["candidate_id"]},
                }
                for candidate in candidates
            ],
        },
    )

    baseline_path = (
        root / "benchmarks" / "baselines" / "rotated-surface-single-logical-p001.json"
    )
    _write_json(
        baseline_path,
        {
            "baseline_id": "rotated-surface-single-logical-p001",
            "schema_version": 1,
            "code_id": "rotated-surface-code",
            "layout": "rotated",
            "result_kind": "smoke_fixture",
            "source": {"fixture": "tests/test_search_surface_copy_comparison.py"},
            "rows": baseline_rows
            if baseline_rows is not None
            else [
                _baseline_row(distance=3, failures=10, ci_low=0.0006, ci_high=0.0014),
                _baseline_row(distance=5, failures=4, ci_low=0.0002, ci_high=0.0006),
                _baseline_row(distance=7, failures=2, ci_low=0.00005, ci_high=0.00035),
            ],
        },
    )

    run_root = root / "results" / "search" / CAMPAIGN_ID / RUN_ID
    _write_json(
        run_root / "run_spec.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "run_id": RUN_ID,
            "suite_id": SUITE_ID,
            "task_ids": [TASK_ID],
            "decoder_ids": [DECODER_ID],
            "candidate_ids": [candidate["candidate_id"] for candidate in candidates],
            "created_at": "2026-07-08T00:00:00Z",
            "mode": "placeholder",
        },
    )
    _write_json(run_root / "env.json", {})
    _write_json(run_root / "frontier.json", {"items": []})
    (run_root / "leaderboard.csv").write_text("candidate_id,distance,decoder,p,ler\n")
    (run_root / "summary.md").write_text("# Surface Copy Fixture\n")

    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        candidate_root = run_root / "candidates" / candidate_id
        _write_json(
            candidate_root / "candidate.json",
            {
                "candidate_id": candidate_id,
                "campaign_id": CAMPAIGN_ID,
                "run_id": RUN_ID,
                "code_family": "quantum-tanner-code",
                "parameters": {"label": candidate_id},
                "provenance": {"kind": "fixture", "label": candidate_id},
                "status": "evaluated",
            },
        )
        _write_json(
            candidate_root / "structure.json",
            {
                "status": "completed",
                "n": candidate["n"],
                "k": candidate["k"],
                "mx": candidate["n"] - candidate["k"],
                "mz": candidate["n"] - candidate["k"],
                "rank_hx": candidate["n"] - candidate["k"],
                "rank_hz": candidate["n"] - candidate["k"],
                "css_commute": True,
                "commutation_failures": [],
            },
        )
        _write_json(
            candidate_root / "distance.json",
            {
                "status": "completed",
                "distance": 3,
                "method": "fixture",
                "source_instance_id": candidate_id,
                "source_instance_path": f"fixtures/{candidate_id}",
            },
        )
        _write_json(
            candidate_root
            / "evaluations"
            / TASK_ID
            / DECODER_ID
            / "manifest.json",
            {
                "campaign_id": CAMPAIGN_ID,
                "run_id": RUN_ID,
                "candidate_id": candidate_id,
                "task_id": TASK_ID,
                "decoder_id": DECODER_ID,
                "status": "completed",
                "decoder_parameters": {},
                "points": [
                    {
                        "p": 0.001,
                        "rounds": 9,
                        "shots": 10000,
                        "errors": int(candidate["ler"] * 10000),
                        "ler": candidate["ler"],
                        "ci_low": candidate["ci_low"],
                        "ci_high": candidate["ci_high"],
                        "seconds": 1.0,
                    }
                ],
                "run_metadata": {
                    "decoder_impl": "rbposd",
                    "logical_failure_aggregation": candidate[
                        "logical_failure_aggregation"
                    ],
                    "logical_observable_basis": "x",
                    "logical_observable_count": max(candidate["k"], 1),
                    "logical_observable_source": "explicit",
                    "seed": 7,
                },
                "tool_revisions": {
                    "autoqec_search": "0.1.0",
                    "rsinter": "rsinter 0.1.1",
                },
                "created_at": "2026-07-08T00:00:00Z",
            },
        )

    return root, run_root, baseline_path


def _row(model: dict, candidate_id: str) -> dict:
    for row in model["rows"]:
        if row["candidate_id"] == candidate_id:
            return row
    raise AssertionError(f"missing candidate row: {candidate_id}")


def test_k1_copied_block_ler_equals_single_patch_ler(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [_candidate("candidate-k1", n=9, k=1)],
    )
    model = compare_surface_copy(root, run_root, baseline_path)
    row = _row(model, "candidate-k1")
    assert row["status"] == "accepted"
    assert row["surface_block_ler"] == row["surface_single_ler"]


def test_placeholder_candidate_without_structure_is_ignored(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [
            _candidate("candidate-completed", n=9, k=1),
            _candidate("candidate-skipped", n=16, k=2),
        ],
    )
    skipped_root = run_root / "candidates" / "candidate-skipped"
    _write_json(
        skipped_root / "structure.json",
        {"status": "not-computed", "n": None, "k": None, "mx": None, "mz": None},
    )
    _write_json(
        skipped_root / "evaluations" / TASK_ID / DECODER_ID / "manifest.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "candidate_id": "candidate-skipped",
            "created_at": "2026-07-10T00:00:00Z",
            "decoder_id": DECODER_ID,
            "metrics": {"logical_error_rate": None},
            "run_id": RUN_ID,
            "status": "placeholder",
            "task_id": TASK_ID,
        },
    )

    model = compare_surface_copy(root, run_root, baseline_path)

    assert [row["candidate_id"] for row in model["rows"]] == ["candidate-completed"]
    assert model["counts"] == {"rows": 1, "accepted": 1, "rejected": 0}


def test_k12_copied_block_ler_uses_elementary_probability(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [_candidate("candidate-k12", n=108, k=12)],
    )
    model = compare_surface_copy(root, run_root, baseline_path)
    row = _row(model, "candidate-k12")
    assert row["surface_single_ler"] == 0.001
    assert row["surface_block_ler"] == pytest.approx(
        1 - (1 - 0.001) ** 12,
        abs=1e-15,
    )
    written = write_surface_copy_comparison(model, tmp_path / "surface-copy.html")
    assert written["html"] == tmp_path / "surface-copy.html"
    assert written["json"] == tmp_path / "surface-copy.json"
    assert written["html"].is_file()
    assert written["json"].is_file()
    html = written["html"].read_text()
    assert "candidate-k12" in html
    for label in (
        "Candidate ID",
        "n",
        "k",
        "Tanner LER+CI",
        "Aggregation",
        "Surface Distance",
        "d^2",
        "Copied Physical",
        "Unused Budget",
        "Single-Patch Surface LER",
        "Copied Block Surface LER",
        "Copied Block CI",
        "Status/Reason",
    ):
        assert label in html
    assert "application/json" in html
    assert json.loads(written["json"].read_text()) == model


def test_copied_ci_endpoints_are_transformed_and_ordered(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [_candidate("candidate-ci", n=108, k=12)],
    )
    model = compare_surface_copy(root, run_root, baseline_path)
    row = _row(model, "candidate-ci")
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
    assert (
        "copied CI provenance"
        in model["row_contract"]["support_fields"]["surface_single_ci_low"]
    )


def test_selected_surface_patch_stays_under_physical_budget(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [_candidate("candidate-budget", n=305, k=12)],
    )
    row = _row(compare_surface_copy(root, run_root, baseline_path), "candidate-budget")
    assert row["surface_distance"] == 5
    assert row["surface_copied_total_physical"] == 300
    assert row["surface_copied_total_physical"] <= row["n"]
    assert row["unused_physical_budget"] == 5


def test_only_any_logical_tanner_points_are_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [
            _candidate("candidate-any", n=108, k=12),
            _candidate(
                "candidate-per-logical",
                n=108,
                k=12,
                logical_failure_aggregation="per_logical",
            ),
        ],
    )
    model = compare_surface_copy(root, run_root, baseline_path)
    assert _row(model, "candidate-any")["status"] == "accepted"
    rejected = _row(model, "candidate-per-logical")
    assert rejected["status"] == "rejected"
    assert "any_logical" in rejected["reason"]
    out_path = tmp_path / "surface-copy-cli.html"
    code = main(
        [
            "compare-surface-copy",
            "--root",
            str(root),
            "--run",
            str(run_root.relative_to(root)),
            "--baseline",
            str(baseline_path.relative_to(root)),
            "--out",
            str(out_path),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert out_path.is_file()
    assert out_path.with_suffix(".json").is_file()
    payload = json.loads(out_path.with_suffix(".json").read_text())
    assert _row(payload, "candidate-any")["status"] == "accepted"
    assert _row(payload, "candidate-per-logical")["status"] == "rejected"
    assert "wrote surface copy comparison" in captured.out

    invalid_root = tmp_path / "invalid-workspace"
    invalid_root.mkdir()
    with pytest.raises(SearchIntegrityError, match="missing required directory"):
        compare_surface_copy(invalid_root, run_root, baseline_path)

    with pytest.raises(SearchIntegrityError, match="unknown search run"):
        compare_surface_copy(root, root / "results" / "search" / CAMPAIGN_ID / "missing-run", baseline_path)


def test_tanner_row_with_nonpositive_k_is_rejected(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [_candidate("candidate-bad-k", n=108, k=0)],
    )
    row = _row(compare_surface_copy(root, run_root, baseline_path), "candidate-bad-k")
    assert row["status"] == "rejected"
    assert row["reason"] == "candidate k must be positive"


def test_surface_baseline_with_wrong_p_is_rejected(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [_candidate("candidate-k12", n=108, k=12)],
        baseline_rows=[{**_baseline_row(distance=3, failures=10), "p": 0.01}],
    )
    with pytest.raises(SearchIntegrityError, match="p=0.001"):
        compare_surface_copy(root, run_root, baseline_path)


def test_tanner_row_without_fitting_surface_patch_is_rejected(tmp_path: Path) -> None:
    root, run_root, baseline_path = _fixture_root(
        tmp_path,
        [_candidate("candidate-no-fit", n=100, k=12)],
    )
    row = _row(compare_surface_copy(root, run_root, baseline_path), "candidate-no-fit")
    assert row["status"] == "rejected"
    assert "k*d*d <= n" in row["reason"]
