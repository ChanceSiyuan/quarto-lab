#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def popcount(x):
    return x.bit_count()


def parity(x):
    return x.bit_count() & 1


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        ncols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if bit:
                    x |= 1 << i
            rows.append(x)
        return rows, ncols

    if {"num_cols", "rows"} <= set(obj):
        ncols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            prev = -1
            for col in row:
                col = int(col)
                if col <= prev or col < 0 or col >= ncols:
                    raise ValueError("invalid sparse row")
                x |= 1 << col
                prev = col
            rows.append(x)
        return rows, ncols

    raise ValueError("unsupported matrix JSON format")


def reduce_by_basis(x, basis):
    for p in sorted(basis, reverse=True):
        if (x >> p) & 1:
            x ^= basis[p]
    return x


def insert_basis(x, basis):
    x = reduce_by_basis(x, basis)
    if not x:
        return False
    p = x.bit_length() - 1
    for q, row in list(basis.items()):
        if (row >> p) & 1:
            basis[q] = row ^ x
    basis[p] = x
    return True


def make_basis(rows):
    basis = {}
    for row in rows:
        if row:
            insert_basis(row, basis)
    return basis


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, ncols):
    rref = make_basis(rows)
    pivots = set(rref)
    free_cols = [c for c in range(ncols) if c not in pivots]
    out = []
    for c in free_cols:
        v = 1 << c
        for p, row in rref.items():
            if parity(row & v):
                v |= 1 << p
        out.append(v)
    return out


def logical_basis(kernel_basis, stabilizer_basis):
    combined = dict(stabilizer_basis)
    out = []
    for v in sorted(kernel_basis, key=popcount):
        if insert_basis(v, combined):
            out.append(v)
    return out


def make_reducers(stabilizer_rows, stabilizer_basis, rng, limit):
    seeds = [r for r in stabilizer_rows if r]
    seeds.extend(stabilizer_basis.values())
    uniq = {}
    for r in seeds:
        uniq[r] = None

    light = sorted([r for r in seeds if r], key=popcount)[: min(len(seeds), 512)]
    attempts = min(limit * 4, 6000)
    for _ in range(attempts):
        if len(uniq) >= limit or not light:
            break
        r = 0
        for _ in range(rng.randint(2, 4)):
            r ^= rng.choice(light)
        if r:
            uniq[r] = None

    return sorted(uniq, key=popcount)


def reduce_coset(v, reducers, rng, rounds):
    if not v:
        return v
    best = v
    best_w = popcount(v)
    ordered = list(reducers)

    for r in ordered:
        w = popcount(v ^ r)
        if w < best_w:
            v ^= r
            best = v
            best_w = w

    for _ in range(rounds):
        changed = False
        rng.shuffle(ordered)
        for r in ordered:
            w = popcount(v ^ r)
            if w < best_w:
                v ^= r
                best = v
                best_w = w
                changed = True
        if not changed:
            break
    return best


def verifies(v, check_rows, stabilizer_basis):
    if not v:
        return False
    for row in check_rows:
        if parity(row & v):
            return False
    return not in_rowspace(v, stabilizer_basis)


def int_to_bits(v, ncols):
    return [(v >> i) & 1 for i in range(ncols)]


def search_basis(label, check_rows, stabilizer_rows, ncols, rng, deadline):
    stabilizer_basis = make_basis(stabilizer_rows)
    kernel = nullspace_basis(check_rows, ncols)
    logicals = logical_basis(kernel, stabilizer_basis)
    if not logicals:
        return None

    reducers = make_reducers(
        stabilizer_rows,
        stabilizer_basis,
        rng,
        limit=max(128, min(4096, 16 * ncols)),
    )
    best = None
    best_w = ncols + 1

    def consider(v, rounds):
        nonlocal best, best_w
        if not v:
            return
        v = reduce_coset(v, reducers, rng, rounds)
        if verifies(v, check_rows, stabilizer_basis):
            w = popcount(v)
            if w < best_w:
                best = v
                best_w = w

    for v in logicals:
        consider(v, 4)

    trials = max(800, min(20000, 80 * ncols + 300 * len(logicals)))
    max_subset = min(12, len(logicals))
    for t in range(trials):
        if time.monotonic() > deadline:
            break
        v = 0
        if t % 5 == 0:
            take = 1
        else:
            take = rng.randint(1, max_subset)
        for idx in rng.sample(range(len(logicals)), take):
            v ^= logicals[idx]
        consider(v, 2)

    if best is None:
        return None
    return {"basis": label, "vector": int_to_bits(best, ncols), "upper_bound": best_w}


def failure():
    return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("HX and HZ have different column counts")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        deadline = time.monotonic() + 8.0
        results = [
            search_basis("x", hz, hx, nx, rng, deadline),
            search_basis("z", hx, hz, nx, rng, deadline),
        ]
        results = [r for r in results if r is not None]
        if not results:
            ans = failure()
        else:
            ans = min(results, key=lambda r: r["upper_bound"])
            ans = {
                "status": "completed",
                "basis": ans["basis"],
                "vector": ans["vector"],
                "upper_bound": ans["upper_bound"],
            }
    except Exception:
        ans = failure()

    print(json.dumps(ans, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
