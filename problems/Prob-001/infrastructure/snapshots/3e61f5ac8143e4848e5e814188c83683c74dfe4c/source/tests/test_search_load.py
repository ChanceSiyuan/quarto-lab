from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError, load_search_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]
M1_TASK_ID = "rotated-memory-z-cdep-v1"
QT_CAMPAIGN_ID = "quantum-tanner-autoresearch"
QT_RUN_ID = "loader-screening"
QT_TASK_ID = "quantum-tanner-css-memory-x-rbposd-p001-v1"
QT_SUITE_ID = "quantum-tanner-rbposd-p001-v1"
QT_DECODER_ID = "rbposd-osd10-v1"


def _copy_search_workspace(tmp_path: Path) -> Path:
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


def _make_example_run_autoresearch(work_root: Path) -> Path:
    run_root = _example_run_root(work_root)
    run_spec_path = run_root / "run_spec.json"
    run_spec = json.loads(run_spec_path.read_text())
    run_spec["mode"] = "autoresearch"
    run_spec["tag"] = run_spec["run_id"]
    run_spec["wall_clock_seconds"] = 90
    run_spec["seed"] = 7
    run_spec_path.write_text(json.dumps(run_spec, indent=2, sort_keys=True) + "\n")
    (run_root / "experiment-log.tsv").write_text(
        "candidate_id\tler\tstatus\tdescription\n"
        "rotated-surface-d3-example\t\tcrash\texample\n"
    )
    (run_root / "run-summary.html").write_text("<!doctype html><title>run</title>\n")
    (run_root / "run_status.json").write_text(
        json.dumps(
            {
                "campaign_id": run_spec["campaign_id"],
                "run_id": run_spec["run_id"],
                "tag": run_spec["tag"],
                "status": "finalized",
                "finalized_at": "2026-06-09T00:00:01Z",
                "candidates_attempted": 1,
                "frontier_size": 0,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return run_root


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _make_quantum_tanner_placeholder_run(work_root: Path) -> Path:
    run_root = work_root / "results" / "search" / QT_CAMPAIGN_ID / QT_RUN_ID
    candidate_id = "quantum-tanner-toric-d4"
    candidate_root = run_root / "candidates" / candidate_id
    created_at = "2026-07-07T00:00:00Z"

    _write_json(
        run_root / "run_spec.json",
        {
            "campaign_id": QT_CAMPAIGN_ID,
            "run_id": QT_RUN_ID,
            "suite_id": QT_SUITE_ID,
            "task_ids": [QT_TASK_ID],
            "decoder_ids": [QT_DECODER_ID],
            "candidate_ids": [candidate_id],
            "created_at": created_at,
            "mode": "placeholder",
        },
    )
    _write_json(run_root / "env.json", {})
    _write_json(run_root / "frontier.json", {"items": []})
    (run_root / "leaderboard.csv").write_text("candidate_id,distance,decoder,p,ler\n")
    (run_root / "summary.md").write_text("# Placeholder\n")

    _write_json(
        candidate_root / "candidate.json",
        {
            "candidate_id": candidate_id,
            "campaign_id": QT_CAMPAIGN_ID,
            "run_id": QT_RUN_ID,
            "code_family": "quantum-tanner-code",
            "parameters": {"distance": 4},
            "provenance": {
                "kind": "distance-ladder-fixture",
                "label": candidate_id,
            },
            "status": "placeholder",
        },
    )
    _write_json(
        candidate_root / "structure.json",
        {"status": "not-computed", "n": None, "mx": None, "mz": None},
    )
    _write_json(
        candidate_root / "distance.json",
        {"status": "not-computed", "distance": None},
    )
    _write_json(
        candidate_root / "evaluations" / QT_TASK_ID / QT_DECODER_ID / "manifest.json",
        {
            "campaign_id": QT_CAMPAIGN_ID,
            "run_id": QT_RUN_ID,
            "candidate_id": candidate_id,
            "task_id": QT_TASK_ID,
            "decoder_id": QT_DECODER_ID,
            "status": "placeholder",
            "metrics": {"logical_error_rate": None},
            "created_at": created_at,
        },
    )
    return run_root


def test_load_search_workspace_collects_campaigns_and_contracts() -> None:
    workspace = load_search_workspace(REPO_ROOT)

    assert sorted(workspace.campaigns) == [
        "bb72-qldpc-campaign",
        "decoder-registry-css-bb-smoke",
        "quantum-tanner-autoresearch",
        "rotated-surface-baseline",
        "rotated-surface-css-fixture",
        "rotated-surface-strategy-fixture",
    ]
    assert sorted(workspace.search_spaces) == [
        "bb72-qldpc-campaign",
        "decoder-registry-css-bb-smoke",
        "quantum-tanner-autoresearch",
        "rotated-surface-baseline",
        "rotated-surface-css-fixture",
        "rotated-surface-strategy-fixture",
    ]
    assert sorted(workspace.tasks) == [
        "bb-css-memory-x-cdep-v1",
        "quantum-tanner-css-memory-x-rbposd-p001-v1",
        "rotated-memory-x-cdep-v1",
        M1_TASK_ID,
    ]
    assert sorted(workspace.decoders) == [
        "predict-zero-v1",
        "rbposd-bb72-osd1-v1",
        "rbposd-bb72-osd10-v1",
        "rbposd-default-v1",
        "rbposd-osd0-v1",
        "rbposd-osd10-v1",
        "rilpqec-default-v1",
        "rmatching-default-v1",
    ]
    assert sorted(workspace.suites) == [
        "bb72-qldpc-campaign-v1",
        "decoder-registry-css-bb-smoke-v1",
        "quantum-tanner-rbposd-p001-v1",
        "rotated-surface-baseline-v1",
        "rotated-surface-css-fixture-v1",
    ]
    assert (
        workspace.search_spaces["rotated-surface-baseline"]["candidate_specs"][0]["candidate_id"]
        == "rotated-surface-d3-example"
    )


def test_load_search_workspace_rejects_unknown_default_suite(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)

    campaign_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "campaign.json"
    )
    payload = json.loads(campaign_path.read_text())
    payload["default_suite_id"] = "missing-suite"
    campaign_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="unknown default_suite_id"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_incomplete_layout(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")

    with pytest.raises(SearchIntegrityError, match="missing required directory"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_suite_with_unknown_task(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)

    suite_path = work_root / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json"
    payload = json.loads(suite_path.read_text())
    payload["task_ids"] = ["missing-task"]
    suite_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="unknown task_id"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_suite_with_unknown_decoder(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)

    suite_path = work_root / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json"
    payload = json.loads(suite_path.read_text())
    payload["decoder_ids"] = ["missing-decoder"]
    suite_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="unknown decoder_id"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_task_collection_override_with_unknown_decoder(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_workspace(tmp_path)

    task_path = work_root / "benchmarks" / "tasks" / "bb-css-memory-x-cdep-v1.json"
    payload = json.loads(task_path.read_text())
    payload["collection"]["decoder_overrides"] = {
        "rbposd-osd010-v1": {"max_shots": 1}
    }
    task_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(
        SearchIntegrityError,
        match="unknown decoder_overrides on task bb-css-memory-x-cdep-v1",
    ):
        load_search_workspace(work_root)


@pytest.mark.parametrize(
    ("kind", "match"),
    [
        ("campaign", "duplicate campaign id"),
        ("tasks", "duplicate id in benchmarks/tasks"),
        ("decoders", "duplicate id in benchmarks/decoders"),
        ("suites", "duplicate id in benchmarks/suites"),
    ],
)
def test_load_search_workspace_rejects_duplicate_source_ids(
    tmp_path: Path, kind: str, match: str
) -> None:
    work_root = _copy_search_workspace(tmp_path)

    if kind == "campaign":
        source_dir = work_root / "campaigns" / "examples" / "rotated-surface-baseline"
        duplicate_dir = work_root / "campaigns" / "examples" / "duplicate-campaign"
        shutil.copytree(source_dir, duplicate_dir)
    else:
        source_path = {
            "tasks": work_root / "benchmarks" / "tasks" / f"{M1_TASK_ID}.json",
            "decoders": work_root
            / "benchmarks"
            / "decoders"
            / "rmatching-default-v1.json",
            "suites": work_root
            / "benchmarks"
            / "suites"
            / "rotated-surface-baseline-v1.json",
        }[kind]
        duplicate_path = source_path.with_name(f"duplicate-{source_path.name}")
        duplicate_path.write_text(source_path.read_text())

    with pytest.raises(SearchIntegrityError, match=match):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_duplicate_candidate_ids_in_search_space(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_workspace(tmp_path)

    search_space_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "search_space.json"
    )
    payload = json.loads(search_space_path.read_text())
    payload["candidate_specs"].append(
        {
            "candidate_id": "rotated-surface-d3-example",
            "code_family": "rotated-surface-code",
            "parameters": {
                "distance": 5,
                "layout": "rotated",
            },
            "provenance": {
                "kind": "seed",
                "label": "duplicate-example",
            },
        }
    )
    search_space_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="duplicate candidate_id in search space"):
        load_search_workspace(work_root)


def test_load_search_workspace_collects_example_run() -> None:
    workspace = load_search_workspace(REPO_ROOT)

    expected_runs = {
        "decoder-registry-css-bb-smoke/issue16-bb-css-validation",
        "rotated-surface-baseline/2026-06-09-example",
        "rotated-surface-baseline/m1-demo",
    }
    assert expected_runs <= set(workspace.runs)
    loaded_run = workspace.runs["rotated-surface-baseline/2026-06-09-example"]
    assert loaded_run.payload["suite_id"] == "rotated-surface-baseline-v1"
    assert sorted(loaded_run.candidates) == ["rotated-surface-d3-example"]


def test_load_search_workspace_rejects_candidate_directory_mismatch(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)

    candidate_path = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
        / "candidates"
        / "rotated-surface-d3-example"
        / "candidate.json"
    )
    payload = json.loads(candidate_path.read_text())
    payload["candidate_id"] = "mismatched-candidate-id"
    candidate_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="candidate_id mismatch"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_manifest_task_mismatch(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)

    manifest_path = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
        / "candidates"
        / "rotated-surface-d3-example"
        / "evaluations"
        / M1_TASK_ID
        / "rmatching-default-v1"
        / "manifest.json"
    )
    payload = json.loads(manifest_path.read_text())
    payload["task_id"] = "wrong-task-id"
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="manifest task_id mismatch"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_quantum_tanner_run_missing_screening(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_workspace(tmp_path)
    _make_quantum_tanner_placeholder_run(work_root)

    with pytest.raises(
        SearchIntegrityError,
        match="missing quantum Tanner screening artifact",
    ):
        load_search_workspace(work_root)


def test_load_search_workspace_accepts_quantum_tanner_run_screening_artifacts(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_workspace(tmp_path)
    run_root = _make_quantum_tanner_placeholder_run(work_root)
    candidate_id = "quantum-tanner-toric-d4"
    _write_json(
        run_root / "candidates" / candidate_id / "screening.json",
        {
            "screening_status": "skipped",
            "distance_bound_type": "upper",
            "distance_upper_bound": None,
            "reason": "missing_upper_bound_payload",
        },
    )

    workspace = load_search_workspace(work_root)

    assert f"{QT_CAMPAIGN_ID}/{QT_RUN_ID}" in workspace.runs


def test_load_search_workspace_rejects_admitted_quantum_tanner_placeholder(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_workspace(tmp_path)
    run_root = _make_quantum_tanner_placeholder_run(work_root)
    candidate_id = "quantum-tanner-toric-d4"
    _write_json(
        run_root / "candidates" / candidate_id / "screening.json",
        {
            "screening_status": "admitted",
            "distance_bound_type": "upper",
            "distance_upper_bound": 4,
            "reason": "verified_upper_bound_witness",
        },
    )

    with pytest.raises(
        SearchIntegrityError,
        match="admitted quantum Tanner screening requires completed manifest",
    ):
        load_search_workspace(work_root)


def test_load_search_workspace_accepts_autoresearch_notebook_metadata(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_workspace(tmp_path)
    _make_example_run_autoresearch(work_root)

    workspace = load_search_workspace(work_root)

    loaded_run = workspace.runs["rotated-surface-baseline/2026-06-09-example"]
    assert loaded_run.payload["mode"] == "autoresearch"
    assert loaded_run.payload["tag"] == "2026-06-09-example"


def test_load_search_workspace_rejects_autoresearch_missing_run_status(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_workspace(tmp_path)
    run_root = _make_example_run_autoresearch(work_root)
    (run_root / "run_status.json").unlink()

    with pytest.raises(SearchIntegrityError, match="run status artifact"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_autoresearch_run_status_mismatch(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_workspace(tmp_path)
    run_root = _make_example_run_autoresearch(work_root)
    run_status_path = run_root / "run_status.json"
    run_status = json.loads(run_status_path.read_text())
    run_status["run_id"] = "wrong-run"
    run_status_path.write_text(json.dumps(run_status, indent=2, sort_keys=True) + "\n")

    with pytest.raises(SearchIntegrityError, match="run_status run_id mismatch"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_autoresearch_missing_run_spec_fields(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_workspace(tmp_path)
    run_root = _make_example_run_autoresearch(work_root)
    run_spec_path = run_root / "run_spec.json"
    run_spec = json.loads(run_spec_path.read_text())
    del run_spec["tag"]
    run_spec_path.write_text(json.dumps(run_spec, indent=2, sort_keys=True) + "\n")

    with pytest.raises(SearchIntegrityError, match="autoresearch run missing tag"):
        load_search_workspace(work_root)


def test_search_space_accepts_strategy_config(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)
    search_space_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "search_space.json"
    )
    payload = json.loads(search_space_path.read_text())
    payload["strategy"] = {"name": "adaptive", "params": {}}
    search_space_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    workspace = load_search_workspace(work_root)

    assert workspace.search_spaces["rotated-surface-baseline"]["strategy"] == {
        "name": "adaptive",
        "params": {},
    }


def test_search_space_rejects_unknown_strategy_name(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)
    search_space_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "search_space.json"
    )
    payload = json.loads(search_space_path.read_text())
    payload["strategy"] = {"name": "mystery", "params": {}}
    search_space_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    with pytest.raises(Exception, match="mystery"):
        load_search_workspace(work_root)


def test_candidate_provenance_accepts_strategy_field(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)
    candidate_path = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
        / "candidates"
        / "rotated-surface-d3-example"
        / "candidate.json"
    )
    payload = json.loads(candidate_path.read_text())
    payload["provenance"]["strategy"] = "grid"
    candidate_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    workspace = load_search_workspace(work_root)

    loaded = workspace.runs[
        "rotated-surface-baseline/2026-06-09-example"
    ].candidates["rotated-surface-d3-example"]
    assert loaded.payload["provenance"]["strategy"] == "grid"


def test_new_autoresearch_run_status_requires_stop_reason(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)
    run_root = _make_example_run_autoresearch(work_root)
    run_spec_path = run_root / "run_spec.json"
    run_spec = json.loads(run_spec_path.read_text())
    run_spec["strategy"] = {"name": "grid", "params": {}}
    run_spec_path.write_text(json.dumps(run_spec, indent=2, sort_keys=True) + "\n")
    strategy_trace = {
        "campaign_id": run_spec["campaign_id"],
        "run_id": run_spec["run_id"],
        "strategy": {"name": "grid", "params": {}},
        "events": [],
    }
    (run_root / "strategy_trace.json").write_text(
        json.dumps(strategy_trace, indent=2, sort_keys=True) + "\n"
    )

    with pytest.raises(SearchIntegrityError, match="stop_reason"):
        load_search_workspace(work_root)
