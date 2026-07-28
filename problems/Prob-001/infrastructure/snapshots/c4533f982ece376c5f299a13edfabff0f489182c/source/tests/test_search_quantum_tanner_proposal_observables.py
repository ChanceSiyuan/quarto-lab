from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from autoqec_search.eval_candidates import resolve_campaign_candidate_spec
from autoqec_search import quantum_tanner_proposal_observables as proposal_observables_module
from autoqec_search.screening import screen_upper_bound_candidate
from autoqec_search.structure import gf2_rank, gf2_vector_in_kernel, matrix_data


REPO_ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ID = "quantum-tanner-autoresearch"
QT_TASK = {
    "id": "quantum-tanner-css-memory-x-rbposd-p001-v1",
    "input_type": "css",
    "css_memory": {
        "basis": "x",
        "observables": "optional",
        "schedule": "greedy",
        "seed": 12345,
    },
}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _cli_env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}


def _proposal_payload(candidate_id: str) -> dict:
    return {
        "candidate_fingerprint": f"{candidate_id}-candidate-fingerprint",
        "exact_distance_status": "unknown",
        "materialization_manifest": f"proposal-instances/{candidate_id}/materialization_manifest.json",
        "materialization_run": {"qec_code": {"bin": "/unused/qec-code"}},
        "materializer_version": "test-materializer",
        "output_hashes": {
            "hx.json": f"{candidate_id}-hx",
            "hz.json": f"{candidate_id}-hz",
            "instance.json": f"{candidate_id}-instance",
            "qec_code_quantum_tanner_spec.json": f"{candidate_id}-spec",
        },
        "proposal_fingerprint": f"{candidate_id}-proposal-fingerprint",
        "proposal_id": candidate_id,
        "qec_code_spec_path": f"proposal-instances/{candidate_id}/qec_code_quantum_tanner_spec.json",
        "validator_fingerprint": f"{candidate_id}-validator-fingerprint",
    }


def _make_workspace(
    work_root: Path,
    *,
    candidate_id: str = "proposal-k2",
    witness_basis: str = "x",
    existing_observables: dict | None = None,
    empty_checks: bool = False,
) -> tuple[Path, Path, Path]:
    campaign_root = work_root / "campaigns" / "examples" / CAMPAIGN_ID
    campaign_root.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copyfile(
        REPO_ROOT / "campaigns" / "examples" / CAMPAIGN_ID / "campaign.json",
        campaign_root / "campaign.json",
    )
    (work_root / "results" / "search").mkdir(parents=True)

    instance_dir = work_root / "proposal-instances" / candidate_id
    hx_rows = [] if empty_checks else [[2]]
    hz_rows = [] if empty_checks else [[3]]
    expected_k = 4 if empty_checks else 2
    _write_json(
        instance_dir / "hx.json",
        {"format": "sparse_rows", "num_cols": 4, "rows": hx_rows},
    )
    _write_json(
        instance_dir / "hz.json",
        {"format": "sparse_rows", "num_cols": 4, "rows": hz_rows},
    )
    artifacts = {"hx": "hx.json", "hz": "hz.json"}
    if existing_observables is not None:
        artifacts["observables_x"] = "observables_x.json"
        _write_json(instance_dir / "observables_x.json", existing_observables)
    _write_json(
        instance_dir / "instance.json",
        {
            "artifacts": artifacts,
            "candidate_id": candidate_id,
            "code_id": "quantum-tanner-code",
            "derived_properties": {
                "distance": None,
                "kx": None,
                "kz": None,
                "mx": len(hx_rows),
                "mz": len(hz_rows),
                "n": 4,
            },
            "instance_id": candidate_id,
            "instance_kind": "finite_css_instance",
            "k": expected_k,
            "matrix_format": "sparse_rows_json",
            "n": 4,
            "parameters": {"distance": None},
            "proposal_id": candidate_id,
            "provenance": {"materializer": {"version": "test-materializer"}},
            "quantum_tanner_spec": "qec_code_quantum_tanner_spec.json",
        },
    )
    _write_json(instance_dir / "qec_code_quantum_tanner_spec.json", {"fixture_id": candidate_id})
    _write_json(
        instance_dir / "materialization_manifest.json",
        {
            "candidate_id": candidate_id,
            "exact_distance_status": "unknown",
            "materializer_version": "test-materializer",
            "output_hashes": _proposal_payload(candidate_id)["output_hashes"],
            "proposal_fingerprint": _proposal_payload(candidate_id)["proposal_fingerprint"],
            "proposal_id": candidate_id,
            "qec_code": {"bin": "/unused/qec-code"},
            "validator": {
                "fingerprint": _proposal_payload(candidate_id)["validator_fingerprint"],
                "version": "test-validator",
            },
        },
    )

    witness_path = campaign_root / "witnesses" / f"{candidate_id}-{witness_basis}-witness.json"
    _write_json(witness_path, {"basis": witness_basis, "vector": [1, 0, 0, 0]})
    search_space_path = campaign_root / "search_space.json"
    _write_json(
        search_space_path,
        {
            "campaign_id": CAMPAIGN_ID,
            "mode": "explicit_list",
            "candidate_specs": [
                {
                    "candidate_id": candidate_id,
                    "code_family": "quantum-tanner-code",
                    "instance_path": f"proposal-instances/{candidate_id}",
                    "upper_bound_witness_path": str(witness_path.relative_to(work_root)),
                    "provenance": {
                        "kind": "proposal-derived",
                        "label": candidate_id,
                        "proposal": _proposal_payload(candidate_id),
                    },
                }
            ],
        },
    )
    return work_root, search_space_path, instance_dir


def _run_complete(work_root: Path, search_space_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "complete-quantum-tanner-proposal-observables",
            "--root",
            str(work_root),
            "--search-space",
            str(search_space_path),
            "--basis",
            "x",
            "--qec-code-bin",
            "/unused/qec-code",
            "--force",
        ],
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=REPO_ROOT,
    )


def _run_complete_without_force(
    work_root: Path,
    search_space_path: Path,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        "-m",
        "autoqec_search.cli",
        "complete-quantum-tanner-proposal-observables",
        "--root",
        str(work_root),
        "--search-space",
        str(search_space_path),
        "--basis",
        "x",
    ]
    return subprocess.run(
        args,
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


def _sparse_rows_to_dense_rows(payload: dict) -> list[list[int]]:
    rows = []
    for sparse_row in payload["rows"]:
        dense_row = [0] * payload["num_cols"]
        for column in sparse_row:
            dense_row[column] = 1
        rows.append(dense_row)
    return rows


def _assert_valid_x_observables(instance_dir: Path, expected_rows: int) -> None:
    hx = matrix_data(_load_json(instance_dir / "hx.json"), "hx.json")
    hz = matrix_data(_load_json(instance_dir / "hz.json"), "hz.json")
    observables = _load_json(instance_dir / "observables_x.json")
    assert observables["format"] == "sparse_rows"
    assert observables["num_cols"] == 4
    assert len(observables["rows"]) == expected_rows
    dense_rows = _sparse_rows_to_dense_rows(observables)
    for row in dense_rows:
        assert gf2_vector_in_kernel(hz, row)
    assert gf2_rank([*hx, *dense_rows]) == gf2_rank(hx) + expected_rows


def test_complete_proposal_observables_writes_exactly_k_valid_x_rows(
    tmp_path: Path,
) -> None:
    work_root, search_space_path, instance_dir = _make_workspace(tmp_path / "workspace")

    result = _run_complete(work_root, search_space_path)

    assert result.returncode == 0, result.stderr
    assert "completed=1" in result.stdout
    _assert_valid_x_observables(instance_dir, expected_rows=2)
    instance = _load_json(instance_dir / "instance.json")
    assert instance["artifacts"]["observables_x"] == "observables_x.json"
    provenance = _load_json(instance_dir / "observables_x_provenance.json")
    assert provenance["method"] == "complete_logical_observable_basis"
    assert provenance["basis"] == "x"
    assert provenance["input_witness"]["path"].endswith("proposal-k2-x-witness.json")

    validated = _run_validate(work_root)
    assert validated.returncode == 0, validated.stderr

    search_space = _load_json(search_space_path)
    candidate = resolve_campaign_candidate_spec(
        work_root,
        search_space["candidate_specs"][0],
        campaign_id=CAMPAIGN_ID,
    )
    assert candidate.observables_x == _load_json(instance_dir / "observables_x.json")


def test_complete_proposal_observables_skips_candidate_without_witness(
    tmp_path: Path,
) -> None:
    work_root, search_space_path, witnessed_instance_dir = _make_workspace(
        tmp_path / "workspace",
        candidate_id="proposal-with-witness",
    )
    missing_candidate_id = "proposal-without-witness"
    missing_instance_dir = work_root / "proposal-instances" / missing_candidate_id
    shutil.copytree(witnessed_instance_dir, missing_instance_dir)
    missing_instance = _load_json(missing_instance_dir / "instance.json")
    missing_instance["candidate_id"] = missing_candidate_id
    missing_instance["instance_id"] = missing_candidate_id
    missing_instance["proposal_id"] = missing_candidate_id
    _write_json(missing_instance_dir / "instance.json", missing_instance)
    _write_json(
        missing_instance_dir / "qec_code_quantum_tanner_spec.json",
        {"fixture_id": missing_candidate_id},
    )
    missing_manifest = _load_json(missing_instance_dir / "materialization_manifest.json")
    missing_proposal = _proposal_payload(missing_candidate_id)
    missing_manifest.update(
        {
            "candidate_id": missing_candidate_id,
            "output_hashes": missing_proposal["output_hashes"],
            "proposal_fingerprint": missing_proposal["proposal_fingerprint"],
            "proposal_id": missing_candidate_id,
            "validator": {
                "fingerprint": missing_proposal["validator_fingerprint"],
                "version": "test-validator",
            },
        }
    )
    _write_json(missing_instance_dir / "materialization_manifest.json", missing_manifest)

    search_space = _load_json(search_space_path)
    search_space["candidate_specs"].append(
        {
            "candidate_id": missing_candidate_id,
            "code_family": "quantum-tanner-code",
            "instance_path": f"proposal-instances/{missing_candidate_id}",
            "provenance": {
                "kind": "proposal-derived",
                "label": missing_candidate_id,
                "proposal": missing_proposal,
            },
        }
    )
    _write_json(search_space_path, search_space)

    result = _run_complete(work_root, search_space_path)

    assert result.returncode == 0, result.stderr
    assert "completed=1" in result.stdout
    assert "skipped=1" in result.stdout
    _assert_valid_x_observables(witnessed_instance_dir, expected_rows=2)
    assert not (missing_instance_dir / "observables_x.json").exists()
    assert not (missing_instance_dir / "observables_x_provenance.json").exists()


def test_completed_sparse_proposal_candidate_screens_without_dense_width_lookup(
    tmp_path: Path,
) -> None:
    work_root, search_space_path, _instance_dir = _make_workspace(tmp_path / "workspace")
    result = _run_complete(work_root, search_space_path)
    assert result.returncode == 0, result.stderr
    search_space = _load_json(search_space_path)
    candidate_spec = search_space["candidate_specs"][0]
    candidate = resolve_campaign_candidate_spec(
        work_root,
        candidate_spec,
        campaign_id=CAMPAIGN_ID,
    )

    decision = screen_upper_bound_candidate(
        work_root,
        candidate=candidate,
        candidate_spec=candidate_spec,
        benchmark_task=QT_TASK,
    )

    assert decision.screening_status == "admitted"
    assert decision.reason == "verified_upper_bound_witness"
    assert decision.observables_x_override is not None
    assert decision.observables_x_override["format"] == "sparse_rows"
    assert decision.observables_x_override["num_cols"] == 4
    assert len(decision.observables_x_override["rows"]) == 2


def test_complete_proposal_observables_writes_root_relative_provenance(
    tmp_path: Path,
) -> None:
    work_root, search_space_path, instance_dir = _make_workspace(tmp_path / "workspace")

    result = _run_complete(work_root, search_space_path)

    assert result.returncode == 0, result.stderr
    provenance = _load_json(instance_dir / "observables_x_provenance.json")
    assert provenance["command_options"]["root"] == "."
    assert (
        provenance["command_options"]["search_space_path"]
        == "campaigns/examples/quantum-tanner-autoresearch/search_space.json"
    )
    assert (
        provenance["input_witness"]["path"]
        == "campaigns/examples/quantum-tanner-autoresearch/witnesses/proposal-k2-x-witness.json"
    )
    assert str(work_root) not in json.dumps(provenance, sort_keys=True)


def test_complete_proposal_observables_rejects_incomplete_x_rows(
    tmp_path: Path,
) -> None:
    incomplete = {"format": "sparse_rows", "num_cols": 4, "rows": [[0]]}
    work_root, search_space_path, _instance_dir = _make_workspace(
        tmp_path / "workspace",
        existing_observables=incomplete,
    )

    result = _run_complete_without_force(work_root, search_space_path)

    assert result.returncode != 0
    assert "explicit X observables define 1 rows, expected k = 2" in result.stderr


def test_complete_proposal_observables_rejects_z_like_witness_for_memory_x(
    tmp_path: Path,
) -> None:
    work_root, search_space_path, instance_dir = _make_workspace(
        tmp_path / "workspace",
        witness_basis="z",
    )

    result = _run_complete(work_root, search_space_path)

    assert result.returncode != 0
    assert "incompatible" in result.stderr
    assert not (instance_dir / "observables_x.json").exists()


def test_complete_proposal_observables_preserves_width_from_empty_matrix_metadata(
    tmp_path: Path,
) -> None:
    work_root, search_space_path, instance_dir = _make_workspace(
        tmp_path / "workspace",
        candidate_id="proposal-k4-empty",
        empty_checks=True,
    )

    result = _run_complete(work_root, search_space_path)

    assert result.returncode == 0, result.stderr
    _assert_valid_x_observables(instance_dir, expected_rows=4)
    observables_payload = _load_json(instance_dir / "observables_x.json")
    provenance_payload = _load_json(instance_dir / "observables_x_provenance.json")
    assert observables_payload["num_cols"] == 4
    assert len(observables_payload["rows"]) == 4
    assert provenance_payload["matrix_dimensions"]["n"] == 4
    assert provenance_payload["computed_k"] == 4


def test_complete_proposal_observables_rejects_witness_symlink_outside_root(
    tmp_path: Path,
) -> None:
    work_root, search_space_path, instance_dir = _make_workspace(tmp_path / "workspace")
    outside_witness_path = tmp_path / "outside-witness.json"
    _write_json(outside_witness_path, {"basis": "x", "vector": [1, 0, 0, 0]})

    search_space = _load_json(search_space_path)
    witness_repo_path = work_root / search_space["candidate_specs"][0]["upper_bound_witness_path"]
    witness_repo_path.unlink()
    witness_repo_path.symlink_to(outside_witness_path)

    result = _run_complete(work_root, search_space_path)

    assert result.returncode != 0
    assert "upper_bound_witness_path" in result.stderr
    assert (
        "repository root" in result.stderr
        or "safe relative path" in result.stderr
    )
    assert not (instance_dir / "observables_x.json").exists()


def test_write_completion_plan_restores_original_files_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance_dir = tmp_path / "proposal-instances" / "proposal-k2"
    instance_dir.mkdir(parents=True)
    observables_path = instance_dir / "observables_x.json"
    provenance_path = instance_dir / "observables_x_provenance.json"
    instance_path = instance_dir / "instance.json"
    sentinel_path = instance_dir / "sentinel.txt"

    original_observables = {"format": "sparse_rows", "num_cols": 4, "rows": [[0], [1]]}
    original_provenance = {"method": "old-method"}
    original_instance = {"artifacts": {"observables_x": "observables_x.json"}, "k": 2}
    _write_json(observables_path, original_observables)
    _write_json(provenance_path, original_provenance)
    _write_json(instance_path, original_instance)
    sentinel_path.write_text("keep\n")

    plan = proposal_observables_module._CompletionPlan(
        completion=proposal_observables_module.CompletedProposalObservables(
            candidate_id="proposal-k2",
            instance_dir=instance_dir,
            observables_path=observables_path,
            provenance_path=provenance_path,
            row_count=2,
        ),
        observables_payload={"format": "sparse_rows", "num_cols": 4, "rows": [[0, 1], [0, 2]]},
        instance_payload={"artifacts": {"observables_x": "observables_x.json"}, "k": 2},
        provenance_payload={"method": "new-method"},
    )

    original_replace = Path.replace
    failure_state = {"raised": False}

    def replace_with_instance_failure(self: Path, target: Path) -> Path:
        if Path(target) == instance_path and not failure_state["raised"]:
            failure_state["raised"] = True
            raise OSError("simulated instance publish failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", replace_with_instance_failure)

    with pytest.raises(OSError, match="simulated instance publish failure"):
        proposal_observables_module._write_completion_plan(plan)

    assert _load_json(observables_path) == original_observables
    assert _load_json(provenance_path) == original_provenance
    assert _load_json(instance_path) == original_instance
    assert sentinel_path.read_text() == "keep\n"
