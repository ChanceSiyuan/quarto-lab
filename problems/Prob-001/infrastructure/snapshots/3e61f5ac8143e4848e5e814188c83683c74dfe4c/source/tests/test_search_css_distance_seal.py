from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

import autoqec_search.css_distance_seal as seal
from autoqec_search.css_distance_seal import (
    create_candidate_freeze,
    open_final_manifest,
    validate_candidate_freeze,
)
from autoqec_search.load import SearchIntegrityError


IMAGE_DIGEST = "sha256:" + "1" * 64
SEEDS = [
    104729,
    130363,
    155921,
    196613,
    262147,
    327673,
    393241,
    458789,
    524309,
    589867,
    655373,
    720899,
    786433,
    851971,
    917519,
    983063,
    1048583,
    1114129,
    1179661,
    1245187,
]
METHOD_CONFIG = {"method": "quotient-coset-upper-bound", "max_no_improvement": 128}
DEVELOPMENT_SUMMARY = {"runs": 480, "verified_witnesses": 480}
SUITE_COMMITMENT = {
    "schema_version": 1,
    "counts": {"development": 24, "final": 12},
    "development_manifest_commitment": "2" * 64,
    "final_manifest_commitment": "3" * 64,
}


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def _candidate_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "candidate"
    repo.mkdir()
    _run(["git", "init", "-q"], repo)
    _run(["git", "config", "user.email", "test@example.test"], repo)
    _run(["git", "config", "user.name", "AutoQEC Test"], repo)
    (repo / "candidate.py").write_text("print('candidate')\n")
    _run(["git", "add", "candidate.py"], repo)
    _run(["git", "commit", "-q", "-m", "candidate"], repo)
    return repo


def _freeze(repo: Path) -> dict:
    return create_candidate_freeze(
        candidate_worktree=repo,
        candidate_path=Path("candidate.py"),
        image_digest=IMAGE_DIGEST,
        method_config=METHOD_CONFIG,
        seed_manifest={"seeds": SEEDS},
        development_summary=DEVELOPMENT_SUMMARY,
        suite_commitment=SUITE_COMMITMENT,
        created_at="2026-07-21T00:00:00Z",
    )


def test_create_and_validate_candidate_freeze_requires_clean_git_state(
    tmp_path: Path,
) -> None:
    repo = _candidate_repo(tmp_path)

    freeze = _freeze(repo)

    assert freeze["schema_version"] == 1
    assert freeze["created_at"] == "2026-07-21T00:00:00Z"
    assert freeze["candidate_path"] == "candidate.py"
    assert freeze["image_digest"] == IMAGE_DIGEST
    assert freeze["time_limit_seconds"] == 300
    assert len(freeze["git_commit"]) == 40
    assert len(freeze["candidate_sha256"]) == 64
    assert len(freeze["method_config_sha256"]) == 64
    assert len(freeze["seed_manifest_sha256"]) == 64
    assert len(freeze["development_summary_sha256"]) == 64
    assert len(freeze["suite_commitment_sha256"]) == 64
    assert validate_candidate_freeze(
        candidate_worktree=repo,
        freeze=freeze,
        image_digest=IMAGE_DIGEST,
        method_config=METHOD_CONFIG,
        seed_manifest={"seeds": SEEDS},
        development_summary=DEVELOPMENT_SUMMARY,
        suite_commitment=SUITE_COMMITMENT,
    ) == {"status": "pass"}

    (repo / "candidate.py").write_text("print('changed')\n")
    with pytest.raises(SearchIntegrityError, match="dirty"):
        create_candidate_freeze(
            candidate_worktree=repo,
            candidate_path=Path("candidate.py"),
            image_digest=IMAGE_DIGEST,
            method_config=METHOD_CONFIG,
            seed_manifest={"seeds": SEEDS},
            development_summary=DEVELOPMENT_SUMMARY,
            suite_commitment=SUITE_COMMITMENT,
            created_at="2026-07-21T00:00:00Z",
        )
    with pytest.raises(SearchIntegrityError, match="dirty"):
        validate_candidate_freeze(
            candidate_worktree=repo,
            freeze=freeze,
            image_digest=IMAGE_DIGEST,
            method_config=METHOD_CONFIG,
            seed_manifest={"seeds": SEEDS},
            development_summary=DEVELOPMENT_SUMMARY,
            suite_commitment=SUITE_COMMITMENT,
        )


def test_freeze_rejects_bad_seed_count_and_image_digest(tmp_path: Path) -> None:
    repo = _candidate_repo(tmp_path)

    with pytest.raises(SearchIntegrityError, match="image digest"):
        create_candidate_freeze(
            candidate_worktree=repo,
            candidate_path=Path("candidate.py"),
            image_digest="not-a-digest",
            method_config=METHOD_CONFIG,
            seed_manifest={"seeds": SEEDS},
            development_summary=DEVELOPMENT_SUMMARY,
            suite_commitment=SUITE_COMMITMENT,
            created_at="2026-07-21T00:00:00Z",
        )
    with pytest.raises(SearchIntegrityError, match="20"):
        create_candidate_freeze(
            candidate_worktree=repo,
            candidate_path=Path("candidate.py"),
            image_digest=IMAGE_DIGEST,
            method_config=METHOD_CONFIG,
            seed_manifest={"seeds": SEEDS[:-1]},
            development_summary=DEVELOPMENT_SUMMARY,
            suite_commitment=SUITE_COMMITMENT,
            created_at="2026-07-21T00:00:00Z",
        )


@pytest.mark.parametrize(
    "drift",
    ["missing_freeze", "candidate", "image", "config", "seed", "commitment", "ledger"],
)
def test_open_final_manifest_rejects_drift_before_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    repo = _candidate_repo(tmp_path)
    freeze = _freeze(repo)
    private_root = tmp_path / "private"
    ledger = private_root / "final" / "final-run-ledger.jsonl"
    loader_called = False

    def forbidden_loader(path: Path) -> dict:
        nonlocal loader_called
        loader_called = True
        return {"split": "final", "cases": []}

    monkeypatch.setattr(seal, "_load_private_final_manifest", forbidden_loader)

    kwargs = {
        "private_root": private_root,
        "freeze": freeze,
        "candidate_worktree": repo,
        "image_digest": IMAGE_DIGEST,
        "method_config": METHOD_CONFIG,
        "seed_manifest": {"seeds": SEEDS},
        "development_summary": DEVELOPMENT_SUMMARY,
        "suite_commitment": SUITE_COMMITMENT,
    }
    if drift == "missing_freeze":
        kwargs["freeze"] = None
    elif drift == "candidate":
        (repo / "candidate.py").write_text("print('changed')\n")
    elif drift == "image":
        kwargs["image_digest"] = "sha256:" + "4" * 64
    elif drift == "config":
        kwargs["method_config"] = {"method": "quotient-coset-upper-bound", "extra": True}
    elif drift == "seed":
        kwargs["seed_manifest"] = {"seeds": [*SEEDS[:-1], 9999991]}
    elif drift == "commitment":
        kwargs["suite_commitment"] = {**SUITE_COMMITMENT, "final_manifest_commitment": "5" * 64}
    elif drift == "ledger":
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({"attempt_type": "algorithm"}) + "\n")

    with pytest.raises(SearchIntegrityError):
        open_final_manifest(**kwargs)
    assert loader_called is False


def test_valid_frozen_candidate_opens_final_manifest_once_and_records_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _candidate_repo(tmp_path)
    freeze = _freeze(repo)
    private_root = tmp_path / "private"

    monkeypatch.setattr(
        seal,
        "_load_private_final_manifest",
        lambda path: {"split": "final", "cases": [{"case_id": "final-000"}]},
    )

    manifest = open_final_manifest(
        private_root=private_root,
        freeze=freeze,
        candidate_worktree=repo,
        image_digest=IMAGE_DIGEST,
        method_config=METHOD_CONFIG,
        seed_manifest={"seeds": SEEDS},
        development_summary=DEVELOPMENT_SUMMARY,
        suite_commitment=SUITE_COMMITMENT,
    )

    assert manifest == {"split": "final", "cases": [{"case_id": "final-000"}]}
    ledger = private_root / "final" / "final-run-ledger.jsonl"
    attempts = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert attempts == [
        {
            "attempt_type": "algorithm",
            "git_commit": freeze["git_commit"],
            "candidate_sha256": freeze["candidate_sha256"],
            "suite_commitment_sha256": freeze["suite_commitment_sha256"],
        }
    ]

    with pytest.raises(SearchIntegrityError, match="already"):
        open_final_manifest(
            private_root=private_root,
            freeze=freeze,
            candidate_worktree=repo,
            image_digest=IMAGE_DIGEST,
            method_config=METHOD_CONFIG,
            seed_manifest={"seeds": SEEDS},
            development_summary=DEVELOPMENT_SUMMARY,
            suite_commitment=SUITE_COMMITMENT,
        )
