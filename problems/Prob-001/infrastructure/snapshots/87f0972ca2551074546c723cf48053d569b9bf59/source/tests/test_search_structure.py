from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.structure import gf2_rank, summarize_css_structure


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_ROOT = (
    REPO_ROOT
    / "zoo"
    / "codes"
    / "rotated-surface-code"
    / "instances"
    / "rotated-surface-code-d3"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_gf2_rank_handles_dependent_rows() -> None:
    assert gf2_rank([[1, 0, 1], [0, 1, 1], [1, 1, 0]]) == 2
    assert gf2_rank([[1, 0, 0], [0, 1, 0], [0, 0, 1]]) == 3


def test_summarize_css_structure_reports_rotated_d3() -> None:
    summary = summarize_css_structure(
        _load_json(INSTANCE_ROOT / "hx.json"),
        _load_json(INSTANCE_ROOT / "hz.json"),
    )

    assert summary == {
        "status": "completed",
        "n": 9,
        "k": 1,
        "rank_hx": 4,
        "rank_hz": 4,
        "mx": 4,
        "mz": 4,
        "css_commute": True,
        "commutation_failures": [],
    }


def test_summarize_css_structure_reports_commutation_failure() -> None:
    hx = _load_json(INSTANCE_ROOT / "hx.json")
    hz = _load_json(INSTANCE_ROOT / "hz.json")
    hz["data"][0][2] = 1

    summary = summarize_css_structure(hx, hz)

    assert summary["status"] == "failed"
    assert summary["css_commute"] is False
    assert summary["commutation_failures"] == [{"hx_row": 0, "hz_row": 0}]


def test_summarize_css_structure_rejects_mismatched_column_counts() -> None:
    hx = _load_json(INSTANCE_ROOT / "hx.json")
    hz = _load_json(INSTANCE_ROOT / "hz.json")
    hz["n_cols"] = 10

    with pytest.raises(SearchIntegrityError, match="matrix column mismatch"):
        summarize_css_structure(hx, hz)


def test_summarize_css_structure_rejects_non_object_hx_payload() -> None:
    hz = _load_json(INSTANCE_ROOT / "hz.json")

    with pytest.raises(SearchIntegrityError, match="invalid matrix payload"):
        summarize_css_structure([], hz)


def test_summarize_css_structure_rejects_negative_empty_matrix_dimensions() -> None:
    hx = {
        "format": "dense_binary_matrix",
        "n_rows": 0,
        "n_cols": -1,
        "data": [],
    }
    hz = {
        "format": "dense_binary_matrix",
        "n_rows": 0,
        "n_cols": -1,
        "data": [],
    }

    with pytest.raises(SearchIntegrityError, match="invalid matrix dimensions"):
        summarize_css_structure(hx, hz)
