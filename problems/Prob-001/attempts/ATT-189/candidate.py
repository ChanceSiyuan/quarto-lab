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
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError("dense row length does not match n_cols")
            mask = 0
            for j, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if bit:
                    mask |= 1 << j
            rows.append(mask)
        if len(rows) != int(obj["n_rows"]):
            raise ValueError("dense matrix row count does not match n_rows")
        return rows, n_cols

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            prev = -1
            mask = 0
            for j in row:
                j = int(j)
                if j <= prev or j < 0 or j >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing column indices")
                mask |= 1 << j
                prev = j
            rows.append(mask)
        return rows, n_cols

    raise ValueError("unrecognized matrix JSON format")


def weight(x):
    return int(x.bit_count())


def rref(rows, n_cols):
    rows = [int(r) for r in rows if r]
    pivots = []
    r = 0
    for col in range(n_cols):
        pivot = None
        bit = 1 << col
        for i in range(r, len(rows)):
            if rows[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        rows[r], rows[pivot] = rows[pivot], rows[r]
        for i in range(len(rows)):
            if i != r and (rows[i] & bit):
                rows[i] ^= rows[r]
        pivots.append(col)
        r += 1
        if r == len(rows):
            break
    return rows[:r], pivots


def in_rowspace(vec, basis):
    x = int(vec)
    for row in basis:
        y = x ^ row
        if y < x:
            x = y
    return x == 0


def nullspace_basis(rows, n_cols):
    rr, pivots = rref(rows, n_cols)
    pivot_set = set(pivots)
    basis = []
    for free_col in range(n_cols):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        for row, pivot_col in zip(rr, pivots):
            if row & (1 << free_col):
                v |= 1 << pivot_col
        basis.append(v)
    return basis


def dot_rows_zero(vec, checks):
    return all(((vec & row).bit_count() & 1) == 0 for row in checks)


def mask_to_list(vec, n_cols):
    return [1 if (vec >> j) & 1 else 0 for j in range(n_cols)]


def random_combo(vectors, rng, p_num=1, p_den=2):
    x = 0
    used = False
    for v in vectors:
        if rng.randrange(p_den) < p_num:
            x ^= v
            used = True
    if not used and vectors:
        x = rng.choice(vectors)
    return x


def reduce_by_stabilizers(vec, stabilizers, rng, passes=8):
    if not stabilizers:
        return vec
    best = vec
    ordered = list(stabilizers)
    for _ in range(passes):
        changed = False
        rng.shuffle(ordered)
        for row in ordered:
            cand = best ^ row
            if weight(cand) < weight(best):
                best = cand
                changed = True
        if not changed:
            break
    return best


def search_basis(name, commute_checks, stabilizers, n_cols, rng):
    stab_basis, _ = rref(stabilizers, n_cols)
    kernel = nullspace_basis(commute_checks, n_cols)
    if not kernel:
        return None

    candidates = []
    for v in kernel:
        if v and not in_rowspace(v, stab_basis):
            candidates.append(v)

    # Random low-density kernel combinations are cheap and often expose lighter
    # witnesses than a raw nullspace vector, especially on sparse LDPC inputs.
    trials = max(256, min(12000, 80 * (len(kernel) + len(stab_basis) + 1)))
    densities = [(1, 8), (1, 4), (1, 2), (3, 4)]
    for t in range(trials):
        p_num, p_den = densities[t % len(densities)]
        v = random_combo(kernel, rng, p_num, p_den)
        if v and not in_rowspace(v, stab_basis):
            candidates.append(v)

    best = None
    for v in candidates:
        v = reduce_by_stabilizers(v, stabilizers, rng)
        if v and dot_rows_zero(v, commute_checks) and not in_rowspace(v, stab_basis):
            if best is None or weight(v) < weight(best):
                best = v
    if best is None:
        return None
    return {"basis": name, "vector": best, "upper_bound": weight(best)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz must have the same number of columns")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        searches = [
            search_basis("x", hz, hx, nx, rng),
            search_basis("z", hx, hz, nx, rng),
        ]
        hits = [s for s in searches if s is not None]
        if not hits:
            result = {"status": "not_found", "basis": "x", "vector": [], "upper_bound": None}
        else:
            hit = min(hits, key=lambda s: (s["upper_bound"], 0 if s["basis"] == "x" else 1))
            result = {
                "status": "completed",
                "basis": hit["basis"],
                "vector": mask_to_list(hit["vector"], nx),
                "upper_bound": hit["upper_bound"],
            }
    except Exception:
        result = {"status": "error", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
