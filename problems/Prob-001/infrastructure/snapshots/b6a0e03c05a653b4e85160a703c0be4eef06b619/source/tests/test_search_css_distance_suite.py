from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

import pytest

from autoqec_search.css_distance_suite import (
    ValidatedSuiteCase,
    canonical_rowspace_fingerprint,
    load_and_validate_source_pool,
    prepare_blind_suite,
    validate_split_manifest,
    verify_suite_commitment,
)
from autoqec_search.load import SearchIntegrityError


HX_5 = {
    "format": "dense_binary_matrix",
    "n_rows": 2,
    "n_cols": 5,
    "data": [
        [1, 1, 0, 0, 0],
        [0, 0, 1, 1, 0],
    ],
}
HZ_5 = {
    "format": "dense_binary_matrix",
    "n_rows": 2,
    "n_cols": 5,
    "data": [
        [1, 1, 1, 1, 0],
        [0, 0, 0, 0, 1],
    ],
}
X_WITNESS_5 = {"basis": "x", "vector": [1, 0, 1, 0, 0]}


def _json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()


def _write_json(path: Path, payload: dict) -> str:
    data = _json_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _record(
    tmp_path: Path,
    *,
    case_id: str = "case-a",
    family: str = "geometric",
    construction_kind: str = "surface",
    hx_payload: dict | None = None,
    hz_payload: dict | None = None,
    construction: dict | None = None,
    witness: dict | None = None,
    k: int = 1,
    bound_type: str = "exact",
    value: int = 3,
) -> dict:
    hx_payload = copy.deepcopy(hx_payload or HX_5)
    hz_payload = copy.deepcopy(hz_payload or HZ_5)
    hx_path = Path("instances") / case_id / "hx.json"
    hz_path = Path("instances") / case_id / "hz.json"
    hx_sha = _write_json(tmp_path / hx_path, hx_payload)
    hz_sha = _write_json(tmp_path / hz_path, hz_payload)
    reference: dict = {
        "bound_type": bound_type,
        "value": value,
        "evidence": {"kind": "fixture", "citation": "test"},
    }
    if bound_type == "upper":
        reference["witness"] = copy.deepcopy(witness or X_WITNESS_5)
    return {
        "case_id": case_id,
        "family": family,
        "construction_kind": construction_kind,
        "construction": construction or {"name": case_id},
        "n": hx_payload["n_cols"],
        "k": k,
        "hx_path": str(hx_path),
        "hz_path": str(hz_path),
        "hx_sha256": hx_sha,
        "hz_sha256": hz_sha,
        "hx_rowspace_sha256": canonical_rowspace_fingerprint(hx_payload["data"]),
        "hz_rowspace_sha256": canonical_rowspace_fingerprint(hz_payload["data"]),
        "reference": reference,
        "provenance": {
            "source_repository": "https://example.test/source",
            "source_commit": "a" * 40,
            "generator_command": ["fixture-generator", case_id],
            "license_status": "redistribution-approved",
        },
    }


def _write_pool(tmp_path: Path, records: list[dict]) -> Path:
    pool = {
        "schema_version": 1,
        "created_at": "2026-07-21T00:00:00Z",
        "cases": records,
    }
    path = tmp_path / "source_pool.json"
    _write_json(path, pool)
    return path


def _load_pool(tmp_path: Path, records: list[dict]) -> tuple[ValidatedSuiteCase, ...]:
    return load_and_validate_source_pool(
        root=tmp_path,
        path=_write_pool(tmp_path, records).relative_to(tmp_path),
    )


def test_validates_exact_source_record_and_matrix_integrity(tmp_path: Path) -> None:
    cases = _load_pool(tmp_path, [_record(tmp_path)])

    assert len(cases) == 1
    case = cases[0]
    assert case.record["case_id"] == "case-a"
    assert case.record["k"] == 1
    assert case.record["reference"]["bound_type"] == "exact"
    assert case.hx_payload == HX_5
    assert case.hz_payload == HZ_5


def test_validates_upper_source_record_with_independent_witness(tmp_path: Path) -> None:
    cases = _load_pool(
        tmp_path,
        [_record(tmp_path, bound_type="upper", value=2)],
    )

    assert cases[0].record["reference"]["witness"] == X_WITNESS_5


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda record: record.update({"hx_path": "../hx.json"}),
            "unsafe matrix path",
        ),
        (
            lambda record: record.update({"hx_sha256": "0" * 64}),
            "matrix hash mismatch",
        ),
        (
            lambda record: record.update({"k": 2}),
            "k mismatch",
        ),
        (
            lambda record: record.update({"family": "not-a-family"}),
            "source pool schema",
        ),
    ],
)
def test_rejects_invalid_source_records(
    tmp_path: Path,
    mutator,
    message: str,
) -> None:
    record = _record(tmp_path)
    mutator(record)

    with pytest.raises(SearchIntegrityError, match=message):
        _load_pool(tmp_path, [record])


def test_rejects_noncommuting_source_matrices(tmp_path: Path) -> None:
    record = _record(
        tmp_path,
        hz_payload={
            "format": "dense_binary_matrix",
            "n_rows": 1,
            "n_cols": 5,
            "data": [[1, 0, 0, 0, 0]],
        },
    )

    with pytest.raises(SearchIntegrityError, match="CSS checks do not commute"):
        _load_pool(tmp_path, [record])


def test_rejects_invalid_upper_witness(tmp_path: Path) -> None:
    record = _record(tmp_path, bound_type="upper", value=2)
    record["reference"]["witness"] = {"basis": "x", "vector": [1, 0, 0, 0, 0]}

    with pytest.raises(SearchIntegrityError, match="invalid upper witness"):
        _load_pool(tmp_path, [record])


def test_rejects_duplicate_construction_records(tmp_path: Path) -> None:
    first = _record(tmp_path, case_id="case-a")
    second = _record(tmp_path, case_id="case-b")
    second["construction"] = copy.deepcopy(first["construction"])

    with pytest.raises(SearchIntegrityError, match="duplicate construction"):
        _load_pool(tmp_path, [first, second])


def test_rejects_duplicate_rowspace_fingerprints(tmp_path: Path) -> None:
    first = _record(tmp_path, case_id="case-a")
    second = _record(tmp_path, case_id="case-b")

    with pytest.raises(SearchIntegrityError, match="duplicate row-space"):
        _load_pool(tmp_path, [first, second])


def _source_case(
    source_id: str,
    *,
    family: str,
    construction_kind: str,
    n: int,
    bound_type: str,
) -> ValidatedSuiteCase:
    return ValidatedSuiteCase(
        record={
            "case_id": source_id,
            "family": family,
            "construction_kind": construction_kind,
            "construction": {"name": source_id},
            "n": n,
            "reference": {"bound_type": bound_type, "value": 3},
        },
        hx_payload={},
        hz_payload={},
    )


def _development_source_cases() -> tuple[ValidatedSuiteCase, ...]:
    source_cases: list[ValidatedSuiteCase] = []
    quotas = [
        ("geometric", "surface", 4),
        ("geometric", "toric", 4),
        ("bivariate-bicycle", "bb", 6),
        ("apm-kasai", "apm-kasai", 4),
        ("quantum-tanner", "quantum-tanner", 6),
    ]
    sizes = [64, 256, 1024]
    for family, construction_kind, count in quotas:
        for _ in range(count):
            index = len(source_cases)
            source_cases.append(
                _source_case(
                    f"source-{index:03d}",
                    family=family,
                    construction_kind=construction_kind,
                    n=sizes[index % len(sizes)],
                    bound_type="exact" if index < 12 else "upper",
                )
            )
    return tuple(source_cases)


def test_validates_development_split_manifest_counts_and_coverage() -> None:
    source_cases = _development_source_cases()
    manifest = {
        "schema_version": 1,
        "split": "development",
        "created_at": "2026-07-21T00:00:00Z",
        "cases": [
            {"case_id": f"development-{index:03d}", "source_case_id": case.record["case_id"]}
            for index, case in enumerate(source_cases)
        ],
    }

    summary = validate_split_manifest(
        root=Path("/operator/private"),
        payload=manifest,
        source_cases=source_cases,
    )

    assert summary == {
        "status": "pass",
        "split": "development",
        "case_count": 24,
        "family_counts": {
            "geometric": 8,
            "bivariate-bicycle": 6,
            "apm-kasai": 4,
            "quantum-tanner": 6,
        },
        "geometric_kind_counts": {"surface": 4, "toric": 4},
        "reference_counts": {"exact": 12, "upper": 12},
        "size_bands": {"large": 8, "medium": 8, "small": 8},
    }


def test_rejects_split_manifest_with_wrong_family_count() -> None:
    source_cases = list(_development_source_cases())
    source_cases[-1] = _source_case(
        source_cases[-1].record["case_id"],
        family="bivariate-bicycle",
        construction_kind="bb",
        n=1024,
        bound_type="upper",
    )
    manifest = {
        "schema_version": 1,
        "split": "development",
        "created_at": "2026-07-21T00:00:00Z",
        "cases": [
            {"case_id": f"development-{index:03d}", "source_case_id": case.record["case_id"]}
            for index, case in enumerate(source_cases)
        ],
    }

    with pytest.raises(SearchIntegrityError, match="family counts"):
        validate_split_manifest(
            root=Path("/operator/private"),
            payload=manifest,
            source_cases=tuple(source_cases),
        )

    assert Counter(case.record["family"] for case in source_cases)["quantum-tanner"] == 5


def _matrix_pair(index: int, n: int) -> tuple[dict, dict, dict]:
    offset = (index * 7) % (n - 6)
    positions = list(range(offset, offset + 6))
    hx_rows = [[0] * n for _ in range(2)]
    hz_rows = [[0] * n for _ in range(2)]
    hx_rows[0][positions[0]] = 1
    hx_rows[0][positions[1]] = 1
    hx_rows[1][positions[2]] = 1
    hx_rows[1][positions[3]] = 1
    for position in positions[:4]:
        hz_rows[0][position] = 1
    hz_rows[1][positions[4]] = 1
    hz_rows[1][positions[5]] = 1
    witness = [0] * n
    witness[positions[0]] = 1
    witness[positions[2]] = 1
    return (
        {
            "format": "dense_binary_matrix",
            "n_rows": 2,
            "n_cols": n,
            "data": hx_rows,
        },
        {
            "format": "dense_binary_matrix",
            "n_rows": 2,
            "n_cols": n,
            "data": hz_rows,
        },
        {"basis": "x", "vector": witness},
    )


def _selection_pool_records(tmp_path: Path) -> list[dict]:
    records: list[dict] = []
    quotas = [
        ("geometric", "surface", 8),
        ("geometric", "toric", 8),
        ("bivariate-bicycle", "bb", 12),
        ("apm-kasai", "apm-kasai", 8),
        ("quantum-tanner", "quantum-tanner", 12),
    ]
    sizes = [64, 256, 1024]
    for family, construction_kind, count in quotas:
        for local_index in range(count):
            index = len(records)
            n = sizes[index % len(sizes)]
            hx_payload, hz_payload, witness = _matrix_pair(index, n)
            bound_type = "exact" if local_index % 2 == 0 else "upper"
            records.append(
                _record(
                    tmp_path,
                    case_id=f"source-{index:03d}",
                    family=family,
                    construction_kind=construction_kind,
                    construction={
                        "family": family,
                        "kind": construction_kind,
                        "local_index": local_index,
                        "n": n,
                    },
                    hx_payload=hx_payload,
                    hz_payload=hz_payload,
                    witness=witness,
                    k=n - 4,
                    bound_type=bound_type,
                    value=2 if bound_type == "upper" else 3,
                )
            )
    return records


def _selection_pool_records_with_upper_only_apm(tmp_path: Path) -> list[dict]:
    records = _selection_pool_records(tmp_path)
    for record in records:
        if record["family"] != "apm-kasai":
            continue
        index = int(record["case_id"].removeprefix("source-"))
        _hx_payload, _hz_payload, witness = _matrix_pair(index, record["n"])
        record["reference"] = {
            "bound_type": "upper",
            "value": 2,
            "evidence": {"kind": "fixture", "citation": "test"},
            "witness": witness,
        }
    return records


def _prepare_fixture_suite(tmp_path: Path) -> tuple[Path, Path, dict]:
    source_pool_path = _write_pool(tmp_path, _selection_pool_records(tmp_path))
    work_root = tmp_path / "operator"
    commitment_path = tmp_path / "commitment.json"
    commitment = prepare_blind_suite(
        root=tmp_path,
        source_pool_path=source_pool_path.relative_to(tmp_path),
        work_root=work_root,
        commitment_path=commitment_path,
        created_at="2026-07-21T00:00:00Z",
        secret=bytes(range(32)),
        salt=bytes(range(32, 64)),
    )
    return work_root / "private" / "css-distance-paper-suite", commitment_path, commitment


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_text_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def test_prepare_blind_suite_materializes_24_12_private_split_and_safe_commitment(
    tmp_path: Path,
) -> None:
    source_pool_path = _write_pool(tmp_path, _selection_pool_records(tmp_path))

    commitment = prepare_blind_suite(
        root=tmp_path,
        source_pool_path=source_pool_path.relative_to(tmp_path),
        work_root=tmp_path / "operator",
        commitment_path=tmp_path / "commitment.json",
        created_at="2026-07-21T00:00:00Z",
        secret=bytes(range(32)),
        salt=bytes(range(32, 64)),
    )

    assert commitment["counts"] == {"development": 24, "final": 12}
    assert commitment == _load_json(tmp_path / "commitment.json")
    safe_commitment = json.dumps(commitment)
    assert "case_id" not in safe_commitment
    assert "construction" not in safe_commitment
    assert "hx_path" not in safe_commitment
    assert "hz_path" not in safe_commitment
    assert "reference" not in safe_commitment
    assert "witness" not in safe_commitment
    assert "development-000" not in safe_commitment
    assert "final-000" not in safe_commitment

    private_root = tmp_path / "operator" / "private" / "css-distance-paper-suite"
    assert _mode(private_root) == 0o700
    assert _mode(private_root / "selection-secret.bin") == 0o600
    assert _mode(private_root / "salt.bin") == 0o600
    assert _mode(private_root / "development" / "manifest.json") == 0o600
    assert _mode(private_root / "final" / "manifest.json") == 0o600

    development = _load_json(private_root / "development" / "manifest.json")
    final = _load_json(private_root / "final" / "manifest.json")
    assert len(development["cases"]) == 24
    assert len(final["cases"]) == 12
    assert {case["case_id"] for case in development["cases"]} == {
        f"development-{index:03d}" for index in range(24)
    }
    assert {case["case_id"] for case in final["cases"]} == {
        f"final-{index:03d}" for index in range(12)
    }
    assert (private_root / "development" / "development-000" / "hx.json").is_file()
    assert (private_root / "final" / "final-000" / "hz.json").is_file()

    verification = verify_suite_commitment(private_root=private_root, commitment=commitment)
    assert verification == {"status": "pass", "development": 24, "final": 12}

    repeated = prepare_blind_suite(
        root=tmp_path,
        source_pool_path=source_pool_path.relative_to(tmp_path),
        work_root=tmp_path / "operator-repeat",
        commitment_path=tmp_path / "commitment-repeat.json",
        created_at="2026-07-21T00:00:00Z",
        secret=bytes(range(32)),
        salt=bytes(range(32, 64)),
    )
    assert repeated == commitment


def test_prepare_blind_suite_accepts_upper_only_apm_when_split_coverage_holds(
    tmp_path: Path,
) -> None:
    source_pool_path = _write_pool(
        tmp_path,
        _selection_pool_records_with_upper_only_apm(tmp_path),
    )

    commitment = prepare_blind_suite(
        root=tmp_path,
        source_pool_path=source_pool_path.relative_to(tmp_path),
        work_root=tmp_path / "operator",
        commitment_path=tmp_path / "commitment.json",
        created_at="2026-07-21T00:00:00Z",
        secret=bytes(range(32)),
        salt=bytes(range(32, 64)),
    )

    assert commitment["counts"] == {"development": 24, "final": 12}
    private_root = tmp_path / "operator" / "private" / "css-distance-paper-suite"
    development = _load_json(private_root / "development" / "manifest.json")
    final = _load_json(private_root / "final" / "manifest.json")
    assert {
        case["reference"]["bound_type"]
        for case in development["cases"]
        if case["family"] == "apm-kasai"
    } == {"upper"}
    assert {
        case["reference"]["bound_type"]
        for case in final["cases"]
        if case["family"] == "apm-kasai"
    } == {"upper"}


@pytest.mark.parametrize("tamper", ["target", "split", "salt", "source_pool", "matrix"])
def test_verify_suite_commitment_rejects_tampering(
    tmp_path: Path,
    tamper: str,
) -> None:
    private_root, _commitment_path, commitment = _prepare_fixture_suite(tmp_path)

    if tamper == "target":
        manifest_path = private_root / "development" / "manifest.json"
        manifest = _load_json(manifest_path)
        manifest["cases"][0]["reference"]["value"] += 1
        _write_text_json(manifest_path, manifest)
    elif tamper == "split":
        manifest_path = private_root / "development" / "manifest.json"
        manifest = _load_json(manifest_path)
        manifest["cases"][0]["source_case_id"] = manifest["cases"][1]["source_case_id"]
        _write_text_json(manifest_path, manifest)
    elif tamper == "salt":
        (private_root / "salt.bin").write_bytes(b"not-the-original-salt")
    elif tamper == "source_pool":
        source_pool = _load_json(private_root / "source_pool.json")
        source_pool["cases"][0]["n"] += 1
        _write_text_json(private_root / "source_pool.json", source_pool)
    elif tamper == "matrix":
        matrix_path = private_root / "development" / "development-000" / "hx.json"
        matrix = _load_json(matrix_path)
        matrix["data"][0][0] ^= 1
        _write_text_json(matrix_path, matrix)

    with pytest.raises(SearchIntegrityError, match="suite commitment|matrix hash"):
        verify_suite_commitment(private_root=private_root, commitment=commitment)
