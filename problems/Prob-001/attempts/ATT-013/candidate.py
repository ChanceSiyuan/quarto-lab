#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for i, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        n = int(obj.get("n_cols", max((len(r) for r in obj["data"]), default=0)))
        rows = []
        for r in obj["data"]:
            x = 0
            for i, v in enumerate(r[:n]):
                if int(v) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for c in r:
                ci = int(c)
                if 0 <= ci < n:
                    x ^= 1 << ci
            rows.append(x)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def mask_n(n):
    return (1 << n) - 1 if n > 0 else 0


def rref(rows, n):
    a = [r & mask_n(n) for r in rows if r & mask_n(n)]
    pivots = []
    rank = 0
    for col in range(n):
        sel = -1
        bit = 1 << col
        for i in range(rank, len(a)):
            if a[i] & bit:
                sel = i
                break
        if sel < 0:
            continue
        a[rank], a[sel] = a[sel], a[rank]
        for i in range(len(a)):
            if i != rank and (a[i] & bit):
                a[i] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == len(a):
            break
    return a[:rank], pivots


def nullspace_basis(rows, n):
    rr, pivots = rref(rows, n)
    pivot_set = set(pivots)
    out = []
    for f in range(n):
        if f in pivot_set:
            continue
        v = 1 << f
        for row, p in zip(rr, pivots):
            if row & (1 << f):
                v |= 1 << p
        out.append(v)
    return out


def add_to_echelon(basis, row):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def echelon_basis(rows, n):
    basis = {}
    m = mask_n(n)
    for r in rows:
        add_to_echelon(basis, r & m)
    return basis


def in_span(row, basis):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        x ^= b
    return True


def mat_vec_zero(rows, vec):
    # Rows represent parity checks; the dot product is parity(row & vec).
    for r in rows:
        if (r & vec).bit_count() & 1:
            return False
    return True


def bits_to_list(vec, n):
    return [(vec >> i) & 1 for i in range(n)]


def xor_from_coeff(coeff, basis):
    v = 0
    c = coeff
    while c:
        lsb = c & -c
        i = lsb.bit_length() - 1
        if i < len(basis):
            v ^= basis[i]
        c ^= lsb
    return v


def certify(vec, kernel_checks, stabilizer_basis):
    return vec != 0 and mat_vec_zero(kernel_checks, vec) and not in_span(vec, stabilizer_basis)


def greedy_reduce(vec, stab_rows, kernel_checks, stab_basis, rng, deadline, rounds=3):
    if not stab_rows:
        return vec
    best = vec
    best_w = vec.bit_count()
    rows = list(stab_rows)
    for _ in range(rounds):
        if time.monotonic() > deadline:
            break
        rng.shuffle(rows)
        improved = False
        for s in rows:
            cand = best ^ s
            w = cand.bit_count()
            if w < best_w and certify(cand, kernel_checks, stab_basis):
                best, best_w = cand, w
                improved = True
        if not improved:
            break
    return best


def build_logical_basis(kernel_basis, stabilizer_rows, n, rng):
    span = echelon_basis(stabilizer_rows, n)
    ordered = list(kernel_basis)
    ordered.sort(key=lambda x: (x.bit_count(), rng.random()))
    logical = []
    for v in ordered:
        if add_to_echelon(span, v):
            logical.append(v)
    return logical


def random_log_coeff(k, rng):
    if k <= 0:
        return 0
    x = rng.getrandbits(k)
    return x if x else (1 << rng.randrange(k))


def random_sparse_coeff(length, rng, max_terms=16):
    coeff = 0
    if length <= 0:
        return coeff
    terms = 1 + rng.randrange(max(1, min(max_terms, length)))
    for _ in range(terms):
        coeff ^= 1 << rng.randrange(length)
    return coeff


def mutate_coeff(coeff, length, rng, p_num=2, p_den=5):
    if length <= 0:
        return coeff
    flips = 1
    if rng.randrange(p_den) < p_num:
        flips += rng.randrange(1, min(4, length) + 1)
    for _ in range(flips):
        coeff ^= 1 << rng.randrange(length)
    return coeff


def crossover(a, b, length, rng):
    if length <= 0:
        return 0
    mask = rng.getrandbits(length)
    return (a & mask) ^ (b & ~mask)


def search_basis(label, kernel_checks, stabilizer_rows, n, seed, deadline):
    rng = random.Random((seed << 7) ^ (0x58 if label == "x" else 0x7a) ^ n)
    stab_basis = echelon_basis(stabilizer_rows, n)
    ker_basis = nullspace_basis(kernel_checks, n)
    logical_basis = build_logical_basis(ker_basis, stabilizer_rows, n, rng)
    k = len(logical_basis)
    if k == 0:
        return None

    # Use independent stabilizer generators from row reduction for compact genomes.
    stab_reduced = list(echelon_basis(stabilizer_rows, n).values())
    r = len(stab_reduced)

    best = None
    seeds = []
    for i, lb in enumerate(logical_basis[: min(k, 64)]):
        if time.monotonic() > deadline:
            break
        v = greedy_reduce(lb, stab_reduced, kernel_checks, stab_basis, rng, deadline, rounds=2)
        if certify(v, kernel_checks, stab_basis):
            lc = 1 << i
            seeds.append((lc, 0, v, v.bit_count()))
            if best is None or v.bit_count() < best.bit_count():
                best = v

    pop_size = 36 if n < 2500 else 24
    generations = 90 if n < 2500 else 45
    population = []
    population.extend(seeds[:pop_size])

    while len(population) < pop_size and time.monotonic() <= deadline:
        lc = random_sparse_coeff(k, rng, max_terms=12) if k > 64 else random_log_coeff(k, rng)
        if lc == 0:
            lc = random_log_coeff(k, rng)
        sc = random_sparse_coeff(r, rng, max_terms=20) if r and rng.random() < 0.75 else 0
        v = xor_from_coeff(lc, logical_basis) ^ xor_from_coeff(sc, stab_reduced)
        v = greedy_reduce(v, stab_reduced, kernel_checks, stab_basis, rng, deadline, rounds=1)
        if certify(v, kernel_checks, stab_basis):
            item = (lc, sc, v, v.bit_count())
            population.append(item)
            if best is None or item[3] < best.bit_count():
                best = v

    if best is None:
        # Guaranteed positive-k fallback: a quotient-basis representative is in the
        # kernel and outside the stabilizer span by construction, then certified.
        for lb in logical_basis:
            v = greedy_reduce(lb, stab_reduced, kernel_checks, stab_basis, rng, deadline, rounds=1)
            if certify(v, kernel_checks, stab_basis):
                return {"basis": label, "vector": v, "weight": v.bit_count()}
        return None

    for _ in range(generations):
        if time.monotonic() > deadline or not population:
            break
        population.sort(key=lambda t: t[3])
        population = population[:pop_size]
        if population[0][3] < best.bit_count():
            best = population[0][2]
        elite_count = max(4, pop_size // 4)
        children = population[:elite_count]
        while len(children) < pop_size and time.monotonic() <= deadline:
            p1 = population[rng.randrange(min(len(population), elite_count * 2))]
            p2 = population[rng.randrange(min(len(population), elite_count * 2))]
            lc = crossover(p1[0], p2[0], k, rng)
            if lc == 0:
                lc = p1[0] or p2[0] or random_log_coeff(k, rng)
            sc = crossover(p1[1], p2[1], r, rng)
            if rng.random() < 0.55:
                lc = mutate_coeff(lc, k, rng)
                if lc == 0:
                    lc = random_log_coeff(k, rng)
            if rng.random() < 0.85:
                sc = mutate_coeff(sc, r, rng)
            v = xor_from_coeff(lc, logical_basis) ^ xor_from_coeff(sc, stab_reduced)
            v = greedy_reduce(v, stab_reduced, kernel_checks, stab_basis, rng, deadline, rounds=2)
            if certify(v, kernel_checks, stab_basis):
                children.append((lc, sc, v, v.bit_count()))
                if v.bit_count() < best.bit_count():
                    best = v
        population = children

    if best is not None and certify(best, kernel_checks, stab_basis):
        return {"basis": label, "vector": best, "weight": best.bit_count()}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & mask_n(n) for r in hx]
    hz = [r & mask_n(n) for r in hz]

    deadline = time.monotonic() + 28.0
    candidates = []
    # X logicals commute with Z checks and are nontrivial modulo X stabilizers.
    for spec in (("x", hz, hx), ("z", hx, hz)):
        if time.monotonic() > deadline:
            break
        res = search_basis(spec[0], spec[1], spec[2], n, args.seed, deadline)
        if res is not None:
            candidates.append(res)

    if candidates:
        best = min(candidates, key=lambda t: (t["weight"], 0 if t["basis"] == "x" else 1))
        obj = {
            "status": "completed",
            "basis": best["basis"],
            "vector": bits_to_list(best["vector"], n),
            "upper_bound": int(best["weight"]),
        }
    else:
        obj = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(obj, separators=(",", ":")))


if __name__ == "__main__":
    main()
