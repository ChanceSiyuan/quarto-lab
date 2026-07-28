#!/usr/bin/env python3
import argparse
import json
import random
import sys


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n:
                raise ValueError(f"dense row has length {len(row)}, expected {n}")
            bits = 0
            for i, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if bit:
                    bits |= 1 << i
            rows.append(bits)
        if int(obj["n_rows"]) != len(rows):
            raise ValueError("n_rows does not match dense data length")
        return rows, n

    if {"num_cols", "rows"} <= set(obj):
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            prev = -1
            for col in row:
                col = int(col)
                if col <= prev or col < 0 or col >= n:
                    raise ValueError("sparse rows must be strictly increasing valid indices")
                bits |= 1 << col
                prev = col
            rows.append(bits)
        return rows, n

    raise ValueError("unrecognized matrix JSON format")


def rref_basis(rows, n):
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
        for q in sorted(basis, reverse=True):
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


def in_rowspace(x, row_basis):
    return reduce_by_basis(x, row_basis) == 0


def kernel_basis(check_rows, n):
    pivots = rref_basis(check_rows, n)
    pivot_cols = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_cols]
    out = []
    for c in free_cols:
        x = 1 << c
        for p, row in pivots.items():
            if (row >> c) & 1:
                x |= 1 << p
        out.append(x)
    return out


def syndrome_zero(x, check_rows):
    for row in check_rows:
        if (x & row).bit_count() & 1:
            return False
    return True


def to_vector(x, n):
    return [(x >> i) & 1 for i in range(n)]


def greedy_stabilizer_descent(x, stabilizers, rng):
    cur = x
    cur_w = cur.bit_count()
    rows = [r for r in stabilizers if r]
    improved = True
    while improved:
        improved = False
        rng.shuffle(rows)
        for row in rows:
            y = cur ^ row
            w = y.bit_count()
            if w < cur_w:
                cur, cur_w = y, w
                improved = True
    return cur


def random_combo(rows, rng, p):
    x = 0
    for row in rows:
        if rng.random() < p:
            x ^= row
    return x


def verified_witness(x, kernel_checks, stabilizer_basis):
    return x != 0 and syndrome_zero(x, kernel_checks) and not in_rowspace(x, stabilizer_basis)


def search_basis(name, kernel_checks, stabilizers, n, rng):
    stab_basis = rref_basis(stabilizers, n)
    ker = kernel_basis(kernel_checks, n)
    logical_seed = [v for v in ker if not in_rowspace(v, stab_basis)]
    if not logical_seed:
        return None

    candidates = []
    candidates.extend(sorted(logical_seed, key=int.bit_count)[: min(64, len(logical_seed))])

    rounds = max(512, 24 * n + 12 * len(ker))
    probs = [0.015, 0.03, 0.06, 0.125, 0.25, 0.5]
    for _ in range(rounds):
        p = probs[rng.randrange(len(probs))]
        x = random_combo(logical_seed, rng, p)
        if x == 0 or in_rowspace(x, stab_basis):
            x ^= logical_seed[rng.randrange(len(logical_seed))]
        candidates.append(x)

    best = None
    best_w = n + 1
    for x in candidates:
        y = greedy_stabilizer_descent(x, stabilizers, rng)
        if verified_witness(y, kernel_checks, stab_basis):
            w = y.bit_count()
            if 0 < w < best_w:
                best, best_w = y, w

    if best is None:
        return None
    return {"basis": name, "vector": to_vector(best, n), "upper_bound": best_w}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("Hx and Hz must have the same number of columns")
    n = nx

    rng = random.Random(args.seed)
    searches = [
        search_basis("x", hz, hx, n, rng),
        search_basis("z", hx, hz, n, rng),
    ]
    hits = [hit for hit in searches if hit is not None]
    if hits:
        hit = min(hits, key=lambda h: (h["upper_bound"], 0 if h["basis"] == "x" else 1))
        result = {
            "status": "completed",
            "basis": hit["basis"],
            "vector": hit["vector"],
            "upper_bound": hit["upper_bound"],
        }
    else:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
        sys.exit(0)
