#!/usr/bin/env python3
import argparse
import json
import os
import random


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n = int(obj["n_cols"])
        rows = []
        for row in obj.get("data", []):
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x |= 1 << i
            rows.append(x)
        return n, rows

    if "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj.get("rows", []):
            x = 0
            last = -1
            for i in row:
                i = int(i)
                if i <= last or i < 0 or i >= n:
                    raise ValueError("invalid sparse row")
                x |= 1 << i
                last = i
            rows.append(x)
        return n, rows

    raise ValueError("unsupported matrix JSON format")


def rref_rows(rows, n):
    rows = [r for r in rows if r]
    rank = 0
    pivots = []
    for col in range(n):
        bit = 1 << col
        pivot = None
        for i in range(rank, len(rows)):
            if rows[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        prow = rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & bit):
                rows[i] ^= prow
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return rows[:rank], pivots


def rowspace_basis(rows, n):
    rref, pivots = rref_rows(rows, n)
    return {p: r for p, r in zip(pivots, rref)}


def reduce_by_basis(x, basis):
    while x:
        lb = x & -x
        p = lb.bit_length() - 1
        row = basis.get(p)
        if row is None:
            break
        x ^= row
    return x


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    rref, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    out = []
    for f in range(n):
        if f in pivot_set:
            continue
        v = 1 << f
        for row, p in zip(rref, pivots):
            if row & (1 << f):
                v |= 1 << p
        out.append(v)
    return out


def is_kernel(v, checks):
    return all(((v & row).bit_count() & 1) == 0 for row in checks)


def bits_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def random_combo(vectors, rng, force_nonzero=True):
    x = 0
    used = False
    for v in vectors:
        if rng.getrandbits(1):
            x ^= v
            used = True
    if force_nonzero and vectors and not used:
        x = rng.choice(vectors)
    return x


def greedy_coset_reduce(v, stabilizers, rng, rounds):
    if not stabilizers:
        return v
    rows = list(stabilizers)
    best = v
    best_w = v.bit_count()
    for _ in range(rounds):
        changed = False
        rng.shuffle(rows)
        for row in rows:
            w = (v ^ row).bit_count()
            if w < v.bit_count():
                v ^= row
                changed = True
        vw = v.bit_count()
        if vw < best_w:
            best = v
            best_w = vw
        if not changed:
            break
    return best


def quotient_seeds(kernel_basis, stabilizers, n):
    span = rowspace_basis(stabilizers, n)
    seeds = []
    grow = list(stabilizers)
    for v in sorted(kernel_basis, key=int.bit_count):
        if not in_rowspace(v, span):
            seeds.append(v)
            grow.append(v)
            span = rowspace_basis(grow, n)
    return seeds


def search_basis(name, checks, stabilizers, n, rng):
    stab_rref, _ = rref_rows(stabilizers, n)
    stab_basis = rowspace_basis(stab_rref, n)
    kern = nullspace_basis(checks, n)
    seeds = quotient_seeds(kern, stab_rref, n)
    if not seeds:
        return None

    candidates = list(seeds)
    candidates.append(random_combo(seeds, rng))

    best = None
    best_w = n + 1

    def accept(v):
        nonlocal best, best_w
        if not v:
            return
        if not is_kernel(v, checks):
            return
        if in_rowspace(v, stab_basis):
            return
        w = v.bit_count()
        if w < best_w:
            best = v
            best_w = w

    for seed in candidates:
        accept(greedy_coset_reduce(seed, stab_rref, rng, 8))

    trials = max(250, min(2500, 8 * max(1, n) + 30 * len(seeds)))
    for t in range(trials):
        if t % 5 == 0:
            v = random_combo(seeds, rng)
        else:
            v = random_combo(kern, rng)
        if not v:
            continue
        if stab_rref and rng.random() < 0.35:
            v ^= random_combo(stab_rref, rng, force_nonzero=False)
        rounds = 3 + (t % 7 == 0) * 7
        v = greedy_coset_reduce(v, stab_rref, rng, rounds)
        accept(v)

    if best is None:
        return None
    return {"basis": name, "vector": bits_to_list(best, n), "upper_bound": best_w}


def solve(hx_path, hz_path, seed, output_dir):
    nx, hx = load_matrix(hx_path)
    nz, hz = load_matrix(hz_path)
    n = max(nx, nz)
    mask = (1 << n) - 1
    hx = [r & mask for r in hx]
    hz = [r & mask for r in hz]
    rng = random.Random(seed)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    searches = [
        ("x", hz, hx),
        ("z", hx, hz),
    ]
    rng.shuffle(searches)

    found = []
    for name, checks, stabilizers in searches:
        result = search_basis(name, checks, stabilizers, n, rng)
        if result is not None:
            found.append(result)

    if found:
        found.sort(key=lambda r: (r["upper_bound"], r["basis"]))
        ans = found[0]
        return {
            "status": "completed",
            "basis": ans["basis"],
            "vector": ans["vector"],
            "upper_bound": ans["upper_bound"],
        }

    return {"status": "not_found", "basis": "x", "vector": [0] * n, "upper_bound": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        result = solve(args.hx, args.hz, args.seed, args.output_dir)
    except Exception:
        result = {"status": "error", "basis": "x", "vector": [], "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
