from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from autoqec_search.cli import main
from autoqec_search.report import build_report_model
from autoqec_search.run_loop import run_autoresearch


REPO_ROOT = Path(__file__).resolve().parents[1]
QT_CAMPAIGN_ID = "quantum-tanner-autoresearch"
QT_RUN_ID = "qt-gate"
QT_TASK_ID = "quantum-tanner-css-memory-x-rbposd-p001-v1"
QT_SUITE_ID = "quantum-tanner-rbposd-p001-v1"
QT_DECODER_ID = "rbposd-osd10-v1"
QT_D4_Z_WITNESS_PATH = (
    "campaigns/examples/quantum-tanner-autoresearch/witnesses/"
    "quantum-tanner-toric-d4-z-upper-bound-witness.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _copy_repo(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"

    def ignore(_directory: str, names: list[str]) -> set[str]:
        ignored = {".git", ".worktrees", "__pycache__", ".pytest_cache", ".mypy_cache"}
        ignored.update(name for name in names if name.endswith(".pyc"))
        return ignored & set(names)

    shutil.copytree(REPO_ROOT, work_root, ignore=ignore)
    subprocess.run(
        ["git", "init"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "autoqec@example.com"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "AutoQEC"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return work_root


def _search_space_path(work_root: Path) -> Path:
    return work_root / "campaigns" / "examples" / QT_CAMPAIGN_ID / "search_space.json"


def _replace_search_space_candidates(work_root: Path, candidate_specs: list[dict]) -> None:
    search_space_path = _search_space_path(work_root)
    search_space = _load_json(search_space_path)
    search_space["candidate_specs"] = candidate_specs
    _write_json(search_space_path, search_space)
    subprocess.run(
        ["git", "add", str(search_space_path.relative_to(work_root))],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "test search space"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _qt_d4_search_candidate(**extra: object) -> dict:
    candidate = {
        "candidate_id": "quantum-tanner-toric-d4",
        "code_family": "quantum-tanner-code",
        "fixture_catalog_path": (
            "campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json"
        ),
        "provenance": {
            "kind": "distance-ladder-fixture",
            "label": "quantum-tanner-toric-d4",
        },
    }
    candidate.update(extra)
    return candidate


def _qt_d4_observables_x_path(work_root: Path) -> Path:
    return (
        work_root
        / "benchmarks"
        / "distance_ladders"
        / "surface-toric-bb-kasai-tanner-v2"
        / "instances"
        / "quantum-tanner-toric-d4"
        / "observables_x.json"
    )


def _write_fake_rsinter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import json
import os
import sys
from pathlib import Path
import tomllib

if sys.argv[1:] == ["--version"]:
    print("rsinter git main abc123")
    raise SystemExit(0)

args = sys.argv[1:]
if args[:2] != ["bench", "run"] or "--spec" not in args or "--out" not in args:
    raise SystemExit(2)

spec_path = Path(args[args.index("--spec") + 1])
out_dir = Path(args[args.index("--out") + 1])
spec_log = Path(os.environ["FAKE_RSINTER_SPEC_LOG"])
spec_log.parent.mkdir(parents=True, exist_ok=True)
with spec_log.open("a") as handle:
    handle.write(str(spec_path) + "\\n")

spec = tomllib.loads(spec_path.read_text())
for runner in spec.get("runner", []):
    params = dict(runner["params"])
    p_values = params.get("p")
    if p_values != [0.001]:
        raise SystemExit(f"unexpected p sweep: {{p_values!r}}")
    if len(p_values) != 1:
        raise SystemExit(f"expected exactly one p value: {{p_values!r}}")

    row_params = dict(params)
    row_params["p"] = 0.001
    observable_count = 0
    if "observables" in row_params:
        observables_path = spec_path.parent / row_params["observables"]
        observables = json.loads(observables_path.read_text())
        observable_count = len(observables["rows"])
        if observable_count != 2:
            raise SystemExit(f"expected two explicit observables, got {{observable_count}}")
        row_params.update(
            {{
                "logical_failure_aggregation": "any_logical",
                "logical_observable_basis": "x",
                "logical_observable_count": observable_count,
                "logical_observable_source": "explicit",
                "seed": 12345,
            }}
        )

    results_dir = out_dir / runner["name"] / "test-run"
    results_dir.mkdir(parents=True, exist_ok=True)
    record = {{
        "benchmark": spec["name"],
        "runner": runner["name"],
        "language": runner["language"],
        "status": "ok",
        "params": row_params,
        "case_summary": {{
            "num_dets": 8,
            "num_obs": observable_count,
            "num_shots_generated": 1000,
            "logical_observable_count": observable_count,
        }},
        "metrics": {{
            "shots_used": 1000,
            "logical_errors": 1,
            "logical_error_rate": 0.001,
            "decode_us_per_shot": 10.0,
        }},
        "artifacts": {{}},
        "error": None,
    }}
    (results_dir / "results.jsonl").write_text(json.dumps(record, sort_keys=True) + "\\n")
raise SystemExit(0)
"""
    )
    executable.chmod(0o755)
    return bin_dir


def _run_env(bin_dir: Path, spec_log: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "FAKE_RSINTER_SPEC_LOG": str(spec_log),
    }


def _run_quantum_tanner_autoresearch(
    work_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    bin_dir = _write_fake_rsinter(tmp_path)
    spec_log = tmp_path / "rsinter-specs.log"
    env = _run_env(bin_dir, spec_log)
    monkeypatch.setenv("PATH", env["PATH"])
    monkeypatch.setenv("PYTHONPATH", env["PYTHONPATH"])
    monkeypatch.setenv("FAKE_RSINTER_SPEC_LOG", env["FAKE_RSINTER_SPEC_LOG"])

    run_root = run_autoresearch(
        work_root,
        campaign_id=QT_CAMPAIGN_ID,
        wall_clock="90s",
        seed=None,
        run_id=QT_RUN_ID,
        resume=False,
        cleanup_worktree=False,
        allow_dirty_root=False,
    )
    return run_root, spec_log


def _screening_path(run_root: Path, candidate_id: str) -> Path:
    return run_root / "candidates" / candidate_id / "screening.json"


def _report_candidate(report: dict, candidate_id: str) -> dict:
    for candidate in report["candidates"]:
        if candidate["candidate_id"] == candidate_id:
            return candidate
    raise AssertionError(f"missing report candidate: {candidate_id}")


def test_quantum_tanner_autoresearch_admits_d4_and_writes_screening_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = _copy_repo(tmp_path)
    run_root, spec_log = _run_quantum_tanner_autoresearch(work_root, tmp_path, monkeypatch)

    d4_screening = _load_json(_screening_path(run_root, "quantum-tanner-toric-d4"))
    assert d4_screening == {
        "screening_status": "admitted",
        "distance_bound_type": "upper",
        "distance_upper_bound": 4,
        "reason": "verified_upper_bound_witness",
    }

    spec_path = run_root / "candidates" / "quantum-tanner-toric-d4" / "rsinter" / "spec.toml"
    assert spec_log.read_text().splitlines() == [str(spec_path)]
    results = json.loads(
        (
            run_root
            / "candidates"
            / "quantum-tanner-toric-d4"
            / "rsinter"
            / "out"
            / QT_DECODER_ID
            / "test-run"
            / "results.jsonl"
        )
        .read_text()
        .strip()
    )
    assert results["params"]["p"] == 0.001
    assert results["params"]["logical_failure_aggregation"] == "any_logical"
    observables = _load_json(
        run_root
        / "candidates"
        / "quantum-tanner-toric-d4"
        / "rsinter"
        / "input"
        / "observables.css.json"
    )
    assert len(observables["rows"]) == 2

    report = build_report_model(work_root, run_root)
    assert _report_candidate(report, "quantum-tanner-toric-d4")["screening"] == d4_screening


def test_quantum_tanner_autoresearch_records_any_logical_aggregation_for_d4(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = _copy_repo(tmp_path)
    run_root, _spec_log = _run_quantum_tanner_autoresearch(work_root, tmp_path, monkeypatch)

    manifest = _load_json(
        run_root
        / "candidates"
        / "quantum-tanner-toric-d4"
        / "evaluations"
        / QT_TASK_ID
        / QT_DECODER_ID
        / "manifest.json"
    )
    assert manifest["status"] == "completed"
    assert manifest["run_metadata"] == {
        "decoder_impl": "rbposd",
        "logical_failure_aggregation": "any_logical",
        "logical_observable_basis": "x",
        "logical_observable_count": 2,
        "logical_observable_source": "explicit",
        "seed": 12345,
    }

    report = build_report_model(work_root, run_root)
    assert _report_candidate(report, "quantum-tanner-toric-d4")["screening"][
        "reason"
    ] == "verified_upper_bound_witness"


def test_quantum_tanner_autoresearch_skips_d6_with_screening_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = _copy_repo(tmp_path)
    run_root, _spec_log = _run_quantum_tanner_autoresearch(work_root, tmp_path, monkeypatch)

    d6_screening = _load_json(_screening_path(run_root, "quantum-tanner-toric-d6"))
    assert d6_screening == {
        "screening_status": "skipped",
        "distance_bound_type": "upper",
        "distance_upper_bound": None,
        "reason": "missing_upper_bound_payload",
    }

    report = build_report_model(work_root, run_root)
    assert _report_candidate(report, "quantum-tanner-toric-d6")["screening"] == d6_screening
    report_html = (run_root / "report.html").read_text()
    definitions_html = (run_root / "construction-definitions.html").read_text()
    assert "quantum-tanner-toric-d6" in report_html
    assert "[[36,2]]" in report_html
    assert "rsinter not run" in report_html
    assert "Construction metadata unavailable" not in definitions_html


def test_quantum_tanner_autoresearch_rejects_z_witness_without_calling_rsinter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = _copy_repo(tmp_path)
    _replace_search_space_candidates(
        work_root,
        [_qt_d4_search_candidate(upper_bound_witness_path=QT_D4_Z_WITNESS_PATH)],
    )

    run_root, spec_log = _run_quantum_tanner_autoresearch(work_root, tmp_path, monkeypatch)

    screening = _load_json(_screening_path(run_root, "quantum-tanner-toric-d4"))
    assert screening == {
        "screening_status": "failed",
        "distance_bound_type": "upper",
        "distance_upper_bound": None,
        "reason": "incompatible_upper_bound_witness_basis",
    }
    assert not spec_log.exists() or spec_log.read_text() == ""


def test_quantum_tanner_autoresearch_rejects_z_payload_without_calling_rsinter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = _copy_repo(tmp_path)
    _write_json(
        _qt_d4_observables_x_path(work_root),
        {"format": "sparse_rows", "num_cols": 16, "rows": [[0, 1, 8, 12]]},
    )
    subprocess.run(
        [
            "git",
            "add",
            str(_qt_d4_observables_x_path(work_root).relative_to(work_root)),
        ],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "test observables x"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    _replace_search_space_candidates(
        work_root,
        [
            _qt_d4_search_candidate(
                upper_bound_payload={
                    "status": "completed",
                    "method": "css-upper-bound-witness",
                    "bound_type": "upper",
                    "upper_bound": 4,
                    "basis": "z",
                }
            )
        ],
    )

    run_root, spec_log = _run_quantum_tanner_autoresearch(work_root, tmp_path, monkeypatch)

    screening = _load_json(_screening_path(run_root, "quantum-tanner-toric-d4"))
    assert screening == {
        "screening_status": "failed",
        "distance_bound_type": "upper",
        "distance_upper_bound": None,
        "reason": "incompatible_upper_bound_witness_basis",
    }
    assert not spec_log.exists() or spec_log.read_text() == ""


def test_quantum_tanner_autoresearch_fails_d8_without_calling_rsinter_for_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = _copy_repo(tmp_path)
    run_root, spec_log = _run_quantum_tanner_autoresearch(work_root, tmp_path, monkeypatch)

    d8_screening = _load_json(_screening_path(run_root, "quantum-tanner-toric-d8"))
    assert d8_screening == {
        "screening_status": "failed",
        "distance_bound_type": "upper",
        "distance_upper_bound": None,
        "reason": "not_in_kernel",
    }

    spec_path = run_root / "candidates" / "quantum-tanner-toric-d4" / "rsinter" / "spec.toml"
    assert spec_log.read_text().splitlines() == [str(spec_path)]

    report = build_report_model(work_root, run_root)
    assert _report_candidate(report, "quantum-tanner-toric-d8")["screening"] == d8_screening


def test_quantum_tanner_autoresearch_validate_rejects_p001_suite_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = _copy_repo(tmp_path)
    run_root, _spec_log = _run_quantum_tanner_autoresearch(work_root, tmp_path, monkeypatch)

    assert main(["validate", "--root", str(work_root)]) == 0

    suite_path = (
        work_root / "benchmarks" / "suites" / f"{QT_SUITE_ID}.json"
    )
    suite = _load_json(suite_path)
    suite["shared_settings"]["default_p"] = 0.01
    _write_json(suite_path, suite)

    assert main(["validate", "--root", str(work_root)]) != 0
    assert _load_json(
        run_root / "candidates" / "quantum-tanner-toric-d4" / "screening.json"
    ) == {
        "screening_status": "admitted",
        "distance_bound_type": "upper",
        "distance_upper_bound": 4,
        "reason": "verified_upper_bound_witness",
    }
