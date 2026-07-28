#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_matrix(value):
    if os.path.exists(value):
        root = os.path.realpath(os.getcwd())
        path = os.path.realpath(value)
        if path != root and not path.startswith(root + os.sep):
            raise ValueError("matrix path is outside the current project directory")
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
    else:
        obj = json.loads(value)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n:
                    raise ValueError("invalid sparse row")
                x |= 1 << col
                last = col
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def row_basis(rows):
    basis = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            y = basis.get(p)
            if y is None:
                basis[p] = x
                break
            x ^= y
    return basis


def in_rowspace(x, basis):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        y = basis.get(p)
        if y is None:
            return False
        x ^= y
    return True


def kernel_ok(rows, x):
    for row in rows:
        if ((row & x).bit_count() & 1) != 0:
            return False
    return True


def permute_row(row, order):
    y = 0
    for new_col, old_col in enumerate(order):
        if (row >> old_col) & 1:
            y |= 1 << new_col
    return y


def unpermute_row(row, order):
    y = 0
    while row:
        low = row & -row
        new_col = low.bit_length() - 1
        y |= 1 << order[new_col]
        row ^= low
    return y


def nullspace_basis(rows, n, order):
    work = [permute_row(r, order) for r in rows if r]
    rank = 0
    pivots = []
    for col in range(n):
        found = None
        bit = 1 << col
        for i in range(rank, len(work)):
            if work[i] & bit:
                found = i
                break
        if found is None:
            continue
        work[rank], work[found] = work[found], work[rank]
        pivot_row = work[rank]
        for i in range(len(work)):
            if i != rank and (work[i] & bit):
                work[i] ^= pivot_row
        pivots.append(col)
        rank += 1
        if rank == len(work):
            break

    pivot_set = set(pivots)
    out = []
    for free_col in range(n):
        if free_col in pivot_set:
            continue
        x = 1 << free_col
        free_bit = 1 << free_col
        for i, pivot_col in enumerate(pivots):
            if work[i] & free_bit:
                x |= 1 << pivot_col
        out.append(unpermute_row(x, order))
    return out


def verify(rows_for_kernel, stabilizer_basis, x):
    return x != 0 and kernel_ok(rows_for_kernel, x) and not in_rowspace(x, stabilizer_basis)


def greedy_reduce(x, kernel_rows, stabilizer_rows, stabilizer_basis, rng):
    pool = [r for r in stabilizer_rows if r and kernel_ok(kernel_rows, r)]
    pool.sort(key=lambda r: r.bit_count())
    best = x
    changed = True
    rounds = 0
    while changed and rounds < 6:
        changed = False
        rounds += 1
        if len(pool) > 1:
            head = pool[: min(len(pool), 128)]
            tail = pool[min(len(pool), 128):]
            rng.shuffle(tail)
            scan = head + tail[:512]
        else:
            scan = pool
        for row in scan:
            y = best ^ row
            if y.bit_count() < best.bit_count():
                best = y
                changed = True
    if in_rowspace(best, stabilizer_basis):
        return x
    return best


def improve_with_kernel_moves(x, kernel_rows, stabilizer_basis, moves, rng):
    best = x
    moves = [m for m in moves if m]
    moves.sort(key=lambda r: r.bit_count())
    for _ in range(3):
        changed = False
        scan = moves[:192]
        if len(moves) > 192:
            extra = moves[192:]
            rng.shuffle(extra)
            scan += extra[:384]
        for row in scan:
            y = best ^ row
            if y.bit_count() < best.bit_count() and verify(kernel_rows, stabilizer_basis, y):
                best = y
                changed = True
        if not changed:
            break
    return best


def consider(x, label, n, kernel_rows, stabilizer_rows, stabilizer_basis, moves, rng, best):
    if x == 0:
        return best
    if not kernel_ok(kernel_rows, x):
        return best
    x = greedy_reduce(x, kernel_rows, stabilizer_rows, stabilizer_basis, rng)
    if not verify(kernel_rows, stabilizer_basis, x):
        return best
    x = improve_with_kernel_moves(x, kernel_rows, stabilizer_basis, moves, rng)
    if not verify(kernel_rows, stabilizer_basis, x):
        return best
    weight = x.bit_count()
    if best is None or weight < best[2]:
        return (label, x, weight)
    return best


def random_combo(vectors, rng, max_terms):
    if not vectors:
        return 0
    x = 0
    terms = 1 + rng.randrange(max(1, max_terms))
    for _ in range(terms):
        x ^= vectors[rng.randrange(len(vectors))]
    return x


def search_one(label, kernel_rows, stabilizer_rows, n, rng):
    stabilizer_basis = row_basis(stabilizer_rows)
    best = None
    base_order = list(range(n))

    if n <= 128:
        passes = 72
    elif n <= 512:
        passes = 48
    else:
        passes = 28

    saved_moves = []
    for pass_id in range(passes):
        order = base_order[:]
        if pass_id:
            rng.shuffle(order)
        basis = nullspace_basis(kernel_rows, n, order)
        if not basis:
            continue
        basis.sort(key=lambda r: r.bit_count())
        saved_moves = basis

        for v in basis[: min(len(basis), 256)]:
            best = consider(v, label, n, kernel_rows, stabilizer_rows, stabilizer_basis, basis, rng, best)

        trials = min(900, 80 + 6 * len(basis))
        max_terms = 2 if len(basis) < 8 else min(12, 2 + len(basis).bit_length())
        for _ in range(trials):
            if best is not None and best[2] <= 1:
                return best
            x = random_combo(basis[: min(len(basis), 384)], rng, max_terms)
            best = consider(x, label, n, kernel_rows, stabilizer_rows, stabilizer_basis, basis, rng, best)

        if best is not None and pass_id >= 5:
            break

    if best is None and saved_moves:
        for _ in range(2000):
            x = random_combo(saved_moves, rng, min(24, max(2, len(saved_moves).bit_length())))
            best = consider(x, label, n, kernel_rows, stabilizer_rows, stabilizer_basis, saved_moves, rng, best)
            if best is not None:
                break
    return best


def int_to_vector(x, n):
    return [int((x >> i) & 1) for i in range(n)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        n = nx
        rng = random.Random(args.seed)

        # X logicals commute with Hz and are nontrivial modulo rows of Hx.
        bx = search_one("x", hz, hx, n, rng)
        # Z logicals commute with Hx and are nontrivial modulo rows of Hz.
        bz = search_one("z", hx, hz, n, rng)
        best = bx
        if bz is not None and (best is None or bz[2] < best[2]):
            best = bz

        if best is None:
            result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
        else:
            basis, vec, weight = best
            result = {
                "status": "completed",
                "basis": basis,
                "vector": int_to_vector(vec, n),
                "upper_bound": int(weight),
            }
    except Exception:
        result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
