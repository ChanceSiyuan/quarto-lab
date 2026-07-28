from __future__ import annotations

import json
from pathlib import Path

from autoqec_search.cli import main
from autoqec_search.structure import verify_css_upper_bound_witness


HX = {
    "format": "dense_binary_matrix",
    "n_rows": 1,
    "n_cols": 4,
    "data": [[1, 1, 0, 0]],
}
HZ = {
    "format": "dense_binary_matrix",
    "n_rows": 1,
    "n_cols": 4,
    "data": [[0, 0, 1, 1]],
}


def _verify(basis: str, vector: list[object]) -> dict:
    return verify_css_upper_bound_witness(HX, HZ, {"basis": basis, "vector": vector})


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def test_accepts_valid_x_type_witness_with_weight(
    tmp_path: Path,
    capsys,
) -> None:
    result = _verify("x", [0, 0, 1, 1])
    assert result["status"] == "pass"
    assert result["basis"] == "x"
    assert result["weight"] == 2
    assert result["distance_payload"]["bound_type"] == "upper"
    assert result["distance_payload"]["upper_bound"] == 2

    hx_path = tmp_path / "hx.json"
    hz_path = tmp_path / "hz.json"
    witness_path = tmp_path / "witness.json"
    _write_json(hx_path, HX)
    _write_json(hz_path, HZ)
    _write_json(witness_path, {"basis": "x", "vector": [0, 0, 1, 1]})

    assert (
        main(
            [
                "verify-witness",
                "--hx",
                str(hx_path),
                "--hz",
                str(hz_path),
                "--witness",
                str(witness_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == result


def test_accepts_valid_z_type_witness_with_weight() -> None:
    result = _verify("z", [1, 1, 0, 0])
    assert result["status"] == "pass"
    assert result["basis"] == "z"
    assert result["weight"] == 2
    assert result["distance_payload"]["bound_type"] == "upper"
    assert result["distance_payload"]["upper_bound"] == 2


def test_rejects_x_stabilizer_row_space_witness() -> None:
    assert _verify("x", [1, 1, 0, 0]) == {
        "status": "fail",
        "reason": "in_stabilizer_row_space",
    }


def test_rejects_z_stabilizer_row_space_witness() -> None:
    assert _verify("z", [0, 0, 1, 1]) == {
        "status": "fail",
        "reason": "in_stabilizer_row_space",
    }


def test_rejects_nonzero_syndrome_witness() -> None:
    assert _verify("x", [1, 0, 1, 0]) == {
        "status": "fail",
        "reason": "not_in_kernel",
    }


def test_rejects_length_mismatch() -> None:
    assert _verify("x", [0, 0, 1]) == {
        "status": "fail",
        "reason": "length_mismatch",
    }


def test_rejects_invalid_basis() -> None:
    assert _verify("y", [0, 0, 1, 1]) == {
        "status": "fail",
        "reason": "invalid_basis",
    }


def test_rejects_non_binary_entries_and_bools() -> None:
    assert _verify("x", [0, 0, 1, 2]) == {
        "status": "fail",
        "reason": "non_binary_vector",
    }
    assert _verify("x", [0, 0, 1, True]) == {
        "status": "fail",
        "reason": "non_binary_vector",
    }


REPO_ROOT = Path(__file__).resolve().parents[1]
WITNESS_FIXTURE_ROOT = (
    REPO_ROOT / "benchmarks" / "fixtures" / "upper-bound-witness"
)
QEC_CODE_REQUIRED_KEYS = {
    "status",
    "method",
    "bound_type",
    "upper_bound",
    "logical_class",
    "witness",
    "options",
    "provenance",
}


def _load_fixture_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_witness_fixture_manifest() -> dict:
    return _load_fixture_json(WITNESS_FIXTURE_ROOT / "manifest.json")


def _fixture_entries(payload_kind: str) -> list[dict]:
    manifest = _load_witness_fixture_manifest()
    return [
        entry
        for entry in manifest["fixtures"]
        if entry["payload_kind"] == payload_kind
    ]


def _qec_code_logical_class_to_basis(logical_class: str) -> str | None:
    return {
        "x_like": "x",
        "z_like": "z",
    }.get(logical_class)


def _validate_qec_code_random_window_contract(payload: dict) -> str | None:
    missing = sorted(QEC_CODE_REQUIRED_KEYS - payload.keys())
    if missing:
        if missing == ["witness"]:
            return "missing_witness"
        return "missing_required_key"
    if payload["status"] != "completed":
        return "invalid_status"
    if payload["method"] != "random-window-upper-bound":
        return "invalid_method"
    if payload["bound_type"] != "upper":
        return "invalid_bound_type"
    if type(payload["upper_bound"]) is not int or payload["upper_bound"] <= 0:
        return "invalid_upper_bound"
    witness = payload["witness"]
    if not isinstance(witness, dict):
        return "missing_witness"
    if set(witness) != {"x", "z", "weight"}:
        return "invalid_witness_keys"
    x_vector = witness["x"]
    z_vector = witness["z"]
    if not isinstance(x_vector, list) or not isinstance(z_vector, list):
        return "invalid_witness_vector"
    if len(x_vector) != len(z_vector):
        return "x_z_width_mismatch"
    entries = [*x_vector, *z_vector]
    if any(type(bit) is not int or bit not in {0, 1} for bit in entries):
        return "non_binary_witness_entry"
    if type(witness["weight"]) is not int or witness["weight"] <= 0:
        return "invalid_witness_weight"
    if payload["upper_bound"] != witness["weight"]:
        return "upper_bound_weight_mismatch"
    if sum(entries) != witness["weight"]:
        return "witness_weight_mismatch"
    if _qec_code_logical_class_to_basis(payload["logical_class"]) is None:
        return "unsupported_logical_class"
    if not isinstance(payload["options"], dict):
        return "invalid_options"
    if not isinstance(payload["provenance"], dict):
        return "invalid_provenance"
    return None


def test_upper_bound_witness_catalog_manifest_entries_resolve() -> None:
    manifest = _load_witness_fixture_manifest()

    assert manifest["catalog_id"] == "upper-bound-witness-known-answer-v1"
    assert manifest["hx_path"] == "hx.json"
    assert manifest["hz_path"] == "hz.json"
    assert _load_fixture_json(WITNESS_FIXTURE_ROOT / manifest["hx_path"]) == HX
    assert _load_fixture_json(WITNESS_FIXTURE_ROOT / manifest["hz_path"]) == HZ

    fixture_ids = {entry["id"] for entry in manifest["fixtures"]}
    assert fixture_ids == {
        "autoqec-x-logical",
        "autoqec-z-logical",
        "autoqec-x-stabilizer-row-space",
        "autoqec-x-length-mismatch",
        "qec-code-random-window-x-completed",
        "qec-code-random-window-z-completed",
        "qec-code-mixed-logical-class",
        "qec-code-upper-bound-weight-mismatch",
        "qec-code-x-z-width-mismatch",
        "qec-code-non-binary-witness-entry",
        "qec-code-malformed-missing-witness",
    }
    for entry in manifest["fixtures"]:
        assert entry["payload_kind"] in {"autoqec-witness", "qec-code-result"}
        assert entry["basis"] in {"x", "z", "mixed"}
        assert type(entry["expected_weight"]) is int
        assert entry["expected_verifier_status"] in {"pass", "fail", "not_applicable"}
        assert (WITNESS_FIXTURE_ROOT / entry["path"]).is_file()


def test_upper_bound_witness_catalog_autoqec_entries_match_verifier() -> None:
    manifest = _load_witness_fixture_manifest()
    hx_payload = _load_fixture_json(WITNESS_FIXTURE_ROOT / manifest["hx_path"])
    hz_payload = _load_fixture_json(WITNESS_FIXTURE_ROOT / manifest["hz_path"])
    results_by_id = {}

    for entry in _fixture_entries("autoqec-witness"):
        witness_payload = _load_fixture_json(WITNESS_FIXTURE_ROOT / entry["path"])
        result = verify_css_upper_bound_witness(
            hx_payload,
            hz_payload,
            witness_payload,
        )
        results_by_id[entry["id"]] = result
        assert result["status"] == entry["expected_verifier_status"]
        if entry["expected_verifier_status"] == "pass":
            assert result["basis"] == entry["basis"]
            assert result["weight"] == entry["expected_weight"]
            assert result["distance_payload"] == {
                "status": "completed",
                "method": "css-upper-bound-witness",
                "bound_type": "upper",
                "upper_bound": entry["expected_weight"],
                "basis": entry["basis"],
            }
        else:
            assert result["reason"] == entry["expected_reason"]

    assert results_by_id["autoqec-x-logical"]["weight"] == 2
    assert results_by_id["autoqec-z-logical"]["weight"] == 2
    assert results_by_id["autoqec-x-stabilizer-row-space"] == {
        "status": "fail",
        "reason": "in_stabilizer_row_space",
    }
    assert results_by_id["autoqec-x-length-mismatch"] == {
        "status": "fail",
        "reason": "length_mismatch",
    }


def test_qec_code_random_window_upper_bound_fixtures_match_contract() -> None:
    valid_ids = set()
    rejection_reasons = {}
    hx_payload = _load_fixture_json(WITNESS_FIXTURE_ROOT / "hx.json")
    hz_payload = _load_fixture_json(WITNESS_FIXTURE_ROOT / "hz.json")

    for entry in _fixture_entries("qec-code-result"):
        payload = _load_fixture_json(WITNESS_FIXTURE_ROOT / entry["path"])
        rejection_reason = _validate_qec_code_random_window_contract(payload)
        if entry["expected_contract_status"] == "valid":
            valid_ids.add(entry["id"])
            assert rejection_reason is None
            assert payload["status"] == "completed"
            assert payload["method"] == "random-window-upper-bound"
            assert payload["bound_type"] == "upper"
            assert payload["upper_bound"] == entry["expected_weight"]
            basis = _qec_code_logical_class_to_basis(payload["logical_class"])
            assert basis == entry["basis"]
            assert payload["witness"]["weight"] == entry["expected_weight"]
            assert set(payload["witness"]) == {"x", "z", "weight"}
            selected_vector = payload["witness"][basis]
            non_selected_component = (
                payload["witness"]["z"] if basis == "x" else payload["witness"]["x"]
            )
            assert all(bit == 0 for bit in non_selected_component)
            verify_result = verify_css_upper_bound_witness(
                hx_payload,
                hz_payload,
                {
                    "basis": basis,
                    "vector": selected_vector,
                },
            )
            assert verify_result["status"] == "pass"
            assert verify_result["weight"] == entry["expected_weight"]
            assert isinstance(payload["options"], dict)
            assert isinstance(payload["provenance"], dict)
        else:
            rejection_reasons[entry["id"]] = rejection_reason
            assert rejection_reason == entry["expected_rejection_reason"]

    assert valid_ids == {
        "qec-code-random-window-x-completed",
        "qec-code-random-window-z-completed",
    }
    assert rejection_reasons == {
        "qec-code-mixed-logical-class": "unsupported_logical_class",
        "qec-code-upper-bound-weight-mismatch": "upper_bound_weight_mismatch",
        "qec-code-x-z-width-mismatch": "x_z_width_mismatch",
        "qec-code-non-binary-witness-entry": "non_binary_witness_entry",
        "qec-code-malformed-missing-witness": "missing_witness",
    }
