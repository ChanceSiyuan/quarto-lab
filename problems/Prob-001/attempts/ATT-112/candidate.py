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

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError("dense row length does not match n_cols")
            mask = 0
            for i, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if bit:
                    mask |= 1 << i
            rows.append(mask)
        return n_cols, rows

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            prev = -1
            mask = 0
            for c in row:
                c = int(c)
                if c <= prev or c < 0 or c >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing valid indices")
                mask |= 1 << c
                prev = c
            rows.append(mask)
        return n_cols, rows

    raise ValueError("unrecognized matrix JSON format")


def rref(rows, n_cols):
    a = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n_cols):
        found = None
        bit = 1 << col
        for i in range(rank, len(a)):
            if a[i] & bit:
                found = i
                break
        if found is None:
            continue
        a[rank], a[found] = a[found], a[rank]
        for i in range(len(a)):
            if i != rank and (a[i] & bit):
                a[i] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == len(a):
            break
    return a[:rank], pivots


def nullspace_basis(rows, n_cols):
    rr, pivots = rref(rows, n_cols)
    pivot_set = set(pivots)
    basis = []
    for free_col in range(n_cols):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        bit = 1 << free_col
        for row, pivot in zip(rr, pivots):
            if row & bit:
                v |= 1 << pivot
        basis.append(v)
    return basis


class RowSpace:
    def __init__(self, rows=()):
        self.basis = {}
        for row in rows:
            self.add(row)

    def reduce(self, v):
        while v:
            p = v.bit_length() - 1
            b = self.basis.get(p)
            if b is None:
                return v
            v ^= b
        return 0

    def contains(self, v):
        return self.reduce(v) == 0

    def add(self, v):
        v = self.reduce(v)
        if not v:
            return False
        self.basis[v.bit_length() - 1] = v
        return True


def in_kernel(v, checks):
    for row in checks:
        if (v & row).bit_count() & 1:
            return False
    return True


def mask_to_list(v, n_cols):
    return [(v >> i) & 1 for i in range(n_cols)]


def logical_basis(null_basis, stabilizers):
    span = RowSpace(stabilizers)
    logicals = []
    for v in sorted(null_basis, key=lambda x: (x.bit_count(), x)):
        if span.add(v):
            logicals.append(v)
    return [v for v in logicals if not RowSpace(stabilizers).contains(v)]


def greedy_stabilizer_reduce(v, stabilizers, rng, max_passes=8):
    rows = [r for r in stabilizers if r]
    if not rows:
        return v

    # Include the independent basis rows as cheap dense combinations that often
    # lower weight more effectively than the raw checks alone.
    basis_rows = list(RowSpace(rows).basis.values())
    pool = rows + basis_rows
    best = v
    improved = True
    passes = 0
    while improved and passes < max_passes:
        improved = False
        passes += 1
        rng.shuffle(pool)
        for r in pool:
            cand = best ^ r
            if cand and cand.bit_count() < best.bit_count():
                best = cand
                improved = True
    return best


def random_xor(vectors, rng):
    out = 0
    for v in vectors:
        if rng.getrandbits(1):
            out ^= v
    return out


def search_basis(name, checks, stabilizers, n_cols, rng):
    null_basis = nullspace_basis(checks, n_cols)
    if not null_basis:
        return None

    stab_space = RowSpace(stabilizers)
    logs = logical_basis(null_basis, stabilizers)
    if not logs:
        return None

    best = None

    def consider(v):
        nonlocal best
        if not v:
            return
        v = greedy_stabilizer_reduce(v, stabilizers, rng)
        if in_kernel(v, checks) and not stab_space.contains(v):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for v in logs:
        consider(v)

    n_logs = len(logs)
    n_stabs = len([r for r in stabilizers if r])
    trials = max(256, min(12000, 64 * (n_logs + 1) + 4 * (n_stabs + n_cols)))
    for _ in range(trials):
        v = random_xor(logs, rng)
        if not v:
            v = logs[rng.randrange(n_logs)]

        # A random stabilizer displacement selects a coset representative before
        # local descent; this is a randomized upper-bound witness search, not an
        # exact distance procedure.
        if stabilizers:
            sample = min(len(stabilizers), 24)
            for r in rng.sample(stabilizers, sample):
                if rng.getrandbits(1):
                    v ^= r
        consider(v)

    if best is None:
        return None
    return {"basis": name, "vector": best, "upper_bound": best.bit_count()}


def verify_witness(basis, vector, hx_rows, hz_rows):
    if basis == "x":
        return in_kernel(vector, hz_rows) and not RowSpace(hx_rows).contains(vector)
    if basis == "z":
        return in_kernel(vector, hx_rows) and not RowSpace(hz_rows).contains(vector)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        os.makedirs(args.output_dir, exist_ok=True)
        nx, hx_rows = load_matrix(args.hx)
        nz, hz_rows = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz must have the same number of columns")
        n_cols = nx
        rng = random.Random(args.seed)

        candidates = []
        order = [
            ("x", hz_rows, hx_rows),
            ("z", hx_rows, hz_rows),
        ]
        rng.shuffle(order)
        for name, checks, stabilizers in order:
            hit = search_basis(name, checks, stabilizers, n_cols, rng)
            if hit is not None:
                candidates.append(hit)

        if candidates:
            candidates.sort(key=lambda c: (c["upper_bound"], c["basis"]))
            hit = candidates[0]
            if verify_witness(hit["basis"], hit["vector"], hx_rows, hz_rows):
                result = {
                    "status": "completed",
                    "basis": hit["basis"],
                    "vector": mask_to_list(hit["vector"], n_cols),
                    "upper_bound": hit["upper_bound"],
                }
            else:
                result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
        else:
            result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
