#!/usr/bin/env python3
import argparse
import json
import os
import random


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n_cols

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            last = -1
            for j in row:
                j = int(j)
                if j <= last or j < 0 or j >= n_cols:
                    raise ValueError("invalid sparse row")
                x |= 1 << j
                last = j
            rows.append(x)
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


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
                for q, other in list(basis.items()):
                    if q != p and ((other >> p) & 1):
                        basis[q] = other ^ x
                break
    return basis


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return y
        y ^= row
    return 0


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def in_kernel(x, check_rows):
    for row in check_rows:
        if (x & row).bit_count() & 1:
            return False
    return True


def nullspace_basis(check_rows, n_cols):
    rb = rref_basis(check_rows)
    pivots = set(rb)
    out = []
    for f in range(n_cols):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def verified(v, check_rows, stab_basis):
    return v != 0 and in_kernel(v, check_rows) and not in_rowspace(v, stab_basis)


def greedy_reduce(v, check_rows, stab_rows, stab_basis, rng, max_passes=8):
    if not verified(v, check_rows, stab_basis):
        return 0
    cur = v
    cur_w = cur.bit_count()
    rows = [r for r in stab_rows if r]

    for _ in range(max_passes):
        changed = False
        rng.shuffle(rows)
        for row in rows:
            cand = cur ^ row
            cand_w = cand.bit_count()
            if cand_w < cur_w and verified(cand, check_rows, stab_basis):
                cur = cand
                cur_w = cand_w
                changed = True
        if not changed:
            break
    return cur


def random_kernel_vector(kernel_basis, rng):
    m = len(kernel_basis)
    if m == 0:
        return 0

    mode = rng.random()
    v = 0
    if mode < 0.45:
        take = 1 + int(rng.expovariate(0.7))
        take = min(take, m)
        for idx in rng.sample(range(m), take):
            v ^= kernel_basis[idx]
    elif mode < 0.85:
        p = min(0.5, max(1.0 / m, 0.02 + 4.0 / (m + 8.0)))
        for row in kernel_basis:
            if rng.random() < p:
                v ^= row
    else:
        for row in kernel_basis:
            if rng.getrandbits(1):
                v ^= row
    return v


def search_basis(name, check_rows, stab_rows, n_cols, seed):
    rng = random.Random(seed)
    stab_basis = rref_basis(stab_rows)
    kernel_basis = nullspace_basis(check_rows, n_cols)
    if len(kernel_basis) <= len(stab_basis):
        return None

    best = None
    best_w = n_cols + 1

    def consider(v):
        nonlocal best, best_w
        if not verified(v, check_rows, stab_basis):
            return
        v = greedy_reduce(v, check_rows, stab_rows, stab_basis, rng)
        if v and verified(v, check_rows, stab_basis):
            w = v.bit_count()
            if w < best_w:
                best = v
                best_w = w

    order = list(kernel_basis)
    rng.shuffle(order)
    for v in order[: min(len(order), 256)]:
        consider(v)

    rank_gap = max(1, len(kernel_basis) - len(stab_basis))
    iterations = 1200 + 80 * min(n_cols, 200) + 200 * min(rank_gap, 20)
    iterations = min(iterations, 24000)
    stale = 0
    for _ in range(iterations):
        before = best_w
        consider(random_kernel_vector(kernel_basis, rng))
        if best_w < before:
            stale = 0
        else:
            stale += 1
        if best_w == 1 or (best is not None and stale > 5000):
            break

    if best is None:
        return None
    return {"basis": name, "vector_int": best, "upper_bound": best_w}


def bits_to_list(x, n_cols):
    return [int((x >> j) & 1) for j in range(n_cols)]


def run(args):
    hx_rows, nx = load_matrix(args.hx)
    hz_rows, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("HX and HZ have different numbers of columns")
    n = nx

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    sx = (int(args.seed) << 1) ^ 0x58A53
    sz = (int(args.seed) << 1) ^ 0xA57C9
    candidates = [
        search_basis("x", hz_rows, hx_rows, n, sx),
        search_basis("z", hx_rows, hz_rows, n, sz),
    ]
    candidates = [c for c in candidates if c is not None]
    if not candidates:
        return {
            "status": "not_found",
            "basis": None,
            "vector": [],
            "upper_bound": None,
        }

    best = min(candidates, key=lambda c: (c["upper_bound"], c["basis"]))
    return {
        "status": "completed",
        "basis": best["basis"],
        "vector": bits_to_list(best["vector_int"], n),
        "upper_bound": best["upper_bound"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        result = run(args)
    except Exception:
        result = {
            "status": "error",
            "basis": None,
            "vector": [],
            "upper_bound": None,
        }
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
