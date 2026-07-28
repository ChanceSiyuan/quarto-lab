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

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for j, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", obj.get("num_cols", max((len(r) for r in data), default=0))))
        rows = []
        for r in data:
            x = 0
            for j, v in enumerate(r):
                if j < n and (int(v) & 1):
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            x = 0
            for j in r:
                jj = int(j)
                if 0 <= jj < n:
                    x |= 1 << jj
            rows.append(x)
        return rows, n

    raise ValueError("unrecognized matrix format")


def pivot_index(x):
    return x.bit_length() - 1


def reduce_by_basis(x, basis):
    for p in sorted(basis, reverse=True):
        if (x >> p) & 1:
            x ^= basis[p]
    return x


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = reduce_by_basis(row, basis)
        if x:
            p = pivot_index(x)
            for q, y in list(basis.items()):
                if (y >> p) & 1:
                    basis[q] = y ^ x
            basis[p] = x
    return basis


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    rb = rref_basis(rows)
    pivots = set(rb)
    free_cols = [j for j in range(n) if j not in pivots]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def mat_vec_zero(rows, v):
    return all(((r & v).bit_count() & 1) == 0 for r in rows)


def css_commutes(a_rows, b_rows):
    for a in a_rows:
        for b in b_rows:
            if (a & b).bit_count() & 1:
                return False
    return True


def vector_list(v, n):
    return [(v >> j) & 1 for j in range(n)]


def luby(i):
    # 1-indexed Luby restart sequence: 1,1,2,1,1,2,4,...
    k = 1
    while (1 << k) - 1 < i:
        k += 1
    if i == (1 << k) - 1:
        return 1 << (k - 1)
    return luby(i - (1 << (k - 1)) + 1)


def quotient_logicals(check_rows, stab_rows, n):
    stab_basis = rref_basis(stab_rows)
    q_basis = {}
    reps = []
    for v in nullspace_basis(check_rows, n):
        r = reduce_by_basis(v, stab_basis)
        if r and reduce_by_basis(r, q_basis):
            rr = reduce_by_basis(r, q_basis)
            p = pivot_index(rr)
            for q, y in list(q_basis.items()):
                if (y >> p) & 1:
                    q_basis[q] = y ^ rr
            q_basis[p] = rr
            reps.append(r)
    return reps, stab_basis


def verify_witness(v, basis_name, hx, hz, hx_basis, hz_basis, n):
    if v == 0 or (v >> n):
        return False
    if basis_name == "x":
        return mat_vec_zero(hz, v) and not in_rowspace(v, hx_basis)
    return mat_vec_zero(hx, v) and not in_rowspace(v, hz_basis)


def greedy_descent(v, stab_rows, rng, budget, best_limit=None):
    if not stab_rows:
        return v
    cur = v
    cur_w = cur.bit_count()
    rows = stab_rows[:]
    passes = max(1, budget)
    stale = 0
    for _ in range(passes):
        rng.shuffle(rows)
        improved = False
        # The cutoff keeps long restarts useful without spending all time on
        # huge stabilizer sets where no single-row move helps.
        scan = rows if len(rows) <= 2048 else rows[:2048]
        for s in scan:
            cand = cur ^ s
            w = cand.bit_count()
            if w < cur_w:
                cur, cur_w = cand, w
                improved = True
                if best_limit is not None and cur_w <= best_limit:
                    return cur
        if not improved:
            stale += 1
            if stale >= 2:
                break
        else:
            stale = 0
    return cur


def random_combo(reps, rng):
    if len(reps) == 1:
        return reps[0]
    order = list(range(len(reps)))
    rng.shuffle(order)
    # Heavy-tailed combination size: many small combinations, occasional broad
    # quotient jumps.
    size = 1 + min(len(reps) - 1, int(rng.paretovariate(1.35)))
    v = 0
    for idx in order[:size]:
        v ^= reps[idx]
    if v == 0:
        v = reps[order[0]]
    return v


def search_side(name, check_rows, stab_rows, n, rng, deadline):
    reps, stab_basis = quotient_logicals(check_rows, stab_rows, n)
    if not reps:
        return None, stab_basis

    # Basis-derived fallback: guaranteed logical if the quotient is nonempty.
    best = min(reps, key=lambda x: (x.bit_count(), x))
    best = greedy_descent(best, stab_rows, rng, 3)
    best_w = best.bit_count()
    if best_w <= 1:
        return best, stab_basis

    reps = sorted(set(reps), key=lambda x: (x.bit_count(), x))
    restart = 1
    while best_w > 1 and time.monotonic() < deadline:
        budget = luby(restart)
        restart += 1
        seed = random_combo(reps[: min(len(reps), 96)], rng)

        # Occasionally perturb by a stabilizer before descent; this samples
        # different points of the same logical coset without changing validity.
        if stab_rows and rng.random() < 0.45:
            for _ in range(1 + int(rng.paretovariate(1.6))):
                seed ^= stab_rows[rng.randrange(len(stab_rows))]

        cand = greedy_descent(seed, stab_rows, rng, budget, best_w - 1)
        w = cand.bit_count()
        if 0 < w < best_w:
            best, best_w = cand, w

        # Rare quotient crossover restart, distinct from stabilizer-only walks.
        if len(reps) > 1 and rng.random() < 0.2:
            a = reps[rng.randrange(min(len(reps), 96))]
            b = reps[rng.randrange(min(len(reps), 96))]
            cand = greedy_descent(a ^ b if a != b else a, stab_rows, rng, budget)
            w = cand.bit_count()
            if 0 < w < best_w:
                best, best_w = cand, w

    return best, stab_basis


def solve(hx, hz, n, seed):
    rng = random.Random(seed)
    hx_basis = rref_basis(hx)
    hz_basis = rref_basis(hz)

    if not css_commutes(hx, hz):
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    # Keep runtime predictable for campaign launchers. Linear algebra dominates
    # small instances; randomized search receives fixed per-basis slices.
    candidates = []

    x, _ = search_side("x", hz, hx, n, rng, time.monotonic() + 3.5)
    if x is not None and verify_witness(x, "x", hx, hz, hx_basis, hz_basis, n):
        candidates.append(("x", x))

    z, _ = search_side("z", hx, hz, n, rng, time.monotonic() + 3.5)
    if z is not None and verify_witness(z, "z", hx, hz, hx_basis, hz_basis, n):
        candidates.append(("z", z))

    if not candidates:
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    basis_name, v = min(candidates, key=lambda t: (t[1].bit_count(), t[0], t[1]))
    return {
        "status": "completed",
        "basis": basis_name,
        "vector": vector_list(v, n),
        "upper_bound": int(v.bit_count()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
        result = solve(hx, hz, n, args.seed)
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
