from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from autoqec_search.structure import (
    complete_logical_observable_basis,
    gf2_rank,
    gf2_vector_in_kernel,
    matrix_data,
    verify_css_upper_bound_witness,
)
from autoqec_search.screening import (
    resolve_catalog_backed_candidate,
    screen_upper_bound_candidate,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
QT_CAMPAIGN_ID = "quantum-tanner-autoresearch"
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
Z_WITNESS_PATH = (
    "campaigns/examples/quantum-tanner-autoresearch/witnesses/"
    "quantum-tanner-toric-d4-z-upper-bound-witness.json"
)
Z_PAYLOAD_PATH = (
    "campaigns/examples/quantum-tanner-autoresearch/witnesses/"
    "quantum-tanner-toric-d4-z-upper-bound-payload.json"
)


def _qt_d4_candidate_spec(**extra: object) -> dict:
    candidate_spec = {
        "candidate_id": "quantum-tanner-toric-d4",
        "code_family": "quantum-tanner-code",
        "fixture_catalog_path": (
            "campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json"
        ),
        "provenance": {
            "kind": "distance-ladder-fixture",
            "label": "quantum-tanner-toric-d4",
        },
    }
    candidate_spec.update(extra)
    return candidate_spec


def _sparse_rows_to_dense_rows(payload: dict) -> list[list[int]]:
    rows = []
    for sparse_row in payload["rows"]:
        dense_row = [0] * payload["num_cols"]
        for column in sparse_row:
            dense_row[column] = 1
        rows.append(dense_row)
    return rows


def _assert_logical_x_observable_basis(
    candidate, payload: dict, expected_rows: int
) -> None:
    assert payload["format"] == "sparse_rows"
    assert payload["num_cols"] == candidate.hx["n_cols"]
    assert len(payload["rows"]) == expected_rows
    hx = matrix_data(candidate.hx, "hx.json")
    hz = matrix_data(candidate.hz, "hz.json")
    dense_rows = _sparse_rows_to_dense_rows(payload)
    for row in dense_rows:
        assert gf2_vector_in_kernel(hz, row)
    assert gf2_rank([*hx, *dense_rows]) == gf2_rank(hx) + expected_rows


def test_logical_observable_basis_completes_quantum_tanner_d4_witness() -> None:
    candidate_spec = _qt_d4_candidate_spec(
        upper_bound_witness_path=(
            "campaigns/examples/quantum-tanner-autoresearch/witnesses/"
            "quantum-tanner-toric-d4-upper-bound-witness.json"
        )
    )
    candidate = resolve_catalog_backed_candidate(
        REPO_ROOT,
        candidate_spec,
        campaign_id=QT_CAMPAIGN_ID,
    )
    assert candidate is not None
    witness = {
        "basis": "x",
        "vector": [1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    }
    hx = matrix_data(candidate.hx, "hx.json")
    hz = matrix_data(candidate.hz, "hz.json")

    rows = complete_logical_observable_basis(
        kernel_rows=hz,
        stabilizer_rows=hx,
        preferred_vector=witness["vector"],
    )

    assert rows[0] == witness["vector"]
    assert len(rows) == 2
    for row in rows:
        assert gf2_vector_in_kernel(hz, row)
    assert gf2_rank([*hx, *rows]) == gf2_rank(hx) + 2


def test_screen_upper_bound_candidate_admits_inline_upper_bound_payload() -> None:
    candidate_spec = _qt_d4_candidate_spec(
        upper_bound_payload={
            "status": "completed",
            "method": "css-upper-bound-witness",
            "bound_type": "upper",
            "upper_bound": 4,
            "basis": "x",
        }
    )
    candidate = resolve_catalog_backed_candidate(
        REPO_ROOT,
        candidate_spec,
        campaign_id=QT_CAMPAIGN_ID,
    )
    assert candidate is not None
    candidate = replace(
        candidate,
        observables_x={"format": "sparse_rows", "num_cols": 16, "rows": [[0, 1, 8, 12]]},
    )

    decision = screen_upper_bound_candidate(
        REPO_ROOT,
        candidate=candidate,
        candidate_spec=candidate_spec,
    )

    assert decision.screening_status == "admitted"
    assert decision.distance_bound_type == "upper"
    assert decision.distance_upper_bound == 4
    assert decision.reason == "loaded_upper_bound_payload"
    assert decision.distance_payload_override == candidate_spec["upper_bound_payload"]
    assert decision.observables_x_override == candidate.observables_x


def test_screen_upper_bound_candidate_fails_payload_without_explicit_observables() -> None:
    candidate_spec = _qt_d4_candidate_spec(
        upper_bound_payload={
            "status": "completed",
            "method": "css-upper-bound-witness",
            "bound_type": "upper",
            "upper_bound": 4,
            "basis": "x",
        }
    )
    candidate = resolve_catalog_backed_candidate(
        REPO_ROOT,
        candidate_spec,
        campaign_id=QT_CAMPAIGN_ID,
    )
    assert candidate is not None

    decision = screen_upper_bound_candidate(
        REPO_ROOT,
        candidate=candidate,
        candidate_spec=candidate_spec,
    )

    assert decision.screening_status == "failed"
    assert decision.distance_bound_type == "upper"
    assert decision.distance_upper_bound is None
    assert decision.reason == "missing_explicit_logical_observables"


def test_screen_upper_bound_candidate_marks_malformed_inputs_failed() -> None:
    candidate_spec = _qt_d4_candidate_spec(
        upper_bound_witness_path=(
            "campaigns/examples/quantum-tanner-autoresearch/witnesses/"
            "quantum-tanner-toric-d4-upper-bound-witness.json"
        ),
        upper_bound_payload={
            "status": "completed",
            "method": "css-upper-bound-witness",
            "bound_type": "upper",
            "upper_bound": 4,
            "basis": "x",
        },
    )
    candidate = resolve_catalog_backed_candidate(
        REPO_ROOT,
        candidate_spec,
        campaign_id=QT_CAMPAIGN_ID,
    )
    assert candidate is not None

    decision = screen_upper_bound_candidate(
        REPO_ROOT,
        candidate=candidate,
        candidate_spec=candidate_spec,
    )

    assert decision.screening_status == "failed"
    assert decision.distance_bound_type == "upper"
    assert decision.distance_upper_bound is None
    assert decision.reason == "candidate has multiple upper-bound inputs"


def test_screen_upper_bound_candidate_admits_x_witness_for_memory_x_task() -> None:
    candidate_spec = _qt_d4_candidate_spec(upper_bound_witness_path=(
        "campaigns/examples/quantum-tanner-autoresearch/witnesses/"
        "quantum-tanner-toric-d4-upper-bound-witness.json"
    ))
    candidate = resolve_catalog_backed_candidate(
        REPO_ROOT,
        candidate_spec,
        campaign_id=QT_CAMPAIGN_ID,
    )
    assert candidate is not None

    decision = screen_upper_bound_candidate(
        REPO_ROOT,
        candidate=candidate,
        candidate_spec=candidate_spec,
        benchmark_task=QT_TASK,
    )

    assert decision.screening_status == "admitted"
    assert decision.reason == "verified_upper_bound_witness"
    assert decision.distance_upper_bound == 4
    assert decision.observables_x_override is not None
    assert decision.observables_x_override["rows"][0] == [0, 1, 8, 12]
    _assert_logical_x_observable_basis(
        candidate,
        decision.observables_x_override,
        expected_rows=2,
    )


def test_screen_upper_bound_candidate_rejects_x_witness_outside_kernel_before_observables(
    tmp_path: Path,
) -> None:
    witness_path = tmp_path / "bad-x-witness.json"
    witness_path.write_text(
        '{"basis": "x", "vector": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}'
    )
    candidate_spec = _qt_d4_candidate_spec(
        upper_bound_witness_path="bad-x-witness.json"
    )
    candidate = resolve_catalog_backed_candidate(
        REPO_ROOT,
        candidate_spec,
        campaign_id=QT_CAMPAIGN_ID,
    )
    assert candidate is not None

    decision = screen_upper_bound_candidate(
        tmp_path,
        candidate=candidate,
        candidate_spec=candidate_spec,
        benchmark_task=QT_TASK,
    )

    assert decision.screening_status == "failed"
    assert decision.reason == "not_in_kernel"
    assert decision.observables_x_override is None


def test_screen_upper_bound_candidate_rejects_z_witness_for_memory_x_task() -> None:
    candidate_spec = _qt_d4_candidate_spec(upper_bound_witness_path=Z_WITNESS_PATH)
    candidate = resolve_catalog_backed_candidate(
        REPO_ROOT,
        candidate_spec,
        campaign_id=QT_CAMPAIGN_ID,
    )
    assert candidate is not None

    verification = verify_css_upper_bound_witness(
        candidate.hx,
        candidate.hz,
        {
            "basis": "z",
            "vector": [1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        },
    )
    assert verification["status"] == "pass"
    assert verification["basis"] == "z"

    decision = screen_upper_bound_candidate(
        REPO_ROOT,
        candidate=candidate,
        candidate_spec=candidate_spec,
        benchmark_task=QT_TASK,
    )

    assert decision.screening_status == "failed"
    assert decision.distance_bound_type == "upper"
    assert decision.distance_upper_bound is None
    assert decision.reason == "incompatible_upper_bound_witness_basis"
    assert decision.observables_x_override is None


def test_screen_upper_bound_candidate_rejects_inline_z_payload_for_memory_x_task() -> None:
    candidate_spec = _qt_d4_candidate_spec(
        upper_bound_payload={
            "status": "completed",
            "method": "css-upper-bound-witness",
            "bound_type": "upper",
            "upper_bound": 4,
            "basis": "z",
        }
    )
    candidate = resolve_catalog_backed_candidate(
        REPO_ROOT,
        candidate_spec,
        campaign_id=QT_CAMPAIGN_ID,
    )
    assert candidate is not None
    candidate = replace(
        candidate,
        observables_x={"format": "sparse_rows", "num_cols": 16, "rows": [[0, 1, 8, 12]]},
    )

    decision = screen_upper_bound_candidate(
        REPO_ROOT,
        candidate=candidate,
        candidate_spec=candidate_spec,
        benchmark_task=QT_TASK,
    )

    assert decision.screening_status == "failed"
    assert decision.reason == "incompatible_upper_bound_witness_basis"
    assert decision.distance_payload_override is None
    assert decision.observables_x_override is None


def test_screen_upper_bound_candidate_rejects_z_payload_path_for_memory_x_task() -> None:
    candidate_spec = _qt_d4_candidate_spec(upper_bound_payload_path=Z_PAYLOAD_PATH)
    candidate = resolve_catalog_backed_candidate(
        REPO_ROOT,
        candidate_spec,
        campaign_id=QT_CAMPAIGN_ID,
    )
    assert candidate is not None
    candidate = replace(
        candidate,
        observables_x={"format": "sparse_rows", "num_cols": 16, "rows": [[0, 1, 8, 12]]},
    )

    decision = screen_upper_bound_candidate(
        REPO_ROOT,
        candidate=candidate,
        candidate_spec=candidate_spec,
        benchmark_task=QT_TASK,
    )

    assert decision.screening_status == "failed"
    assert decision.reason == "incompatible_upper_bound_witness_basis"
    assert decision.distance_payload_override is None
    assert decision.observables_x_override is None
