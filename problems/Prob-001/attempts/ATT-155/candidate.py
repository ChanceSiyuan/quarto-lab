#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_rows = int(obj["n_rows"])
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            for j, val in enumerate(row):
                if val & 1:
                    bits |= 1 << j
            rows.append(bits)
        if len(rows) != n_rows:
            raise ValueError("dense matrix row count mismatch")
        return n_cols, rows

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for j in row:
                j = int(j)
                if j <= last or j < 0 or j >= n_cols:
                    raise ValueError("invalid sparse row")
                bits |= 1 << j
                last = j
            rows.append(bits)
        return n_cols, rows

    raise ValueError("unsupported matrix JSON format")


def popcount(x):
    return x.bit_count()


def bit_positions(x):
    while x:
        low = x & -x
        yield low.bit_length() - 1
        x ^= low


class XorBasis:
    def __init__(self, rows=()):
        self.pivots = {}
        for row in rows:
            self.add(row)

    def reduce(self, x):
        while x:
            p = x.bit_length() - 1
            row = self.pivots.get(p)
            if row is None:
                return x
            x ^= row
        return 0

    def contains(self, x):
        return self.reduce(x) == 0

    def add(self, x):
        x = self.reduce(x)
        if not x:
            return False
        self.pivots[x.bit_length() - 1] = x
        return True

    def rows(self):
        return list(self.pivots.values())


def rref_pivots(rows):
    basis = XorBasis(rows)
    pivots = dict(basis.pivots)
    for p in sorted(pivots):
        row = pivots[p]
        for q in list(pivots):
            if q != p and ((pivots[q] >> p) & 1):
                pivots[q] ^= row
    return pivots


def nullspace_basis(check_rows, n_cols):
    pivots = rref_pivots(check_rows)
    pivot_cols = set(pivots)
    free_cols = [j for j in range(n_cols) if j not in pivot_cols]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in pivots.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(rows, v):
    for row in rows:
        if popcount(row & v) & 1:
            return False
    return True


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def randomized_stabilizer_descent(v, stabilizers, rng, rounds):
    best = v
    best_w = popcount(v)
    if not stabilizers:
        return best

    current = v
    current_w = best_w
    rows = list(stabilizers)
    for _ in range(rounds):
        rng.shuffle(rows)
        improved = False
        for row in rows:
            cand = current ^ row
            w = popcount(cand)
            if w < current_w or (w == current_w and rng.random() < 0.03):
                current = cand
                current_w = w
                improved = True
                if w < best_w:
                    best = cand
                    best_w = w
        if not improved:
            if rng.random() < 0.35:
                current = best
                current_w = best_w
            else:
                row = rows[rng.randrange(len(rows))]
                current ^= row
                current_w = popcount(current)
    return best


def sparse_cluster_seed(check_rows, stabilizer_basis, n_cols, rng):
    col_to_checks = [[] for _ in range(n_cols)]
    for r, row in enumerate(check_rows):
        for c in bit_positions(row):
            col_to_checks[c].append(r)

    target = max(1, min(n_cols, 8 + int(n_cols ** 0.5)))
    start = rng.randrange(n_cols)
    support = {start}
    frontier = [start]
    for _ in range(target * 4):
        if not frontier:
            frontier = list(support)
        c = frontier.pop(rng.randrange(len(frontier)))
        neigh = set()
        for r in col_to_checks[c]:
            neigh.update(bit_positions(check_rows[r]))
        neigh.difference_update(support)
        if not neigh:
            continue
        nxt = rng.choice(tuple(neigh))
        support.add(nxt)
        frontier.append(nxt)
        if len(support) >= target:
            break

    v = 0
    for c in support:
        v |= 1 << c
    return v if v and not stabilizer_basis.contains(v) else 0


def logical_seeds(kernel_rows, stabilizer_rows, n_cols, rng):
    ns = nullspace_basis(kernel_rows, n_cols)
    rng.shuffle(ns)
    span = XorBasis(stabilizer_rows)
    seeds = []
    for v in ns:
        if span.add(v):
            seeds.append(v)
    return seeds


def search_side(name, kernel_rows, stabilizer_rows, n_cols, rng):
    stabilizer_basis = XorBasis(stabilizer_rows)
    seeds = logical_seeds(kernel_rows, stabilizer_rows, n_cols, rng)
    if not seeds:
        return None

    candidates = []
    candidates.extend(seeds)

    trials = max(300, 30 * len(seeds), 6 * n_cols)
    for _ in range(trials):
        v = 0
        # Biased random logical combination: usually small, sometimes broad.
        if rng.random() < 0.75:
            take = 1 + rng.randrange(min(4, len(seeds)))
            for s in rng.sample(seeds, take):
                v ^= s
        else:
            for s in seeds:
                if rng.random() < 0.5:
                    v ^= s
        if v:
            candidates.append(v)

        cluster = sparse_cluster_seed(kernel_rows, stabilizer_basis, n_cols, rng)
        if cluster:
            # Use the local cluster as a bias for choosing logical cosets while
            # keeping every trial inside the kernel generated by the seeds.
            ranked = sorted(seeds, key=lambda s: popcount(s & cluster), reverse=True)
            pool = ranked[: max(1, min(len(ranked), 8))]
            v = 0
            for s in rng.sample(pool, 1 + rng.randrange(min(3, len(pool)))):
                v ^= s
            candidates.append(v)

    best = None
    best_w = n_cols + 1
    descent_rounds = max(20, min(240, 8 * len(stabilizer_rows) + 20))
    for v in candidates:
        if not syndrome_zero(kernel_rows, v) or stabilizer_basis.contains(v):
            continue
        v = randomized_stabilizer_descent(v, stabilizer_rows, rng, descent_rounds)
        if syndrome_zero(kernel_rows, v) and not stabilizer_basis.contains(v):
            w = popcount(v)
            if 0 < w < best_w:
                best = v
                best_w = w

    if best is None:
        return None
    return {"basis": name, "vector": vector_to_list(best, n_cols), "upper_bound": best_w}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    try:
        nx, hx = load_matrix(args.hx)
        nz, hz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        # X logicals commute with Hz and are nontrivial modulo rowspan(Hx).
        # Z logicals commute with Hx and are nontrivial modulo rowspan(Hz).
        sides = [
            ("x", hz, hx),
            ("z", hx, hz),
        ]
        rng.shuffle(sides)
        results = []
        for side in sides:
            found = search_side(side[0], side[1], side[2], nx, rng)
            if found is not None:
                results.append(found)

        if results:
            results.sort(key=lambda r: (r["upper_bound"], r["basis"]))
            result = {"status": "completed", **results[0]}
        else:
            result = {"status": "not_found", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "error", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
