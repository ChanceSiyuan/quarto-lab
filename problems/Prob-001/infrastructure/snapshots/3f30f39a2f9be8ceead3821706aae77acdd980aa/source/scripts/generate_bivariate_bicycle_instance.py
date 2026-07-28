#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_exponents(value: str, *, label: str) -> list[list[int]]:
    parsed = json.loads(value)
    if (
        not isinstance(parsed, list)
        or not parsed
        or any(
            not isinstance(item, list)
            or len(item) != 2
            or any(not isinstance(axis, int) or isinstance(axis, bool) for axis in item)
            for item in parsed
        )
    ):
        raise ValueError(f"{label} must be a non-empty JSON list of [x, y] integers")
    return [[int(item[0]), int(item[1])] for item in parsed]


def _dense_shift_matrix(rows: int, columns: int, exponents: list[list[int]]) -> list[list[int]]:
    block_size = rows * columns
    matrix = [[0 for _ in range(block_size)] for _ in range(block_size)]
    for row_x in range(rows):
        for row_y in range(columns):
            row_index = row_x * columns + row_y
            for shift_x, shift_y in exponents:
                column_x = (row_x + shift_x) % rows
                column_y = (row_y + shift_y) % columns
                matrix[row_index][column_x * columns + column_y] ^= 1
    return matrix


def _transpose(matrix: list[list[int]]) -> list[list[int]]:
    return [list(column) for column in zip(*matrix, strict=True)]


def _hstack(left: list[list[int]], right: list[list[int]]) -> list[list[int]]:
    return [left_row + right_row for left_row, right_row in zip(left, right, strict=True)]


def _matrix_payload(matrix: list[list[int]]) -> dict[str, Any]:
    return {
        "format": "dense_binary_matrix",
        "n_rows": len(matrix),
        "n_cols": len(matrix[0]) if matrix else 0,
        "data": matrix,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _instance_payload(
    *,
    rows: int,
    columns: int,
    vc: list[list[int]],
    hd: list[list[int]],
    generated_at: str,
) -> dict[str, Any]:
    block_size = rows * columns
    parameters = {"m": rows, "n": columns, "vc": vc, "hd": hd}
    return {
        "id": f"bivariate-bicycle-code-m{rows}-n{columns}",
        "code_id": "bivariate-bicycle-code",
        "family_id": "bivariate-bicycle-code",
        "title": f"Bivariate Bicycle Code m={rows} n={columns}",
        "instance_kind": "finite_css_instance",
        "matrix_format": "dense_binary_json",
        "artifacts": {"hx": "hx.json", "hz": "hz.json"},
        "parameters": parameters,
        "derived_properties": {
            "distance": None,
            "n": 2 * block_size,
            "kx": None,
            "kz": None,
            "mx": block_size,
            "mz": block_size,
        },
        "provenance": {
            "generator": "autoqec-bivariate-bicycle-fallback",
            "generator_env": "python3",
            "generated_at": generated_at,
            "generator_script": "scripts/generate_bivariate_bicycle_instance.py",
            "generator_parameters": parameters,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--m", type=int, required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--vc", required=True)
    parser.add_argument("--hd", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    if args.m < 1 or args.n < 1:
        parser.error("--m and --n must be positive")
    vc = _parse_exponents(args.vc, label="--vc")
    hd = _parse_exponents(args.hd, label="--hd")

    a_matrix = _dense_shift_matrix(args.m, args.n, vc)
    b_matrix = _dense_shift_matrix(args.m, args.n, hd)
    hx = _hstack(a_matrix, b_matrix)
    hz = _hstack(_transpose(b_matrix), _transpose(a_matrix))

    _write_json(
        args.output_root / "instance.json",
        _instance_payload(
            rows=args.m,
            columns=args.n,
            vc=vc,
            hd=hd,
            generated_at=args.generated_at,
        ),
    )
    _write_json(args.output_root / "hx.json", _matrix_payload(hx))
    _write_json(args.output_root / "hz.json", _matrix_payload(hz))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
