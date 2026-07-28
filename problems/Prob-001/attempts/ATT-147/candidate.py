#!/usr/bin/env python3
import argparse
import json
import random
from pathlib import Path


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_rows = int(obj["n_rows"])
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            for j, value in enumerate(row):
                if int(value) & 1:
                    bits |= 1 << j
            rows.append(bits)
        if len(rows) != n_rows:
            raise ValueError(f"{path}: n_rows does not match data length")
        return n_cols, rows

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for j in row:
                j = int(j)
                if j <= last or j < 0 or j >= n_cols:
                    raise ValueError(f"{path}: sparse row is not strictly increasing in range")
                bits |= 1 << j
                last = j
            rows.append(bits)
        return n_cols, rows

    raise ValueError(f"{path}: unsupported matrix JSON format")


def rref_rows(rows, n_cols):
    rows = [r for r in rows if r]
    rank = 0
    pivots = []
    for col in range(n_cols):
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


def rowspace_basis(rows, n_cols):
    basis = [0] * n_cols
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if basis[p]:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def reduce_by_basis(value, basis):
    x = value
    while x:
        p = x.bit_length() - 1
        b = basis[p]
        if not b:
            return x
        x ^= b
    return 0


def in_rowspace(value, basis):
    return reduce_by_basis(value, basis) == 0


def nullspace_basis(rows, n_cols):
    rref, pivots = rref_rows(rows, n_cols)
    pivot_set = set(pivots)
    out = []
    for free_col in range(n_cols):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        for row, pivot_col in zip(rref, pivots):
            if row & (1 << free_col):
                v |= 1 << pivot_col
        out.append(v)
    return out


def syndrome_zero(vector, checks):
    for row in checks:
        if (vector & row).bit_count() & 1:
            return False
    return True


def to_list(vector, n_cols):
    return [(vector >> i) & 1 for i in range(n_cols)]


def greedy_reduce(vector, stabilizers, protect_basis, rng, passes):
    v = vector
    if not v:
        return v
    rows = [s for s in stabilizers if s]
    sample_limit = 768
    for _ in range(passes):
        if len(rows) > sample_limit:
            active = rng.sample(rows, sample_limit)
        else:
            active = rows[:]
            rng.shuffle(active)
        changed = False
        for s in active:
            candidate = v ^ s
            if candidate and candidate.bit_count() < v.bit_count():
                if not in_rowspace(candidate, protect_basis):
                    v = candidate
                    changed = True
        if not changed:
            break
    return v


def randomized_witness(kernel, checks, stabilizers, stab_basis, n_cols, rng, budget):
    seeds = list(kernel)
    rng.shuffle(seeds)
    best = None

    def consider(v, passes=8):
        nonlocal best
        if not v or not syndrome_zero(v, checks) or in_rowspace(v, stab_basis):
            return
        v = greedy_reduce(v, stabilizers, stab_basis, rng, passes)
        if syndrome_zero(v, checks) and not in_rowspace(v, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for v in seeds[: min(len(seeds), 256)]:
        consider(v, passes=10)

    if not kernel:
        return best

    target_terms = min(32, max(2, len(kernel)))
    for t in range(budget):
        v = 0
        if t % 5 == 0 and best is not None:
            v = best
        count = 1 + rng.randrange(target_terms)
        for _ in range(count):
            v ^= kernel[rng.randrange(len(kernel))]
        consider(v, passes=6)

        if best is not None and t % 17 == 0:
            v = best
            flips = 1 + rng.randrange(min(8, len(stabilizers) or 1))
            for _ in range(flips):
                if stabilizers:
                    v ^= stabilizers[rng.randrange(len(stabilizers))]
            consider(v, passes=12)

    return best


def search_basis(name, kernel_checks, stabilizer_rows, n_cols, seed, effort):
    rng = random.Random((seed << 8) ^ (0x58 if name == "x" else 0x7A))
    kernel = nullspace_basis(kernel_checks, n_cols)
    stab_basis = rowspace_basis(stabilizer_rows, n_cols)
    return randomized_witness(kernel, kernel_checks, stabilizer_rows, stab_basis, n_cols, rng, effort)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        nx, hx = load_matrix(args.hx)
        nz, hz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz have different column counts")
        n_cols = nx
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)

        effort = max(700, min(7000, 60 * n_cols))
        x = search_basis("x", hz, hx, n_cols, args.seed, effort)
        z = search_basis("z", hx, hz, n_cols, args.seed + 104729, effort)
        candidates = []
        if x is not None:
            candidates.append(("x", x))
        if z is not None:
            candidates.append(("z", z))

        if candidates:
            basis, vector = min(candidates, key=lambda item: (item[1].bit_count(), item[0]))
            result = {
                "status": "completed",
                "basis": basis,
                "vector": to_list(vector, n_cols),
                "upper_bound": int(vector.bit_count()),
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
