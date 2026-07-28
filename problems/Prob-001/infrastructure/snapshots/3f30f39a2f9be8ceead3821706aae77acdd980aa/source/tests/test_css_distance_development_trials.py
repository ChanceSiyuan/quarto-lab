from __future__ import annotations

from pathlib import Path
import json
import statistics

import pytest

import autoqec_search.css_distance_development_baselines as baselines
import autoqec_search.css_distance_development_trials as development_trials
from autoqec_search.css_distance_development_baselines import DevelopmentCase
from autoqec_search.css_distance_development_trials import (
    aggregate_trial_results,
    append_trial_result_log,
    nearest_rank_percentile,
    not_run_trial_summary,
    run_development_trial,
    write_trial_report,
)
from autoqec_search.css_distance_container import (
    CssDistanceInfrastructureError,
    DockerImage,
)


_PROPOSAL_IMAGE_ID = "sha256:" + "1" * 64
_EVALUATOR_IMAGE_ID = "sha256:" + "2" * 64


def _case(index: int) -> DevelopmentCase:
    return DevelopmentCase(
        case_id=f"development-{index:03d}",
        hx_path=Path("hidden/hx.json"),
        hz_path=Path("hidden/hz.json"),
        target=1,
        bound_type="exact",
    )


def _write_private_split(tmp_path: Path) -> Path:
    work_root = tmp_path / "private-work-root"
    development = (
        work_root / "private" / "css-distance-paper-suite" / "development"
    )
    development.mkdir(parents=True)
    matrix = {
        "format": "sparse_rows",
        "num_cols": 4,
        "rows": [[0, 1]],
    }
    records = []
    for index in range(24):
        case_id = f"development-{index:03d}"
        case_root = development / case_id
        case_root.mkdir()
        for name in ("hx.json", "hz.json"):
            (case_root / name).write_text(json.dumps(matrix), encoding="utf-8")
        records.append(
            {
                "case_id": case_id,
                "reference": {"bound_type": "exact", "value": 1},
                "hx_path": f"{case_id}/hx.json",
                "hz_path": f"{case_id}/hz.json",
            }
        )
    (development / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "split": "development", "cases": records}),
        encoding="utf-8",
    )
    return work_root


def test_aggregate_trial_results_includes_timeout_in_quantiles() -> None:
    cases = [_case(index) for index in range(24)]
    results = [
        {
            "case_id": case.case_id,
            "status": "timeout" if index in {22, 23} else "completed",
            "runtime_seconds": float(index + 1),
            **({} if index in {22, 23} else {"verified_weight": case.target}),
        }
        for index, case in enumerate(cases)
    ]

    summary = aggregate_trial_results(cases=cases, results=results, timeout_seconds=300)
    durations = [float(index + 1) for index in range(22)] + [300.0, 300.0]

    assert summary["runs"] == 24
    assert summary["median_seconds"] == statistics.median(durations)
    assert summary["p95_seconds"] == 300.0
    assert summary["runtime_seconds"] == sum(durations)
    assert summary["average_seconds"] == statistics.mean(durations)


@pytest.mark.parametrize("timeout_seconds", [299, True])
def test_aggregate_trial_results_requires_the_fixed_300_second_timeout(
    timeout_seconds: float,
) -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be exactly 300"):
        aggregate_trial_results(
            cases=[],
            results=[],
            timeout_seconds=timeout_seconds,
        )


def test_nearest_rank_percentile_uses_sorted_timeout_inclusive_durations() -> None:
    assert nearest_rank_percentile([3.0, 1.0, 2.0, 300.0], 0.95) == 300.0
    assert nearest_rank_percentile([3.0, 1.0, 2.0, 300.0], 0.5) == 2.0


@pytest.mark.parametrize("values", [[], [float("nan")], [float("inf")], [-0.1]])
def test_nearest_rank_percentile_rejects_unsafe_durations(values: list[float]) -> None:
    with pytest.raises(ValueError, match="percentile requires|duration"):
        nearest_rank_percentile(values, 0.95)


@pytest.mark.parametrize("percentile", [0, -0.1, 1.1])
def test_nearest_rank_percentile_rejects_unsafe_percentiles(percentile: float) -> None:
    with pytest.raises(ValueError, match="percentile requires"):
        nearest_rank_percentile([1.0], percentile)


@pytest.mark.parametrize("failure", ["missing", "duplicate", "unsafe"])
def test_aggregate_trial_results_rejects_missing_duplicate_or_unsafe_case_results(
    failure: str,
) -> None:
    cases = [_case(index) for index in range(24)]
    results: list[dict[str, object]] = [
        {
            "case_id": case.case_id,
            "status": "completed",
            "runtime_seconds": 1.0,
            "verified_weight": case.target,
        }
        for case in cases
    ]
    if failure == "missing":
        results.pop()
    elif failure == "duplicate":
        results[-1]["case_id"] = cases[0].case_id
    else:
        results[0]["runtime_seconds"] = float("nan")

    with pytest.raises(ValueError, match="case result|duration"):
        aggregate_trial_results(cases=cases, results=results)


def test_not_run_trial_summary_omits_timing_fields() -> None:
    summary = not_run_trial_summary()

    assert summary == {
        "decision": "rejected",
        "accepted": False,
        "runs": 0,
        "verified_witnesses": 0,
        "target_hits": 0,
        "timeouts": 0,
        "crashes": 0,
        "invalid_claims": 1,
        "weighted_target_hits": 0,
        "normalized_quality": 0.0,
        "runtime_seconds": 0.0,
    }
    assert "average_seconds" not in summary
    assert "median_seconds" not in summary
    assert "p95_seconds" not in summary


def test_run_development_trial_uses_only_24_development_cases_and_derived_seeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = [_case(index) for index in range(24)]
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        "autoqec_search.css_distance_development_trials.load_development_cases",
        lambda suite_work_root: cases,
    )

    def fake_run_container_method(**kwargs: object) -> list[dict[str, object]]:
        observed.update(kwargs)
        return [
            {
                "case_id": case.case_id,
                "status": "completed",
                "runtime_seconds": 0.5,
                "verified_weight": case.target,
            }
            for case in cases
        ]

    monkeypatch.setattr(
        "autoqec_search.css_distance_development_trials._run_container_method",
        fake_run_container_method,
    )

    summary = run_development_trial(
        proposal=101,
        suite_work_root=tmp_path / "suite",
        candidate_worktree=tmp_path / "candidate",
        docker_image=DockerImage("image:latest", "baseline"),
        output_root=tmp_path / "output",
    )

    assert observed["cases"] == cases
    assert observed["seeds"] == [202607230000 + 101 * 100 + index for index in range(24)]
    assert observed["timeout_seconds"] == 300
    assert observed["max_parallel"] == 2
    assert summary["runs"] == 24
    assert summary["median_seconds"] == 0.5
    assert "case_id" not in summary


def test_run_development_trial_reuses_one_snapshot_without_reloading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = getattr(baselines, "load_development_snapshot", None)
    assert callable(loader)
    load_calls = 0

    def counted_loader(path: Path) -> object:
        nonlocal load_calls
        load_calls += 1
        return loader(path)

    snapshot = counted_loader(_write_private_split(tmp_path))
    observed_cases: list[tuple[tuple[str, int], ...]] = []

    def fake_run_container_method(**kwargs: object) -> list[dict[str, object]]:
        cases = kwargs["cases"]
        assert isinstance(cases, tuple)
        observed_cases.append(tuple((case.case_id, case.target) for case in cases))
        return [
            {
                "case_id": case.case_id,
                "status": "completed",
                "runtime_seconds": 0.5,
                "verified_weight": case.target,
            }
            for case in cases
        ]

    monkeypatch.setattr(
        development_trials,
        "load_development_cases",
        lambda _: (_ for _ in ()).throw(
            AssertionError("snapshot-backed trials must not reload cases")
        ),
    )
    monkeypatch.setattr(
        development_trials,
        "_run_container_method",
        fake_run_container_method,
    )

    for proposal in (101, 102):
        summary = run_development_trial(
            proposal=proposal,
            suite_work_root=tmp_path / "ignored-suite-root",
            development_snapshot=snapshot,
            candidate_worktree=tmp_path / "candidate",
            docker_image=DockerImage("image:latest", "baseline"),
            output_root=tmp_path / "output",
        )
        assert summary["runs"] == 24

    assert load_calls == 1
    assert observed_cases[0] == observed_cases[1]


def test_run_development_trial_accepts_pinned_cases_directly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = getattr(baselines, "load_development_snapshot", None)
    assert callable(loader)
    snapshot = loader(_write_private_split(tmp_path))
    observed: dict[str, object] = {}

    def fake_run_container_method(**kwargs: object) -> list[dict[str, object]]:
        observed.update(kwargs)
        cases = kwargs["cases"]
        return [
            {
                "case_id": case.case_id,
                "status": "completed",
                "runtime_seconds": 0.5,
                "verified_weight": case.target,
            }
            for case in cases
        ]

    monkeypatch.setattr(
        development_trials,
        "load_development_cases",
        lambda _: (_ for _ in ()).throw(
            AssertionError("direct pinned cases must not reload")
        ),
    )
    monkeypatch.setattr(
        development_trials,
        "_run_container_method",
        fake_run_container_method,
    )

    summary = run_development_trial(
        proposal=101,
        suite_work_root=tmp_path / "ignored-suite-root",
        development_cases=snapshot.cases,
        candidate_worktree=tmp_path / "candidate",
        docker_image=DockerImage("image:latest", "baseline"),
        output_root=tmp_path / "output",
    )

    assert observed["cases"] is snapshot.cases
    assert summary["runs"] == 24


@pytest.mark.parametrize("drift", ["manifest-target", "matrix"])
def test_run_development_trial_rejects_snapshot_drift_between_trials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    loader = getattr(baselines, "load_development_snapshot", None)
    assert callable(loader)
    snapshot = loader(_write_private_split(tmp_path))
    evaluations = 0

    def fake_run_container_method(**kwargs: object) -> list[dict[str, object]]:
        nonlocal evaluations
        evaluations += 1
        cases = kwargs["cases"]
        return [
            {
                "case_id": case.case_id,
                "status": "completed",
                "runtime_seconds": 0.5,
                "verified_weight": case.target,
            }
            for case in cases
        ]

    monkeypatch.setattr(
        development_trials,
        "_run_container_method",
        fake_run_container_method,
    )
    run_development_trial(
        proposal=101,
        suite_work_root=tmp_path / "ignored-suite-root",
        development_snapshot=snapshot,
        candidate_worktree=tmp_path / "candidate",
        docker_image=DockerImage("image:latest", "baseline"),
        output_root=tmp_path / "output",
    )

    if drift == "manifest-target":
        manifest = snapshot.manifest.path
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["cases"][0]["reference"]["value"] = 2
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        changed_path = manifest
    else:
        changed_path = snapshot.cases[0].hx_path
        changed_path.write_text(
            json.dumps(
                {
                    "format": "sparse_rows",
                    "num_cols": 4,
                    "rows": [[0, 2]],
                }
            ),
            encoding="utf-8",
        )

    with pytest.raises(CssDistanceInfrastructureError) as error:
        run_development_trial(
            proposal=102,
            suite_work_root=tmp_path / "ignored-suite-root",
            development_snapshot=snapshot,
            candidate_worktree=tmp_path / "candidate",
            docker_image=DockerImage("image:latest", "baseline"),
            output_root=tmp_path / "output",
        )

    assert str(error.value) == "development suite snapshot changed"
    assert str(changed_path) not in str(error.value)
    assert "development-000" not in str(error.value)
    assert evaluations == 1


def test_development_runner_propagates_container_infrastructure_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matrix = {
        "format": "dense_binary_matrix",
        "n_rows": 1,
        "n_cols": 2,
        "data": [[1, 1]],
    }
    case_root = tmp_path / "case"
    case_root.mkdir()
    for name in ("hx.json", "hz.json"):
        (case_root / name).write_text(json.dumps(matrix), encoding="utf-8")
    cases = [
        DevelopmentCase(
            case_id=f"development-{index:03d}",
            hx_path=case_root / "hx.json",
            hz_path=case_root / "hz.json",
            target=1,
            bound_type="exact",
        )
        for index in range(24)
    ]
    workspace = tmp_path / "candidate" / "proposal-workspace"
    workspace.mkdir(parents=True)
    (workspace / "candidate.py").write_text("print('{}')\n", encoding="utf-8")

    monkeypatch.setattr(
        "autoqec_search.css_distance_development_trials.load_development_cases",
        lambda suite_work_root: cases,
    )
    monkeypatch.setattr(
        "autoqec_search.css_distance_development_baselines.run_candidate_case",
        lambda **kwargs: (_ for _ in ()).throw(
            CssDistanceInfrastructureError("docker transport exit 125")
        ),
    )

    with pytest.raises(CssDistanceInfrastructureError, match="125"):
        run_development_trial(
            proposal=101,
            suite_work_root=tmp_path / "suite",
            candidate_worktree=workspace.parent,
            docker_image=DockerImage("evaluator:test", "baseline"),
            output_root=tmp_path / "output",
            max_parallel=2,
        )


def test_run_development_trial_rejects_out_of_range_proposal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="proposal"):
        run_development_trial(
            proposal=100,
            suite_work_root=tmp_path,
            candidate_worktree=tmp_path,
            docker_image=DockerImage("image:latest", "baseline"),
            output_root=tmp_path,
        )


@pytest.mark.parametrize("timeout_seconds", [299, True])
def test_run_development_trial_requires_fixed_timeout_before_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    timeout_seconds: float,
) -> None:
    def should_not_load(_: Path) -> list[DevelopmentCase]:
        raise AssertionError("development cases must not be loaded")

    monkeypatch.setattr(
        "autoqec_search.css_distance_development_trials.load_development_cases",
        should_not_load,
    )

    with pytest.raises(ValueError, match="timeout_seconds must be exactly 300"):
        run_development_trial(
            proposal=101,
            suite_work_root=tmp_path,
            candidate_worktree=tmp_path,
            docker_image=DockerImage("image:latest", "baseline"),
            output_root=tmp_path,
            timeout_seconds=timeout_seconds,
        )


def test_append_trial_result_log_keeps_only_safe_aggregate_fields(tmp_path: Path) -> None:
    summary = {
        "decision": "accepted",
        "accepted": True,
        "runs": 24,
        "verified_witnesses": 24,
        "target_hits": 24,
        "timeouts": 0,
        "crashes": 0,
        "invalid_claims": 0,
        "weighted_target_hits": 24,
        "normalized_quality": 1.0,
        "runtime_seconds": 16.8,
        "average_seconds": 0.7,
        "median_seconds": 0.6,
        "p95_seconds": 1.2,
        "case_id": "development-000",
    }

    log = append_trial_result_log(tmp_path, summary=summary)

    contents = log.read_text(encoding="utf-8")
    assert "## Development Result" in contents
    assert "average_seconds: 0.7" in contents
    assert "median_seconds: 0.6" in contents
    assert "p95_seconds: 1.2" in contents
    assert "development-000" not in contents


def test_write_trial_report_serializes_safe_timing_quantiles(tmp_path: Path) -> None:
    report = write_trial_report(
        tmp_path / "REPORT.md",
        proposal=101,
        branch="autoresearch/css-distance/run200-proposal-101",
        method="matrix-free randomized aggregate search",
        public_contract_status="passed",
        proposal_image_id=_PROPOSAL_IMAGE_ID,
        evaluator_image_id=_EVALUATOR_IMAGE_ID,
        summary={
            "decision": "accepted",
            "accepted": True,
            "runs": 24,
            "verified_witnesses": 24,
            "target_hits": 24,
            "timeouts": 0,
            "crashes": 0,
            "invalid_claims": 0,
            "weighted_target_hits": 24,
            "normalized_quality": 1.0,
            "runtime_seconds": 16.8,
            "average_seconds": 0.7,
            "median_seconds": 0.6,
            "p95_seconds": 1.2,
        },
    )

    contents = report.read_text(encoding="utf-8")
    assert "# CSS Distance Proposal 101 Report" in contents
    assert "autoresearch/css-distance/run200-proposal-101" in contents
    assert "| Proposal total | 200 |" in contents
    assert "| Average seconds | 0.700000000000000 |" in contents
    assert "| Median seconds | 0.600000000000000 |" in contents
    assert "| P95 seconds | 1.200000000000000 |" in contents
    assert f"| Proposal image ID | {_PROPOSAL_IMAGE_ID} |" in contents
    assert f"| Evaluator image ID | {_EVALUATOR_IMAGE_ID} |" in contents


def test_write_trial_report_marks_zero_run_quantiles_not_run(tmp_path: Path) -> None:
    report = write_trial_report(
        tmp_path / "REPORT.md",
        proposal=101,
        branch="autoresearch/css-distance/run200-proposal-101",
        method="matrix-free randomized aggregate search",
        public_contract_status="failed",
        proposal_image_id=_PROPOSAL_IMAGE_ID,
        evaluator_image_id=_EVALUATOR_IMAGE_ID,
        summary=not_run_trial_summary(),
    )

    contents = report.read_text(encoding="utf-8")
    assert contents.count("| not run |") == 3


@pytest.mark.parametrize(
    ("method", "branch", "timeout_seconds"),
    [
        ("/private/candidate.py", "autoresearch/css-distance/run200-proposal-101", 300),
        ("matrix-free randomized aggregate search", "autoresearch/css-distance/run200-proposal-102", 300),
        ("matrix-free randomized aggregate search", "autoresearch/css-distance/run200-proposal-101", 30),
    ],
)
def test_write_trial_report_rejects_unsafe_public_contract(
    tmp_path: Path,
    method: str,
    branch: str,
    timeout_seconds: float,
) -> None:
    with pytest.raises(ValueError):
        write_trial_report(
            tmp_path / "REPORT.md",
            proposal=101,
            branch=branch,
            method=method,
            public_contract_status="passed",
            proposal_image_id=_PROPOSAL_IMAGE_ID,
            evaluator_image_id=_EVALUATOR_IMAGE_ID,
            summary=not_run_trial_summary(),
            timeout_seconds=timeout_seconds,
        )


@pytest.mark.parametrize(
    ("proposal_image_id", "evaluator_image_id"),
    [
        ("proposal:latest", _EVALUATOR_IMAGE_ID),
        (_PROPOSAL_IMAGE_ID, _PROPOSAL_IMAGE_ID),
    ],
)
def test_write_trial_report_requires_distinct_immutable_image_evidence(
    tmp_path: Path,
    proposal_image_id: str,
    evaluator_image_id: str,
) -> None:
    with pytest.raises(ValueError, match="image"):
        write_trial_report(
            tmp_path / "REPORT.md",
            proposal=101,
            branch="autoresearch/css-distance/run200-proposal-101",
            method="matrix-free randomized aggregate search",
            public_contract_status="failed",
            proposal_image_id=proposal_image_id,
            evaluator_image_id=evaluator_image_id,
            summary=not_run_trial_summary(),
        )
