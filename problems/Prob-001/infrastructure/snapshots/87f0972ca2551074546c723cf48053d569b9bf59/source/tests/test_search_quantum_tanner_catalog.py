from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from autoqec_search.cli import main
from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_catalog import (
    load_quantum_tanner_fixture_catalog,
    normalize_quantum_tanner_fixture_entry,
    resolve_quantum_tanner_fixture_entry,
    validate_quantum_tanner_fixture_catalog,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = (
    REPO_ROOT
    / "campaigns"
    / "examples"
    / "quantum-tanner-autoresearch"
    / "fixture_catalog.json"
)
EXPECTED_CANDIDATES = [
    "quantum-tanner-toric-d4",
    "quantum-tanner-toric-d6",
    "quantum-tanner-toric-d8",
]
DISTANCE_LADDER_REL = Path(
    "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2"
)
GENERATED_CATALOG_REL = Path(
    "campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _catalog() -> dict:
    return _load_json(CATALOG_PATH)


def _entry_by_id() -> dict[str, dict]:
    return {entry["candidate_id"]: entry for entry in _catalog()["entries"]}


def _copy_catalog_repo(tmp_path: Path) -> Path:
    work_root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    return work_root


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _normalized_quantum_tanner_spec_path(spec_path: Path) -> str:
    prefix = Path("benchmarks/distance_ladders")
    return str(spec_path.relative_to(prefix))


def _write_generated_toric_fixture(
    work_root: Path,
    *,
    distance: int,
    n: int,
    matrix_num_cols: int | None = None,
) -> dict:
    candidate_id = f"quantum-tanner-toric-d{distance}"
    fixture_rel = DISTANCE_LADDER_REL / "instances" / candidate_id
    spec_rel = DISTANCE_LADDER_REL / "quantum_tanner_specs" / f"toric-d{distance}.json"
    fixture_dir = work_root / fixture_rel
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (work_root / spec_rel).parent.mkdir(parents=True, exist_ok=True)

    num_cols = matrix_num_cols if matrix_num_cols is not None else n
    _write_json(
        fixture_dir / "hx.json",
        {"format": "sparse_rows", "num_cols": num_cols, "rows": [[0], [1, 2]]},
    )
    _write_json(
        fixture_dir / "hz.json",
        {"format": "sparse_rows", "num_cols": num_cols, "rows": [[0, 1], [2]]},
    )
    _write_json(
        work_root / spec_rel,
        {
            "family": "quantum_tanner_toric_test_fixture",
            "distance": distance,
            "note": "temporary test artifact",
        },
    )
    _write_json(
        fixture_dir / "instance.json",
        {
            "instance_id": candidate_id,
            "code_id": "quantum-tanner-code",
            "qec_code_spec": f"quantum_tanner:toric_d{distance}",
            "quantum_tanner_spec": _normalized_quantum_tanner_spec_path(spec_rel),
            "n": n,
            "k": 2,
            "expected_distance": distance,
            "expected_bound_type": "exact",
            "artifacts": {"hx": "hx.json", "hz": "hz.json"},
        },
    )
    return {
        "candidate_id": candidate_id,
        "code_id": "quantum-tanner-code",
        "n": n,
        "k": 2,
        "distance": distance,
        "hx": str(fixture_rel / "hx.json"),
        "hz": str(fixture_rel / "hz.json"),
        "source_fixture_path": str(fixture_rel),
        "source_instance": str(fixture_rel / "instance.json"),
        "provenance": {
            "kind": "distance-ladder-fixture",
            "label": candidate_id,
            "distance_ladder": "surface-toric-bb-kasai-tanner-v2",
            "qec_code_spec": f"quantum_tanner:toric_d{distance}",
            "quantum_tanner_spec": str(spec_rel),
            "generator": "test-fixture-generator",
            "construction_mode": "lr_cayley_no_cover_v1",
            "base_group": f"Z{distance}xZ{distance}",
        },
        "search_ready": True,
        "adaptation": "catalog-normalized-finite-css-instance",
    }


def _matrix_num_cols(path: Path) -> int:
    payload = _load_json(path)
    assert payload["format"] == "sparse_rows"
    num_cols = payload["num_cols"]
    assert type(num_cols) is int and num_cols > 0
    rows = payload["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, list)
        previous = -1
        for column in row:
            assert type(column) is int
            assert 0 <= column < num_cols
            assert column > previous
            previous = column
    return num_cols


def test_catalog_contains_exact_pinned_m1_smoke_entries() -> None:
    catalog = _catalog()

    assert catalog["catalog_id"] == "quantum-tanner-autoresearch-m1-fixtures"
    assert catalog["schema_version"] == 1
    assert [entry["candidate_id"] for entry in catalog["entries"]] == EXPECTED_CANDIDATES

    expected = {
        "quantum-tanner-toric-d4": {"n": 16, "k": 2, "distance": 4},
        "quantum-tanner-toric-d6": {"n": 36, "k": 2, "distance": 6},
        "quantum-tanner-toric-d8": {"n": 64, "k": 2, "distance": 8},
    }
    for candidate_id, fields in expected.items():
        entry = _entry_by_id()[candidate_id]
        for key, value in fields.items():
            assert entry[key] == value
        for required in (
            "candidate_id",
            "code_id",
            "n",
            "k",
            "hx",
            "hz",
            "source_fixture_path",
            "source_instance",
            "provenance",
            "search_ready",
        ):
            assert required in entry
        assert entry["code_id"] == "quantum-tanner-code"
        assert entry["source_fixture_path"].endswith(f"/instances/{candidate_id}")
        assert entry["hx"].endswith(f"/instances/{candidate_id}/hx.json")
        assert entry["hz"].endswith(f"/instances/{candidate_id}/hz.json")
        assert entry["source_instance"].endswith(f"/instances/{candidate_id}/instance.json")
        assert entry["provenance"]["kind"] == "distance-ladder-fixture"
        assert entry["provenance"]["label"] == candidate_id
        assert entry["provenance"]["quantum_tanner_spec"].endswith(
            f"/quantum_tanner_specs/toric-d{entry['distance']}.json"
        )
        assert entry["search_ready"] is True
        assert entry["adaptation"] == "catalog-normalized-finite-css-instance"


def test_catalog_matrix_artifacts_exist_with_matching_binary_columns() -> None:
    for entry in _catalog()["entries"]:
        hx_path = REPO_ROOT / entry["hx"]
        hz_path = REPO_ROOT / entry["hz"]

        assert hx_path.is_file()
        assert hz_path.is_file()
        assert _matrix_num_cols(hx_path) == entry["n"]
        assert _matrix_num_cols(hz_path) == entry["n"]


def test_search_ready_entries_normalize_to_search_layer_candidate_fields() -> None:
    catalog = load_quantum_tanner_fixture_catalog(REPO_ROOT)
    search_ready_entries = [
        entry for entry in catalog["entries"] if entry["search_ready"] is True
    ]
    assert [entry["candidate_id"] for entry in search_ready_entries] == EXPECTED_CANDIDATES

    for entry in search_ready_entries:
        normalized = normalize_quantum_tanner_fixture_entry(REPO_ROOT, entry)
        assert normalized["id"] == entry["candidate_id"]
        assert normalized["code_id"] == entry["code_id"]
        assert normalized["instance_kind"] == "finite_css_instance"
        assert normalized["matrix_format"] == "dense_binary_json"
        assert normalized["parameters"]["distance"] == entry["distance"]
        assert normalized["parameters"]["source_fixture_id"] == entry["candidate_id"]
        assert normalized["derived_properties"]["n"] == entry["n"]
        assert normalized["derived_properties"]["k"] == entry["k"]
        assert normalized["derived_properties"]["distance"] == entry["distance"]
        assert normalized["artifacts"] == {"hx": "hx.json", "hz": "hz.json"}

        candidate = resolve_quantum_tanner_fixture_entry(REPO_ROOT, entry)
        assert candidate.spec.candidate_id == entry["candidate_id"]
        assert candidate.spec.code_family == entry["code_id"]
        assert candidate.spec.parameters == normalized["parameters"]
        assert candidate.instance == normalized
        assert candidate.source_kind == "quantum-tanner-fixture-catalog"
        assert candidate.hx["format"] == "dense_binary_matrix"
        assert candidate.hz["format"] == "dense_binary_matrix"
        assert candidate.hx["n_cols"] == entry["n"]
        assert candidate.hz["n_cols"] == entry["n"]

    corrupted = dict(search_ready_entries[0])
    corrupted["n"] = corrupted["n"] + 1
    with pytest.raises(SearchIntegrityError, match="source fixture n mismatch"):
        normalize_quantum_tanner_fixture_entry(REPO_ROOT, corrupted)

    bad_provenance = dict(search_ready_entries[0])
    bad_provenance["provenance"] = dict(search_ready_entries[0]["provenance"])
    bad_provenance["provenance"]["label"] = "other-candidate"
    with pytest.raises(SearchIntegrityError, match="provenance label mismatch"):
        normalize_quantum_tanner_fixture_entry(REPO_ROOT, bad_provenance)

    zero_distance = dict(search_ready_entries[0])
    zero_distance["distance"] = 0
    with pytest.raises(SearchIntegrityError, match="invalid distance"):
        normalize_quantum_tanner_fixture_entry(REPO_ROOT, zero_distance)


def test_generated_non_default_catalog_accepts_unpinned_candidates_and_records_catalog_path(
    tmp_path: Path,
) -> None:
    work_root = _copy_catalog_repo(tmp_path / "generated")
    smoke_d4 = dict(_catalog()["entries"][0])
    smoke_d4["provenance"] = dict(smoke_d4["provenance"])
    d10 = _write_generated_toric_fixture(work_root, distance=10, n=100)
    payload = {
        "catalog_id": "generated-quantum-tanner-fixtures",
        "schema_version": 1,
        "entries": [smoke_d4, d10],
    }
    _write_json(work_root / GENERATED_CATALOG_REL, payload)

    catalog = load_quantum_tanner_fixture_catalog(work_root, GENERATED_CATALOG_REL)
    assert [entry["candidate_id"] for entry in catalog["entries"]] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d10",
    ]

    d10_entry = catalog["entries"][1]
    assert d10_entry["provenance"]["qec_code_spec"] == "quantum_tanner:toric_d10"
    assert d10_entry["provenance"]["quantum_tanner_spec"] == str(
        DISTANCE_LADDER_REL / "quantum_tanner_specs/toric-d10.json"
    )
    assert d10_entry["provenance"]["generator"] == "test-fixture-generator"
    assert d10_entry["provenance"]["construction_mode"] == "lr_cayley_no_cover_v1"
    assert d10_entry["provenance"]["base_group"] == "Z10xZ10"
    normalized = normalize_quantum_tanner_fixture_entry(
        work_root,
        d10_entry,
        catalog_path=GENERATED_CATALOG_REL,
    )
    assert normalized["id"] == "quantum-tanner-toric-d10"
    assert normalized["derived_properties"]["n"] == 100
    assert normalized["derived_properties"]["distance"] == 10
    assert normalized["provenance"]["catalog"] == str(GENERATED_CATALOG_REL)

    resolved = resolve_quantum_tanner_fixture_entry(
        work_root,
        d10_entry,
        catalog_path=GENERATED_CATALOG_REL,
    )
    assert resolved.spec.candidate_id == "quantum-tanner-toric-d10"
    assert resolved.hx["n_cols"] == 100
    assert resolved.hz["n_cols"] == 100
    assert resolved.instance["provenance"]["catalog"] == str(GENERATED_CATALOG_REL)


def test_generated_catalog_rejects_entry_n_that_disagrees_with_matrix_width(
    tmp_path: Path,
) -> None:
    work_root = _copy_catalog_repo(tmp_path / "bad-width")
    bad_d10 = _write_generated_toric_fixture(
        work_root,
        distance=10,
        n=100,
        matrix_num_cols=99,
    )
    payload = {
        "catalog_id": "generated-quantum-tanner-fixtures",
        "schema_version": 1,
        "entries": [bad_d10],
    }
    _write_json(work_root / GENERATED_CATALOG_REL, payload)

    with pytest.raises(SearchIntegrityError, match="matrix width mismatch"):
        validate_quantum_tanner_fixture_catalog(work_root, GENERATED_CATALOG_REL)


def test_generated_catalog_accepts_root_relative_spec_that_matches_manifest_relative_instance(
    tmp_path: Path,
) -> None:
    work_root = _copy_catalog_repo(tmp_path / "manifest-relative")
    entry = _write_generated_toric_fixture(work_root, distance=10, n=100)
    entry["provenance"]["distance_ladder_manifest"] = str(
        DISTANCE_LADDER_REL.with_suffix(".json")
    )
    entry["provenance"]["quantum_tanner_spec"] = str(
        DISTANCE_LADDER_REL / "quantum_tanner_specs/toric-d10.json"
    )
    instance_path = work_root / entry["source_instance"]
    instance = _load_json(instance_path)
    instance["quantum_tanner_spec"] = (
        "surface-toric-bb-kasai-tanner-v2/quantum_tanner_specs/toric-d10.json"
    )
    _write_json(instance_path, instance)
    payload = {
        "catalog_id": "generated-quantum-tanner-fixtures",
        "schema_version": 1,
        "entries": [entry],
    }
    _write_json(work_root / GENERATED_CATALOG_REL, payload)

    validate_quantum_tanner_fixture_catalog(work_root, GENERATED_CATALOG_REL)


def test_catalog_validation_rejects_duplicate_candidate_ids(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work_root = _copy_catalog_repo(tmp_path / "duplicate")
    catalog_path = work_root / "campaigns" / "examples" / "quantum-tanner-autoresearch" / "fixture_catalog.json"
    payload = _load_json(catalog_path)
    payload["entries"][1]["candidate_id"] = payload["entries"][0]["candidate_id"]
    _write_json(catalog_path, payload)

    with pytest.raises(SearchIntegrityError, match="duplicate candidate_id"):
        validate_quantum_tanner_fixture_catalog(work_root)

    work_root = _copy_catalog_repo(tmp_path / "catalog-id")
    catalog_path = work_root / "campaigns" / "examples" / "quantum-tanner-autoresearch" / "fixture_catalog.json"
    payload = _load_json(catalog_path)
    payload["catalog_id"] = "other-fixture-catalog"
    _write_json(catalog_path, payload)

    with pytest.raises(SearchIntegrityError, match="catalog_id"):
        validate_quantum_tanner_fixture_catalog(work_root)

    work_root = _copy_catalog_repo(tmp_path / "schema-version")
    catalog_path = work_root / "campaigns" / "examples" / "quantum-tanner-autoresearch" / "fixture_catalog.json"
    payload = _load_json(catalog_path)
    payload["schema_version"] = 2
    _write_json(catalog_path, payload)

    with pytest.raises(SearchIntegrityError, match="schema_version"):
        validate_quantum_tanner_fixture_catalog(work_root)

    work_root = _copy_catalog_repo(tmp_path / "search-ready")
    catalog_path = work_root / "campaigns" / "examples" / "quantum-tanner-autoresearch" / "fixture_catalog.json"
    payload = _load_json(catalog_path)
    payload["entries"][0]["search_ready"] = False
    _write_json(catalog_path, payload)

    with pytest.raises(SearchIntegrityError, match="search_ready"):
        validate_quantum_tanner_fixture_catalog(work_root)
    assert main(["validate", "--root", str(work_root)]) != 0
    captured = capsys.readouterr()
    assert "error:" in captured.err

    work_root = _copy_catalog_repo(tmp_path / "adaptation")
    catalog_path = work_root / "campaigns" / "examples" / "quantum-tanner-autoresearch" / "fixture_catalog.json"
    payload = _load_json(catalog_path)
    payload["entries"][0]["adaptation"] = "other-adapter"
    _write_json(catalog_path, payload)

    with pytest.raises(SearchIntegrityError, match="adaptation"):
        validate_quantum_tanner_fixture_catalog(work_root)

    work_root = _copy_catalog_repo(tmp_path / "provenance")
    catalog_path = work_root / "campaigns" / "examples" / "quantum-tanner-autoresearch" / "fixture_catalog.json"
    payload = _load_json(catalog_path)
    payload["entries"][0]["provenance"]["kind"] = "other-kind"
    _write_json(catalog_path, payload)

    with pytest.raises(SearchIntegrityError, match="provenance"):
        validate_quantum_tanner_fixture_catalog(work_root)


def test_catalog_validation_rejects_missing_hx_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work_root = _copy_catalog_repo(tmp_path)
    catalog_path = (
        work_root
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "fixture_catalog.json"
    )
    payload = _load_json(catalog_path)
    payload["entries"][0]["hx"] = (
        "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/"
        "instances/quantum-tanner-toric-d4/missing-hx.json"
    )
    _write_json(catalog_path, payload)

    with pytest.raises(SearchIntegrityError, match="missing hx artifact"):
        validate_quantum_tanner_fixture_catalog(work_root)

    corrupted = _load_json(catalog_path)["entries"][0]
    with pytest.raises(SearchIntegrityError, match="missing hx artifact"):
        normalize_quantum_tanner_fixture_entry(work_root, corrupted)

    outside_hx = tmp_path / "outside-hx.json"
    _write_json(
        outside_hx,
        {
            "format": "sparse_rows",
            "num_cols": corrupted["n"],
            "rows": [[] for _ in range(2)],
        },
    )
    absolute_hx_entry = dict(corrupted)
    absolute_hx_entry["hx"] = str(outside_hx)
    with pytest.raises(SearchIntegrityError, match="safe relative path"):
        normalize_quantum_tanner_fixture_entry(work_root, absolute_hx_entry)

    unsafe_source_fixture_entry = dict(_catalog()["entries"][0])
    unsafe_source_fixture_entry["source_fixture_path"] = str(
        tmp_path / "outside-fixture-dir"
    )
    with pytest.raises(SearchIntegrityError, match="safe relative path"):
        resolve_quantum_tanner_fixture_entry(work_root, unsafe_source_fixture_entry)

    payload = _catalog()
    payload["entries"][0].update(
        {
            "n": payload["entries"][1]["n"],
            "k": payload["entries"][1]["k"],
            "distance": payload["entries"][1]["distance"],
            "hx": payload["entries"][1]["hx"],
            "hz": payload["entries"][1]["hz"],
        }
    )
    payload["entries"][0]["provenance"].update(
        {
            "qec_code_spec": payload["entries"][1]["provenance"]["qec_code_spec"],
            "quantum_tanner_spec": payload["entries"][1]["provenance"][
                "quantum_tanner_spec"
            ],
            "base_group": payload["entries"][1]["provenance"]["base_group"],
        }
    )
    _write_json(catalog_path, payload)

    with pytest.raises(SearchIntegrityError, match="source fixture"):
        validate_quantum_tanner_fixture_catalog(work_root)

    assert main(["validate", "--root", str(work_root)]) != 0
    captured = capsys.readouterr()
    assert "error:" in captured.err


def test_workspace_validation_rejects_unsafe_fixture_catalog_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work_root = _copy_catalog_repo(tmp_path / "unsafe-catalog-path")
    search_space_path = (
        work_root
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "search_space.json"
    )
    payload = _load_json(search_space_path)
    payload["candidate_specs"][0]["fixture_catalog_path"] = "../outside/fixture_catalog.json"
    _write_json(search_space_path, payload)

    assert main(["validate", "--root", str(work_root)]) != 0
    captured = capsys.readouterr()
    assert "fixture_catalog_path must be a safe relative path" in captured.err
