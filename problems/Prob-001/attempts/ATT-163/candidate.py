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

    if "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            v = 0
            for i, bit in enumerate(row):
                if bit:
                    v |= 1 << i
            rows.append(v)
        return rows, n_cols

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            v = 0
            last = -1
            for i in row:
                i = int(i)
                if i <= last or i < 0 or i >= n_cols:
                    raise ValueError(f"invalid sparse row in {path}")
                v |= 1 << i
                last = i
            rows.append(v)
        return rows, n_cols

    raise ValueError(f"unrecognized matrix JSON format: {path}")


def rref(rows, n_cols):
    rows = [r for r in rows if r]
    rank = 0
    pivots = []
    for col in range(n_cols):
        pivot_at = None
        bit = 1 << col
        for i in range(rank, len(rows)):
            if rows[i] & bit:
                pivot_at = i
                break
        if pivot_at is None:
            continue
        rows[rank], rows[pivot_at] = rows[pivot_at], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & bit):
                rows[i] ^= rows[rank]
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return rows[:rank], pivots


def pivot_basis(rows, n_cols):
    basis = {}
    for row in rref(rows, n_cols)[0]:
        if row:
            basis[(row & -row).bit_length() - 1] = row
    return basis


def reduce_with_basis(v, basis):
    while v:
        col = (v & -v).bit_length() - 1
        row = basis.get(col)
        if row is None:
            return v
        v ^= row
    return 0


def in_span(v, basis):
    return reduce_with_basis(v, basis) == 0


def kernel_basis(rows, n_cols):
    rr, pivots = rref(rows, n_cols)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n_cols) if c not in pivot_set]
    out = []
    for free in free_cols:
        v = 1 << free
        for row, pivot in zip(rr, pivots):
            if row & (1 << free):
                v |= 1 << pivot
        out.append(v)
    return out


def mat_vec_zero(rows, v):
    return all(((row & v).bit_count() & 1) == 0 for row in rows)


def to_bits(v, n_cols):
    return [(v >> i) & 1 for i in range(n_cols)]


def verified(v, check_rows, stab_basis):
    return v != 0 and mat_vec_zero(check_rows, v) and not in_span(v, stab_basis)


def independent_logical_generators(check_rows, stab_rows, n_cols):
    span = pivot_basis(stab_rows, n_cols)
    logicals = []
    for v in kernel_basis(check_rows, n_cols):
        if reduce_with_basis(v, span) != 0:
            logicals.append(v)
            span = pivot_basis(list(span.values()) + [v], n_cols)
    return logicals


def sample_xor(items, rng, limit=None):
    if not items:
        return 0
    v = 0
    if limit is None:
        for item in items:
            if rng.getrandbits(1):
                v ^= item
    else:
        k = rng.randint(1, min(limit, len(items)))
        for item in rng.sample(items, k):
            v ^= item
    return v


def improve_by_stabilizers(v, moves, rng, rounds):
    best = v
    best_w = v.bit_count()
    if not moves:
        return best

    order = list(moves)
    for _ in range(rounds):
        changed = False
        rng.shuffle(order)
        for row in order:
            w = (best ^ row).bit_count()
            if w < best_w or (w == best_w and rng.random() < 0.015):
                best ^= row
                best_w = w
                changed = True
        if not changed:
            break
    return best


def search_basis(name, check_rows, stab_rows, n_cols, rng, deadline):
    stab_basis = pivot_basis(stab_rows, n_cols)
    logicals = independent_logical_generators(check_rows, stab_rows, n_cols)
    if not logicals:
        return None

    moves = [row for row in stab_rows if row and mat_vec_zero(check_rows, row)]
    candidates = list(logicals)
    best = None
    best_w = n_cols + 1

    attempts = 0
    max_attempts = max(600, 90 * (len(logicals) + len(moves) + 1))
    while attempts < max_attempts and time.monotonic() < deadline:
        attempts += 1
        if candidates:
            v = candidates.pop()
        else:
            if rng.random() < 0.70:
                v = sample_xor(logicals, rng, limit=min(8, len(logicals)))
            else:
                v = sample_xor(logicals, rng)
            if v == 0:
                continue
            if moves and rng.random() < 0.55:
                v ^= sample_xor(moves, rng, limit=min(12, len(moves)))

        v = improve_by_stabilizers(v, moves, rng, rounds=2 + (attempts % 4))
        if verified(v, check_rows, stab_basis):
            w = v.bit_count()
            if w < best_w:
                best = (name, v, w)
                best_w = w
                if w <= 1:
                    break

    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("hx and hz have different numbers of physical qubits")
    os.makedirs(args.output_dir, exist_ok=True)

    deadline = time.monotonic() + 6.0
    results = [
        search_basis("x", hz, hx, nx, rng, deadline),
        search_basis("z", hx, hz, nx, rng, deadline),
    ]
    results = [r for r in results if r is not None]

    if results:
        basis, v, w = min(results, key=lambda item: (item[2], item[0]))
        out = {
            "status": "completed",
            "basis": basis,
            "vector": to_bits(v, nx),
            "upper_bound": w,
        }
    else:
        out = {
            "status": "not_found",
            "basis": None,
            "vector": [],
            "upper_bound": None,
        }

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({
            "status": "error",
            "basis": None,
            "vector": [],
            "upper_bound": None,
        }, separators=(",", ":")))
        sys.exit(1)
