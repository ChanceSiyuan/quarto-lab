#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n_cols = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            x = 0
            for j, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n_cols

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data", [])
        n_cols = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for j, b in enumerate(r[:n_cols]):
                if int(b) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n_cols

    if "rows" in obj:
        sparse = obj.get("rows", [])
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n_cols <= 0:
            n_cols = 1 + max((int(c) for r in sparse for c in r), default=-1)
        rows = []
        for r in sparse:
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n_cols:
                    x ^= 1 << c
            rows.append(x)
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


def wt(x):
    return x.bit_count()


def rref(rows, n):
    a = [r & ((1 << n) - 1) for r in rows if r]
    rank = 0
    pivots = []
    for col in range(n):
        bit = 1 << col
        piv = None
        for i in range(rank, len(a)):
            if a[i] & bit:
                piv = i
                break
        if piv is None:
            continue
        a[rank], a[piv] = a[piv], a[rank]
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
    basis = []
    for f in range(n):
        if f in pivot_set:
            continue
        v = 1 << f
        for row, p in zip(rr, pivots):
            if row & (1 << f):
                v |= 1 << p
        basis.append(v)
    return basis


def add_basis(basis, x):
    x = reduce_by_basis(basis, x)
    if not x:
        return False
    p = x.bit_length() - 1
    basis[p] = x
    return True


def reduce_by_basis(basis, x):
    for p in sorted(basis.keys(), reverse=True):
        if x & (1 << p):
            x ^= basis[p]
    return x


def make_basis(rows):
    basis = {}
    for r in rows:
        add_basis(basis, r)
    return basis


def in_span(basis, x):
    return reduce_by_basis(basis, x) == 0


def kernel_ok(check_rows, v):
    return all(((r & v).bit_count() & 1) == 0 for r in check_rows)


def vector_from_coeff(coeff, logical_basis):
    v = 0
    c = coeff
    while c:
        lsb = c & -c
        i = lsb.bit_length() - 1
        if i < len(logical_basis):
            v ^= logical_basis[i]
        c ^= lsb
    return v


def greedy_reduce(v, stab_rows, rng, rounds=2):
    if not stab_rows:
        return v
    rows = sorted([r for r in stab_rows if r], key=wt)
    cur = v
    improved = True
    while improved:
        improved = False
        for r in rows:
            nr = cur ^ r
            if wt(nr) < wt(cur):
                cur = nr
                improved = True
    for _ in range(rounds):
        sample = rows[:]
        rng.shuffle(sample)
        for r in sample:
            nr = cur ^ r
            if wt(nr) <= wt(cur) and (wt(nr) < wt(cur) or rng.random() < 0.08):
                cur = nr
        for r in rows:
            nr = cur ^ r
            if wt(nr) < wt(cur):
                cur = nr
    return cur


def build_logical_basis(check_rows, stab_rows, n):
    ker = sorted(nullspace_basis(check_rows, n), key=wt)
    span = make_basis(stab_rows)
    logical = []
    for v in ker:
        if not in_span(span, v):
            logical.append(v)
            add_basis(span, v)
    return logical


def random_coeff(rng, k):
    if k <= 0:
        return 0
    if k <= 62:
        c = rng.getrandbits(k)
    else:
        c = 0
        for i in range(k):
            if rng.getrandbits(1):
                c |= 1 << i
    if c == 0:
        c = 1 << rng.randrange(k)
    return c


def mutate_coeff(c, k, rng, rate):
    for i in range(k):
        if rng.random() < rate:
            c ^= 1 << i
    if c == 0 and k:
        c = 1 << rng.randrange(k)
    return c


def crossover(a, b, k, rng):
    if k <= 1:
        return a or b or 1
    mode = rng.randrange(3)
    if mode == 0:
        mask = 0
        for i in range(k):
            if rng.getrandbits(1):
                mask |= 1 << i
        c = (a & mask) | (b & ~mask)
    elif mode == 1:
        cut = rng.randrange(1, k)
        low = (1 << cut) - 1
        c = (a & low) | (b & ~low)
    else:
        # Symmetric-difference crossover deliberately explores a new logical
        # class while staying in the verified quotient space.
        c = a ^ b
    c &= (1 << k) - 1
    if c == 0:
        c = 1 << rng.randrange(k)
    return c


def certify(v, check_rows, stab_basis):
    return v != 0 and kernel_ok(check_rows, v) and not in_span(stab_basis, v)


def search_side(name, check_rows, stab_rows, n, seed, time_budget):
    rng = random.Random((seed * 1000003) ^ (0x5858 if name == "x" else 0x5A5A) ^ n)
    stab_basis = make_basis(stab_rows)
    logical_basis = build_logical_basis(check_rows, stab_rows, n)
    k = len(logical_basis)
    if k == 0:
        return None

    start = time.monotonic()
    pop = []
    best = None

    def add_individual(coeff, extra_rounds=2):
        nonlocal best
        coeff &= (1 << k) - 1
        if coeff == 0:
            return
        v = vector_from_coeff(coeff, logical_basis)
        v = greedy_reduce(v, stab_rows, rng, rounds=extra_rounds)
        if certify(v, check_rows, stab_basis):
            item = (wt(v), coeff, v)
            pop.append(item)
            if best is None or item[0] < best[0]:
                best = item

    for i in range(k):
        add_individual(1 << i, extra_rounds=3)
    for i in range(min(4 * k + 24, 180)):
        c = random_coeff(rng, k)
        if i < k:
            c ^= 1 << i
        add_individual(c, extra_rounds=2)

    if best is None:
        for i, v in enumerate(logical_basis):
            if certify(v, check_rows, stab_basis):
                return {"basis": name, "vector": v, "upper_bound": wt(v)}
        return None

    max_pop = 72 if n < 2000 else 48
    generations = 180 if n < 2000 else 80
    mutation = min(0.22, max(0.015, 2.0 / max(2, k)))

    for gen in range(generations):
        if time.monotonic() - start > time_budget:
            break
        pop.sort(key=lambda t: (t[0], rng.random()))
        pop = pop[:max_pop]
        elite = pop[: max(4, min(len(pop), max_pop // 4))]
        for _ in range(max(8, max_pop // 2)):
            p1 = rng.choice(elite)
            p2 = rng.choice(pop)
            c = crossover(p1[1], p2[1], k, rng)
            c = mutate_coeff(c, k, rng, mutation)
            add_individual(c, extra_rounds=1 + (gen % 3 == 0))
        if gen % 9 == 0:
            add_individual(random_coeff(rng, k), extra_rounds=3)

    if best is None:
        return None
    return {"basis": name, "vector": best[2], "upper_bound": best[0]}


def bits_to_list(v, n):
    return [1 if (v >> i) & 1 else 0 for i in range(n)]


def solve(args):
    hx, nx = parse_matrix(args.hx)
    hz, nz = parse_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1) for r in hx]
    hz = [r & ((1 << n) - 1) for r in hz]

    seed = int(args.seed)
    # Keep the entrypoint responsive under unknown evaluator limits while still
    # giving both CSS bases a chance to produce and improve a witness.
    per_side = 7.0 if n < 4000 else 4.0
    candidates = [
        search_side("x", hz, hx, n, seed, per_side),
        search_side("z", hx, hz, n, seed ^ 0x9E3779B97F4A7C15, per_side),
    ]
    candidates = [c for c in candidates if c is not None]
    if not candidates:
        return {"status": "failed", "basis": "", "vector": [], "upper_bound": None}
    best = min(candidates, key=lambda c: (c["upper_bound"], c["basis"]))
    return {
        "status": "completed",
        "basis": best["basis"],
        "vector": bits_to_list(best["vector"], n),
        "upper_bound": best["upper_bound"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    try:
        out = solve(args)
    except Exception:
        out = {"status": "failed", "basis": "", "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
