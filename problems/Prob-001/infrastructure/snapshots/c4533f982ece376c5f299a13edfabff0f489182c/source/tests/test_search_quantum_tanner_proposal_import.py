from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from autoqec_search.eval_candidates import resolve_campaign_candidate_spec


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_PROPOSAL = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "valid-dihedral-d3.json"
)
CAMPAIGN_ID = "quantum-tanner-autoresearch"
UNRELATED_CANDIDATE = {
    "candidate_id": "unrelated-distance-5",
    "code_family": "rotated-surface-code",
    "parameters": {"distance": 5},
    "provenance": {"kind": "manual-fixture", "label": "unrelated-distance-5"},
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_candidate_fingerprint(instance_dir: Path) -> str:
    manifest = _load_json(instance_dir / "materialization_manifest.json")
    instance = _load_json(instance_dir / "instance.json")
    derived = instance["derived_properties"]
    payload = {
        "dimensions": {
            "kx": derived["kx"],
            "kz": derived["kz"],
            "mx": derived["mx"],
            "mz": derived["mz"],
            "n": derived["n"],
        },
        "output_hashes": {
            name: manifest["output_hashes"][name]
            for name in ("hx.json", "hz.json", "qec_code_quantum_tanner_spec.json")
        },
        "proposal_fingerprint": manifest["proposal_fingerprint"],
        "validator_fingerprint": manifest["validator"]["fingerprint"],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _write_fake_qec_code(path: Path) -> Path:
    path.write_text(
        """#!/bin/sh
set -eu
if [ "${1:-}" = "--version" ]; then printf 'fake-qec-code 1.0\n'; exit 0; fi
if [ "$6" = "hx" ]; then
  printf '%s\n' '{"format":"sparse_rows","num_cols":6,"rows":[[0,1],[2,3]]}'
elif [ "$6" = "hz" ]; then
  printf '%s\n' '{"format":"sparse_rows","num_cols":6,"rows":[[4,5]]}'
else
  echo "unexpected matrix: $6" >&2
  exit 9
fi
""",
    )
    path.chmod(0o755)
    return path


def _make_workspace(work_root: Path) -> tuple[Path, Path]:
    campaign_root = work_root / "campaigns" / "examples" / CAMPAIGN_ID
    campaign_root.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copyfile(
        REPO_ROOT / "campaigns" / "examples" / CAMPAIGN_ID / "campaign.json",
        campaign_root / "campaign.json",
    )
    _write_json(
        campaign_root / "search_space.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "mode": "explicit_list",
            "candidate_specs": [copy.deepcopy(UNRELATED_CANDIDATE)],
        },
    )
    (work_root / "results" / "search").mkdir(parents=True)
    return work_root, campaign_root / "search_space.json"


def _cli_env(*, minimal_path: bool = False) -> dict[str, str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    if minimal_path:
        env["PATH"] = "/nonexistent"
    return env


def _run_materialize(instance_root: Path, qec_code_bin: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "materialize-quantum-tanner-proposals",
            "--root",
            str(REPO_ROOT),
            "--proposal",
            str(VALID_PROPOSAL),
            "--out-root",
            str(instance_root),
            "--qec-code-bin",
            str(qec_code_bin),
            "--force",
        ],
        capture_output=True,
        text=True,
        env=_cli_env(minimal_path=True),
        cwd=REPO_ROOT,
    )


def _run_import(
    work_root: Path,
    *,
    instance_root: Path,
    search_space_path: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "import-quantum-tanner-proposal-instances",
            "--root",
            str(work_root),
            "--campaign",
            CAMPAIGN_ID,
            "--instance-root",
            str(instance_root),
            "--search-space",
            str(search_space_path),
        ],
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=REPO_ROOT,
    )


def _run_validate(work_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
        env=_cli_env(),
        cwd=REPO_ROOT,
    )


def _proposal_search_space_validator(work_root: Path) -> Draft202012Validator:
    schema = _load_json(work_root / "benchmarks" / "schemas" / "search-space.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _find_candidate(search_space: dict, candidate_id: str) -> dict:
    return next(
        candidate
        for candidate in search_space["candidate_specs"]
        if candidate["candidate_id"] == candidate_id
    )


def test_import_proposal_instances_writes_schema_valid_explicit_search_space(
    tmp_path: Path,
) -> None:
    work_root, search_space_path = _make_workspace(tmp_path / "workspace")
    qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    instance_root = work_root / "proposal-instances"

    materialize = _run_materialize(instance_root, qec_code)
    assert materialize.returncode == 0, materialize.stderr
    assert "materialized=1 failed=0" in materialize.stdout

    result = _run_import(
        work_root,
        instance_root=instance_root,
        search_space_path=search_space_path,
    )
    assert result.returncode == 0, result.stderr
    assert "imported=1" in result.stdout

    search_space = _load_json(search_space_path)
    assert UNRELATED_CANDIDATE in search_space["candidate_specs"]
    imported = _find_candidate(search_space, "valid-dihedral-d3")

    validator = _proposal_search_space_validator(work_root)
    validator.validate(search_space)

    invalid_search_space = copy.deepcopy(search_space)
    invalid_imported = _find_candidate(invalid_search_space, "valid-dihedral-d3")
    del invalid_imported["provenance"]["proposal"]["proposal_id"]
    with pytest.raises(ValidationError):
        validator.validate(invalid_search_space)

    missing_run_search_space = copy.deepcopy(search_space)
    missing_run_imported = _find_candidate(missing_run_search_space, "valid-dihedral-d3")
    del missing_run_imported["provenance"]["proposal"]["materialization_run"]
    with pytest.raises(ValidationError):
        validator.validate(missing_run_search_space)

    missing_proposal_search_space = copy.deepcopy(search_space)
    missing_proposal_imported = _find_candidate(
        missing_proposal_search_space,
        "valid-dihedral-d3",
    )
    del missing_proposal_imported["provenance"]["proposal"]
    with pytest.raises(ValidationError):
        validator.validate(missing_proposal_search_space)

    invalid_status_search_space = copy.deepcopy(search_space)
    invalid_status_imported = _find_candidate(
        invalid_status_search_space,
        "valid-dihedral-d3",
    )
    invalid_status_imported["provenance"]["proposal"]["exact_distance_status"] = "exact"
    with pytest.raises(ValidationError):
        validator.validate(invalid_status_search_space)

    missing_hash_search_space = copy.deepcopy(search_space)
    missing_hash_imported = _find_candidate(missing_hash_search_space, "valid-dihedral-d3")
    del missing_hash_imported["provenance"]["proposal"]["output_hashes"]["hx.json"]
    with pytest.raises(ValidationError):
        validator.validate(missing_hash_search_space)

    validated = _run_validate(work_root)
    assert validated.returncode == 0, validated.stderr

    candidate = resolve_campaign_candidate_spec(
        work_root,
        imported,
        campaign_id=CAMPAIGN_ID,
    )
    assert candidate.spec.code_family == "quantum-tanner-code"
    assert candidate.spec.parameters["distance"] is None
    assert candidate.instance["derived_properties"]["distance"] is None
    assert candidate.hx["format"] == "sparse_rows"
    assert candidate.hz["format"] == "sparse_rows"
    assert candidate.spec.provenance["proposal"]["proposal_id"] == "valid-dihedral-d3"

    (instance_root / "valid-dihedral-d3" / "hx.json").unlink()
    invalidated = _run_validate(work_root)
    assert invalidated.returncode != 0
    assert "missing hx artifact" in invalidated.stderr


def test_import_proposal_instances_resolves_null_distance_candidate(tmp_path: Path) -> None:
    work_root, search_space_path = _make_workspace(tmp_path / "workspace")
    qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    instance_root = work_root / "proposal-instances"

    materialize = _run_materialize(instance_root, qec_code)
    assert materialize.returncode == 0, materialize.stderr

    result = _run_import(
        work_root,
        instance_root=instance_root,
        search_space_path=search_space_path,
    )
    assert result.returncode == 0, result.stderr

    search_space = _load_json(search_space_path)
    imported = _find_candidate(search_space, "valid-dihedral-d3")
    candidate = resolve_campaign_candidate_spec(
        work_root,
        imported,
        campaign_id=CAMPAIGN_ID,
    )

    assert candidate.spec.parameters["distance"] is None
    assert candidate.instance["parameters"]["distance"] is None
    assert candidate.instance["derived_properties"]["distance"] is None
    assert candidate.spec.provenance["proposal"]["proposal_id"] == "valid-dihedral-d3"


def test_import_proposal_instances_candidate_fingerprint_is_path_independent(
    tmp_path: Path,
) -> None:
    qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    fingerprints: list[str] = []

    for workspace_name in ("workspace-a", "workspace-b"):
        work_root, search_space_path = _make_workspace(tmp_path / workspace_name)
        instance_root = work_root / "proposal-instances"

        materialize = _run_materialize(instance_root, qec_code)
        assert materialize.returncode == 0, materialize.stderr

        result = _run_import(
            work_root,
            instance_root=instance_root,
            search_space_path=search_space_path,
        )
        assert result.returncode == 0, result.stderr

        imported = _find_candidate(
            _load_json(search_space_path),
            "valid-dihedral-d3",
        )
        fingerprints.append(imported["provenance"]["proposal"]["candidate_fingerprint"])

    assert fingerprints[0] == fingerprints[1]


def test_import_proposal_instances_creates_missing_search_space(tmp_path: Path) -> None:
    work_root, search_space_path = _make_workspace(tmp_path / "workspace")
    search_space_path.unlink()
    qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    instance_root = work_root / "proposal-instances"

    materialize = _run_materialize(instance_root, qec_code)
    assert materialize.returncode == 0, materialize.stderr

    result = _run_import(
        work_root,
        instance_root=instance_root,
        search_space_path=search_space_path,
    )
    assert result.returncode == 0, result.stderr
    assert "imported=1 preserved=0" in result.stdout

    search_space = _load_json(search_space_path)
    assert search_space["mode"] == "explicit_list"
    assert search_space["campaign_id"] == CAMPAIGN_ID
    assert [candidate["candidate_id"] for candidate in search_space["candidate_specs"]] == [
        "valid-dihedral-d3"
    ]
    _proposal_search_space_validator(work_root).validate(search_space)

    validated = _run_validate(work_root)
    assert validated.returncode == 0, validated.stderr


def test_import_proposal_instances_rejects_non_explicit_search_space(
    tmp_path: Path,
) -> None:
    work_root, search_space_path = _make_workspace(tmp_path / "workspace")
    qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    instance_root = work_root / "proposal-instances"

    materialize = _run_materialize(instance_root, qec_code)
    assert materialize.returncode == 0, materialize.stderr

    search_space = _load_json(search_space_path)
    search_space["mode"] = "grid"
    _write_json(search_space_path, search_space)

    result = _run_import(
        work_root,
        instance_root=instance_root,
        search_space_path=search_space_path,
    )
    assert result.returncode != 0
    assert "search space mode must be explicit_list" in result.stderr


def test_import_proposal_instances_rejects_matrix_dimension_mismatch(
    tmp_path: Path,
) -> None:
    work_root, search_space_path = _make_workspace(tmp_path / "workspace")
    qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    instance_root = work_root / "proposal-instances"

    materialize = _run_materialize(instance_root, qec_code)
    assert materialize.returncode == 0, materialize.stderr

    instance_path = instance_root / "valid-dihedral-d3" / "instance.json"
    instance = _load_json(instance_path)
    instance["derived_properties"]["mx"] = 999
    _write_json(instance_path, instance)

    manifest_path = instance_root / "valid-dihedral-d3" / "materialization_manifest.json"
    manifest = _load_json(manifest_path)
    manifest["output_hashes"]["instance.json"] = _file_sha256(instance_path)
    _write_json(manifest_path, manifest)

    result = _run_import(
        work_root,
        instance_root=instance_root,
        search_space_path=search_space_path,
    )
    assert result.returncode != 0
    assert "hx row count mismatch" in result.stderr


def test_import_proposal_instances_rejects_duplicate_fingerprints(tmp_path: Path) -> None:
    work_root, search_space_path = _make_workspace(tmp_path / "workspace")
    qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    instance_root = work_root / "proposal-instances"

    materialize = _run_materialize(instance_root, qec_code)
    assert materialize.returncode == 0, materialize.stderr

    original_dir = instance_root / "valid-dihedral-d3"
    duplicate_dir = instance_root / "valid-dihedral-d3-copy"
    shutil.copytree(original_dir, duplicate_dir)

    duplicate_instance_path = duplicate_dir / "instance.json"
    duplicate_instance = _load_json(duplicate_instance_path)
    duplicate_instance["candidate_id"] = "valid-dihedral-d3-copy"
    duplicate_instance["instance_id"] = "valid-dihedral-d3-copy"
    _write_json(duplicate_instance_path, duplicate_instance)

    manifest_path = duplicate_dir / "materialization_manifest.json"
    manifest = _load_json(manifest_path)
    manifest["candidate_id"] = "valid-dihedral-d3-copy"
    manifest["output_hashes"]["instance.json"] = _file_sha256(duplicate_instance_path)
    _write_json(manifest_path, manifest)

    result = _run_import(
        work_root,
        instance_root=instance_root,
        search_space_path=search_space_path,
    )
    assert result.returncode != 0
    assert "duplicate proposal fingerprint" in result.stderr


def test_import_proposal_instances_rejects_duplicate_candidate_fingerprints(
    tmp_path: Path,
) -> None:
    work_root, search_space_path = _make_workspace(tmp_path / "workspace")
    qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    instance_root = work_root / "proposal-instances"

    materialize = _run_materialize(instance_root, qec_code)
    assert materialize.returncode == 0, materialize.stderr

    imported_dir = instance_root / "valid-dihedral-d3"
    existing_dir = instance_root / "existing-proposal-derived-collision"
    shutil.copytree(imported_dir, existing_dir)

    existing_instance_path = existing_dir / "instance.json"
    existing_instance = _load_json(existing_instance_path)
    existing_instance["candidate_id"] = "existing-proposal-derived-collision"
    existing_instance["instance_id"] = "existing-proposal-derived-collision"
    existing_instance["proposal_id"] = "existing-proposal-derived-collision"
    _write_json(existing_instance_path, existing_instance)

    existing_manifest_path = existing_dir / "materialization_manifest.json"
    existing_manifest = _load_json(existing_manifest_path)
    existing_manifest["candidate_id"] = "existing-proposal-derived-collision"
    existing_manifest["proposal_id"] = "existing-proposal-derived-collision"
    existing_manifest["proposal_fingerprint"] = "existing-proposal-fingerprint"
    existing_manifest["validator"]["fingerprint"] = "existing-validator-fingerprint"
    existing_manifest["output_hashes"]["instance.json"] = _file_sha256(existing_instance_path)
    _write_json(existing_manifest_path, existing_manifest)

    candidate_fingerprint = _expected_candidate_fingerprint(imported_dir)

    search_space = _load_json(search_space_path)
    search_space["candidate_specs"].append(
        {
            "candidate_id": "existing-proposal-derived-collision",
            "code_family": "quantum-tanner-code",
            "instance_path": str(existing_dir.relative_to(work_root)),
            "provenance": {
                "kind": "proposal-derived",
                "label": "existing-proposal-derived-collision",
                "proposal": {
                    "candidate_fingerprint": candidate_fingerprint,
                    "exact_distance_status": existing_manifest["exact_distance_status"],
                    "materialization_manifest": str(
                        existing_manifest_path.relative_to(work_root)
                    ),
                    "materialization_run": {
                        "qec_code": existing_manifest["qec_code"],
                    },
                    "materializer_version": existing_manifest["materializer_version"],
                    "output_hashes": {
                        name: existing_manifest["output_hashes"][name]
                        for name in sorted(existing_manifest["output_hashes"])
                    },
                    "proposal_id": "existing-proposal-derived-collision",
                    "proposal_fingerprint": existing_manifest["proposal_fingerprint"],
                    "qec_code_spec_path": str(
                        (existing_dir / "qec_code_quantum_tanner_spec.json").relative_to(
                            work_root
                        )
                    ),
                    "validator_fingerprint": existing_manifest["validator"][
                        "fingerprint"
                    ],
                },
            },
        }
    )
    _write_json(search_space_path, search_space)

    result = _run_import(
        work_root,
        instance_root=instance_root,
        search_space_path=search_space_path,
    )
    assert result.returncode != 0
    assert "duplicate candidate fingerprint" in result.stderr
