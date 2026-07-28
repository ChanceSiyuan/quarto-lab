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
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            mask = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for cols in obj["rows"]:
            last = -1
            mask = 0
            for col in cols:
                col = int(col)
                if col <= last or col < 0 or col >= n:
                    raise ValueError("sparse rows must be strictly increasing valid indices")
                mask |= 1 << col
                last = col
            rows.append(mask)
        return rows, n

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        return load_matrix({"dense_binary_matrix": obj})
    raise ValueError("unknown matrix JSON format")


def weight(x):
    return x.bit_count()


def rref(rows):
    basis = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        row = basis[p]
        for q in sorted(basis, reverse=True):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    pivots = sorted(basis, reverse=True)
    return [basis[p] for p in pivots], pivots


def reduce_by_basis(x, basis_rows):
    y = int(x)
    for row in basis_rows:
        if y and ((y >> (row.bit_length() - 1)) & 1):
            y ^= row
    return y


def in_rowspace(x, basis_rows):
    return reduce_by_basis(x, basis_rows) == 0


def kernel_basis(rows, n):
    rbasis, pivots = rref(rows)
    pivot_set = set(pivots)
    by_pivot = {row.bit_length() - 1: row for row in rbasis}
    out = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for p in pivots:
            if (by_pivot[p] >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, checks):
    for row in checks:
        if weight(v & row) & 1:
            return False
    return True


def mask_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def quotient_logical_basis(kernel, stab_basis):
    qrows = []
    reps = []
    for v in sorted(kernel, key=weight):
        key = reduce_by_basis(v, stab_basis)
        if key and not in_rowspace(key, qrows):
            reps.append(v)
            qrows, _ = rref(qrows + [key])
    return reps


def greedy_reduce(v, rows, rng, rounds=3):
    cur = v
    best_w = weight(cur)
    pool = list(rows)
    pool.sort(key=weight)
    for _ in range(rounds):
        changed = False
        rng.shuffle(pool)
        pool.sort(key=lambda r: weight(cur ^ r) - best_w)
        for row in pool:
            cand = cur ^ row
            cw = weight(cand)
            if cw < best_w:
                cur, best_w = cand, cw
                changed = True
        if not changed:
            break
    return cur


def randomized_coset_search(kernel_checks, stabilizers, n, rng, deadline):
    stab_basis, _ = rref(stabilizers)
    kbas = kernel_basis(kernel_checks, n)
    logical_reps = quotient_logical_basis(kbas, stab_basis)
    if not logical_reps:
        return None

    stab_pool = list(set([r for r in stabilizers + stab_basis if r]))
    stab_pool.sort(key=weight)
    best = None
    best_w = n + 1

    seeds = list(logical_reps)
    for rep in logical_reps:
        seeds.append(greedy_reduce(rep, stab_pool, rng, rounds=4))

    attempts = 0
    while time.monotonic() < deadline:
        if attempts < len(seeds):
            v = seeds[attempts]
        else:
            v = 0
            take = 1 + rng.randrange(max(1, min(len(logical_reps), 8)))
            for rep in rng.sample(logical_reps, take):
                if rng.getrandbits(1):
                    v ^= rep
            if v == 0:
                v = rng.choice(logical_reps)
            for row in stab_pool:
                if rng.random() < 0.08:
                    v ^= row
        attempts += 1

        v = greedy_reduce(v, stab_pool, rng, rounds=5)
        if v and not in_rowspace(v, stab_basis) and syndrome_zero(v, kernel_checks):
            w = weight(v)
            if w < best_w:
                best, best_w = v, w
                if best_w <= 1:
                    break

    return best


def verified(v, basis, hx, hz, hx_basis, hz_basis):
    if not v:
        return False
    if basis == "x":
        return syndrome_zero(v, hz) and not in_rowspace(v, hx_basis)
    return syndrome_zero(v, hx) and not in_rowspace(v, hz_basis)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz have different column counts")
        n = nx
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        hx_basis, _ = rref(hx)
        hz_basis, _ = rref(hz)
        deadline = time.monotonic() + float(os.environ.get("CANDIDATE_TIME_LIMIT", "25.0"))

        choices = [("x", hz, hx), ("z", hx, hz)]
        rng.shuffle(choices)
        best_basis = None
        best_v = None
        best_w = n + 1

        while time.monotonic() < deadline:
            progressed = False
            for basis, checks, stabs in choices:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sub_deadline = time.monotonic() + max(0.05, remaining / 2.0)
                v = randomized_coset_search(checks, stabs, n, rng, sub_deadline)
                if v is None:
                    continue
                progressed = True
                if verified(v, basis, hx, hz, hx_basis, hz_basis):
                    w = weight(v)
                    if w < best_w:
                        best_basis, best_v, best_w = basis, v, w
            if best_v is not None or not progressed:
                break

        if best_v is not None and verified(best_v, best_basis, hx, hz, hx_basis, hz_basis):
            result = {
                "status": "completed",
                "basis": best_basis,
                "vector": mask_to_list(best_v, n),
                "upper_bound": best_w,
            }
        else:
            result["basis"] = choices[0][0]
            result["vector"] = [0] * n
    except Exception:
        pass

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
