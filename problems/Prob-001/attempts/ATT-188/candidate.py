#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def fail(message=None):
    result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    if message:
        os.environ.setdefault("CANDIDATE_ERROR", message)
    print(json.dumps(result, separators=(",", ":")))
    sys.exit(0)


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
            mask = 0
            for j, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if bit:
                    mask |= 1 << j
            rows.append(mask)
        return rows, n_cols

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            mask = 0
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing valid indices")
                mask |= 1 << col
                last = col
            rows.append(mask)
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


def require_project_path(path, project_root):
    real = os.path.realpath(path)
    if os.path.commonpath([project_root, real]) != project_root:
        raise ValueError("path is outside the current project directory")
    return real


def rref(rows, n_cols):
    work = [r for r in rows if r]
    out = []
    pivots = []
    rank = 0
    for col in range(n_cols):
        pivot = None
        bit = 1 << col
        for i in range(rank, len(work)):
            if work[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        prow = work[rank]
        for i in range(len(work)):
            if i != rank and (work[i] & bit):
                work[i] ^= prow
        out.append(work[rank])
        pivots.append(col)
        rank += 1
        if rank == len(work):
            break
    return out, pivots


def reduce_by_basis(v, basis, pivots):
    for row, pivot in zip(basis, pivots):
        if v & (1 << pivot):
            v ^= row
    return v


def in_rowspace(v, basis, pivots):
    return reduce_by_basis(v, basis, pivots) == 0


def kernel_basis(rows, n_cols):
    rr, pivots = rref(rows, n_cols)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n_cols) if c not in pivot_set]
    basis = []
    for free in free_cols:
        v = 1 << free
        fbit = 1 << free
        for row, pivot in zip(rr, pivots):
            if row & fbit:
                v |= 1 << pivot
        basis.append(v)
    return basis


def random_kernel_vector(kbasis, rng):
    v = 0
    # Bias half the starts toward sparse combinations and half toward broad ones.
    if rng.getrandbits(1) and len(kbasis) > 8:
        take = 1 + rng.randrange(min(len(kbasis), 16))
        for idx in rng.sample(range(len(kbasis)), take):
            v ^= kbasis[idx]
    else:
        for row in kbasis:
            if rng.getrandbits(1):
                v ^= row
    return v


def greedy_coset_descent(v, stabilizers, rng, passes=8):
    if not stabilizers:
        return v
    best = v
    best_w = v.bit_count()
    rows = list(stabilizers)
    for _ in range(passes):
        rng.shuffle(rows)
        changed = False
        for row in rows:
            cand = best ^ row
            w = cand.bit_count()
            if w < best_w or (w == best_w and rng.randrange(8) == 0):
                best = cand
                changed = w < best_w
                best_w = w
        if not changed:
            break
    return best


def randomized_witness(check_rows, stabilizer_rows, n_cols, label, seed):
    rng = random.Random(seed)
    kbasis = kernel_basis(check_rows, n_cols)
    if not kbasis:
        return None

    stab_basis, stab_pivots = rref(stabilizer_rows, n_cols)
    candidates = []
    order = list(kbasis)
    rng.shuffle(order)
    candidates.extend(order[: min(len(order), 64)])

    attempts = max(256, min(4096, 32 * len(kbasis)))
    for _ in range(attempts):
        candidates.append(random_kernel_vector(kbasis, rng))

    best = None
    best_w = n_cols + 1
    for v in candidates:
        if v == 0 or in_rowspace(v, stab_basis, stab_pivots):
            continue
        v = greedy_coset_descent(v, stabilizer_rows, rng)
        if v and not in_rowspace(v, stab_basis, stab_pivots):
            w = v.bit_count()
            if w < best_w:
                best = v
                best_w = w

    if best is None:
        return None
    return {"basis": label, "mask": best, "upper_bound": best_w}


def commutes(v, checks):
    return all(((row & v).bit_count() & 1) == 0 for row in checks)


def mask_to_vector(v, n_cols):
    return [(v >> i) & 1 for i in range(n_cols)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        project_root = os.path.realpath(os.getcwd())
        hx_path = require_project_path(args.hx, project_root)
        hz_path = require_project_path(args.hz, project_root)
        require_project_path(args.output_dir, project_root)

        hx, nx = load_matrix(hx_path)
        hz, nz = load_matrix(hz_path)
        if nx != nz:
            fail("Hx and Hz have different numbers of columns")
        n_cols = nx

        found = []
        xw = randomized_witness(hz, hx, n_cols, "x", args.seed ^ 0x58)
        zw = randomized_witness(hx, hz, n_cols, "z", args.seed ^ 0x5A)
        if xw is not None:
            found.append(xw)
        if zw is not None:
            found.append(zw)
        if not found:
            fail("no logical witness found")

        found.sort(key=lambda item: (item["upper_bound"], item["basis"]))
        chosen = found[0]
        v = chosen["mask"]
        if chosen["basis"] == "x":
            check_rows, stab_rows = hz, hx
        else:
            check_rows, stab_rows = hx, hz
        stab_basis, stab_pivots = rref(stab_rows, n_cols)
        if not commutes(v, check_rows) or in_rowspace(v, stab_basis, stab_pivots):
            fail("internal verification rejected witness")

        result = {
            "status": "completed",
            "basis": chosen["basis"],
            "vector": mask_to_vector(v, n_cols),
            "upper_bound": int(chosen["upper_bound"]),
        }
        print(json.dumps(result, separators=(",", ":")))
    except Exception as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()
