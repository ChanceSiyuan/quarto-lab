#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for j, b in enumerate(r[:n]):
                if int(b) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        raw_rows = obj["rows"]
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = 1 + max((int(c) for r in raw_rows for c in r), default=-1)
        rows = []
        for r in raw_rows:
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    x |= 1 << c
            rows.append(x)
        return rows, n

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for j, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def parity(x):
    return x.bit_count() & 1


def make_row_basis(rows):
    basis = {}
    for r in rows:
        x = int(r)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def reduce_by_basis(x, basis):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    rb = make_row_basis(rows)
    pivots = set(rb)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p in sorted(rb):
            row = rb[p]
            if parity(row & v):
                v |= 1 << p
        out.append(v)
    return out


def syndrome(v, checks):
    s = 0
    for i, r in enumerate(checks):
        if parity(v & r):
            s |= 1 << i
    return s


def make_syndrome_solver(checks, n):
    # Basis of column syndromes. The companion value is the qubit set producing it.
    basis = {}
    for j in range(n):
        col = 0
        bit = 1 << j
        for i, r in enumerate(checks):
            if r & bit:
                col |= 1 << i
        x = col
        combo = bit
        while x:
            p = x.bit_length() - 1
            if p in basis:
                bx, bc = basis[p]
                x ^= bx
                combo ^= bc
            else:
                basis[p] = (x, combo)
                break

    def solve(s):
        x = s
        combo = 0
        while x:
            p = x.bit_length() - 1
            item = basis.get(p)
            if item is None:
                return None
            bx, bc = item
            x ^= bx
            combo ^= bc
        return combo

    return solve


def vec_to_list(v, n):
    return [(v >> j) & 1 for j in range(n)]


def is_verified(v, checks, stab_basis):
    return v != 0 and syndrome(v, checks) == 0 and not in_rowspace(v, stab_basis)


def random_span_combo(rng, basis, limit=None):
    if not basis:
        return 0
    if limit is None:
        limit = len(basis)
    limit = max(1, min(limit, len(basis)))
    # Sparse combinations are emphasized because dense nullspace sums are rarely
    # good upper-bound witnesses.
    k = 1 + int(rng.expovariate(0.75))
    k = max(1, min(limit, k))
    v = 0
    for b in rng.sample(basis, k):
        v ^= b
    return v


def greedy_reduce(v, stab_rows, checks, stab_basis, rng, deadline):
    if not stab_rows:
        return v
    cur = v
    rows = list(stab_rows)
    best_seen = cur
    passes = 4
    while passes > 0 and time.monotonic() < deadline:
        passes -= 1
        rng.shuffle(rows)
        improved = False
        for r in rows:
            cand = cur ^ r
            if cand.bit_count() < cur.bit_count() and is_verified(cand, checks, stab_basis):
                cur = cand
                improved = True
                if cur.bit_count() < best_seen.bit_count():
                    best_seen = cur
        if not improved:
            break
    return best_seen


def basis_search(checks, stab_rows, n, rng, deadline):
    stab_basis = make_row_basis(stab_rows)
    ns = nullspace_basis(checks, n)
    candidates = []
    for b in ns:
        if is_verified(b, checks, stab_basis):
            candidates.append(b)
    # Add random quotient representatives. This helps when individual free
    # variable representatives are valid but poor, and seeds genetic diversity.
    limit = min(len(ns), 24)
    while len(candidates) < 96 and time.monotonic() < deadline and ns:
        v = random_span_combo(rng, ns, limit)
        if is_verified(v, checks, stab_basis):
            candidates.append(v)
    uniq = []
    seen = set()
    for v in sorted(candidates, key=lambda x: x.bit_count()):
        if v not in seen:
            seen.add(v)
            uniq.append(greedy_reduce(v, stab_rows, checks, stab_basis, rng, deadline))
    uniq = sorted(set(uniq), key=lambda x: x.bit_count())
    return uniq, ns, stab_basis


def crossover_child(a, b, n, rng):
    mode = rng.randrange(4)
    if mode == 0:
        cut = rng.randrange(n + 1)
        mask = (1 << cut) - 1
    elif mode == 1:
        lo = rng.randrange(n + 1)
        hi = rng.randrange(lo, n + 1)
        mask = ((1 << hi) - 1) ^ ((1 << lo) - 1)
    elif mode == 2:
        # Weight-biased uniform crossover: prefer coordinates present in either
        # parent, with occasional outside flips supplied by mutation.
        mask = 0
        union = a | b
        x = union
        while x:
            bit = x & -x
            if rng.getrandbits(1):
                mask |= bit
            x ^= bit
    else:
        # Intersection-preserving crossover keeps agreed support and swaps the
        # parents' disagreements.
        common = a & b
        diff = a ^ b
        mask = common
        x = diff
        while x:
            bit = x & -x
            if rng.random() < 0.5:
                mask |= bit
            x ^= bit
    return (a & mask) ^ (b & ~mask)


def mutate(v, n, rng, rate):
    if n <= 0:
        return v
    flips = 0
    if rng.random() < rate:
        flips += 1
    if rng.random() < rate * 0.35:
        flips += 1 + rng.randrange(3)
    for _ in range(flips):
        v ^= 1 << rng.randrange(n)
    return v


def genetic_crossover_search(checks, stab_rows, n, rng, deadline):
    seeds, ns, stab_basis = basis_search(checks, stab_rows, n, rng, deadline)
    if not seeds:
        return None
    solve_syn = make_syndrome_solver(checks, n)
    population = sorted(set(seeds), key=lambda x: x.bit_count())[:80]
    best = population[0]
    temp = 0.35
    stagnant = 0
    max_iters = max(300, min(6000, 800 + 18 * n + 8 * len(checks)))
    iters = 0

    while time.monotonic() < deadline and iters < max_iters:
        iters += 1
        if best.bit_count() <= 1:
            break
        if len(population) == 1 or rng.random() < 0.18:
            child = random_span_combo(rng, ns, min(len(ns), 32))
        else:
            elite = population[: max(2, min(len(population), 18))]
            a = rng.choice(elite)
            b = rng.choice(population)
            child = crossover_child(a, b, n, rng)
        child = mutate(child, n, rng, temp)
        s = syndrome(child, checks)
        if s:
            repair = solve_syn(s)
            if repair is None:
                continue
            child ^= repair
        if not is_verified(child, checks, stab_basis):
            # Crossing two non-stabilizer representatives can land in the
            # stabilizer subspace; perturb by a known logical seed and recheck.
            child ^= rng.choice(seeds)
            if syndrome(child, checks):
                repair = solve_syn(syndrome(child, checks))
                if repair is not None:
                    child ^= repair
            if not is_verified(child, checks, stab_basis):
                continue
        child = greedy_reduce(child, stab_rows, checks, stab_basis, rng, deadline)
        if not is_verified(child, checks, stab_basis):
            continue

        cw = child.bit_count()
        bw = best.bit_count()
        if cw < bw:
            best = child
            stagnant = 0
            temp = max(0.04, temp * 0.92)
        else:
            stagnant += 1
            if stagnant > 200:
                temp = min(0.55, temp * 1.15 + 0.01)
                stagnant = 0

        if child not in population:
            population.append(child)
        population.sort(key=lambda x: (x.bit_count(), rng.random()))
        del population[80:]

    return best


def solve_css(hx, hz, n, seed):
    rng = random.Random(seed)
    deadline = time.monotonic() + 2.75
    # X logicals commute with HZ and are nontrivial modulo rows of HX.
    # Z logicals commute with HX and are nontrivial modulo rows of HZ.
    attempts = [
        ("x", hz, hx),
        ("z", hx, hz),
    ]
    rng.shuffle(attempts)
    best = None
    for basis, checks, stabs in attempts:
        remaining = max(0.75, deadline - time.monotonic())
        local_deadline = time.monotonic() + remaining / max(1, len(attempts))
        v = genetic_crossover_search(checks, stabs, n, rng, local_deadline)
        if v is None:
            continue
        stab_basis = make_row_basis(stabs)
        if is_verified(v, checks, stab_basis):
            item = (v.bit_count(), basis, v)
            if best is None or item[0] < best[0]:
                best = item
            if best[0] <= 1:
                break

    if best is None:
        # Reliable basis-derived fallback for valid positive-k inputs.
        for basis, checks, stabs in [("x", hz, hx), ("z", hx, hz)]:
            stab_basis = make_row_basis(stabs)
            for v in nullspace_basis(checks, n):
                if is_verified(v, checks, stab_basis):
                    best = (v.bit_count(), basis, v)
                    break
            if best is not None:
                break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    try:
        hx, nx = parse_matrix(args.hx)
        hz, nz = parse_matrix(args.hz)
        n = max(nx, nz)
        os.makedirs(args.output_dir, exist_ok=True)
        result = solve_css(hx, hz, n, args.seed)
        if result is None:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
        else:
            w, basis, v = result
            out = {
                "status": "completed",
                "basis": basis,
                "vector": vec_to_list(v, n),
                "upper_bound": int(w),
            }
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
