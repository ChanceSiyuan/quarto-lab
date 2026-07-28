#!/usr/bin/env python3
import argparse
import json
import os
import random
from typing import Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> Tuple[int, int, List[int]]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n_rows = int(obj["n_rows"])
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            if len(row) != n_cols:
                raise ValueError("dense row has wrong length")
            for j, value in enumerate(row):
                if int(value) & 1:
                    bits |= 1 << j
            rows.append(bits)
        if len(rows) != n_rows:
            raise ValueError("dense matrix has wrong row count")
        return n_rows, n_cols, rows

    if "num_cols" in obj and "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for inds in obj["rows"]:
            bits = 0
            prev = -1
            for raw_j in inds:
                j = int(raw_j)
                if j <= prev or j < 0 or j >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing")
                bits |= 1 << j
                prev = j
            rows.append(bits)
        return len(rows), n_cols, rows

    raise ValueError("unsupported matrix JSON format")


def row_basis(rows: Iterable[int]) -> List[int]:
    pivots = {}
    for raw in rows:
        x = int(raw)
        for p in sorted(pivots, reverse=True):
            if (x >> p) & 1:
                x ^= pivots[p]
        if x:
            p = x.bit_length() - 1
            for q, row in list(pivots.items()):
                if (row >> p) & 1:
                    pivots[q] = row ^ x
            pivots[p] = x
    return [pivots[p] for p in sorted(pivots, reverse=True)]


def reduce_by_basis(x: int, basis: Sequence[int]) -> int:
    y = int(x)
    for b in basis:
        if y & (1 << (b.bit_length() - 1)):
            y ^= b
    return y


def in_rowspace(x: int, basis: Sequence[int]) -> bool:
    return reduce_by_basis(x, basis) == 0


def syndrome_zero(rows: Sequence[int], x: int) -> bool:
    return all(((r & x).bit_count() & 1) == 0 for r in rows)


def nullspace_basis(rows: Sequence[int], n_cols: int) -> List[int]:
    basis = row_basis(rows)
    pivot_cols = set()
    row_for_pivot = {}
    for b in basis:
        p = b.bit_length() - 1
        pivot_cols.add(p)
        row_for_pivot[p] = b

    free_cols = [j for j in range(n_cols) if j not in pivot_cols]
    out = []
    for free in free_cols:
        x = 1 << free
        for p in sorted(pivot_cols):
            row = row_for_pivot[p]
            if (row >> free) & 1:
                x |= 1 << p
        out.append(x)
    return out


def bits_to_list(x: int, n_cols: int) -> List[int]:
    return [(x >> j) & 1 for j in range(n_cols)]


def random_kernel_vector(null_basis: Sequence[int], rng: random.Random, p: float) -> int:
    x = 0
    for b in null_basis:
        if rng.random() < p:
            x ^= b
    if x == 0 and null_basis:
        x = rng.choice(null_basis)
    return x


def greedy_stabilizer_descent(
    x: int,
    stabilizers: Sequence[int],
    rng: random.Random,
    passes: int,
) -> int:
    y = x
    rows = [r for r in stabilizers if r]
    if not rows:
        return y

    for k in range(passes):
        if k & 1:
            rng.shuffle(rows)
        else:
            rows.sort(key=lambda r: (-(r & y).bit_count(), r.bit_count()))
        changed = False
        current_w = y.bit_count()
        for r in rows:
            z = y ^ r
            zw = z.bit_count()
            if zw < current_w or (zw == current_w and rng.random() < 0.015):
                y = z
                current_w = zw
                changed = True
        if not changed:
            break
    return y


def improve_with_kernel_toggles(
    x: int,
    null_basis: Sequence[int],
    stabilizers: Sequence[int],
    rng: random.Random,
    rounds: int,
) -> int:
    y = x
    if not null_basis:
        return y
    for _ in range(rounds):
        b = rng.choice(null_basis)
        z = y ^ b
        z = greedy_stabilizer_descent(z, stabilizers, rng, 2)
        if z and z.bit_count() <= y.bit_count():
            y = z
    return y


def verified_witness(
    basis_name: str,
    check_rows: Sequence[int],
    stabilizer_rows: Sequence[int],
    n_cols: int,
    seed: int,
) -> Optional[Tuple[str, int]]:
    rng = random.Random((seed << 1) ^ (0 if basis_name == "x" else 1))
    null_basis = nullspace_basis(check_rows, n_cols)
    stab_basis = row_basis(stabilizer_rows)
    if not null_basis:
        return None

    best = None
    probabilities = [1.0 / max(2, len(null_basis)), 0.03, 0.07, 0.13, 0.25, 0.5]
    iterations = max(1600, min(45000, 350 * (len(null_basis) + 1)))

    seeds = list(null_basis)
    rng.shuffle(seeds)
    for x in seeds[: min(len(seeds), 512)]:
        y = greedy_stabilizer_descent(x, stabilizer_rows, rng, 6)
        if y and syndrome_zero(check_rows, y) and not in_rowspace(y, stab_basis):
            if best is None or y.bit_count() < best.bit_count():
                best = y

    for t in range(iterations):
        p = probabilities[t % len(probabilities)]
        x = random_kernel_vector(null_basis, rng, p)
        if best is not None and rng.random() < 0.28:
            x ^= best
        x = greedy_stabilizer_descent(x, stabilizer_rows, rng, 8)
        if t % 7 == 0:
            x = improve_with_kernel_toggles(x, null_basis, stabilizer_rows, rng, 4)
        if x and syndrome_zero(check_rows, x) and not in_rowspace(x, stab_basis):
            if best is None or x.bit_count() < best.bit_count():
                best = x

    if best is None:
        return None
    if not syndrome_zero(check_rows, best) or in_rowspace(best, stab_basis):
        return None
    return basis_name, best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        _, nx, hx_rows = load_matrix(args.hx)
        _, nz, hz_rows = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        os.makedirs(args.output_dir, exist_ok=True)

        candidates = [
            verified_witness("x", hz_rows, hx_rows, nx, args.seed),
            verified_witness("z", hx_rows, hz_rows, nx, args.seed),
        ]
        candidates = [c for c in candidates if c is not None]
        if candidates:
            basis_name, vector = min(candidates, key=lambda item: item[1].bit_count())
            result = {
                "status": "completed",
                "basis": basis_name,
                "vector": bits_to_list(vector, nx),
                "upper_bound": int(vector.bit_count()),
            }
        else:
            result = {
                "status": "failed",
                "basis": None,
                "vector": [],
                "upper_bound": None,
            }
    except Exception:
        result = {
            "status": "failed",
            "basis": None,
            "vector": [],
            "upper_bound": None,
        }

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
