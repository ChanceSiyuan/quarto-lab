#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "matrix" in obj:
        obj = obj["matrix"]
    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", 0))
        if n <= 0 and data:
            n = len(data[0])
        rows = []
        for row in data:
            mask = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    mask |= 1 << j
            rows.append(mask)
        return rows, n
    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for row in obj.get("rows") or []:
            mask = 0
            for j in row:
                jj = int(j)
                if 0 <= jj < n:
                    mask |= 1 << jj
            rows.append(mask)
        return rows, n
    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        rows = []
        for row in obj:
            mask = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    mask |= 1 << j
            rows.append(mask)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def lowbit_index(x):
    return (x & -x).bit_length() - 1


def rref_low(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = lowbit_index(x)
            if p not in basis:
                break
            x ^= basis[p]
        if not x:
            continue
        p = lowbit_index(x)
        for q, b in list(basis.items()):
            if (b >> p) & 1:
                basis[q] = b ^ x
        basis[p] = x
    return basis


def kernel_basis(rows, n):
    rr = rref_low(rows)
    pivots = set(rr)
    free_cols = [j for j in range(n) if j not in pivots]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in rr.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def build_high_basis(rows):
    basis = {}
    for row in rows:
        add_high_basis(basis, row)
    return basis


def reduce_high(basis, x):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def add_high_basis(basis, row):
    x = reduce_high(basis, row)
    if not x:
        return False
    p = x.bit_length() - 1
    basis[p] = x
    return True


def in_rowspace(row_basis, v):
    return reduce_high(row_basis, v) == 0


def syndrome_zero(check_rows, v):
    for row in check_rows:
        if ((row & v).bit_count() & 1) != 0:
            return False
    return True


def verified(check_rows, stab_basis, v):
    return v != 0 and syndrome_zero(check_rows, v) and not in_rowspace(stab_basis, v)


def quotient_generators(check_rows, stab_rows, n):
    kbas = kernel_basis(check_rows, n)
    span = build_high_basis(stab_rows)
    gens = []
    for v in kbas:
        if reduce_high(span, v):
            gens.append(v)
            add_high_basis(span, v)
    return gens


def masks_to_adjacency(rows, n):
    checks = []
    var_checks = [[] for _ in range(n)]
    for ci, row in enumerate(rows):
        cols = []
        x = row
        while x:
            lb = x & -x
            j = lb.bit_length() - 1
            cols.append(j)
            var_checks[j].append(ci)
            x ^= lb
        checks.append(cols)
    return checks, var_checks


def bp_zero_reliability(checks, var_checks, n, prior_p, rng, rounds=4):
    prior_p = min(0.45, max(0.02, prior_p))
    base = math.log((1.0 - prior_p) / prior_p)
    v_to_c = {}
    c_to_v = {}
    for j in range(n):
        jitter = rng.uniform(-0.45, 0.45)
        for ci in var_checks[j]:
            v_to_c[(j, ci)] = base + jitter
            c_to_v[(ci, j)] = 0.0
    for _ in range(rounds):
        for ci, cols in enumerate(checks):
            if not cols:
                continue
            absvals = []
            signs = []
            total_sign = 1.0
            min1 = 1e9
            min2 = 1e9
            minpos = -1
            for pos, j in enumerate(cols):
                msg = v_to_c.get((j, ci), base)
                s = -1.0 if msg < 0 else 1.0
                a = abs(msg)
                signs.append(s)
                absvals.append(a)
                total_sign *= s
                if a < min1:
                    min2 = min1
                    min1 = a
                    minpos = pos
                elif a < min2:
                    min2 = a
            for pos, j in enumerate(cols):
                mag = min2 if pos == minpos else min1
                c_to_v[(ci, j)] = 0.82 * total_sign * signs[pos] * mag
        for j in range(n):
            incoming = var_checks[j]
            if not incoming:
                continue
            total = base + rng.uniform(-0.08, 0.08)
            for ci in incoming:
                total += c_to_v.get((ci, j), 0.0)
            for ci in incoming:
                v_to_c[(j, ci)] = total - c_to_v.get((ci, j), 0.0)
    rel = [base] * n
    for j in range(n):
        total = base
        for ci in var_checks[j]:
            total += c_to_v.get((ci, j), 0.0)
        rel[j] = min(8.0, max(0.0, abs(total)))
    return rel


def random_logical_combo(gens, rng):
    if not gens:
        return 0
    v = 0
    # A sparse-to-moderate logical mixture explores quotient directions without
    # turning every restart into the same dense random codeword.
    p = rng.uniform(0.12, 0.55)
    chosen = False
    order = list(range(len(gens)))
    rng.shuffle(order)
    for i in order:
        if rng.random() < p:
            v ^= gens[i]
            chosen = True
    if not chosen:
        v = gens[rng.randrange(len(gens))]
    return v


def weighted_flip_delta(v, row, rel):
    x = row
    delta_w = 0
    delta_r = 0.0
    while x:
        lb = x & -x
        j = lb.bit_length() - 1
        if (v >> j) & 1:
            delta_w -= 1
            delta_r -= 1.0 + rel[j]
        else:
            delta_w += 1
            delta_r += 1.0 + rel[j]
        x ^= lb
    return delta_w, delta_r


def local_reduce(start, check_rows, stab_rows, stab_basis, n, rng, deadline):
    checks, var_checks = masks_to_adjacency(check_rows, n)
    rows = [r for r in stab_rows if r and syndrome_zero(check_rows, r)]
    if not rows:
        return start if verified(check_rows, stab_basis, start) else 0
    v = start
    best = v if verified(check_rows, stab_basis, v) else 0
    best_w = best.bit_count() if best else n + 1
    temp = 1.35
    max_steps = 18 + min(220, 3 * len(rows))
    for step in range(max_steps):
        if time.monotonic() > deadline:
            break
        if step % 5 == 0:
            density = (v.bit_count() + 1.0) / (n + 2.0)
            rel = bp_zero_reliability(checks, var_checks, n, density, rng, rounds=3)
        sample_count = min(len(rows), 24 + int(math.sqrt(len(rows) + 1)))
        sample = rng.sample(rows, sample_count) if sample_count < len(rows) else rows[:]
        scored = []
        for row in sample:
            dw, dr = weighted_flip_delta(v, row, rel)
            scored.append((dw, dr + rng.uniform(-0.35, 0.35), row))
        scored.sort(key=lambda t: (t[0], t[1]))
        moved = False
        for dw, dr, row in scored[: min(10, len(scored))]:
            accept = dw < 0 or dr < -0.25
            if not accept and temp > 0.05:
                accept = rng.random() < math.exp(-max(0.0, dw + 0.18 * dr) / temp)
            if accept:
                v ^= row
                moved = True
                if verified(check_rows, stab_basis, v):
                    w = v.bit_count()
                    if w < best_w:
                        best = v
                        best_w = w
                break
        if not moved:
            row = rng.choice(rows)
            if rng.random() < 0.25:
                v ^= row
        temp *= 0.965
    return best


def search_basis(name, check_rows, stab_rows, n, seed, deadline):
    rng = random.Random(seed)
    stab_basis = build_high_basis(stab_rows)
    gens = quotient_generators(check_rows, stab_rows, n)
    best = 0
    best_w = n + 1
    for g in gens:
        if verified(check_rows, stab_basis, g):
            w = g.bit_count()
            if w < best_w:
                best, best_w = g, w
    if not best:
        return None
    restarts = 12 + min(72, 2 * len(gens) + int(math.sqrt(max(1, n)) * 3))
    # Try individual quotient directions first, then reliability-randomized
    # restarts with stabilizer scrambling and local row-flip descent.
    seeds = gens[: min(len(gens), 24)]
    while len(seeds) < restarts:
        seeds.append(random_logical_combo(gens, rng))
    good_stabs = [r for r in stab_rows if r and syndrome_zero(check_rows, r)]
    for base in seeds:
        if time.monotonic() > deadline:
            break
        v = base
        if good_stabs:
            p = rng.uniform(0.02, 0.22)
            for row in rng.sample(good_stabs, min(len(good_stabs), 80)):
                if rng.random() < p:
                    v ^= row
        cand = local_reduce(v, check_rows, stab_rows, stab_basis, n, rng, deadline)
        if cand and verified(check_rows, stab_basis, cand):
            w = cand.bit_count()
            if w < best_w:
                best, best_w = cand, w
    if not verified(check_rows, stab_basis, best):
        return None
    return {"basis": name, "vector": int_to_bits(best, n), "upper_bound": best.bit_count()}


def int_to_bits(v, n):
    return [(v >> j) & 1 for j in range(n)]


def failure():
    return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1) for r in hx]
    hz = [r & ((1 << n) - 1) for r in hz]
    start = time.monotonic()
    soft = 6.0 + min(10.0, n / 180.0)
    deadline = start + soft
    results = []
    rz = search_basis("z", hx, hz, n, args.seed ^ 0x5A17, deadline)
    if rz:
        results.append(rz)
    rx = search_basis("x", hz, hx, n, args.seed ^ 0xC0DE, deadline)
    if rx:
        results.append(rx)
    if results:
        ans = min(results, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "z" else 1))
        ans = {"status": "completed", **ans}
    else:
        ans = failure()
    print(json.dumps(ans, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps(failure(), separators=(",", ":")))
