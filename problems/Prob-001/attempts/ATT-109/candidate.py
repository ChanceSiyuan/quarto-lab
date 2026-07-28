#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def emit(status, basis="x", vector=None, upper_bound=None):
    if vector is None:
        vector = []
    print(json.dumps({
        "status": status,
        "basis": basis,
        "vector": vector,
        "upper_bound": upper_bound,
    }, separators=(",", ":")))


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            for i, value in enumerate(row):
                if value & 1:
                    bits |= 1 << i
            rows.append(bits)
        return n, rows

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n:
                    raise ValueError("invalid sparse row")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return n, rows

    raise ValueError("unknown matrix JSON format")


def parity(x):
    return x.bit_count() & 1


def reduce_row(row, basis):
    for pivot in sorted(basis.keys(), reverse=True):
        if (row >> pivot) & 1:
            row ^= basis[pivot]
    return row


def add_to_basis(row, basis):
    row = reduce_row(row, basis)
    if row == 0:
        return False
    basis[row.bit_length() - 1] = row
    return True


def build_basis(rows):
    basis = {}
    for row in rows:
        if row:
            add_to_basis(row, basis)
    return basis


def nullspace_basis(rows, n):
    row_basis = build_basis(rows)
    pivots = set(row_basis.keys())
    free_cols = [i for i in range(n) if i not in pivots]
    out = []
    for col in free_cols:
        vec = 1 << col
        for pivot in sorted(pivots):
            row = row_basis[pivot] ^ (1 << pivot)
            if parity(row & vec):
                vec ^= 1 << pivot
        out.append(vec)
    return out


def in_rowspace(vec, basis):
    return reduce_row(vec, basis) == 0


def in_kernel(vec, checks):
    for row in checks:
        if parity(vec & row):
            return False
    return True


def verified(vec, checks, stabilizer_basis):
    return vec != 0 and in_kernel(vec, checks) and not in_rowspace(vec, stabilizer_basis)


def logical_generators(checks, stabilizers, n):
    stab_basis = build_basis(stabilizers)
    quotient_basis = {}
    generators = []
    for vec in nullspace_basis(checks, n):
        rem = reduce_row(vec, stab_basis)
        if rem and add_to_basis(rem, quotient_basis):
            generators.append(vec)
    return generators, stab_basis


def random_logical_combo(gens, rng):
    if not gens:
        return 0
    if len(gens) == 1:
        return gens[0]
    vec = 0
    # Prefer small combinations, with occasional broader mixing.
    if rng.random() < 0.70:
        count = 1 + (rng.randrange(3) if len(gens) >= 3 else rng.randrange(len(gens)))
        for idx in rng.sample(range(len(gens)), min(count, len(gens))):
            vec ^= gens[idx]
    else:
        for g in gens:
            if rng.getrandbits(1):
                vec ^= g
    if vec == 0:
        vec = gens[rng.randrange(len(gens))]
    return vec


def descend_with_stabilizers(vec, stabilizers, rng, deadline):
    if not stabilizers:
        return vec
    rows = [r for r in stabilizers if r]
    if not rows:
        return vec
    weight = vec.bit_count()
    order = list(range(len(rows)))
    passes = 0
    while passes < 8 and time.monotonic() < deadline:
        changed = False
        rng.shuffle(order)
        for idx in order:
            row = rows[idx]
            trial = vec ^ row
            new_weight = trial.bit_count()
            if new_weight < weight or (new_weight == weight and rng.random() < 0.003):
                vec = trial
                weight = new_weight
                changed = True
        passes += 1
        if not changed:
            break
    return vec


def search_basis(label, checks, stabilizers, n, seed, seconds):
    rng = random.Random((seed << 8) ^ (17 if label == "x" else 91))
    deadline = time.monotonic() + seconds
    gens, stab_basis = logical_generators(checks, stabilizers, n)
    if not gens:
        return None

    best = None
    starts = 0
    max_starts = max(64, min(5000, 48 * (len(gens) + 1)))
    ordered = sorted(gens, key=lambda v: v.bit_count())

    for g in ordered[:min(len(ordered), 32)]:
        if time.monotonic() >= deadline:
            break
        starts += 1
        cand = descend_with_stabilizers(g, stabilizers, rng, deadline)
        if verified(cand, checks, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    while starts < max_starts and time.monotonic() < deadline:
        starts += 1
        cand = random_logical_combo(gens, rng)
        if best is not None and rng.random() < 0.35:
            cand ^= best
            if cand == 0:
                cand = random_logical_combo(gens, rng)
        cand = descend_with_stabilizers(cand, stabilizers, rng, deadline)
        if verified(cand, checks, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    if best is None:
        return None
    return label, best, best.bit_count()


def vector_to_list(vec, n):
    return [(vec >> i) & 1 for i in range(n)]


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    try:
        hx_n, hx_rows = load_matrix(args.hx)
        hz_n, hz_rows = load_matrix(args.hz)
        if hx_n != hz_n:
            raise ValueError("matrix column counts differ")
        os.makedirs(args.output_dir, exist_ok=True)
        n = hx_n

        per_basis_seconds = 3.0
        x_res = search_basis("x", hz_rows, hx_rows, n, args.seed, per_basis_seconds)
        z_res = search_basis("z", hx_rows, hz_rows, n, args.seed, per_basis_seconds)
        choices = [r for r in (x_res, z_res) if r is not None]
        if not choices:
            emit("failed", "x", [], None)
            return 0
        label, vec, weight = min(choices, key=lambda r: (r[2], 0 if r[0] == "x" else 1))
        emit("completed", label, vector_to_list(vec, n), weight)
        return 0
    except Exception:
        emit("failed", "x", [], None)
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
