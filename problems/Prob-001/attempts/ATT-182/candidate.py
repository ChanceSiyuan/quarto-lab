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
    if {"n_rows", "n_cols", "data"} <= set(obj):
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if {"num_cols", "rows"} <= set(obj):
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            last = -1
            for i in row:
                i = int(i)
                if i <= last or i < 0 or i >= n:
                    raise ValueError("invalid sparse row")
                x |= 1 << i
                last = i
            rows.append(x)
        return rows, n
    raise ValueError("unknown matrix JSON format")


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        for q in sorted(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= basis[p]
    return basis


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return y
        y ^= row
    return 0


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(check_rows, n_cols):
    basis = rref_basis(check_rows)
    pivots = set(basis)
    vectors = []
    for free_col in range(n_cols):
        if free_col in pivots:
            continue
        v = 1 << free_col
        for p, row in basis.items():
            if (row >> free_col) & 1:
                v |= 1 << p
        vectors.append(v)
    return vectors


def syndrome_zero(v, check_rows):
    return all(((v & row).bit_count() & 1) == 0 for row in check_rows)


def bits_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def random_combination(rng, vectors, p):
    x = 0
    touched = False
    for v in vectors:
        if rng.random() < p:
            x ^= v
            touched = True
    if not touched and vectors:
        x = rng.choice(vectors)
    return x


def reduce_with_stabilizers(rng, v, stabilizers, deadline):
    best = v
    best_w = v.bit_count()
    if not stabilizers:
        return best

    rows = stabilizers[:]
    improved = True
    passes = 0
    while improved and passes < 8 and time.monotonic() < deadline:
        passes += 1
        improved = False
        rng.shuffle(rows)
        for row in rows:
            cand = best ^ row
            w = cand.bit_count()
            if cand and w < best_w:
                best = cand
                best_w = w
                improved = True

    temp = best
    temp_w = best_w
    temperature = max(1.0, temp_w / 3.0)
    trials = min(2000 + 40 * len(rows), 20000)
    for t in range(trials):
        if time.monotonic() >= deadline:
            break
        row = rng.choice(rows)
        cand = temp ^ row
        if not cand:
            continue
        w = cand.bit_count()
        delta = w - temp_w
        if delta <= 0 or rng.random() < 2.0 ** (-delta / temperature):
            temp = cand
            temp_w = w
            if w < best_w:
                best = cand
                best_w = w
        temperature *= 0.997
        if (t & 63) == 63:
            for row in rows:
                cand = temp ^ row
                w = cand.bit_count()
                if cand and w < temp_w:
                    temp = cand
                    temp_w = w
                    if w < best_w:
                        best = cand
                        best_w = w
    return best


def verified(v, kernel_checks, stabilizer_basis):
    return v != 0 and syndrome_zero(v, kernel_checks) and not in_rowspace(v, stabilizer_basis)


def search_basis(rng, basis_name, kernel_checks, stabilizers, n, seconds):
    deadline = time.monotonic() + seconds
    stab_basis = rref_basis(stabilizers)
    ns = nullspace_basis(kernel_checks, n)
    if not ns:
        return None

    best = None
    best_w = n + 1

    seeds = ns[:]
    rng.shuffle(seeds)
    for v in seeds[: min(len(seeds), 256)]:
        if time.monotonic() >= deadline:
            break
        cand = reduce_with_stabilizers(rng, v, stabilizers, deadline)
        if verified(cand, kernel_checks, stab_basis):
            w = cand.bit_count()
            if w < best_w:
                best, best_w = cand, w

    rates = [1.0 / max(1, len(ns)), 2.0 / max(1, len(ns)), 0.05, 0.1, 0.2, 0.5]
    while time.monotonic() < deadline:
        p = rng.choice(rates)
        v = random_combination(rng, ns, p)
        if not v:
            continue
        cand = reduce_with_stabilizers(rng, v, stabilizers, deadline)
        if verified(cand, kernel_checks, stab_basis):
            w = cand.bit_count()
            if w < best_w:
                best, best_w = cand, w

    if best is None:
        return None
    return {
        "status": "completed",
        "basis": basis_name,
        "vector": bits_to_list(best, n),
        "upper_bound": best_w,
    }


def failure():
    return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("Hx and Hz have different column counts")

    rng = random.Random(args.seed)
    order = [("x", hz, hx), ("z", hx, hz)]
    rng.shuffle(order)
    results = []
    for basis_name, kernel_checks, stabilizers in order:
        res = search_basis(rng, basis_name, kernel_checks, stabilizers, nx, 0.85)
        if res is not None:
            results.append(res)

    if results:
        result = min(results, key=lambda r: r["upper_bound"])
    else:
        result = failure()
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps(failure(), separators=(",", ":")))
        sys.exit(0)
