#!/usr/bin/env python3
import argparse
import json
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
                raise ValueError(f"{path}: dense row has wrong length")
            bits = 0
            for i, value in enumerate(row):
                if value not in (0, 1, False, True):
                    raise ValueError(f"{path}: dense entries must be binary")
                if value:
                    bits |= 1 << i
            rows.append(bits)
        return rows, n_cols

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            prev = -1
            bits = 0
            for col in row:
                col = int(col)
                if col <= prev or col < 0 or col >= n_cols:
                    raise ValueError(f"{path}: sparse rows must be strictly increasing valid indices")
                bits |= 1 << col
                prev = col
            rows.append(bits)
        return rows, n_cols

    raise ValueError(f"{path}: unsupported matrix JSON format")


def rank_rows(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return len(basis)


def row_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return [basis[p] for p in sorted(basis, reverse=True)]


def in_span(vec, rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    x = vec
    while x:
        p = x.bit_length() - 1
        if p not in basis:
            return False
        x ^= basis[p]
    return True


def rref_rows(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                for q, b in list(basis.items()):
                    if (b >> p) & 1:
                        basis[q] = b ^ x
                basis[p] = x
                break
    return basis


def nullspace_basis(rows, n_cols):
    rref = rref_rows(rows)
    pivots = set(rref)
    out = []
    for free in range(n_cols):
        if free in pivots:
            continue
        v = 1 << free
        for pivot, row in rref.items():
            if (row >> free) & 1:
                v |= 1 << pivot
        out.append(v)
    return out


def mat_vec_zero(rows, vec):
    return all(((row & vec).bit_count() & 1) == 0 for row in rows)


def vector_list(vec, n_cols):
    return [(vec >> i) & 1 for i in range(n_cols)]


def logical_basis(kernel_rows, stabilizer_rows):
    selected = []
    span = row_basis(stabilizer_rows)
    for v in kernel_rows:
        if v and not in_span(v, span):
            selected.append(v)
            span = row_basis(span + [v])
    return selected


def greedy_reduce(vec, stabilizers, rng, passes=8):
    if not stabilizers:
        return vec
    rows = stabilizers[:]
    current = vec
    current_w = current.bit_count()
    for _ in range(passes):
        improved = False
        rng.shuffle(rows)
        for row in rows:
            nxt = current ^ row
            nxt_w = nxt.bit_count()
            if nxt_w < current_w:
                current = nxt
                current_w = nxt_w
                improved = True
        if not improved:
            break
    return current


def verify(vec, kernel_checks, stabilizers):
    return vec != 0 and mat_vec_zero(kernel_checks, vec) and not in_span(vec, stabilizers)


def search_basis(name, kernel_checks, stabilizers, n_cols, rng, deadline):
    null_basis = nullspace_basis(kernel_checks, n_cols)
    log_basis = logical_basis(null_basis, stabilizers)
    if not log_basis:
        return None

    stab_basis = row_basis(stabilizers)
    candidates = []
    for v in log_basis:
        candidates.append(v)
    for v in log_basis:
        candidates.append(greedy_reduce(v, stab_basis, rng, passes=12))

    best = None
    rounds = 0
    while time.monotonic() < deadline:
        rounds += 1
        if rounds <= len(log_basis):
            v = log_basis[rounds - 1]
        else:
            v = 0
            # Biased sparse logical combinations often find better witnesses
            # than fully dense combinations on LDPC-style instances.
            p = min(0.5, max(1.0 / max(1, len(log_basis)), rng.random() * 0.25 + 0.05))
            while v == 0:
                for b in log_basis:
                    if rng.random() < p:
                        v ^= b
        for row in stab_basis:
            if rng.random() < 0.08:
                v ^= row
        v = greedy_reduce(v, stab_basis, rng, passes=10)
        candidates.append(v)

        if rounds >= 250 and best is not None and time.monotonic() > deadline - 0.05:
            break

    for v in candidates:
        if verify(v, kernel_checks, stabilizers):
            if best is None or v.bit_count() < best.bit_count():
                best = v
    if best is None:
        return None
    return {"basis": name, "vector": best, "upper_bound": best.bit_count()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("hx and hz must have the same number of columns")

    # Keep runtime bounded while still giving the randomized descent a chance.
    deadline = time.monotonic() + 1.0
    choices = [
        search_basis("x", hz, hx, nx, rng, deadline),
        search_basis("z", hx, hz, nx, rng, deadline),
    ]
    choices = [c for c in choices if c is not None]

    if choices:
        best = min(choices, key=lambda c: (c["upper_bound"], c["basis"]))
        result = {
            "status": "completed",
            "basis": best["basis"],
            "vector": vector_list(best["vector"], nx),
            "upper_bound": best["upper_bound"],
        }
    else:
        result = {
            "status": "not_found",
            "basis": None,
            "vector": [],
            "upper_bound": None,
        }

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "error", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
        sys.exit(1)
