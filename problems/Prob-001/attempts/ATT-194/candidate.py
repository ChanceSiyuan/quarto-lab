#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    rows: List[int] = []
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        for row in obj["data"]:
            bits = 0
            for j, val in enumerate(row):
                if int(val) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        for row in obj["rows"]:
            bits = 0
            last = -1
            for j in row:
                j = int(j)
                if j <= last:
                    raise ValueError("sparse row indices must be strictly increasing")
                if j < 0 or j >= n:
                    raise ValueError("sparse row index out of range")
                bits |= 1 << j
                last = j
            rows.append(bits)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def parity(x: int) -> int:
    return x.bit_count() & 1


class RowSpace:
    def __init__(self, rows: Iterable[int]):
        self.basis = {}
        for row in rows:
            self.add(row)

    def add(self, row: int) -> None:
        x = row
        while x:
            p = x.bit_length() - 1
            b = self.basis.get(p)
            if b is None:
                self.basis[p] = x
                return
            x ^= b

    def reduce(self, row: int) -> int:
        x = row
        while x:
            p = x.bit_length() - 1
            b = self.basis.get(p)
            if b is None:
                return x
            x ^= b
        return 0

    def contains(self, row: int) -> bool:
        return self.reduce(row) == 0


def rref_rows(rows: Sequence[int]) -> Tuple[List[Tuple[int, int]], List[int]]:
    work = [r for r in rows if r]
    pivots: List[int] = []
    pivot_rows: List[int] = []
    while work:
        pivot_idx = max(range(len(work)), key=lambda i: work[i].bit_length())
        row = work.pop(pivot_idx)
        p = row.bit_length() - 1
        for i, existing in enumerate(pivot_rows):
            if (existing >> p) & 1:
                pivot_rows[i] = existing ^ row
        new_work = []
        for other in work:
            if (other >> p) & 1:
                other ^= row
            if other:
                new_work.append(other)
        work = new_work
        pivots.append(p)
        pivot_rows.append(row)
    ordered = sorted(zip(pivots, pivot_rows))
    return ordered, [p for p, _ in ordered]


def nullspace_basis(rows: Sequence[int], n: int) -> List[int]:
    ordered, pivots = rref_rows(rows)
    pivot_set = set(pivots)
    by_pivot = {p: row for p, row in ordered}
    basis: List[int] = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for p in pivots:
            if (by_pivot[p] >> free) & 1:
                v |= 1 << p
        basis.append(v)
    return basis


def in_kernel(v: int, checks: Sequence[int]) -> bool:
    return all(parity(v & row) == 0 for row in checks)


def to_binary_list(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def combine_random(ns: Sequence[int], rng: random.Random, p: float) -> int:
    if not ns:
        return 0
    v = 0
    if p >= 0.49:
        for b in ns:
            if rng.random() < p:
                v ^= b
    else:
        count = max(1, int(round(len(ns) * p)))
        count = min(len(ns), count + rng.randrange(max(1, count + 1)))
        for i in rng.sample(range(len(ns)), count):
            v ^= ns[i]
    if v == 0:
        v = rng.choice(ns)
    return v


def greedy_reduce(v: int, stabilizers: Sequence[int], rng: random.Random, rounds: int) -> int:
    best = v
    best_w = v.bit_count()
    rows = [r for r in stabilizers if r]
    if not rows:
        return best

    for _ in range(rounds):
        order = rows[:]
        rng.shuffle(order)
        improved = False
        for row in order:
            cand = best ^ row
            w = cand.bit_count()
            if w < best_w or (w == best_w and rng.random() < 0.015):
                best = cand
                best_w = w
                improved = True
        if not improved:
            break
    return best


def anneal_reduce(v: int, stabilizers: Sequence[int], rng: random.Random, steps: int) -> int:
    rows = [r for r in stabilizers if r]
    if not rows:
        return v
    cur = v
    cur_w = v.bit_count()
    best = cur
    best_w = cur_w
    temp0 = max(1.0, cur_w / 8.0)
    for t in range(max(1, steps)):
        row = rng.choice(rows)
        cand = cur ^ row
        w = cand.bit_count()
        delta = w - cur_w
        temp = temp0 * (1.0 - (t / max(1, steps))) + 0.05
        if delta <= 0 or rng.random() < pow(2.718281828, -delta / temp):
            cur, cur_w = cand, w
            if cur_w < best_w:
                best, best_w = cur, cur_w
    return greedy_reduce(best, rows, rng, 3)


def search_basis(
    name: str,
    checks: Sequence[int],
    stabilizers: Sequence[int],
    n: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    ns = nullspace_basis(checks, n)
    if not ns:
        return None

    rowspace = RowSpace(stabilizers)
    valid_stabilizers = [r for r in stabilizers if in_kernel(r, checks)]
    best: Optional[int] = None
    best_w = n + 1

    def consider(v: int) -> None:
        nonlocal best, best_w
        if v == 0:
            return
        v = greedy_reduce(v, valid_stabilizers, rng, 5)
        if valid_stabilizers and rng.random() < 0.45:
            v = anneal_reduce(v, valid_stabilizers, rng, 80 + 4 * len(valid_stabilizers))
        if v and in_kernel(v, checks) and not rowspace.contains(v):
            w = v.bit_count()
            if w < best_w:
                best = v
                best_w = w

    # Individual nullspace generators often expose sparse logicals directly.
    shuffled = ns[:]
    rng.shuffle(shuffled)
    for b in shuffled[: min(len(shuffled), 96)]:
        consider(b)

    trials = 260 + min(420, 8 * len(ns) + 3 * len(valid_stabilizers))
    probs = [0.5, 0.33, 0.2, 0.125, 0.075, 0.04]
    for _ in range(trials):
        p = rng.choice(probs)
        consider(combine_random(ns, rng, p))

    if best is None:
        return None
    return name, best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)

        candidates = [
            search_basis("x", hz, hx, n, rng),
            search_basis("z", hx, hz, n, rng),
        ]
        candidates = [c for c in candidates if c is not None]

        if candidates:
            basis, vector = min(candidates, key=lambda item: item[1].bit_count())
            result = {
                "status": "completed",
                "basis": basis,
                "vector": to_binary_list(vector, n),
                "upper_bound": int(vector.bit_count()),
            }
        else:
            result = {
                "status": "not_found",
                "basis": "x",
                "vector": [0 for _ in range(n)],
                "upper_bound": None,
            }
    except Exception:
        result = {
            "status": "error",
            "basis": "x",
            "vector": [],
            "upper_bound": None,
        }

    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
