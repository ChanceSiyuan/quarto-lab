#!/usr/bin/env python3
import argparse
import json
import random
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
            bits = 0
            for i, value in enumerate(row):
                if value & 1:
                    bits |= 1 << i
            rows.append(bits)
        return rows, n_cols

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for i in row:
                i = int(i)
                if i <= last or i < 0 or i >= n_cols:
                    raise ValueError("invalid sparse row")
                bits |= 1 << i
                last = i
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unknown matrix JSON format")


def add_basis_row(basis, row):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def make_basis(rows):
    basis = {}
    for row in rows:
        if row:
            add_basis_row(basis, row)
    return basis


def reduce_by_basis(row, basis):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(row, rows):
    return reduce_by_basis(row, make_basis(rows)) == 0


def kernel_basis(rows, n_cols):
    a = [r for r in rows if r]
    pivots = []
    r = 0
    for c in range(n_cols):
        bit = 1 << c
        pivot = None
        for i in range(r, len(a)):
            if a[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        a[r], a[pivot] = a[pivot], a[r]
        for i in range(len(a)):
            if i != r and (a[i] & bit):
                a[i] ^= a[r]
        pivots.append(c)
        r += 1
        if r == len(a):
            break

    pivot_set = set(pivots)
    free_cols = [c for c in range(n_cols) if c not in pivot_set]
    basis = []
    for f in free_cols:
        x = 1 << f
        for row, p in zip(a[: len(pivots)], pivots):
            if row & (1 << f):
                x |= 1 << p
        basis.append(x)
    return basis


def logical_generators(kernel_rows, stabilizer_rows):
    span = make_basis(stabilizer_rows)
    gens = []
    for row in kernel_rows:
        if row and add_basis_row(span, row):
            gens.append(row)
    return gens


def syndrome_zero(vec, checks):
    for row in checks:
        if (vec & row).bit_count() & 1:
            return False
    return True


def verified(vec, kernel_checks, stabilizers):
    return vec != 0 and syndrome_zero(vec, kernel_checks) and not in_rowspace(vec, stabilizers)


def bits_to_list(x, n):
    return [(x >> i) & 1 for i in range(n)]


def descend(vec, stabilizer_moves, rng, rounds):
    best = vec
    best_w = vec.bit_count()
    current = vec
    current_w = best_w
    moves = stabilizer_moves[:]
    if not moves:
        return best

    for _ in range(rounds):
        rng.shuffle(moves)
        changed = False
        for move in moves:
            cand = current ^ move
            w = cand.bit_count()
            if w < current_w:
                current, current_w = cand, w
                changed = True
                if w < best_w:
                    best, best_w = cand, w
        if not changed:
            break
    return best


def random_combo(gens, rng):
    k = len(gens)
    v = 0
    if k == 1:
        return gens[0]

    mode = rng.randrange(4)
    if mode == 0:
        take = 1
    elif mode == 1:
        take = min(k, 2 + rng.randrange(min(4, k)))
    elif mode == 2:
        take = max(1, int(rng.expovariate(1.0 / max(2.0, k ** 0.5))))
        take = min(k, take)
    else:
        take = rng.randrange(1, k + 1)

    for i in rng.sample(range(k), take):
        v ^= gens[i]
    return v


def search_basis(name, kernel_checks, stabilizers, n, seed):
    rng = random.Random((seed << 8) ^ (17 if name == "x" else 43))
    k_basis = kernel_basis(kernel_checks, n)
    gens = logical_generators(k_basis, stabilizers)
    if not gens:
        return None

    stab_basis = list(make_basis(stabilizers).values())
    stab_rows = [r for r in stabilizers if r]
    moves = stab_basis + rng.sample(stab_rows, min(len(stab_rows), 128))
    moves = sorted(set(moves), key=lambda x: x.bit_count())

    best = None
    best_w = n + 1
    start = time.monotonic()
    trial_budget = min(50000, max(2500, 300 * len(gens) + 20 * n))
    time_budget = 2.5 if n < 2000 else 5.0

    seeds = gens[:]
    seeds.sort(key=lambda x: x.bit_count())
    for v in seeds[: min(len(seeds), 256)]:
        cand = descend(v, moves, rng, 6)
        if verified(cand, kernel_checks, stabilizers):
            w = cand.bit_count()
            if w < best_w:
                best, best_w = cand, w

    for t in range(trial_budget):
        if t % 128 == 0 and time.monotonic() - start > time_budget:
            break
        v = random_combo(gens, rng)
        if not v:
            continue
        if moves and rng.random() < 0.35:
            for move in rng.sample(moves, min(len(moves), 1 + rng.randrange(5))):
                v ^= move
        cand = descend(v, moves, rng, 4)
        if verified(cand, kernel_checks, stabilizers):
            w = cand.bit_count()
            if w < best_w:
                best, best_w = cand, w

    if best is None:
        return None
    return {"basis": name, "vector": bits_to_list(best, n), "upper_bound": best_w}


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

        x_result = search_basis("x", hz, hx, nx, args.seed)
        z_result = search_basis("z", hx, hz, nx, args.seed)
        candidates = [r for r in (x_result, z_result) if r is not None]
        if candidates:
            result = min(candidates, key=lambda r: r["upper_bound"])
            out = {
                "status": "completed",
                "basis": result["basis"],
                "vector": result["vector"],
                "upper_bound": result["upper_bound"],
            }
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
