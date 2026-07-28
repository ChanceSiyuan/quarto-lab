from __future__ import annotations

import json
import os
import shutil
import stat
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


def _env_with_fake_rsinter(
    tmp_path: Path, version: str = "rsinter git main abc123"
) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rsinter = bin_dir / "rsinter"
    rsinter.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n")
    rsinter.chmod(rsinter.stat().st_mode | stat.S_IXUSR)
    return {
        **os.environ,
        "PATH": str(bin_dir),
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }


def _run_preflight(
    root: Path,
    env: dict[str, str],
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "preflight",
            "--root",
            str(root),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def test_preflight_passes_with_valid_contracts_fixture_and_backend(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    result = _run_preflight(work_root, _env_with_fake_rsinter(tmp_path))

    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS" in result.stdout
    assert "FAIL" not in result.stdout
    assert "workspace contracts" in result.stdout
    assert "rsinter available" in result.stdout
    assert "fixture rotated-d3" in result.stdout


def test_rotated_d3_fixture_uses_current_rsinter_row_shape() -> None:
    results_path = REPO_ROOT / "benchmarks" / "fixtures" / "rotated-d3" / "results.jsonl"
    record = json.loads(results_path.read_text().splitlines()[0])

    assert record["benchmark"] == "autoqec-rotated-memory-x-cdep-v1"
    assert record["runner"] == "rmatching-default-v1"
    assert record["status"] == "ok"
    assert record["params"]["distance"] == 3
    assert record["params"]["p"] == 0.005
    assert record["metrics"]["shots_used"] == 76533.0
    assert record["metrics"]["logical_errors"] == 1000.0
    assert "fixture_id" not in record
    assert "logical_error_rate" not in record


def test_preflight_fails_when_rsinter_is_missing(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    env = {
        **os.environ,
        "PATH": str(empty_bin),
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }

    result = _run_preflight(work_root, env)

    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "rsinter available" in result.stdout


def test_preflight_writes_self_contained_html(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    html_path = tmp_path / "doctor.html"

    result = _run_preflight(
        work_root,
        _env_with_fake_rsinter(tmp_path),
        "--html",
        str(html_path),
    )

    assert result.returncode == 0, result.stderr + result.stdout
    html = html_path.read_text()
    assert "<!doctype html>" in html
    assert "fixture rotated-d3" in html
    assert "PASS" in html


def test_preflight_fails_when_fixture_errors_exceed_shots(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    results_path = work_root / "benchmarks" / "fixtures" / "rotated-d3" / "results.jsonl"
    record = json.loads(results_path.read_text().splitlines()[0])
    record["metrics"]["logical_errors"] = record["metrics"]["shots_used"] + 1
    results_path.write_text(json.dumps(record, sort_keys=True) + "\n")

    result = _run_preflight(work_root, _env_with_fake_rsinter(tmp_path))

    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "fixture rotated-d3" in result.stdout
    assert "errors exceed shots" in result.stdout


def test_preflight_fails_when_fixture_p_is_non_finite(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    results_path = work_root / "benchmarks" / "fixtures" / "rotated-d3" / "results.jsonl"
    record = json.loads(results_path.read_text().splitlines()[0])
    record["params"]["p"] = float("nan")
    results_path.write_text(json.dumps(record, sort_keys=True) + "\n")

    result = _run_preflight(work_root, _env_with_fake_rsinter(tmp_path))

    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "fixture rotated-d3" in result.stdout
    assert "invalid p" in result.stdout
