from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from autoqec_search.css_distance_eval import DEFAULT_TIMEOUT_SECONDS
from autoqec_search.css_distance_autoresearch import (
    build_public_proposal_prompt,
    create_css_distance_algorithm_worktree,
    evaluate_css_distance_algorithm,
)
from autoqec_search.css_distance_autoresearch import CssDistanceEvaluationResult
from autoqec_search.cli import main
from autoqec_search.load import SearchIntegrityError


HX = {
    "format": "dense_binary_matrix",
    "n_rows": 1,
    "n_cols": 4,
    "data": [[1, 1, 0, 0]],
}
HZ = {
    "format": "dense_binary_matrix",
    "n_rows": 1,
    "n_cols": 4,
    "data": [[0, 0, 1, 1]],
}
SELECTED_IDS = [
    "surface-rotated-d21",
    "toric-d17",
    "toric-d21",
    "bb72",
    "bb144",
    "bb288-same-shifts",
    "bb432-same-shifts",
    "apm-kasai-p96",
    "apm-kasai-p192",
    "quantum-tanner-toric-d8",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _init_repo(root: Path) -> None:
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=root,
        check=True,
    )
    (root / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=root, check=True)


def _tiny_ladder(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    entries = []
    for source_id in SELECTED_IDS:
        case = source / source_id
        case.mkdir(parents=True)
        _write_json(case / "hx.json", HX)
        _write_json(case / "hz.json", HZ)
        entries.append(
            {
                "instance_id": source_id,
                "expected_distance": 2,
                "expected_bound_type": "exact",
            }
        )
    ladder_path = tmp_path / "ladder.json"
    _write_json(ladder_path, {"artifact_root": "source", "entries": entries})
    return ladder_path, source


def test_creates_per_algorithm_worktree_with_sanitized_log(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)

    experiment = create_css_distance_algorithm_worktree(
        root,
        algorithm_id="qdist-rndmw-seed1",
        created_at="2026-07-19T00:00:00Z",
        allow_dirty_root=False,
    )

    assert experiment.branch == "autoresearch/css-distance/qdist-rndmw-seed1"
    assert experiment.worktree_root == root / ".worktrees" / "css-distance-qdist-rndmw-seed1"
    assert (experiment.worktree_root / ".git").exists()
    log = (experiment.worktree_root / "LOG.md").read_text()
    assert "qdist-rndmw-seed1" in log
    assert "300s" in log
    assert "private issue #38 holdout" in log
    for forbidden in (
        "surface-rotated-d21",
        "toric-d17",
        "bb432-same-shifts",
        "apm-kasai-p96",
        "case-0001",
        "answers.json",
    ):
        assert forbidden not in log


def test_worktree_creation_ignores_ambient_git_dir_and_work_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "intended"
    hostile = tmp_path / "hostile"
    _init_repo(root)
    _init_repo(hostile)
    expected_branch = "autoresearch/css-distance/ambient-safe"
    subprocess.run(
        ["git", "branch", expected_branch],
        cwd=hostile,
        check=True,
    )
    (hostile / "ambient-dirty.txt").write_text(
        "hostile untracked state\n",
        encoding="utf-8",
    )
    hostile_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=hostile,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    hostile_branches = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)", "refs/heads"],
        cwd=hostile,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    monkeypatch.setenv("GIT_DIR", str(hostile / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(hostile))

    experiment = create_css_distance_algorithm_worktree(
        root,
        algorithm_id="ambient-safe",
        created_at="2026-07-19T00:00:00Z",
        allow_dirty_root=False,
    )
    monkeypatch.delenv("GIT_DIR")
    monkeypatch.delenv("GIT_WORK_TREE")

    assert subprocess.run(
        ["git", "show-ref", "--verify", f"refs/heads/{expected_branch}"],
        cwd=root,
        check=False,
        capture_output=True,
    ).returncode == 0
    assert subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=experiment.worktree_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() == str(root / ".git")
    assert subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=hostile,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() == hostile_head
    assert subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)", "refs/heads"],
        cwd=hostile,
        check=True,
        capture_output=True,
        text=True,
    ).stdout == hostile_branches


def test_public_proposal_prompt_uses_survey_and_source_without_private_holdout() -> None:
    source = {
        "repository": "https://github.com/m-webster/codeDistancePYPI",
        "commit": "a4afe9c09bbf5790da9ecc05b65c5b62343979ad",
        "baseline_methods": ["QDistEvol", "QDistRndMW", "decoderDist"],
    }

    prompt = build_public_proposal_prompt(
        research_brief=(
            "QDistRnd, QDistEvol, decoder residual search, linked cluster, "
            "and APM quotient/lift/fiber witness searches are relevant. "
            "Exact SAT/MaxSAT is out of scope."
        ),
        source_pin=source,
    )

    assert "QDistRndMW" in prompt
    assert "randomized upper-bound CSS distance" in prompt
    assert "candidate.py" in prompt
    assert '`status` must be exactly `"completed"`' in prompt
    assert "Exact SAT/MaxSAT is out of scope" in prompt
    assert "a4afe9c09bbf5790da9ecc05b65c5b62343979ad" in prompt
    for forbidden in (
        "surface-rotated-d21",
        "toric-d17",
        "bb432-same-shifts",
        "apm-kasai-p96",
        "case-0001",
        "answers.json",
        "expected_distance",
    ):
        assert forbidden not in prompt


def test_public_proposal_prompt_rejects_private_holdout_markers() -> None:
    with pytest.raises(SearchIntegrityError, match="private holdout"):
        build_public_proposal_prompt(
            research_brief="Try to optimize for case-0001 and surface-rotated-d21.",
            source_pin={
                "repository": "https://github.com/m-webster/codeDistancePYPI",
                "commit": "a4afe9c09bbf5790da9ecc05b65c5b62343979ad",
                "baseline_methods": ["QDistRndMW"],
            },
        )


def test_screening_evaluation_logs_only_sanitized_aggregate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = tmp_path / "work"
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "LOG.md").write_text("# Candidate Log\n")
    _write_json(
        work_root / "private" / "holdout" / "answers.json",
        {
            "screening_seed": 11,
            "finalist_seeds": [17, 19, 23],
            "cases": [
                {
                    "case_id": "case-0001",
                    "source_id": "bb72",
                    "target": 6,
                    "bound_type": "exact",
                    "tier": "regression",
                    "weight": 2,
                }
            ],
        },
    )
    observed: dict[str, object] = {}

    def fake_run_private_phase(*, command, command_builder, work_root, phase, timeout_seconds):
        observed.update(
            {
                "command": tuple(command),
                "command_builder": command_builder,
                "work_root": work_root,
                "phase": phase,
                "timeout_seconds": timeout_seconds,
            }
        )
        return [
            {
                "case_id": "case-0001",
                "seed": 11,
                "status": "completed",
                "verified_weight": 6,
                "runtime_seconds": 1.25,
                "vector": [1, 0, 1, 0],
            }
        ]

    monkeypatch.setattr(
        "autoqec_search.css_distance_autoresearch.run_private_phase",
        fake_run_private_phase,
    )

    result = evaluate_css_distance_algorithm(
        algorithm_id="qdist-rndmw-seed1",
        candidate_worktree=candidate,
        work_root=work_root,
        command=["candidate-entrypoint"],
        phase="screening",
    )

    assert observed["command"] == ("candidate-entrypoint",)
    assert observed["phase"] == "screening"
    assert observed["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS
    assert result.summary["decision"] == "accepted"
    assert result.summary["verified_witnesses"] == 1
    log = (candidate / "LOG.md").read_text()
    assert "decision: accepted" in log
    assert "weighted_target_hits: 2" in log
    for forbidden in (
        "case-0001",
        "bb72",
        "target:",
        "seed",
        "vector",
        "answers.json",
    ):
        assert forbidden not in log


def test_cli_prepares_css_distance_algorithm_worktree(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "repo"
    _init_repo(root)

    status = main(
        [
            "prepare-css-distance-algorithm",
            "--root",
            str(root),
            "--algorithm-id",
            "qdist-evol-seed2",
            "--created-at",
            "2026-07-19T00:00:00Z",
        ]
    )

    assert status == 0
    output = capsys.readouterr().out
    assert "autoresearch/css-distance/qdist-evol-seed2" in output
    assert str(root / ".worktrees" / "css-distance-qdist-evol-seed2") in output
    assert (root / ".worktrees" / "css-distance-qdist-evol-seed2" / "LOG.md").is_file()


def test_cli_writes_redacted_css_distance_proposal_prompt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    brief = tmp_path / "brief.md"
    source = tmp_path / "source.json"
    out = tmp_path / "prompt.txt"
    brief.write_text(
        "QDistRnd and decoder residual search are useful randomized upper-bound "
        "baselines. Exact SAT/MaxSAT is out of scope."
    )
    _write_json(
        source,
        {
            "repository": "https://github.com/m-webster/codeDistancePYPI",
            "commit": "a4afe9c09bbf5790da9ecc05b65c5b62343979ad",
            "baseline_methods": ["QDistRndMW", "decoderDist"],
        },
    )

    status = main(
        [
            "prepare-css-distance-proposal",
            "--brief",
            str(brief),
            "--source",
            str(source),
            "--out",
            str(out),
        ]
    )

    assert status == 0
    assert f"wrote CSS-distance proposal prompt to {out}" in capsys.readouterr().out
    prompt = out.read_text()
    assert "candidate.py" in prompt
    assert "QDistRndMW" in prompt
    for forbidden in ("case-0001", "answers.json", "expected_distance"):
        assert forbidden not in prompt


def test_cli_materializes_private_css_distance_holdout_without_answer_leak(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ladder_path, _ = _tiny_ladder(tmp_path)
    work_root = tmp_path / "work"

    status = main(
        [
            "materialize-css-distance-holdout",
            "--ladder",
            str(ladder_path),
            "--work-root",
            str(work_root),
        ]
    )

    assert status == 0
    output = capsys.readouterr().out
    assert "materialized private CSS-distance holdout cases=10" in output
    assert "answers.json" not in output
    assert "case-0001" not in output
    assert (work_root / "private" / "holdout" / "answers.json").is_file()


def test_cli_reports_css_distance_holdout_materialization_error_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ladder_path, _ = _tiny_ladder(tmp_path)

    def fail_materialization(*, ladder_path, work_root):
        raise __import__(
            "autoqec_search.css_distance_eval",
            fromlist=["CssDistanceEvalError"],
        ).CssDistanceEvalError("unsafe directory")

    monkeypatch.setattr(
        "autoqec_search.cli.materialize_private_holdout",
        fail_materialization,
    )

    status = main(
        [
            "materialize-css-distance-holdout",
            "--ladder",
            str(ladder_path),
            "--work-root",
            str(tmp_path / "work"),
        ]
    )

    captured = capsys.readouterr()
    assert status == 1
    assert "error: unsafe directory" in captured.err
    assert "Traceback" not in captured.err


def test_cli_runs_css_distance_candidate_through_docker_evaluator_wiring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    work_root = tmp_path / "work"
    observed: dict[str, object] = {}

    def fake_preflight(image):
        observed["image_reference"] = image.reference
        observed["image_baseline"] = image.baseline

    def fake_evaluate(**kwargs):
        observed.update(kwargs)
        return CssDistanceEvaluationResult(
            algorithm_id=kwargs["algorithm_id"],
            phase=kwargs["phase"],
            summary={
                "decision": "accepted",
                "accepted": True,
                "runs": 10,
                "verified_witnesses": 10,
                "target_hits": 7,
                "timeouts": 0,
                "crashes": 0,
                "invalid_claims": 0,
                "weighted_target_hits": 11,
                "normalized_quality": 0.9,
                "runtime_seconds": 12.5,
            },
        )

    monkeypatch.setattr(
        "autoqec_search.cli.require_docker_preflight",
        fake_preflight,
    )
    monkeypatch.setattr(
        "autoqec_search.cli.evaluate_css_distance_algorithm",
        fake_evaluate,
    )

    status = main(
        [
            "run-css-distance-candidate",
            "--algorithm-id",
            "qdist-rndmw-seed1",
            "--candidate-worktree",
            str(candidate),
            "--work-root",
            str(work_root),
            "--image",
            "css-distance:evaluator",
            "--baseline",
            "a4afe9c09bbf5790da9ecc05b65c5b62343979ad",
        ]
    )

    assert status == 0
    assert observed["image_reference"] == "css-distance:evaluator"
    assert observed["image_baseline"] == "a4afe9c09bbf5790da9ecc05b65c5b62343979ad"
    assert observed["algorithm_id"] == "qdist-rndmw-seed1"
    assert observed["candidate_worktree"] == candidate
    assert observed["work_root"] == work_root
    assert observed["command"] == ["candidate-entrypoint"]
    assert observed["phase"] == "screening"
    assert observed["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS
    assert "decision=accepted" in capsys.readouterr().out


def test_cli_reports_css_distance_docker_preflight_error_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()

    def fail_preflight(image):
        raise __import__(
            "autoqec_search.css_distance_container",
            fromlist=["CssDistanceContainerError"],
        ).CssDistanceContainerError("Docker Desktop is required")

    monkeypatch.setattr(
        "autoqec_search.cli.require_docker_preflight",
        fail_preflight,
    )

    status = main(
        [
            "run-css-distance-candidate",
            "--algorithm-id",
            "qdist-rndmw-seed1",
            "--candidate-worktree",
            str(candidate),
            "--work-root",
            str(tmp_path / "work"),
            "--image",
            "css-distance:evaluator",
            "--baseline",
            "a4afe9c09bbf5790da9ecc05b65c5b62343979ad",
        ]
    )

    captured = capsys.readouterr()
    assert status == 1
    assert "error: Docker Desktop is required" in captured.err
    assert "Traceback" not in captured.err
