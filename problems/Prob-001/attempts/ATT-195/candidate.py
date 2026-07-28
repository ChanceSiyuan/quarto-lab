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
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x ^= 1 << i
            rows.append(x)
        return rows, n_cols

    if "num_cols" in obj and "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            prev = -1
            for col in row:
                col = int(col)
                if col <= prev or col < 0 or col >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing and in range")
                x ^= 1 << col
                prev = col
            rows.append(x)
        return rows, n_cols

    raise ValueError("unknown matrix JSON format")


def weight(x):
    return x.bit_count()


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                for q, old in list(basis.items()):
                    if (old >> p) & 1:
                        basis[q] = old ^ x
                basis[p] = x
                break
            x ^= b
    return [basis[p] for p in sorted(basis, reverse=True)]


def rows_rank(rows):
    return len(rref_basis(rows))


def rowspace_basis(rows):
    return rref_basis(rows)


def in_rowspace(x, basis_rows):
    y = x
    for row in basis_rows:
        if not y:
            return True
        p = row.bit_length() - 1
        if (y >> p) & 1:
            y ^= row
    return y == 0


def nullspace_basis(rows, n_cols):
    rref = rref_basis(rows)
    pivot_rows = [(row.bit_length() - 1, row) for row in rref]
    pivots = {p for p, _ in pivot_rows}
    free_cols = [c for c in range(n_cols) if c not in pivots]
    out = []
    for free in free_cols:
        v = 1 << free
        for p, row in pivot_rows:
            if (row >> free) & 1:
                v ^= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, checks):
    for row in checks:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def xor_sample(rng, vectors, p=0.5):
    x = 0
    used = False
    for v in vectors:
        if rng.random() < p:
            x ^= v
            used = True
    if not used and vectors:
        x = rng.choice(vectors)
    return x


def quotient_generators(kernel_basis, stabilizer_basis):
    gens = []
    span = list(stabilizer_basis)
    rank = rows_rank(span)
    for v in sorted(kernel_basis, key=weight):
        new_rank = rows_rank(span + [v])
        if new_rank > rank:
            gens.append(v)
            span.append(v)
            rank = new_rank
    return gens


def reduce_by_stabilizers(v, stabilizers, rng, rounds):
    if not stabilizers:
        return v
    current = v
    current_w = weight(current)
    rows = list(stabilizers)
    for _ in range(rounds):
        improved = False
        rng.shuffle(rows)
        for row in rows:
            candidate = current ^ row
            w = weight(candidate)
            if w < current_w:
                current = candidate
                current_w = w
                improved = True
        if not improved:
            break
    return current


def search_basis(name, commute_checks, stabilizers, n_cols, rng):
    stabilizer_basis = rowspace_basis(stabilizers)
    kernel_basis = nullspace_basis(commute_checks, n_cols)
    logical_gens = quotient_generators(kernel_basis, stabilizer_basis)
    if not logical_gens:
        return None

    candidates = []
    candidates.extend(logical_gens)
    trials = max(600, 80 * (len(logical_gens) + len(stabilizer_basis) + 1))
    trials = min(trials, 12000)

    for _ in range(trials):
        if rng.random() < 0.65:
            p = rng.choice((0.08, 0.12, 0.18, 0.25, 0.35, 0.5))
            v = xor_sample(rng, logical_gens, p)
        else:
            v = rng.choice(logical_gens)
        if stabilizer_basis and rng.random() < 0.8:
            v ^= xor_sample(rng, stabilizer_basis, rng.choice((0.03, 0.06, 0.1, 0.18)))
        candidates.append(v)

    best = None
    best_w = n_cols + 1
    for v in candidates:
        if v == 0:
            continue
        v = reduce_by_stabilizers(v, stabilizer_basis, rng, 8)
        if v == 0:
            continue
        if weight(v) >= best_w:
            continue
        if syndrome_zero(v, commute_checks) and not in_rowspace(v, stabilizer_basis):
            best = v
            best_w = weight(v)

    if best is None:
        return None
    return name, best


def vector_list(v, n_cols):
    return [int((v >> i) & 1) for i in range(n_cols)]


def emit(status, basis, vector, upper_bound):
    print(json.dumps({
        "status": status,
        "basis": basis,
        "vector": vector,
        "upper_bound": upper_bound,
    }, separators=(",", ":")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        os.makedirs(args.output_dir, exist_ok=True)
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different numbers of columns")
        n_cols = nx
        rng = random.Random(args.seed)

        attempts = [
            search_basis("x", hz, hx, n_cols, rng),
            search_basis("z", hx, hz, n_cols, rng),
        ]
        attempts = [a for a in attempts if a is not None]
        if not attempts:
            emit("not_found", "", [], None)
            return 0

        basis, vec = min(attempts, key=lambda item: weight(item[1]))
        if basis == "x":
            ok = syndrome_zero(vec, hz) and not in_rowspace(vec, rowspace_basis(hx))
        else:
            ok = syndrome_zero(vec, hx) and not in_rowspace(vec, rowspace_basis(hz))
        if not ok:
            emit("not_found", "", [], None)
            return 0

        emit("completed", basis, vector_list(vec, n_cols), weight(vec))
        return 0
    except Exception:
        emit("error", "", [], None)
        return 0


if __name__ == "__main__":
    sys.exit(main())
