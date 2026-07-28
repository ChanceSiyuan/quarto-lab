#!/usr/bin/env python3
import argparse
import json
import random


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError("dense row has wrong length")
            bits = 0
            for i, value in enumerate(row):
                if value not in (0, 1, False, True):
                    raise ValueError("dense entries must be binary")
                if value:
                    bits |= 1 << i
            rows.append(bits)
        return rows, n_cols

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            bits = 0
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("invalid sparse row")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


def weight(x):
    return x.bit_count()


def rref_basis(rows):
    basis = {}
    for value in rows:
        x = int(value)
        while x:
            pivot = x.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = x
                break
            x ^= basis[pivot]
    return basis


def reduce_by_basis(x, basis):
    y = int(x)
    while y:
        pivot = y.bit_length() - 1
        row = basis.get(pivot)
        if row is None:
            break
        y ^= row
    return y


def in_rowspace(x, row_basis):
    return reduce_by_basis(x, row_basis) == 0


def syndrome_zero(x, checks):
    for row in checks:
        if ((x & row).bit_count() & 1) != 0:
            return False
    return True


def nullspace_basis(check_rows, n_cols):
    rows = [int(r) for r in check_rows if r]
    pivot_rows = {}
    rank = 0
    for col in range(n_cols):
        found = None
        mask = 1 << col
        for i in range(rank, len(rows)):
            if rows[i] & mask:
                found = i
                break
        if found is None:
            continue
        rows[rank], rows[found] = rows[found], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & mask):
                rows[i] ^= rows[rank]
        pivot_rows[col] = rows[rank]
        rank += 1

    pivots = set(pivot_rows)
    basis = []
    for free in range(n_cols):
        if free in pivots:
            continue
        v = 1 << free
        for pivot, row in pivot_rows.items():
            if row & (1 << free):
                v |= 1 << pivot
        basis.append(v)
    return basis


def binary_list(x, n_cols):
    return [(x >> i) & 1 for i in range(n_cols)]


def verified(candidate, checks, stabilizers, n_cols):
    if candidate == 0 or candidate >= (1 << n_cols):
        return False
    if not syndrome_zero(candidate, checks):
        return False
    return not in_rowspace(candidate, rref_basis(stabilizers))


def greedy_stabilizer_descent(v, stabilizers, rng, rounds):
    candidate = v
    stab = [s for s in stabilizers if s]
    if not stab:
        return candidate

    best = candidate
    best_w = weight(best)
    for _ in range(rounds):
        rng.shuffle(stab)
        changed = False
        for row in stab:
            trial = candidate ^ row
            tw = weight(trial)
            if tw < weight(candidate):
                candidate = trial
                changed = True
                if tw < best_w:
                    best = trial
                    best_w = tw
        if not changed:
            row = rng.choice(stab)
            trial = candidate ^ row
            if weight(trial) <= weight(candidate) + 1 and rng.random() < 0.20:
                candidate = trial
    return best


def independent_logical_seeds(kernel_basis, stabilizer_basis):
    seeds = []
    span = dict(stabilizer_basis)
    for v in sorted(kernel_basis, key=weight):
        residue = reduce_by_basis(v, span)
        if residue:
            seeds.append(v)
            span[residue.bit_length() - 1] = residue
    return seeds


def random_combo(vectors, rng, p):
    x = 0
    picked = False
    for v in vectors:
        if rng.random() < p:
            x ^= v
            picked = True
    if not picked and vectors:
        x = rng.choice(vectors)
    return x


def search_basis(name, checks, stabilizers, n_cols, rng):
    kernel = nullspace_basis(checks, n_cols)
    stab_basis = rref_basis(stabilizers)
    seeds = independent_logical_seeds(kernel, stab_basis)
    if not seeds:
        return None

    best = None
    best_w = n_cols + 1
    trials = max(400, min(8000, 80 * max(1, len(seeds) + len(kernel))))
    probabilities = [0.06, 0.10, 0.18, 0.30, 0.50]
    stream = list(seeds)
    rng.shuffle(stream)

    for t in range(trials):
        if t < len(stream):
            v = stream[t]
        elif rng.random() < 0.70:
            v = random_combo(seeds, rng, rng.choice(probabilities))
        else:
            v = random_combo(kernel, rng, rng.choice(probabilities))

        if in_rowspace(v, stab_basis):
            continue
        v = greedy_stabilizer_descent(v, stabilizers, rng, 8)
        if verified(v, checks, stabilizers, n_cols):
            w = weight(v)
            if w < best_w:
                best = v
                best_w = w

    if best is None:
        return None
    return {"basis": name, "vector": binary_list(best, n_cols), "upper_bound": best_w}


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
            raise ValueError("Hx and Hz have different column counts")

        rng = random.Random(args.seed)
        candidates = [
            search_basis("x", hz, hx, nx, rng),
            search_basis("z", hx, hz, nx, rng),
        ]
        candidates = [c for c in candidates if c is not None]
        if candidates:
            result = min(candidates, key=lambda c: (c["upper_bound"], c["basis"]))
            result = {
                "status": "completed",
                "basis": result["basis"],
                "vector": result["vector"],
                "upper_bound": result["upper_bound"],
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
