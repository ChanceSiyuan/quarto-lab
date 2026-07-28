#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        return rows_to_ints(data, n), n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        return rows_to_ints(data, n), n
    if "rows" in obj:
        rows = obj["rows"]
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = 1 + max((c for r in rows for c in r), default=-1)
        out = []
        for r in rows:
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    x ^= 1 << c
            out.append(x)
        return out, n
    raise ValueError("unsupported matrix JSON format: %s" % path)


def rows_to_ints(data, n):
    out = []
    for r in data:
        x = 0
        for i, v in enumerate(r[:n]):
            if int(v) & 1:
                x |= 1 << i
        out.append(x)
    return out


def bit_count(x):
    return int(x).bit_count()


def rref_basis(rows):
    piv = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            if p in piv:
                x ^= piv[p]
            else:
                piv[p] = x
                break
    for p in sorted(piv):
        for q in list(piv):
            if q != p and ((piv[q] >> p) & 1):
                piv[q] ^= piv[p]
    return [piv[p] for p in sorted(piv, reverse=True)]


def rank(rows):
    return len(rref_basis(rows))


def reduce_by_basis(x, basis):
    y = int(x)
    for b in basis:
        if y == 0:
            break
        p = b.bit_length() - 1
        if (y >> p) & 1:
            y ^= b
    return y


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    piv = {row.bit_length() - 1: row for row in rref_basis(rows) if row}
    pivot_cols = set(piv)
    basis = []
    for f in range(n):
        if f in pivot_cols:
            continue
        v = 1 << f
        for p, row in piv.items():
            if (row >> f) & 1:
                v |= 1 << p
        basis.append(v)
    return basis


def syndrome_zero(v, checks):
    return all((bit_count(v & r) & 1) == 0 for r in checks)


def vec_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def greedy_stabilizer_descent(v, stabilizers, passes=3):
    cur = int(v)
    if not stabilizers:
        return cur
    rows = sorted(set(stabilizers), key=bit_count)
    improved = True
    p = 0
    while improved and p < passes:
        improved = False
        p += 1
        for s in rows:
            nxt = cur ^ s
            if bit_count(nxt) < bit_count(cur):
                cur = nxt
                improved = True
    return cur


def logical_generators(kernel_rows, stabilizer_rows, n):
    stab_basis = rref_basis(stabilizer_rows)
    ker = nullspace_basis(kernel_rows, n)
    gens = []
    span = list(stab_basis)
    span_rank = len(span)
    for b in sorted(ker, key=bit_count):
        trial = rref_basis(span + [b])
        if len(trial) > span_rank:
            gens.append(b)
            span = trial
            span_rank = len(span)
    return gens, stab_basis


def verified(v, kernel_rows, stabilizer_basis):
    return v != 0 and syndrome_zero(v, kernel_rows) and not in_span(v, stabilizer_basis)


def improve_side(kernel_rows, stabilizer_rows, n, rng, deadline):
    gens, stab_basis = logical_generators(kernel_rows, stabilizer_rows, n)
    if not gens:
        return None

    stabs = [s for s in stabilizer_rows if s]
    stabs_by_weight = sorted(set(stabs), key=bit_count)
    low_gens = sorted(set(gens), key=bit_count)
    best = None

    def consider(v):
        nonlocal best
        v = greedy_stabilizer_descent(v, stabs_by_weight)
        if verified(v, kernel_rows, stab_basis):
            if best is None or bit_count(v) < bit_count(best):
                best = v

    for g in low_gens:
        consider(g)
    m = len(low_gens)
    for i in range(min(m, 80)):
        acc = low_gens[i]
        for j in range(i + 1, min(m, i + 18)):
            consider(acc ^ low_gens[j])

    if best is None:
        # Positive-k fallback: a quotient generator is already a valid logical.
        best = low_gens[0]

    if time.time() >= deadline:
        return best

    pool = low_gens[: min(len(low_gens), 96)]
    if not pool:
        return best
    active = best
    active_w = bit_count(active)
    temp0 = max(1.5, active_w / 2.0)
    iters = 0
    max_iters = 25000 + 1200 * min(n, 400) + 4000 * min(len(pool), 40)
    while iters < max_iters and time.time() < deadline:
        iters += 1
        cand = active

        # Nullspace recombination: mostly small low-weight mixtures, with a
        # heavy-tailed count to escape one-generator basins.
        r = rng.random()
        if r < 0.72:
            flips = 1 + (rng.randrange(3) == 0)
        elif r < 0.94:
            flips = 3 + rng.randrange(4)
        else:
            flips = 7 + rng.randrange(min(18, len(pool)))
        bias_window = max(1, int(len(pool) * (0.15 + 0.85 * rng.random() ** 2)))
        for _ in range(flips):
            cand ^= pool[rng.randrange(bias_window)]

        # Annealed mutation inside the same logical coset by adding stabilizers.
        if stabs_by_weight:
            sflips = 1 + (rng.randrange(5) == 0) + (rng.randrange(17) == 0)
            sw = max(1, int(len(stabs_by_weight) * (0.2 + 0.8 * rng.random() ** 2)))
            for _ in range(sflips):
                cand ^= stabs_by_weight[rng.randrange(sw)]

        if cand == 0 or in_span(cand, stab_basis):
            cand ^= pool[rng.randrange(len(pool))]
        cand = greedy_stabilizer_descent(cand, stabs_by_weight, passes=2)
        if not verified(cand, kernel_rows, stab_basis):
            continue

        cw = bit_count(cand)
        t = temp0 * (1.0 - min(0.999, iters / float(max_iters))) + 0.05
        if cw <= active_w or rng.random() < pow(2.718281828459045, -(cw - active_w) / t):
            active, active_w = cand, cw
        if best is None or cw < bit_count(best):
            best = cand
            active, active_w = cand, cw

    return best


def solve(hx, hz, seed):
    rng = random.Random(seed)
    n = max(hx[1], hz[1])
    hx_rows = hx[0]
    hz_rows = hz[0]
    deadline = time.time() + float(os.environ.get("CANDIDATE_TIME_LIMIT", "25"))

    bx = improve_side(hz_rows, hx_rows, n, rng, deadline)
    bz = improve_side(hx_rows, hz_rows, n, rng, deadline)

    options = []
    if bx is not None:
        options.append(("x", bx, hz_rows, rref_basis(hx_rows)))
    if bz is not None:
        options.append(("z", bz, hx_rows, rref_basis(hz_rows)))
    verified_options = [(b, v) for b, v, k, s in options if verified(v, k, s)]
    if not verified_options:
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    basis, vec = min(verified_options, key=lambda item: bit_count(item[1]))
    return {
        "status": "completed",
        "basis": basis,
        "vector": vec_to_list(vec, n),
        "upper_bound": bit_count(vec),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()
    try:
        os.makedirs(args.output_dir, exist_ok=True)
        result = solve(parse_matrix(args.hx), parse_matrix(args.hz), args.seed)
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
