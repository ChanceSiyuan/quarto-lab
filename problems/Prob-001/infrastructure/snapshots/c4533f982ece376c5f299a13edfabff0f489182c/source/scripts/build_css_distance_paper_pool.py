#!/usr/bin/env python3
"""Build the public CSS-distance paper-validation source pool.

The committed source pool is intentionally split-free: it contains only
redistribution-approved matrices, provenance, reference labels, and verified
upper-bound witnesses. The private 24/12 split is prepared later from this pool.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from autoqec_search.css_distance_suite import (
    canonical_rowspace_fingerprint,
    load_and_validate_source_pool,
    sha256_bytes,
)
from autoqec_search.load import SearchIntegrityError
from autoqec_search.quotient_coset_upper_bound import find_quotient_coset_upper_bound
from autoqec_search.structure import gf2_rank, matrix_data


CREATED_AT = "2026-07-21T00:00:00Z"
TIME_LIMIT_SECONDS = 300
SEEDS = [
    104729,
    130363,
    155921,
    196613,
    262147,
    327673,
    393241,
    458789,
    524309,
    589867,
    655373,
    720899,
    786433,
    851971,
    917519,
    983063,
    1048583,
    1114129,
    1179661,
    1245187,
]

WITNESS_SEED = SEEDS[0]
WITNESS_MAX_NO_IMPROVEMENT = 512
WITNESS_TIMEOUT_SECONDS = 30.0

POOL_REL = Path("benchmarks/css_distance_paper_validation")
INSTANCES_REL = POOL_REL / "instances"
ISSUE38_REL = Path("benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2")

SAME_SHIFT_A = [[3, 0], [0, 1], [0, 2]]
SAME_SHIFT_B = [[0, 3], [1, 0], [2, 0]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()

    root = args.root.resolve()
    pool_root = root / POOL_REL
    instances_root = root / INSTANCES_REL
    _reset_output(pool_root, instances_root)

    source_commit = _git_head_or_zero(root)
    records: list[dict[str, Any]] = []
    curation: list[dict[str, Any]] = []

    def add_case(
        *,
        case_id: str,
        family: str,
        construction_kind: str,
        construction: dict[str, Any],
        hx_payload: dict[str, Any],
        hz_payload: dict[str, Any],
        reference_kind: str,
        reference_value: int | None,
        evidence_key: str,
        evidence_kind: str,
        evidence_citation: str,
        source_pin: str,
        generator_command: list[str],
        source_repository: str = "local:autoqec",
    ) -> None:
        case_root = instances_root / case_id
        _write_json(case_root / "hx.json", hx_payload)
        _write_json(case_root / "hz.json", hz_payload)
        record = _record_from_files(
            root=root,
            case_id=case_id,
            family=family,
            construction_kind=construction_kind,
            construction=construction,
            reference_kind=reference_kind,
            reference_value=reference_value,
            evidence_kind=evidence_kind,
            evidence_citation=evidence_citation,
            source_commit=source_commit,
            source_repository=source_repository,
            generator_command=generator_command,
        )
        records.append(record)
        curation.append(
            {
                "case_id": case_id,
                "source_pin": source_pin,
                "generator_command": generator_command,
                "evidence_key": evidence_key,
                "redistribution_decision": "redistribution-approved",
                "reference_type": record["reference"]["bound_type"],
            }
        )

    def copy_case(
        *,
        case_id: str,
        source_rel: Path,
        family: str,
        construction_kind: str,
        construction: dict[str, Any],
        reference_kind: str,
        reference_value: int | None,
        evidence_key: str,
        evidence_kind: str,
        evidence_citation: str,
    ) -> None:
        source_root = root / source_rel
        add_case(
            case_id=case_id,
            family=family,
            construction_kind=construction_kind,
            construction=construction,
            hx_payload=_load_json(source_root / "hx.json"),
            hz_payload=_load_json(source_root / "hz.json"),
            reference_kind=reference_kind,
            reference_value=reference_value,
            evidence_key=evidence_key,
            evidence_kind=evidence_kind,
            evidence_citation=evidence_citation,
            source_pin=f"git:{source_commit}:{source_rel.as_posix()}",
            generator_command=["copy-css-instance", source_rel.as_posix()],
        )

    for distance in [5, 9, 13, 17]:
        case_id = f"surface-rotated-d{distance}"
        copy_case(
            case_id=case_id,
            source_rel=ISSUE38_REL / "instances" / case_id,
            family="geometric",
            construction_kind="surface",
            construction={
                "family": "rotated-surface",
                "distance": distance,
                "source": "issue-38-distance-ladder",
            },
            reference_kind="exact",
            reference_value=distance,
            evidence_key="surface-code:rotated-distance-formula",
            evidence_kind="formula",
            evidence_citation="rotated surface-code distance d; issue-38 qec-code export",
        )
    copy_case(
        case_id="surface-rotated-d7",
        source_rel=Path(
            "zoo/codes/rotated-surface-code/instances/rotated-surface-code-d7"
        ),
        family="geometric",
        construction_kind="surface",
        construction={
            "family": "rotated-surface",
            "distance": 7,
            "source": "zoo-rotated-surface-code-d7",
        },
        reference_kind="exact",
        reference_value=7,
        evidence_key="zoo:rotated-surface-code-d7",
        evidence_kind="zoo-record",
        evidence_citation="zoo rotated-surface-code-d7 derived distance",
    )
    add_case(
        case_id="surface-rotated-d11",
        family="geometric",
        construction_kind="surface",
        construction={
            "family": "rotated-surface",
            "distance": 11,
            "source": "closed-form-local-generator",
        },
        hx_payload=_sparse_payload(_rotated_surface_rows(11, basis="x"), 11 * 11),
        hz_payload=_sparse_payload(_rotated_surface_rows(11, basis="z"), 11 * 11),
        reference_kind="exact",
        reference_value=11,
        evidence_key="surface-code:rotated-distance-formula",
        evidence_kind="formula",
        evidence_citation="rotated surface-code distance d; generated from closed-form checks",
        source_pin=f"git:{source_commit}:scripts/build_css_distance_paper_pool.py",
        generator_command=[
            "PYTHONPATH=src",
            "python3",
            "scripts/build_css_distance_paper_pool.py",
        ],
    )

    for distance in [5, 9, 13, 17]:
        case_id = f"toric-d{distance}"
        copy_case(
            case_id=case_id,
            source_rel=ISSUE38_REL / "instances" / case_id,
            family="geometric",
            construction_kind="toric",
            construction={
                "family": "toric",
                "distance": distance,
                "source": "issue-38-distance-ladder",
            },
            reference_kind="exact",
            reference_value=distance,
            evidence_key="toric-code:distance-formula",
            evidence_kind="formula",
            evidence_citation="toric-code distance d; issue-38 qec-code export",
        )
    for distance in [7, 11]:
        hx_rows, hz_rows = _toric_rows(distance)
        add_case(
            case_id=f"toric-d{distance}",
            family="geometric",
            construction_kind="toric",
            construction={
                "family": "toric",
                "distance": distance,
                "source": "closed-form-local-generator",
            },
            hx_payload=_sparse_payload(hx_rows, 2 * distance * distance),
            hz_payload=_sparse_payload(hz_rows, 2 * distance * distance),
            reference_kind="exact",
            reference_value=distance,
            evidence_key="toric-code:distance-formula",
            evidence_kind="formula",
            evidence_citation="toric-code distance d; generated from closed-form checks",
            source_pin=f"git:{source_commit}:scripts/build_css_distance_paper_pool.py",
            generator_command=[
                "PYTHONPATH=src",
                "python3",
                "scripts/build_css_distance_paper_pool.py",
            ],
        )

    for case_id, value in [("bb72", 6), ("bb144", 12)]:
        copy_case(
            case_id=case_id,
            source_rel=ISSUE38_REL / "instances" / case_id,
            family="bivariate-bicycle",
            construction_kind="bb",
            construction={
                "family": "bivariate-bicycle",
                "source": "bravyi-et-al-table-3",
                "id": case_id,
            },
            reference_kind="exact",
            reference_value=value,
            evidence_key="2308.07915:bivariate-bicycle-code.distance",
            evidence_kind="paper-table",
            evidence_citation="Bravyi et al. Table 3 reported BB exact distance",
        )
    for case_id in ["bb288-same-shifts", "bb432-same-shifts"]:
        copy_case(
            case_id=case_id,
            source_rel=ISSUE38_REL / "instances" / case_id,
            family="bivariate-bicycle",
            construction_kind="bb",
            construction={
                "family": "bivariate-bicycle",
                "source": "issue-38-distance-ladder",
                "id": case_id,
                "reference_polynomials": {
                    "a": SAME_SHIFT_A,
                    "b": SAME_SHIFT_B,
                },
            },
            reference_kind="upper",
            reference_value=None,
            evidence_key="issue-38:bb-upper-verified-witness",
            evidence_kind="verified-witness",
            evidence_citation="quotient-coset verified upper-bound witness on issue-38 matrix",
        )
    for case_id, rows, columns, a_exponents, b_exponents, evidence_key in [
        (
            "bb108-same-m6-n9",
            6,
            9,
            SAME_SHIFT_A,
            SAME_SHIFT_B,
            "2308.07915:bivariate-bicycle-code.parameters",
        ),
        (
            "bb216-same-m6-n18",
            6,
            18,
            SAME_SHIFT_A,
            SAME_SHIFT_B,
            "2308.07915:bivariate-bicycle-code.parameters",
        ),
        (
            "bb196-alt2-m7-n14",
            7,
            14,
            [[0, 0], [2, 1], [5, 3]],
            [[0, 2], [3, 0], [1, 4]],
            "2408.10001:bivariate-bicycle-code.parameters",
        ),
        (
            "bb252-alt3-m9-n14",
            9,
            14,
            [[0, 0], [1, 3], [4, 2]],
            [[0, 1], [3, 0], [5, 5]],
            "2408.10001:bivariate-bicycle-code.parameters",
        ),
        (
            "bb540-gross-m15-n18",
            15,
            18,
            [[0, 0], [1, 2], [3, 1]],
            [[0, 1], [2, 0], [4, 3]],
            "2308.07915:bivariate-bicycle-code.parameters",
        ),
    ]:
        hx_payload, hz_payload = _bb_payload(rows, columns, a_exponents, b_exponents)
        add_case(
            case_id=case_id,
            family="bivariate-bicycle",
            construction_kind="bb",
            construction={
                "family": "bivariate-bicycle",
                "rows": rows,
                "columns": columns,
                "a": a_exponents,
                "b": b_exponents,
                "source": "local-bivariate-circulant-generator",
            },
            hx_payload=hx_payload,
            hz_payload=hz_payload,
            reference_kind="upper",
            reference_value=None,
            evidence_key=evidence_key,
            evidence_kind="verified-witness",
            evidence_citation="local bivariate-circulant construction with verified upper-bound witness",
            source_pin=f"git:{source_commit}:scripts/build_css_distance_paper_pool.py",
            generator_command=[
                "PYTHONPATH=src",
                "python3",
                "scripts/build_css_distance_paper_pool.py",
            ],
        )

    for case_id, p_value, a_shifts, b_shifts in [
        ("apm-kasai-affine-p24", 24, [0, 7, 23], [0, 11, 31]),
        ("apm-kasai-affine-p48", 48, [0, 7, 23], [0, 11, 31]),
        ("apm-kasai-affine-p72", 72, [0, 7, 23], [0, 11, 31]),
        ("apm-kasai-affine-p300", 300, [0, 11, 37], [0, 17, 43]),
    ]:
        hx_payload, hz_payload = _apm_affine_payload(p_value, a_shifts, b_shifts)
        add_case(
            case_id=case_id,
            family="apm-kasai",
            construction_kind="apm-kasai",
            construction={
                "family": "apm-kasai-affine-proxy",
                "p": p_value,
                "a_shifts": a_shifts,
                "b_shifts": b_shifts,
                "source": "local-affine-permutation-matrix-generator",
            },
            hx_payload=hx_payload,
            hz_payload=hz_payload,
            reference_kind="upper",
            reference_value=None,
            evidence_key="kasai-apm:affine-shift-upper-fixture",
            evidence_kind="verified-witness",
            evidence_citation="locally generated affine-permutation CSS fixture with verified upper-bound witness",
            source_pin=f"git:{source_commit}:scripts/build_css_distance_paper_pool.py",
            generator_command=[
                "PYTHONPATH=src",
                "python3",
                "scripts/build_css_distance_paper_pool.py",
            ],
        )
    for case_id, p_value in [("apm-kasai-p96", 96), ("apm-kasai-p192", 192)]:
        copy_case(
            case_id=case_id,
            source_rel=ISSUE38_REL / "instances" / case_id,
            family="apm-kasai",
            construction_kind="apm-kasai",
            construction={
                "family": "apm-kasai",
                "p": p_value,
                "source": "issue-38-distance-ladder",
            },
            reference_kind="upper",
            reference_value=None,
            evidence_key="issue-38:apm-kasai-upper-verified-witness",
            evidence_kind="verified-witness",
            evidence_citation="quotient-coset verified upper-bound witness on issue-38 APM/Kasai matrix",
        )

    for distance in [4, 6, 8]:
        case_id = f"quantum-tanner-toric-d{distance}"
        copy_case(
            case_id=case_id,
            source_rel=ISSUE38_REL / "instances" / case_id,
            family="quantum-tanner",
            construction_kind="quantum-tanner",
            construction={
                "family": "quantum-tanner",
                "mode": "pinned-toric-spec",
                "distance": distance,
                "source": "issue-38-distance-ladder",
                "spec": (
                    ISSUE38_REL
                    / "quantum_tanner_specs"
                    / f"toric-d{distance}.json"
                ).as_posix(),
            },
            reference_kind="exact",
            reference_value=distance,
            evidence_key="issue-38:quantum-tanner-toric-exact",
            evidence_kind="fixture",
            evidence_citation="issue-38 pinned quantum-Tanner toric fixture",
        )
    for distance in [10, 12, 14, 16, 18, 20]:
        hx_rows, hz_rows = _toric_rows(distance)
        add_case(
            case_id=f"quantum-tanner-toric-product-d{distance}",
            family="quantum-tanner",
            construction_kind="quantum-tanner",
            construction={
                "family": "quantum-tanner",
                "mode": "toric-product-proxy",
                "distance": distance,
                "source": "closed-form-local-generator",
                "limitation": "proxy until pinned quantum-Tanner materializer is available",
            },
            hx_payload=_sparse_payload(hx_rows, 2 * distance * distance),
            hz_payload=_sparse_payload(hz_rows, 2 * distance * distance),
            reference_kind="exact",
            reference_value=distance,
            evidence_key="quantum-tanner:toric-product-proxy-exact",
            evidence_kind="formula",
            evidence_citation="toric-product CSS proxy exact distance d; quantum-Tanner limitation recorded in curation",
            source_pin=f"git:{source_commit}:scripts/build_css_distance_paper_pool.py",
            generator_command=[
                "PYTHONPATH=src",
                "python3",
                "scripts/build_css_distance_paper_pool.py",
            ],
        )

    source_pool = {
        "schema_version": 1,
        "created_at": CREATED_AT,
        "cases": sorted(records, key=lambda record: record["case_id"]),
    }
    _write_json(pool_root / "source_pool.json", source_pool)
    _write_json(
        pool_root / "seeds.json",
        {
            "schema_version": 1,
            "time_limit_seconds": TIME_LIMIT_SECONDS,
            "seeds": SEEDS,
        },
    )
    _write_json(
        pool_root / "curation.json",
        {"schema_version": 1, "cases": sorted(curation, key=lambda row: row["case_id"])},
    )
    _write_readme(pool_root / "README.md")

    load_and_validate_source_pool(root=root, path=POOL_REL / "source_pool.json")
    print(f"wrote CSS-distance paper source pool cases={len(records)}")
    return 0


def _reset_output(pool_root: Path, instances_root: Path) -> None:
    pool_root.mkdir(parents=True, exist_ok=True)
    if instances_root.exists():
        shutil.rmtree(instances_root)
    for filename in ["source_pool.json", "seeds.json", "curation.json", "README.md"]:
        path = pool_root / filename
        if path.exists():
            path.unlink()


def _record_from_files(
    *,
    root: Path,
    case_id: str,
    family: str,
    construction_kind: str,
    construction: dict[str, Any],
    reference_kind: str,
    reference_value: int | None,
    evidence_kind: str,
    evidence_citation: str,
    source_commit: str,
    source_repository: str,
    generator_command: list[str],
) -> dict[str, Any]:
    hx_rel = INSTANCES_REL / case_id / "hx.json"
    hz_rel = INSTANCES_REL / case_id / "hz.json"
    hx_file = root / hx_rel
    hz_file = root / hz_rel
    hx_payload = _load_json(hx_file)
    hz_payload = _load_json(hz_file)
    hx_rows = matrix_data(hx_payload, "hx.json")
    hz_rows = matrix_data(hz_payload, "hz.json")
    n = _matrix_width(hx_payload)
    if n != _matrix_width(hz_payload):
        raise SearchIntegrityError(f"{case_id}: matrix width mismatch")
    k = n - gf2_rank(hx_rows) - gf2_rank(hz_rows)
    if k <= 0:
        raise SearchIntegrityError(f"{case_id}: generated code has no logical qubits")

    reference = {
        "bound_type": reference_kind,
        "value": reference_value,
        "evidence": {"kind": evidence_kind, "citation": evidence_citation},
    }
    if reference_kind == "upper":
        result = find_quotient_coset_upper_bound(
            hx_payload,
            hz_payload,
            basis="both",
            seed=WITNESS_SEED,
            max_no_improvement=WITNESS_MAX_NO_IMPROVEMENT,
            timeout_seconds=WITNESS_TIMEOUT_SECONDS,
        )
        reference["value"] = result["upper_bound"]
        reference["witness"] = result["witness_payload"]
    if not isinstance(reference["value"], int) or reference["value"] <= 0:
        raise SearchIntegrityError(f"{case_id}: invalid reference value")

    return {
        "case_id": case_id,
        "family": family,
        "construction_kind": construction_kind,
        "construction": construction,
        "n": n,
        "k": k,
        "hx_path": hx_rel.as_posix(),
        "hz_path": hz_rel.as_posix(),
        "hx_sha256": _sha256_file(hx_file),
        "hz_sha256": _sha256_file(hz_file),
        "hx_rowspace_sha256": canonical_rowspace_fingerprint(hx_rows),
        "hz_rowspace_sha256": canonical_rowspace_fingerprint(hz_rows),
        "reference": reference,
        "provenance": {
            "source_repository": source_repository,
            "source_commit": source_commit,
            "generator_command": generator_command,
            "license_status": "redistribution-approved",
        },
    }


def _rotated_surface_rows(distance: int, *, basis: str) -> list[list[int]]:
    def qubit(row: int, column: int) -> int:
        return row * distance + column

    rows: list[list[int]] = []
    for row in range(distance - 1):
        for column in range(distance - 1):
            support = [
                qubit(row, column),
                qubit(row, column + 1),
                qubit(row + 1, column),
                qubit(row + 1, column + 1),
            ]
            if basis == "x" and (row + column) % 2 == 1:
                rows.append(sorted(support))
            if basis == "z" and (row + column) % 2 == 0:
                rows.append(sorted(support))
    if basis == "x":
        for row in range(0, distance - 1, 2):
            rows.append(sorted([qubit(row, 0), qubit(row + 1, 0)]))
        for row in range(1, distance - 1, 2):
            rows.append(sorted([qubit(row, distance - 1), qubit(row + 1, distance - 1)]))
    elif basis == "z":
        for column in range(1, distance - 1, 2):
            rows.append(sorted([qubit(0, column), qubit(0, column + 1)]))
        for column in range(0, distance - 1, 2):
            rows.append(sorted([qubit(distance - 1, column), qubit(distance - 1, column + 1)]))
    else:
        raise ValueError("basis must be x or z")
    return sorted(rows)


def _toric_rows(distance: int) -> tuple[list[list[int]], list[list[int]]]:
    def horizontal(row: int, column: int) -> int:
        return (row % distance) * distance + (column % distance)

    def vertical(row: int, column: int) -> int:
        return distance * distance + (row % distance) * distance + (column % distance)

    hx_rows: list[list[int]] = []
    hz_rows: list[list[int]] = []
    for row in range(distance):
        for column in range(distance):
            hx_rows.append(
                sorted(
                    [
                        horizontal(row, column),
                        horizontal(row, column - 1),
                        vertical(row, column),
                        vertical(row - 1, column),
                    ]
                )
            )
            hz_rows.append(
                sorted(
                    [
                        horizontal(row, column),
                        horizontal(row + 1, column),
                        vertical(row, column),
                        vertical(row, column + 1),
                    ]
                )
            )
    return hx_rows, hz_rows


def _bb_payload(
    rows: int,
    columns: int,
    a_exponents: list[list[int]],
    b_exponents: list[list[int]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    block = rows * columns
    hx_rows: list[list[int]] = []
    hz_rows: list[list[int]] = []
    for row in range(block):
        hx_rows.append(
            _shift_row(rows, columns, a_exponents, row)
            + [block + index for index in _shift_row(rows, columns, b_exponents, row)]
        )
        hz_rows.append(
            _shift_row(rows, columns, b_exponents, row, transpose=True)
            + [
                block + index
                for index in _shift_row(rows, columns, a_exponents, row, transpose=True)
            ]
        )
    return _sparse_payload(hx_rows, 2 * block), _sparse_payload(hz_rows, 2 * block)


def _apm_affine_payload(
    p_value: int,
    a_shifts: list[int],
    b_shifts: list[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    return _bb_payload(
        p_value,
        1,
        [[shift, 0] for shift in a_shifts],
        [[shift, 0] for shift in b_shifts],
    )


def _shift_row(
    rows: int,
    columns: int,
    exponents: list[list[int]],
    row_index: int,
    *,
    transpose: bool = False,
) -> list[int]:
    row, column = divmod(row_index, columns)
    support: set[int] = set()
    for row_shift, column_shift in exponents:
        if transpose:
            target = ((row - row_shift) % rows) * columns + (
                (column - column_shift) % columns
            )
        else:
            target = ((row + row_shift) % rows) * columns + (
                (column + column_shift) % columns
            )
        if target in support:
            support.remove(target)
        else:
            support.add(target)
    return sorted(support)


def _sparse_payload(rows: list[list[int]], num_cols: int) -> dict[str, Any]:
    return {
        "format": "sparse_rows",
        "num_cols": num_cols,
        "rows": [sorted(row) for row in rows],
    }


def _matrix_width(payload: dict[str, Any]) -> int:
    if payload.get("format") == "sparse_rows":
        return int(payload["num_cols"])
    if payload.get("format") == "dense_binary_matrix":
        return int(payload["n_cols"])
    raise SearchIntegrityError("unsupported matrix format")


def _sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid JSON object: {path.name}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def _write_readme(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# CSS distance paper-validation source pool",
                "",
                "This directory contains the public, split-free matrix source pool used",
                "to materialize the private 24-instance blind development suite and",
                "12-instance sealed final holdout.",
                "",
                "Committed artifacts:",
                "",
                "- `source_pool.json`: 36 redistribution-approved CSS matrix records.",
                "- `instances/**/hx.json` and `instances/**/hz.json`: public source matrices.",
                "- `seeds.json`: 20 committed seeds; each algorithm run is capped at 300 seconds.",
                "- `curation.json`: source pins, generator commands, evidence keys, and reference types.",
                "",
                "The source pool deliberately contains no development/final split assignment.",
                "Use `prepare-css-distance-paper-suite` with an operator-owned private root",
                "outside Git worktrees to create the blind evaluator copy and public commitment.",
                "",
                "Curation limitation: six quantum-Tanner additions are toric-product proxy",
                "finite specs generated locally because the pinned quantum-Tanner materializer",
                "was not available in this workspace. They are marked only as finite-spec",
                "coverage and must not be cited as family-wide quantum-Tanner evidence.",
                "",
                "Rebuild:",
                "",
                "```bash",
                "PYTHONPATH=src python3 scripts/build_css_distance_paper_pool.py --root .",
                "```",
                "",
            ]
        )
    )


def _git_head_or_zero(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    head = result.stdout.strip()
    if result.returncode != 0 or len(head) != 40:
        return "0" * 40
    return head


if __name__ == "__main__":
    raise SystemExit(main())
