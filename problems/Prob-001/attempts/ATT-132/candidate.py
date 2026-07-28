#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


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
            if len(row) != n_cols:
                raise ValueError("dense row length does not match n_cols")
            bits = 0
            for i, value in enumerate(row):
                if value not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if value:
                    bits |= 1 << i
            rows.append(bits)
        if len(rows) != int(obj["n_rows"]):
            raise ValueError("dense n_rows does not match data length")
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
                    raise ValueError("sparse rows must be strictly increasing valid indices")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


def echelon_basis(rows):
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


def reduce_by_basis(value, basis):
    x = int(value)
    while x:
        pivot = x.bit_length() - 1
        row = basis.get(pivot)
        if row is None:
            return x
        x ^= row
    return 0


def in_rowspace(value, rows):
    return reduce_by_basis(value, echelon_basis(rows)) == 0


def syndrome_zero(value, checks):
    return all(((value & row).bit_count() & 1) == 0 for row in checks)


def rref(rows, n_cols):
    mat = [int(r) for r in rows if r]
    pivots = []
    r = 0
    for col in range(n_cols):
        pivot_at = None
        mask = 1 << col
        for i in range(r, len(mat)):
            if mat[i] & mask:
                pivot_at = i
                break
        if pivot_at is None:
            continue
        mat[r], mat[pivot_at] = mat[pivot_at], mat[r]
        for i in range(len(mat)):
            if i != r and (mat[i] & mask):
                mat[i] ^= mat[r]
        pivots.append(col)
        r += 1
        if r == len(mat):
            break
    return mat[:r], pivots


def kernel_basis(checks, n_cols):
    rows, pivots = rref(checks, n_cols)
    pivot_set = set(pivots)
    out = []
    for free_col in range(n_cols):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        free_bit = 1 << free_col
        for row, pivot_col in zip(rows, pivots):
            if row & free_bit:
                v |= 1 << pivot_col
        out.append(v)
    return out


def bits_to_list(value, n_cols):
    return [(value >> i) & 1 for i in range(n_cols)]


def greedy_coset_descent(value, stabilizers, rng, passes=8):
    best = int(value)
    best_w = best.bit_count()
    rows = [r for r in stabilizers if r]
    if not rows:
        return best

    for _ in range(passes):
        changed = False
        rng.shuffle(rows)
        for row in rows:
            candidate = best ^ row
            w = candidate.bit_count()
            if w < best_w:
                best = candidate
                best_w = w
                changed = True
        if not changed:
            break
    return best


def random_kernel_vector(kernel, rng):
    k = len(kernel)
    if k == 0:
        return 0
    mode = rng.random()
    v = 0
    if mode < 0.60:
        count = rng.randint(1, max(1, min(k, 10)))
        for i in rng.sample(range(k), count):
            v ^= kernel[i]
    elif mode < 0.90:
        p = rng.uniform(0.02, 0.20)
        for row in kernel:
            if rng.random() < p:
                v ^= row
    else:
        for row in kernel:
            if rng.getrandbits(1):
                v ^= row
    return v


def verified(value, checks, stabilizers):
    return value != 0 and syndrome_zero(value, checks) and not in_rowspace(value, stabilizers)


def search_basis(name, checks, stabilizers, n_cols, rng, deadline):
    kernel = kernel_basis(checks, n_cols)
    if not kernel:
        return None

    best = None
    stab_basis = echelon_basis(stabilizers)

    def consider(v):
        nonlocal best
        if v == 0:
            return
        v = greedy_coset_descent(v, stabilizers, rng)
        if v == 0 or not syndrome_zero(v, checks):
            return
        if reduce_by_basis(v, stab_basis) == 0:
            return
        if best is None or v.bit_count() < best.bit_count():
            best = v

    order = list(range(len(kernel)))
    rng.shuffle(order)
    for i in order[: min(len(order), 512)]:
        consider(kernel[i])

    population = []
    for _ in range(48):
        v = random_kernel_vector(kernel, rng)
        consider(v)
        if verified(v, checks, stabilizers):
            population.append(v)

    iterations = 0
    while time.monotonic() < deadline:
        iterations += 1
        if population and rng.random() < 0.45:
            v = rng.choice(population)
            for _ in range(rng.randint(1, 6)):
                v ^= rng.choice(kernel)
        else:
            v = random_kernel_vector(kernel, rng)
        consider(v)
        if best is not None:
            population.append(best)
            if len(population) > 96:
                population.sort(key=int.bit_count)
                population = population[:64] + rng.sample(population[64:], min(16, len(population[64:])))
        if iterations >= 20000 and best is not None:
            break

    if best is None:
        return None
    return name, best


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
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        time_limit = float(os.environ.get("CANDIDATE_TIME_LIMIT", "25.0"))
        start = time.monotonic()
        first = search_basis("x", hz, hx, nx, rng, start + 0.5 * time_limit)
        second = search_basis("z", hx, hz, nx, rng, start + time_limit)
        choices = [item for item in (first, second) if item is not None]
        if not choices:
            emit("not_found", None, [], None)
            return 0

        basis, value = min(choices, key=lambda item: item[1].bit_count())
        checks = hz if basis == "x" else hx
        stabilizers = hx if basis == "x" else hz
        if not verified(value, checks, stabilizers):
            emit("not_found", None, [], None)
            return 0

        vector = bits_to_list(value, nx)
        emit("completed", basis, vector, int(value.bit_count()))
        return 0
    except Exception:
        emit("error", None, [], None)
        return 0


if __name__ == "__main__":
    sys.exit(main())
