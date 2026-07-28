#!/usr/bin/env python3
import argparse
import json
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
            bits = 0
            for j, value in enumerate(row):
                if value & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n_cols

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for j in row:
                j = int(j)
                if j <= last or j < 0 or j >= n_cols:
                    raise ValueError("invalid sparse row")
                bits |= 1 << j
                last = j
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unrecognized matrix JSON format")


def in_row_space(vector, rows):
    x = vector
    pivots = {}
    for value in rows:
        y = value
        while y:
            p = y.bit_length() - 1
            if p not in pivots:
                pivots[p] = y
                break
            y ^= pivots[p]
    while x:
        p = x.bit_length() - 1
        row = pivots.get(p)
        if row is None:
            return False
        x ^= row
    return True


def row_basis(rows):
    pivots = {}
    for value in rows:
        x = value
        while x:
            p = x.bit_length() - 1
            if p not in pivots:
                pivots[p] = x
                break
            x ^= pivots[p]
    return list(pivots.values())


def kernel_basis(check_rows, n_cols):
    pivots = {}
    for value in check_rows:
        x = value
        while x:
            p = x.bit_length() - 1
            if p not in pivots:
                pivots[p] = x
                break
            x ^= pivots[p]

    pivot_cols = set(pivots)
    free_cols = [j for j in range(n_cols) if j not in pivot_cols]
    basis = []
    for free in free_cols:
        x = 1 << free
        for p in sorted(pivots):
            if ((pivots[p] & x).bit_count() & 1) != 0:
                x |= 1 << p
        basis.append(x)
    return basis


def logical_representatives(check_rows, stabilizer_rows, n_cols):
    reps = []
    span = row_basis(stabilizer_rows)
    for vec in kernel_basis(check_rows, n_cols):
        if not in_row_space(vec, span):
            reps.append(vec)
            span = row_basis(span + [vec])
    return reps


def commutes_with_all(vector, check_rows):
    for row in check_rows:
        if ((vector & row).bit_count() & 1) != 0:
            return False
    return True


def verify_witness(vector, check_rows, stabilizer_rows):
    return (
        vector != 0
        and commutes_with_all(vector, check_rows)
        and not in_row_space(vector, stabilizer_rows)
    )


def to_binary_list(vector, n_cols):
    return [(vector >> j) & 1 for j in range(n_cols)]


def greedy_reduce(vector, stabilizers, rng, passes=6):
    current = vector
    current_w = current.bit_count()
    if not stabilizers:
        return current

    rows = list(stabilizers)
    for _ in range(passes):
        improved = False
        rng.shuffle(rows)
        for row in rows:
            candidate = current ^ row
            weight = candidate.bit_count()
            if weight < current_w:
                current = candidate
                current_w = weight
                improved = True
        if not improved:
            break
    return current


def random_logical_seed(reps, rng):
    vec = 0
    for rep in reps:
        if rng.getrandbits(1):
            vec ^= rep
    if vec == 0:
        vec = rng.choice(reps)
    return vec


def search_basis(name, check_rows, stabilizer_rows, n_cols, rng, trials):
    reps = logical_representatives(check_rows, stabilizer_rows, n_cols)
    if not reps:
        return None

    stab_basis = row_basis(stabilizer_rows)
    best = None
    best_w = n_cols + 1

    initial = sorted(reps, key=lambda x: x.bit_count())[: min(len(reps), 64)]
    for vec in initial:
        candidate = greedy_reduce(vec, stab_basis, rng, passes=10)
        if verify_witness(candidate, check_rows, stabilizer_rows):
            weight = candidate.bit_count()
            if weight < best_w:
                best = candidate
                best_w = weight

    for _ in range(trials):
        candidate = random_logical_seed(reps, rng)
        if stab_basis:
            toggles = 1 + rng.randrange(min(len(stab_basis), 32))
            for row in rng.sample(stab_basis, toggles):
                if rng.random() < 0.65:
                    candidate ^= row
        candidate = greedy_reduce(candidate, stab_basis, rng, passes=8)
        if verify_witness(candidate, check_rows, stabilizer_rows):
            weight = candidate.bit_count()
            if weight < best_w:
                best = candidate
                best_w = weight

    if best is None:
        return None
    return {"basis": name, "vector": best, "upper_bound": best_w}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        n_cols = nx

        # X logicals commute with Z checks and are quotiented by X stabilizers;
        # Z logicals use the dual condition.
        trials = max(600, min(20000, 80 * n_cols))
        candidates = []
        for item in (
            search_basis("x", hz, hx, n_cols, rng, trials),
            search_basis("z", hx, hz, n_cols, rng, trials),
        ):
            if item is not None:
                candidates.append(item)

        if candidates:
            result = min(candidates, key=lambda item: item["upper_bound"])
            output = {
                "status": "completed",
                "basis": result["basis"],
                "vector": to_binary_list(result["vector"], n_cols),
                "upper_bound": result["upper_bound"],
            }
        else:
            output = {
                "status": "not_found",
                "basis": "x",
                "vector": [],
                "upper_bound": None,
            }
    except Exception:
        output = {
            "status": "error",
            "basis": "x",
            "vector": [],
            "upper_bound": None,
        }

    sys.stdout.write(json.dumps(output, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
