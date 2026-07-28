#!/usr/bin/env python3
"""Randomized CSS logical upper-bound witness search.

This entrypoint intentionally reports only verified logical witnesses.  It uses
binary linear algebra to build quotient representatives and to verify the final
candidate, then performs a randomized stabilizer-descent search for low-weight
members of those logical cosets.
"""

import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def fail() -> None:
    print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))


def row_to_int(indices: Iterable[int]) -> int:
    value = 0
    for idx in indices:
        if idx < 0:
            raise ValueError("negative column index")
        value ^= 1 << idx
    return value


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as handle:
        obj = json.load(handle)

    if isinstance(obj, dict) and {"n_rows", "n_cols", "data"} <= set(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError("dense row length mismatch")
            bits = [i for i, bit in enumerate(row) if int(bit) & 1]
            rows.append(row_to_int(bits))
        return rows, n_cols

    if isinstance(obj, dict) and {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            clean = []
            for idx in row:
                idx = int(idx)
                if idx <= last or idx >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing and in range")
                clean.append(idx)
                last = idx
            rows.append(row_to_int(clean))
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


def pivot_index(row: int) -> int:
    return row.bit_length() - 1


def rref_basis(rows: Sequence[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for original in rows:
        row = original
        while row:
            p = pivot_index(row)
            if p not in basis:
                basis[p] = row
                break
            row ^= basis[p]

    for p in sorted(list(basis)):
        row = basis[p]
        for q, other in list(basis.items()):
            if q != p and ((other >> p) & 1):
                basis[q] = other ^ row
    return basis


def reduce_with_basis(row: int, basis: Dict[int, int]) -> int:
    while row:
        p = pivot_index(row)
        reducer = basis.get(p)
        if reducer is None:
            return row
        row ^= reducer
    return 0


def in_rowspace(row: int, basis: Dict[int, int]) -> bool:
    return reduce_with_basis(row, basis) == 0


def nullspace_basis(check_rows: Sequence[int], n_cols: int) -> List[int]:
    basis = rref_basis(check_rows)
    pivots = set(basis)
    free_cols = [c for c in range(n_cols) if c not in pivots]
    result = []
    for free in free_cols:
        vec = 1 << free
        for p, row in basis.items():
            if (row >> free) & 1:
                vec |= 1 << p
        result.append(vec)
    return result


def quotient_logical_basis(kernel_basis: Sequence[int], stabilizer_basis: Dict[int, int]) -> List[int]:
    span = dict(stabilizer_basis)
    logicals = []
    for vec in sorted(kernel_basis, key=lambda x: (x.bit_count(), x)):
        rem = reduce_with_basis(vec, span)
        if rem:
            logicals.append(vec)
            span[pivot_index(rem)] = rem
    return logicals


def int_to_vector(value: int, n_cols: int) -> List[int]:
    return [(value >> i) & 1 for i in range(n_cols)]


def random_combo(vectors: Sequence[int], rng: random.Random, p: float = 0.5) -> int:
    value = 0
    for vec in vectors:
        if rng.random() < p:
            value ^= vec
    return value


def verify_witness(vec: int, check_rows: Sequence[int], stabilizer_basis: Dict[int, int]) -> bool:
    if vec == 0:
        return False
    if any((vec & row).bit_count() & 1 for row in check_rows):
        return False
    return not in_rowspace(vec, stabilizer_basis)


def greedy_stabilizer_descent(
    start: int,
    stabilizers: Sequence[int],
    rng: random.Random,
    passes: int,
) -> int:
    cur = start
    cur_w = cur.bit_count()
    if not stabilizers:
        return cur

    order = list(stabilizers)
    for _ in range(passes):
        improved = False
        rng.shuffle(order)
        for row in order:
            nxt = cur ^ row
            nxt_w = nxt.bit_count()
            if nxt_w < cur_w or (nxt_w == cur_w and rng.random() < 0.015):
                cur, cur_w = nxt, nxt_w
                improved = True
        if not improved:
            break
    return cur


def annealed_stabilizer_walk(
    start: int,
    stabilizers: Sequence[int],
    rng: random.Random,
    steps: int,
) -> int:
    cur = start
    cur_w = cur.bit_count()
    best = cur
    best_w = cur_w
    if not stabilizers:
        return cur

    for step in range(steps):
        row = stabilizers[rng.randrange(len(stabilizers))]
        nxt = cur ^ row
        nxt_w = nxt.bit_count()
        delta = nxt_w - cur_w
        temperature = max(0.25, 4.0 * (1.0 - step / max(1, steps)))
        if delta <= 0 or rng.random() < 2.0 ** (-delta / temperature):
            cur, cur_w = nxt, nxt_w
            if cur_w < best_w:
                best, best_w = cur, cur_w
    return greedy_stabilizer_descent(best, stabilizers, rng, passes=4)


def make_stabilizer_pool(rows: Sequence[int], rng: random.Random, limit: int) -> List[int]:
    base = [row for row in rows if row]
    pool = list(base)
    if not base:
        return pool
    rounds = max(0, min(limit - len(pool), 4 * len(base)))
    for _ in range(rounds):
        width = 1 + rng.randrange(min(8, len(base)))
        combo = 0
        for row in rng.sample(base, width):
            combo ^= row
        if combo:
            pool.append(combo)
    pool.sort(key=lambda x: (x.bit_count(), x))
    return pool[:limit]


def search_basis(
    label: str,
    check_rows: Sequence[int],
    stabilizer_rows: Sequence[int],
    n_cols: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    stabilizer_rref = rref_basis(stabilizer_rows)
    kernel = nullspace_basis(check_rows, n_cols)
    logicals = quotient_logical_basis(kernel, stabilizer_rref)
    if not logicals:
        return None

    stabilizer_pool = make_stabilizer_pool(stabilizer_rows, rng, limit=max(64, min(4096, 8 * max(1, len(stabilizer_rows)))))
    best: Optional[int] = None

    seeds: List[int] = list(logicals)
    for _ in range(min(256, max(32, 4 * len(logicals)))):
        combo = random_combo(logicals, rng, p=min(0.5, max(1.0 / max(1, len(logicals)), 0.08)))
        if combo:
            seeds.append(combo)

    budget = max(256, min(6000, 80 * max(1, len(logicals)) + 12 * n_cols))
    for step in range(budget):
        if step < len(seeds):
            start = seeds[step]
        else:
            p = rng.choice((0.08, 0.12, 0.18, 0.25, 0.35, 0.5))
            start = random_combo(logicals, rng, p=p)
            if not start:
                start = rng.choice(logicals)
        if rng.random() < 0.35:
            cand = annealed_stabilizer_walk(start, stabilizer_pool, rng, steps=min(900, 20 + 2 * len(stabilizer_pool)))
        else:
            cand = greedy_stabilizer_descent(start, stabilizer_pool, rng, passes=5)
        if verify_witness(cand, check_rows, stabilizer_rref):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    if best is None:
        return None
    return label, best


def run(args: argparse.Namespace) -> None:
    hx_rows, hx_cols = load_matrix(args.hx)
    hz_rows, hz_cols = load_matrix(args.hz)
    if hx_cols != hz_cols:
        raise ValueError("Hx and Hz column counts differ")

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    n_cols = hx_cols
    rng = random.Random(args.seed)
    zx = search_basis("x", hz_rows, hx_rows, n_cols, rng)
    zz = search_basis("z", hx_rows, hz_rows, n_cols, rng)
    options = [item for item in (zx, zz) if item is not None]
    if not options:
        fail()
        return

    basis, vec = min(options, key=lambda item: (item[1].bit_count(), item[0]))
    out = {
        "status": "completed",
        "basis": basis,
        "vector": int_to_vector(vec, n_cols),
        "upper_bound": int(vec.bit_count()),
    }
    print(json.dumps(out, separators=(",", ":")))


def main() -> int:
    parser = argparse.ArgumentParser(description="Randomized CSS logical upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        run(args)
    except Exception:
        fail()
    return 0


if __name__ == "__main__":
    sys.exit(main())
