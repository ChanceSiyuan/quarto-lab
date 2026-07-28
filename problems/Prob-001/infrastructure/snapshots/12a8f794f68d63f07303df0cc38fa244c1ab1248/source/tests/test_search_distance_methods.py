from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.distance_methods import (
    COPIED_ZOO_EXACT,
    RSTIM_ILP_EXACT,
    DistanceMethodOptions,
    compute_distance_payload,
    dense_binary_matrix_to_sparse_rows,
    load_distance_payload,
    load_distance_payload_from_dict,
    normalize_distance_method_options,
)
from autoqec_search.eval_candidates import CandidateInput, ResolvedCandidate
from autoqec_search.load import SearchIntegrityError


def _candidate(*, distance: int = 3) -> ResolvedCandidate:
    return ResolvedCandidate(
        spec=CandidateInput(
            candidate_id="example",
            campaign_id="campaign",
            code_family="code",
            parameters={"distance": distance},
            provenance={"kind": "test", "label": "unit"},
        ),
        artifact_root=Path("/tmp/source-instance"),
        instance={
            "id": "source-instance",
            "code_id": "code",
            "parameters": {"distance": distance},
            "derived_properties": {"distance": distance},
        },
        hx={
            "format": "dense_binary_matrix",
            "n_rows": 2,
            "n_cols": 4,
            "data": [[1, 0, 1, 0], [0, 0, 0, 1]],
        },
        hz={
            "format": "dense_binary_matrix",
            "n_rows": 1,
            "n_cols": 4,
            "data": [[0, 1, 0, 1]],
        },
        source_kind="zoo-instance",
    )


def test_normalize_distance_method_options_defaults_to_exact() -> None:
    options = normalize_distance_method_options(method=None, seed=11)

    assert options.method == "copied-zoo-exact"
    assert options.qec_code_bin == "qec-code"


def test_copied_zoo_exact_payload_has_contract_metadata() -> None:
    payload = compute_distance_payload(
        _candidate(distance=5),
        normalize_distance_method_options(method=COPIED_ZOO_EXACT, qec_code_bin="qec-code"),
    )

    assert payload["status"] == "completed"
    assert payload["distance"] == 5
    assert payload["method"] == COPIED_ZOO_EXACT
    assert payload["bound_type"] == "exact"
    assert payload["options"] == {"method": COPIED_ZOO_EXACT, "qec_code_bin": "qec-code"}
    assert payload["provenance"] == {
        "source": "zoo-instance",
        "source_instance_id": "source-instance",
        "source_instance_path": "/tmp/source-instance",
    }


def test_normalize_distance_method_options_accepts_guarded_rstim_exact() -> None:
    options = normalize_distance_method_options(
        method=RSTIM_ILP_EXACT,
        qec_code_bin="/tmp/qec-code",
    )

    assert options.method == RSTIM_ILP_EXACT
    assert options.qec_code_bin == "/tmp/qec-code"


def test_compute_distance_payload_reports_unavailable_rstim_exact_backend() -> None:
    with pytest.raises(SearchIntegrityError, match="rstim exact CSS distance backend is not available"):
        compute_distance_payload(
            _candidate(distance=3),
            DistanceMethodOptions(method=RSTIM_ILP_EXACT, qec_code_bin="/definitely/missing/qec-code"),
        )


def test_dense_binary_matrix_to_sparse_rows() -> None:
    payload = dense_binary_matrix_to_sparse_rows(
        {
            "format": "dense_binary_matrix",
            "n_rows": 3,
            "n_cols": 5,
            "data": [
                [1, 0, 1, 0, 0],
                [0, 0, 0, 0, 0],
                [0, 1, 0, 1, 1],
            ],
        }
    )

    assert payload == {
        "format": "sparse_rows",
        "num_cols": 5,
        "rows": [[0, 2], [], [1, 3, 4]],
    }


def test_dense_binary_matrix_to_sparse_rows_accepts_empty_checks() -> None:
    payload = dense_binary_matrix_to_sparse_rows(
        {
            "format": "dense_binary_matrix",
            "n_rows": 0,
            "n_cols": 5,
            "data": [],
        }
    )

    assert payload == {"format": "sparse_rows", "num_cols": 5, "rows": []}


def test_load_distance_payload_accepts_legacy_exact(tmp_path: Path) -> None:
    path = tmp_path / "distance.json"
    path.write_text(
        json.dumps(
            {
                "status": "completed",
                "distance": 3,
                "method": "copied-from-zoo-instance",
            }
        )
        + "\n"
    )

    loaded = load_distance_payload(path)

    assert loaded.distance == 3
    assert loaded.method == "copied-from-zoo-instance"
    assert loaded.bound_type == "exact"


def test_load_distance_payload_rejects_randomized_payload_without_upper_bound_type() -> None:
    with pytest.raises(SearchIntegrityError, match="randomized-upper-bound.*bound_type upper"):
        load_distance_payload_from_dict(
            {
                "status": "completed",
                "distance": 3,
                "method": "randomized-upper-bound",
                "upper_bound": 3,
            },
            label="test distance",
        )


def test_load_distance_payload_rejects_unknown_upper_bound_method() -> None:
    with pytest.raises(SearchIntegrityError, match="upper-bound distance payload"):
        load_distance_payload_from_dict(
            {
                "status": "completed",
                "distance": 3,
                "method": "some-upper-bound",
                "bound_type": "upper",
                "upper_bound": 3,
            },
            label="test distance",
        )


def test_load_distance_payload_rejects_unknown_upper_bound_method_without_bound_type() -> None:
    with pytest.raises(SearchIntegrityError, match="upper-bound distance payload"):
        load_distance_payload_from_dict(
            {
                "status": "completed",
                "distance": 3,
                "method": "some-upper-bound",
                "upper_bound": 3,
            },
            label="test distance",
        )


def test_load_distance_payload_from_dict_rejects_bad_upper_bound() -> None:
    with pytest.raises(SearchIntegrityError, match="upper_bound"):
        load_distance_payload_from_dict(
            {
                "status": "completed",
                "distance": 3,
                "method": "randomized-upper-bound",
                "bound_type": "upper",
                "upper_bound": 2,
            },
            label="test distance",
        )
