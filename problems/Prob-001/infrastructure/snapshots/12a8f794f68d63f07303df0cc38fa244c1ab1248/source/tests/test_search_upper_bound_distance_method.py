from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from autoqec_search.distance_methods import (
    DistanceMethodOptions,
    compute_distance_payload,
    load_distance_payload_from_dict,
    normalize_distance_method_options,
)
from autoqec_search.eval_candidates import (
    CandidateInput,
    ResolvedCandidate,
    copy_candidate_artifacts,
)
from autoqec_search.eval_run import evaluate_single_candidate
from autoqec_search.load import SearchIntegrityError
from autoqec_search.promote import evaluate_promotions
from autoqec_search.report import build_report_model


REPO_ROOT = Path(__file__).resolve().parents[1]
METHOD = "random-window-upper-bound"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _copy_search_tree(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    shutil.copytree(REPO_ROOT / "zoo", work_root / "zoo")
    return work_root


def _copied_candidate(*, distance: int = 3) -> ResolvedCandidate:
    artifact_root = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    instance = _load_json(artifact_root / "instance.json")
    if distance != instance["derived_properties"]["distance"]:
        instance["derived_properties"]["distance"] = distance
        instance["parameters"]["distance"] = distance
    return ResolvedCandidate(
        spec=CandidateInput(
            candidate_id="rotated-surface-d3-example",
            campaign_id="rotated-surface-baseline",
            code_family="rotated-surface-code",
            parameters={"distance": distance, "layout": "rotated"},
            provenance={"kind": "test", "label": "upper-bound"},
        ),
        artifact_root=artifact_root,
        instance=instance,
        hx=_load_json(artifact_root / "hx.json"),
        hz=_load_json(artifact_root / "hz.json"),
        source_kind="zoo-instance",
    )


def _run_root_with_random_window_upper_bound(tmp_path: Path) -> tuple[Path, Path]:
    work_root = _copy_search_tree(tmp_path)
    run_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
    )
    candidate_root = run_root / "candidates" / "rotated-surface-d3-example"

    _write_json(
        candidate_root / "distance.json",
        {
            "status": "completed",
            "method": METHOD,
            "bound_type": "upper",
            "upper_bound": 3,
            "options": {"method": METHOD},
        },
    )

    candidate = _load_json(candidate_root / "candidate.json")
    candidate["status"] = "evaluated"
    _write_json(candidate_root / "candidate.json", candidate)

    artifact_root = candidate_root / "artifacts"
    artifact_source = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    artifact_root.mkdir(exist_ok=True, parents=True)
    for name in ("instance.json", "hx.json", "hz.json"):
        shutil.copyfile(artifact_source / name, artifact_root / name)

    _write_json(
        run_root / "frontier.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "2026-06-09-example",
            "items": [
                {
                    "candidate_id": "rotated-surface-d3-example",
                    "distance": 3,
                    "decoder_id": "rmatching-default-v1",
                    "p": 0.01,
                    "ler": 0.5,
                    "manifest_path": (
                        "candidates/rotated-surface-d3-example/evaluations/"
                        "rotated-memory-z-cdep-v1/rmatching-default-v1/manifest.json"
                    ),
                }
            ],
        },
    )
    _write_json(
        candidate_root
        / "evaluations"
        / "rotated-memory-z-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "2026-06-09-example",
            "candidate_id": "rotated-surface-d3-example",
            "task_id": "rotated-memory-z-cdep-v1",
            "decoder_id": "rmatching-default-v1",
            "status": "completed",
            "created_at": "2026-06-09T00:00:00Z",
            "tool_revisions": {"autoqec_search": "0.1.0", "rsinter": "rsinter fake"},
            "points": [
                {
                    "p": 0.01,
                    "rounds": 3,
                    "shots": 1000,
                    "errors": 500,
                    "ler": 0.5,
                    "ci_low": 0.0,
                    "ci_high": 1.0,
                    "seconds": 0.1,
                }
            ],
        },
    )
    return work_root, run_root


def test_eval_records_random_window_upper_bound_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = _copy_search_tree(tmp_path)

    def fake_run_rsinter(
        spec_path: Path,
        out_dir: Path,
        *,
        executable: str,
        timeout_seconds: int = 3600,
        requires_general_css_support: bool = False,
    ) -> None:
        result_path = out_dir / "predict-zero-v1" / "test-run" / "results.jsonl"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "benchmark": "autoqec-bb-css-memory-x-cdep-v1",
                    "runner": "predict-zero-v1",
                    "language": "rust",
                    "status": "ok",
                    "params": {
                        "input_type": "css",
                        "code_id": "bivariate-bicycle-code-m6-n6",
                        "hx": "../artifacts/hx.sparse_rows.json",
                        "hz": "../artifacts/hz.sparse_rows.json",
                        "basis": "x",
                        "schedule": "greedy",
                        "observables": "input/observables.css.json",
                        "rounds": 3,
                        "p": 0.003,
                        "max_shots": 64,
                        "max_errors": 32,
                        "batch_size": 64,
                        "decoder_impl": "predict-zero",
                        "logical_failure_aggregation": "any_logical",
                        "logical_observable_source": "explicit",
                        "logical_observable_basis": "x",
                        "logical_observable_count": 12,
                        "seed": 12345,
                    },
                    "case_summary": {
                        "num_dets": 216,
                        "num_obs": 12,
                        "num_shots_generated": 64,
                    },
                    "metrics": {
                        "shots_used": 64,
                        "logical_errors": 1,
                        "logical_error_rate": 1 / 64,
                    },
                    "artifacts": {},
                    "error": None,
                },
                sort_keys=True,
            )
            + "\n"
        )

    monkeypatch.setattr(
        "autoqec_search.eval_run.require_rsinter",
        lambda: ("/bin/rsinter", "rsinter fake"),
    )
    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fake_run_rsinter)

    options = normalize_distance_method_options(method=METHOD, qec_code_bin="qec-code")
    result = evaluate_single_candidate(
        work_root,
        campaign_id="decoder-registry-css-bb-smoke",
        distance=None,
        candidate_dir=None,
        run_id="m2-upper-bound-eval",
        decoder_filter=["predict-zero-v1"],
        p_filter=["0.003"],
        force=False,
        distance_method_options=options,
    )
    env = _load_json(result.run_root / "env.json")

    assert options.method == METHOD
    assert env["distance_method"]["method"] == METHOD
    assert env["distance_method"]["bound_type"] == "upper"


def test_copied_candidate_artifact_writes_upper_bound_distance_payload(tmp_path: Path) -> None:
    candidate = _copied_candidate(distance=3)
    payload = compute_distance_payload(
        candidate,
        DistanceMethodOptions(method=METHOD, qec_code_bin="qec-code"),
    )
    candidate_root = tmp_path / "tmp-upper-bound-artifact"

    copy_candidate_artifacts(candidate, candidate_root, distance_payload=payload)
    distance = _load_json(candidate_root / "distance.json")

    assert distance["method"] == METHOD
    assert distance["bound_type"] == "upper"
    assert distance["upper_bound"] == 3
    assert "distance" not in distance


def test_build_report_model_exposes_random_window_upper_bound_distance_type(
    tmp_path: Path,
) -> None:
    work_root, run_root = _run_root_with_random_window_upper_bound(tmp_path)
    model = build_report_model(work_root, run_root)

    assert model["candidates"][0]["distance_method"] == METHOD
    assert model["candidates"][0]["distance_bound_type"] == "upper"
    assert model["candidates"][0]["upper_bound"] == 3
    assert model["candidates"][0]["parameters"] == {
        "distance": 3,
        "layout": "rotated",
    }
    assert model["candidates"][0]["provenance"] == {
        "kind": "seed",
        "label": "repo-example",
    }


def test_evaluate_promotions_rejects_random_window_upper_bound_candidate(
    tmp_path: Path,
) -> None:
    _, run_root = _run_root_with_random_window_upper_bound(tmp_path)

    with pytest.raises(SearchIntegrityError, match="requires an exact distance"):
        evaluate_promotions(run_root, {"min_distance": 3, "require_distance_verified": True})


def test_load_distance_payload_rejects_corrupted_random_window_upper_bound_payload() -> None:
    legacy_loaded = load_distance_payload_from_dict(
        {
            "status": "completed",
            "distance": 3,
            "upper_bound": 3,
            "method": "randomized-upper-bound",
            "bound_type": "upper",
        },
        label="legacy randomized payload",
    )

    assert legacy_loaded.bound_type == "upper"
    assert legacy_loaded.distance == 3

    with pytest.raises(
        SearchIntegrityError,
        match="random-window-upper-bound distance payload must use bound_type upper",
    ):
        load_distance_payload_from_dict(
            {
                "status": "completed",
                "distance": 3,
                "upper_bound": 3,
                "method": METHOD,
                "bound_type": "exact",
            },
            label="distance payload",
        )


def test_normalize_distance_method_options_rejects_unknown_upper_bound_method() -> None:
    with pytest.raises(SearchIntegrityError, match="unknown distance method: some-upper-bound"):
        normalize_distance_method_options(method="some-upper-bound", qec_code_bin="qec-code")
