#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def fail(message):
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
    sys.exit(0)


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError("dense row length mismatch")
            bits = 0
            for i, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if bit:
                    bits |= 1 << i
            rows.append(bits)
        if len(rows) != int(obj["n_rows"]):
            raise ValueError("dense row count mismatch")
        return rows, n_cols

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            bits = 0
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing valid indices")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unknown matrix JSON format")


def parity(x):
    return x.bit_count() & 1


def echelon_basis(rows):
    basis = {}
    for row in rows:
        v = int(row)
        while v:
            p = v.bit_length() - 1
            if p not in basis:
                basis[p] = v
                for q, b in list(basis.items()):
                    if q != p and ((b >> p) & 1):
                        basis[q] = b ^ v
                break
            v ^= basis[p]
    return basis


def reduce_by_basis(v, basis):
    v = int(v)
    while v:
        p = v.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return v
        v ^= b
    return 0


def in_rowspace(v, basis):
    return reduce_by_basis(v, basis) == 0


def nullspace_basis(check_rows, n_cols):
    row_basis = echelon_basis(check_rows)
    pivots = set(row_basis)
    out = []
    for free in range(n_cols):
        if free in pivots:
            continue
        v = 1 << free
        for p, row in row_basis.items():
            if parity(row & v):
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, checks):
    return all(parity(v & row) == 0 for row in checks)


def to_bits(v, n_cols):
    return [(v >> i) & 1 for i in range(n_cols)]


def minimize_by_stabilizers(v, stabilizer_rows, rng, rounds):
    rows = [r for r in stabilizer_rows if r]
    if not rows:
        return v

    rows = sorted(set(rows), key=lambda r: (r.bit_count(), r))
    best = v
    improved = True
    passes = 0
    while improved and passes < 12:
        improved = False
        passes += 1
        for row in rows:
            cand = best ^ row
            if cand and cand.bit_count() < best.bit_count():
                best = cand
                improved = True

    work = rows[:]
    for _ in range(rounds):
        rng.shuffle(work)
        cur = best
        for row in work:
            cand = cur ^ row
            if cand and cand.bit_count() <= cur.bit_count() + (1 if rng.random() < 0.04 else 0):
                cur = cand
        cur = greedy_polish(cur, rows)
        if cur.bit_count() < best.bit_count():
            best = cur
    return best


def greedy_polish(v, rows):
    changed = True
    while changed:
        changed = False
        for row in rows:
            cand = v ^ row
            if cand and cand.bit_count() < v.bit_count():
                v = cand
                changed = True
    return v


def random_kernel_combo(kernel_basis, rng):
    v = 0
    if not kernel_basis:
        return 0
    # Bias toward sparse combinations while still allowing broad exploration.
    p = rng.uniform(0.08, 0.45)
    for b in kernel_basis:
        if rng.random() < p:
            v ^= b
    if v == 0:
        v = rng.choice(kernel_basis)
    return v


def search_basis(name, kernel_checks, stabilizer_rows, n_cols, rng):
    kernel = nullspace_basis(kernel_checks, n_cols)
    stab_basis = echelon_basis(stabilizer_rows)
    stab_reducers = list(stabilizer_rows) + list(stab_basis.values())

    best = None
    base_trials = min(5000, max(400, 60 * max(1, len(kernel))))
    descent_rounds = min(140, max(10, len(stab_reducers) // 2))

    starts = list(kernel)
    rng.shuffle(starts)
    for v in starts[: min(len(starts), 256)]:
        if v and not in_rowspace(v, stab_basis):
            cand = minimize_by_stabilizers(v, stab_reducers, rng, descent_rounds)
            if cand and not in_rowspace(cand, stab_basis):
                if best is None or cand.bit_count() < best.bit_count():
                    best = cand

    for _ in range(base_trials):
        v = random_kernel_combo(kernel, rng)
        if not v or in_rowspace(v, stab_basis):
            continue
        cand = minimize_by_stabilizers(v, stab_reducers, rng, descent_rounds)
        if cand and not in_rowspace(cand, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    if best is None:
        return None
    if not syndrome_zero(best, kernel_checks):
        return None
    if in_rowspace(best, stab_basis):
        return None
    return {"basis": name, "vector": to_bits(best, n_cols), "upper_bound": best.bit_count()}


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz column counts differ")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        candidates = []
        xb = search_basis("x", hz, hx, nx, rng)
        if xb is not None:
            candidates.append(xb)
        zb = search_basis("z", hx, hz, nx, rng)
        if zb is not None:
            candidates.append(zb)

        if not candidates:
            fail("no witness found")

        candidates.sort(key=lambda c: (c["upper_bound"], c["basis"]))
        result = candidates[0]
        print(json.dumps({
            "status": "completed",
            "basis": result["basis"],
            "vector": result["vector"],
            "upper_bound": result["upper_bound"],
        }, separators=(",", ":")))
    except Exception:
        fail("exception")


if __name__ == "__main__":
    main()
