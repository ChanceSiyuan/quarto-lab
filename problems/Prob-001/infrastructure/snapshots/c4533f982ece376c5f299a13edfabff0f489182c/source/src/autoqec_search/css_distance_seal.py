"""Candidate freeze and sealed-final gate for CSS-distance validation."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

from autoqec_search.css_distance_suite import (
    MINIMUM_SEEDS,
    TIME_LIMIT_SECONDS,
    _validate_schema,
    canonical_json_bytes,
    sha256_bytes,
)
from autoqec_search.load import SearchIntegrityError


_IMAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def create_candidate_freeze(
    *,
    candidate_worktree: Path,
    candidate_path: Path,
    image_digest: str,
    method_config: dict,
    seed_manifest: dict,
    development_summary: dict,
    suite_commitment: dict,
    created_at: str,
) -> dict:
    _require_clean_git_worktree(candidate_worktree)
    candidate_file = _candidate_file(candidate_worktree, candidate_path)
    _require_image_digest(image_digest)
    _validate_seed_manifest(seed_manifest)

    freeze = {
        "schema_version": 1,
        "created_at": created_at,
        "git_commit": _git_head(candidate_worktree),
        "candidate_path": str(candidate_path),
        "candidate_sha256": _sha256_file(candidate_file),
        "image_digest": image_digest,
        "method_config_sha256": _hash_payload(method_config),
        "seed_manifest_sha256": _hash_payload(seed_manifest),
        "development_summary_sha256": _hash_payload(development_summary),
        "suite_commitment_sha256": _hash_payload(suite_commitment),
        "time_limit_seconds": TIME_LIMIT_SECONDS,
    }
    _validate_schema(
        "css-distance-candidate-freeze.schema.json",
        freeze,
        "candidate freeze",
    )
    return freeze


def validate_candidate_freeze(
    *,
    candidate_worktree: Path,
    freeze: dict,
    image_digest: str,
    method_config: dict,
    seed_manifest: dict,
    development_summary: dict,
    suite_commitment: dict,
) -> dict:
    if not isinstance(freeze, dict):
        raise SearchIntegrityError("candidate freeze is required")
    _validate_schema(
        "css-distance-candidate-freeze.schema.json",
        freeze,
        "candidate freeze",
    )
    _require_clean_git_worktree(candidate_worktree)
    candidate_file = _candidate_file(candidate_worktree, Path(freeze["candidate_path"]))
    _require_image_digest(image_digest)
    _validate_seed_manifest(seed_manifest)

    expected = {
        "git_commit": _git_head(candidate_worktree),
        "candidate_sha256": _sha256_file(candidate_file),
        "image_digest": image_digest,
        "method_config_sha256": _hash_payload(method_config),
        "seed_manifest_sha256": _hash_payload(seed_manifest),
        "development_summary_sha256": _hash_payload(development_summary),
        "suite_commitment_sha256": _hash_payload(suite_commitment),
        "time_limit_seconds": TIME_LIMIT_SECONDS,
    }
    for key, value in expected.items():
        if freeze[key] != value:
            raise SearchIntegrityError("candidate freeze drift")
    return {"status": "pass"}


def open_final_manifest(
    *,
    private_root: Path,
    freeze: dict | None,
    candidate_worktree: Path,
    image_digest: str,
    method_config: dict,
    seed_manifest: dict,
    development_summary: dict,
    suite_commitment: dict,
) -> dict:
    if freeze is None:
        raise SearchIntegrityError("candidate freeze is required")
    ledger = private_root / "final" / "final-run-ledger.jsonl"
    _reject_existing_final_attempt(ledger)
    validate_candidate_freeze(
        candidate_worktree=candidate_worktree,
        freeze=freeze,
        image_digest=image_digest,
        method_config=method_config,
        seed_manifest=seed_manifest,
        development_summary=development_summary,
        suite_commitment=suite_commitment,
    )
    _append_final_attempt(ledger, freeze)
    return _load_private_final_manifest(private_root)


def _load_private_final_manifest(private_root: Path) -> dict:
    with (private_root / "final" / "manifest.json").open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SearchIntegrityError("invalid final manifest")
    return payload


def _candidate_file(candidate_worktree: Path, candidate_path: Path) -> Path:
    if candidate_path.is_absolute() or ".." in candidate_path.parts:
        raise SearchIntegrityError("unsafe candidate path")
    root = candidate_worktree.resolve()
    candidate = (root / candidate_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise SearchIntegrityError("unsafe candidate path")
    if not candidate.is_file():
        raise SearchIntegrityError("candidate file is missing")
    return candidate


def _require_clean_git_worktree(candidate_worktree: Path) -> None:
    status = _git(candidate_worktree, ["status", "--porcelain"])
    if status:
        raise SearchIntegrityError("candidate worktree is dirty")


def _git_head(candidate_worktree: Path) -> str:
    head = _git(candidate_worktree, ["rev-parse", "HEAD"]).strip()
    if len(head) != 40 or any(char not in "0123456789abcdef" for char in head):
        raise SearchIntegrityError("invalid candidate git commit")
    return head


def _git(candidate_worktree: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=candidate_worktree,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise SearchIntegrityError("candidate git command failed") from error
    if result.returncode != 0:
        raise SearchIntegrityError("candidate git command failed")
    return result.stdout


def _require_image_digest(image_digest: str) -> None:
    if not isinstance(image_digest, str) or _IMAGE_DIGEST_RE.fullmatch(image_digest) is None:
        raise SearchIntegrityError("invalid image digest")


def _validate_seed_manifest(seed_manifest: dict) -> None:
    seeds = seed_manifest.get("seeds") if isinstance(seed_manifest, dict) else None
    if not isinstance(seeds, list):
        raise SearchIntegrityError("invalid seed manifest")
    if len(seeds) < MINIMUM_SEEDS:
        raise SearchIntegrityError("seed manifest requires at least 20 unique integer seeds")
    if len(set(seeds)) != len(seeds):
        raise SearchIntegrityError("seed manifest requires at least 20 unique integer seeds")
    if any(type(seed) is not int for seed in seeds):
        raise SearchIntegrityError("seed manifest requires at least 20 unique integer seeds")


def _hash_payload(payload: dict) -> str:
    return sha256_bytes(canonical_json_bytes(payload))


def _sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _reject_existing_final_attempt(ledger: Path) -> None:
    if not ledger.exists():
        return
    for line in ledger.read_text().splitlines():
        if not line.strip():
            continue
        try:
            attempt = json.loads(line)
        except json.JSONDecodeError as error:
            raise SearchIntegrityError("invalid final-run ledger") from error
        if attempt.get("attempt_type") != "infrastructure-retry":
            raise SearchIntegrityError("final holdout already opened")


def _append_final_attempt(ledger: Path, freeze: dict) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    attempt = {
        "attempt_type": "algorithm",
        "git_commit": freeze["git_commit"],
        "candidate_sha256": freeze["candidate_sha256"],
        "suite_commitment_sha256": freeze["suite_commitment_sha256"],
    }
    with ledger.open("a") as handle:
        handle.write(json.dumps(attempt, sort_keys=True) + "\n")
