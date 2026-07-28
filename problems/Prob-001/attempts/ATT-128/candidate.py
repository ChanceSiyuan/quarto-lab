#!/usr/bin/env python3
import argparse
import json
import os
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
    raise ValueError("unrecognized matrix JSON format")


def leading_bit(x):
    return x.bit_length() - 1


def row_reduce(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = leading_bit(x)
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        for q in list(basis):
            if p != q and ((basis[q] >> p) & 1):
                basis[q] ^= basis[p]
    return basis


def in_span(x, basis):
    y = x
    while y:
        p = leading_bit(y)
        b = basis.get(p)
        if b is None:
            return False
        y ^= b
    return True


def kernel_basis(rows, n):
    piv = row_reduce(rows)
    pivot_cols = set(piv)
    out = []
    for free in range(n):
        if free in pivot_cols:
            continue
        x = 1 << free
        for p, row in piv.items():
            if (row >> free) & 1:
                x |= 1 << p
        out.append(x)
    return out


def logical_reps(comm_rows, stab_rows, n):
    ker = kernel_basis(comm_rows, n)
    span = row_reduce(stab_rows)
    reps = []
    for v in ker:
        if not in_span(v, span):
            reps.append(v)
            span = row_reduce(list(span.values()) + [v])
    return reps


def dot_parity(a, b):
    return (a & b).bit_count() & 1


def in_kernel(v, rows):
    return all(dot_parity(v, r) == 0 for r in rows)


def verify(v, comm_rows, stab_rows):
    return v != 0 and in_kernel(v, comm_rows) and not in_span(v, row_reduce(stab_rows))


def to_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


def reduce_by_stabilizers(v, stab_rows, rng, passes):
    if not stab_rows:
        return v
    cur = v
    cur_w = cur.bit_count()
    rows = list(stab_rows)
    for _ in range(passes):
        rng.shuffle(rows)
        improved = False
        for r in rows:
            nxt = cur ^ r
            w = nxt.bit_count()
            was_better = w < cur_w
            if was_better or (w == cur_w and rng.randrange(64) == 0):
                cur, cur_w = nxt, w
                improved = improved or was_better
        if not improved and rng.randrange(5):
            break
    return cur


def random_mix(reps, rng):
    v = 0
    for r in reps:
        if rng.getrandbits(1):
            v ^= r
    if v == 0 and reps:
        v = rng.choice(reps)
    return v


def search_basis(name, comm_rows, stab_rows, n, rng):
    usable_stabs = [r for r in stab_rows if r and in_kernel(r, comm_rows)]
    reps = logical_reps(comm_rows, stab_rows, n)
    if not reps:
        return None

    best = None
    rounds = max(128, min(4096, 24 * (len(reps) + len(usable_stabs) + 1)))
    passes = max(4, min(32, len(usable_stabs) // 8 + 4))

    seeds = sorted(reps, key=int.bit_count)[: min(len(reps), 64)]
    for seed in seeds:
        cand = reduce_by_stabilizers(seed, usable_stabs, rng, passes)
        if verify(cand, comm_rows, stab_rows):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    for _ in range(rounds):
        cand = random_mix(reps, rng)
        cand = reduce_by_stabilizers(cand, usable_stabs, rng, passes)
        if verify(cand, comm_rows, stab_rows):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    if best is None:
        return None
    return {"basis": name, "vector": to_bits(best, n), "upper_bound": best.bit_count()}


def emit(obj):
    print(json.dumps(obj, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)

        # X logicals commute with Hz modulo X stabilizers Hx; Z swaps the roles.
        candidates = [
            search_basis("x", hz, hx, nx, rng),
            search_basis("z", hx, hz, nx, rng),
        ]
        candidates = [c for c in candidates if c is not None]
        if not candidates:
            emit({"status": "failed", "basis": "x", "vector": [], "upper_bound": None})
            return 0
        ans = min(candidates, key=lambda c: (c["upper_bound"], 0 if c["basis"] == "x" else 1))
        ans["status"] = "completed"
        emit({"status": ans["status"], "basis": ans["basis"], "vector": ans["vector"], "upper_bound": ans["upper_bound"]})
        return 0
    except Exception:
        emit({"status": "failed", "basis": "x", "vector": [], "upper_bound": None})
        return 0


if __name__ == "__main__":
    sys.exit(main())
