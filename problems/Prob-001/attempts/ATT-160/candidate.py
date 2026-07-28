#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            if len(row) != n_cols:
                raise ValueError("dense row length does not match n_cols")
            for i, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if bit:
                    bits |= 1 << i
            rows.append(bits)
        return rows, n_cols

    if "num_cols" in obj and "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            prev = -1
            bits = 0
            for idx in row:
                idx = int(idx)
                if idx <= prev or idx < 0 or idx >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing indices")
                bits |= 1 << idx
                prev = idx
            rows.append(bits)
        return rows, n_cols

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
        row = basis[p]
        for q, other in list(basis.items()):
            if q != p and ((other >> p) & 1):
                basis[q] = other ^ row
    return basis


def in_rowspace(vec, basis):
    x = vec
    while x:
        p = x.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return False
        x ^= row
    return True


def nullspace_basis(rows, n_cols):
    pivots = rref_basis(rows)
    pivot_cols = set(pivots)
    out = []
    for free in range(n_cols):
        if free in pivot_cols:
            continue
        v = 1 << free
        for p, row in pivots.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(vec, checks):
    return all(((vec & row).bit_count() & 1) == 0 for row in checks)


def int_to_bits(vec, n_cols):
    return [(vec >> i) & 1 for i in range(n_cols)]


def random_kernel_vector(kernel_basis, rng):
    v = 0
    # A light-tailed subset gives sparse starting points more often, while the
    # fallback full Bernoulli pass keeps the search from staying too local.
    if kernel_basis and rng.random() < 0.65:
        draws = 1 + int(rng.expovariate(0.35))
        for _ in range(min(draws, len(kernel_basis))):
            v ^= rng.choice(kernel_basis)
    else:
        for row in kernel_basis:
            if rng.getrandbits(1):
                v ^= row
    return v


def reduce_by_stabilizers(vec, stabilizers, rng, passes):
    cur = vec
    cur_w = cur.bit_count()
    if not stabilizers:
        return cur
    rows = [r for r in stabilizers if r]
    for _ in range(passes):
        improved = False
        rng.shuffle(rows)
        for row in rows:
            nxt = cur ^ row
            nxt_w = nxt.bit_count()
            if nxt_w < cur_w or (nxt_w == cur_w and rng.random() < 0.015):
                was_better = nxt_w < cur_w
                cur, cur_w = nxt, nxt_w
                if was_better:
                    improved = True
        if not improved and rng.random() < 0.7:
            break
    return cur


def certify(vec, kernel_checks, stabilizer_basis):
    return vec != 0 and syndrome_zero(vec, kernel_checks) and not in_rowspace(vec, stabilizer_basis)


def search_basis(name, kernel_checks, stabilizers, n_cols, rng, deadline):
    kernel_basis = nullspace_basis(kernel_checks, n_cols)
    stabilizer_basis = rref_basis(stabilizers)
    if len(kernel_basis) <= len(stabilizer_basis):
        return None

    best = None
    attempts = 0
    max_attempts = 12000 + 80 * n_cols + 120 * len(kernel_basis)
    passes = 3 + min(24, max(1, len(stabilizers) // 16))

    seeded = list(kernel_basis)
    rng.shuffle(seeded)
    while attempts < max_attempts and time.monotonic() < deadline:
        attempts += 1
        if seeded:
            cand = seeded.pop()
        else:
            cand = random_kernel_vector(kernel_basis, rng)
        if cand == 0 or in_rowspace(cand, stabilizer_basis):
            continue

        cand = reduce_by_stabilizers(cand, stabilizers, rng, passes)
        if not certify(cand, kernel_checks, stabilizer_basis):
            continue
        if best is None or cand.bit_count() < best.bit_count():
            best = cand
            if best.bit_count() <= 1:
                break

    if best is None:
        return None
    return {
        "basis": name,
        "vector": int_to_bits(best, n_cols),
        "upper_bound": best.bit_count(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz must have the same number of columns")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        deadline = time.monotonic() + 25.0
        order = [("x", hz, hx), ("z", hx, hz)]
        rng.shuffle(order)

        best = None
        for name, kernel_checks, stabilizers in order:
            found = search_basis(name, kernel_checks, stabilizers, nx, rng, deadline)
            if found and (best is None or found["upper_bound"] < best["upper_bound"]):
                best = found

        if best is None:
            result = {"status": "failed", "basis": order[0][0], "vector": [], "upper_bound": None}
        else:
            result = {
                "status": "completed",
                "basis": best["basis"],
                "vector": best["vector"],
                "upper_bound": best["upper_bound"],
            }
    except Exception:
        result = {"status": "error", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
