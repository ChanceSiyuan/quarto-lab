#!/usr/bin/env python3
import argparse
import json
import os
import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"}.issubset(obj):
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n:
                raise ValueError("dense row length does not match n_cols")
            bits = 0
            for i, value in enumerate(row):
                if value not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if int(value):
                    bits |= 1 << i
            rows.append(bits)
        return rows, n

    if {"num_cols", "rows"}.issubset(obj):
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            bits = 0
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n:
                    raise ValueError("sparse rows must be strictly increasing valid indices")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return rows, n

    raise ValueError("unknown matrix JSON format")


def rref(rows: Iterable[int]) -> Tuple[Dict[int, int], List[int]]:
    basis: Dict[int, int] = {}
    for value in rows:
        x = int(value)
        while x:
            pivot = x.bit_length() - 1
            if pivot in basis:
                x ^= basis[pivot]
            else:
                basis[pivot] = x
                break

    for pivot in sorted(basis):
        row = basis[pivot]
        for other in sorted(basis):
            if other != pivot and ((basis[other] >> pivot) & 1):
                basis[other] ^= row

    pivots = sorted(basis)
    return basis, pivots


def reduce_with_basis(value: int, basis: Dict[int, int]) -> int:
    x = int(value)
    while x:
        pivot = x.bit_length() - 1
        row = basis.get(pivot)
        if row is None:
            return x
        x ^= row
    return 0


def in_rowspace(value: int, basis: Dict[int, int]) -> bool:
    return reduce_with_basis(value, basis) == 0


def nullspace_basis(check_rows: Sequence[int], n: int) -> List[int]:
    basis, pivots = rref(check_rows)
    pivot_set = set(pivots)
    result = []
    for free_col in range(n):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        for pivot in pivots:
            row = basis[pivot]
            if ((row & v).bit_count() & 1) != 0:
                v |= 1 << pivot
        result.append(v)
    return result


def commutes_with_checks(value: int, checks: Sequence[int]) -> bool:
    return all(((value & row).bit_count() & 1) == 0 for row in checks)


def bits_to_list(value: int, n: int) -> List[int]:
    return [(value >> i) & 1 for i in range(n)]


def greedy_reduce_by_stabilizers(value: int, stabilizers: Sequence[int], rng: random.Random) -> int:
    current = value
    current_w = current.bit_count()
    rows = [r for r in stabilizers if r]

    for _ in range(4):
        rng.shuffle(rows)
        changed = False
        for row in rows:
            candidate = current ^ row
            w = candidate.bit_count()
            if w < current_w or (w == current_w and rng.random() < 0.02):
                current = candidate
                current_w = w
                changed = True
        if not changed:
            break
    return current


def candidate_for_basis(
    basis_name: str,
    kernel_checks: Sequence[int],
    stabilizers: Sequence[int],
    n: int,
    seed: int,
    rounds: int,
) -> Optional[Tuple[str, int]]:
    rng = random.Random((seed << 8) ^ (0x58 if basis_name == "x" else 0x5A))
    stab_basis, _ = rref(stabilizers)
    logical_generators = nullspace_basis(kernel_checks, n)
    if not logical_generators:
        return None

    direct = [g for g in logical_generators if g and not in_rowspace(g, stab_basis)]
    if not direct:
        return None

    best: Optional[int] = None
    ordered = sorted(direct, key=lambda x: x.bit_count())
    seed_pool = ordered[: min(32, len(ordered))]

    for base in seed_pool:
        reduced = greedy_reduce_by_stabilizers(base, list(stabilizers), rng)
        if reduced and not in_rowspace(reduced, stab_basis) and commutes_with_checks(reduced, kernel_checks):
            if best is None or reduced.bit_count() < best.bit_count():
                best = reduced

    for _ in range(max(0, rounds)):
        v = 0
        picks = 0
        for gen in logical_generators:
            if rng.getrandbits(1):
                v ^= gen
                picks += 1
        if picks == 0:
            v = rng.choice(direct)

        v = greedy_reduce_by_stabilizers(v, list(stabilizers), rng)
        if not v:
            continue
        if in_rowspace(v, stab_basis):
            continue
        if not commutes_with_checks(v, kernel_checks):
            continue
        if best is None or v.bit_count() < best.bit_count():
            best = v

    if best is None:
        return None
    return basis_name, best


def main() -> int:
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        n = nx

        os.makedirs(args.output_dir, exist_ok=True)

        rounds = max(256, min(8192, 64 * max(1, n)))
        attempts = [
            candidate_for_basis("x", hz, hx, n, args.seed, rounds),
            candidate_for_basis("z", hx, hz, n, args.seed + 1, rounds),
        ]
        attempts = [item for item in attempts if item is not None]
        if attempts:
            basis_name, vector = min(attempts, key=lambda item: item[1].bit_count())
            result = {
                "status": "completed",
                "basis": basis_name,
                "vector": bits_to_list(vector, n),
                "upper_bound": int(vector.bit_count()),
            }
        else:
            result = {
                "status": "not_found",
                "basis": "",
                "vector": [],
                "upper_bound": None,
            }
    except Exception:
        result = {
            "status": "error",
            "basis": "",
            "vector": [],
            "upper_bound": None,
        }

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
