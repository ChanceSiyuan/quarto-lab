from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_SCHEMA = json.loads(
    (REPO_ROOT / "zoo" / "schemas" / "code-instance.schema.json").read_text()
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _assert_dense_binary_matrix_payload(payload: dict) -> None:
    assert payload["format"] == "dense_binary_matrix"
    assert payload["n_rows"] == len(payload["data"])
    assert all(len(row) == payload["n_cols"] for row in payload["data"])
    assert all(bit in [0, 1] for row in payload["data"] for bit in row)


def _run_tensorqec_generator(
    tmp_path: Path, *args: str, fresh_depot: bool = False
) -> tuple[subprocess.CompletedProcess[str], Path]:
    julia = shutil.which("julia")
    if julia is None:
        pytest.skip("julia is not installed")

    output_root = tmp_path / "instance"
    env = os.environ.copy()
    if fresh_depot:
        env["JULIA_DEPOT_PATH"] = str(tmp_path / "julia-depot")
    result = subprocess.run(
        [
            julia,
            "--startup-file=no",
            "--history-file=no",
            "--project=julia/tensorqec_env",
            "julia/tensorqec_env/scripts/generate_instance.jl",
            *args,
            "--output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    return result, output_root


def test_build_command_rejects_missing_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-zoo"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "autoqec_zoo.cli", "build", "--root", str(missing_root)],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2
    assert "zoo root does not exist" in result.stderr


def test_build_command_writes_expected_artifacts(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "zoo", work_root / "zoo")
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_zoo.cli",
            "build",
            "--root",
            str(work_root / "zoo"),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "built zoo artifacts" in result.stdout
    assert (work_root / "zoo" / "views" / "site" / "index.html").exists()
    assert (work_root / "zoo" / "views" / "instance-index.json").exists()


def test_build_command_runs_from_repo_root_without_pythonpath(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "zoo", work_root / "zoo")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_zoo.cli",
            "build",
            "--root",
            str(work_root / "zoo"),
            "--date",
            "2026-05-27",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0
    assert "built zoo artifacts under" in result.stdout
    assert (work_root / "zoo" / "views" / "site" / "index.html").exists()


def test_bivariate_bicycle_fallback_generator_reproduces_checked_in_instance(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "bb-instance"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_bivariate_bicycle_instance.py",
            "--m",
            "6",
            "--n",
            "6",
            "--vc",
            "[[3,0],[0,1],[0,2]]",
            "--hd",
            "[[0,3],[1,0],[2,0]]",
            "--generated-at",
            "2026-06-16T00:00:00Z",
            "--output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0, result.stderr
    checked_in_root = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    for artifact_name in ("hx.json", "hz.json"):
        assert (output_root / artifact_name).read_text() == (
            checked_in_root / artifact_name
        ).read_text()
    checked_in_instance = _load_json(checked_in_root / "instance.json")
    assert checked_in_instance["parameters"]["generator"] == {
        "m": 6,
        "n": 6,
        "vc": [[3, 0], [0, 1], [0, 2]],
        "hd": [[0, 3], [1, 0], [2, 0]],
        "source_convention": "autoqec-bivariate-bicycle-fallback",
    }


@pytest.mark.slow
def test_tensorqec_generator_writes_rotated_surface_instance(tmp_path: Path) -> None:
    result, output_root = _run_tensorqec_generator(
        tmp_path,
        "--code-id",
        "rotated-surface-code",
        "--distance",
        "3",
    )

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in output_root.iterdir()) == [
        "hx.json",
        "hz.json",
        "instance.json",
    ]

    instance = _load_json(output_root / "instance.json")
    Draft202012Validator(INSTANCE_SCHEMA).validate(instance)
    assert instance["id"] == "rotated-surface-code-d3"
    assert instance["code_id"] == "rotated-surface-code"
    assert instance["family_id"] == "surface-code"
    assert instance["parameters"] == {"distance": 3, "layout": "rotated"}
    assert instance["provenance"]["generator_parameters"] == {
        "distance": 3,
        "layout": "rotated",
    }

    hx = _load_json(output_root / "hx.json")
    hz = _load_json(output_root / "hz.json")
    _assert_dense_binary_matrix_payload(hx)
    _assert_dense_binary_matrix_payload(hz)
    assert instance["derived_properties"] == {
        "distance": None,
        "n": hx["n_cols"],
        "kx": None,
        "kz": None,
        "mx": hx["n_rows"],
        "mz": hz["n_rows"],
    }


@pytest.mark.slow
def test_tensorqec_generator_writes_rotated_surface_instance_from_fresh_depot(
    tmp_path: Path,
) -> None:
    result, output_root = _run_tensorqec_generator(
        tmp_path,
        "--code-id",
        "rotated-surface-code",
        "--distance",
        "3",
        fresh_depot=True,
    )

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in output_root.iterdir()) == [
        "hx.json",
        "hz.json",
        "instance.json",
    ]

    instance = _load_json(output_root / "instance.json")
    Draft202012Validator(INSTANCE_SCHEMA).validate(instance)
    assert instance["id"] == "rotated-surface-code-d3"
    assert instance["code_id"] == "rotated-surface-code"
    assert instance["family_id"] == "surface-code"
    assert instance["parameters"] == {"distance": 3, "layout": "rotated"}
    assert instance["provenance"]["generator_parameters"] == {
        "distance": 3,
        "layout": "rotated",
    }

    hx = _load_json(output_root / "hx.json")
    hz = _load_json(output_root / "hz.json")
    _assert_dense_binary_matrix_payload(hx)
    _assert_dense_binary_matrix_payload(hz)
    assert instance["derived_properties"] == {
        "distance": None,
        "n": hx["n_cols"],
        "kx": None,
        "kz": None,
        "mx": hx["n_rows"],
        "mz": hz["n_rows"],
    }


@pytest.mark.slow
def test_tensorqec_distance_script_reports_rotated_surface_distance(
    tmp_path: Path,
) -> None:
    result, output_root = _run_tensorqec_generator(
        tmp_path,
        "--code-id",
        "rotated-surface-code",
        "--distance",
        "3",
    )

    assert result.returncode == 0, result.stderr

    julia = shutil.which("julia")
    if julia is None:
        pytest.skip("julia is not installed")

    distance_result = subprocess.run(
        [
            julia,
            "--startup-file=no",
            "--history-file=no",
            "--project=julia/tensorqec_env",
            "julia/tensorqec_env/scripts/compute_distance.jl",
            "--hx-path",
            str(output_root / "hx.json"),
            "--hz-path",
            str(output_root / "hz.json"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert distance_result.returncode == 0, distance_result.stderr
    assert json.loads(distance_result.stdout) == {"distance": 3}


@pytest.mark.slow
def test_tensorqec_generator_writes_unrotated_surface_instance(tmp_path: Path) -> None:
    result, output_root = _run_tensorqec_generator(
        tmp_path,
        "--code-id",
        "surface-code",
        "--distance",
        "3",
    )

    assert result.returncode == 0, result.stderr

    instance = _load_json(output_root / "instance.json")
    Draft202012Validator(INSTANCE_SCHEMA).validate(instance)
    assert instance["id"] == "surface-code-d3"
    assert instance["code_id"] == "surface-code"
    assert instance["family_id"] == "surface-code"
    assert instance["parameters"] == {"distance": 3, "layout": "unrotated"}
    assert instance["provenance"]["generator_parameters"] == {
        "distance": 3,
        "layout": "unrotated",
    }

    hx = _load_json(output_root / "hx.json")
    hz = _load_json(output_root / "hz.json")
    _assert_dense_binary_matrix_payload(hx)
    _assert_dense_binary_matrix_payload(hz)
    assert hx["n_cols"] == hz["n_cols"]
    assert instance["derived_properties"]["n"] == hx["n_cols"]
    assert instance["derived_properties"]["kx"] is None
    assert instance["derived_properties"]["kz"] is None


@pytest.mark.slow
def test_tensorqec_generator_writes_bbcode_instance(tmp_path: Path) -> None:
    result, output_root = _run_tensorqec_generator(
        tmp_path,
        "--code-id",
        "bivariate-bicycle-code",
        "--m",
        "6",
        "--n",
        "6",
        "--vc",
        "[[1,0],[0,1]]",
        "--hd",
        "[[1,1],[0,2]]",
    )

    assert result.returncode == 0, result.stderr

    instance = _load_json(output_root / "instance.json")
    Draft202012Validator(INSTANCE_SCHEMA).validate(instance)
    assert instance["id"] == "bivariate-bicycle-code-m6-n6"
    assert instance["code_id"] == "bivariate-bicycle-code"
    assert instance["family_id"] == "bivariate-bicycle-code"
    assert instance["parameters"] == {
        "m": 6,
        "n": 6,
        "vc": [[1, 0], [0, 1]],
        "hd": [[1, 1], [0, 2]],
    }
    assert instance["provenance"]["generator_parameters"] == instance["parameters"]

    hx = _load_json(output_root / "hx.json")
    hz = _load_json(output_root / "hz.json")
    _assert_dense_binary_matrix_payload(hx)
    _assert_dense_binary_matrix_payload(hz)
    assert hx["n_cols"] == hz["n_cols"]
    assert instance["derived_properties"]["mx"] == hx["n_rows"]
    assert instance["derived_properties"]["mz"] == hz["n_rows"]


@pytest.mark.slow
def test_tensorqec_generator_rejects_invalid_vc_json(tmp_path: Path) -> None:
    result, output_root = _run_tensorqec_generator(
        tmp_path,
        "--code-id",
        "bivariate-bicycle-code",
        "--m",
        "6",
        "--n",
        "6",
        "--vc",
        "not-json",
        "--hd",
        "[[1,1],[0,2]]",
    )

    assert result.returncode != 0
    assert "--vc must be valid JSON" in result.stderr
    assert "JSON parsing error" not in result.stderr
    assert not output_root.exists()


@pytest.mark.slow
def test_tensorqec_generator_rejects_invalid_hd_json(tmp_path: Path) -> None:
    result, output_root = _run_tensorqec_generator(
        tmp_path,
        "--code-id",
        "bivariate-bicycle-code",
        "--m",
        "6",
        "--n",
        "6",
        "--vc",
        "[[1,0],[0,1]]",
        "--hd",
        "not-json",
    )

    assert result.returncode != 0
    assert "--hd must be valid JSON" in result.stderr
    assert "JSON parsing error" not in result.stderr
    assert not output_root.exists()


def test_cli_eczoo_builds_index(tmp_path):
    from autoqec_zoo.cli import main

    zoo_root = tmp_path / "zoo"
    raw_codes = zoo_root / "external" / "eczoo" / "raw" / "codes" / "topo"
    raw_codes.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "eczoo" / "codes" / "topo" / "surface.yml"
    (raw_codes / "surface.yml").write_text(fixture.read_text())
    schemas = zoo_root / "schemas"
    schemas.mkdir()
    real_schemas = Path(__file__).parents[1] / "zoo" / "schemas"
    for name in ("eczoo-code.schema.json", "eczoo-relation.schema.json"):
        (schemas / name).write_text((real_schemas / name).read_text())

    rc = main(["eczoo", "--root", str(zoo_root), "--date", "2026-05-29"])

    assert rc == 0
    assert (zoo_root / "external" / "eczoo" / "index" / "eczoo-codes.json").exists()
