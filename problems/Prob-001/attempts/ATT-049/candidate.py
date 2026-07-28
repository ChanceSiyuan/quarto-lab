#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", 0))
        rows = []
        if n == 0 and data:
            n = len(data[0])
        for row in data:
            x = 0
            for j, v in enumerate(row):
                if v & 1:
                    x ^= 1 << j
            rows.append(x)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for row in obj.get("rows", []):
            x = 0
            for j in row:
                jj = int(j)
                if 0 <= jj < n:
                    x ^= 1 << jj
            rows.append(x)
        return rows, n

    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        rows = []
        for row in obj:
            x = 0
            for j, v in enumerate(row):
                if v & 1:
                    x ^= 1 << j
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def popcount(x):
    return x.bit_count()


def rref_rows(rows, n, order=None):
    basis = {}
    pivots = []
    if order is None:
        order = list(range(n))
    for row in rows:
        x = row
        while x:
            p = None
            for c in order:
                if (x >> c) & 1:
                    p = c
                    break
            if p is None:
                break
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                pivots.append(p)
                for q, b in list(basis.items()):
                    if q != p and ((b >> p) & 1):
                        basis[q] = b ^ x
                break
    pivots.sort()
    return basis, pivots


def reduce_by_basis(x, basis):
    pivots = sorted(basis.keys(), reverse=True)
    changed = True
    while changed:
        changed = False
        for p in pivots:
            if (x >> p) & 1:
                x ^= basis[p]
                changed = True
    return x


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def syndrome_zero(x, rows):
    for r in rows:
        if popcount(x & r) & 1:
            return False
    return True


def nullspace_basis(rows, n, order=None):
    rbasis, pivots = rref_rows(rows, n, order)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in rbasis.items():
            if (row >> f) & 1:
                v ^= 1 << p
        out.append(v)
    return out


def vec_to_list(x, n):
    return [(x >> i) & 1 for i in range(n)]


def verify(v, check_rows, stab_basis):
    return v != 0 and syndrome_zero(v, check_rows) and not in_rowspace(v, stab_basis)


def column_weights(rows, n):
    w = [0] * n
    for r in rows:
        x = r
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            if j < n:
                w[j] += 1
            x ^= lsb
    return w


def weighted_order(rng, weights):
    keys = []
    for i, w in enumerate(weights):
        # Larger weights are considered earlier by the randomized eliminator.
        keys.append((rng.random() / max(1e-9, w), i))
    keys.sort()
    return [i for _, i in keys]


def reduce_weight_by_rows(v, rows, passes=3):
    best = v
    improved = True
    p = 0
    while improved and p < passes:
        improved = False
        p += 1
        for r in rows:
            y = best ^ r
            if popcount(y) < popcount(best):
                best = y
                improved = True
    return best


def random_combo(rng, gens, col_bias, n, target_terms):
    if not gens:
        return 0
    scores = []
    for g in gens:
        x = g
        s = 0.0
        cnt = 0
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            if j < n:
                s += col_bias[j]
                cnt += 1
            x ^= lsb
        s = s / max(1, cnt)
        # Exponential race; low-score generators are more likely.
        scores.append((rng.expovariate(1.0) * max(0.05, s), g))
    scores.sort(key=lambda t: t[0])
    v = 0
    for _, g in scores[:target_terms]:
        v ^= g
    return v


def search_basis(name, check_rows, stab_rows, n, rng, deadline):
    stab_basis, _ = rref_rows(stab_rows, n)
    _, check_rank_pivots = rref_rows(check_rows, n)
    logical_dim = n - len(check_rank_pivots) - len(stab_basis)
    if logical_dim <= 0:
        return None
    density = column_weights(check_rows + stab_rows, n)
    col_bias = [1.0 + 0.08 * d for d in density]
    best = None
    best_w = n + 1
    seen = set()

    def consider(v):
        nonlocal best, best_w, col_bias
        if v == 0:
            return
        v = reduce_weight_by_rows(v, stab_rows, passes=4)
        if v in seen:
            return
        seen.add(v)
        if verify(v, check_rows, stab_basis):
            w = popcount(v)
            if w < best_w:
                best = v
                best_w = w
                hit = set()
                x = v
                while x:
                    lsb = x & -x
                    hit.add(lsb.bit_length() - 1)
                    x ^= lsb
                for j in range(n):
                    if j in hit:
                        col_bias[j] = max(0.05, col_bias[j] * 0.82)
                    else:
                        col_bias[j] = min(25.0, col_bias[j] * 1.015)

    # Reliable basis-derived fallback from the ordinary nullspace.
    base_null = nullspace_basis(check_rows, n)
    for g in sorted(base_null, key=popcount):
        consider(g)
    if best is not None and best_w <= 2:
        return best

    rounds = 0
    while time.monotonic() < deadline:
        rounds += 1
        inv_bias = [1.0 / max(0.05, b) for b in col_bias]
        order = weighted_order(rng, inv_bias if rounds & 1 else col_bias)
        gens = nullspace_basis(check_rows, n, order)
        if not gens:
            break

        gens.sort(key=lambda g: popcount(g) + 0.015 * rng.random())
        for g in gens[: min(len(gens), 32)]:
            consider(g)

        span = len(gens)
        max_trials = 24 if n > 600 else 48
        for _ in range(max_trials):
            if time.monotonic() >= deadline:
                break
            if span <= 4:
                terms = rng.randint(1, span)
            else:
                terms = 1 + int(rng.expovariate(0.55))
                terms = max(1, min(span, terms))
            v = random_combo(rng, gens, col_bias, n, terms)
            consider(v)

            # Adaptive information-set shake: force a few currently cheap
            # physical columns through their associated kernel generators.
            if rng.random() < 0.35:
                cheap = sorted(range(n), key=lambda j: col_bias[j] + 0.03 * rng.random())[: min(n, 10)]
                u = 0
                for j in cheap:
                    if rng.random() < 0.38:
                        for g in gens:
                            if (g >> j) & 1:
                                u ^= g
                                break
                consider(u)

    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1) for r in hx]
    hz = [r & ((1 << n) - 1) for r in hz]

    os.makedirs(args.output_dir, exist_ok=True)
    deadline = time.monotonic() + 55.0

    candidates = []
    # X logicals commute with Z checks and are nontrivial modulo X stabilizers.
    vx = search_basis("x", hz, hx, n, rng, time.monotonic() + 27.0)
    if vx is not None:
        candidates.append(("x", vx, popcount(vx)))
    remaining = max(3.0, deadline - time.monotonic())
    vz = search_basis("z", hx, hz, n, rng, time.monotonic() + remaining)
    if vz is not None:
        candidates.append(("z", vz, popcount(vz)))

    if candidates:
        basis, v, w = min(candidates, key=lambda t: (t[2], 0 if t[0] == "x" else 1))
        out = {"status": "completed", "basis": basis, "vector": vec_to_list(v, n), "upper_bound": w}
    else:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
