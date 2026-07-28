#!/usr/bin/env python3
import argparse
import json
import random
import sys


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as handle:
        obj = json.load(handle)

    if isinstance(obj, list):
        n_rows = len(obj)
        n_cols = max((len(row) for row in obj), default=0)
        rows = []
        for row in obj:
            bits = 0
            for col, value in enumerate(row):
                if value & 1:
                    bits |= 1 << col
            rows.append(bits)
        return n_rows, n_cols, rows

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_rows = int(obj["n_rows"])
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            for col, value in enumerate(row):
                if value & 1:
                    bits |= 1 << col
            rows.append(bits)
        return n_rows, n_cols, rows

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return len(rows), n_cols, rows

    raise ValueError("unrecognized matrix JSON format")


def bit_weight(x):
    return x.bit_count()


def to_vector(x, n_cols):
    return [(x >> col) & 1 for col in range(n_cols)]


def add_to_basis(row, basis):
    x = row
    while x:
        pivot = x.bit_length() - 1
        if pivot in basis:
            x ^= basis[pivot]
        else:
            basis[pivot] = x
            return True
    return False


def rowspace_basis(rows):
    basis = {}
    for row in rows:
        if row:
            add_to_basis(row, basis)
    return basis


def in_rowspace(row, basis):
    x = row
    while x:
        pivot = x.bit_length() - 1
        reducer = basis.get(pivot)
        if reducer is None:
            return False
        x ^= reducer
    return True


def nullspace_basis(rows, n_cols):
    mat = [row & ((1 << n_cols) - 1) for row in rows if row]
    rank = 0
    pivots = []

    for col in range(n_cols):
        pivot_row = None
        mask = 1 << col
        for idx in range(rank, len(mat)):
            if mat[idx] & mask:
                pivot_row = idx
                break
        if pivot_row is None:
            continue

        mat[rank], mat[pivot_row] = mat[pivot_row], mat[rank]
        for idx in range(len(mat)):
            if idx != rank and (mat[idx] & mask):
                mat[idx] ^= mat[rank]
        pivots.append(col)
        rank += 1
        if rank == len(mat):
            break

    pivot_set = set(pivots)
    free_cols = [col for col in range(n_cols) if col not in pivot_set]
    basis = []
    for free_col in free_cols:
        vec = 1 << free_col
        for row_idx, pivot_col in enumerate(pivots):
            if mat[row_idx] & (1 << free_col):
                vec |= 1 << pivot_col
        basis.append(vec)
    return basis


def syndrome_zero(check_rows, vec):
    return all(((row & vec).bit_count() & 1) == 0 for row in check_rows)


def verified_witness(vec, kernel_checks, stabilizer_basis):
    return vec != 0 and syndrome_zero(kernel_checks, vec) and not in_rowspace(vec, stabilizer_basis)


def random_combo(vectors, rng, probability=0.5):
    out = 0
    used = False
    for vec in vectors:
        if rng.random() < probability:
            out ^= vec
            used = True
    if not used and vectors:
        out = rng.choice(vectors)
    return out


def greedy_stabilizer_reduce(vec, stabilizers, rng, passes=6):
    current = vec
    current_w = bit_weight(current)
    if not stabilizers:
        return current

    for _ in range(passes):
        improved = False
        order = stabilizers[:]
        rng.shuffle(order)
        for row in order:
            trial = current ^ row
            trial_w = bit_weight(trial)
            if trial_w < current_w:
                current = trial
                current_w = trial_w
                improved = True
        if not improved:
            break
    return current


def polish_by_random_stabilizers(vec, stabilizers, rng, rounds):
    best = greedy_stabilizer_reduce(vec, stabilizers, rng)
    best_w = bit_weight(best)
    if not stabilizers:
        return best

    max_flips = min(12, max(1, len(stabilizers)))
    for _ in range(rounds):
        trial = best
        flips = 1 + rng.randrange(max_flips)
        for _ in range(flips):
            trial ^= rng.choice(stabilizers)
        trial = greedy_stabilizer_reduce(trial, stabilizers, rng, passes=4)
        trial_w = bit_weight(trial)
        if trial_w < best_w:
            best = trial
            best_w = trial_w
    return best


def logical_seed_pool(kernel_basis, stabilizer_basis):
    pool = []
    span = {}
    for vec in kernel_basis:
        if not in_rowspace(vec, stabilizer_basis):
            pool.append(vec)
            add_to_basis(vec, span)
    return pool


def search_orientation(label, kernel_checks, stabilizer_rows, n_cols, rng):
    stab_basis = rowspace_basis(stabilizer_rows)
    kernel_basis = nullspace_basis(kernel_checks, n_cols)
    if not kernel_basis:
        return None

    seeds = logical_seed_pool(kernel_basis, stab_basis)
    stabilizers = [row for row in stabilizer_rows if row]
    best = None
    best_w = n_cols + 1

    iterations = max(500, min(6000, 80 * max(1, len(kernel_basis))))
    for idx in range(iterations):
        if seeds and (idx < len(seeds) or rng.random() < 0.35):
            seed = seeds[idx % len(seeds)]
            vec = seed ^ random_combo(kernel_basis, rng, probability=0.08)
        else:
            probability = rng.choice((0.03, 0.06, 0.12, 0.25, 0.5))
            vec = random_combo(kernel_basis, rng, probability=probability)

        if not verified_witness(vec, kernel_checks, stab_basis):
            continue

        vec = polish_by_random_stabilizers(vec, stabilizers, rng, rounds=24)
        if not verified_witness(vec, kernel_checks, stab_basis):
            continue

        weight = bit_weight(vec)
        if weight < best_w:
            best = (label, vec, weight)
            best_w = weight
            if best_w <= 1:
                break

    return best


def failure_result(n_cols=0):
    return {"status": "not_found", "basis": "x", "vector": [0] * n_cols, "upper_bound": None}


def main(argv):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    try:
        _, nx, hx_rows = load_matrix(args.hx)
        _, nz, hz_rows = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz must have the same number of columns")

        rng = random.Random(args.seed)
        searches = [
            search_orientation("x", hz_rows, hx_rows, nx, rng),
            search_orientation("z", hx_rows, hz_rows, nx, rng),
        ]
        hits = [hit for hit in searches if hit is not None]
        if not hits:
            result = failure_result(nx)
        else:
            basis, vec, weight = min(hits, key=lambda item: (item[2], rng.random()))
            result = {
                "status": "completed",
                "basis": basis,
                "vector": to_vector(vec, nx),
                "upper_bound": weight,
            }
    except Exception:
        result = failure_result(0)

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main(sys.argv[1:])
