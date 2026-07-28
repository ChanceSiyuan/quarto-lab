#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def project_path(path, must_exist):
    root = os.path.realpath(os.getcwd())
    full = os.path.realpath(os.path.abspath(path))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError("path is outside the current project directory")
    if must_exist and not os.path.exists(full):
        raise ValueError("input path does not exist")
    return full


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
            mask = 0
            if len(row) != n:
                raise ValueError("dense row length does not match n_cols")
            for i, bit in enumerate(row):
                if bit:
                    mask |= 1 << i
            rows.append(mask)
        return n, rows

    if {"num_cols", "rows"} <= set(obj):
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            mask = 0
            prev = -1
            for col in row:
                col = int(col)
                if col <= prev or col < 0 or col >= n:
                    raise ValueError("sparse rows must be strictly increasing column lists")
                mask |= 1 << col
                prev = col
            rows.append(mask)
        return n, rows

    raise ValueError("unsupported matrix JSON format")


def rref_rows(rows, n):
    rows = [r for r in rows if r]
    out = []
    pivots = []
    rank = 0

    for col in range(n):
        bit = 1 << col
        pivot = None
        for i in range(rank, len(rows)):
            if rows[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & bit):
                rows[i] ^= rows[rank]
        out.append(rows[rank])
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break

    return out, pivots


def reduce_by_rref(v, basis, pivots):
    for row, col in zip(basis, pivots):
        if v & (1 << col):
            v ^= row
    return v


def in_rowspace(v, basis, pivots):
    return reduce_by_rref(v, basis, pivots) == 0


def nullspace_basis(rows, n):
    rr, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    basis = []
    for free_col in range(n):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        for row, pivot_col in zip(rr, pivots):
            if row & (1 << free_col):
                v |= 1 << pivot_col
        basis.append(v)
    return basis


def syndrome_zero(v, checks):
    for row in checks:
        if (v & row).bit_count() & 1:
            return False
    return True


def mask_to_vector(v, n):
    return [(v >> i) & 1 for i in range(n)]


def greedy_stabilizer_descent(v, stabilizers, rng, rounds):
    if not stabilizers:
        return v

    rows = sorted((r for r in stabilizers if r), key=lambda x: x.bit_count())
    best = v
    best_w = v.bit_count()

    for _ in range(rounds):
        changed = False
        scan = rows[:]
        rng.shuffle(scan)
        for row in scan:
            trial = v ^ row
            tw = trial.bit_count()
            if tw < v.bit_count():
                v = trial
                changed = True
                if tw < best_w:
                    best = trial
                    best_w = tw
        if not changed:
            break
    return best


def verified(v, kernel_checks, stabilizer_rref, stabilizer_pivots):
    return v != 0 and syndrome_zero(v, kernel_checks) and not in_rowspace(
        v, stabilizer_rref, stabilizer_pivots
    )


def side_search(label, kernel_checks, stabilizers, n, rng, deadline):
    kernel = nullspace_basis(kernel_checks, n)
    stab_rref, stab_pivots = rref_rows(stabilizers, n)

    logical = []
    for v in kernel:
        if reduce_by_rref(v, stab_rref, stab_pivots):
            logical.append(v)
    if not logical:
        return None

    logical.sort(key=lambda x: x.bit_count())
    kernel_by_weight = sorted(kernel, key=lambda x: x.bit_count())
    stabilizers_by_weight = sorted((r for r in stabilizers if r), key=lambda x: x.bit_count())

    best = None
    for seed in logical[: min(len(logical), 32)]:
        v = greedy_stabilizer_descent(seed, stabilizers_by_weight, rng, 3)
        if verified(v, kernel_checks, stab_rref, stab_pivots):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    attempts = 0
    max_attempts = max(250, min(8000, 80 * (len(logical) + 1)))
    while attempts < max_attempts and time.monotonic() < deadline:
        attempts += 1
        v = rng.choice(logical)

        # Random information-set style mixing in the kernel.  The bias keeps
        # samples sparse while still moving across logical cosets.
        pool = kernel_by_weight[: min(len(kernel_by_weight), max(24, n // 2 + 1))]
        flips = 1 + rng.randrange(max(1, min(10, len(pool))))
        for _ in range(flips):
            if rng.random() < 0.55:
                v ^= rng.choice(pool)

        if reduce_by_rref(v, stab_rref, stab_pivots) == 0:
            continue

        rounds = 2 + (attempts % 4)
        v = greedy_stabilizer_descent(v, stabilizers_by_weight, rng, rounds)

        if verified(v, kernel_checks, stab_rref, stab_pivots):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    if best is None:
        return None
    return {"basis": label, "mask": best, "weight": best.bit_count()}


def main():
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx_path = project_path(args.hx, True)
        hz_path = project_path(args.hz, True)
        output_dir = project_path(args.output_dir, False)

        nx, hx = load_matrix(hx_path)
        nz, hz = load_matrix(hz_path)
        if nx != nz:
            raise ValueError("Hx and Hz have different numbers of columns")
        n = nx

        os.makedirs(output_dir, exist_ok=True)
        rng = random.Random(args.seed)
        deadline = time.monotonic() + 8.0

        results = []
        x = side_search("x", hz, hx, n, rng, deadline)
        if x is not None:
            results.append(x)
        z = side_search("z", hx, hz, n, rng, deadline)
        if z is not None:
            results.append(z)

        if results:
            best = min(results, key=lambda item: (item["weight"], item["basis"]))
            result = {
                "status": "completed",
                "basis": best["basis"],
                "vector": mask_to_vector(best["mask"], n),
                "upper_bound": best["weight"],
            }
        else:
            result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
