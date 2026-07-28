#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    rows = []
    n = None

    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", len(data[0]) if data else 0))
        for row in data:
            bits = 0
            for i, val in enumerate(row):
                if int(val) & 1:
                    bits |= 1 << i
            rows.append(bits)
    elif isinstance(obj, dict) and "rows" in obj:
        data = obj.get("rows") or []
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = 1 + max((max(r) for r in data if r), default=-1)
        for row in data:
            bits = 0
            for c in row:
                c = int(c)
                if c >= 0:
                    bits |= 1 << c
            rows.append(bits)
    elif isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        for row in obj:
            bits = 0
            for i, val in enumerate(row):
                if int(val) & 1:
                    bits |= 1 << i
            rows.append(bits)
    else:
        raise ValueError("unsupported matrix JSON format")

    mask = (1 << n) - 1 if n > 0 else 0
    return [r & mask for r in rows], n


def rref(rows, n):
    a = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        bit = 1 << col
        pivot = None
        for i in range(rank, len(a)):
            if a[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        prow = a[rank]
        for i in range(len(a)):
            if i != rank and (a[i] & bit):
                a[i] ^= prow
        pivots.append(col)
        rank += 1
        if rank == len(a):
            break
    return a[:rank], pivots


def in_rowspace(v, basis_rows, pivots):
    x = v
    for row, p in zip(basis_rows, pivots):
        if x & (1 << p):
            x ^= row
    return x == 0


def nullspace_basis(rows, n):
    rr, piv = rref(rows, n)
    pivot_set = set(piv)
    out = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, p in zip(rr, piv):
            if row & (1 << free):
                v |= 1 << p
        out.append(v)
    return out


def quotient_logicals(kernel, stab_rows, stab_pivots, n, limit=256):
    logicals = []
    span_rows = list(stab_rows)
    span_rr, span_piv = rref(span_rows, n)
    for v in kernel:
        if not in_rowspace(v, span_rr, span_piv):
            logicals.append(v)
            span_rows.append(v)
            span_rr, span_piv = rref(span_rows, n)
            if len(logicals) >= limit:
                break
    return logicals


def bit_positions(x):
    while x:
        lsb = x & -x
        yield lsb.bit_length() - 1
        x ^= lsb


def weighted_sample(items, weights, k, rng):
    if k <= 0 or not items:
        return []
    k = min(k, len(items))
    pool = list(items)
    w = [max(1.0e-9, float(weights[i])) for i in pool]
    chosen = []
    for _ in range(k):
        total = sum(w)
        t = rng.random() * total
        acc = 0.0
        idx = 0
        for j, val in enumerate(w):
            acc += val
            if acc >= t:
                idx = j
                break
        chosen.append(pool.pop(idx))
        w.pop(idx)
    return chosen


def solve_sampled_columns(stab_basis, cols, target, nvars, rng):
    if not cols:
        return 0
    eqs = []
    rhs_bit = 1 << nvars
    for c in cols:
        mask = 0
        cb = 1 << c
        for j, row in enumerate(stab_basis):
            if row & cb:
                mask |= 1 << j
        b = rhs_bit if (target & cb) else 0
        eqs.append(mask | b)

    rank = 0
    pivots = []
    for col in range(nvars):
        bit = 1 << col
        pivot = None
        for i in range(rank, len(eqs)):
            if eqs[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        eqs[rank], eqs[pivot] = eqs[pivot], eqs[rank]
        prow = eqs[rank]
        for i in range(len(eqs)):
            if i != rank and (eqs[i] & bit):
                eqs[i] ^= prow
        pivots.append(col)
        rank += 1

    var_mask = (1 << nvars) - 1
    for row in eqs[rank:]:
        if (row & var_mask) == 0 and (row & rhs_bit):
            return None

    pivot_set = set(pivots)
    sol = 0
    for j in range(nvars):
        if j not in pivot_set and rng.random() < 0.18:
            sol |= 1 << j
    for row, p in reversed(list(zip(eqs[:rank], pivots))):
        parity = ((row & var_mask & ~(1 << p) & sol).bit_count() & 1)
        rhs = 1 if (row & rhs_bit) else 0
        if parity ^ rhs:
            sol |= 1 << p
        else:
            sol &= ~(1 << p)
    return sol


def combine_rows(rows, coeffs):
    out = 0
    c = coeffs
    while c:
        lsb = c & -c
        out ^= rows[lsb.bit_length() - 1]
        c ^= lsb
    return out


def descent(v, stab_basis, rng, max_passes=5):
    best = v
    bw = best.bit_count()
    if not stab_basis:
        return best
    order = list(range(len(stab_basis)))
    for _ in range(max_passes):
        changed = False
        rng.shuffle(order)
        for i in order:
            cand = best ^ stab_basis[i]
            cw = cand.bit_count()
            if cw < bw or (cw == bw and rng.random() < 0.02):
                best, bw = cand, cw
                changed = True
        if not changed:
            break
    return best


def verified(v, kernel_rows, stab_rows, stab_piv):
    if v == 0:
        return False
    for row in kernel_rows:
        if (row & v).bit_count() & 1:
            return False
    return not in_rowspace(v, stab_rows, stab_piv)


def make_seed(logicals, rng):
    if not logicals:
        return 0
    if len(logicals) == 1:
        return logicals[0]
    v = 0
    while v == 0:
        for g in logicals:
            if rng.random() < 0.35:
                v ^= g
    return v


def search_side(name, kernel_check, stabilizers, n, rng, deadline):
    stab_rr, stab_piv = rref(stabilizers, n)
    kernel = nullspace_basis(kernel_check, n)
    logicals = quotient_logicals(kernel, stab_rr, stab_piv, n)
    if not logicals:
        return None

    col_degree = [0] * n
    for row in stab_rr + kernel_check:
        for c in bit_positions(row):
            if c < n:
                col_degree[c] += 1
    bias = [1.0 + 0.15 * col_degree[i] for i in range(n)]

    seeds = []
    for g in logicals[: min(len(logicals), 64)]:
        seeds.append(g)
    for _ in range(min(96, 4 * len(logicals) + 16)):
        seeds.append(make_seed(logicals, rng))

    best = None
    for s in seeds:
        cand = descent(s, stab_rr, rng, 4)
        if verified(cand, kernel_check, stab_rr, stab_piv):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand
                for c in bit_positions(cand):
                    bias[c] *= 1.08

    if best is None:
        for g in logicals:
            if verified(g, kernel_check, stab_rr, stab_piv):
                best = g
                break
    if best is None:
        return None

    r = len(stab_rr)
    if r == 0:
        return name, best

    scale = max(1, n + r)
    max_iter = max(160, min(2600, 160000 // scale))
    it = 0
    stale = 0
    while it < max_iter and time.time() < deadline:
        it += 1
        base = seeds[it % len(seeds)] if rng.random() < 0.55 else make_seed(logicals, rng)
        if rng.random() < 0.35:
            base ^= best
            if base == 0:
                base = make_seed(logicals, rng)

        ones = list(bit_positions(base if rng.random() < 0.7 else best))
        if not ones:
            continue
        cap = min(len(ones), r, max(4, int(0.38 * n)))
        lo = 1 if cap < 4 else max(2, cap // 5)
        k = rng.randint(lo, cap)
        weights = [bias[i] * (1.7 if (best & (1 << i)) else 1.0) for i in range(n)]
        cols = weighted_sample(ones, weights, k, rng)
        coeffs = solve_sampled_columns(stab_rr, cols, base, r, rng)
        if coeffs is None:
            stale += 1
            for c in cols:
                bias[c] *= 0.995
            continue

        cand = base ^ combine_rows(stab_rr, coeffs)
        cand = descent(cand, stab_rr, rng, 3 + (1 if stale > 30 else 0))
        if verified(cand, kernel_check, stab_rr, stab_piv):
            cw = cand.bit_count()
            bw = best.bit_count()
            if cw < bw:
                best = cand
                stale = 0
                for c in range(n):
                    if cand & (1 << c):
                        bias[c] = min(50.0, bias[c] * 1.12)
                    else:
                        bias[c] = max(0.2, bias[c] * 0.997)
            else:
                stale += 1
        if stale > 80:
            stale = 0
            for i in range(n):
                bias[i] = 0.85 * bias[i] + 0.15 * (1.0 + 0.15 * col_degree[i])

    return name, best


def vector_list(v, n):
    return [1 if (v & (1 << i)) else 0 for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        if nx != nz:
            hx = [r & ((1 << n) - 1) for r in hx]
            hz = [r & ((1 << n) - 1) for r in hz]

        rng = random.Random(args.seed)
        deadline = time.time() + 7.5

        # X logicals commute with Z checks and are nontrivial modulo X stabilizers.
        sx = search_side("x", hz, hx, n, rng, deadline)
        # Z logicals commute with X checks and are nontrivial modulo Z stabilizers.
        sz = search_side("z", hx, hz, n, rng, deadline)

        choices = [c for c in (sx, sz) if c is not None]
        if choices:
            basis, vec = min(choices, key=lambda t: (t[1].bit_count(), 0 if t[0] == "x" else 1))
            result = {
                "status": "completed",
                "basis": basis,
                "vector": vector_list(vec, n),
                "upper_bound": int(vec.bit_count()),
            }
        else:
            result = {
                "status": "failed",
                "basis": None,
                "vector": [],
                "upper_bound": None,
            }

        os.makedirs(args.output_dir, exist_ok=True)
        print(json.dumps(result, separators=(",", ":")))
    except Exception:
        print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))


if __name__ == "__main__":
    main()
