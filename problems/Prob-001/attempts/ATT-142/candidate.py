#!/usr/bin/env python3
import argparse
import json
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def fail() -> None:
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))


def load_matrix(path: str) -> Tuple[int, List[int]]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        n_cols = max((len(row) for row in obj), default=0)
        rows = []
        for row in obj:
            bits = 0
            for j, value in enumerate(row):
                if int(value) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return n_cols, rows

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or row list")

    if "dense_binary_matrix" in obj and isinstance(obj["dense_binary_matrix"], dict):
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj and isinstance(obj["sparse_rows"], dict):
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_cols = int(obj.get("n_cols", max((len(row) for row in obj["data"]), default=0)))
        rows = []
        for row in obj["data"]:
            bits = 0
            for j, value in enumerate(row):
                if int(value) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return n_cols, rows

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            previous = -1
            for col in row:
                col = int(col)
                if col <= previous or col < 0 or col >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing valid column indices")
                bits |= 1 << col
                previous = col
            rows.append(bits)
        return n_cols, rows

    raise ValueError("unsupported matrix JSON format")


def rref(rows: Iterable[int]) -> Tuple[List[int], List[int]]:
    basis: Dict[int, int] = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break

    pivots = sorted(basis.keys(), reverse=True)
    for p in pivots:
        row = basis[p]
        for q in pivots:
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row

    pivots = sorted(basis.keys())
    return [basis[p] for p in pivots], pivots


def reduce_by_basis(vec: int, basis_rows: Sequence[int], pivots: Sequence[int]) -> int:
    x = int(vec)
    for row, pivot in zip(basis_rows, pivots):
        if (x >> pivot) & 1:
            x ^= row
    return x


def in_rowspace(vec: int, rows: Sequence[int]) -> bool:
    basis_rows, pivots = rref(rows)
    return reduce_by_basis(vec, basis_rows, pivots) == 0


def nullspace_basis(rows: Sequence[int], n_cols: int) -> List[int]:
    basis_rows, pivots = rref(rows)
    pivot_set = set(pivots)
    free_cols = [j for j in range(n_cols) if j not in pivot_set]
    out = []
    for free in free_cols:
        vec = 1 << free
        for row, pivot in zip(basis_rows, pivots):
            if (row >> free) & 1:
                vec |= 1 << pivot
        out.append(vec)
    return out


def syndrome_zero(vec: int, checks: Sequence[int]) -> bool:
    return all(((vec & row).bit_count() & 1) == 0 for row in checks)


def bit_list(vec: int, n_cols: int) -> List[int]:
    return [(vec >> j) & 1 for j in range(n_cols)]


def random_kernel_vector(null_basis: Sequence[int], rng: random.Random) -> int:
    x = 0
    for row in null_basis:
        if rng.getrandbits(1):
            x ^= row
    return x


def quotient_seeds(null_basis: Sequence[int], stabilizers: Sequence[int], rng: random.Random) -> List[int]:
    stab_basis, stab_pivots = rref(stabilizers)
    seeds = []
    quotient_basis: List[int] = []
    order = list(null_basis)
    rng.shuffle(order)
    for vec in order:
        rem = reduce_by_basis(vec, stab_basis, stab_pivots)
        rem = reduce_by_basis(rem, *rref(quotient_basis))
        if rem:
            quotient_basis.append(rem)
            seeds.append(vec)
    rng.shuffle(seeds)
    return seeds


def reduce_weight(vec: int, checks: Sequence[int], stabilizers: Sequence[int], rng: random.Random) -> int:
    best = vec
    best_w = best.bit_count()
    if best_w == 0:
        return best

    rows = [r for r in stabilizers if r]
    if not rows:
        return best

    # Randomized coordinate-descent over the stabilizer coset. This is only an
    # upper-bound search: it improves a known logical witness without proving optimality.
    for _restart in range(18):
        cur = best
        cur_w = best_w
        temperature = 2.5
        for _sweep in range(35):
            rng.shuffle(rows)
            changed = False
            for row in rows:
                cand = cur ^ row
                cw = cand.bit_count()
                delta = cw - cur_w
                if delta < 0 or (delta > 0 and rng.random() < 0.015 * temperature / (delta + 1)):
                    cur = cand
                    cur_w = cw
                    changed = True
                    if cur_w < best_w and syndrome_zero(cur, checks):
                        best = cur
                        best_w = cur_w
            temperature *= 0.82
            if not changed:
                break

        cur = best
        cur_w = best_w
        improved = True
        while improved:
            improved = False
            rng.shuffle(rows)
            for row in rows:
                cand = cur ^ row
                cw = cand.bit_count()
                if cw < cur_w:
                    cur = cand
                    cur_w = cw
                    improved = True
                    if cur_w < best_w and syndrome_zero(cur, checks):
                        best = cur
                        best_w = cur_w
    return best


def find_witness(
    label: str,
    checks: Sequence[int],
    stabilizers: Sequence[int],
    n_cols: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    null_basis = nullspace_basis(checks, n_cols)
    if not null_basis:
        return None

    seeds = quotient_seeds(null_basis, stabilizers, rng)
    for _ in range(160):
        seed = random_kernel_vector(null_basis, rng)
        if seed and not in_rowspace(seed, stabilizers):
            seeds.append(seed)

    best: Optional[int] = None
    best_w: Optional[int] = None
    for seed in seeds[:240]:
        if not seed or in_rowspace(seed, stabilizers):
            continue
        cand = reduce_weight(seed, checks, stabilizers, rng)
        if cand and syndrome_zero(cand, checks) and not in_rowspace(cand, stabilizers):
            cw = cand.bit_count()
            if best is None or cw < best_w:
                best = cand
                best_w = cw

    if best is None:
        return None
    return label, best


def main() -> int:
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound logical witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx_n, hx_rows = load_matrix(args.hx)
        hz_n, hz_rows = load_matrix(args.hz)
        if hx_n != hz_n:
            raise ValueError("Hx and Hz must have the same number of columns")

        rng = random.Random(args.seed)
        x_result = find_witness("x", hz_rows, hx_rows, hx_n, rng)
        z_result = find_witness("z", hx_rows, hz_rows, hx_n, rng)
        results = [r for r in (x_result, z_result) if r is not None]
        if not results:
            fail()
            return 0

        basis, vec = min(results, key=lambda item: (item[1].bit_count(), 0 if item[0] == "x" else 1))
        checks = hz_rows if basis == "x" else hx_rows
        stabilizers = hx_rows if basis == "x" else hz_rows
        if not (vec and syndrome_zero(vec, checks) and not in_rowspace(vec, stabilizers)):
            fail()
            return 0

        out = {
            "status": "completed",
            "basis": basis,
            "vector": bit_list(vec, hx_n),
            "upper_bound": vec.bit_count(),
        }
        print(json.dumps(out, separators=(",", ":")))
        return 0
    except Exception:
        fail()
        return 0


if __name__ == "__main__":
    sys.exit(main())
