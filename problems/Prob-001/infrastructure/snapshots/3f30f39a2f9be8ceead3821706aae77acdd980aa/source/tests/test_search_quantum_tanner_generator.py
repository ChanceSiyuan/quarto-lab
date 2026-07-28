from __future__ import annotations

import json
import os
import subprocess
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from autoqec_search.cli import main
from autoqec_search.quantum_tanner_catalog import (
    load_quantum_tanner_fixture_catalog,
    resolve_quantum_tanner_fixture_entry,
    validate_quantum_tanner_fixture_catalog,
)
from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_generator import (
    emit_quantum_tanner_autoresearch_files,
    generate_quantum_tanner_sweep,
    load_quantum_tanner_sweep_config,
    materialize_quantum_tanner_sweep,
    normalize_quantum_tanner_sweep_config,
    plan_quantum_tanner_sweep_generation,
    render_quantum_tanner_generation_summary,
    render_quantum_tanner_sweep_summary,
)
from autoqec_search import quantum_tanner_generator as qtg


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "quantum_tanner_sweep" / "good.json"
GENERATED_QT_ROOT = Path("/tmp/autoqec-generated-qt-root")


def _payload(**updates: object) -> dict[str, object]:
    payload = json.loads(FIXTURE.read_text())
    payload.update(updates)
    return payload


def _temp_generation_payload(tmp_path: Path, **updates: object) -> dict[str, object]:
    root_name = tmp_path.name
    campaign_dir = tmp_path.parent / "campaigns" / root_name
    campaign_dir.mkdir(parents=True, exist_ok=True)
    campaign_path = campaign_dir / "campaign.json"
    if not campaign_path.exists():
        campaign_path.write_text(
            json.dumps(
                {
                    "id": "quantum-tanner-autoresearch",
                    "title": "Temporary Quantum Tanner Autoresearch",
                    "objective": "Temporary test campaign for generated Tanner sweeps.",
                    "family_id": "quantum-tanner-code",
                    "default_suite_id": "quantum-tanner-rbposd-p001-v1",
                    "budget": {"wall_clock_seconds": 3600, "max_candidates": 2},
                    "stop_conditions": {
                        "max_candidates": 2,
                        "max_wall_clock_seconds": 3600,
                    },
                    "random_seed_policy": {"mode": "fixed", "seed": 7},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    payload = _payload(
        output_root=f"{root_name}/generated",
        spec_root=f"{root_name}/generated/quantum_tanner_specs",
        instance_root=f"{root_name}/instances",
        catalog_path=f"{root_name}/generated_fixture_catalog.json",
        search_space_path=f"campaigns/{root_name}/search_space.json",
        distance_ladder_manifest_path=f"{root_name}/generated-ladder.json",
    )
    payload.update(updates)
    return payload


def _copy_generation_workspace(work_root: Path) -> Path:
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    return work_root


def _workspace_generation_payload(work_root: Path, **updates: object) -> dict[str, object]:
    payload = _payload(
        output_root="campaigns/examples/quantum-tanner-autoresearch/generated",
        spec_root="campaigns/examples/quantum-tanner-autoresearch/generated/quantum_tanner_specs",
        instance_root="benchmarks/distance_ladders/generated-quantum-tanner/instances",
        catalog_path="campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json",
        search_space_path="campaigns/examples/quantum-tanner-autoresearch/search_space.json",
        distance_ladder_manifest_path="benchmarks/distance_ladders/generated-quantum-tanner.json",
        qec_code_bin=str(_write_fake_qec_code(work_root / "qec-code")),
        distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
    )
    payload.update(updates)
    return payload


def _prepare_generated_quantum_tanner_workspace(
    work_root: Path,
    *,
    clean_witnesses: bool = True,
) -> tuple[Path, object]:
    work_root = _copy_generation_workspace(work_root)
    config = normalize_quantum_tanner_sweep_config(_workspace_generation_payload(work_root))
    generate_quantum_tanner_sweep(
        work_root,
        config,
        dry_run=False,
        materialize=True,
        force=True,
    )
    if clean_witnesses:
        search_space_path = work_root / config.search_space_path
        search_space = json.loads(search_space_path.read_text())
        for candidate_spec in search_space["candidate_specs"]:
            if isinstance(candidate_spec, dict):
                candidate_spec.pop("upper_bound_witness_path", None)
        search_space_path.write_text(json.dumps(search_space, indent=2, sort_keys=True) + "\n")

        witness_root = work_root / "campaigns/examples/quantum-tanner-autoresearch/witnesses"
        if witness_root.is_dir():
            for witness_path in witness_root.glob("*.json"):
                witness_path.unlink()
    return work_root, config


def _clone_generated_fixture_entry(
    work_root: Path,
    catalog_path: Path,
    *,
    source_candidate_id: str,
    candidate_id: str,
) -> dict[str, object]:
    catalog = json.loads((work_root / catalog_path).read_text())
    source_entry = next(
        entry for entry in catalog["entries"] if entry["candidate_id"] == source_candidate_id
    )
    source_fixture_root = Path(source_entry["source_fixture_path"])
    cloned_fixture_root = source_fixture_root.parent / candidate_id
    shutil.copytree(work_root / source_fixture_root, work_root / cloned_fixture_root)
    instance_path = work_root / cloned_fixture_root / "instance.json"
    instance_payload = json.loads(instance_path.read_text())
    instance_payload["instance_id"] = candidate_id
    instance_path.write_text(json.dumps(instance_payload, indent=2, sort_keys=True) + "\n")

    cloned_entry = dict(source_entry)
    cloned_entry["candidate_id"] = candidate_id
    cloned_entry["hx"] = str(cloned_fixture_root / "hx.json")
    cloned_entry["hz"] = str(cloned_fixture_root / "hz.json")
    cloned_entry["source_fixture_path"] = str(cloned_fixture_root)
    cloned_entry["source_instance"] = str(cloned_fixture_root / "instance.json")
    cloned_entry["provenance"] = dict(source_entry["provenance"], label=candidate_id)
    return cloned_entry


def _write_config(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def _distance_ladder_exporter_bin() -> Path:
    binary = REPO_ROOT / "target" / "debug" / "autoqec-distance-ladder"
    if not binary.exists():
        subprocess.run(
            ["cargo", "build", "--bin", "autoqec-distance-ladder", "--quiet"],
            cwd=REPO_ROOT,
            check=True,
        )
    return binary


def _write_fake_qec_code(
    path: Path,
    *,
    wrong_hx_width: bool = False,
    wrong_hx_distances: tuple[int, ...] = (),
) -> Path:
    wrong_flag = "1" if wrong_hx_width else "0"
    wrong_distances = " ".join(str(distance) for distance in wrong_hx_distances)
    path.write_text(
        f"""#!/bin/sh
set -eu
if [ "$1" != "code" ] || [ "$2" != "css" ] || [ "$3" != "quantum-tanner" ]; then
  echo "unexpected qec-code args: $*" >&2
  exit 9
fi
spec="$5"
matrix="$6"
distance="$(basename "$spec" .json | sed 's/toric-d//')"
n=$((distance * distance))
wrong_distance_flag=0
for wrong_distance in {wrong_distances}; do
  if [ "$distance" = "$wrong_distance" ]; then
    wrong_distance_flag=1
    break
  fi
done
if [ "$matrix" = "hx" ] && [ "{wrong_flag}" = "1" ]; then
  n=$((n + 1))
elif [ "$matrix" = "hx" ] && [ "$wrong_distance_flag" = "1" ]; then
  n=$((n + 1))
fi
case "$matrix" in
  hx)
    i=0
    rows=""
    while [ "$i" -le $((distance * distance - 3)) ]; do
      if [ -n "$rows" ]; then
        rows="$rows,"
      fi
      rows="$rows[$i]"
      i=$((i + 1))
    done
    printf '{{"format":"sparse_rows","num_cols":%s,"rows":[%s]}}\\n' "$n" "$rows"
    ;;
  hz)
    printf '{{"format":"sparse_rows","num_cols":%s,"rows":[]}}\\n' "$n"
    ;;
  *)
    echo "unexpected matrix: $matrix" >&2
    exit 9
    ;;
esac
""",
    )
    path.chmod(0o755)
    return path


def _write_fake_distance_ladder_exporter(path: Path, *, sentinel: Path) -> Path:
    path.write_text(
        f"""#!/bin/sh
set -eu
touch "{sentinel}"
""",
    )
    path.chmod(0o755)
    return path


def _write_fake_random_window_qec_code(path: Path) -> Path:
    path.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def _arg_value(flag: str) -> str:
    try:
        return sys.argv[sys.argv.index(flag) + 1]
    except (ValueError, IndexError) as exc:
        raise SystemExit(f"missing expected flag: {flag}") from exc


hx_path = Path(_arg_value("--hx"))
hx_payload = json.loads(hx_path.read_text())
width = int(hx_payload["num_cols"])
vector = [0] * width
vector[-1] = 1
payload = {
    "status": "completed",
    "method": "random-window-upper-bound",
    "bound_type": "upper",
    "upper_bound": 1,
    "logical_class": "x_like",
    "witness": {
        "x": vector,
        "z": [0] * width,
        "weight": 1,
    },
    "options": {
        "iterations": int(_arg_value("--iterations")),
        "restarts": int(_arg_value("--restarts")),
        "seed": int(_arg_value("--seed")),
    },
    "provenance": {
        "tool": "fake-random-window-qec-code",
    },
}
print(json.dumps(payload))
""",
    )
    path.chmod(0o755)
    return path


def _write_fake_random_window_qec_code_result(
    path: Path,
    *,
    logical_class: str,
) -> Path:
    if logical_class == "x_like":
        witness_block = """
    "witness": {
        "x": vector,
        "z": [0] * width,
        "weight": 1,
    },
"""
    elif logical_class == "z_like":
        witness_block = """
    "witness": {
        "x": [0] * width,
        "z": vector,
        "weight": 1,
    },
"""
    else:
        raise ValueError(f"unsupported logical_class for test helper: {logical_class}")
    path.write_text(
        f"""#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def _arg_value(flag: str) -> str:
    try:
        return sys.argv[sys.argv.index(flag) + 1]
    except (ValueError, IndexError) as exc:
        raise SystemExit(f"missing expected flag: {{flag}}") from exc


hx_path = Path(_arg_value("--hx"))
hx_payload = json.loads(hx_path.read_text())
width = int(hx_payload["num_cols"])
vector = [0] * width
vector[-1] = 1
payload = {{
    "status": "completed",
    "method": "random-window-upper-bound",
    "bound_type": "upper",
    "upper_bound": 1,
    "logical_class": "{logical_class}",
{witness_block}    "options": {{
        "iterations": int(_arg_value("--iterations")),
        "restarts": int(_arg_value("--restarts")),
        "seed": int(_arg_value("--seed")),
    }},
    "provenance": {{
        "tool": "fake-random-window-qec-code",
    }},
}}
print(json.dumps(payload))
""",
    )
    path.chmod(0o755)
    return path


def _run_cli(config_path: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate-quantum-tanner-sweep",
            "--config",
            str(config_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def _run_generate_cli(
    config_path: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    root = config_path.parent.parent
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "generate-quantum-tanner-sweep",
            "--config",
            str(config_path),
            "--root",
            str(root),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def _run_generate_candidates_cli(
    root: Path,
    config_path: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "generate-quantum-tanner-candidates",
            "--root",
            str(root),
            "--config",
            str(config_path),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def _run_attach_witnesses_cli(
    root: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "attach-quantum-tanner-witnesses",
            "--root",
            str(root),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def _assert_manifest_entry(
    entry: dict[str, object],
    *,
    instance_id: str,
    code_id: str,
    qec_code_spec: str,
    quantum_tanner_spec: str,
    n: int,
    k: int,
    expected_distance: int,
    expected_bound_type: str,
) -> None:
    assert set(entry) == {
        "instance_id",
        "code_id",
        "qec_code_spec",
        "quantum_tanner_spec",
        "n",
        "k",
        "expected_distance",
        "expected_bound_type",
    }
    assert entry == {
        "instance_id": instance_id,
        "code_id": code_id,
        "qec_code_spec": qec_code_spec,
        "quantum_tanner_spec": quantum_tanner_spec,
        "n": n,
        "k": k,
        "expected_distance": expected_distance,
        "expected_bound_type": expected_bound_type,
    }


def test_valid_sweep_config_normalizes_distances_and_candidate_paths() -> None:
    config = load_quantum_tanner_sweep_config(FIXTURE)

    assert config.campaign_id == "quantum-tanner-autoresearch"
    assert config.code_id == "quantum-tanner-code"
    assert config.distances == (4, 6)
    assert config.output_root == Path(
        "campaigns/examples/quantum-tanner-autoresearch/generated"
    )
    assert config.spec_root == Path(
        "campaigns/examples/quantum-tanner-autoresearch/generated/quantum_tanner_specs"
    )
    assert config.instance_root == Path(
        "benchmarks/distance_ladders/generated-quantum-tanner/instances"
    )
    assert config.catalog_path == Path(
        "campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json"
    )
    assert config.search_space_path == Path(
        "campaigns/examples/quantum-tanner-autoresearch/search_space.json"
    )
    assert config.expected_bound_type == "exact"
    assert config.qec_code_bin == "qec-code"
    assert [candidate.candidate_id for candidate in config.candidates] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d6",
    ]

    d4 = config.candidates[0]
    assert d4.distance == 4
    assert d4.qec_code_spec == "quantum_tanner:toric_d4"
    assert d4.quantum_tanner_spec_path == Path(
        "campaigns/examples/quantum-tanner-autoresearch/generated/quantum_tanner_specs/toric-d4.json"
    )
    assert d4.instance_dir == Path(
        "benchmarks/distance_ladders/generated-quantum-tanner/instances/quantum-tanner-toric-d4"
    )
    assert d4.instance_path == d4.instance_dir / "instance.json"
    assert d4.hx_path == d4.instance_dir / "hx.json"
    assert d4.hz_path == d4.instance_dir / "hz.json"


def test_valid_sweep_config_exposes_default_distance_ladder_exporter_bin() -> None:
    config = load_quantum_tanner_sweep_config(FIXTURE)

    assert config.distance_ladder_exporter_bin == "autoqec-distance-ladder"


def test_distances_are_sorted_but_duplicates_are_rejected() -> None:
    config = normalize_quantum_tanner_sweep_config(_payload(distances=[6, 4]))
    assert config.distances == (4, 6)
    assert [candidate.candidate_id for candidate in config.candidates] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d6",
    ]

    with pytest.raises(SearchIntegrityError, match="distances"):
        normalize_quantum_tanner_sweep_config(_payload(distances=[4, 4]))


@pytest.mark.parametrize("distances", [[4.0], ["4"], [True], [1]])
def test_invalid_distances_report_distances_field(distances: list[object]) -> None:
    with pytest.raises(SearchIntegrityError, match="distances"):
        normalize_quantum_tanner_sweep_config(_payload(distances=distances))


@pytest.mark.parametrize("expected_bound_type", ["bogus", "EXACT"])
def test_invalid_expected_bound_type_reports_expected_bound_type(
    expected_bound_type: str,
) -> None:
    with pytest.raises(SearchIntegrityError, match="expected_bound_type"):
        normalize_quantum_tanner_sweep_config(
            _payload(expected_bound_type=expected_bound_type)
        )


@pytest.mark.parametrize("field", ["campaign_id", "code_id", "search_space_path"])
def test_missing_required_fields_report_the_missing_field(field: str) -> None:
    payload = _payload()
    payload.pop(field)

    with pytest.raises(SearchIntegrityError, match=field):
        normalize_quantum_tanner_sweep_config(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("catalog_path", "../outside/fixture_catalog.json"),
        ("spec_root", "/tmp/specs"),
        ("instance_root", ""),
        ("search_space_path", "."),
    ],
)
def test_unsafe_paths_report_the_invalid_field(field: str, value: str) -> None:
    with pytest.raises(SearchIntegrityError, match=field):
        normalize_quantum_tanner_sweep_config(_payload(**{field: value}))


def test_summary_lists_exactly_normalized_candidate_ids() -> None:
    summary = render_quantum_tanner_sweep_summary(load_quantum_tanner_sweep_config(FIXTURE))

    assert "validated quantum Tanner sweep: quantum-tanner-autoresearch" in summary
    assert "quantum-tanner-toric-d4" in summary
    assert "quantum-tanner-toric-d6" in summary
    assert "quantum-tanner-toric-d8" not in summary


def test_generation_dry_run_plans_specs_and_manifest(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))
    plan = plan_quantum_tanner_sweep_generation(tmp_path.parent, config)

    assert not plan.manifest_path.exists()
    assert not any(spec_path.exists() for spec_path in plan.spec_paths)
    assert [entry["instance_id"] for entry in plan.manifest["entries"]] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d6",
    ]
    assert [path.name for path in plan.spec_paths] == ["toric-d4.json", "toric-d6.json"]
    _assert_manifest_entry(
        plan.manifest["entries"][0],
        instance_id="quantum-tanner-toric-d4",
        code_id="quantum-tanner-code",
        qec_code_spec="quantum_tanner:toric_d4",
        quantum_tanner_spec="generated/quantum_tanner_specs/toric-d4.json",
        n=16,
        k=2,
        expected_distance=4,
        expected_bound_type="exact",
    )
    _assert_manifest_entry(
        plan.manifest["entries"][1],
        instance_id="quantum-tanner-toric-d6",
        code_id="quantum-tanner-code",
        qec_code_spec="quantum_tanner:toric_d6",
        quantum_tanner_spec="generated/quantum_tanner_specs/toric-d6.json",
        n=36,
        k=2,
        expected_distance=6,
        expected_bound_type="exact",
    )
    assert "would write 2 quantum Tanner specs" in render_quantum_tanner_generation_summary(
        plan, dry_run=True
    )


def test_generation_write_run_writes_specs_and_manifest(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))
    plan = generate_quantum_tanner_sweep(tmp_path.parent, config, dry_run=False)

    assert plan.manifest_path.is_file()
    manifest = json.loads(plan.manifest_path.read_text())
    assert len(manifest["entries"]) == 2
    _assert_manifest_entry(
        manifest["entries"][0],
        instance_id="quantum-tanner-toric-d4",
        code_id="quantum-tanner-code",
        qec_code_spec="quantum_tanner:toric_d4",
        quantum_tanner_spec="generated/quantum_tanner_specs/toric-d4.json",
        n=16,
        k=2,
        expected_distance=4,
        expected_bound_type="exact",
    )
    _assert_manifest_entry(
        manifest["entries"][1],
        instance_id="quantum-tanner-toric-d6",
        code_id="quantum-tanner-code",
        qec_code_spec="quantum_tanner:toric_d6",
        quantum_tanner_spec="generated/quantum_tanner_specs/toric-d6.json",
        n=36,
        k=2,
        expected_distance=6,
        expected_bound_type="exact",
    )
    for distance, spec_path in zip((4, 6), plan.spec_paths, strict=True):
        spec = json.loads(spec_path.read_text())
        assert spec["fixture_id"] == f"quantum-tanner-toric-d{distance}"
        assert spec["construction_mode"] == "lr_cayley_no_cover_v1"
        assert spec["base_group"]["name"] == f"Z{distance}xZ{distance}"
        assert spec["base_group"]["order"] == distance * distance
        assert spec["local_codes"]["h_a"] == [[1, 1]]
        assert spec["local_codes"]["h_b"] == [[1, 1]]


def test_generation_rejects_spec_path_escape_before_writes(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))
    unsafe_candidate = replace(
        config.candidates[0],
        quantum_tanner_spec_path=Path(f"{tmp_path.name}/generated/../outside/toric-d4.json"),
    )
    unsafe_config = replace(config, candidates=(unsafe_candidate, *config.candidates[1:]))

    with pytest.raises(SearchIntegrityError, match="spec output path"):
        generate_quantum_tanner_sweep(tmp_path.parent, unsafe_config, dry_run=False)

    assert not (tmp_path.parent / f"{tmp_path.name}/generated-ladder.json").exists()
    assert not (tmp_path.parent / f"{tmp_path.name}/generated/quantum_tanner_specs/toric-d4.json").exists()
    assert not (tmp_path.parent / f"{tmp_path.name}/generated/quantum_tanner_specs/toric-d6.json").exists()


def test_generation_rejects_candidate_id_collisions_before_writes(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))
    duplicate = config.candidates[0]
    collided = replace(config, candidates=(duplicate, duplicate))

    with pytest.raises(SearchIntegrityError, match="duplicate candidate_id"):
        generate_quantum_tanner_sweep(tmp_path.parent, collided, dry_run=False)

    assert not (tmp_path.parent / f"{tmp_path.name}/generated-ladder.json").exists()


def test_generation_materializes_and_emits_catalog_and_search_space_for_workspace_validation() -> None:
    work_root = _copy_generation_workspace(GENERATED_QT_ROOT)
    config = normalize_quantum_tanner_sweep_config(_workspace_generation_payload(work_root))

    plan = generate_quantum_tanner_sweep(
        work_root,
        config,
        dry_run=False,
        materialize=True,
        force=True,
    )

    assert plan.autoresearch_files is not None
    catalog_path = work_root / config.catalog_path
    search_space_path = work_root / config.search_space_path
    assert catalog_path.is_file()
    assert search_space_path.is_file()

    catalog = load_quantum_tanner_fixture_catalog(work_root, config.catalog_path)
    assert [entry["candidate_id"] for entry in catalog["entries"]] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d6",
    ]
    assert [entry["distance"] for entry in catalog["entries"]] == [4, 6]

    search_space = json.loads(search_space_path.read_text())
    Draft202012Validator(
        json.loads((work_root / "benchmarks/schemas/search-space.schema.json").read_text())
    ).validate(search_space)
    assert search_space == {
        "campaign_id": "quantum-tanner-autoresearch",
        "mode": "explicit_list",
        "candidate_specs": [
            {
                "candidate_id": "quantum-tanner-toric-d4",
                "code_family": "quantum-tanner-code",
                "fixture_catalog_path": str(config.catalog_path),
                "provenance": {
                    "kind": "distance-ladder-fixture",
                    "label": "quantum-tanner-toric-d4",
                },
            },
            {
                "candidate_id": "quantum-tanner-toric-d6",
                "code_family": "quantum-tanner-code",
                "fixture_catalog_path": str(config.catalog_path),
                "provenance": {
                    "kind": "distance-ladder-fixture",
                    "label": "quantum-tanner-toric-d6",
                },
            },
        ],
    }

    for entry in catalog["entries"]:
        resolved = resolve_quantum_tanner_fixture_entry(
            work_root,
            entry,
            campaign_id=config.campaign_id,
            catalog_path=config.catalog_path,
        )
        assert resolved.spec.candidate_id == entry["candidate_id"]
        assert resolved.hx["n_cols"] == entry["n"]
        assert resolved.hz["n_cols"] == entry["n"]

    assert main(["validate", "--root", str(work_root)]) == 0


def test_emit_quantum_tanner_autoresearch_files_writes_workspace_artifacts() -> None:
    work_root = _copy_generation_workspace(GENERATED_QT_ROOT / "emit")
    config = normalize_quantum_tanner_sweep_config(_workspace_generation_payload(work_root))

    emitted = qtg.emit_quantum_tanner_autoresearch_files(
        work_root,
        config,
        dry_run=False,
        materialize=True,
        force=True,
    )

    catalog_path = work_root / config.catalog_path
    search_space_path = work_root / config.search_space_path
    assert catalog_path.is_file()
    assert search_space_path.is_file()

    if emitted is not None:
        assert emitted.catalog_path.resolve() == catalog_path.resolve()
        assert emitted.search_space_path.resolve() == search_space_path.resolve()

    catalog = load_quantum_tanner_fixture_catalog(work_root, config.catalog_path)
    assert [entry["candidate_id"] for entry in catalog["entries"]] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d6",
    ]
    assert [entry["distance"] for entry in catalog["entries"]] == [4, 6]

    search_space = json.loads(search_space_path.read_text())
    Draft202012Validator(
        json.loads((work_root / "benchmarks/schemas/search-space.schema.json").read_text())
    ).validate(search_space)
    assert search_space == {
        "campaign_id": "quantum-tanner-autoresearch",
        "mode": "explicit_list",
        "candidate_specs": [
            {
                "candidate_id": "quantum-tanner-toric-d4",
                "code_family": "quantum-tanner-code",
                "fixture_catalog_path": str(config.catalog_path),
                "provenance": {
                    "kind": "distance-ladder-fixture",
                    "label": "quantum-tanner-toric-d4",
                },
            },
            {
                "candidate_id": "quantum-tanner-toric-d6",
                "code_family": "quantum-tanner-code",
                "fixture_catalog_path": str(config.catalog_path),
                "provenance": {
                    "kind": "distance-ladder-fixture",
                    "label": "quantum-tanner-toric-d6",
                },
            },
        ],
    }


def test_emit_quantum_tanner_autoresearch_files_converts_existing_materialized_instances(
    tmp_path: Path,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    exporter_bin = _distance_ladder_exporter_bin()
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(exporter_bin),
        )
    )
    plan = generate_quantum_tanner_sweep(tmp_path.parent, config, dry_run=False)

    materialize_quantum_tanner_sweep(plan, config, force=True)

    emitted = emit_quantum_tanner_autoresearch_files(
        tmp_path.parent,
        config,
        dry_run=False,
        materialize=False,
    )

    assert emitted is not None
    assert emitted.catalog_path.resolve() == (tmp_path.parent / config.catalog_path).resolve()
    assert emitted.search_space_path.resolve() == (
        tmp_path.parent / config.search_space_path
    ).resolve()
    assert emitted.catalog_path.is_file()
    assert emitted.search_space_path.is_file()


def test_emit_quantum_tanner_autoresearch_files_materialize_false_rejects_missing_hz(
    tmp_path: Path,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    exporter_bin = _distance_ladder_exporter_bin()
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(exporter_bin),
        )
    )
    plan = generate_quantum_tanner_sweep(tmp_path.parent, config, dry_run=False)
    materialize_quantum_tanner_sweep(plan, config, force=True)

    missing_hz = tmp_path.parent / config.candidates[1].hz_path
    missing_hz.unlink()

    with pytest.raises(SearchIntegrityError) as excinfo:
        emit_quantum_tanner_autoresearch_files(
            tmp_path.parent,
            config,
            dry_run=False,
            materialize=False,
        )

    message = str(excinfo.value)
    assert "missing hz artifact" in message
    assert str(missing_hz) in message


def test_emit_quantum_tanner_autoresearch_files_does_not_mutate_source_instance(
    tmp_path: Path,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    exporter_bin = _distance_ladder_exporter_bin()
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(exporter_bin),
        )
    )
    plan = generate_quantum_tanner_sweep(tmp_path.parent, config, dry_run=False)
    materialize_quantum_tanner_sweep(plan, config, force=True)

    instance_path = tmp_path.parent / config.candidates[0].instance_path
    original_instance = json.loads(instance_path.read_text())

    emit_quantum_tanner_autoresearch_files(plan, config)

    assert json.loads(instance_path.read_text()) == original_instance


def test_emitted_catalog_preserves_source_instance_generator_metadata(tmp_path: Path) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    exporter_bin = _distance_ladder_exporter_bin()
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(exporter_bin),
        )
    )

    emitted = emit_quantum_tanner_autoresearch_files(
        tmp_path.parent,
        config,
        dry_run=False,
        materialize=True,
        force=True,
    )

    assert emitted is not None
    instance_path = tmp_path.parent / config.candidates[0].instance_path
    instance = json.loads(instance_path.read_text())
    assert emitted.catalog["entries"][0]["provenance"]["generator"] == instance["generator"]


def test_generated_workspace_validation_rejects_missing_hz_artifact() -> None:
    work_root = _copy_generation_workspace(GENERATED_QT_ROOT / "missing-hz")
    config = normalize_quantum_tanner_sweep_config(_workspace_generation_payload(work_root))
    generate_quantum_tanner_sweep(
        work_root,
        config,
        dry_run=False,
        materialize=True,
        force=True,
    )
    missing_hz = work_root / config.candidates[1].hz_path
    missing_hz.unlink()

    with pytest.raises(SearchIntegrityError, match="missing hz artifact"):
        validate_quantum_tanner_fixture_catalog(work_root, config.catalog_path)
    assert main(["validate", "--root", str(work_root)]) != 0


def test_cli_validates_fixture_and_prints_candidate_summary() -> None:
    result = _run_cli(FIXTURE)

    assert result.returncode == 0, result.stderr
    assert "quantum-tanner-toric-d4" in result.stdout
    assert "quantum-tanner-toric-d6" in result.stdout
    assert "quantum-tanner-toric-d8" not in result.stdout


def test_cli_generates_quantum_tanner_sweep(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path / "qt-sweep.json", _temp_generation_payload(tmp_path))
    result = _run_generate_cli(config_path)

    assert result.returncode == 0, result.stderr
    assert "wrote 2 quantum Tanner specs" in result.stdout
    assert (tmp_path / "generated-ladder.json").is_file()


def test_generation_materializes_instances_through_distance_ladder_exporter(tmp_path: Path) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    exporter_bin = _distance_ladder_exporter_bin()
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(exporter_bin),
        )
    )

    plan = generate_quantum_tanner_sweep(
        tmp_path.parent,
        config,
        dry_run=False,
        materialize=True,
        force=True,
    )

    assert plan.materialization is not None
    assert plan.autoresearch_files is not None
    assert plan.materialization.returncode == 0
    assert plan.materialization.command[0] == str(exporter_bin)
    manifest_index = plan.materialization.command.index("--manifest") + 1
    assert plan.materialization.command[manifest_index] == str(plan.manifest_path)
    assert "--qec-code-bin" in plan.materialization.command
    assert str(fake_qec_code) in plan.materialization.command
    assert "--force" in plan.materialization.command
    for candidate in config.candidates:
        instance_dir = tmp_path.parent / candidate.instance_dir
        assert (instance_dir / "instance.json").is_file()
        assert (instance_dir / "hx.json").is_file()
        assert (instance_dir / "hz.json").is_file()
        instance = json.loads((instance_dir / "instance.json").read_text())
        assert instance["qec_code_spec"] == candidate.qec_code_spec
        assert instance["quantum_tanner_spec"].endswith(
            f"generated/quantum_tanner_specs/toric-d{candidate.distance}.json"
        )
    assert (
        tmp_path.parent / f"{tmp_path.name}/generated_fixture_catalog.json"
    ).is_file()
    assert (
        tmp_path.parent / "campaigns" / tmp_path.name / "search_space.json"
    ).is_file()


def test_generation_materialization_rejects_non_indexed_search_space_filename(
    tmp_path: Path,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
            search_space_path=f"{tmp_path.name}/generated_search_space.json",
        )
    )

    with pytest.raises(SearchIntegrityError, match="search_space_path"):
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            config,
            dry_run=False,
            materialize=True,
            force=True,
        )

    assert not (tmp_path / "generated-ladder.json").exists()
    assert not (tmp_path / "generated_search_space.json").exists()


def test_generation_materialization_rejects_search_space_not_adjacent_to_campaign(
    tmp_path: Path,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
            search_space_path=f"campaigns/{tmp_path.name}/generated/search_space.json",
        )
    )

    with pytest.raises(SearchIntegrityError, match="adjacent to campaign.json"):
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            config,
            dry_run=False,
            materialize=True,
            force=True,
        )

    assert not (tmp_path / "generated-ladder.json").exists()
    assert not (
        tmp_path.parent
        / "campaigns"
        / tmp_path.name
        / "generated"
        / "search_space.json"
    ).exists()


def test_generation_materialization_rejects_search_space_outside_campaigns(
    tmp_path: Path,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    invisible_campaign_dir = tmp_path / "invisible"
    invisible_campaign_dir.mkdir()
    (invisible_campaign_dir / "campaign.json").write_text("{}\n")
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
            search_space_path=f"{tmp_path.name}/invisible/search_space.json",
        )
    )

    with pytest.raises(SearchIntegrityError, match="under campaigns"):
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            config,
            dry_run=False,
            materialize=True,
            force=True,
        )

    assert not (tmp_path / "generated-ladder.json").exists()
    assert not (invisible_campaign_dir / "search_space.json").exists()


def test_generation_materialization_without_force_omits_force_flag(tmp_path: Path) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    exporter_bin = _distance_ladder_exporter_bin()
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(exporter_bin),
        )
    )

    plan = generate_quantum_tanner_sweep(
        tmp_path.parent,
        config,
        dry_run=False,
        materialize=True,
        force=False,
    )

    assert plan.materialization is not None
    assert plan.materialization.returncode == 0
    assert plan.materialization.command[0] == str(exporter_bin)
    manifest_index = plan.materialization.command.index("--manifest") + 1
    assert plan.materialization.command[manifest_index] == str(plan.manifest_path)
    assert "--force" not in plan.materialization.command


def test_generation_dry_run_materialization_requires_explicit_tool_paths(
    tmp_path: Path,
) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))

    with pytest.raises(SearchIntegrityError, match="qec_code_bin"):
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            config,
            dry_run=True,
            materialize=True,
        )


def test_generation_materialize_false_writes_specs_and_manifest_only(tmp_path: Path) -> None:
    sentinel = tmp_path / "distance-ladder-exporter-not-called"
    fake_exporter = _write_fake_distance_ladder_exporter(
        tmp_path / "distance-ladder-exporter",
        sentinel=sentinel,
    )
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(_write_fake_qec_code(tmp_path / "qec-code")),
            distance_ladder_exporter_bin=str(fake_exporter),
        )
    )

    plan = generate_quantum_tanner_sweep(tmp_path.parent, config, dry_run=False)

    assert plan.manifest_path.is_file()
    manifest = json.loads(plan.manifest_path.read_text())
    assert len(manifest["entries"]) == 2
    for candidate in config.candidates:
        instance_dir = tmp_path.parent / candidate.instance_dir
        assert not (instance_dir / "instance.json").exists()
        assert not (instance_dir / "hx.json").exists()
        assert not (instance_dir / "hz.json").exists()
    for spec_path in plan.spec_paths:
        assert spec_path.is_file()
    assert not sentinel.exists()


def test_generation_materialization_failure_surfaces_exporter_output_and_returns_no_plan(tmp_path: Path) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "bad-qec-code", wrong_hx_width=True)
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
        )
    )

    with pytest.raises(SearchIntegrityError) as excinfo:
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            config,
            dry_run=False,
            materialize=True,
            force=True,
        )

    message = str(excinfo.value)
    assert "distance-ladder exporter failed" in message
    assert "command:" in message
    assert "stdout:" in message
    assert "stderr:" in message
    assert "expected num_cols=16" in message


def test_generation_materialization_failure_cleans_up_new_candidate_dirs_only(
    tmp_path: Path,
) -> None:
    fake_qec_code = _write_fake_qec_code(
        tmp_path / "bad-qec-code",
        wrong_hx_distances=(6,),
    )
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
        )
    )
    existing_dir = tmp_path / "instances" / "quantum-tanner-toric-d6"
    existing_dir.mkdir(parents=True)
    sentinel = existing_dir / "keep.txt"
    sentinel.write_text("pre-existing\n")

    with pytest.raises(SearchIntegrityError, match="expected num_cols=36"):
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            config,
            dry_run=False,
            materialize=True,
            force=True,
        )

    d4_dir = tmp_path / "instances" / "quantum-tanner-toric-d4"
    assert d4_dir.is_dir() is False
    for name in ("instance.json", "hx.json", "hz.json"):
        assert not (d4_dir / name).exists()
        assert not (existing_dir / name).exists()
    assert existing_dir.is_dir()
    assert sentinel.read_text() == "pre-existing\n"


def test_generation_materialization_failure_cleans_new_artifacts_in_existing_dirs(
    tmp_path: Path,
) -> None:
    fake_qec_code = _write_fake_qec_code(
        tmp_path / "bad-qec-code",
        wrong_hx_distances=(6,),
    )
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
        )
    )
    d4_dir = tmp_path / "instances" / "quantum-tanner-toric-d4"
    d4_dir.mkdir(parents=True)
    sentinel = d4_dir / "keep.txt"
    sentinel.write_text("pre-existing\n")

    with pytest.raises(SearchIntegrityError, match="expected num_cols=36"):
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            config,
            dry_run=False,
            materialize=True,
            force=True,
        )

    assert d4_dir.is_dir()
    assert sentinel.read_text() == "pre-existing\n"
    for candidate in config.candidates:
        instance_dir = tmp_path.parent / candidate.instance_dir
        for name in ("instance.json", "hx.json", "hz.json"):
            assert not (instance_dir / name).exists()


def test_materialize_helper_requires_explicit_tool_paths(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))
    plan = generate_quantum_tanner_sweep(tmp_path.parent, config, dry_run=False)

    with pytest.raises(SearchIntegrityError, match="qec_code_bin"):
        materialize_quantum_tanner_sweep(plan, config, force=True)

    explicit_qec_config = replace(config, qec_code_bin="./qec-code")
    with pytest.raises(SearchIntegrityError, match="distance_ladder_exporter_bin"):
        materialize_quantum_tanner_sweep(plan, explicit_qec_config, force=True)


def test_materialize_helper_failure_cleans_new_artifacts_in_existing_dirs(
    tmp_path: Path,
) -> None:
    fake_qec_code = _write_fake_qec_code(
        tmp_path / "bad-qec-code",
        wrong_hx_distances=(6,),
    )
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
        )
    )
    plan = generate_quantum_tanner_sweep(tmp_path.parent, config, dry_run=False)
    d4_dir = tmp_path / "instances" / "quantum-tanner-toric-d4"
    d4_dir.mkdir(parents=True)
    sentinel = d4_dir / "keep.txt"
    sentinel.write_text("pre-existing\n")

    with pytest.raises(SearchIntegrityError, match="expected num_cols=36"):
        materialize_quantum_tanner_sweep(plan, config, force=True)

    assert d4_dir.is_dir()
    assert sentinel.read_text() == "pre-existing\n"
    for candidate in config.candidates:
        instance_dir = tmp_path.parent / candidate.instance_dir
        for name in ("instance.json", "hx.json", "hz.json"):
            assert not (instance_dir / name).exists()


def test_generation_materialization_spawn_failure_surfaces_empty_output_sections(
    tmp_path: Path,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    missing_exporter = tmp_path / "missing-exporter"
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(missing_exporter),
        )
    )

    with pytest.raises(SearchIntegrityError) as excinfo:
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            config,
            dry_run=False,
            materialize=True,
            force=True,
        )

    message = str(excinfo.value)
    assert "distance-ladder exporter failed" in message
    assert f"command: {missing_exporter} export --manifest " in message
    assert "stdout:" in message
    assert "stderr:" in message
    assert "No such file or directory" in message


def test_write_run_summary_uses_past_tense(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))
    plan = generate_quantum_tanner_sweep(tmp_path.parent, config, dry_run=False)

    summary = render_quantum_tanner_generation_summary(plan, dry_run=False)

    assert "wrote 2 quantum Tanner specs and 1 distance ladder manifest" in summary
    assert "would write" not in summary


def test_cli_rejects_duplicate_distances_and_unsafe_path(tmp_path: Path) -> None:
    duplicate = _write_config(tmp_path / "duplicate.json", _payload(distances=[4, 4]))
    duplicate_result = _run_cli(duplicate)
    assert duplicate_result.returncode == 1
    assert "distances" in duplicate_result.stderr

    unsafe = _write_config(
        tmp_path / "unsafe.json",
        _payload(catalog_path="../outside/fixture_catalog.json"),
    )
    unsafe_result = _run_cli(unsafe)
    assert unsafe_result.returncode == 1
    assert "catalog_path" in unsafe_result.stderr


def test_cli_rejects_empty_distance_ladder_exporter_override(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path / "qt-sweep.json", _temp_generation_payload(tmp_path))

    result = _run_generate_cli(config_path, "--distance-ladder-exporter-bin", "")

    assert result.returncode == 1
    assert "distance_ladder_exporter_bin" in result.stderr


def test_generation_materialize_requires_explicit_tool_paths(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))

    with pytest.raises(SearchIntegrityError, match="qec_code_bin"):
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            config,
            dry_run=False,
            materialize=True,
        )

    explicit_qec_config = replace(
        config,
        qec_code_bin="./qec-code",
    )
    with pytest.raises(SearchIntegrityError, match="distance_ladder_exporter_bin"):
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            explicit_qec_config,
            dry_run=False,
            materialize=True,
        )


def test_cli_materialize_rejects_default_bare_tool_values(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path / "qt-sweep.json", _temp_generation_payload(tmp_path))

    result = _run_generate_cli(config_path, "--materialize")

    assert result.returncode == 1
    assert "qec_code_bin" in result.stderr


def test_cli_materializes_quantum_tanner_sweep(tmp_path: Path) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    config_path = _write_config(
        tmp_path / "qt-sweep.json",
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
        ),
    )

    result = _run_generate_cli(config_path, "--materialize", "--force")

    assert result.returncode == 0, result.stderr
    assert "materialized 2 quantum Tanner instances" in result.stdout
    assert (tmp_path / "instances" / "quantum-tanner-toric-d4" / "instance.json").is_file()
    assert (tmp_path / "instances" / "quantum-tanner-toric-d6" / "hz.json").is_file()


def test_cli_generate_quantum_tanner_candidates_dry_run_plans_without_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path.parent
    config_path = _write_config(tmp_path / "qt-sweep.json", _temp_generation_payload(tmp_path))

    result = _run_generate_candidates_cli(root, config_path, "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "would generate 2 quantum Tanner candidates" in result.stdout
    assert "candidate_ids: [4, 6]" in result.stdout
    assert "quantum-tanner-toric-d4" in result.stdout
    assert "n=16" in result.stdout
    assert "k=2" in result.stdout
    assert "distance_label=d4" in result.stdout
    assert "quantum-tanner-toric-d6" in result.stdout
    assert "n=36" in result.stdout
    assert "distance_label=d6" in result.stdout
    assert not (tmp_path / "generated-ladder.json").exists()
    assert not (tmp_path / "generated_fixture_catalog.json").exists()
    assert not (tmp_path.parent / "campaigns" / tmp_path.name / "search_space.json").exists()
    for distance in (4, 6):
        assert not (
            tmp_path / "generated" / "quantum_tanner_specs" / f"toric-d{distance}.json"
        ).exists()
        instance_dir = tmp_path / "instances" / f"quantum-tanner-toric-d{distance}"
        assert not (instance_dir / "instance.json").exists()
        assert not (instance_dir / "hx.json").exists()
        assert not (instance_dir / "hz.json").exists()


def test_cli_generate_quantum_tanner_candidates_materializes_and_validates_root(
    tmp_path: Path,
) -> None:
    work_root = _copy_generation_workspace(GENERATED_QT_ROOT / "cli-candidates")
    config_path = _write_config(
        tmp_path / "qt-sweep.json",
        _workspace_generation_payload(work_root, qec_code_bin="qec-code"),
    )
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")

    result = _run_generate_candidates_cli(
        work_root,
        config_path,
        "--qec-code-bin",
        str(fake_qec_code),
        "--force",
    )

    assert result.returncode == 0, result.stderr
    assert "generated 2 quantum Tanner candidates" in result.stdout
    assert "candidate_ids: [4, 6]" in result.stdout
    assert "emitted fixture_catalog:" in result.stdout
    assert "emitted search_space:" in result.stdout
    assert (work_root / "benchmarks/distance_ladders/generated-quantum-tanner.json").is_file()
    assert (
        work_root
        / "campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json"
    ).is_file()
    assert (
        work_root / "campaigns/examples/quantum-tanner-autoresearch/search_space.json"
    ).is_file()
    for distance in (4, 6):
        candidate_id = f"quantum-tanner-toric-d{distance}"
        instance_dir = (
            work_root / "benchmarks/distance_ladders/generated-quantum-tanner/instances" / candidate_id
        )
        assert (instance_dir / "instance.json").is_file()
        assert (instance_dir / "hx.json").is_file()
        assert (instance_dir / "hz.json").is_file()
    assert main(["validate", "--root", str(work_root)]) == 0


def test_cli_generate_quantum_tanner_candidates_broken_qec_code_fails_materialization(
    tmp_path: Path,
) -> None:
    work_root = _copy_generation_workspace(GENERATED_QT_ROOT / "cli-broken")
    config_path = _write_config(
        tmp_path / "qt-sweep.json",
        _workspace_generation_payload(work_root, qec_code_bin="qec-code"),
    )
    broken_qec_code = _write_fake_qec_code(tmp_path / "bad-qec-code", wrong_hx_width=True)

    result = _run_generate_candidates_cli(
        work_root,
        config_path,
        "--qec-code-bin",
        str(broken_qec_code),
        "--force",
    )

    assert result.returncode != 0
    assert "distance-ladder exporter failed" in result.stderr
    assert "expected num_cols=16" in result.stderr
    assert "generated 2 quantum Tanner candidates" not in result.stdout


def test_attach_quantum_tanner_witnesses_cli_updates_generated_search_space() -> None:
    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-cli"
    )
    witness_dir = "campaigns/examples/quantum-tanner-autoresearch/witnesses"

    result = _run_attach_witnesses_cli(
        work_root,
        "--campaign",
        config.campaign_id,
        "--fixture-catalog",
        str(config.catalog_path),
        "--witness-dir",
        witness_dir,
        "--basis",
        "x",
        "--qec-code-bin",
        str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
        "--iterations",
        "25",
        "--restarts",
        "4",
        "--seed",
        "17",
        "--timeout-seconds",
        "30",
    )

    assert result.returncode == 0
    assert "attached=2 skipped=0 failed=0" in result.stdout
    assert "search_space=" in result.stdout
    assert "summary=" in result.stdout

    search_space = json.loads((work_root / config.search_space_path).read_text())
    assert [spec["upper_bound_witness_path"] for spec in search_space["candidate_specs"]] == [
        str(Path(witness_dir) / "quantum-tanner-toric-d4-upper-bound-witness.json"),
        str(Path(witness_dir) / "quantum-tanner-toric-d6-upper-bound-witness.json"),
    ]

    summary_path = work_root / witness_dir / "witness_finder_summary.json"
    summary = json.loads(summary_path.read_text())
    assert summary["counts"] == {"attached": 2, "skipped": 0, "failed": 0}
    assert summary["summary_path"] == str(Path(witness_dir) / "witness_finder_summary.json")


@pytest.mark.parametrize(
    ("extra_args", "expected_stderr"),
    [
        (
            (
                "--campaign",
                "quantum-tanner-autoresearch",
                "--search-space",
                "campaigns/examples/quantum-tanner-autoresearch/search_space.json",
            ),
            "argument --search-space: not allowed with argument --campaign",
        ),
        (
            (),
            "one of the arguments --campaign --search-space is required",
        ),
    ],
)
def test_attach_quantum_tanner_witnesses_cli_requires_exactly_one_source_selector(
    extra_args: tuple[str, ...],
    expected_stderr: str,
) -> None:
    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-cli-source-selector"
    )

    result = _run_attach_witnesses_cli(
        work_root,
        *extra_args,
        "--fixture-catalog",
        str(config.catalog_path),
        "--witness-dir",
        "campaigns/examples/quantum-tanner-autoresearch/witnesses",
        "--basis",
        "x",
        "--qec-code-bin",
        str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert expected_stderr in result.stderr


def test_attach_quantum_tanner_witnesses_fail_on_skipped_writes_outputs_before_nonzero_exit() -> None:
    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-cli-fail-on-skipped"
    )
    search_space_path = work_root / config.search_space_path
    witness_dir = Path("campaigns/examples/quantum-tanner-autoresearch/witnesses")
    out_search_space_path = Path(
        "campaigns/examples/quantum-tanner-autoresearch/search_space.fail-on-skipped.json"
    )
    summary_path = witness_dir / "fail-on-skipped-summary.json"

    search_space = json.loads(search_space_path.read_text())
    preserved_path = str(witness_dir / "preserved-existing.json")
    search_space["candidate_specs"][1]["upper_bound_witness_path"] = preserved_path
    search_space_path.write_text(json.dumps(search_space, indent=2, sort_keys=True) + "\n")

    result = _run_attach_witnesses_cli(
        work_root,
        "--campaign",
        config.campaign_id,
        "--fixture-catalog",
        str(config.catalog_path),
        "--witness-dir",
        str(witness_dir),
        "--out-search-space",
        str(out_search_space_path),
        "--summary-out",
        str(summary_path),
        "--basis",
        "x",
        "--qec-code-bin",
        str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
        "--iterations",
        "25",
        "--restarts",
        "4",
        "--seed",
        "17",
        "--timeout-seconds",
        "30",
        "--fail-on-skipped",
    )

    assert result.returncode == 1
    assert "attached=1 skipped=1 failed=0" in result.stdout

    updated_search_space = json.loads((work_root / out_search_space_path).read_text())
    assert [
        spec.get("upper_bound_witness_path")
        for spec in updated_search_space["candidate_specs"]
    ] == [
        str(witness_dir / "quantum-tanner-toric-d4-upper-bound-witness.json"),
        preserved_path,
    ]

    summary = json.loads((work_root / summary_path).read_text())
    assert summary["counts"] == {"attached": 1, "skipped": 1, "failed": 0}
    assert [candidate["status"] for candidate in summary["candidates"]] == ["attached", "skipped"]
    assert [candidate["reason"] for candidate in summary["candidates"]] == [
        "verified_upper_bound_witness",
        "existing_upper_bound_witness_path",
    ]


def test_attach_quantum_tanner_witnesses_strict_fails_for_missing_hz_without_search_update() -> None:
    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-cli-missing-hz"
    )
    search_space_path = work_root / config.search_space_path
    catalog_path = work_root / config.catalog_path
    witness_dir = Path("campaigns/examples/quantum-tanner-autoresearch/witnesses")
    out_search_space_path = Path(
        "campaigns/examples/quantum-tanner-autoresearch/search_space.with-witnesses.json"
    )
    summary_path = witness_dir / "strict-summary.json"

    catalog = json.loads(catalog_path.read_text())
    missing_hz_entry = _clone_generated_fixture_entry(
        work_root,
        config.catalog_path,
        source_candidate_id="quantum-tanner-toric-d4",
        candidate_id="missing-hz",
    )
    catalog["entries"] = [missing_hz_entry, *catalog["entries"][1:2]]
    catalog_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")
    (work_root / Path(missing_hz_entry["hz"])).unlink()

    search_space = json.loads(search_space_path.read_text())
    search_space["candidate_specs"] = [
        dict(search_space["candidate_specs"][0], candidate_id="missing-hz"),
        dict(search_space["candidate_specs"][1]),
    ]
    search_space_path.write_text(json.dumps(search_space, indent=2, sort_keys=True) + "\n")

    result = _run_attach_witnesses_cli(
        work_root,
        "--campaign",
        config.campaign_id,
        "--fixture-catalog",
        str(config.catalog_path),
        "--witness-dir",
        str(witness_dir),
        "--out-search-space",
        str(out_search_space_path),
        "--summary-out",
        str(summary_path),
        "--basis",
        "x",
        "--qec-code-bin",
        str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
        "--iterations",
        "25",
        "--restarts",
        "4",
        "--seed",
        "17",
        "--timeout-seconds",
        "30",
        "--require-all",
    )

    assert result.returncode == 1
    assert "attached=1 skipped=0 failed=1" in result.stdout

    updated_search_space = json.loads((work_root / out_search_space_path).read_text())
    assert [
        spec.get("upper_bound_witness_path")
        for spec in updated_search_space["candidate_specs"]
    ] == [
        None,
        str(witness_dir / "quantum-tanner-toric-d6-upper-bound-witness.json"),
    ]

    summary = json.loads((work_root / summary_path).read_text())
    assert summary["counts"] == {"attached": 1, "skipped": 0, "failed": 1}
    assert [candidate["status"] for candidate in summary["candidates"]] == ["failed", "attached"]
    assert summary["candidates"][0]["reason"].startswith("missing hz artifact:")


def test_attach_quantum_tanner_witnesses_strict_fails_for_incompatible_basis_without_search_update() -> None:
    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-cli-basis-mismatch"
    )
    search_space_path = Path(
        "campaigns/examples/quantum-tanner-autoresearch/search_space.z-basis.json"
    )
    summary_path = Path("campaigns/examples/quantum-tanner-autoresearch/witnesses/z-summary.json")

    result = _run_attach_witnesses_cli(
        work_root,
        "--search-space",
        str(config.search_space_path),
        "--fixture-catalog",
        str(config.catalog_path),
        "--witness-dir",
        "campaigns/examples/quantum-tanner-autoresearch/witnesses",
        "--out-search-space",
        str(search_space_path),
        "--summary-out",
        str(summary_path),
        "--basis",
        "x",
        "--qec-code-bin",
        str(
            _write_fake_random_window_qec_code_result(
                work_root / "fake-qec-code-rw-z",
                logical_class="z_like",
            )
        ),
        "--iterations",
        "25",
        "--restarts",
        "4",
        "--seed",
        "17",
        "--timeout-seconds",
        "30",
        "--require-all",
    )

    assert result.returncode == 1
    assert "attached=0 skipped=0 failed=2" in result.stdout

    updated_search_space = json.loads((work_root / search_space_path).read_text())
    assert [
        spec.get("upper_bound_witness_path")
        for spec in updated_search_space["candidate_specs"]
    ] == [None, None]

    summary = json.loads((work_root / summary_path).read_text())
    assert summary["counts"] == {"attached": 0, "skipped": 0, "failed": 2}
    assert [candidate["reason"] for candidate in summary["candidates"]] == [
        "incompatible witness basis: requested x, found z",
        "incompatible witness basis: requested x, found z",
    ]


def test_attach_quantum_tanner_witnesses_writes_two_witnesses_and_updates_search_space() -> None:
    from autoqec_search.quantum_tanner_witness_batch import (
        attach_quantum_tanner_witnesses,
    )

    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses"
    )
    witness_dir = Path("campaigns/examples/quantum-tanner-autoresearch/witnesses")

    summary = attach_quantum_tanner_witnesses(
        work_root,
        campaign_id=config.campaign_id,
        search_space_path=None,
        fixture_catalog_path=config.catalog_path,
        witness_dir=witness_dir,
        basis="x",
        qec_code_bin=str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
        iterations=25,
        restarts=4,
        seed=17,
        target_weight=None,
        timeout_seconds=30.0,
    )

    witness_paths = [
        str(witness_dir / "quantum-tanner-toric-d4-upper-bound-witness.json"),
        str(witness_dir / "quantum-tanner-toric-d6-upper-bound-witness.json"),
    ]
    assert summary == {
        "schema_version": 1,
        "campaign_id": config.campaign_id,
        "basis": "x",
        "fixture_catalog_path": str(config.catalog_path),
        "search_space_path": str(config.search_space_path),
        "source_search_space_path": str(config.search_space_path),
        "witness_dir": str(witness_dir),
        "force": False,
        "counts": {"attached": 2, "skipped": 0, "failed": 0},
        "candidates": [
            {
                "candidate_id": "quantum-tanner-toric-d4",
                "status": "attached",
                "reason": "verified_upper_bound_witness",
                "basis": "x",
                "weight": 1,
                "witness_path": witness_paths[0],
                "search_space_updated": True,
            },
            {
                "candidate_id": "quantum-tanner-toric-d6",
                "status": "attached",
                "reason": "verified_upper_bound_witness",
                "basis": "x",
                "weight": 1,
                "witness_path": witness_paths[1],
                "search_space_updated": True,
            },
        ],
    }

    search_space_path = work_root / config.search_space_path
    search_space = json.loads(search_space_path.read_text())
    candidate_specs = search_space["candidate_specs"]
    assert [spec["candidate_id"] for spec in candidate_specs] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d6",
    ]
    assert [spec["upper_bound_witness_path"] for spec in candidate_specs] == witness_paths

    witness_payloads = [json.loads((work_root / path).read_text()) for path in witness_paths]
    assert [payload["basis"] for payload in witness_payloads] == ["x", "x"]
    assert [sum(payload["vector"]) for payload in witness_payloads] == [1, 1]
    assert [len(payload["vector"]) for payload in witness_payloads] == [16, 36]


def test_attach_quantum_tanner_witnesses_preserves_existing_paths_and_files_without_force() -> None:
    from autoqec_search.quantum_tanner_witness_batch import (
        attach_quantum_tanner_witnesses,
    )

    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-existing"
    )
    witness_dir = Path("campaigns/examples/quantum-tanner-autoresearch/witnesses")
    search_space_path = work_root / config.search_space_path
    search_space = json.loads(search_space_path.read_text())
    candidate_specs = search_space["candidate_specs"]

    preserved_path = str(witness_dir / "preserved-existing.json")
    candidate_specs[1]["upper_bound_witness_path"] = preserved_path
    search_space_path.write_text(json.dumps(search_space, indent=2, sort_keys=True) + "\n")

    existing_witness_path = work_root / witness_dir / "quantum-tanner-toric-d4-upper-bound-witness.json"
    existing_witness_payload = {"basis": "x", "vector": [1] + [0] * 15}
    existing_witness_path.parent.mkdir(parents=True, exist_ok=True)
    existing_witness_path.write_text(
        json.dumps(existing_witness_payload, indent=2, sort_keys=True) + "\n"
    )

    summary = attach_quantum_tanner_witnesses(
        work_root,
        campaign_id=config.campaign_id,
        search_space_path=None,
        fixture_catalog_path=config.catalog_path,
        witness_dir=witness_dir,
        basis="x",
        qec_code_bin=str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
        iterations=25,
        restarts=4,
        seed=17,
        target_weight=None,
        timeout_seconds=30.0,
        force=False,
    )

    assert summary == {
        "schema_version": 1,
        "campaign_id": config.campaign_id,
        "basis": "x",
        "fixture_catalog_path": str(config.catalog_path),
        "search_space_path": str(config.search_space_path),
        "source_search_space_path": str(config.search_space_path),
        "witness_dir": str(witness_dir),
        "force": False,
        "counts": {"attached": 0, "skipped": 2, "failed": 0},
        "candidates": [
            {
                "candidate_id": "quantum-tanner-toric-d4",
                "status": "skipped",
                "reason": "existing_witness_file",
                "basis": "x",
                "weight": None,
                "witness_path": str(witness_dir / "quantum-tanner-toric-d4-upper-bound-witness.json"),
                "search_space_updated": False,
            },
            {
                "candidate_id": "quantum-tanner-toric-d6",
                "status": "skipped",
                "reason": "existing_upper_bound_witness_path",
                "basis": "x",
                "weight": None,
                "witness_path": preserved_path,
                "search_space_updated": False,
            },
        ],
    }

    updated_search_space = json.loads(search_space_path.read_text())
    assert updated_search_space["candidate_specs"][0].get("upper_bound_witness_path") is None
    assert updated_search_space["candidate_specs"][1]["upper_bound_witness_path"] == preserved_path
    assert json.loads(existing_witness_path.read_text()) == existing_witness_payload


def test_attach_quantum_tanner_witnesses_records_per_candidate_failures_without_aborting_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autoqec_search.quantum_tanner_witness_batch as witness_batch

    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-failures"
    )
    witness_dir = Path("campaigns/examples/quantum-tanner-autoresearch/witnesses")
    search_space_path = work_root / config.search_space_path
    catalog_path = work_root / config.catalog_path

    catalog = json.loads(catalog_path.read_text())
    missing_artifacts_entry = _clone_generated_fixture_entry(
        work_root,
        config.catalog_path,
        source_candidate_id="quantum-tanner-toric-d4",
        candidate_id="missing-artifacts",
    )
    backend_failure_entry = _clone_generated_fixture_entry(
        work_root,
        config.catalog_path,
        source_candidate_id="quantum-tanner-toric-d6",
        candidate_id="backend-failure",
    )
    conversion_failure_entry = _clone_generated_fixture_entry(
        work_root,
        config.catalog_path,
        source_candidate_id="quantum-tanner-toric-d4",
        candidate_id="conversion-failure",
    )
    basis_mismatch_entry = _clone_generated_fixture_entry(
        work_root,
        config.catalog_path,
        source_candidate_id="quantum-tanner-toric-d6",
        candidate_id="basis-mismatch",
    )
    catalog["entries"].extend(
        [
            missing_artifacts_entry,
            backend_failure_entry,
            conversion_failure_entry,
            basis_mismatch_entry,
        ]
    )
    catalog_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")
    (work_root / Path(missing_artifacts_entry["hx"])).unlink()

    search_space = json.loads(search_space_path.read_text())
    source_spec = dict(search_space["candidate_specs"][0])
    search_space["candidate_specs"] = [
        dict(source_spec, candidate_id="missing-catalog"),
        dict(source_spec, candidate_id="missing-artifacts"),
        dict(source_spec, candidate_id="backend-failure"),
        dict(source_spec, candidate_id="conversion-failure"),
        dict(source_spec, candidate_id="basis-mismatch"),
        dict(search_space["candidate_specs"][1]),
    ]
    search_space_path.write_text(json.dumps(search_space, indent=2, sort_keys=True) + "\n")

    real_run = witness_batch.run_qec_code_random_window_upper_bound
    real_convert = witness_batch.convert_qec_code_random_window_upper_bound_result

    def fake_run(
        hx_path: str | Path,
        hz_path: str | Path,
        *,
        qec_code_bin: str,
        iterations: int,
        restarts: int,
        seed: int,
        target_weight: int | None = None,
        timeout_seconds: float = 300,
    ) -> dict[str, object]:
        candidate_id = Path(hx_path).parent.name
        if candidate_id == "backend-failure":
            raise SearchIntegrityError("backend failure")
        payload = real_run(
            hx_path,
            hz_path,
            qec_code_bin=qec_code_bin,
            iterations=iterations,
            restarts=restarts,
            seed=seed,
            target_weight=target_weight,
            timeout_seconds=timeout_seconds,
        )
        payload["test_candidate_id"] = candidate_id
        return payload

    def fake_convert(
        payload: object,
        hx_payload: dict,
        hz_payload: dict,
    ) -> dict[str, object]:
        assert isinstance(payload, dict)
        candidate_id = payload.get("test_candidate_id")
        if candidate_id == "conversion-failure":
            raise SearchIntegrityError("conversion failure")
        converted = real_convert(payload, hx_payload, hz_payload)
        if candidate_id == "basis-mismatch":
            converted["witness_payload"] = dict(converted["witness_payload"], basis="z")
        return converted

    monkeypatch.setattr(witness_batch, "run_qec_code_random_window_upper_bound", fake_run)
    monkeypatch.setattr(
        witness_batch,
        "convert_qec_code_random_window_upper_bound_result",
        fake_convert,
    )

    summary = witness_batch.attach_quantum_tanner_witnesses(
        work_root,
        campaign_id=config.campaign_id,
        search_space_path=None,
        fixture_catalog_path=config.catalog_path,
        witness_dir=witness_dir,
        basis="x",
        qec_code_bin=str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
        iterations=25,
        restarts=4,
        seed=17,
        target_weight=None,
        timeout_seconds=30.0,
    )

    assert summary["counts"] == {"attached": 1, "skipped": 0, "failed": 5}
    assert [candidate["candidate_id"] for candidate in summary["candidates"]] == [
        "missing-catalog",
        "missing-artifacts",
        "backend-failure",
        "conversion-failure",
        "basis-mismatch",
        "quantum-tanner-toric-d6",
    ]
    assert [candidate["status"] for candidate in summary["candidates"]] == [
        "failed",
        "failed",
        "failed",
        "failed",
        "failed",
        "attached",
    ]
    assert [candidate["reason"] for candidate in summary["candidates"]] == [
        "missing_catalog_entry",
        f"missing hx artifact: {(work_root / Path(missing_artifacts_entry['hx'])).resolve()}",
        "backend failure",
        "conversion failure",
        "incompatible witness basis: requested x, found z",
        "verified_upper_bound_witness",
    ]
    assert all(candidate["basis"] == "x" for candidate in summary["candidates"])
    assert [candidate["weight"] for candidate in summary["candidates"]] == [
        None,
        None,
        None,
        None,
        None,
        1,
    ]
    assert [candidate["search_space_updated"] for candidate in summary["candidates"]] == [
        False,
        False,
        False,
        False,
        False,
        True,
    ]

    updated_search_space = json.loads(search_space_path.read_text())
    updated_specs = updated_search_space["candidate_specs"]
    assert [
        spec.get("upper_bound_witness_path")
        for spec in updated_specs
    ] == [
        None,
        None,
        None,
        None,
        None,
        str(witness_dir / "quantum-tanner-toric-d6-upper-bound-witness.json"),
    ]


def test_attach_quantum_tanner_witnesses_preserves_unrelated_search_space_candidates() -> None:
    from autoqec_search.quantum_tanner_witness_batch import (
        attach_quantum_tanner_witnesses,
    )

    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-mixed-search-space"
    )
    witness_dir = Path("campaigns/examples/quantum-tanner-autoresearch/witnesses")
    search_space_path = work_root / config.search_space_path
    search_space = json.loads(search_space_path.read_text())
    targeted_candidate = dict(search_space["candidate_specs"][0])
    unrelated_parameter_candidate = {
        "candidate_id": "rotated-surface-d3-example",
        "code_family": "rotated-surface-code",
        "parameters": {"distance": 3},
        "provenance": {
            "kind": "zoo-fixture",
            "label": "rotated-surface-d3-example",
        },
    }
    unrelated_catalog_candidate = dict(
        search_space["candidate_specs"][1],
        candidate_id="other-catalog-candidate",
        fixture_catalog_path="campaigns/examples/other/fixture_catalog.json",
    )
    search_space["candidate_specs"] = [
        unrelated_parameter_candidate,
        unrelated_catalog_candidate,
        targeted_candidate,
    ]
    search_space_path.write_text(json.dumps(search_space, indent=2, sort_keys=True) + "\n")

    summary = attach_quantum_tanner_witnesses(
        work_root,
        campaign_id=config.campaign_id,
        search_space_path=None,
        fixture_catalog_path=config.catalog_path,
        witness_dir=witness_dir,
        basis="x",
        qec_code_bin=str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
        iterations=25,
        restarts=4,
        seed=17,
        target_weight=None,
        timeout_seconds=30.0,
    )

    assert summary["counts"] == {"attached": 1, "skipped": 0, "failed": 0}
    assert [candidate["candidate_id"] for candidate in summary["candidates"]] == [
        "quantum-tanner-toric-d4"
    ]

    updated_search_space = json.loads(search_space_path.read_text())
    assert updated_search_space["candidate_specs"][0] == unrelated_parameter_candidate
    assert updated_search_space["candidate_specs"][1] == unrelated_catalog_candidate
    assert updated_search_space["candidate_specs"][2]["upper_bound_witness_path"] == str(
        witness_dir / "quantum-tanner-toric-d4-upper-bound-witness.json"
    )


def test_attach_quantum_tanner_witnesses_rejects_unsafe_candidate_ids_without_writes() -> None:
    from autoqec_search.quantum_tanner_witness_batch import (
        attach_quantum_tanner_witnesses,
    )

    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-unsafe-candidate-ids"
    )
    witness_dir = Path("campaigns/examples/quantum-tanner-autoresearch/witnesses")
    search_space_path = work_root / config.search_space_path
    catalog_path = work_root / config.catalog_path

    unsafe_candidate_ids = [
        "bad/name",
        "..",
        r"bad\name",
        "bad\nname",
        "bad\x7fname",
        "bad\u0085name",
    ]
    catalog = json.loads(catalog_path.read_text())
    source_entry = catalog["entries"][0]
    catalog["entries"] = [
        dict(
            source_entry,
            candidate_id=candidate_id,
            provenance=dict(source_entry["provenance"], label=candidate_id),
        )
        for candidate_id in unsafe_candidate_ids
    ]
    catalog_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")

    search_space = json.loads(search_space_path.read_text())
    source_spec = dict(search_space["candidate_specs"][0])
    search_space["candidate_specs"] = [
        dict(source_spec, candidate_id=candidate_id)
        for candidate_id in unsafe_candidate_ids
    ]
    search_space_path.write_text(json.dumps(search_space, indent=2, sort_keys=True) + "\n")

    summary = attach_quantum_tanner_witnesses(
        work_root,
        campaign_id=config.campaign_id,
        search_space_path=None,
        fixture_catalog_path=config.catalog_path,
        witness_dir=witness_dir,
        basis="x",
        qec_code_bin=str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
        iterations=25,
        restarts=4,
        seed=17,
        target_weight=None,
        timeout_seconds=30.0,
    )

    assert summary["counts"] == {"attached": 0, "skipped": 0, "failed": 6}
    assert [candidate["candidate_id"] for candidate in summary["candidates"]] == unsafe_candidate_ids
    assert [candidate["status"] for candidate in summary["candidates"]] == [
        "failed",
        "failed",
        "failed",
        "failed",
        "failed",
        "failed",
    ]
    assert [
        candidate["reason"] for candidate in summary["candidates"]
    ] == [
        "candidate_id must be a safe path segment",
        "candidate_id must be a safe path segment",
        "candidate_id must be a safe path segment",
        "candidate_id must be a safe path segment",
        "candidate_id must be a safe path segment",
        "candidate_id must be a safe path segment",
    ]
    assert [candidate["witness_path"] for candidate in summary["candidates"]] == [
        None,
        None,
        None,
        None,
        None,
        None,
    ]
    assert not any((work_root / witness_dir).glob("*upper-bound-witness.json"))
    updated_search_space = json.loads(search_space_path.read_text())
    assert all(
        "upper_bound_witness_path" not in candidate_spec
        for candidate_spec in updated_search_space["candidate_specs"]
    )


def test_attach_quantum_tanner_witnesses_rejects_summary_search_space_output_collision() -> None:
    from autoqec_search.quantum_tanner_witness_batch import (
        attach_quantum_tanner_witnesses,
    )

    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-summary-search-space-collision"
    )
    witness_dir = Path("campaigns/examples/quantum-tanner-autoresearch/witnesses")
    collided_path = Path(
        "campaigns/examples/quantum-tanner-autoresearch/search_space.with-witnesses.json"
    )

    with pytest.raises(SearchIntegrityError, match="output paths must be distinct"):
        attach_quantum_tanner_witnesses(
            work_root,
            campaign_id=config.campaign_id,
            search_space_path=None,
            fixture_catalog_path=config.catalog_path,
            witness_dir=witness_dir,
            basis="x",
            qec_code_bin=str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
            iterations=25,
            restarts=4,
            seed=17,
            target_weight=None,
            timeout_seconds=30.0,
            out_search_space_path=collided_path,
            summary_path=collided_path,
        )

    assert not (work_root / collided_path).exists()
    assert not any((work_root / witness_dir).glob("*upper-bound-witness.json"))


def test_attach_quantum_tanner_witnesses_rejects_summary_witness_output_collision() -> None:
    from autoqec_search.quantum_tanner_witness_batch import (
        attach_quantum_tanner_witnesses,
    )

    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-summary-witness-collision"
    )
    witness_dir = Path("campaigns/examples/quantum-tanner-autoresearch/witnesses")
    collided_path = witness_dir / "quantum-tanner-toric-d4-upper-bound-witness.json"

    with pytest.raises(SearchIntegrityError, match="output paths must be distinct"):
        attach_quantum_tanner_witnesses(
            work_root,
            campaign_id=config.campaign_id,
            search_space_path=None,
            fixture_catalog_path=config.catalog_path,
            witness_dir=witness_dir,
            basis="x",
            qec_code_bin=str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
            iterations=25,
            restarts=4,
            seed=17,
            target_weight=None,
            timeout_seconds=30.0,
            summary_path=collided_path,
        )

    assert not (work_root / collided_path).exists()
    search_space = json.loads((work_root / config.search_space_path).read_text())
    assert all(
        "upper_bound_witness_path" not in candidate_spec
        for candidate_spec in search_space["candidate_specs"]
    )


def test_attach_quantum_tanner_witnesses_rejects_output_paths_resolving_outside_root(
    tmp_path: Path,
) -> None:
    from autoqec_search.quantum_tanner_witness_batch import (
        attach_quantum_tanner_witnesses,
    )

    work_root, config = _prepare_generated_quantum_tanner_workspace(
        GENERATED_QT_ROOT / "attach-witnesses-path-escape"
    )
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    (work_root / "linked-outside").symlink_to(outside_root, target_is_directory=True)

    with pytest.raises(SearchIntegrityError, match="witness_dir"):
        attach_quantum_tanner_witnesses(
            work_root,
            campaign_id=config.campaign_id,
            search_space_path=None,
            fixture_catalog_path=config.catalog_path,
            witness_dir=Path("linked-outside/witnesses"),
            basis="x",
            qec_code_bin=str(_write_fake_random_window_qec_code(work_root / "fake-qec-code-rw")),
            iterations=25,
            restarts=4,
            seed=17,
            target_weight=None,
            timeout_seconds=30.0,
        )

    assert list(outside_root.rglob("*.json")) == []
