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
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            last = -1
            for i in row:
                i = int(i)
                if i <= last or i < 0 or i >= n:
                    raise ValueError(f"invalid sparse row in {path}")
                x |= 1 << i
                last = i
            rows.append(x)
        return rows, n

    raise ValueError(f"unsupported matrix JSON format: {path}")


def popcount(x):
    return x.bit_count()


def rref(rows, n):
    rows = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        bit = 1 << col
        pivot = None
        for i in range(rank, len(rows)):
            if rows[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & bit):
                rows[i] ^= rows[rank]
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return rows[:rank], pivots


class RowSpace:
    def __init__(self, rows, n):
        self.rows, self.pivots = rref(rows, n)

    def reduce(self, x):
        for row, col in zip(self.rows, self.pivots):
            if x & (1 << col):
                x ^= row
        return x

    def contains(self, x):
        return self.reduce(x) == 0


def nullspace_basis(rows, n):
    rr, pivots = rref(rows, n)
    pivot_set = set(pivots)
    basis = []
    for free_col in range(n):
        if free_col in pivot_set:
            continue
        x = 1 << free_col
        bit = 1 << free_col
        for row, pivot_col in zip(rr, pivots):
            if row & bit:
                x |= 1 << pivot_col
        basis.append(x)
    return basis


def syndrome_zero(rows, x):
    return all(((row & x).bit_count() & 1) == 0 for row in rows)


def int_to_bits(x, n):
    return [(x >> i) & 1 for i in range(n)]


def xor_sample(rng, moves, p_num, p_den):
    x = 0
    for row in moves:
        if rng.randrange(p_den) < p_num:
            x ^= row
    return x


def greedy_reduce(x, moves, rng, passes=6):
    if not x:
        return x
    ordered = list(moves)
    for _ in range(passes):
        rng.shuffle(ordered)
        improved = False
        wx = popcount(x)
        for row in ordered:
            y = x ^ row
            wy = popcount(y)
            if y and wy < wx:
                x = y
                wx = wy
                improved = True
        if not improved:
            break
    return x


def anneal_reduce(x, moves, stabilizer_space, rng, rounds):
    if not x or not moves:
        return x
    best = x
    cur = x
    cur_w = popcount(cur)
    for t in range(rounds):
        row = moves[rng.randrange(len(moves))]
        y = cur ^ row
        if not y or stabilizer_space.contains(y):
            continue
        wy = popcount(y)
        slack = 2 if t < rounds // 3 else 1 if t < 2 * rounds // 3 else 0
        if wy <= cur_w + slack or rng.randrange(128) == 0:
            cur = y
            cur_w = wy
            if wy < popcount(best):
                best = y
    return best


def verified_candidate(x, syndrome_rows, stabilizer_space):
    return bool(x) and syndrome_zero(syndrome_rows, x) and not stabilizer_space.contains(x)


def search_basis(name, syndrome_rows, stabilizer_rows, n, rng):
    stabilizer_space = RowSpace(stabilizer_rows, n)
    kernel = nullspace_basis(syndrome_rows, n)
    if not kernel:
        return None

    stabilizer_moves = [r for r in stabilizer_rows if r]
    kernel_moves = [r for r in kernel if r]
    local_moves = stabilizer_moves + kernel_moves
    local_moves.sort(key=popcount)

    best = None

    def consider(x):
        nonlocal best
        if not x:
            return
        x = greedy_reduce(x, stabilizer_moves, rng)
        if verified_candidate(x, syndrome_rows, stabilizer_space):
            if best is None or popcount(x) < popcount(best):
                best = x
        y = greedy_reduce(x, local_moves[: min(len(local_moves), 256)], rng, passes=3)
        if verified_candidate(y, syndrome_rows, stabilizer_space):
            if best is None or popcount(y) < popcount(best):
                best = y

    for row in kernel_moves:
        if not stabilizer_space.contains(row):
            consider(row)

    trials = max(600, min(12000, 80 * max(1, n) + 25 * len(kernel_moves)))
    probabilities = [(1, 2), (1, 3), (1, 4), (1, 6), (1, 8)]
    for t in range(trials):
        p = probabilities[t % len(probabilities)]
        x = xor_sample(rng, kernel_moves, p[0], p[1])
        if x:
            consider(x)
        if best is not None and (t + 1) % 97 == 0:
            y = anneal_reduce(best, local_moves, stabilizer_space, rng, max(50, min(500, 4 * n)))
            consider(y)

    if best is None:
        return None
    if not verified_candidate(best, syndrome_rows, stabilizer_space):
        return None
    return {"basis": name, "vector": int_to_bits(best, n), "upper_bound": popcount(best)}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    hx_rows, nx = load_matrix(args.hx)
    hz_rows, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("hx and hz have different numbers of physical qubits")
    n = nx

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    rng = random.Random(args.seed)
    searches = [
        ("x", hz_rows, hx_rows),
        ("z", hx_rows, hz_rows),
    ]
    rng.shuffle(searches)

    best = None
    for name, syndrome_rows, stabilizer_rows in searches:
        hit = search_basis(name, syndrome_rows, stabilizer_rows, n, rng)
        if hit is not None and (best is None or hit["upper_bound"] < best["upper_bound"]):
            best = hit

    if best is None:
        result = {"status": "not_found", "basis": None, "vector": [], "upper_bound": None}
    else:
        result = {
            "status": "completed",
            "basis": best["basis"],
            "vector": best["vector"],
            "upper_bound": best["upper_bound"],
        }
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as exc:
        print(json.dumps({"status": "error", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
