#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def fail(status="not_found"):
    print(json.dumps({"status": status, "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))


def resolve_project_path(path):
    root = os.path.realpath(os.getcwd())
    full = os.path.realpath(path)
    if full != root and not full.startswith(root + os.sep):
        raise ValueError("input path is outside the project directory")
    return full


def load_matrix(path):
    with open(resolve_project_path(path), "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    rows = []
    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_cols = int(obj["n_cols"])
        data = obj["data"]
        for row in data:
            if len(row) != n_cols:
                raise ValueError("dense row has wrong length")
            bits = 0
            for i, val in enumerate(row):
                if val not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if int(val):
                    bits |= 1 << i
            rows.append(bits)
        return rows, n_cols

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        for row in obj["rows"]:
            last = -1
            bits = 0
            for idx in row:
                idx = int(idx)
                if idx <= last or idx < 0 or idx >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing and in range")
                bits |= 1 << idx
                last = idx
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unrecognized matrix JSON format")


def reduce_basis(rows):
    basis = {}
    for row in rows:
        x = row
        for p in sorted(basis, reverse=True):
            if (x >> p) & 1:
                x ^= basis[p]
        if x:
            p = x.bit_length() - 1
            for q, b in list(basis.items()):
                if (b >> p) & 1:
                    basis[q] = b ^ x
            basis[p] = x
    return basis


def in_span(x, basis):
    y = x
    for p in sorted(basis, reverse=True):
        if (y >> p) & 1:
            y ^= basis[p]
    if y:
        return False
    return True


def add_to_basis(x, basis):
    y = x
    for p in sorted(basis, reverse=True):
        if (y >> p) & 1:
            y ^= basis[p]
    if y:
        p = y.bit_length() - 1
        for q, row in list(basis.items()):
            if (row >> p) & 1:
                basis[q] = row ^ y
        basis[p] = y
        return True
    return False


def nullspace_basis(check_rows, n_cols):
    reduced = reduce_basis(check_rows)
    pivots = set(reduced)
    free_cols = [c for c in range(n_cols) if c not in pivots]
    out = []
    for free in free_cols:
        x = 1 << free
        for p in sorted(pivots):
            row = reduced[p]
            if (row >> free) & 1:
                x |= 1 << p
        out.append(x)
    return out


def syndrome_zero(v, checks):
    for row in checks:
        if (v & row).bit_count() & 1:
            return False
    return True


def vector_from_int(v, n_cols):
    return [(v >> i) & 1 for i in range(n_cols)]


def logical_generators(kernel_rows, stabilizer_rows):
    span = reduce_basis(stabilizer_rows)
    logicals = []
    for row in kernel_rows:
        if add_to_basis(row, span):
            logicals.append(row)
    return logicals


def random_combo(rows, rng, force_nonempty=False):
    x = 0
    used = False
    for row in rows:
        if rng.getrandbits(1):
            x ^= row
            used = True
    if force_nonempty and rows and not used:
        x ^= rows[rng.randrange(len(rows))]
    return x


def greedy_reduce(v, stabilizers, rng, passes):
    if not stabilizers:
        return v
    rows = list(stabilizers)
    best = v
    best_w = v.bit_count()
    for _ in range(passes):
        rng.shuffle(rows)
        changed = False
        for row in rows:
            cand = best ^ row
            w = cand.bit_count()
            if w < best_w:
                best = cand
                best_w = w
                changed = True
        if not changed:
            break
    return best


def search_basis(name, kernel_checks, stabilizer_rows, n_cols, seed):
    kernel = nullspace_basis(kernel_checks, n_cols)
    logicals = logical_generators(kernel, stabilizer_rows)
    if not logicals:
        return None

    rng = random.Random((seed << 8) ^ (0x58 if name == "x" else 0x5A) ^ n_cols)
    stab_basis = reduce_basis(stabilizer_rows)
    best = None
    best_w = n_cols + 1

    def consider(v):
        nonlocal best, best_w
        if v == 0 or not syndrome_zero(v, kernel_checks) or in_span(v, stab_basis):
            return
        w = v.bit_count()
        if w < best_w:
            best = v
            best_w = w

    ordered_stabs = sorted(set(stabilizer_rows), key=lambda x: x.bit_count(), reverse=True)
    for g in logicals:
        consider(greedy_reduce(g, ordered_stabs, rng, 4))

    rounds = 800 + 80 * min(n_cols, 200) + 150 * min(len(logicals), 64)
    rounds = min(rounds, 30000)
    for t in range(rounds):
        base = random_combo(logicals, rng, force_nonempty=True)
        if stabilizer_rows:
            if t & 1:
                base ^= random_combo(stabilizer_rows, rng, force_nonempty=False)
            else:
                for row in rng.sample(stabilizer_rows, min(len(stabilizer_rows), 1 + rng.randrange(8))):
                    if rng.random() < 0.65:
                        base ^= row
        candidate = greedy_reduce(base, ordered_stabs, rng, 2 + (t % 3 == 0))
        consider(candidate)

    if best is None:
        return None
    return {"basis": name, "vector": vector_from_int(best, n_cols), "upper_bound": best_w}


def main():
    parser = argparse.ArgumentParser(description="Randomized CSS logical upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz have different column counts")
        os.makedirs(resolve_project_path(args.output_dir), exist_ok=True)

        x_result = search_basis("x", hz, hx, nx, args.seed)
        z_result = search_basis("z", hx, hz, nx, args.seed)
        results = [r for r in (x_result, z_result) if r is not None]
        if not results:
            fail()
            return
        result = min(results, key=lambda r: (r["upper_bound"], r["basis"]))
        print(json.dumps({"status": "completed", **result}, separators=(",", ":")))
    except Exception:
        fail("error")


if __name__ == "__main__":
    main()
