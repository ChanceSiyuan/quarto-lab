#!/usr/bin/env python3
import argparse
import json
import os
import random
from typing import Dict, Iterable, List, Optional, Tuple


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            for j, val in enumerate(row):
                if val & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    if {"num_cols", "rows"} <= set(obj):
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for j in row:
                j = int(j)
                if j <= last or j < 0 or j >= n:
                    raise ValueError(f"invalid sparse row in {path}")
                bits |= 1 << j
                last = j
            rows.append(bits)
        return rows, n

    raise ValueError(f"unknown matrix JSON format: {path}")


def add_basis(basis: Dict[int, int], value: int) -> bool:
    x = value
    while x:
        p = x.bit_length() - 1
        row = basis.get(p)
        if row is None:
            basis[p] = x
            return True
        x ^= row
    return False


def make_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for row in rows:
        if row:
            add_basis(basis, row)
    return basis


def in_span(basis: Dict[int, int], value: int) -> bool:
    x = value
    while x:
        p = x.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return False
        x ^= row
    return True


def rref_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis = make_basis(rows)
    for p in sorted(list(basis)):
        row = basis[p]
        for q in sorted(list(basis), reverse=True):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    return basis


def nullspace_basis(rows: List[int], n_cols: int) -> List[int]:
    rref = rref_basis(rows)
    pivots = set(rref)
    out = []
    for free in range(n_cols):
        if free in pivots:
            continue
        v = 1 << free
        for p, row in rref.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(rows: List[int], v: int) -> bool:
    return all(((row & v).bit_count() & 1) == 0 for row in rows)


def bits_to_list(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def greedy_stabilizer_descent(v: int, stabilizers: List[int], rng: random.Random) -> int:
    current = v
    rows = [r for r in stabilizers if r]
    if not rows:
        return current

    best_weight = current.bit_count()
    order = rows[:]
    for _ in range(18):
        improved = False
        rng.shuffle(order)
        for row in order:
            trial = current ^ row
            w = trial.bit_count()
            if w < best_weight or (w == best_weight and w > 0 and rng.random() < 0.015):
                current = trial
                if w < best_weight:
                    best_weight = w
                    improved = True
        if not improved:
            break
    return current


def quotient_generators(
    kernel: List[int], stabilizers: List[int], rng: random.Random
) -> List[int]:
    span = make_basis(stabilizers)
    gens = kernel[:]
    rng.shuffle(gens)
    logicals = []
    for v in gens:
        if add_basis(span, v):
            logicals.append(v)
    return logicals


def search_basis(
    basis_name: str,
    constraints: List[int],
    stabilizers: List[int],
    n: int,
    rng: random.Random,
) -> Optional[int]:
    kernel = nullspace_basis(constraints, n)
    stab_basis = make_basis(stabilizers)
    logicals = quotient_generators(kernel, stabilizers, rng)
    if not logicals:
        return None

    best: Optional[int] = None

    def consider(v: int) -> None:
        nonlocal best
        if not v:
            return
        v = greedy_stabilizer_descent(v, stabilizers, rng)
        if syndrome_zero(constraints, v) and not in_span(stab_basis, v):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for v in sorted(logicals, key=lambda x: x.bit_count()):
        consider(v)

    rounds = max(256, 64 * len(logicals))
    rounds = min(rounds, 12000)
    for _ in range(rounds):
        v = 0
        # Bias toward small random combinations, while occasionally mixing broadly.
        if len(logicals) <= 8 or rng.random() < 0.2:
            for g in logicals:
                if rng.random() < 0.5:
                    v ^= g
        else:
            take = 1 + int(rng.expovariate(0.7))
            take = min(take, len(logicals))
            for g in rng.sample(logicals, take):
                v ^= g
        consider(v)

    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        n = nx

        choices = [
            ("x", hz, hx),
            ("z", hx, hz),
        ]
        rng.shuffle(choices)

        best_basis: Optional[str] = None
        best_vector: Optional[int] = None
        for name, constraints, stabilizers in choices:
            v = search_basis(name, constraints, stabilizers, n, rng)
            if v is not None and (best_vector is None or v.bit_count() < best_vector.bit_count()):
                best_basis = name
                best_vector = v

        if best_vector is None or best_basis is None:
            result = {
                "status": "failed",
                "basis": None,
                "vector": [],
                "upper_bound": None,
            }
        else:
            result = {
                "status": "completed",
                "basis": best_basis,
                "vector": bits_to_list(best_vector, n),
                "upper_bound": best_vector.bit_count(),
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
