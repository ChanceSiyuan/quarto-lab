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

    if "data" in obj:
        n_rows = int(obj.get("n_rows", len(obj["data"])))
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError("dense row length does not match n_cols")
            bits = 0
            for j, bit in enumerate(row):
                if bit:
                    bits |= 1 << j
            rows.append(bits)
        if len(rows) != n_rows:
            raise ValueError("dense n_rows does not match data")
        return n_cols, rows

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            prev = -1
            for j in row:
                j = int(j)
                if j <= prev or j < 0 or j >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing indices")
                bits |= 1 << j
                prev = j
            rows.append(bits)
        return n_cols, rows

    raise ValueError("unknown matrix JSON format")


def rref(rows, n_cols):
    work = [r for r in rows if r]
    out = []
    pivots = []
    rank = 0
    for col in range(n_cols):
        mask = 1 << col
        pivot = None
        for i in range(rank, len(work)):
            if work[i] & mask:
                pivot = i
                break
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        for i in range(len(work)):
            if i != rank and (work[i] & mask):
                work[i] ^= work[rank]
        out.append(work[rank])
        pivots.append(col)
        rank += 1
        if rank == len(work):
            break
    return out, pivots


def reduce_by_rref(v, basis, pivots):
    x = v
    for row, pivot in zip(basis, pivots):
        if x & (1 << pivot):
            x ^= row
    return x


def in_rowspace(v, basis, pivots):
    return reduce_by_rref(v, basis, pivots) == 0


def nullspace_basis(rows, n_cols):
    rbasis, pivots = rref(rows, n_cols)
    pivot_set = set(pivots)
    out = []
    for free_col in range(n_cols):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        for row, pivot in zip(rbasis, pivots):
            if row & (1 << free_col):
                v |= 1 << pivot
        out.append(v)
    return out


def commutes_with_all(v, checks):
    return all(((row & v).bit_count() & 1) == 0 for row in checks)


def to_list(v, n_cols):
    return [(v >> i) & 1 for i in range(n_cols)]


def weight(v):
    return v.bit_count()


def verify(v, checks, stabilizer_basis, stabilizer_pivots):
    return v != 0 and commutes_with_all(v, checks) and not in_rowspace(v, stabilizer_basis, stabilizer_pivots)


def greedy_coset_reduce(v, stabilizers, rng, passes):
    if not stabilizers:
        return v
    current = v
    current_w = weight(current)
    gens = list(stabilizers)
    for _ in range(passes):
        rng.shuffle(gens)
        changed = False
        for row in gens:
            trial = current ^ row
            trial_w = weight(trial)
            if trial_w < current_w:
                current = trial
                current_w = trial_w
                changed = True
        if not changed:
            break
    return current


def sample_witness(label, checks, stabilizers, n_cols, rng):
    stabilizer_basis, stabilizer_pivots = rref(stabilizers, n_cols)
    logical_basis = []
    for v in nullspace_basis(checks, n_cols):
        if not in_rowspace(v, stabilizer_basis, stabilizer_pivots):
            logical_basis.append(v)

    if not logical_basis:
        return None

    logical_basis.sort(key=weight)
    stabilizer_gens = sorted(set([r for r in stabilizers if r] + stabilizer_basis), key=weight)
    best = None

    def consider(v):
        nonlocal best
        if not verify(v, checks, stabilizer_basis, stabilizer_pivots):
            return
        reduced = greedy_coset_reduce(v, stabilizer_gens, rng, max(4, min(24, n_cols // 3 + 2)))
        if verify(reduced, checks, stabilizer_basis, stabilizer_pivots):
            v = reduced
        if best is None or weight(v) < weight(best):
            best = v

    for v in logical_basis[: min(len(logical_basis), 64)]:
        consider(v)

    trials = max(256, min(6000, 80 * max(1, n_cols)))
    basis_count = len(logical_basis)
    for t in range(trials):
        if best is not None and weight(best) <= 1:
            break
        draw = 1 + int(rng.expovariate(1.0 / max(2.0, min(24.0, basis_count / 4.0))))
        draw = min(draw, basis_count)
        v = 0
        for idx in rng.sample(range(basis_count), draw):
            v ^= logical_basis[idx]
        if t & 1 and basis_count > 8:
            for idx in rng.sample(range(min(basis_count, 32)), rng.randrange(1, min(8, basis_count) + 1)):
                v ^= logical_basis[idx]
        consider(v)

    if best is None:
        return None
    return {"basis": label, "vector": to_list(best, n_cols), "upper_bound": weight(best)}


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
            raise ValueError("hx and hz have different numbers of columns")
        os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)

        candidates = []
        # X logicals commute with Z checks and are nontrivial modulo X stabilizers.
        xw = sample_witness("x", hz, hx, nx, rng)
        if xw is not None:
            candidates.append(xw)
        # Z logicals commute with X checks and are nontrivial modulo Z stabilizers.
        zw = sample_witness("z", hx, hz, nx, rng)
        if zw is not None:
            candidates.append(zw)

        if candidates:
            result = min(candidates, key=lambda item: item["upper_bound"])
            result = {
                "status": "completed",
                "basis": result["basis"],
                "vector": result["vector"],
                "upper_bound": result["upper_bound"],
            }
        else:
            result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
