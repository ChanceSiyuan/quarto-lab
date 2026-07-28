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
    if isinstance(obj, dict):
        if "dense_binary_matrix" in obj:
            obj = obj["dense_binary_matrix"]
        elif "sparse_rows" in obj:
            obj = obj["sparse_rows"]
    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", 0))
        rows = []
        for row in data:
            x = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    x ^= 1 << j
            rows.append(x)
        if n == 0 and data:
            n = len(data[0])
        return rows, n
    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for cols in obj.get("rows") or []:
            x = 0
            for j in cols:
                jj = int(j)
                if jj >= 0:
                    x ^= 1 << jj
            rows.append(x)
        return rows, n
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for row in obj:
            x = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    x ^= 1 << j
            rows.append(x)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def rref(rows, n):
    basis = {}
    for row in rows:
        x = row & ((1 << n) - 1 if n else 0)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        row = basis[p]
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    pivots = sorted(basis, reverse=True)
    return [basis[p] for p in pivots], pivots, basis


def reduce_by_basis(x, basis_by_pivot):
    y = x
    while y:
        p = y.bit_length() - 1
        row = basis_by_pivot.get(p)
        if row is None:
            return y
        y ^= row
    return 0


def in_rowspace(x, basis_by_pivot):
    return reduce_by_basis(x, basis_by_pivot) == 0


def nullspace_basis(rows, n):
    _, pivots, by_pivot = rref(rows, n)
    pivot_set = set(pivots)
    free_cols = [j for j in range(n) if j not in pivot_set]
    out = []
    for f in free_cols:
        v = 1 << f
        for p in pivots:
            row = by_pivot[p]
            if (row >> f) & 1:
                v ^= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, checks):
    return all(((v & row).bit_count() & 1) == 0 for row in checks)


def vec_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def random_combination(rng, vecs, p):
    x = 0
    for v in vecs:
        if rng.random() < p:
            x ^= v
    return x


def greedy_reduce(v, stabilizers, rng, passes=4):
    cur = v
    cur_w = cur.bit_count()
    rows = [r for r in stabilizers if r]
    for _ in range(passes):
        improved = False
        rng.shuffle(rows)
        for r in rows:
            nw = (cur ^ r).bit_count()
            if nw < cur_w or (nw == cur_w and rng.random() < 0.015):
                cur ^= r
                cur_w = nw
                improved = True
        if not improved:
            break
    return cur


def annealed_coset_reduce(v, stabilizers, rng, budget):
    cur = greedy_reduce(v, stabilizers, rng, 3)
    best = cur
    cur_w = cur.bit_count()
    best_w = cur_w
    rows = [r for r in stabilizers if r]
    if not rows:
        return best
    budget = max(1, budget)
    for t in range(budget):
        temp = max(0.05, 2.5 * (1.0 - t / budget))
        r = rows[rng.randrange(len(rows))]
        nxt = cur ^ r
        nw = nxt.bit_count()
        delta = nw - cur_w
        if delta <= 0 or rng.random() < pow(2.718281828, -delta / temp):
            cur = nxt
            cur_w = nw
            if cur_w < best_w:
                best = cur
                best_w = cur_w
        if (t & 31) == 31:
            cur = greedy_reduce(cur, rows, rng, 1)
            cur_w = cur.bit_count()
            if cur_w < best_w:
                best = cur
                best_w = cur_w
    return best


def logical_seed_from_kernel(kernel_basis, stab_basis_by_pivot):
    span_basis = dict(stab_basis_by_pivot)
    seeds = []
    for v in sorted(kernel_basis, key=lambda z: z.bit_count()):
        r = reduce_by_basis(v, span_basis)
        if r:
            seeds.append(v)
            p = r.bit_length() - 1
            span_basis[p] = r
            for q in list(span_basis):
                if q != p and ((span_basis[q] >> p) & 1):
                    span_basis[q] ^= r
    return seeds


def search_basis(name, check_rows, stab_rows, n, rng, deadline):
    kernel = nullspace_basis(check_rows, n)
    _, _, stab_by_pivot = rref(stab_rows, n)
    seeds = logical_seed_from_kernel(kernel, stab_by_pivot)
    if not seeds:
        return None

    candidates = []
    for s in seeds[: min(len(seeds), 64)]:
        candidates.append(s)
    small_kernel = sorted(kernel, key=lambda z: z.bit_count())[: max(8, min(len(kernel), 160))]
    small_seeds = sorted(seeds, key=lambda z: z.bit_count())[: max(4, min(len(seeds), 48))]

    best = None
    def consider(v, budget):
        nonlocal best
        if not v or in_rowspace(v, stab_by_pivot):
            return
        w = annealed_coset_reduce(v, stab_rows, rng, budget)
        if w and not in_rowspace(w, stab_by_pivot) and syndrome_zero(w, check_rows):
            if best is None or w.bit_count() < best.bit_count():
                best = w

    for v in candidates:
        consider(v, 16 + min(512, len(stab_rows) * 3))

    if best is not None and best.bit_count() <= 2:
        return best

    n_iter = 650 + 18 * min(n, 300) + 8 * min(len(kernel), 300)
    n_iter = min(n_iter, 9000)
    for it in range(n_iter):
        if time.time() > deadline:
            break
        frac = it / max(1, n_iter - 1)
        temp = 1.0 - frac
        if rng.random() < 0.58 and small_seeds:
            v = small_seeds[rng.randrange(len(small_seeds))]
        else:
            v = 0
            seed_count = 1 + int(rng.random() ** 2 * min(7, len(small_seeds)))
            for _ in range(seed_count):
                v ^= small_seeds[rng.randrange(len(small_seeds))]
        p = 0.018 + 0.12 * temp
        if small_kernel:
            # Low-weight nullspace recombination: mutation is kernel-preserving,
            # while the annealed rate cools from exploratory to local.
            if rng.random() < 0.75:
                touches = 1 + int((rng.random() ** 1.7) * min(20, len(small_kernel)))
                for _ in range(touches):
                    if rng.random() < p * 7.0:
                        v ^= small_kernel[rng.randrange(len(small_kernel))]
            else:
                v ^= random_combination(rng, small_kernel, p)
        consider(v, 8 + min(260, len(stab_rows) * 2))

    if best is not None:
        return best

    # Reliable positive-k fallback: a quotient-independent kernel basis vector,
    # then stabilizer coset descent. This is a witness search, not exact distance.
    for s in seeds:
        consider(s, 8 + min(256, len(stab_rows) * 2))
        if best is not None:
            return best
    return None


def choose_witness(hx, hz, n, seed):
    rng = random.Random(seed)
    deadline = time.time() + 28.0
    searches = [
        ("x", hz, hx),
        ("z", hx, hz),
    ]
    rng.shuffle(searches)
    found = []
    for name, checks, stabs in searches:
        w = search_basis(name, checks, stabs, n, rng, deadline)
        if w is not None:
            found.append((w.bit_count(), name, w, checks, stabs))
    if not found:
        return None
    found.sort(key=lambda item: item[0])
    _, name, w, checks, stabs = found[0]
    _, _, stab_by_pivot = rref(stabs, n)
    if w and syndrome_zero(w, checks) and not in_rowspace(w, stab_by_pivot):
        return name, w
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        os.makedirs(args.output_dir, exist_ok=True)
        result = choose_witness(hx, hz, n, args.seed)
        if result is None:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
        else:
            basis, v = result
            out = {
                "status": "completed",
                "basis": basis,
                "vector": vec_to_list(v, n),
                "upper_bound": int(v.bit_count()),
            }
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
