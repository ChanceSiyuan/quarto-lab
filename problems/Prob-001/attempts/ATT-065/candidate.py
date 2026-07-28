#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def load_matrix_arg(value):
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            obj = json.load(f)
    else:
        obj = json.loads(value)
    return parse_matrix(obj)


def parse_matrix(obj):
    if obj is None:
        return [], 0
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << i
            if x:
                rows.append(x)
        return rows, n

    n = int(obj.get("n_cols", obj.get("num_cols", 0)))
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
        n = int(obj.get("n_cols", obj.get("num_cols", n)))
    if "sparse_rows" in obj and isinstance(obj["sparse_rows"], dict):
        obj = obj["sparse_rows"]
        n = int(obj.get("num_cols", obj.get("n_cols", n)))

    if "data" in obj:
        data = obj["data"]
        if not n:
            n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << i
            if x:
                rows.append(x)
        return rows, n

    data = obj.get("rows", [])
    if not n:
        n = 1 + max((c for r in data for c in r), default=-1)
    rows = []
    for r in data:
        x = 0
        for c in r:
            c = int(c)
            if 0 <= c < n:
                x |= 1 << c
        if x:
            rows.append(x)
    return rows, n


def popcount(x):
    return x.bit_count()


def mask_rows(rows, n):
    m = (1 << n) - 1 if n > 0 else 0
    return [r & m for r in rows if r & m]


def dot_parity(a, b):
    return (a & b).bit_count() & 1


def kernel_ok(v, checks):
    return all(dot_parity(v, r) == 0 for r in checks)


def linear_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def in_span(v, basis):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        x ^= b
    return True


def rank(rows):
    return len(linear_basis(rows))


def rref_ordered(rows, n, col_order):
    work = [r for r in rows if r]
    pivots = []
    basis = {}
    rank_rows = []
    for col in col_order:
        hit = None
        for i in range(len(work)):
            if (work[i] >> col) & 1:
                hit = i
                break
        if hit is None:
            continue
        row = work.pop(hit)
        for p in pivots:
            if (row >> p) & 1:
                row ^= basis[p]
        if not ((row >> col) & 1):
            work.append(row)
            continue
        for p in list(pivots):
            if (basis[p] >> col) & 1:
                basis[p] ^= row
        for i in range(len(work)):
            if (work[i] >> col) & 1:
                work[i] ^= row
        basis[col] = row
        pivots.append(col)
        rank_rows.append(row)
    return basis, pivots, rank_rows


def nullspace_ordered(rows, n, col_order):
    rref, pivots, _ = rref_ordered(rows, n, col_order)
    pivot_set = set(pivots)
    free_cols = [c for c in col_order if c not in pivot_set]
    basis = []
    for f in free_cols:
        v = 1 << f
        for p in pivots:
            if (rref[p] >> f) & 1:
                v |= 1 << p
        basis.append(v)
    return basis, free_cols


def add_to_basis_if_independent(row, basis):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def verified(v, checks, stab_basis):
    return v != 0 and kernel_ok(v, checks) and not in_span(v, stab_basis)


def greedy_reduce(v, stabilizers, checks, stab_basis, rng, n, passes=4):
    if not stabilizers:
        return v
    cur = v
    rows = list(stabilizers)
    best_w = popcount(cur)
    for _ in range(passes):
        rng.shuffle(rows)
        changed = False
        for s in rows:
            cand = cur ^ s
            cw = popcount(cand)
            if cw < best_w and verified(cand, checks, stab_basis):
                cur, best_w = cand, cw
                changed = True
        if not changed:
            break
    return cur & ((1 << n) - 1)


def fallback_logical(checks, stabilizers, n, rng):
    ns, _ = nullspace_ordered(checks, n, list(range(n)))
    span = linear_basis(stabilizers)
    trial_basis = dict(span)
    best = None
    reducers = [r for r in stabilizers if r] + list(span.values())
    for v in sorted(ns, key=popcount):
        if add_to_basis_if_independent(v, trial_basis):
            cand = greedy_reduce(v, reducers, checks, span, rng, n, passes=8)
            if verified(cand, checks, span):
                if best is None or popcount(cand) < popcount(best):
                    best = cand
    return best


def column_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        x = r
        while x:
            lsb = x & -x
            deg[lsb.bit_length() - 1] += 1
            x ^= lsb
    return deg


def weighted_column_order(scores, rng):
    # Low keys go early and tend to become pivots; invert scores so preferred
    # physical columns are more often left as free information-set coordinates.
    return sorted(range(len(scores)), key=lambda c: rng.random() * max(1e-9, scores[c]))


def sample_combo(null_basis, free_cols, col_scores, rng, n):
    if not null_basis:
        return 0
    weights = []
    for v, f in zip(null_basis, free_cols):
        w = popcount(v)
        weights.append((col_scores[f] + 0.15) / (1.0 + 0.20 * w))
    avg = sum(weights) / max(1, len(weights))
    mode = rng.random()
    v = 0
    if mode < 0.25:
        i = max(range(len(weights)), key=lambda j: weights[j] * rng.random())
        v = null_basis[i]
    else:
        scale = rng.uniform(0.35, 1.8)
        for b, wt in zip(null_basis, weights):
            p = min(0.65, max(0.015, scale * wt / (avg * len(weights) ** 0.55 + 1e-9)))
            if rng.random() < p:
                v ^= b
        if v == 0:
            v = null_basis[rng.randrange(len(null_basis))]
    return v & ((1 << n) - 1)


def search_basis(label, checks, stabilizers, n, seed, deadline):
    rng = random.Random((seed * 1000003) ^ (17 if label == "x" else 43))
    stab_basis = linear_basis(stabilizers)
    reducers = [r for r in stabilizers if r] + list(stab_basis.values())

    best = fallback_logical(checks, stabilizers, n, rng)
    if best is not None:
        best = greedy_reduce(best, reducers, checks, stab_basis, rng, n, passes=10)

    deg_check = column_degrees(checks, n)
    deg_stab = column_degrees(stabilizers, n)
    col_scores = []
    for c in range(n):
        # Prefer sparse, weakly constrained columns initially; the adaptive
        # updates below then concentrate on supports of good logical witnesses.
        col_scores.append(1.0 / (1.0 + deg_check[c] + 0.35 * deg_stab[c]))

    rounds = 0
    max_rounds = 96 if n <= 256 else 48
    samples_per_round = 80 if n <= 256 else 36
    while rounds < max_rounds and time.time() < deadline:
        order = weighted_column_order(col_scores, rng)
        ns, free_cols = nullspace_ordered(checks, n, order)
        if not ns:
            break
        # Try the lightest few basis-derived candidates for this randomized
        # information set before random combinations.
        probes = sorted(ns, key=popcount)[: min(10, len(ns))]
        for v in probes:
            if time.time() >= deadline:
                break
            cand = greedy_reduce(v, reducers, checks, stab_basis, rng, n, passes=5)
            if verified(cand, checks, stab_basis):
                if best is None or popcount(cand) < popcount(best):
                    best = cand
        for _ in range(samples_per_round):
            if time.time() >= deadline:
                break
            v = sample_combo(ns, free_cols, col_scores, rng, n)
            cand = greedy_reduce(v, reducers, checks, stab_basis, rng, n, passes=4)
            if not verified(cand, checks, stab_basis):
                continue
            cw = popcount(cand)
            if best is None or cw < popcount(best):
                best = cand
                support = set(i for i in range(n) if (cand >> i) & 1)
                for i in range(n):
                    if i in support:
                        col_scores[i] = min(12.0, col_scores[i] * 1.22 + 0.05)
                    else:
                        col_scores[i] = max(0.02, col_scores[i] * 0.992)
            else:
                # Mild reinforcement of columns appearing in any verified
                # witness keeps later information sets near valid logical cosets.
                x = cand
                while x:
                    lsb = x & -x
                    i = lsb.bit_length() - 1
                    col_scores[i] = min(12.0, col_scores[i] * 1.015)
                    x ^= lsb
        rounds += 1
    if best is not None and verified(best, checks, stab_basis):
        return best
    return None


def vector_to_list(v, n):
    return [1 if ((v >> i) & 1) else 0 for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix_arg(args.hx)
        hz, nz = load_matrix_arg(args.hz)
        n = max(nx, nz)
        hx = mask_rows(hx, n)
        hz = mask_rows(hz, n)

        deadline = time.time() + 28.0
        candidates = []
        x = search_basis("x", hz, hx, n, args.seed, deadline)
        if x is not None:
            candidates.append(("x", x, popcount(x)))
        z = search_basis("z", hx, hz, n, args.seed, deadline)
        if z is not None:
            candidates.append(("z", z, popcount(z)))

        if candidates:
            basis, vec, ub = min(candidates, key=lambda t: (t[2], 0 if t[0] == "x" else 1))
            result = {
                "status": "completed",
                "basis": basis,
                "vector": vector_to_list(vec, n),
                "upper_bound": ub,
            }
        else:
            result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
