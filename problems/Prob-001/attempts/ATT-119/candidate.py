#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def fail(basis="x"):
    return {"status": "failed", "basis": basis, "vector": [], "upper_bound": None}


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_rows = int(obj["n_rows"])
        n_cols = int(obj["n_cols"])
        data = obj["data"]
        if len(data) != n_rows:
            raise ValueError("dense matrix row count mismatch")
        rows = []
        for row in data:
            if len(row) != n_cols:
                raise ValueError("dense matrix column count mismatch")
            bits = 0
            for j, val in enumerate(row):
                if val not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if int(val) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return n_cols, rows

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            bits = 0
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return n_cols, rows

    raise ValueError("unsupported matrix JSON format")


def lsb_index(x):
    return (x & -x).bit_length() - 1


def rref(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = lsb_index(x)
            y = basis.get(p)
            if y is None:
                basis[p] = x
                break
            x ^= y

    pivots = sorted(basis)
    for p in pivots:
        row = basis[p]
        for q in pivots:
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    return [(p, basis[p]) for p in sorted(basis)]


def reduce_by_basis(vec, basis):
    x = vec
    table = {p: row for p, row in basis}
    while x:
        p = lsb_index(x)
        row = table.get(p)
        if row is None:
            return x
        x ^= row
    return 0


def in_rowspace(vec, basis):
    return reduce_by_basis(vec, basis) == 0


def nullspace_basis(check_rows, n_cols):
    rr = rref(check_rows)
    pivot_rows = {p: row for p, row in rr}
    pivots = set(pivot_rows)
    out = []
    for free in range(n_cols):
        if free in pivots:
            continue
        v = 1 << free
        for p, row in pivot_rows.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def extend_rref_basis(existing_basis, vec):
    rows = [row for _, row in existing_basis]
    rows.append(vec)
    return rref(rows)


def quotient_basis(kernel_basis, stabilizer_basis):
    span = list(stabilizer_basis)
    logicals = []
    for v in kernel_basis:
        if not in_rowspace(v, span):
            logicals.append(v)
            span = extend_rref_basis(span, v)
    return logicals


def dot_parity(a, b):
    return (a & b).bit_count() & 1


def in_kernel(vec, check_rows):
    return all(dot_parity(vec, row) == 0 for row in check_rows)


def verified(vec, check_rows, stabilizer_basis):
    return vec != 0 and in_kernel(vec, check_rows) and not in_rowspace(vec, stabilizer_basis)


def random_combo(rows, rng):
    v = 0
    for row in rows:
        if rng.getrandbits(1):
            v ^= row
    return v


def greedy_reduce(vec, moves, rng, rounds):
    best = vec
    best_w = best.bit_count()
    if not moves:
        return best

    current = vec
    current_w = best_w
    order = list(moves)
    for _ in range(rounds):
        improved = False
        rng.shuffle(order)
        for row in order:
            nxt = current ^ row
            w = nxt.bit_count()
            if w < current_w:
                current, current_w = nxt, w
                improved = True
                if w < best_w:
                    best, best_w = nxt, w
        if not improved:
            break
    return best


def search_basis(name, check_rows, stabilizer_rows, n_cols, rng):
    stab_basis = rref(stabilizer_rows)
    kernel = nullspace_basis(check_rows, n_cols)
    logicals = quotient_basis(kernel, stab_basis)
    if not logicals:
        return None

    # Only kernel-preserving stabilizer moves are used during the heuristic walk.
    moves = [row for row in stabilizer_rows if row and in_kernel(row, check_rows)]
    moves += [row for _, row in rref(moves)]
    moves = list(dict.fromkeys(moves))

    if n_cols <= 96:
        samples = 384
    elif n_cols <= 512:
        samples = 192
    else:
        samples = 96
    samples += 8 * min(len(logicals), 64)
    descent_rounds = 3 + min(8, max(1, len(moves) // 32))

    best = None
    best_w = n_cols + 1

    seeds = list(logicals)
    for _ in range(samples):
        v = random_combo(logicals, rng)
        if v == 0:
            v = rng.choice(logicals)
        if moves and rng.random() < 0.7:
            v ^= random_combo(moves, rng)
        seeds.append(v)

    for v in seeds:
        v = greedy_reduce(v, moves, rng, descent_rounds)
        if verified(v, check_rows, stab_basis):
            w = v.bit_count()
            if w < best_w:
                best, best_w = v, w

    if best is None:
        return None
    return {"basis": name, "vec": best, "weight": best_w}


def int_to_bits(vec, n_cols):
    return [(vec >> i) & 1 for i in range(n_cols)]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    try:
        hx_n, hx_rows = load_matrix(args.hx)
        hz_n, hz_rows = load_matrix(args.hz)
        if hx_n != hz_n:
            raise ValueError("Hx and Hz must have the same number of columns")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        # X logicals commute with Hz and are nontrivial modulo rows of Hx.
        x_rng = random.Random(rng.getrandbits(64))
        z_rng = random.Random(rng.getrandbits(64))
        candidates = [
            search_basis("x", hz_rows, hx_rows, hx_n, x_rng),
            search_basis("z", hx_rows, hz_rows, hx_n, z_rng),
        ]
        candidates = [c for c in candidates if c is not None]
        if not candidates:
            result = fail("x")
        else:
            chosen = min(candidates, key=lambda c: (c["weight"], c["basis"]))
            result = {
                "status": "completed",
                "basis": chosen["basis"],
                "vector": int_to_bits(chosen["vec"], hx_n),
                "upper_bound": int(chosen["weight"]),
            }
    except Exception:
        result = fail("x")

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
