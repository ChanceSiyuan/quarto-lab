from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError


REPO_ROOT = Path(__file__).resolve().parents[1]
M1_TASK_ID = "rotated-memory-z-cdep-v1"
M1_FIRST_P = 0.008
M1_PROMOTION_P = 0.01
EXPANDED_SURFACE_CANDIDATES = (
    "rotated-surface-d3-example",
    "rotated-surface-d5-example",
    "rotated-surface-d7-example",
)


def _copy_repo(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"

    def ignore(_directory: str, names: list[str]) -> set[str]:
        ignored = {".git", ".worktrees", "__pycache__"}
        ignored.update(name for name in names if name.endswith(".pyc"))
        return ignored & set(names)

    shutil.copytree(REPO_ROOT, work_root, ignore=ignore)
    subprocess.run(
        ["git", "init"], cwd=work_root, check=True, capture_output=True, text=True
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


def _write_fake_rsinter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import json
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
spec = tomllib.loads(spec_path.read_text())
for runner in spec.get("runner", []):
    decoder_id = runner["name"]
    params = runner["params"]
    results_dir = out_dir / decoder_id / "test-run"
    results_dir.mkdir(parents=True, exist_ok=True)
    records = []
    rounds = int(params["rounds"][0])
    distance = int(params["distance"][0])
    errors = 13 if spec_path.parts[-3] == "rotated-surface-d3-example" else 20
    for p in params["p"]:
        p = float(p)
        shots = 1000
        records.append(
            json.dumps(
                {{
                    "benchmark": spec["name"],
                    "runner": decoder_id,
                    "language": runner["language"],
                    "status": "ok",
                    "params": {{
                        "distance": distance,
                        "rounds": rounds,
                        "p": p,
                    }},
                    "case_summary": {{
                        "num_dets": 8,
                        "num_obs": 1,
                        "num_shots_generated": shots,
                    }},
                    "metrics": {{
                        "shots_used": shots,
                        "logical_errors": errors,
                        "logical_error_rate": errors / shots,
                        "decode_us_per_shot": 10.0,
                    }},
                    "artifacts": {{}},
                    "error": None,
                }},
                sort_keys=True,
            )
        )
    (results_dir / "results.jsonl").write_text("\\n".join(records) + "\\n")
raise SystemExit(0)
"""
    )
    executable.chmod(0o755)
    return bin_dir


def _write_failing_rsinter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import sys

if sys.argv[1:] == ["--version"]:
    print("rsinter git main abc123")
    raise SystemExit(0)

print("intentional rsinter failure", file=sys.stderr)
raise SystemExit(7)
"""
    )
    executable.chmod(0o755)
    return bin_dir


def _write_marker_rsinter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import os
import sys
from pathlib import Path

if sys.argv[1:] == ["--version"]:
    print("rsinter git main abc123")
    raise SystemExit(0)

Path(os.environ["RSINTER_BENCH_MARKER"]).write_text("called\\n")
raise SystemExit(9)
"""
    )
    executable.chmod(0o755)
    return bin_dir


def _write_sleeping_rsinter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import sys
import time

if sys.argv[1:] == ["--version"]:
    print("rsinter git main abc123")
    raise SystemExit(0)

time.sleep(30)
"""
    )
    executable.chmod(0o755)
    return bin_dir


def _env(bin_dir: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }


def _run_autoresearch(
    work_root: Path, env: dict[str, str], *extra: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            *extra,
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def _assert_root_clean(work_root: Path) -> None:
    assert (
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=work_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        == ""
    )


def _branch_exists(work_root: Path, branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "branch", "--list", branch],
            cwd=work_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        != ""
    )


def _commit_all(work_root: Path, message: str) -> None:
    subprocess.run(
        ["git", "add", "-A"],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    )


def _write_non_promoting_rules(work_root: Path) -> None:
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.write_text(json.dumps({"min_distance": 5}, indent=2, sort_keys=True) + "\n")
    _commit_all(work_root, "make promote rules non-promoting")


def _assert_lab_notebook(work_root: Path) -> None:
    worktree = work_root / ".worktrees" / "fixed-check"
    run_root = (
        worktree
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "fixed-check"
    )
    assert run_root.is_dir()
    assert (run_root / "run-summary.html").is_file()
    assert (run_root / "report.html").is_file()
    report = (run_root / "report.html").read_text()
    assert "AutoQEC Search Report" in report
    for candidate_id in (
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
    ):
        assert candidate_id in report
        candidate = json.loads(
            (run_root / "candidates" / candidate_id / "candidate.json").read_text()
        )
        assert candidate["provenance"]["strategy"] == "grid"
        assert "_strategy_name" not in candidate
    assert "0.013" in report
    assert "http://" not in report
    assert "https://" not in report
    run_status = json.loads((run_root / "run_status.json").read_text())
    assert run_status["status"] == "finalized"
    assert run_status["run_id"] == "fixed-check"
    assert isinstance(run_status["finalized_at"], str)
    assert run_status["stop_reason"] in {
        "completed",
        "max-candidates",
        "search-space-exhausted",
        "wall-clock",
    }

    run_spec = json.loads((run_root / "run_spec.json").read_text())
    assert run_spec["strategy"] == {"name": "grid", "params": {}}
    strategy_trace = json.loads((run_root / "strategy_trace.json").read_text())
    assert strategy_trace["campaign_id"] == "rotated-surface-baseline"
    assert strategy_trace["run_id"] == "fixed-check"
    assert strategy_trace["strategy"] == {"name": "grid", "params": {}}
    assert [
        event["candidate_id"]
        for event in strategy_trace["events"]
        if event["action"] == "evaluated"
    ] == [
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
    ]
    assert all(
        event["frontier_quality"] is not None
        for event in strategy_trace["events"]
        if event["action"] == "evaluated"
    )

    log = (run_root / "experiment-log.tsv").read_text()
    assert (
        "rotated-surface-d3-example\t0.013\tkeep\t"
        "entered frontier for distance 3"
    ) in log
    assert (
        "rotated-surface-d5-example\t0.02\tkeep\t"
        "entered frontier for distance 5"
    ) in log
    assert (
        "rotated-surface-d7-example\t0.02\tkeep\t"
        "entered frontier for distance 7"
    ) in log

    leaderboard = (run_root / "leaderboard.csv").read_text()
    assert "rotated-surface-d3-example" in leaderboard
    assert "rotated-surface-d5-example" in leaderboard
    assert "rotated-surface-d7-example" in leaderboard

    branch_log = subprocess.run(
        ["git", "log", "--oneline", "autoresearch/fixed-check"],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "start autoresearch run fixed-check" in branch_log
    assert "evaluate rotated-surface-d3-example" in branch_log
    assert "evaluate rotated-surface-d5-example" in branch_log
    assert "evaluate rotated-surface-d7-example" in branch_log
    assert "finalize autoresearch run fixed-check" in branch_log


def _run_spec(run_root: Path) -> dict:
    return json.loads((run_root / "run_spec.json").read_text())


def _manifest_path(
    run_root: Path,
    *,
    candidate_id: str,
    decoder_id: str,
    task_id: str | None = None,
) -> Path:
    run_spec = _run_spec(run_root)
    actual_task_id = task_id or run_spec["task_ids"][0]
    return (
        run_root
        / "candidates"
        / candidate_id
        / "evaluations"
        / actual_task_id
        / decoder_id
        / "manifest.json"
    )


def _run_direct(work_root: Path, **overrides) -> Path:
    from autoqec_search.run_loop import run_autoresearch

    options = {
        "campaign_id": "rotated-surface-baseline",
        "wall_clock": "90s",
        "seed": None,
        "run_id": "fixed-check",
        "resume": False,
        "cleanup_worktree": False,
        "allow_dirty_root": False,
    }
    options.update(overrides)
    return run_autoresearch(work_root, **options)


def test_run_creates_worktree_branch_and_lab_notebook(tmp_path: Path) -> None:
    work_root = _copy_repo(tmp_path)
    env = _env(_write_fake_rsinter(tmp_path))

    result = _run_autoresearch(
        work_root,
        env,
        "--wall-clock",
        "90s",
        "--run-id",
        "fixed-check",
    )

    assert result.returncode == 0, result.stderr
    assert "autoresearch/fixed-check" in result.stdout
    _assert_root_clean(work_root)
    _assert_lab_notebook(work_root)


def test_run_cleanup_reports_branch_without_stale_worktree_path(tmp_path: Path) -> None:
    work_root = _copy_repo(tmp_path)
    env = _env(_write_fake_rsinter(tmp_path))

    result = _run_autoresearch(
        work_root,
        env,
        "--wall-clock",
        "90s",
        "--run-id",
        "cleanup-check",
        "--cleanup-worktree",
    )

    assert result.returncode == 0, result.stderr
    assert "completed autoresearch run on autoresearch/cleanup-check" in result.stdout
    assert "worktree removed" in result.stdout
    assert " at " not in result.stdout
    assert not (work_root / ".worktrees" / "cleanup-check").exists()
    assert _branch_exists(work_root, "autoresearch/cleanup-check")
    run_status = subprocess.run(
        [
            "git",
            "show",
            "autoresearch/cleanup-check:"
            "results/search/rotated-surface-baseline/cleanup-check/run_status.json",
        ],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert json.loads(run_status)["status"] == "finalized"
    report_html = subprocess.run(
        [
            "git",
            "show",
            "autoresearch/cleanup-check:"
            "results/search/rotated-surface-baseline/cleanup-check/report.html",
        ],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "AutoQEC Search Report" in report_html


def test_run_autoresearch_orchestrates_worktree_branch_and_lab_notebook(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    run_root = _run_direct(work_root)

    assert _branch_exists(work_root, "autoresearch/fixed-check")
    assert run_root == (
        work_root
        / ".worktrees"
        / "fixed-check"
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "fixed-check"
    )
    _assert_root_clean(work_root)
    _assert_lab_notebook(work_root)


def test_run_autoresearch_allow_dirty_root_uses_clean_branch_state(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    campaign_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "campaign.json"
    )
    search_space_path = campaign_path.with_name("search_space.json")
    campaign = json.loads(campaign_path.read_text())
    search_space = json.loads(search_space_path.read_text())
    campaign["random_seed_policy"]["seed"] = 999
    search_space["candidate_specs"] = search_space["candidate_specs"][:1]
    campaign_path.write_text(json.dumps(campaign, indent=2, sort_keys=True) + "\n")
    search_space_path.write_text(
        json.dumps(search_space, indent=2, sort_keys=True) + "\n"
    )

    run_root = _run_direct(
        work_root,
        run_id="dirty-clean-head",
        allow_dirty_root=True,
    )

    run_spec = _run_spec(run_root)
    assert run_spec["seed"] == 7
    assert run_spec["candidate_ids"] == [
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
    ]
    log = (run_root / "experiment-log.tsv").read_text()
    assert (
        "rotated-surface-d7-example\t0.02\tkeep\t"
        "entered frontier for distance 7"
    ) in log


def test_run_autoresearch_dirty_root_requires_explicit_run_id(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    campaign_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "campaign.json"
    )
    campaign = json.loads(campaign_path.read_text())
    campaign["random_seed_policy"]["seed"] = 999
    campaign_path.write_text(json.dumps(campaign, indent=2, sort_keys=True) + "\n")

    with pytest.raises(SearchIntegrityError, match="explicit run_id"):
        _run_direct(
            work_root,
            run_id=None,
            allow_dirty_root=True,
        )


def test_run_autoresearch_records_rsinter_crash_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_failing_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    run_root = _run_direct(work_root, run_id="crash-check")

    run_spec = _run_spec(run_root)
    manifest = json.loads(
        _manifest_path(
            run_root,
            candidate_id=run_spec["candidate_ids"][0],
            decoder_id=run_spec["decoder_ids"][0],
        ).read_text()
    )
    assert manifest["status"] == "crash"
    assert "rsinter bench run exited 7" in manifest["error"]
    assert json.loads((run_root / "run_status.json").read_text())["status"] == "finalized"
    assert "\tcrash\t" in (run_root / "experiment-log.tsv").read_text()


def test_run_autoresearch_tiny_budget_timeout_is_retriable(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_sleeping_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    run_root = _run_direct(work_root, run_id="tiny-budget", wall_clock="1s")

    run_spec = _run_spec(run_root)
    manifest = json.loads(
        _manifest_path(
            run_root,
            candidate_id=run_spec["candidate_ids"][0],
            decoder_id=run_spec["decoder_ids"][0],
        ).read_text()
    )
    assert manifest["status"] == "placeholder"
    run_status = json.loads((run_root / "run_status.json").read_text())
    assert run_status["status"] == "finalized"
    assert run_status["candidates_attempted"] == 0
    assert run_status["stop_reason"] == "wall-clock"
    strategy_trace = json.loads((run_root / "strategy_trace.json").read_text())
    assert strategy_trace["strategy"] == {"name": "grid", "params": {}}
    assert strategy_trace["events"] == []

    retry_bin_dir = _write_fake_rsinter(tmp_path / "retry")
    monkeypatch.setenv(
        "PATH", f"{retry_bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    )

    resumed_root = _run_direct(
        work_root,
        run_id="tiny-budget",
        wall_clock="1s",
        resume=True,
    )

    assert resumed_root == run_root
    resumed_manifest = json.loads(
        _manifest_path(
            run_root,
            candidate_id=run_spec["candidate_ids"][0],
            decoder_id=run_spec["decoder_ids"][0],
        ).read_text()
    )
    assert resumed_manifest["status"] == "completed"


def test_run_autoresearch_frontier_failure_does_not_rewrite_completed_candidate(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    from autoqec_search import run_loop as run_loop_module

    def fail_frontier(*_args, **_kwargs):
        raise SearchIntegrityError("frontier boom")

    monkeypatch.setattr(run_loop_module, "update_frontier", fail_frontier)

    with pytest.raises(SearchIntegrityError, match="frontier boom"):
        _run_direct(work_root, run_id="frontier-failure")

    run_root = (
        work_root
        / ".worktrees"
        / "frontier-failure"
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "frontier-failure"
    )
    manifest = json.loads(
        _manifest_path(
            run_root,
            candidate_id="rotated-surface-d3-example",
            decoder_id="rmatching-default-v1",
        ).read_text()
    )
    assert manifest["status"] == "completed"


def test_quantum_tanner_run_autoresearch_rejects_p001_task_drift(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    task_path = (
        work_root
        / "benchmarks"
        / "tasks"
        / "quantum-tanner-css-memory-x-rbposd-p001-v1.json"
    )
    task = json.loads(task_path.read_text())
    task["p_list"] = [0.01]
    task_path.write_text(json.dumps(task, indent=2, sort_keys=True) + "\n")
    subprocess.run(
        ["git", "add", str(task_path.relative_to(work_root))],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "corrupt quantum tanner p list"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )

    with pytest.raises(SearchIntegrityError, match="quantum Tanner p001 task"):
        _run_direct(
            work_root,
            campaign_id="quantum-tanner-autoresearch",
            run_id="qt-p-drift",
        )


def test_quantum_tanner_run_autoresearch_rejects_p001_suite_drift(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_marker_rsinter(tmp_path)
    marker = tmp_path / "bench-called.txt"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("RSINTER_BENCH_MARKER", str(marker))
    suite_path = (
        work_root
        / "benchmarks"
        / "suites"
        / "quantum-tanner-rbposd-p001-v1.json"
    )
    suite = json.loads(suite_path.read_text())
    suite["shared_settings"]["default_p"] = 0.01
    suite_path.write_text(json.dumps(suite, indent=2, sort_keys=True) + "\n")
    subprocess.run(
        ["git", "add", str(suite_path.relative_to(work_root))],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "corrupt quantum tanner suite p"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )

    with pytest.raises(SearchIntegrityError, match="shared_settings"):
        _run_direct(
            work_root,
            campaign_id="quantum-tanner-autoresearch",
            run_id="qt-suite-p-drift",
        )
    assert not marker.exists()


def test_run_autoresearch_unexpected_candidate_bug_is_not_crash_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    from autoqec_search import run_loop as run_loop_module

    def fail_with_bug(*_args, **_kwargs):
        raise RuntimeError("unexpected candidate bug")

    monkeypatch.setattr(
        run_loop_module,
        "resolve_campaign_candidate_spec",
        fail_with_bug,
    )

    with pytest.raises(RuntimeError, match="unexpected candidate bug"):
        _run_direct(work_root, run_id="unexpected-bug")

    run_root = (
        work_root
        / ".worktrees"
        / "unexpected-bug"
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "unexpected-bug"
    )
    manifest = json.loads(
        _manifest_path(
            run_root,
            candidate_id="rotated-surface-d3-example",
            decoder_id="rmatching-default-v1",
        ).read_text()
    )
    assert manifest["status"] == "placeholder"
    assert not (run_root / "run_status.json").exists()


def test_run_autoresearch_requires_rsinter_before_creating_worktree_or_branch(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    git_executable = shutil.which("git")
    assert git_executable is not None
    os.symlink(git_executable, empty_bin / "git")
    monkeypatch.setenv("PATH", str(empty_bin))

    with pytest.raises(SearchIntegrityError, match="rsinter not found"):
        _run_direct(work_root, run_id="missing-rsinter")

    assert not (work_root / ".worktrees" / "missing-rsinter").exists()
    assert not _branch_exists(work_root, "autoresearch/missing-rsinter")


def test_run_autoresearch_rejects_invalid_wall_clock_before_creating_paths(
    tmp_path: Path,
) -> None:
    work_root = _copy_repo(tmp_path)

    with pytest.raises(SearchIntegrityError, match="invalid wall-clock"):
        _run_direct(work_root, run_id="bad-clock", wall_clock="0s")

    assert not (work_root / ".worktrees" / "bad-clock").exists()
    assert not _branch_exists(work_root, "autoresearch/bad-clock")


def test_run_autoresearch_rejects_unsafe_campaign_id_before_creating_paths(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    campaign_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "campaign.json"
    )
    search_space_path = campaign_path.with_name("search_space.json")
    campaign = json.loads(campaign_path.read_text())
    search_space = json.loads(search_space_path.read_text())
    campaign["id"] = "bad/campaign"
    search_space["campaign_id"] = "bad/campaign"
    campaign_path.write_text(json.dumps(campaign, indent=2, sort_keys=True) + "\n")
    search_space_path.write_text(
        json.dumps(search_space, indent=2, sort_keys=True) + "\n"
    )
    _commit_all(work_root, "make campaign id unsafe")

    with pytest.raises(SearchIntegrityError, match="campaign_id"):
        _run_direct(
            work_root,
            campaign_id="bad/campaign",
            run_id="unsafe-campaign",
        )

    assert not (work_root / ".worktrees" / "unsafe-campaign").exists()
    assert not _branch_exists(work_root, "autoresearch/unsafe-campaign")


def test_run_autoresearch_rejects_unsafe_suite_task_id_before_creating_paths(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    suite_path = work_root / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json"
    task_path = work_root / "benchmarks" / "tasks" / f"{M1_TASK_ID}.json"
    suite = json.loads(suite_path.read_text())
    task = json.loads(task_path.read_text())
    suite["task_ids"] = ["bad/task"]
    task["id"] = "bad/task"
    suite_path.write_text(json.dumps(suite, indent=2, sort_keys=True) + "\n")
    task_path.write_text(json.dumps(task, indent=2, sort_keys=True) + "\n")
    _commit_all(work_root, "make task id unsafe")

    with pytest.raises(SearchIntegrityError, match="task_id"):
        _run_direct(work_root, run_id="unsafe-task")

    assert not (work_root / ".worktrees" / "unsafe-task").exists()
    assert not _branch_exists(work_root, "autoresearch/unsafe-task")


def test_run_autoresearch_rejects_dirty_existing_resume_worktree(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    _run_direct(work_root)
    dirty_path = work_root / ".worktrees" / "fixed-check" / "dirty.txt"
    dirty_path.write_text("dirty\n")

    with pytest.raises(SearchIntegrityError, match="dirty"):
        _run_direct(work_root, resume=True)


def test_run_autoresearch_rejects_wrong_branch_existing_resume_worktree(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    _run_direct(work_root)
    worktree = work_root / ".worktrees" / "fixed-check"
    subprocess.run(
        ["git", "checkout", "-b", "unrelated-resume-branch"],
        cwd=worktree,
        capture_output=True,
        text=True,
        check=True,
    )

    with pytest.raises(SearchIntegrityError, match="expected autoresearch/fixed-check"):
        _run_direct(work_root, resume=True)


def test_run_autoresearch_rejects_corrupt_resume_run_skeleton(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    run_root = _run_direct(work_root)
    worktree = work_root / ".worktrees" / "fixed-check"
    run_spec_path = run_root / "run_spec.json"
    run_spec = json.loads(run_spec_path.read_text())
    run_spec["candidate_ids"] = ["rotated-surface-d3-example"]
    run_spec_path.write_text(json.dumps(run_spec, indent=2, sort_keys=True) + "\n")
    _commit_all(worktree, "corrupt autoresearch run skeleton")

    with pytest.raises(SearchIntegrityError, match="candidate_ids"):
        _run_direct(work_root, resume=True)

    branch_log = subprocess.run(
        ["git", "log", "--oneline", "-1", "autoresearch/fixed-check"],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "corrupt autoresearch run skeleton" in branch_log


def test_run_autoresearch_rejects_extra_key_in_resume_run_skeleton(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    run_root = _run_direct(work_root)
    worktree = work_root / ".worktrees" / "fixed-check"
    run_spec_path = run_root / "run_spec.json"
    run_spec = json.loads(run_spec_path.read_text())
    run_spec["unexpected"] = True
    run_spec_path.write_text(json.dumps(run_spec, indent=2, sort_keys=True) + "\n")
    _commit_all(worktree, "corrupt autoresearch run skeleton keys")

    with pytest.raises(SearchIntegrityError, match="run_spec keys"):
        _run_direct(work_root, resume=True)


def test_run_autoresearch_rejects_bad_created_at_in_resume_run_skeleton(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    run_root = _run_direct(work_root)
    worktree = work_root / ".worktrees" / "fixed-check"
    run_spec_path = run_root / "run_spec.json"
    run_spec = json.loads(run_spec_path.read_text())
    run_spec["created_at"] = "not-a-timestamp"
    run_spec_path.write_text(json.dumps(run_spec, indent=2, sort_keys=True) + "\n")
    _commit_all(worktree, "corrupt autoresearch run skeleton created_at")

    with pytest.raises(SearchIntegrityError, match="created_at"):
        _run_direct(work_root, resume=True)


def test_run_autoresearch_rejects_missing_registered_resume_worktree(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    _run_direct(work_root)
    shutil.rmtree(work_root / ".worktrees" / "fixed-check")

    with pytest.raises(SearchIntegrityError, match="registered worktree path is missing"):
        _run_direct(work_root, resume=True)


def test_run_autoresearch_resume_recomputes_missing_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    _write_non_promoting_rules(work_root)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    run_root = _run_direct(work_root, run_id="resume-repair")
    worktree = work_root / ".worktrees" / "resume-repair"
    run_spec = _run_spec(run_root)
    manifest_path = _manifest_path(
        run_root,
        candidate_id=run_spec["candidate_ids"][0],
        decoder_id=run_spec["decoder_ids"][1],
    )
    manifest_path.unlink()
    _commit_all(worktree, "remove placeholder manifest")

    resumed_root = _run_direct(
        work_root,
        run_id="resume-repair",
        resume=True,
    )

    assert resumed_root == run_root
    repaired_manifest = json.loads(manifest_path.read_text())
    assert repaired_manifest["status"] == "placeholder"
    branch_log = subprocess.run(
        ["git", "log", "--oneline", "autoresearch/resume-repair"],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "evaluate rotated-surface-d3-example" in branch_log


def test_run_autoresearch_resume_migrates_legacy_run_without_strategy_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    _write_non_promoting_rules(work_root)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    run_root = _run_direct(work_root, run_id="legacy-resume")
    worktree = work_root / ".worktrees" / "legacy-resume"

    run_spec_path = run_root / "run_spec.json"
    run_spec = json.loads(run_spec_path.read_text())
    del run_spec["strategy"]
    run_spec_path.write_text(json.dumps(run_spec, indent=2, sort_keys=True) + "\n")

    env_path = run_root / "env.json"
    env = json.loads(env_path.read_text())
    env.pop("strategy_name", None)
    env.pop("strategy_params", None)
    env_path.write_text(json.dumps(env, indent=2, sort_keys=True) + "\n")

    run_status_path = run_root / "run_status.json"
    run_status = json.loads(run_status_path.read_text())
    run_status.pop("stop_reason", None)
    run_status_path.write_text(json.dumps(run_status, indent=2, sort_keys=True) + "\n")
    (run_root / "strategy_trace.json").unlink()
    _commit_all(worktree, "simulate legacy autoresearch run")

    resumed_root = _run_direct(
        work_root,
        run_id="legacy-resume",
        resume=True,
    )

    assert resumed_root == run_root
    migrated_run_spec = json.loads(run_spec_path.read_text())
    assert migrated_run_spec["strategy"] == {"name": "grid", "params": {}}
    migrated_env = json.loads(env_path.read_text())
    assert migrated_env["strategy_name"] == "grid"
    assert migrated_env["strategy_params"] == {}
    migrated_status = json.loads(run_status_path.read_text())
    assert migrated_status["stop_reason"] in {
        "completed",
        "max-candidates",
        "search-space-exhausted",
        "wall-clock",
    }
    strategy_trace = json.loads((run_root / "strategy_trace.json").read_text())
    assert strategy_trace["strategy"] == {"name": "grid", "params": {}}
    reconstructed = [
        event
        for event in strategy_trace["events"]
        if event["reason"] == "resume-terminal-candidate"
    ]
    assert [event["candidate_id"] for event in reconstructed] == list(
        EXPANDED_SURFACE_CANDIDATES
    )
    assert all(event["action"] == "evaluated" for event in reconstructed)


def test_run_autoresearch_resume_rejects_corrupt_strategy_trace(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    _write_non_promoting_rules(work_root)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    run_root = _run_direct(work_root, run_id="corrupt-trace")
    worktree = work_root / ".worktrees" / "corrupt-trace"
    (run_root / "strategy_trace.json").write_text(
        json.dumps({"campaign_id": "wrong", "run_id": "corrupt-trace"}) + "\n"
    )
    _commit_all(worktree, "corrupt strategy trace")

    with pytest.raises(SearchIntegrityError, match="strategy_trace"):
        _run_direct(
            work_root,
            run_id="corrupt-trace",
            resume=True,
        )


def test_run_autoresearch_resume_uses_worktree_state_when_parent_root_drifts(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    _write_non_promoting_rules(work_root)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    run_root = _run_direct(work_root)
    search_space_path = (
        work_root
        / "campaigns"
        / "examples"
        / "rotated-surface-baseline"
        / "search_space.json"
    )
    search_space = json.loads(search_space_path.read_text())
    search_space["candidate_specs"] = search_space["candidate_specs"][:1]
    search_space_path.write_text(
        json.dumps(search_space, indent=2, sort_keys=True) + "\n"
    )
    _commit_all(work_root, "drift parent root search space")

    resumed_root = _run_direct(work_root, resume=True)

    assert resumed_root == run_root
    run_spec = json.loads((run_root / "run_spec.json").read_text())
    assert run_spec["candidate_ids"] == list(EXPANDED_SURFACE_CANDIDATES)
    log = (run_root / "experiment-log.tsv").read_text()
    assert "rotated-surface-d7-example\t0.02\tkeep\t" in log


def test_run_autoresearch_resume_uses_worktree_seed_when_parent_root_drifts(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    _write_non_promoting_rules(work_root)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    run_root = _run_direct(work_root)
    campaign_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "campaign.json"
    )
    campaign = json.loads(campaign_path.read_text())
    campaign["random_seed_policy"]["seed"] = 999
    campaign_path.write_text(json.dumps(campaign, indent=2, sort_keys=True) + "\n")
    _commit_all(work_root, "drift parent root seed")

    resumed_root = _run_direct(work_root, resume=True)

    assert resumed_root == run_root
    run_spec = json.loads((run_root / "run_spec.json").read_text())
    assert run_spec["seed"] == 7


def test_run_autoresearch_resume_uses_worktree_budget_when_parent_root_drifts(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    _write_non_promoting_rules(work_root)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    run_root = _run_direct(work_root, run_id="budget-check", wall_clock=None)
    campaign_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "campaign.json"
    )
    campaign = json.loads(campaign_path.read_text())
    campaign["budget"]["wall_clock_seconds"] = 1234
    campaign["stop_conditions"]["max_wall_clock_seconds"] = 1234
    campaign_path.write_text(json.dumps(campaign, indent=2, sort_keys=True) + "\n")
    _commit_all(work_root, "drift parent root wall clock")

    resumed_root = _run_direct(
        work_root,
        run_id="budget-check",
        wall_clock=None,
        resume=True,
    )

    assert resumed_root == run_root
    run_spec = json.loads((run_root / "run_spec.json").read_text())
    assert run_spec["wall_clock_seconds"] == 3600


def test_run_autoresearch_rejects_foreign_linked_resume_worktree(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    _run_direct(work_root)
    own_worktree = work_root / ".worktrees" / "fixed-check"
    subprocess.run(
        ["git", "worktree", "remove", str(own_worktree)],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    )
    other_root = tmp_path / "other"
    other_root.mkdir()
    subprocess.run(
        ["git", "init"], cwd=other_root, capture_output=True, text=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "autoqec@example.com"],
        cwd=other_root,
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "AutoQEC"],
        cwd=other_root,
        capture_output=True,
        text=True,
        check=True,
    )
    (other_root / "README.md").write_text("foreign\n")
    _commit_all(other_root, "initial foreign")
    subprocess.run(
        ["git", "worktree", "add", "-b", "autoresearch/fixed-check", str(own_worktree)],
        cwd=other_root,
        capture_output=True,
        text=True,
        check=True,
    )

    with pytest.raises(SearchIntegrityError, match="not registered by parent root"):
        _run_direct(work_root, resume=True)


def test_run_autoresearch_resume_calls_promotion_with_existing_summary(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.unlink()
    _commit_all(work_root, "remove promote rules")
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    run_root = _run_direct(work_root, run_id="promotion-resume-call")
    assert json.loads((run_root / "promotion_summary.json").read_text())["status"] == "skipped_no_rules"

    from autoqec_search import run_loop as run_loop_module

    calls = []

    def record_promotion(worktree_root: Path, actual_run_root: Path, *, rules_path, force):
        calls.append((worktree_root, actual_run_root, rules_path, force))
        return {}

    monkeypatch.setattr(run_loop_module, "promote_run", record_promotion)

    _run_direct(
        work_root,
        run_id="promotion-resume-call",
        resume=True,
    )

    assert calls == [
        (
            work_root / ".worktrees" / "promotion-resume-call",
            run_root,
            None,
            False,
        )
    ]


def test_run_autoresearch_resume_after_successful_promotion_is_idempotent(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    run_root = _run_direct(work_root, run_id="promotion-resume-idempotent")
    first_summary = json.loads((run_root / "promotion_summary.json").read_text())
    assert first_summary["status"] == "completed"

    resumed_root = _run_direct(
        work_root,
        run_id="promotion-resume-idempotent",
        resume=True,
    )

    assert resumed_root == run_root
    second_summary = json.loads((run_root / "promotion_summary.json").read_text())
    assert second_summary["status"] == "completed"
    assert [item["candidate_id"] for item in second_summary["promoted"]] == list(
        EXPANDED_SURFACE_CANDIDATES
    )


def test_run_autoresearch_resume_reevaluates_completed_candidate_missing_rule_p(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    run_root = _run_direct(work_root, run_id="promotion-resume-rule-p")
    worktree = work_root / ".worktrees" / "promotion-resume-rule-p"
    manifest_path = _manifest_path(
        run_root,
        candidate_id="rotated-surface-d3-example",
        decoder_id="rmatching-default-v1",
    )
    manifest = json.loads(manifest_path.read_text())
    manifest["points"] = [
        point for point in manifest["points"] if point["p"] == M1_FIRST_P
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _commit_all(worktree, "simulate old manifest without promotion p")

    _run_direct(
        work_root,
        run_id="promotion-resume-rule-p",
        resume=True,
    )

    repaired_manifest = json.loads(manifest_path.read_text())
    assert M1_PROMOTION_P in [point["p"] for point in repaired_manifest["points"]]


def test_run_autoresearch_promotes_kept_candidate_into_zoo(tmp_path: Path, monkeypatch) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    run_root = _run_direct(work_root, run_id="promotion-check")
    worktree = work_root / ".worktrees" / "promotion-check"
    instance_root = worktree / "zoo" / "codes" / "rotated-surface-code" / "instances"

    assert run_root == (
        worktree
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "promotion-check"
    )
    for candidate_id in EXPANDED_SURFACE_CANDIDATES:
        promoted = instance_root / candidate_id
        assert promoted.is_dir()
        instance = json.loads((promoted / "instance.json").read_text())
        assert instance["id"] == candidate_id
        assert instance["provenance"]["source_run"] == "rotated-surface-baseline/m1-demo"
    summary = json.loads((run_root / "promotion_summary.json").read_text())
    assert summary["status"] == "completed"
    assert [item["candidate_id"] for item in summary["promoted"]] == list(
        EXPANDED_SURFACE_CANDIDATES
    )
    for candidate_id in EXPANDED_SURFACE_CANDIDATES:
        manifest_path = (
            run_root
            / "candidates"
            / candidate_id
            / "evaluations"
            / M1_TASK_ID
            / "rmatching-default-v1"
            / "manifest.json"
        )
        manifest = json.loads(manifest_path.read_text())
        assert M1_PROMOTION_P in [point["p"] for point in manifest["points"]]
    instance_index = json.loads((worktree / "zoo" / "views" / "instance-index.json").read_text())
    indexed_ids = [item["id"] for item in instance_index["items"]]
    for candidate_id in EXPANDED_SURFACE_CANDIDATES:
        assert candidate_id in indexed_ids

    branch_log = subprocess.run(
        ["git", "log", "--oneline", "autoresearch/promotion-check"],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "finalize autoresearch run promotion-check" in branch_log


def test_run_autoresearch_missing_rules_writes_skip_summary(tmp_path: Path, monkeypatch) -> None:
    work_root = _copy_repo(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.unlink()
    _commit_all(work_root, "remove promote rules")
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    run_root = _run_direct(work_root, run_id="promotion-skip")

    summary = json.loads((run_root / "promotion_summary.json").read_text())
    assert summary["status"] == "skipped_no_rules"
    assert summary["promoted"] == []
    promoted = (
        work_root
        / ".worktrees"
        / "promotion-skip"
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    assert promoted.is_dir()
    instance = json.loads((promoted / "instance.json").read_text())
    assert instance["provenance"]["source_run"] == "rotated-surface-baseline/m1-demo"


def test_run_autoresearch_upper_bound_finalization_skips_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work_root = _copy_repo(tmp_path)
    suite_path = work_root / "benchmarks" / "suites" / "decoder-registry-css-bb-smoke-v1.json"
    suite = json.loads(suite_path.read_text())
    suite["decoder_ids"] = ["predict-zero-v1"]
    suite_path.write_text(json.dumps(suite, indent=2, sort_keys=True) + "\n")
    shutil.rmtree(
        work_root / "results" / "search" / "decoder-registry-css-bb-smoke",
        ignore_errors=True,
    )
    rules_path = (
        work_root
        / "campaigns"
        / "examples"
        / "decoder-registry-css-bb-smoke"
        / "promote_rules.json"
    )
    rules_path.write_text(
        json.dumps(
            {
                "max_ler_at_p": {"p": 0.003, "ler": 1.0},
                "min_distance": 1,
                "require_distance_verified": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    _commit_all(work_root, "prepare upper-bound promotion rules")

    from autoqec_search import eval_run as eval_run_module
    from autoqec_search import run_loop as run_loop_module

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
        records = []
        for p in (0.003, 0.01):
            records.append(
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
                            "p": p,
                            "max_shots": 64,
                            "max_errors": 64,
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
            )
        result_path.write_text("\n".join(records) + "\n")

    monkeypatch.setattr(
        run_loop_module,
        "require_rsinter",
        lambda: ("/bin/rsinter", "rsinter fake"),
    )
    monkeypatch.setattr(eval_run_module, "run_rsinter", fake_run_rsinter)

    run_root = _run_direct(
        work_root,
        campaign_id="decoder-registry-css-bb-smoke",
        run_id="upper-bound-finalize",
        distance_method="random-window-upper-bound",
    )

    summary = json.loads((run_root / "promotion_summary.json").read_text())
    distance = json.loads(
        (
            run_root
            / "candidates"
            / "bivariate-bicycle-code-m6-n6"
            / "distance.json"
        ).read_text()
    )

    assert summary["status"] == "skipped_non_exact_distance"
    assert summary["distance_method"]["method"] == "random-window-upper-bound"
    assert summary["distance_method"]["bound_type"] == "upper"
    assert summary["promoted"] == []
    assert distance["method"] == "random-window-upper-bound"
    assert distance["bound_type"] == "upper"
    assert "distance" not in distance


def test_run_autoresearch_invalid_rules_fail_during_final_promotion(
    tmp_path: Path, monkeypatch
) -> None:
    work_root = _copy_repo(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.write_text(
        json.dumps({"max_ler_at_p": {"p": 0.005}}, indent=2, sort_keys=True) + "\n"
    )
    _commit_all(work_root, "make promote rules invalid")
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    with pytest.raises(SearchIntegrityError, match="invalid promote rules"):
        _run_direct(work_root, run_id="promotion-invalid-rules")

    run_root = (
        work_root
        / ".worktrees"
        / "promotion-invalid-rules"
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "promotion-invalid-rules"
    )
    assert (run_root / "report.html").is_file()
    assert json.loads((run_root / "run_status.json").read_text())["status"] == "finalized"
