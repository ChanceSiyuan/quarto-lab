#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        rows = obj
        n_cols = max((len(r) for r in rows), default=0)
        return [row_to_int([i for i, b in enumerate(r) if b & 1]) for r in rows], n_cols

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError("dense row length does not match n_cols")
            rows.append(row_to_int(i for i, b in enumerate(row) if int(b) & 1))
        return rows, n_cols

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            bits = []
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing valid columns")
                bits.append(col)
                last = col
            rows.append(row_to_int(bits))
        return rows, n_cols

    raise ValueError("unrecognized matrix JSON format")


def row_to_int(cols):
    value = 0
    for col in cols:
        value ^= 1 << int(col)
    return value


def int_to_binary_list(value, n_cols):
    return [(value >> i) & 1 for i in range(n_cols)]


def parity(value):
    return value.bit_count() & 1


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            pivot = x.bit_length() - 1
            if pivot in basis:
                x ^= basis[pivot]
            else:
                basis[pivot] = x
                break

    for pivot in sorted(basis):
        row = basis[pivot]
        for other_pivot, other in list(basis.items()):
            if other_pivot != pivot and ((other >> pivot) & 1):
                basis[other_pivot] = other ^ row
    return dict(sorted(basis.items(), reverse=True))


def reduce_by_basis(value, basis):
    x = value
    while x:
        pivot = x.bit_length() - 1
        row = basis.get(pivot)
        if row is None:
            break
        x ^= row
    return x


def in_rowspace(value, basis):
    return reduce_by_basis(value, basis) == 0


def nullspace_basis(check_rows, n_cols):
    rref = rref_basis(check_rows)
    pivots = set(rref)
    free_cols = [c for c in range(n_cols) if c not in pivots]
    out = []
    for free in free_cols:
        vector = 1 << free
        for pivot, row in rref.items():
            if (row >> free) & 1:
                vector ^= 1 << pivot
        out.append(vector)
    return out


def in_kernel(vector, check_rows):
    return all(parity(vector & row) == 0 for row in check_rows)


def greedy_coset_reduce(vector, stabilizers, rng, rounds=3):
    best = vector
    rows = [r for r in stabilizers if r]
    if not rows:
        return best
    for _ in range(rounds):
        rng.shuffle(rows)
        changed = True
        while changed:
            changed = False
            for row in rows:
                trial = best ^ row
                if trial.bit_count() < best.bit_count():
                    best = trial
                    changed = True
    return best


def verified(vector, check_rows, stabilizer_basis):
    return vector != 0 and in_kernel(vector, check_rows) and not in_rowspace(vector, stabilizer_basis)


def randomized_witness(check_rows, stabilizer_rows, n_cols, rng):
    stab_basis = rref_basis(stabilizer_rows)
    null_basis = nullspace_basis(check_rows, n_cols)
    if not null_basis:
        return None

    best = None

    def consider(v):
        nonlocal best
        if v == 0:
            return
        v = greedy_coset_reduce(v, stabilizer_rows, rng)
        if verified(v, check_rows, stab_basis) and (best is None or v.bit_count() < best.bit_count()):
            best = v

    shuffled = list(null_basis)
    rng.shuffle(shuffled)
    for v in shuffled:
        consider(v)

    # Random information-set style sampling over the kernel basis. This is a
    # heuristic upper-bound search only; certification below gates all outputs.
    dim = len(null_basis)
    trials = max(2000, min(60000, 1200 * max(1, dim)))
    for t in range(trials):
        v = 0
        if t & 7 == 0:
            picks = rng.randint(1, min(dim, 8))
            for i in rng.sample(range(dim), picks):
                v ^= null_basis[i]
        else:
            density = rng.choice((0.03, 0.06, 0.10, 0.18, 0.30, 0.50))
            for b in null_basis:
                if rng.random() < density:
                    v ^= b
            if v == 0:
                v = null_basis[rng.randrange(dim)]
        consider(v)

        if best is not None and best.bit_count() <= 1:
            break

    return best


def solve(hx_rows, hz_rows, n_cols, seed):
    rng = random.Random(seed)
    bases = [("x", hz_rows, hx_rows), ("z", hx_rows, hz_rows)]
    rng.shuffle(bases)

    best_basis = None
    best_vec = None
    for basis, checks, stabilizers in bases:
        vec = randomized_witness(checks, stabilizers, n_cols, rng)
        if vec is not None and (best_vec is None or vec.bit_count() < best_vec.bit_count()):
            best_basis = basis
            best_vec = vec

    if best_vec is None:
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    return {
        "status": "completed",
        "basis": best_basis,
        "vector": int_to_binary_list(best_vec, n_cols),
        "upper_bound": best_vec.bit_count(),
    }


def main():
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx_rows, hx_cols = load_matrix(args.hx)
        hz_rows, hz_cols = load_matrix(args.hz)
        if hx_cols != hz_cols:
            raise ValueError("hx and hz must have the same number of columns")
        os.makedirs(args.output_dir, exist_ok=True)
        result = solve(hx_rows, hz_rows, hx_cols, args.seed)
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
