#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import sys
import time


def read_matrix_arg(value):
    if value == "-":
        obj = json.load(sys.stdin)
    elif os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            obj = json.load(f)
    else:
        obj = json.loads(value)
    return parse_matrix(obj)


def parse_matrix(obj):
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        return rows_to_ints(obj, n), n

    if not isinstance(obj, dict):
        raise ValueError("matrix must be a JSON object or row list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        data = obj["data"]
        if data and all(isinstance(x, int) for x in data):
            if n <= 0 or len(data) % n:
                raise ValueError("flat dense data requires n_cols")
            data = [data[i : i + n] for i in range(0, len(data), n)]
        if n <= 0:
            n = max((len(r) for r in data), default=0)
        return rows_to_ints(data, n), n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for c in r:
                c = int(c)
                if c < 0:
                    raise ValueError("negative column index")
                x ^= 1 << c
                if c + 1 > n:
                    n = c + 1
            rows.append(x)
        return rows, n

    raise ValueError("unrecognized matrix format")


def rows_to_ints(data, n):
    rows = []
    for row in data:
        x = 0
        for i, bit in enumerate(row[:n]):
            if int(bit) & 1:
                x |= 1 << i
        rows.append(x)
    return rows


def parity(x):
    return x.bit_count() & 1


def reduce_by_basis(x, basis):
    while x:
        p = x.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return x
        x ^= row
    return 0


def add_to_basis(x, basis):
    x = reduce_by_basis(x, basis)
    if not x:
        return False
    p = x.bit_length() - 1
    for q, row in list(basis.items()):
        if (row >> p) & 1:
            basis[q] = row ^ x
    basis[p] = x
    return True


def make_basis(rows):
    basis = {}
    for r in rows:
        if r:
            add_to_basis(r, basis)
    return basis


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    mat = [r & ((1 << n) - 1) for r in rows if r]
    r = 0
    pivots = []
    for c in range(n):
        pivot = None
        for i in range(r, len(mat)):
            if (mat[i] >> c) & 1:
                pivot = i
                break
        if pivot is None:
            continue
        mat[r], mat[pivot] = mat[pivot], mat[r]
        for i in range(len(mat)):
            if i != r and ((mat[i] >> c) & 1):
                mat[i] ^= mat[r]
        pivots.append(c)
        r += 1
        if r == len(mat):
            break

    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    out = []
    for f in free_cols:
        x = 1 << f
        for row, c in zip(mat[: len(pivots)], pivots):
            if parity(row & x):
                x |= 1 << c
        out.append(x)
    return out


def vector_from_int(x, n):
    return [(x >> i) & 1 for i in range(n)]


def verify(v, check_rows, stabilizer_basis):
    if not v:
        return False
    for r in check_rows:
        if parity(r & v):
            return False
    return not in_rowspace(v, stabilizer_basis)


def logical_generators(check_rows, stab_rows, n):
    stab_basis = make_basis(stab_rows)
    span = dict(stab_basis)
    logicals = []
    for k in nullspace_basis(check_rows, n):
        if k and not in_rowspace(k, span):
            logicals.append(k)
            add_to_basis(k, span)
    return logicals, stab_basis


def column_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        x = r
        while x:
            lb = x & -x
            deg[lb.bit_length() - 1] += 1
            x ^= lb
    return deg


def weighted_score(row, residual, reliability, rng, temperature):
    x = row
    score = 0.0
    while x:
        lb = x & -x
        i = lb.bit_length() - 1
        score += reliability[i] if ((residual >> i) & 1) else -reliability[i]
        x ^= lb
    return score + rng.gauss(0.0, temperature)


def greedy_polish(v, stab_rows):
    improved = True
    while improved:
        improved = False
        best = v
        best_w = v.bit_count()
        for s in stab_rows:
            u = v ^ s
            w = u.bit_count()
            if w < best_w:
                best = u
                best_w = w
        if best != v:
            v = best
            improved = True
    return v


def bp_reliability_reduce(seed, stab_rows, check_rows, n, rng, deadline):
    if not stab_rows:
        return seed

    sdeg = column_degrees(stab_rows, n)
    cdeg = column_degrees(check_rows, n)
    base = [1.0 + math.log1p(cdeg[i] + sdeg[i]) for i in range(n)]
    best = greedy_polish(seed, stab_rows)
    best_w = best.bit_count()

    row_count = len(stab_rows)
    restarts = min(64, max(12, 4 + row_count // 3))
    step_cap = min(1600, max(120, 10 * row_count))

    for restart in range(restarts):
        if time.monotonic() > deadline:
            break

        residual = seed
        # Randomized restart in the same logical coset.  Later restarts use
        # lower density so the search alternates exploration and polishing.
        density = 0.30 / (1.0 + 0.05 * restart)
        for s in stab_rows:
            if rng.random() < density:
                residual ^= s

        memory = [0.0] * n
        tabu = {}
        temperature = 1.25 + 0.08 * (restart % 7)
        no_gain = 0

        for step in range(step_cap):
            if time.monotonic() > deadline:
                break
            w = residual.bit_count()
            if w < best_w:
                best = residual
                best_w = w
                no_gain = 0
            else:
                no_gain += 1
                if no_gain > 120:
                    break

            reliability = base[:]
            x = residual
            while x:
                lb = x & -x
                i = lb.bit_length() - 1
                memory[i] = 0.85 * memory[i] + 0.15
                x ^= lb
            for i in range(n):
                reliability[i] += 1.7 * memory[i] + rng.random() * 0.12

            sample = min(row_count, 96)
            if sample == row_count:
                indices = range(row_count)
            else:
                indices = rng.sample(range(row_count), sample)

            best_i = None
            best_score = -1.0e100
            for i in indices:
                if tabu.get(i, -1) > step:
                    continue
                score = weighted_score(stab_rows[i], residual, reliability, rng, temperature)
                if score > best_score:
                    best_score = score
                    best_i = i

            if best_i is None:
                break

            old_w = residual.bit_count()
            candidate = residual ^ stab_rows[best_i]
            new_w = candidate.bit_count()
            accept = new_w <= old_w or rng.random() < math.exp(min(0.0, (old_w - new_w) / temperature))
            if accept:
                residual = candidate
                tabu[best_i] = step + 2 + rng.randrange(5)
            temperature *= 0.997

        polished = greedy_polish(residual, stab_rows)
        if polished.bit_count() < best_w:
            best = polished
            best_w = polished.bit_count()

    return best


def candidate_seeds(logicals, rng):
    seeds = list(logicals)
    ell = len(logicals)
    if ell <= 1:
        return seeds
    trials = min(96, 8 * ell + 24)
    for _ in range(trials):
        x = 0
        # A sparse random logical combination often gives an easier coset than
        # the raw quotient basis vector.
        p = rng.uniform(0.15, 0.55)
        for g in logicals:
            if rng.random() < p:
                x ^= g
        if x:
            seeds.append(x)
    return seeds


def solve_basis(name, check_rows, stab_rows, n, rng, deadline):
    logicals, stab_basis = logical_generators(check_rows, stab_rows, n)
    if not logicals:
        return None

    clean_stabs = [r for r in stab_rows if r]
    best = None
    for seed in candidate_seeds(logicals, rng):
        if time.monotonic() > deadline:
            break
        reduced = bp_reliability_reduce(seed, clean_stabs, check_rows, n, rng, deadline)
        if verify(reduced, check_rows, stab_basis):
            if best is None or reduced.bit_count() < best.bit_count():
                best = reduced

    if best is None:
        for seed in logicals:
            polished = greedy_polish(seed, clean_stabs)
            if verify(polished, check_rows, stab_basis):
                if best is None or polished.bit_count() < best.bit_count():
                    best = polished

    if best is None:
        return None
    return {
        "basis": name,
        "vector": vector_from_int(best, n),
        "upper_bound": int(best.bit_count()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    try:
        hx, nx = read_matrix_arg(args.hx)
        hz, nz = read_matrix_arg(args.hz)
        n = max(nx, nz)
        mask = (1 << n) - 1
        hx = [r & mask for r in hx]
        hz = [r & mask for r in hz]

        rng = random.Random(args.seed)
        deadline = time.monotonic() + 28.0
        results = []
        for item in (
            solve_basis("x", hz, hx, n, rng, deadline),
            solve_basis("z", hx, hz, n, rng, deadline),
        ):
            if item is not None:
                results.append(item)

        if results:
            results.sort(key=lambda d: (d["upper_bound"], 0 if d["basis"] == "x" else 1))
            out = {"status": "completed", **results[0]}
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
