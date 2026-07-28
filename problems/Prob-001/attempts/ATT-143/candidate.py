#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


Mask = int


def load_matrix(path: str) -> Tuple[List[Mask], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            m = 0
            if len(row) != n_cols:
                raise ValueError(f"dense row has length {len(row)}, expected {n_cols}")
            for i, bit in enumerate(row):
                if bit:
                    m |= 1 << i
            rows.append(m)
        return rows, n_cols

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for inds in obj["rows"]:
            prev = -1
            m = 0
            for idx in inds:
                idx = int(idx)
                if idx <= prev or idx < 0 or idx >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing and in range")
                m |= 1 << idx
                prev = idx
            rows.append(m)
        return rows, n_cols

    raise ValueError(f"unrecognized matrix JSON format in {path}")


def rref_basis(rows: Iterable[Mask]) -> Tuple[List[Mask], List[int]]:
    basis: Dict[int, Mask] = {}
    for value in rows:
        x = value
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        row = basis[p]
        for q in sorted(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    pivots = sorted(basis, reverse=True)
    return [basis[p] for p in pivots], pivots


def reduce_by_basis(v: Mask, basis: Sequence[Mask], pivots: Sequence[int]) -> Mask:
    x = v
    for row, p in zip(basis, pivots):
        if (x >> p) & 1:
            x ^= row
    return x


def in_rowspace(v: Mask, basis: Sequence[Mask], pivots: Sequence[int]) -> bool:
    return reduce_by_basis(v, basis, pivots) == 0


def nullspace_basis(rows: Sequence[Mask], n_cols: int) -> List[Mask]:
    rbasis, pivots = rref_basis(rows)
    pivot_set = set(pivots)
    free_cols = [i for i in range(n_cols) if i not in pivot_set]
    out = []
    for free in free_cols:
        v = 1 << free
        for row, p in zip(rbasis, pivots):
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def dot_parity(a: Mask, b: Mask) -> int:
    return (a & b).bit_count() & 1


def in_kernel(v: Mask, checks: Sequence[Mask]) -> bool:
    return all(dot_parity(v, row) == 0 for row in checks)


def mask_to_bits(v: Mask, n_cols: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n_cols)]


def random_span_vector(rng: random.Random, rows: Sequence[Mask], p_num: int = 1, p_den: int = 2) -> Mask:
    v = 0
    for row in rows:
        if rng.randrange(p_den) < p_num:
            v ^= row
    return v


def greedy_reduce(v: Mask, stabilizers: Sequence[Mask], rng: random.Random, rounds: int) -> Mask:
    best = v
    best_w = best.bit_count()
    if not stabilizers:
        return best

    current = v
    current_w = current.bit_count()
    order = list(stabilizers)
    temperature = 2
    stale = 0
    for r in range(rounds):
        rng.shuffle(order)
        improved = False
        for row in order:
            cand = current ^ row
            cw = cand.bit_count()
            if cw < current_w or (temperature and cw <= current_w + 1 and rng.randrange(64) == 0):
                current, current_w = cand, cw
                if cw < best_w:
                    best, best_w = cand, cw
                    improved = True
        if not improved:
            stale += 1
            if stale % 8 == 0:
                current = best ^ random_span_vector(rng, order, 1, 16)
                current_w = current.bit_count()
        temperature = 1 if r < rounds // 2 else 0
    return best


def quotient_representatives(kernel_rows: Sequence[Mask], stabilizers: Sequence[Mask]) -> List[Mask]:
    span_basis, span_pivots = rref_basis(stabilizers)
    reps = []
    current_rows = list(stabilizers)
    for row in sorted(kernel_rows, key=lambda x: x.bit_count()):
        if row and not in_rowspace(row, span_basis, span_pivots):
            reps.append(row)
            current_rows.append(row)
            span_basis, span_pivots = rref_basis(current_rows)
    return reps


def search_basis(
    name: str,
    commute_checks: Sequence[Mask],
    stabilizers: Sequence[Mask],
    n_cols: int,
    rng: random.Random,
) -> Optional[Tuple[str, Mask]]:
    stab_basis, stab_pivots = rref_basis(stabilizers)
    kernel = nullspace_basis(commute_checks, n_cols)
    reps = quotient_representatives(kernel, stabilizers)
    if not reps:
        return None

    seeds = list(reps)
    for rep in reps:
        seeds.append(rep ^ random_span_vector(rng, stabilizers, 1, 8))
    for _ in range(min(512, 32 * max(1, len(reps)))):
        seeds.append(random_span_vector(rng, reps, 1, 2))

    best: Optional[Mask] = None
    best_w = n_cols + 1
    rounds = max(12, min(240, 12 + len(stabilizers) // 2))
    for seed in seeds:
        if seed == 0:
            continue
        cand = greedy_reduce(seed, stabilizers, rng, rounds)
        if cand and in_kernel(cand, commute_checks) and not in_rowspace(cand, stab_basis, stab_pivots):
            cw = cand.bit_count()
            if cw < best_w:
                best, best_w = cand, cw

    return (name, best) if best is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz must have the same number of columns")
        os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)

        candidates = [
            search_basis("x", hz, hx, nx, rng),
            search_basis("z", hx, hz, nx, rng),
        ]
        witnesses = [c for c in candidates if c is not None]
        if witnesses:
            basis, vec = min(witnesses, key=lambda item: (item[1].bit_count(), item[0]))
            result = {
                "status": "completed",
                "basis": basis,
                "vector": mask_to_bits(vec, nx),
                "upper_bound": vec.bit_count(),
            }
        else:
            result = {"status": "not_found", "basis": "x", "vector": [], "upper_bound": None}
    except Exception as exc:
        result = {"status": "error", "basis": "x", "vector": [], "upper_bound": None}
        try:
            os.makedirs(args.output_dir, exist_ok=True)
            with open(os.path.join(args.output_dir, "error.txt"), "w", encoding="utf-8") as f:
                f.write(str(exc) + "\n")
        except Exception:
            pass

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
