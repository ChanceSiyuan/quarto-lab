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
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_rows = int(obj["n_rows"])
        n_cols = int(obj["n_cols"])
        data = obj["data"]
        if len(data) != n_rows:
            raise ValueError("dense matrix row count mismatch")
        rows = []
        for row in data:
            if len(row) != n_cols:
                raise ValueError("dense matrix column count mismatch")
            mask = 0
            for j, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if bit:
                    mask |= 1 << j
            rows.append(mask)
        return rows, n_cols

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for inds in obj["rows"]:
            prev = -1
            mask = 0
            for j in inds:
                j = int(j)
                if j <= prev or j < 0 or j >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing valid indices")
                mask |= 1 << j
                prev = j
            rows.append(mask)
        return rows, n_cols

    raise ValueError("unrecognized matrix JSON format")


def gf2_basis(rows):
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
    for p in sorted(list(basis)):
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= basis[p]
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


def syndrome_zero(vec, checks):
    for row in checks:
        if (row & vec).bit_count() & 1:
            return False
    return True


def nullspace_basis(rows, n_cols):
    basis = gf2_basis(rows)
    pivots = set(basis)
    free_cols = [j for j in range(n_cols) if j not in pivots]
    out = []
    for free in free_cols:
        x = 1 << free
        for pivot, row in basis.items():
            if (row >> free) & 1:
                x |= 1 << pivot
        out.append(x)
    return out


def mask_to_list(mask, n_cols):
    return [(mask >> j) & 1 for j in range(n_cols)]


def verified(vec, checks, stabilizer_basis):
    return vec != 0 and syndrome_zero(vec, checks) and not in_rowspace(vec, stabilizer_basis)


def reduce_by_stabilizers(vec, stabilizers, rng, passes):
    if not stabilizers:
        return vec
    v = vec
    best_w = v.bit_count()
    rows = list(stabilizers)
    for _ in range(passes):
        rng.shuffle(rows)
        improved = False
        for row in rows:
            cand = v ^ row
            w = cand.bit_count()
            if w < best_w or (w == best_w and rng.random() < 0.015):
                v = cand
                best_w = w
                improved = True
        if not improved and rng.random() < 0.35:
            row = rows[rng.randrange(len(rows))]
            cand = v ^ row
            if cand.bit_count() <= best_w + 2:
                v = cand
                best_w = v.bit_count()
    return v


def random_kernel_vector(kernel, rng):
    if not kernel:
        return 0
    m = len(kernel)
    rates = (0.5, 0.25, 0.125, 0.0625)
    p = rates[rng.randrange(len(rates))]
    v = 0
    picked = False
    order = list(range(m))
    rng.shuffle(order)
    for i in order:
        if rng.random() < p:
            v ^= kernel[i]
            picked = True
    if not picked:
        v = kernel[rng.randrange(m)]
    return v


def search_basis(name, checks, stabilizers, n_cols, seed):
    rng = random.Random(seed)
    stabilizer_basis = gf2_basis(stabilizers)
    kernel = nullspace_basis(checks, n_cols)
    if not kernel:
        return None

    best = None
    best_w = n_cols + 1
    attempts = max(512, min(20000, 80 * (len(kernel) + len(stabilizers) + 1)))
    passes = 4 if len(stabilizers) > 250 else 8

    seeds = list(kernel)
    rng.shuffle(seeds)
    seeds = seeds[: min(len(seeds), 256)]

    for t in range(attempts + len(seeds)):
        if t < len(seeds):
            v = seeds[t]
            for _ in range(3):
                if rng.random() < 0.5:
                    v ^= random_kernel_vector(kernel, rng)
        else:
            v = random_kernel_vector(kernel, rng)

        if in_rowspace(v, stabilizer_basis):
            continue
        v = reduce_by_stabilizers(v, stabilizers, rng, passes)
        if verified(v, checks, stabilizer_basis):
            w = v.bit_count()
            if w < best_w:
                best = v
                best_w = w
                if best_w <= 1:
                    break

    if best is None:
        return None
    return {"basis": name, "vector": mask_to_list(best, n_cols), "upper_bound": best_w}


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        os.makedirs(args.output_dir, exist_ok=True)
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz column counts differ")
        n_cols = nx

        # X logicals commute with Z checks modulo X stabilizers; Z logicals are dual.
        x_res = search_basis("x", hz, hx, n_cols, args.seed ^ 0x58A7)
        z_res = search_basis("z", hx, hz, n_cols, args.seed ^ 0x5A3D)
        choices = [r for r in (x_res, z_res) if r is not None]
        if not choices:
            emit({"status": "not_found", "basis": None, "vector": [], "upper_bound": None})
            return 0
        best = min(choices, key=lambda r: (r["upper_bound"], r["basis"]))
        emit(
            {
                "status": "completed",
                "basis": best["basis"],
                "vector": best["vector"],
                "upper_bound": best["upper_bound"],
            }
        )
        return 0
    except Exception as exc:
        _ = exc
        emit({"status": "error", "basis": None, "vector": [], "upper_bound": None})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
