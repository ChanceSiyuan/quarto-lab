#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def row_weight(x):
    return x.bit_count()


def rows_to_ints_from_dense(data, n_cols):
    rows = []
    if data is None:
        return rows
    if len(data) == 0:
        return rows
    if all(isinstance(r, list) for r in data):
        for r in data:
            v = 0
            for j, bit in enumerate(r[:n_cols]):
                if bit & 1:
                    v |= 1 << j
            rows.append(v)
    else:
        for i in range(0, len(data), n_cols):
            v = 0
            for j, bit in enumerate(data[i:i + n_cols]):
                if bit & 1:
                    v |= 1 << j
            rows.append(v)
    return rows


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        n_cols = int(obj.get("n_cols", obj.get("num_cols", 0)))
        return rows_to_ints_from_dense(obj.get("data", []), n_cols), n_cols

    if isinstance(obj, dict) and "rows" in obj:
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            v = 0
            for j in r:
                jj = int(j)
                if 0 <= jj < n_cols:
                    v |= 1 << jj
            rows.append(v)
        return rows, n_cols

    if isinstance(obj, list):
        n_cols = max((len(r) for r in obj if isinstance(r, list)), default=0)
        return rows_to_ints_from_dense(obj, n_cols), n_cols

    return [], 0


class LinearBasis:
    def __init__(self):
        self.by_pivot = {}

    def copy(self):
        b = LinearBasis()
        b.by_pivot = dict(self.by_pivot)
        return b

    def reduce(self, v):
        while v:
            p = v.bit_length() - 1
            r = self.by_pivot.get(p)
            if r is None:
                break
            v ^= r
        return v

    def contains(self, v):
        return self.reduce(v) == 0

    def insert(self, v):
        v = self.reduce(v)
        if v == 0:
            return False
        p = v.bit_length() - 1
        for q, r in list(self.by_pivot.items()):
            if (r >> p) & 1:
                self.by_pivot[q] = r ^ v
        self.by_pivot[p] = v
        return True

    def rank(self):
        return len(self.by_pivot)


def make_basis(rows):
    b = LinearBasis()
    for r in rows:
        if r:
            b.insert(r)
    return b


def rref_rows(rows, n):
    a = [r & ((1 << n) - 1) for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        pivot = None
        for i in range(rank, len(a)):
            if (a[i] >> col) & 1:
                pivot = i
                break
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        for i in range(len(a)):
            if i != rank and ((a[i] >> col) & 1):
                a[i] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == len(a):
            break
    return a[:rank], pivots


def nullspace_basis(check_rows, n):
    rref, pivots = rref_rows(check_rows, n)
    pivot_set = set(pivots)
    basis = []
    for free_col in range(n):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        for row, pivot_col in zip(rref, pivots):
            if (row >> free_col) & 1:
                v |= 1 << pivot_col
        basis.append(v)
    return basis


def in_kernel(v, check_rows):
    for r in check_rows:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def verified(v, check_rows, stabilizer_basis):
    return v != 0 and in_kernel(v, check_rows) and not stabilizer_basis.contains(v)


def logical_generators(check_rows, stabilizer_rows, n):
    ns = sorted(nullspace_basis(check_rows, n), key=row_weight)
    span = make_basis(stabilizer_rows)
    logicals = []
    for v in ns:
        if v and not span.contains(v):
            logicals.append(v)
            span.insert(v)
    return logicals


def greedy_descent(v, moves):
    improved = True
    while improved:
        improved = False
        current_w = row_weight(v)
        for m in moves:
            u = v ^ m
            uw = row_weight(u)
            if uw < current_w:
                v = u
                current_w = uw
                improved = True
    return v


def walk_minimize(start, stabilizer_rows, rng, rounds):
    moves = [r for r in stabilizer_rows if r]
    if not moves:
        return start

    moves.sort(key=row_weight)
    v = greedy_descent(start, moves)
    best = v
    best_w = row_weight(best)

    hot = max(1, min(len(moves), 64))
    for restart in range(max(2, rounds // 80)):
        if restart:
            v = best
            for _ in range(rng.randint(1, min(6, len(moves)))):
                v ^= rng.choice(moves[:hot])
        temp = 2.5 + 0.25 * restart
        steps = max(20, rounds // max(1, rounds // 80))
        for t in range(steps):
            if rng.random() < 0.18 and len(moves) > 1:
                m = rng.choice(moves) ^ rng.choice(moves[:hot])
                if m == 0:
                    continue
            else:
                m = rng.choice(moves if rng.random() < 0.35 else moves[:hot])
            u = v ^ m
            dw = row_weight(u) - row_weight(v)
            if dw <= 0 or rng.random() < pow(2.718281828, -dw / max(0.2, temp)):
                v = u
                vw = row_weight(v)
                if vw < best_w:
                    best, best_w = v, vw
                    v = greedy_descent(v, moves[:hot])
                    if row_weight(v) < best_w:
                        best, best_w = v, row_weight(v)
            temp *= 0.995
    return greedy_descent(best, moves)


def random_logical_seed(logicals, rng):
    if not logicals:
        return 0
    ordered = sorted(logicals, key=row_weight)
    v = 0
    if rng.random() < 0.70:
        count = 1 + rng.randrange(min(4, len(ordered)))
        pool = ordered[:max(count, min(len(ordered), 12))]
        for g in rng.sample(pool, count):
            v ^= g
    else:
        for g in ordered:
            if rng.random() < min(0.5, 2.0 / max(2, len(ordered))):
                v ^= g
    if v == 0:
        v = rng.choice(ordered)
    return v


def search_side(name, check_rows, stabilizer_rows, n, seed):
    stab_basis = make_basis(stabilizer_rows)
    logicals = logical_generators(check_rows, stabilizer_rows, n)
    if not logicals:
        return None

    rng = random.Random((seed * 1315423911) ^ (17 if name == "x" else 29) ^ n)
    candidates = []
    for g in sorted(logicals, key=row_weight)[:min(len(logicals), 24)]:
        candidates.append(g)
    for i in range(min(24, len(logicals))):
        for j in range(i + 1, min(24, len(logicals))):
            if rng.random() < 0.20:
                candidates.append(logicals[i] ^ logicals[j])

    trials = max(80, min(900, 60 + 18 * len(logicals) + 4 * n))
    for _ in range(trials):
        candidates.append(random_logical_seed(logicals, rng))

    best = None
    best_w = n + 1
    rounds = max(180, min(1600, 140 + 10 * len(stabilizer_rows) + 3 * n))
    for c in candidates:
        if c == 0:
            continue
        v = walk_minimize(c, stabilizer_rows, rng, rounds)
        if verified(v, check_rows, stab_basis):
            w = row_weight(v)
            if w < best_w:
                best, best_w = v, w

    if best is None:
        for g in logicals:
            if verified(g, check_rows, stab_basis):
                best, best_w = g, row_weight(g)
                break

    if best is None:
        return None
    return {"basis": name, "value": best, "weight": best_w}


def int_to_bits(v, n):
    return [int((v >> i) & 1) for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    hx, nx = parse_matrix(args.hx)
    hz, nz = parse_matrix(args.hz)
    n = max(nx, nz)
    mask = (1 << n) - 1 if n > 0 else 0
    hx = [r & mask for r in hx]
    hz = [r & mask for r in hz]

    results = [
        search_side("x", hz, hx, n, args.seed),
        search_side("z", hx, hz, n, args.seed),
    ]
    results = [r for r in results if r is not None]
    if not results:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    else:
        best = min(results, key=lambda r: (r["weight"], 0 if r["basis"] == "x" else 1))
        out = {
            "status": "completed",
            "basis": best["basis"],
            "vector": int_to_bits(best["value"], n),
            "upper_bound": best["weight"],
        }
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
