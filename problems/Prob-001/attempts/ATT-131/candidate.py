#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        rows = obj
        n_cols = max((len(r) for r in rows), default=0)
        return [row_to_int_dense(r) for r in rows], n_cols

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n_cols = int(obj["n_cols"])
        data = obj["data"]
        if len(data) != int(obj["n_rows"]):
            raise ValueError("dense matrix row count does not match n_rows")
        return [row_to_int_dense(r, n_cols) for r in data], n_cols

    if "num_cols" in obj and "rows" in obj:
        n_cols = int(obj["num_cols"])
        return [row_to_int_sparse(r, n_cols) for r in obj["rows"]], n_cols

    if "n_cols" in obj and "rows" in obj:
        n_cols = int(obj["n_cols"])
        return [row_to_int_dense(r, n_cols) for r in obj["rows"]], n_cols

    raise ValueError("unrecognized matrix JSON format")


def row_to_int_dense(row, n_cols=None):
    if n_cols is None:
        n_cols = len(row)
    if len(row) != n_cols:
        raise ValueError("dense row length does not match n_cols")
    x = 0
    for i, bit in enumerate(row):
        if int(bit) & 1:
            x |= 1 << i
    return x


def row_to_int_sparse(row, n_cols):
    x = 0
    prev = -1
    for col in row:
        col = int(col)
        if col <= prev or col < 0 or col >= n_cols:
            raise ValueError("sparse row indices must be strictly increasing and in range")
        x |= 1 << col
        prev = col
    return x


def rref_rows(rows):
    basis = {}
    for value in rows:
        x = int(value)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        row = basis[p]
        for q in sorted(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    return basis


def reduce_with_basis(value, basis):
    x = int(value)
    while x:
        p = x.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return x
        x ^= row
    return 0


def in_span(value, basis):
    return reduce_with_basis(value, basis) == 0


def nullspace_basis(rows, n_cols):
    rref = rref_rows(rows)
    pivots = set(rref)
    free_cols = [c for c in range(n_cols) if c not in pivots]
    out = []
    for free in free_cols:
        v = 1 << free
        for p, row in rref.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def quotient_logical_seeds(kernel_rows, stabilizer_rows):
    span = rref_rows(stabilizer_rows)
    seeds = []
    for v in sorted(kernel_rows, key=int.bit_count):
        if v and not in_span(v, span):
            seeds.append(v)
            span = rref_rows(list(span.values()) + [v])
    return seeds


def vector_to_list(value, n_cols):
    return [(value >> i) & 1 for i in range(n_cols)]


def commutes(check_rows, value):
    return all(((r & value).bit_count() & 1) == 0 for r in check_rows)


def is_witness(value, kernel_checks, stabilizer_basis):
    if value == 0:
        return False
    return commutes(kernel_checks, value) and not in_span(value, stabilizer_basis)


def greedy_reduce(value, stabilizers, rng, passes=8):
    x = value
    rows = [r for r in stabilizers if r]
    if not rows:
        return x
    for _ in range(passes):
        changed = False
        rng.shuffle(rows)
        for r in rows:
            y = x ^ r
            if y.bit_count() < x.bit_count():
                x = y
                changed = True
        if not changed:
            break
    return x


def random_candidate(seeds, stabilizers, rng):
    v = 0
    if len(seeds) == 1:
        v = seeds[0]
    else:
        for s in seeds:
            if rng.getrandbits(1):
                v ^= s
        if v == 0:
            v = rng.choice(seeds)

    if stabilizers:
        # A light random stabilizer mask starts the local search in a different
        # representative of the same logical coset without changing validity.
        for r in rng.sample(stabilizers, min(len(stabilizers), 48)):
            if rng.random() < 0.18:
                v ^= r
    return v


def search_basis(name, kernel_checks, stabilizers, n_cols, rng, trials):
    stabilizer_basis = rref_rows(stabilizers)
    seeds = quotient_logical_seeds(nullspace_basis(kernel_checks, n_cols), stabilizers)
    if not seeds:
        return None

    best = None
    starters = sorted(seeds, key=int.bit_count)[: min(len(seeds), 32)]
    for s in starters:
        v = greedy_reduce(s, stabilizers, rng, passes=10)
        if is_witness(v, kernel_checks, stabilizer_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for _ in range(max(0, trials)):
        v = random_candidate(seeds, stabilizers, rng)
        v = greedy_reduce(v, stabilizers, rng, passes=8)
        if is_witness(v, kernel_checks, stabilizer_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    if best is None:
        return None
    return {"basis": name, "vector": vector_to_list(best, n_cols), "upper_bound": best.bit_count()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n_cols = max(nx, nz)
        hx = [r & ((1 << n_cols) - 1) for r in hx]
        hz = [r & ((1 << n_cols) - 1) for r in hz]
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        trials = max(256, min(12000, 96 * n_cols))
        x_result = search_basis("x", hz, hx, n_cols, rng, trials)
        z_result = search_basis("z", hx, hz, n_cols, rng, trials)
        results = [r for r in (x_result, z_result) if r is not None]

        if results:
            result = min(results, key=lambda r: (r["upper_bound"], r["basis"]))
            result = {
                "status": "completed",
                "basis": result["basis"],
                "vector": result["vector"],
                "upper_bound": result["upper_bound"],
            }
        else:
            result = {"status": "not_found", "basis": "x", "vector": [], "upper_bound": None}
    except Exception as exc:
        result = {"status": "error", "basis": "x", "vector": [], "upper_bound": None}
        print(json.dumps(result, separators=(",", ":")))
        print(str(exc), file=sys.stderr)
        return 0

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
