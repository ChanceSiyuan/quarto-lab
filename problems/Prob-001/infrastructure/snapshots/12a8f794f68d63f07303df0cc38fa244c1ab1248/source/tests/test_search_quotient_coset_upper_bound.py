from __future__ import annotations

import json
from pathlib import Path

import pytest

import autoqec_search.cli as search_cli
import autoqec_search.quotient_coset_upper_bound as quotient_search
from autoqec_search.load import SearchIntegrityError
from autoqec_search.cli import _atomic_write_witness_with_provenance, main
from autoqec_search.quotient_coset_upper_bound import (
    METHOD,
    _RowSpace,
    _build_logical_reps,
    _greedy_reduce,
    _kernel_basis,
    _rows_to_ints,
    _vector_to_list,
    find_quotient_coset_upper_bound,
)
from autoqec_search.structure import verify_css_upper_bound_witness


HX_4 = {
    "format": "dense_binary_matrix",
    "n_rows": 1,
    "n_cols": 4,
    "data": [[1, 1, 0, 0]],
}
HZ_4 = {
    "format": "dense_binary_matrix",
    "n_rows": 1,
    "n_cols": 4,
    "data": [[0, 0, 1, 1]],
}
REPO_ROOT = Path(__file__).resolve().parents[1]
D5_INSTANCE = (
    REPO_ROOT
    / "benchmarks"
    / "distance_ladders"
    / "surface-toric-bb-kasai-tanner-v2"
    / "instances"
    / "surface-rotated-d5"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def test_rows_to_ints_and_vector_round_trip() -> None:
    rows = _rows_to_ints([[1, 0, 1], [0, 1, 1]], num_cols=3, label="fixture")
    assert rows == [0b101, 0b110]
    assert _vector_to_list(0b101, 3) == [1, 0, 1]


def test_kernel_basis_vectors_have_zero_syndrome() -> None:
    rows = _rows_to_ints([[1, 1, 0], [0, 1, 1]], num_cols=3, label="check")
    kernel = _kernel_basis(rows, 3)
    assert kernel == [0b111]
    assert all((row & kernel[0]).bit_count() % 2 == 0 for row in rows)


def test_row_space_reduction_and_quotient_reps() -> None:
    span = _RowSpace([0b0011])
    assert span.contains(0b0011)
    assert not span.contains(0b1100)
    reps = _build_logical_reps([0b0011, 0b1100], [0b0011], seed=7)
    assert reps == [0b1100]


def test_greedy_reduce_lowers_coset_weight() -> None:
    reduced = _greedy_reduce(0b1111, [0b0011], seed=5, deadline_seconds=1.0, passes=3)
    assert reduced == 0b1100


def test_find_quotient_coset_upper_bound_is_deterministic_and_verified() -> None:
    first = find_quotient_coset_upper_bound(
        HX_4,
        HZ_4,
        basis="both",
        seed=19,
        max_no_improvement=64,
        timeout_seconds=5,
    )
    second = find_quotient_coset_upper_bound(
        HX_4,
        HZ_4,
        basis="both",
        seed=19,
        max_no_improvement=64,
        timeout_seconds=5,
    )
    assert {
        key: value
        for key, value in first.items()
        if key != "provenance"
    } == {
        key: value
        for key, value in second.items()
        if key != "provenance"
    }
    assert first["provenance"]["seed"] == second["provenance"]["seed"] == 19
    assert first["provenance"]["basis_requested"] == second["provenance"]["basis_requested"] == "both"
    assert first["provenance"]["max_no_improvement"] == second["provenance"]["max_no_improvement"] == 64
    assert first["status"] == "completed"
    assert first["method"] == METHOD
    assert first["bound_type"] == "upper"
    # This fixture has a weight-one logical in each requested CSS quotient.
    assert first["upper_bound"] == 1
    assert first["distance_payload"] == {
        "status": "completed",
        "method": "css-upper-bound-witness",
        "bound_type": "upper",
        "upper_bound": 1,
        "basis": first["basis"],
    }
    assert first["verification"]["status"] == "pass"
    assert verify_css_upper_bound_witness(HX_4, HZ_4, first["witness_payload"])["status"] == "pass"


def test_basis_x_and_z_requests_return_requested_basis() -> None:
    x_result = find_quotient_coset_upper_bound(
        HX_4,
        HZ_4,
        basis="x",
        seed=1,
        max_no_improvement=32,
        timeout_seconds=5,
    )
    z_result = find_quotient_coset_upper_bound(
        HX_4,
        HZ_4,
        basis="z",
        seed=1,
        max_no_improvement=32,
        timeout_seconds=5,
    )

    assert x_result["basis"] == "x"
    assert z_result["basis"] == "z"


def test_public_rotated_surface_d5_fixture_finds_weight_five_upper_bound() -> None:
    result = find_quotient_coset_upper_bound(
        _load(D5_INSTANCE / "hx.json"),
        _load(D5_INSTANCE / "hz.json"),
        basis="both",
        seed=2026,
        max_no_improvement=128,
        timeout_seconds=10,
    )

    assert result["upper_bound"] == 5
    assert result["distance_payload"]["upper_bound"] == 5
    assert result["verification"]["status"] == "pass"


def test_rejects_noncommuting_css_checks_before_search() -> None:
    hx = {
        "format": "dense_binary_matrix",
        "n_rows": 1,
        "n_cols": 2,
        "data": [[1, 0]],
    }
    hz = {
        "format": "dense_binary_matrix",
        "n_rows": 1,
        "n_cols": 2,
        "data": [[1, 1]],
    }

    with pytest.raises(SearchIntegrityError, match="commute"):
        find_quotient_coset_upper_bound(
            hx,
            hz,
            basis="both",
            seed=0,
            max_no_improvement=8,
            timeout_seconds=5,
        )


def test_timeout_can_expire_during_matrix_preprocessing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClock:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self) -> float:
            self.calls += 1
            return 0.0 if self.calls <= 6 else 2.0

    clock = FakeClock()
    monkeypatch.setattr(quotient_search.time, "monotonic", clock)

    with pytest.raises(SearchIntegrityError, match="timeout"):
        find_quotient_coset_upper_bound(
            HX_4,
            HZ_4,
            basis="both",
            seed=0,
            max_no_improvement=8,
            timeout_seconds=1,
        )


def test_finder_preprocessing_does_not_call_monolithic_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_helper(*args: object, **kwargs: object) -> object:
        raise AssertionError("monolithic preprocessing helper was called")

    monkeypatch.setattr(quotient_search, "matrix_data", forbidden_helper, raising=False)
    monkeypatch.setattr(
        quotient_search,
        "commutation_failures",
        forbidden_helper,
        raising=False,
    )
    monkeypatch.setattr(
        quotient_search,
        "_matrix_num_cols",
        forbidden_helper,
        raising=False,
    )

    result = find_quotient_coset_upper_bound(
        HX_4,
        HZ_4,
        basis="both",
        seed=19,
        max_no_improvement=64,
        timeout_seconds=5,
    )

    assert result["status"] == "completed"
    assert result["verification"]["status"] == "pass"


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"basis": "y"}, "basis"),
        ({"seed": -1}, "seed"),
        ({"seed": True}, "seed"),
        ({"max_no_improvement": 0}, "max_no_improvement"),
        ({"timeout_seconds": 0}, "timeout_seconds"),
        ({"timeout_seconds": 300.1}, "timeout_seconds"),
    ],
)
def test_rejects_invalid_options(options: dict[str, object], message: str) -> None:
    with pytest.raises(SearchIntegrityError, match=message):
        find_quotient_coset_upper_bound(HX_4, HZ_4, **options)


def test_rejects_width_mismatch() -> None:
    bad_hz = {
        "format": "dense_binary_matrix",
        "n_rows": 1,
        "n_cols": 3,
        "data": [[1, 0, 1]],
    }

    with pytest.raises(SearchIntegrityError, match="column mismatch"):
        find_quotient_coset_upper_bound(HX_4, bad_hz, timeout_seconds=5)


def test_rejects_ragged_and_nonbinary_matrices() -> None:
    ragged = {
        "format": "dense_binary_matrix",
        "n_rows": 1,
        "n_cols": 4,
        "data": [[1, 0, 1]],
    }
    nonbinary = {
        "format": "dense_binary_matrix",
        "n_rows": 1,
        "n_cols": 4,
        "data": [[1, 0, 2, 0]],
    }

    with pytest.raises(SearchIntegrityError, match="matrix column mismatch"):
        find_quotient_coset_upper_bound(ragged, HZ_4, timeout_seconds=5)
    with pytest.raises(SearchIntegrityError, match="non-binary"):
        find_quotient_coset_upper_bound(nonbinary, HZ_4, timeout_seconds=5)


def test_rejects_code_with_no_logical_witness() -> None:
    hx = {
        "format": "dense_binary_matrix",
        "n_rows": 2,
        "n_cols": 2,
        "data": [[1, 0], [0, 1]],
    }
    hz = {
        "format": "dense_binary_matrix",
        "n_rows": 0,
        "n_cols": 2,
        "data": [],
    }

    with pytest.raises(
        SearchIntegrityError,
        match="no quotient-coset upper-bound witness found",
    ):
        find_quotient_coset_upper_bound(
            hx,
            hz,
            basis="x",
            seed=0,
            max_no_improvement=8,
            timeout_seconds=5,
        )


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def test_cli_writes_witness_and_distinct_provenance_sidecar(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hx_path = tmp_path / "hx.json"
    hz_path = tmp_path / "hz.json"
    out_path = tmp_path / "witness.json"
    _write_json(hx_path, HX_4)
    _write_json(hz_path, HZ_4)

    assert main([
        "find-quotient-coset-upper-bound",
        "--hx",
        str(hx_path),
        "--hz",
        str(hz_path),
        "--basis",
        "both",
        "--out",
        str(out_path),
        "--seed",
        "19",
        "--max-no-improvement",
        "64",
        "--timeout-seconds",
        "5",
    ]) == 0

    witness = json.loads(out_path.read_text())
    provenance = json.loads((tmp_path / "witness.json.provenance.json").read_text())
    assert witness["basis"] in {"x", "z"}
    assert witness["vector"]
    assert provenance["method"] == METHOD
    assert provenance["basis_requested"] == "both"
    assert provenance["distance_payload"]["bound_type"] == "upper"
    assert "found quotient-coset upper-bound witness" in capsys.readouterr().out


def test_cli_rejects_same_witness_and_provenance_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hx_path = tmp_path / "hx.json"
    hz_path = tmp_path / "hz.json"
    out_path = tmp_path / "witness.json"
    _write_json(hx_path, HX_4)
    _write_json(hz_path, HZ_4)

    assert main([
        "find-quotient-coset-upper-bound",
        "--hx",
        str(hx_path),
        "--hz",
        str(hz_path),
        "--basis",
        "both",
        "--out",
        str(out_path),
        "--provenance-out",
        str(out_path),
    ]) == 1
    assert not out_path.exists()
    assert "provenance output path must be distinct" in capsys.readouterr().err


def test_cli_leaves_no_artifacts_on_search_failure(tmp_path: Path) -> None:
    hx_path = tmp_path / "hx.json"
    hz_path = tmp_path / "hz.json"
    out_path = tmp_path / "witness.json"
    provenance_path = tmp_path / "provenance.json"
    _write_json(hx_path, {"format": "dense_binary_matrix", "n_rows": 2, "n_cols": 2, "data": [[1, 0], [0, 1]]})
    _write_json(hz_path, {"format": "dense_binary_matrix", "n_rows": 0, "n_cols": 2, "data": []})

    assert main([
        "find-quotient-coset-upper-bound",
        "--hx",
        str(hx_path),
        "--hz",
        str(hz_path),
        "--basis",
        "x",
        "--out",
        str(out_path),
        "--provenance-out",
        str(provenance_path),
        "--max-no-improvement",
        "8",
        "--timeout-seconds",
        "5",
    ]) == 1
    assert not out_path.exists()
    assert not provenance_path.exists()


def test_cli_rolls_back_artifacts_when_provenance_publish_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hx_path = tmp_path / "hx.json"
    hz_path = tmp_path / "hz.json"
    out_path = tmp_path / "witness.json"
    provenance_path = tmp_path / "provenance.json"
    _write_json(hx_path, HX_4)
    _write_json(hz_path, HZ_4)

    original_replace = Path.replace

    def fail_provenance_publish(source: Path, target: str | Path) -> Path:
        if Path(target) == provenance_path:
            raise OSError("simulated provenance publish failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_provenance_publish)

    assert main([
        "find-quotient-coset-upper-bound",
        "--hx",
        str(hx_path),
        "--hz",
        str(hz_path),
        "--basis",
        "both",
        "--out",
        str(out_path),
        "--provenance-out",
        str(provenance_path),
        "--seed",
        "19",
        "--max-no-improvement",
        "64",
        "--timeout-seconds",
        "5",
    ]) == 1
    assert not out_path.exists()
    assert not provenance_path.exists()
    assert "could not write witness and provenance outputs" in capsys.readouterr().err


def test_atomic_publish_removes_obsolete_backups(tmp_path: Path) -> None:
    witness_path = tmp_path / "witness.json"
    provenance_path = tmp_path / "provenance.json"
    _write_json(witness_path, {"version": "old-witness"})
    _write_json(provenance_path, {"version": "old-provenance"})

    _atomic_write_witness_with_provenance(
        witness_path,
        {"version": "new-witness"},
        provenance_path,
        {"version": "new-provenance"},
    )

    assert json.loads(witness_path.read_text()) == {"version": "new-witness"}
    assert json.loads(provenance_path.read_text()) == {"version": "new-provenance"}
    assert list(tmp_path.glob("*.bak")) == []
    assert list(tmp_path.glob(".*.bak")) == []


def test_atomic_publish_failure_restores_preexisting_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    witness_path = tmp_path / "witness.json"
    provenance_path = tmp_path / "provenance.json"
    _write_json(witness_path, {"version": "old-witness"})
    _write_json(provenance_path, {"version": "old-provenance"})
    original_replace = Path.replace

    def fail_provenance_publish(source: Path, target: str | Path) -> Path:
        if Path(target) == provenance_path and source.suffix == ".tmp":
            raise OSError("simulated provenance publish failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_provenance_publish)

    with pytest.raises(SearchIntegrityError, match="could not write witness"):
        _atomic_write_witness_with_provenance(
            witness_path,
            {"version": "new-witness"},
            provenance_path,
            {"version": "new-provenance"},
        )

    assert json.loads(witness_path.read_text()) == {"version": "old-witness"}
    assert json.loads(provenance_path.read_text()) == {"version": "old-provenance"}
    assert list(tmp_path.glob(".*.bak")) == []


def test_atomic_restore_failure_preserves_failed_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    witness_path = tmp_path / "witness.json"
    provenance_path = tmp_path / "provenance.json"
    old_witness = {"version": "old-witness"}
    _write_json(witness_path, old_witness)
    _write_json(provenance_path, {"version": "old-provenance"})
    original_path_replace = Path.replace
    original_os_replace = search_cli.os.replace

    def fail_provenance_publish(source: Path, target: str | Path) -> Path:
        if Path(target) == provenance_path and source.suffix == ".tmp":
            raise OSError("simulated provenance publish failure")
        return original_path_replace(source, target)

    def fail_witness_restore(source: str | Path, target: str | Path) -> None:
        source_path = Path(source)
        if source_path.suffix == ".bak" and Path(target) == witness_path:
            raise OSError("simulated witness restore failure")
        original_os_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_provenance_publish)
    monkeypatch.setattr(search_cli.os, "replace", fail_witness_restore)

    with pytest.raises(SearchIntegrityError, match="rollback failed"):
        _atomic_write_witness_with_provenance(
            witness_path,
            {"version": "new-witness"},
            provenance_path,
            {"version": "new-provenance"},
        )

    failed_backups = list(tmp_path.glob(".witness.json.*.bak"))
    assert len(failed_backups) == 1
    assert json.loads(failed_backups[0].read_text()) == old_witness
