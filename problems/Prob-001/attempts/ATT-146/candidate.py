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

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            mask = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    mask ^= 1 << i
            rows.append(mask)
        return rows, n_cols

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            mask = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing in range")
                mask |= 1 << col
                last = col
            rows.append(mask)
        return rows, n_cols

    raise ValueError("unknown matrix JSON format")


def insert_basis(basis, vec):
    x = vec
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def build_basis(rows):
    basis = {}
    for row in rows:
        insert_basis(basis, row)
    return basis


def reduce_by_basis(vec, basis):
    x = vec
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_span(vec, basis):
    return reduce_by_basis(vec, basis) == 0


def kernel_basis(rows, n_cols):
    row_basis = build_basis(rows)
    pivots = set(row_basis)
    free_cols = [i for i in range(n_cols) if i not in pivots]
    out = []
    for free in free_cols:
        vec = 1 << free
        for pivot in sorted(pivots):
            row = row_basis[pivot]
            if ((row & ~(1 << pivot) & vec).bit_count() & 1):
                vec |= 1 << pivot
        out.append(vec)
    return out


def commutes_with_all(vec, check_rows):
    for row in check_rows:
        if (vec & row).bit_count() & 1:
            return False
    return True


def logical_generators(check_rows, stabilizer_rows, n_cols):
    stab_basis = build_basis(stabilizer_rows)
    quotient_basis = dict(stab_basis)
    logicals = []
    for vec in kernel_basis(check_rows, n_cols):
        if vec and not in_span(vec, quotient_basis):
            logicals.append(vec)
            insert_basis(quotient_basis, vec)
    return logicals, stab_basis


def greedy_reduce(vec, stabilizer_rows, rng, rounds):
    x = vec
    if not stabilizer_rows:
        return x

    rows = list({row for row in stabilizer_rows if row})
    best = x
    best_w = x.bit_count()
    for _ in range(rounds):
        rng.shuffle(rows)
        changed = True
        while changed:
            changed = False
            for row in rows:
                y = x ^ row
                if y.bit_count() < x.bit_count():
                    x = y
                    changed = True
        w = x.bit_count()
        if w < best_w:
            best = x
            best_w = w
        if len(rows) > 1:
            x = best ^ rng.choice(rows)
    return best


def random_logical_combo(logicals, rng):
    x = 0
    while x == 0:
        for gen in logicals:
            if rng.getrandbits(1):
                x ^= gen
    return x


def search_basis(name, check_rows, stabilizer_rows, n_cols, seed):
    logicals, stab_basis = logical_generators(check_rows, stabilizer_rows, n_cols)
    if not logicals:
        return None

    rng = random.Random((seed << 8) ^ (1 if name == "x" else 2) ^ n_cols)
    trials = max(256, min(12000, 80 * (len(logicals) + len(stabilizer_rows) + 1)))
    rounds = 2 if len(stabilizer_rows) > 2000 else 4
    best = None
    best_w = n_cols + 1

    seeds = list(logicals)
    for i in range(min(len(logicals), 256)):
        for j in range(i + 1, min(len(logicals), i + 17, len(logicals))):
            seeds.append(logicals[i] ^ logicals[j])

    for base in seeds:
        cand = greedy_reduce(base, stabilizer_rows, rng, rounds)
        if cand and commutes_with_all(cand, check_rows) and not in_span(cand, stab_basis):
            w = cand.bit_count()
            if w < best_w:
                best, best_w = cand, w

    for _ in range(trials):
        base = random_logical_combo(logicals, rng)
        cand = greedy_reduce(base, stabilizer_rows, rng, rounds)
        if cand and commutes_with_all(cand, check_rows) and not in_span(cand, stab_basis):
            w = cand.bit_count()
            if w < best_w:
                best, best_w = cand, w

    if best is None:
        return None
    return name, best, best_w


def mask_to_list(mask, n_cols):
    return [(mask >> i) & 1 for i in range(n_cols)]


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
            raise ValueError("Hx and Hz must have the same number of columns")
        os.makedirs(args.output_dir, exist_ok=True)

        candidates = [
            search_basis("x", hz, hx, nx, args.seed),
            search_basis("z", hx, hz, nx, args.seed),
        ]
        candidates = [c for c in candidates if c is not None]
        if candidates:
            basis, vec, weight = min(candidates, key=lambda item: item[2])
            result = {
                "status": "completed",
                "basis": basis,
                "vector": mask_to_list(vec, nx),
                "upper_bound": int(weight),
            }
        else:
            result = {
                "status": "not_found",
                "basis": None,
                "vector": [],
                "upper_bound": None,
            }
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
