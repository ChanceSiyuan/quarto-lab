#!/usr/bin/env python3
"""Randomized CSS logical witness search.

This entrypoint returns only verified upper-bound witnesses.  It does not try
to prove minimum distance.
"""

import argparse
import json
import os
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError(f"{path}: dense row has wrong length")
            bits = 0
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    bits |= 1 << i
            rows.append(bits)
        return n_cols, rows

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError(f"{path}: sparse row indices are invalid")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return n_cols, rows

    raise ValueError(f"{path}: unsupported matrix JSON format")


def gf2_basis(rows):
    basis = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            if p not in basis:
                basis[p] = x
                break
            x ^= basis[p]
    for p in sorted(basis):
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= basis[p]
    return basis


def gf2_rank(rows):
    return len(gf2_basis(rows))


def in_rowspace(vec, basis):
    x = int(vec)
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        x ^= b
    return True


def nullspace_basis(rows, n_cols):
    pivots = gf2_basis(rows)
    pivot_cols = set(pivots)
    free_cols = [c for c in range(n_cols) if c not in pivot_cols]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in pivots.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(vec, checks):
    return all(((vec & row).bit_count() & 1) == 0 for row in checks)


def to_binary_list(vec, n_cols):
    return [(vec >> i) & 1 for i in range(n_cols)]


def verify_witness(vec, kernel_checks, stabilizers, stab_basis):
    return vec != 0 and syndrome_zero(vec, kernel_checks) and not in_rowspace(vec, stab_basis)


def random_kernel_vector(null_basis, rng):
    if not null_basis:
        return 0

    mode = rng.randrange(4)
    if mode == 0:
        p = 0.08
    elif mode == 1:
        p = 0.18
    elif mode == 2:
        p = 0.5
    else:
        p = min(0.9, 2.0 / max(1, len(null_basis)))

    v = 0
    for b in null_basis:
        if rng.random() < p:
            v ^= b
    if v == 0:
        v = rng.choice(null_basis)
    return v


def greedy_reduce(vec, stabilizers, rng):
    if not stabilizers:
        return vec

    current = vec
    cur_w = current.bit_count()
    rows = list(stabilizers)
    improved = True
    passes = 0
    while improved and passes < 10:
        improved = False
        passes += 1
        if len(rows) > 768:
            order = rng.sample(rows, 768)
        else:
            order = rows[:]
            rng.shuffle(order)
        for row in order:
            cand = current ^ row
            w = cand.bit_count()
            if w < cur_w:
                current = cand
                cur_w = w
                improved = True
    return current


def perturb_by_stabilizers(vec, stabilizers, rng):
    if not stabilizers:
        return vec
    out = vec
    flips = 1 + rng.randrange(min(8, len(stabilizers)))
    for _ in range(flips):
        out ^= rng.choice(stabilizers)
    return out


def search_basis(name, kernel_checks, stabilizers, n_cols, rng, deadline):
    stab_basis = gf2_basis(stabilizers)
    null_basis = nullspace_basis(kernel_checks, n_cols)
    if len(null_basis) <= len(stab_basis):
        return None

    best = None

    # Try some low-complexity kernel generators before fully random sampling.
    seeds = list(null_basis)
    rng.shuffle(seeds)
    for v in seeds[: min(len(seeds), 256)]:
        if time.monotonic() >= deadline:
            break
        if not in_rowspace(v, stab_basis):
            v = greedy_reduce(v, stabilizers, rng)
            if verify_witness(v, kernel_checks, stabilizers, stab_basis):
                if best is None or v.bit_count() < best.bit_count():
                    best = v

    attempts = max(1200, 80 * (len(null_basis) + len(stabilizers) + 1))
    for i in range(attempts):
        if time.monotonic() >= deadline:
            break
        v = random_kernel_vector(null_basis, rng)
        if i % 3 == 0 and best is not None:
            v ^= best
            if v == 0:
                v = random_kernel_vector(null_basis, rng)
        if in_rowspace(v, stab_basis):
            continue

        v = greedy_reduce(v, stabilizers, rng)
        for _ in range(3):
            trial = greedy_reduce(perturb_by_stabilizers(v, stabilizers, rng), stabilizers, rng)
            if trial.bit_count() < v.bit_count():
                v = trial

        if verify_witness(v, kernel_checks, stabilizers, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v
                if best.bit_count() <= 1:
                    break

    if best is None:
        return None
    return {
        "status": "completed",
        "basis": name,
        "vector": to_binary_list(best, n_cols),
        "upper_bound": best.bit_count(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    os.makedirs(args.output_dir, exist_ok=True)
    nx, hx = load_matrix(args.hx)
    nz, hz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("hx and hz must have the same number of columns")
    n_cols = nx

    rng = random.Random(args.seed)
    deadline = time.monotonic() + 8.0

    # X logicals are in ker(Hz) modulo row(Hx); Z logicals are in ker(Hx)
    # modulo row(Hz).
    order = [("x", hz, hx), ("z", hx, hz)]
    rng.shuffle(order)
    results = []
    for spec in order:
        found = search_basis(*spec, n_cols=n_cols, rng=rng, deadline=deadline)
        if found is not None:
            results.append(found)

    if results:
        results.sort(key=lambda r: (r["upper_bound"], r["basis"]))
        result = results[0]
    else:
        result = {"status": "not_found", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            json.dumps(
                {"status": "error", "basis": None, "vector": [], "upper_bound": None},
                separators=(",", ":"),
            ),
            flush=True,
        )
        print(str(exc), file=sys.stderr)
        sys.exit(1)
