#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import sys


def popcount(x):
    return x.bit_count()


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj and "rows" not in obj:
        obj = obj["sparse_rows"]

    rows = []
    n = None

    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        if n <= 0:
            raise ValueError("dense matrix missing n_cols")
        if data and all(isinstance(v, int) for v in data):
            if len(data) % n != 0:
                raise ValueError("flat dense data length is not divisible by n_cols")
            data = [data[i:i + n] for i in range(0, len(data), n)]
        for row in data:
            v = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    v |= 1 << j
            rows.append(v)
    elif isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            raise ValueError("sparse matrix missing num_cols")
        for row in obj["rows"]:
            v = 0
            for j in row:
                jj = int(j)
                if jj < 0 or jj >= n:
                    raise ValueError("sparse row index out of range")
                v |= 1 << jj
            rows.append(v)
    elif isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        for row in obj:
            v = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    v |= 1 << j
            rows.append(v)
    else:
        raise ValueError("unrecognized matrix JSON format")

    mask = (1 << n) - 1 if n > 0 else 0
    return [r & mask for r in rows], n


def build_basis(rows):
    basis = {}
    for row in rows:
        v = row
        while v:
            p = v.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = v
                break
            v ^= b
    return basis


def reduce_with_basis(v, basis):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(v, basis):
    return reduce_with_basis(v, basis) == 0


def rref(rows, n):
    a = [r for r in rows if r]
    pivots = []
    r = 0
    for c in range(n):
        bit = 1 << c
        pivot = None
        for i in range(r, len(a)):
            if a[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        a[r], a[pivot] = a[pivot], a[r]
        for i in range(len(a)):
            if i != r and (a[i] & bit):
                a[i] ^= a[r]
        pivots.append(c)
        r += 1
        if r == len(a):
            break
    return a[:r], pivots


def nullspace_basis(rows, n):
    rr, pivots = rref(rows, n)
    pivot_set = set(pivots)
    basis = []
    for f in range(n):
        if f in pivot_set:
            continue
        v = 1 << f
        for row, p in zip(rr, pivots):
            if row & (1 << f):
                v |= 1 << p
        basis.append(v)
    return basis


def row_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        x = r
        while x:
            lsb = x & -x
            deg[lsb.bit_length() - 1] += 1
            x ^= lsb
    return deg


def bit_indices(v):
    while v:
        lsb = v & -v
        j = lsb.bit_length() - 1
        yield j
        v ^= lsb


def support_cost(v, reliability):
    return sum(reliability[j] for j in bit_indices(v))


def noisy_bp_reliability(check_rows, stab_rows, n, rng, rounds=5):
    checks = [r for r in check_rows if r]
    cdeg = row_degrees(checks, n)
    sdeg = row_degrees(stab_rows, n)
    llr = []
    for j in range(n):
        base = 1.0 + 0.18 * cdeg[j] + 0.05 * sdeg[j]
        llr.append(base + rng.expovariate(1.0) * 0.35 + rng.uniform(-0.25, 0.25))

    adjacency = [[] for _ in range(n)]
    for ci, row in enumerate(checks):
        for j in bit_indices(row):
            adjacency[j].append(ci)

    # Min-sum style zero-syndrome reliability update.  It is deliberately noisy:
    # the values only order bits and rows for randomized witness search.
    v_to_c = {}
    c_to_v = {}
    for ci, row in enumerate(checks):
        for j in bit_indices(row):
            v_to_c[(j, ci)] = llr[j]
            c_to_v[(ci, j)] = 0.0
    for _ in range(rounds):
        for ci, row in enumerate(checks):
            cols = list(bit_indices(row))
            if len(cols) <= 1:
                for j in cols:
                    c_to_v[(ci, j)] = 6.0
                continue
            abs_msgs = [(abs(v_to_c[(j, ci)]), j) for j in cols]
            abs_msgs.sort()
            m1, j1 = abs_msgs[0]
            m2 = abs_msgs[1][0]
            sign_all = 1.0
            for j in cols:
                if v_to_c[(j, ci)] < 0:
                    sign_all = -sign_all
            for j in cols:
                msg_sign = sign_all * (-1.0 if v_to_c[(j, ci)] < 0 else 1.0)
                mag = m2 if j == j1 else m1
                c_to_v[(ci, j)] = max(-6.0, min(6.0, msg_sign * mag * 0.72))
        for j in range(n):
            total = llr[j] + sum(c_to_v[(ci, j)] for ci in adjacency[j])
            for ci in adjacency[j]:
                v_to_c[(j, ci)] = max(-8.0, min(8.0, total - c_to_v[(ci, j)]))
    rel = []
    for j in range(n):
        total = llr[j] + sum(c_to_v[(ci, j)] for ci in adjacency[j])
        rel.append(abs(total) + rng.uniform(0.0, 0.15))
    return rel


def logical_generators(kernel_basis, stab_rows):
    aug = build_basis(stab_rows)
    gens = []
    for v in sorted(kernel_basis, key=lambda x: (popcount(x), x.bit_length())):
        rem = reduce_with_basis(v, aug)
        if rem:
            gens.append(v)
            p = rem.bit_length() - 1
            aug[p] = rem
    return gens


def verify(v, check_rows, stab_basis):
    if v == 0:
        return False
    for row in check_rows:
        if popcount(v & row) & 1:
            return False
    return not in_rowspace(v, stab_basis)


def greedy_coset_reduce(v, stab_rows, reliability, rng, passes=4):
    cur = v
    rows = [r for r in stab_rows if r]
    if not rows:
        return cur
    for p in range(passes):
        scored = []
        for r in rows:
            gain = popcount(cur) - popcount(cur ^ r)
            border = support_cost(r & cur, reliability) - 0.35 * support_cost(r & ~cur, reliability)
            scored.append((gain, border + rng.uniform(-0.5, 0.5), r))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        changed = False
        slack = 1 if p == 0 and rng.random() < 0.35 else 0
        for gain, _score, r in scored:
            if gain > 0 or (slack and gain == 0 and rng.random() < 0.08):
                nxt = cur ^ r
                if popcount(nxt) <= popcount(cur) + slack:
                    cur = nxt
                    changed = True
        if not changed:
            break
    return cur


def make_seed(gens, reliability, rng, restart):
    if len(gens) == 1:
        return gens[0]
    ordered = sorted(gens, key=lambda g: (support_cost(g, reliability), popcount(g)))
    if restart % 5 == 0:
        seed = ordered[0]
    else:
        pool = ordered[:max(2, min(len(ordered), 16))]
        seed = rng.choice(pool)
    p = 0.10 + 0.18 * rng.random()
    if restart % 7 == 3:
        p = 0.45
    for g in ordered[:min(len(ordered), 48)]:
        if g != seed and rng.random() < p / math.sqrt(1.0 + popcount(g)):
            seed ^= g
    return seed


def search_basis(name, check_rows, stab_rows, n, rng):
    stab_basis = build_basis(stab_rows)
    kernel = nullspace_basis(check_rows, n)
    gens = logical_generators(kernel, stab_rows)
    if not gens:
        return None

    best = None
    best_w = n + 1

    def consider(v):
        nonlocal best, best_w
        if verify(v, check_rows, stab_basis):
            w = popcount(v)
            if w < best_w:
                best = v
                best_w = w

    # Deterministic basis-derived fallback candidates first.
    base_rel = [1.0] * n
    for g in gens[:min(len(gens), 64)]:
        consider(greedy_coset_reduce(g, stab_rows, base_rel, rng, passes=3))
        consider(g)

    edge_count = sum(popcount(r) for r in check_rows) + sum(popcount(r) for r in stab_rows)
    restarts = 80 + min(220, 8 * len(gens) + n // 2)
    if edge_count > 20000 or n > 1200:
        restarts = min(restarts, 90)
    elif edge_count > 8000 or n > 600:
        restarts = min(restarts, 150)
    for r in range(restarts):
        rel = noisy_bp_reliability(check_rows, stab_rows, n, rng, rounds=3 + (r % 4))
        seed = make_seed(gens, rel, rng, r)
        if seed == 0:
            continue
        cur = seed
        # Random stabilizer shake before reliability-ordered descent.
        if stab_rows:
            for s in rng.sample(stab_rows, min(len(stab_rows), 1 + (r % 6))):
                if rng.random() < 0.55:
                    cur ^= s
        cur = greedy_coset_reduce(cur, stab_rows, rel, rng, passes=5)
        consider(cur)
        if best_w <= 1:
            break

    if best is None:
        # Last resort: any logical generator is already a valid witness when it
        # passes the independent gate.
        for g in gens:
            consider(g)
            if best is not None:
                break
    if best is None:
        return None
    return {"basis": name, "vector_int": best, "upper_bound": best_w}


def vector_list(v, n):
    return [1 if (v >> j) & 1 else 0 for j in range(n)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    try:
        hx, nx = parse_matrix(args.hx)
        hz, nz = parse_matrix(args.hz)
        n = max(nx, nz)
        if nx != n:
            hx = [r & ((1 << nx) - 1) for r in hx]
        if nz != n:
            hz = [r & ((1 << nz) - 1) for r in hz]
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        candidates = []
        x = search_basis("x", hz, hx, n, rng)
        if x is not None:
            candidates.append(x)
        z = search_basis("z", hx, hz, n, rng)
        if z is not None:
            candidates.append(z)

        if candidates:
            best = min(candidates, key=lambda c: (c["upper_bound"], 0 if c["basis"] == "x" else 1))
            out = {
                "status": "completed",
                "basis": best["basis"],
                "vector": vector_list(best["vector_int"], n),
                "upper_bound": best["upper_bound"],
            }
        else:
            out = {"status": "failed", "basis": "", "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": "", "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
