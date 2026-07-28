from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from autoqec_search.baselines import load_surface_single_logical_baseline
from autoqec_search.load import SearchIntegrityError


REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = (
    REPO_ROOT
    / "benchmarks"
    / "baselines"
    / "rotated-surface-single-logical-p001.json"
)


def _loaded_rows() -> list[dict]:
    manifest = load_surface_single_logical_baseline(BASELINE_PATH)
    rows = manifest["rows"]
    assert rows
    return rows


def _corrupted_manifest_path(tmp_path: Path, row_update: dict) -> Path:
    work_root = tmp_path / "work"
    baseline_dir = work_root / "benchmarks" / "baselines"
    schema_dir = work_root / "benchmarks" / "schemas"
    baseline_dir.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "benchmarks" / "schemas", schema_dir)

    payload = json.loads(BASELINE_PATH.read_text())
    payload = deepcopy(payload)
    payload["rows"][0].update(row_update)

    target = baseline_dir / BASELINE_PATH.name
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return target


def test_surface_single_logical_baseline_accepts_valid_p001_manifest() -> None:
    manifest = load_surface_single_logical_baseline(BASELINE_PATH)

    assert manifest["baseline_id"] == "rotated-surface-single-logical-p001"
    assert manifest["code_id"] == "rotated-surface-code"
    assert manifest["layout"] == "rotated"
    assert [row["p"] for row in manifest["rows"]] == [0.001, 0.001, 0.001]


def test_surface_single_logical_baseline_rows_are_single_logical() -> None:
    rows = _loaded_rows()

    assert all(row["logical_qubits"] == 1 for row in rows)


def test_surface_single_logical_baseline_rows_use_distance_squared_physical_qubits() -> None:
    rows = _loaded_rows()

    assert all(row["physical_qubits"] == row["distance"] ** 2 for row in rows)


def test_surface_single_logical_baseline_rejects_bad_p001_row(tmp_path: Path) -> None:
    corrupted_path = _corrupted_manifest_path(tmp_path, {"p": 0.01})

    with pytest.raises(SearchIntegrityError, match="p=0.001"):
        load_surface_single_logical_baseline(corrupted_path)


def test_surface_single_logical_baseline_rejects_multi_logical_row(
    tmp_path: Path,
) -> None:
    corrupted_path = _corrupted_manifest_path(tmp_path, {"logical_qubits": 2})

    with pytest.raises(SearchIntegrityError, match="logical_qubits.*1"):
        load_surface_single_logical_baseline(corrupted_path)
