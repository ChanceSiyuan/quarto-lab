from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_search_tree(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    return work_root


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_init_run_creates_placeholder_run(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "init-run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--run-id",
            "tmp-run",
            "--timestamp",
            "2026-06-09T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr

    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "tmp-run"
    assert sorted(path.name for path in run_root.iterdir()) == [
        "candidates",
        "env.json",
        "frontier.json",
        "leaderboard.csv",
        "run_spec.json",
        "summary.md",
    ]

    run_spec = _load_json(run_root / "run_spec.json")
    assert run_spec["campaign_id"] == "rotated-surface-baseline"
    assert run_spec["suite_id"] == "rotated-surface-baseline-v1"
    assert run_spec["candidate_ids"] == [
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
    ]
    assert run_spec["decoder_ids"] == [
        "rmatching-default-v1",
        "rbposd-default-v1",
        "rbposd-osd0-v1",
        "rbposd-osd10-v1",
        "rilpqec-default-v1",
    ]

    for candidate_id in run_spec["candidate_ids"]:
        for decoder_id in run_spec["decoder_ids"]:
            manifest = _load_json(
                run_root
                / "candidates"
                / candidate_id
                / "evaluations"
                / "rotated-memory-z-cdep-v1"
                / decoder_id
                / "manifest.json"
            )
            assert manifest["status"] == "placeholder"
            assert manifest["metrics"] == {"logical_error_rate": None}


def test_init_run_rejects_existing_run_without_force(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    first = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "init-run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--run-id",
            "tmp-run",
            "--timestamp",
            "2026-06-09T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert first.returncode == 0, first.stderr

    second = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "init-run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--run-id",
            "tmp-run",
            "--timestamp",
            "2026-06-09T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert second.returncode == 1
    assert "run already exists" in second.stderr


def test_init_run_rejects_nested_run_id(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "init-run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--run-id",
            "bad/nested",
            "--timestamp",
            "2026-06-09T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "run_id must be a single path segment" in result.stderr


def test_init_run_rejects_duplicate_candidate_ids(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    search_space_path = (
        work_root
        / "campaigns"
        / "examples"
        / "rotated-surface-baseline"
        / "search_space.json"
    )
    payload = _load_json(search_space_path)
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

    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "init-run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--run-id",
            "tmp-run",
            "--timestamp",
            "2026-06-09T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "duplicate candidate_id in search space" in result.stderr


def test_init_run_rejects_invalid_timestamp_without_writing_run(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "init-run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--run-id",
            "tmp-run",
            "--timestamp",
            "not-a-timestamp",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "invalid timestamp" in result.stderr
    assert not (
        work_root / "results" / "search" / "rotated-surface-baseline" / "tmp-run"
    ).exists()
