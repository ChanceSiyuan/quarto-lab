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


def test_surface_single_logical_baseline_rejects_failures_above_shots(
    tmp_path: Path,
) -> None:
    corrupted_path = _corrupted_manifest_path(tmp_path, {"failures": 10001})

    with pytest.raises(SearchIntegrityError, match="failures.*shots"):
        load_surface_single_logical_baseline(corrupted_path)


def test_surface_single_logical_baseline_rejects_ler_drift(
    tmp_path: Path,
) -> None:
    corrupted_path = _corrupted_manifest_path(tmp_path, {"ler": 0.001})

    with pytest.raises(SearchIntegrityError, match="ler must equal failures / shots"):
        load_surface_single_logical_baseline(corrupted_path)


def test_surface_single_logical_baseline_rejects_bad_ci_containment(
    tmp_path: Path,
) -> None:
    corrupted_path = _corrupted_manifest_path(
        tmp_path,
        {"ci_low": 0.0009, "ci_high": 0.0011},
    )

    with pytest.raises(SearchIntegrityError, match="ler must lie inside the CI"):
        load_surface_single_logical_baseline(corrupted_path)


def test_surface_single_logical_baseline_rejects_missing_schema_for_copied_manifest(
    tmp_path: Path,
) -> None:
    work_root = tmp_path / "work"
    baseline_dir = work_root / "benchmarks" / "baselines"
    baseline_dir.mkdir(parents=True)

    target = baseline_dir / BASELINE_PATH.name
    shutil.copyfile(BASELINE_PATH, target)

    with pytest.raises(
        SearchIntegrityError,
        match="surface-single-logical-baseline.schema.json",
    ):
        load_surface_single_logical_baseline(target)
