from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from autoqec_search.quantum_tanner_proposals import (
    DegenerateQuantumTannerFace,
    GroupOrderLimitExceeded,
    InvalidGroupTable,
    InvalidLocalCodeMatrix,
    KnownToricTemplateDuplicate,
    LocalCodeWidthMismatch,
    NonSymmetricGeneratorSet,
    QuantumTannerProposalValidationError,
    validate_quantum_tanner_proposal,
    validate_quantum_tanner_proposal_file,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    REPO_ROOT / "benchmarks" / "schemas" / "quantum-tanner-proposal.schema.json"
)
FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "dihedral-d4-proposal.json"
)
CATALOG_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "catalog.json"
)
BAD_GROUP_TABLE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "invalid-bad-group-table.json"
)
OVERSIZED_GROUP_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "invalid-oversized-bad-associativity.json"
)
VALID_D3_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "valid-dihedral-d3.json"
)
KNOWN_TORIC_DUPLICATE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "known-toric-template-duplicate.json"
)
NONSYMMETRIC_GENERATORS_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "invalid-nonsymmetric-generators.json"
)
BAD_LOCAL_CODE_WIDTH_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "invalid-local-code-width.json"
)
DEGENERATE_FACE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "invalid-degenerate-face.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _validator() -> Draft202012Validator:
    return _validator_for_schema(SCHEMA_PATH)


def _validator_for_schema(schema_path: Path) -> Draft202012Validator:
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _resolve_repo_file(value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise AssertionError(f"{label} must be a non-empty repo-relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise AssertionError(f"{label} must be a safe repo-relative path: {value}")
    resolved = (REPO_ROOT / path).resolve()
    root = REPO_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise AssertionError(f"{label} must resolve inside repository root: {value}")
    if not resolved.is_file():
        raise AssertionError(f"missing {label}: {value}")
    return resolved


def _first_schema_error(
    validator: Draft202012Validator, proposal: dict
) -> ValidationError | None:
    errors = sorted(validator.iter_errors(proposal), key=lambda error: list(error.path))
    return errors[0] if errors else None


def _check_quantum_tanner_proposal_fixture_catalog(
    catalog: dict | None = None,
) -> dict[str, int]:
    catalog = _proposal_fixture_catalog() if catalog is None else catalog

    if catalog.get("catalog_id") != "quantum-tanner-proposal-fixtures-v1":
        raise AssertionError("catalog_id mismatch in proposal fixture catalog")
    if catalog.get("schema_version") != 1:
        raise AssertionError("schema_version mismatch in proposal fixture catalog")
    schema_path = _resolve_repo_file(catalog.get("schema_path"), label="schema_path")
    if schema_path.resolve() != SCHEMA_PATH.resolve():
        raise AssertionError("schema_path mismatch in proposal fixture catalog")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or not entries:
        raise AssertionError("proposal fixture catalog entries must be a non-empty list")

    validator = _validator_for_schema(schema_path)
    counts = {"valid": 0, "invalid": 0, "valid_non_toric": 0}
    seen_fixture_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise AssertionError("proposal fixture catalog entry must be an object")
        fixture_id = entry.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id:
            raise AssertionError("proposal fixture catalog entry fixture_id must be non-empty")
        if fixture_id in seen_fixture_ids:
            raise AssertionError(f"duplicate proposal fixture id: {fixture_id}")
        seen_fixture_ids.add(fixture_id)
        provenance = entry.get("provenance")
        if not isinstance(provenance, dict) or not provenance:
            raise AssertionError(f"{fixture_id} provenance must be a non-empty object")
        expected_status = entry.get("expected_status")
        if expected_status not in {"valid", "invalid"}:
            raise AssertionError(f"{fixture_id} expected_status must be valid or invalid")
        expected_error_kind = entry.get("expected_error_kind")
        if expected_status == "valid" and expected_error_kind is not None:
            raise AssertionError(f"{fixture_id} valid fixtures must not expect an error kind")
        if expected_status == "invalid" and not isinstance(expected_error_kind, str):
            raise AssertionError(f"{fixture_id} invalid fixtures must expect an error kind")

        proposal = _load_json(_resolve_repo_file(entry.get("path"), label=fixture_id))
        error = _first_schema_error(validator, proposal)
        actual_status = "invalid" if error is not None else "valid"
        if actual_status != expected_status:
            raise AssertionError(
                f"fixture verdict mismatch: {fixture_id} expected "
                f"{expected_status} got {actual_status}"
            )
        if error is not None:
            if error.validator != expected_error_kind:
                raise AssertionError(
                    f"fixture verdict mismatch: {fixture_id} expected "
                    f"{expected_error_kind} got {error.validator}"
                )
            expected_pointer = entry.get("expected_error_pointer")
            actual_pointer = _json_pointer(error)
            if expected_pointer is not None and expected_pointer != actual_pointer:
                raise AssertionError(
                    f"fixture verdict mismatch: {fixture_id} expected "
                    f"{expected_pointer} got {actual_pointer}"
                )
            counts["invalid"] += 1
        else:
            counts["valid"] += 1
            tags = proposal.get("search_hints", {}).get("tags", [])
            if isinstance(tags, list) and "non-toric" in tags:
                counts["valid_non_toric"] += 1

    if counts["valid_non_toric"] < 1:
        raise AssertionError("expected at least one schema-valid non-toric proposal")
    if counts["invalid"] < 2:
        raise AssertionError("expected at least two schema-invalid fixtures")
    return counts


def _fixture() -> dict:
    return _load_json(FIXTURE_PATH)


def _proposal_fixture_catalog() -> dict:
    return _load_json(CATALOG_PATH)


def _json_pointer(error: ValidationError) -> str:
    if not error.path:
        return "/"
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in error.path]
    return "/" + "/".join(escaped)


def test_quantum_tanner_proposal_schema_accepts_non_toric_fixture() -> None:
    _validator().validate(_fixture())


def test_quantum_tanner_proposal_fixture_catalog_is_complete() -> None:
    counts = _check_quantum_tanner_proposal_fixture_catalog()

    assert counts["valid_non_toric"] >= 1
    assert counts["invalid"] >= 2


def test_quantum_tanner_proposal_fixture_catalog_detects_bad_expected_verdict() -> None:
    catalog = copy.deepcopy(_proposal_fixture_catalog())
    entry = next(
        entry
        for entry in catalog["entries"]
        if entry["fixture_id"] == "valid-dihedral-d3"
    )
    entry["expected_status"] = "invalid"
    entry["expected_error_kind"] = "required"

    with pytest.raises(AssertionError, match="fixture verdict mismatch"):
        _check_quantum_tanner_proposal_fixture_catalog(catalog)


def test_quantum_tanner_proposal_schema_rejects_missing_required_fields() -> None:
    proposal = _fixture()
    del proposal["local_codes"]["field"]

    with pytest.raises(ValidationError) as exc_info:
        _validator().validate(proposal)

    assert _json_pointer(exc_info.value) == "/local_codes"
    assert exc_info.value.validator == "required"
    assert "'field' is a required property" in exc_info.value.message


def test_quantum_tanner_proposal_schema_rejects_malformed_generated_at_timestamp() -> None:
    proposal = copy.deepcopy(_fixture())
    proposal["provenance"]["generated_at"] = "not-a-timestamp"

    with pytest.raises(ValidationError) as exc_info:
        _validator().validate(proposal)

    assert _json_pointer(exc_info.value) == "/provenance/generated_at"
    assert exc_info.value.validator == "pattern"


def test_quantum_tanner_proposal_schema_rejects_unknown_top_level_fields() -> None:
    proposal = _fixture()
    proposal["unexpected"] = True

    with pytest.raises(ValidationError) as exc_info:
        _validator().validate(proposal)

    assert _json_pointer(exc_info.value) == "/"
    assert exc_info.value.validator == "additionalProperties"


def test_deterministic_proposal_validator_rejects_bad_group_table() -> None:
    with pytest.raises(InvalidGroupTable) as exc_info:
        validate_quantum_tanner_proposal_file(BAD_GROUP_TABLE_PATH, max_group_order=32)

    assert exc_info.value.kind == "InvalidGroupTable"


def test_deterministic_proposal_validator_rejects_group_order_over_limit_before_associativity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autoqec_search.quantum_tanner_proposals as proposals

    def fail_if_called(table: list[list[int]]) -> None:
        raise AssertionError("associativity check should not run")

    monkeypatch.setattr(proposals, "_validate_associativity", fail_if_called)

    with pytest.raises(GroupOrderLimitExceeded) as exc_info:
        validate_quantum_tanner_proposal_file(OVERSIZED_GROUP_PATH, max_group_order=8)

    assert exc_info.value.kind == "GroupOrderLimitExceeded"


def test_deterministic_proposal_validator_accepts_valid_non_toric_fixture() -> None:
    summary = validate_quantum_tanner_proposal_file(VALID_D3_PATH, max_group_order=32)

    assert summary.proposal_id == "valid-dihedral-d3"
    assert summary.group_order == 8
    assert summary.a_generator_count == 2
    assert summary.b_generator_count == 2
    assert summary.h_a_dimensions == (1, 2)
    assert summary.h_b_dimensions == (1, 2)
    assert summary.validator_version == "quantum-tanner-proposal-validator-v1"
    assert summary.fingerprint == "be862896e6fcf9278b92e826bf87f2dae3d82fd994509669f7716a299e09d23f"


def test_deterministic_proposal_validator_rejects_known_toric_template_duplicate() -> None:
    with pytest.raises(KnownToricTemplateDuplicate) as exc_info:
        validate_quantum_tanner_proposal_file(
            KNOWN_TORIC_DUPLICATE_PATH, max_group_order=32
        )

    assert exc_info.value.kind == "KnownToricTemplateDuplicate"


@pytest.mark.parametrize(
    "reversed_keys",
    [
        ("a_generator_indices",),
        ("b_generator_indices",),
        ("a_generator_indices", "b_generator_indices"),
    ],
)
def test_deterministic_proposal_validator_rejects_reversed_toric_generators(
    reversed_keys: tuple[str, ...],
) -> None:
    proposal = _load_json(KNOWN_TORIC_DUPLICATE_PATH)
    for key in reversed_keys:
        proposal[key] = list(reversed(proposal[key]))

    with pytest.raises(KnownToricTemplateDuplicate) as exc_info:
        validate_quantum_tanner_proposal(proposal)

    assert exc_info.value.kind == "KnownToricTemplateDuplicate"


def test_deterministic_proposal_validator_rejects_swapped_toric_roles() -> None:
    proposal = _load_json(KNOWN_TORIC_DUPLICATE_PATH)
    proposal["a_generator_indices"], proposal["b_generator_indices"] = (
        proposal["b_generator_indices"],
        proposal["a_generator_indices"],
    )
    proposal["local_codes"]["h_a"], proposal["local_codes"]["h_b"] = (
        proposal["local_codes"]["h_b"],
        proposal["local_codes"]["h_a"],
    )

    with pytest.raises(KnownToricTemplateDuplicate) as exc_info:
        validate_quantum_tanner_proposal(proposal)

    assert exc_info.value.kind == "KnownToricTemplateDuplicate"


def test_deterministic_proposal_validator_rejects_nonsymmetric_generators() -> None:
    with pytest.raises(NonSymmetricGeneratorSet) as exc_info:
        validate_quantum_tanner_proposal_file(
            NONSYMMETRIC_GENERATORS_PATH, max_group_order=32
        )

    assert exc_info.value.kind == "NonSymmetricGeneratorSet"


def test_deterministic_proposal_validator_rejects_nonbipartite_cayley_graph() -> None:
    proposal = _load_json(VALID_D3_PATH)
    order = 10
    proposal["proposal_id"] = "invalid-c10-nonbipartite"
    proposal["base_group"] = {
        "name": "C10",
        "element_order": "id = x for x in Z10",
        "order": order,
        "identity": 0,
        "multiplication_table": [
            [(left + right) % order for right in range(order)]
            for left in range(order)
        ],
    }
    proposal["a_generator_indices"] = [1, 9]
    proposal["b_generator_indices"] = [2, 8]
    proposal["local_codes"]["h_a"] = [[1, 1]]
    proposal["local_codes"]["h_b"] = [[1, 1]]

    with pytest.raises(QuantumTannerProposalValidationError) as exc_info:
        validate_quantum_tanner_proposal(proposal)

    assert exc_info.value.kind == "NonBipartiteCayleyGraph"
    assert "adjacent vertices" in exc_info.value.message


def test_deterministic_proposal_validator_rejects_bad_local_code_width() -> None:
    with pytest.raises(LocalCodeWidthMismatch) as exc_info:
        validate_quantum_tanner_proposal_file(
            BAD_LOCAL_CODE_WIDTH_PATH, max_group_order=32
        )

    assert exc_info.value.kind == "LocalCodeWidthMismatch"


def test_deterministic_proposal_validator_rejects_degenerate_face() -> None:
    with pytest.raises(DegenerateQuantumTannerFace) as exc_info:
        validate_quantum_tanner_proposal_file(DEGENERATE_FACE_PATH, max_group_order=32)

    assert exc_info.value.kind == "DegenerateQuantumTannerFace"
    assert "degenerate quantum Tanner face" in exc_info.value.message


@pytest.mark.parametrize("matrix_key", ["h_a", "h_b"])
def test_deterministic_proposal_validator_rejects_boolean_matrix_entries(
    matrix_key: str,
) -> None:
    proposal = _load_json(VALID_D3_PATH)
    proposal["local_codes"][matrix_key][0][0] = True

    with pytest.raises(InvalidLocalCodeMatrix) as exc_info:
        validate_quantum_tanner_proposal(proposal)

    assert exc_info.value.kind == "InvalidLocalCodeMatrix"


def test_deterministic_proposal_fingerprint_ignores_metadata() -> None:
    proposal = _load_json(VALID_D3_PATH)
    control = validate_quantum_tanner_proposal(proposal)

    mutated = copy.deepcopy(proposal)
    mutated["provenance"]["generated_at"] = "2099-12-31T23:59:59Z"
    mutated["search_hints"]["tags"] = ["modified", "metadata"]
    mutated["search_hints"]["notes"] = "metadata-only change for hash-stability test"

    trial = validate_quantum_tanner_proposal(mutated)

    assert trial.fingerprint == control.fingerprint


def test_validate_quantum_tanner_proposal_cli_reports_pass_and_typed_failures() -> None:
    import os
    import subprocess
    import sys

    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    valid = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate-quantum-tanner-proposal",
            "--proposal",
            str(VALID_D3_PATH),
            "--max-group-order",
            "32",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert valid.returncode == 0, valid.stderr
    assert "PASS quantum_tanner_proposal proposal_id=valid-dihedral-d3" in valid.stdout

    toric = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate-quantum-tanner-proposal",
            "--proposal",
            str(KNOWN_TORIC_DUPLICATE_PATH),
            "--max-group-order",
            "32",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert toric.returncode == 1
    assert "KnownToricTemplateDuplicate" in toric.stderr

    oversized = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate-quantum-tanner-proposal",
            "--proposal",
            str(OVERSIZED_GROUP_PATH),
            "--max-group-order",
            "8",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert oversized.returncode == 1
    assert "GroupOrderLimitExceeded" in oversized.stderr


@pytest.mark.parametrize(
    ("path", "value", "expected_pointer"),
    [
        (("construction_mode",), "covered_left_right_v1", "/construction_mode"),
        (("local_codes", "field"), "GF(4)", "/local_codes/field"),
        (("local_codes", "matrix_role"), "generator", "/local_codes/matrix_role"),
    ],
)
def test_quantum_tanner_proposal_schema_rejects_unsupported_modes(
    path: tuple[str, ...], value: object, expected_pointer: str
) -> None:
    proposal = copy.deepcopy(_fixture())
    target = proposal
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValidationError) as exc_info:
        _validator().validate(proposal)

    assert _json_pointer(exc_info.value) == expected_pointer
