#!/usr/bin/env python3
import argparse
import json
import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def emit(status: str, basis: Optional[str], vector: Optional[List[int]], upper_bound: Optional[int]) -> None:
    print(json.dumps({"status": status, "basis": basis, "vector": vector, "upper_bound": upper_bound}, separators=(",", ":")))


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
            v = 0
            for i, bit in enumerate(row):
                if bit:
                    v |= 1 << i
            rows.append(v)
        return rows, n

    if {"num_cols", "rows"}.issubset(obj):
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            v = 0
            last = -1
            for idx in row:
                idx = int(idx)
                if idx <= last or idx < 0 or idx >= n:
                    raise ValueError("invalid sparse row")
                v |= 1 << idx
                last = idx
            rows.append(v)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


class GF2Basis:
    def __init__(self, rows: Iterable[int] = ()):
        self.rows: Dict[int, int] = {}
        for row in rows:
            self.add(row)

    def copy(self) -> "GF2Basis":
        other = GF2Basis()
        other.rows = dict(self.rows)
        return other

    def reduce(self, v: int) -> int:
        while v:
            p = v.bit_length() - 1
            row = self.rows.get(p)
            if row is None:
                break
            v ^= row
        return v

    def add(self, v: int) -> bool:
        v = self.reduce(v)
        if not v:
            return False
        self.rows[v.bit_length() - 1] = v
        return True

    def contains(self, v: int) -> bool:
        return self.reduce(v) == 0


def rref_rows(rows: Sequence[int]) -> Dict[int, int]:
    basis = GF2Basis(rows)
    pivots = sorted(basis.rows, reverse=True)
    rref = dict(basis.rows)
    for p in pivots:
        row = rref[p]
        for q in pivots:
            if q != p and ((rref[q] >> p) & 1):
                rref[q] ^= row
    return rref


def nullspace_basis(check_rows: Sequence[int], n: int) -> List[int]:
    rref = rref_rows(check_rows)
    pivot_cols = set(rref)
    out = []
    for free in range(n):
        if free in pivot_cols:
            continue
        v = 1 << free
        for p, row in rref.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def commutes(v: int, checks: Sequence[int]) -> bool:
    return all(((v & row).bit_count() & 1) == 0 for row in checks)


def logical_representatives(kernel: Sequence[int], stabilizers: Sequence[int]) -> List[int]:
    stab = GF2Basis(stabilizers)
    span = stab.copy()
    reps = []
    for v in sorted(kernel, key=lambda x: (x.bit_count(), x)):
        r = span.reduce(v)
        if r:
            span.add(r)
            if not stab.contains(r):
                reps.append(r)
    return reps


def vector_to_list(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def random_sum(rng: random.Random, rows: Sequence[int], max_terms: int) -> int:
    if not rows:
        return 0
    terms = rng.randint(1, min(max_terms, len(rows)))
    v = 0
    for i in rng.sample(range(len(rows)), terms):
        v ^= rows[i]
    return v


def polish_with_stabilizers(rng: random.Random, v: int, stabilizers: Sequence[int], passes: int) -> int:
    nonzero = [s for s in stabilizers if s]
    if not nonzero:
        return v
    current = v
    current_w = current.bit_count()
    for _ in range(passes):
        improved = False
        order = list(range(len(nonzero)))
        rng.shuffle(order)
        for idx in order:
            candidate = current ^ nonzero[idx]
            w = candidate.bit_count()
            if w < current_w or (w == current_w and rng.random() < 0.03):
                current = candidate
                current_w = w
                improved = True
        if not improved:
            break
    return current


def search_basis(
    rng: random.Random,
    name: str,
    kernel_checks: Sequence[int],
    stabilizers: Sequence[int],
    n: int,
) -> Optional[Tuple[str, int]]:
    kernel = nullspace_basis(kernel_checks, n)
    reps = logical_representatives(kernel, stabilizers)
    if not reps:
        return None

    stab_basis = GF2Basis(stabilizers)
    best = None
    logical_dim = len(reps)
    iterations = max(300, min(8000, 250 * max(1, logical_dim) + 20 * len(stabilizers)))
    max_terms = min(10, max(1, logical_dim))

    starts = list(reps)
    for _ in range(iterations):
        v = random_sum(rng, reps, max_terms)
        if rng.random() < 0.35:
            v ^= random_sum(rng, stabilizers, min(12, max(1, len(stabilizers))))
        starts.append(v)

    for v in starts:
        if not v:
            continue
        v = polish_with_stabilizers(rng, v, stabilizers, passes=3)
        if v and commutes(v, kernel_checks) and not stab_basis.contains(v):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    if best is None:
        return None
    return name, best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        n = nx
        rng = random.Random(args.seed)

        # X logicals commute with Hz and are nontrivial modulo rows of Hx.
        # Z logicals commute with Hx and are nontrivial modulo rows of Hz.
        results = [
            search_basis(rng, "x", hz, hx, n),
            search_basis(rng, "z", hx, hz, n),
        ]
        results = [r for r in results if r is not None]
        if not results:
            emit("not_found", None, None, None)
            return

        basis, vec = min(results, key=lambda item: (item[1].bit_count(), 0 if item[0] == "x" else 1))
        emit("completed", basis, vector_to_list(vec, n), vec.bit_count())
    except Exception:
        emit("error", None, None, None)


if __name__ == "__main__":
    main()
