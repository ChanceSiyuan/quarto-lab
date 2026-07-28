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

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            for i, value in enumerate(row):
                if int(value) & 1:
                    bits ^= 1 << i
            rows.append(bits)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n:
                    raise ValueError("sparse row indices must be strictly increasing and in range")
                bits ^= 1 << col
                last = col
            rows.append(bits)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def weight(x):
    return x.bit_count()


def permute_bits(x, perm):
    y = 0
    for new_col, old_col in enumerate(perm):
        if (x >> old_col) & 1:
            y |= 1 << new_col
    return y


def unpermute_bits(x, perm):
    y = 0
    for new_col, old_col in enumerate(perm):
        if (x >> new_col) & 1:
            y |= 1 << old_col
    return y


def rref(rows, n):
    rows = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        pivot = None
        mask = 1 << col
        for i in range(rank, len(rows)):
            if rows[i] & mask:
                pivot = i
                break
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & mask):
                rows[i] ^= rows[rank]
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return rows[:rank], pivots


def rowspace_basis(rows, n):
    return rref(rows, n)[0]


def in_rowspace(x, basis):
    y = x
    for row in basis:
        if y == 0:
            return True
        p = row & -row
        if y & p:
            y ^= row
    return y == 0


def kernel_basis(rows, n, rng):
    perm = list(range(n))
    rng.shuffle(perm)
    prows = [permute_bits(row, perm) for row in rows]
    rbasis, pivots = rref(prows, n)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    out = []
    for free in free_cols:
        v = 1 << free
        for row, pivot in zip(rbasis, pivots):
            if (row >> free) & 1:
                v |= 1 << pivot
        out.append(unpermute_bits(v, perm))
    rng.shuffle(out)
    return out


def syndrome_zero(v, checks):
    for row in checks:
        if (row & v).bit_count() & 1:
            return False
    return True


def reduce_by_stabilizers(v, stabilizers, rng, passes=6):
    rows = [r for r in stabilizers if r]
    best = v
    for _ in range(passes):
        changed = False
        rng.shuffle(rows)
        for row in rows:
            cand = best ^ row
            if 0 < weight(cand) < weight(best):
                best = cand
                changed = True
        if not changed:
            break
    return best


def random_kernel_candidate(kbasis, rng):
    if not kbasis:
        return 0
    r = rng.random()
    if r < 0.55:
        count = 1
    elif r < 0.80:
        count = 2
    elif r < 0.94:
        count = min(4, len(kbasis))
    else:
        count = rng.randint(1, min(len(kbasis), 24))
    v = 0
    for b in rng.sample(kbasis, count):
        v ^= b
    return v


def verified(v, kernel_checks, stabilizer_basis):
    return v != 0 and syndrome_zero(v, kernel_checks) and not in_rowspace(v, stabilizer_basis)


def search_basis(name, hx, hz, n, rng, rounds):
    if name == "x":
        kernel_checks, stabilizers = hz, hx
    else:
        kernel_checks, stabilizers = hx, hz
    stabilizer_basis = rowspace_basis(stabilizers, n)
    best = None

    for _ in range(rounds):
        kbasis = kernel_basis(kernel_checks, n, rng)
        if not kbasis:
            continue

        trials = min(256, max(64, 4 * len(kbasis)))
        seeds = kbasis[: min(len(kbasis), 64)]
        seeds.extend(random_kernel_candidate(kbasis, rng) for _ in range(trials))
        for v in seeds:
            if v == 0:
                continue
            v = reduce_by_stabilizers(v, stabilizers, rng)
            if verified(v, kernel_checks, stabilizer_basis):
                if best is None or weight(v) < weight(best):
                    best = v
    return best


def vector_list(v, n):
    return [int((v >> i) & 1) for i in range(n)]


def main():
    parser = argparse.ArgumentParser(description="Randomized CSS logical upper-bound witness search")
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
        n = nx
        rounds = max(24, min(160, 12 + n // 2))
        x = search_basis("x", hx, hz, n, rng, rounds)
        z = search_basis("z", hx, hz, n, rng, rounds)

        choices = []
        if x is not None:
            choices.append(("x", x))
        if z is not None:
            choices.append(("z", z))
        if choices:
            basis, vec = min(choices, key=lambda item: (weight(item[1]), item[0]))
            result = {
                "status": "completed",
                "basis": basis,
                "vector": vector_list(vec, n),
                "upper_bound": weight(vec),
            }
        else:
            result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception as exc:
        result = {"status": "error", "basis": None, "vector": [], "upper_bound": None}
        print(json.dumps(result, separators=(",", ":")))
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
