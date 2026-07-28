from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import autoqec_search.cli as search_cli


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("timeout_value", ["0", "-1", "301"])
def test_prepare_css_distance_algorithm_rejects_invalid_timeout_before_creation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    timeout_value: str,
) -> None:
    creation_calls: list[object] = []
    monkeypatch.setattr(
        search_cli,
        "create_css_distance_algorithm_worktree",
        lambda *args, **kwargs: creation_calls.append((args, kwargs)),
    )

    result = search_cli.main(
        [
            "prepare-css-distance-algorithm",
            "--root",
            str(tmp_path),
            "--algorithm-id",
            "candidate-a",
            "--created-at",
            "2026-07-21T00:00:00Z",
            "--timeout-seconds",
            timeout_value,
        ]
    )

    stderr = capsys.readouterr().err
    assert result == 1
    assert "error:" in stderr
    assert "timeout" in stderr
    assert "Traceback" not in stderr
    assert creation_calls == []


@pytest.mark.parametrize("timeout_value", ["0", "-1", "301", "nan", "inf"])
def test_run_css_distance_candidate_rejects_invalid_timeout_before_preflight(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    timeout_value: str,
) -> None:
    preflight_calls: list[object] = []
    monkeypatch.setattr(
        search_cli,
        "require_docker_preflight",
        lambda image: preflight_calls.append(image),
    )

    result = search_cli.main(
        [
            "run-css-distance-candidate",
            "--algorithm-id",
            "candidate-a",
            "--candidate-worktree",
            str(tmp_path / "candidate"),
            "--work-root",
            str(tmp_path / "work"),
            "--image",
            "evaluator:test",
            "--baseline",
            "baseline",
            "--timeout-seconds",
            timeout_value,
        ]
    )

    stderr = capsys.readouterr().err
    assert result == 1
    assert "error:" in stderr
    assert "timeout" in stderr
    assert "Traceback" not in stderr
    assert preflight_calls == []


def test_prepare_css_distance_paper_suite_cli_reports_safe_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_prepare(**kwargs):
        calls.append(kwargs)
        return {"counts": {"development": 24, "final": 12}}

    monkeypatch.setattr(search_cli, "prepare_blind_suite", fake_prepare)

    result = search_cli.main(
        [
            "prepare-css-distance-paper-suite",
            "--root",
            str(tmp_path),
            "--source-pool",
            "pool.json",
            "--work-root",
            str(tmp_path / "operator-private-marker"),
            "--commitment-out",
            str(tmp_path / "commitment.json"),
            "--created-at",
            "2026-07-21T00:00:00Z",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out == "prepared blinded CSS-distance paper suite development=24 final=12\n"
    assert captured.err == ""
    assert "operator-private-marker" not in captured.out
    assert calls == [
        {
            "root": tmp_path,
            "source_pool_path": Path("pool.json"),
            "work_root": tmp_path / "operator-private-marker",
            "commitment_path": tmp_path / "commitment.json",
            "created_at": "2026-07-21T00:00:00Z",
        }
    ]


def test_validate_css_distance_paper_suite_cli_reports_safe_status(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commitment_path = tmp_path / "commitment.json"
    commitment_path.write_text(json.dumps({"schema_version": 1}) + "\n")
    load_calls: list[dict] = []
    verify_calls: list[dict] = []

    def fake_load_source_pool(**kwargs):
        load_calls.append(kwargs)
        return ()

    def fake_verify(**kwargs):
        verify_calls.append(kwargs)
        return {"status": "pass", "development": 24, "final": 12}

    monkeypatch.setattr(search_cli, "load_and_validate_source_pool", fake_load_source_pool)
    monkeypatch.setattr(search_cli, "verify_suite_commitment", fake_verify)

    result = search_cli.main(
        [
            "validate-css-distance-paper-suite",
            "--root",
            str(tmp_path),
            "--source-pool",
            "pool.json",
            "--work-root",
            str(tmp_path / "operator-private-marker"),
            "--commitment",
            str(commitment_path),
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out == (
        "status=pass development=24 final=12 "
        "time_limit_seconds=300 minimum_seeds=20\n"
    )
    assert captured.err == ""
    assert "operator-private-marker" not in captured.out
    assert load_calls == [{"root": tmp_path, "path": Path("pool.json")}]
    assert verify_calls == [
        {
            "private_root": tmp_path
            / "operator-private-marker"
            / "private"
            / "css-distance-paper-suite",
            "commitment": {"schema_version": 1},
        }
    ]


def test_freeze_css_distance_paper_candidate_cli_writes_safe_record(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method_config = tmp_path / "method.json"
    seeds = tmp_path / "seeds.json"
    development_summary = tmp_path / "development-summary.json"
    commitment = tmp_path / "commitment.json"
    out = tmp_path / "freeze.json"
    for path, payload in [
        (method_config, {"method": "quotient-coset-upper-bound"}),
        (seeds, {"seeds": [104729 + index for index in range(20)]}),
        (development_summary, {"runs": 480}),
        (commitment, {"schema_version": 1}),
    ]:
        path.write_text(json.dumps(payload, sort_keys=True) + "\n")
    freeze = {
        "schema_version": 1,
        "git_commit": "a" * 40,
        "candidate_sha256": "b" * 64,
        "time_limit_seconds": 300,
    }
    calls: list[dict] = []

    def fake_freeze(**kwargs):
        calls.append(kwargs)
        return freeze

    monkeypatch.setattr(search_cli, "create_candidate_freeze", fake_freeze)

    result = search_cli.main(
        [
            "freeze-css-distance-paper-candidate",
            "--candidate-worktree",
            str(tmp_path / "candidate-private-marker"),
            "--candidate",
            "candidate.py",
            "--image-digest",
            "sha256:" + "1" * 64,
            "--method-config",
            str(method_config),
            "--seeds",
            str(seeds),
            "--development-summary",
            str(development_summary),
            "--commitment",
            str(commitment),
            "--out",
            str(out),
            "--created-at",
            "2026-07-21T00:00:00Z",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert json.loads(out.read_text()) == freeze
    assert captured.out == "froze CSS-distance paper candidate time_limit_seconds=300\n"
    assert captured.err == ""
    assert "candidate-private-marker" not in captured.out
    assert calls == [
        {
            "candidate_worktree": tmp_path / "candidate-private-marker",
            "candidate_path": Path("candidate.py"),
            "image_digest": "sha256:" + "1" * 64,
            "method_config": {"method": "quotient-coset-upper-bound"},
            "seed_manifest": {"seeds": [104729 + index for index in range(20)]},
            "development_summary": {"runs": 480},
            "suite_commitment": {"schema_version": 1},
            "created_at": "2026-07-21T00:00:00Z",
        }
    ]


def test_validate_rejects_missing_repo_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-repo"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate",
            "--root",
            str(missing_root),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2
    assert "repository root does not exist" in result.stderr


def test_validate_command_reports_workspace_counts() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate",
            "--root",
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "validated search workspace under" in result.stdout
    assert "6 campaigns" in result.stdout
    assert "5 suites" in result.stdout
    assert "4 runs" in result.stdout


def test_validate_reports_missing_schema_file_as_clean_error(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    (work_root / "benchmarks" / "schemas" / "campaign.schema.json").unlink()

    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate",
            "--root",
            str(work_root),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "error:" in result.stderr
    assert "campaign.schema.json" in result.stderr


def test_validate_rejects_corrupted_copied_baseline_row(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")

    baseline_path = (
        work_root
        / "benchmarks"
        / "baselines"
        / "rotated-surface-single-logical-p001.json"
    )
    baseline = json.loads(baseline_path.read_text())
    baseline["rows"][0]["logical_qubits"] = 2
    baseline_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")

    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate",
            "--root",
            str(work_root),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "surface single-logical baseline row 0 logical_qubits must equal 1" in result.stderr


def test_show_prints_example_run_summary() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    run_root = (
        REPO_ROOT
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "show",
            "--run",
            str(run_root),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "campaign: rotated-surface-baseline" in result.stdout
    assert "run: 2026-06-09-example" in result.stdout
    assert "candidates: 1" in result.stdout
    assert "placeholder manifests: 3" in result.stdout


def test_show_ignores_unrelated_broken_sibling_run(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")

    broken_run_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "bad-run"
    )
    broken_run_root.mkdir(parents=True)
    shutil.copyfile(
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
        / "run_spec.json",
        broken_run_root / "run_spec.json",
    )

    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    run_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "show",
            "--run",
            str(run_root),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=work_root,
    )

    assert result.returncode == 0, result.stderr
    assert "campaign: rotated-surface-baseline" in result.stdout
    assert "run: 2026-06-09-example" in result.stdout
    assert "candidates: 1" in result.stdout
    assert "placeholder manifests: 3" in result.stdout


def test_validate_rejects_real_decoder_without_impl_key(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")

    decoder_path = work_root / "benchmarks" / "decoders" / "rmatching-default-v1.json"
    decoder = json.loads(decoder_path.read_text())
    decoder.pop("impl_key")
    decoder_path.write_text(json.dumps(decoder, indent=2) + "\n")

    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate",
            "--root",
            str(work_root),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "impl_key" in result.stderr


def test_compare_candidates_help_is_available() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "compare-candidates",
            "--help",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "Compare completed candidate points across two or more search runs" in result.stdout


UPPER_BOUND_FIXTURE_ROOT = REPO_ROOT / "benchmarks" / "fixtures" / "upper-bound-witness"
QEC_CODE_FIXTURE_ROOT = UPPER_BOUND_FIXTURE_ROOT / "qec-code"


def _write_fake_qec_code(path: Path) -> Path:
    script = """#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import sys
import time

sleep_seconds = os.environ.get("AUTOQEC_FAKE_QEC_CODE_SLEEP")
if sleep_seconds:
    time.sleep(float(sleep_seconds))

stderr_text = os.environ.get("AUTOQEC_FAKE_QEC_CODE_STDERR", "")
if stderr_text:
    sys.stderr.write(stderr_text)

stdout_text = os.environ.get("AUTOQEC_FAKE_QEC_CODE_STDOUT")
payload_path = os.environ.get("AUTOQEC_FAKE_QEC_CODE_PAYLOAD")
if stdout_text is not None:
    sys.stdout.write(stdout_text)
elif payload_path:
    sys.stdout.write(Path(payload_path).read_text())

sys.exit(int(os.environ.get("AUTOQEC_FAKE_QEC_CODE_EXIT", "0")))
"""
    path.write_text(script)
    path.chmod(0o755)
    return path


def test_find_upper_bound_witness_writes_verified_x_witness(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    witness_path = tmp_path / "found-witness.json"
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json"),
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "find-upper-bound-witness",
            "--hx",
            str(UPPER_BOUND_FIXTURE_ROOT / "hx.json"),
            "--hz",
            str(UPPER_BOUND_FIXTURE_ROOT / "hz.json"),
            "--basis",
            "x",
            "--out",
            str(witness_path),
            "--qec-code-bin",
            str(fake_qec_code),
            "--iterations",
            "16",
            "--restarts",
            "3",
            "--seed",
            "61",
            "--timeout-seconds",
            "5",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(witness_path.read_text()) == {
        "basis": "x",
        "vector": [0, 0, 1, 1],
    }
    assert "basis=x" in result.stdout
    assert "weight=2" in result.stdout
    assert "method=css-upper-bound-witness" in result.stdout
    assert str(witness_path) in result.stdout
    provenance = json.loads((tmp_path / "found-witness.json.provenance.json").read_text())
    assert provenance["basis_requested"] == "x"
    assert provenance["distance_payload"]["upper_bound"] == 2
    assert provenance["qec_code_result"]["method"] == "random-window-upper-bound"

    verify_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "verify-witness",
            "--hx",
            str(UPPER_BOUND_FIXTURE_ROOT / "hx.json"),
            "--hz",
            str(UPPER_BOUND_FIXTURE_ROOT / "hz.json"),
            "--witness",
            str(witness_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert verify_result.returncode == 0, verify_result.stderr


def test_find_upper_bound_witness_rejects_incompatible_basis_without_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    witness_path = tmp_path / "found-witness.json"
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-z-completed.json"),
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "find-upper-bound-witness",
            "--hx",
            str(UPPER_BOUND_FIXTURE_ROOT / "hx.json"),
            "--hz",
            str(UPPER_BOUND_FIXTURE_ROOT / "hz.json"),
            "--basis",
            "x",
            "--out",
            str(witness_path),
            "--qec-code-bin",
            str(fake_qec_code),
            "--iterations",
            "16",
            "--restarts",
            "3",
            "--seed",
            "61",
            "--timeout-seconds",
            "5",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "incompatible witness basis" in result.stderr
    assert not witness_path.exists()
    assert not (tmp_path / "found-witness.json.provenance.json").exists()


def test_find_upper_bound_witness_timeout_leaves_no_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    witness_path = tmp_path / "found-witness.json"
    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_SLEEP", "2")
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json"),
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "find-upper-bound-witness",
            "--hx",
            str(UPPER_BOUND_FIXTURE_ROOT / "hx.json"),
            "--hz",
            str(UPPER_BOUND_FIXTURE_ROOT / "hz.json"),
            "--basis",
            "x",
            "--out",
            str(witness_path),
            "--qec-code-bin",
            str(fake_qec_code),
            "--iterations",
            "16",
            "--restarts",
            "3",
            "--seed",
            "61",
            "--timeout-seconds",
            "0.1",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "timed out" in result.stderr
    assert not witness_path.exists()
    assert not (tmp_path / "found-witness.json.provenance.json").exists()


def test_find_upper_bound_witness_rejects_aliasing_provenance_out(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    witness_path = tmp_path / "found-witness.json"
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json"),
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "find-upper-bound-witness",
            "--hx",
            str(UPPER_BOUND_FIXTURE_ROOT / "hx.json"),
            "--hz",
            str(UPPER_BOUND_FIXTURE_ROOT / "hz.json"),
            "--basis",
            "x",
            "--out",
            str(witness_path),
            "--provenance-out",
            str(witness_path),
            "--qec-code-bin",
            str(fake_qec_code),
            "--iterations",
            "16",
            "--restarts",
            "3",
            "--seed",
            "61",
            "--timeout-seconds",
            "5",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "provenance" in result.stderr
    assert "distinct" in result.stderr or "collision" in result.stderr
    assert not witness_path.exists()


def test_find_upper_bound_witness_rejects_directory_provenance_out_before_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    witness_path = tmp_path / "found-witness.json"
    provenance_path = tmp_path / "provenance-dir"
    provenance_path.mkdir()
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json"),
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "find-upper-bound-witness",
            "--hx",
            str(UPPER_BOUND_FIXTURE_ROOT / "hx.json"),
            "--hz",
            str(UPPER_BOUND_FIXTURE_ROOT / "hz.json"),
            "--basis",
            "x",
            "--out",
            str(witness_path),
            "--provenance-out",
            str(provenance_path),
            "--qec-code-bin",
            str(fake_qec_code),
            "--iterations",
            "16",
            "--restarts",
            "3",
            "--seed",
            "61",
            "--timeout-seconds",
            "5",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "provenance" in result.stderr
    assert "directory" in result.stderr
    assert not witness_path.exists()
