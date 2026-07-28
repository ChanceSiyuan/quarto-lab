#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict):
        if "dense_binary_matrix" in obj:
            obj = obj["dense_binary_matrix"]
        elif "sparse_rows" in obj:
            obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        if n <= 0 and data:
            n = max(len(r) for r in data)
        rows = []
        for r in data:
            bits = 0
            if isinstance(r, str):
                for i, ch in enumerate(r.strip()):
                    if ch == "1":
                        bits |= 1 << i
            else:
                for i, val in enumerate(r):
                    if int(val) & 1:
                        bits |= 1 << i
            rows.append(bits)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows") or []:
            bits = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    bits |= 1 << c
            rows.append(bits)
        return rows, n

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            bits = 0
            for i, val in enumerate(r):
                if int(val) & 1:
                    bits |= 1 << i
            rows.append(bits)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def pivot(x):
    return x.bit_length() - 1


def reduce_by_basis(x, basis):
    y = x
    for p, row in basis:
        if (y >> p) & 1:
            y ^= row
    return y


def make_basis(rows):
    by_pivot = {}
    for row in rows:
        x = int(row)
        while x:
            p = pivot(x)
            if p in by_pivot:
                x ^= by_pivot[p]
            else:
                by_pivot[p] = x
                break
    pivots = sorted(by_pivot.keys(), reverse=True)
    for p in list(reversed(pivots)):
        row = by_pivot[p]
        for q in pivots:
            if q > p and ((by_pivot[q] >> p) & 1):
                by_pivot[q] ^= row
    return [(p, by_pivot[p]) for p in sorted(by_pivot.keys(), reverse=True)]


def add_to_basis(basis, row):
    x = reduce_by_basis(row, basis)
    if not x:
        return False, basis
    rows = [r for _, r in basis]
    rows.append(x)
    return True, make_basis(rows)


def kernel_basis(check_rows, n):
    rb = make_basis(check_rows)
    pivots = {p for p, _ in rb}
    free_cols = [i for i in range(n) if i not in pivots]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in rb:
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def in_rowspace(v, stab_basis):
    return reduce_by_basis(v, stab_basis) == 0


def in_kernel(v, check_rows):
    # Parity of every check overlap must be zero.
    for row in check_rows:
        if ((row & v).bit_count() & 1) != 0:
            return False
    return True


def verified(v, check_rows, stab_basis):
    return v != 0 and in_kernel(v, check_rows) and not in_rowspace(v, stab_basis)


def quotient_basis(check_rows, stab_rows, n):
    stab_basis = make_basis(stab_rows)
    current = list(stab_basis)
    logicals = []
    for v in kernel_basis(check_rows, n):
        if reduce_by_basis(v, current):
            logicals.append(v)
            _, current = add_to_basis(current, v)
    return logicals, stab_basis


def combine_from_mask(vecs, mask):
    v = 0
    i = 0
    m = mask
    while m:
        if m & 1:
            v ^= vecs[i]
        m >>= 1
        i += 1
    return v


def random_nonzero_mask(rng, m):
    if m <= 0:
        return 0
    # Python handles large bit lengths, but getrandbits(0) is invalid.
    x = 0
    while x == 0:
        x = rng.getrandbits(m)
    return x


def minimize_by_stabilizers(v, stab_rows, rng, n, rounds=4):
    if not stab_rows:
        return v
    rows = [r for r in stab_rows if r]
    rows.extend(r for _, r in make_basis(stab_rows) if r)
    # Keep the row list bounded on very large checks while retaining diversity.
    if len(rows) > 1600:
        rows.sort(key=lambda x: x.bit_count())
        keep = rows[:800]
        rest = rows[800:]
        rng.shuffle(rest)
        rows = keep + rest[:800]

    best = v
    best_w = v.bit_count()
    for _ in range(rounds):
        rng.shuffle(rows)
        changed = False
        for r in rows:
            cand = best ^ r
            cw = cand.bit_count()
            if cw < best_w:
                best, best_w = cand, cw
                changed = True
        if not changed:
            break

    # A few randomized two-row kicks escape shallow local minima without
    # enumerating the stabilizer span.
    tries = min(256, max(16, len(rows) // 2))
    for _ in range(tries):
        a = rows[rng.randrange(len(rows))]
        b = rows[rng.randrange(len(rows))]
        cand = best ^ a ^ b
        cw = cand.bit_count()
        if cw < best_w:
            best, best_w = cand, cw
    return best


def crossover_masks(a, b, m, rng):
    if m <= 1:
        return a or b
    mode = rng.randrange(3)
    if mode == 0:
        cut = rng.randrange(1, m)
        low = (1 << cut) - 1
        child = (a & low) | (b & ~low)
    elif mode == 1:
        selector = rng.getrandbits(m)
        child = (a & selector) | (b & ~selector)
    else:
        child = a ^ b
        if child == 0:
            child = a | b
    child &= (1 << m) - 1
    if child == 0:
        child = random_nonzero_mask(rng, m)
    return child


def mutate_mask(mask, m, rng, rate):
    if m <= 0:
        return 0
    flips = 1
    if rng.random() < 0.35:
        flips += rng.randrange(1, min(4, m) + 1)
    for _ in range(flips):
        if rng.random() < rate or flips == 1:
            mask ^= 1 << rng.randrange(m)
    if mask == 0:
        mask = random_nonzero_mask(rng, m)
    return mask & ((1 << m) - 1)


def search_basis(name, check_rows, stab_rows, n, seed):
    rng = random.Random((seed << 7) ^ (0x58 if name == "x" else 0x7A) ^ n)
    logicals, stab_basis = quotient_basis(check_rows, stab_rows, n)
    m = len(logicals)
    if m == 0:
        return None

    def materialize(mask, extra_rounds=3):
        v = combine_from_mask(logicals, mask)
        v = minimize_by_stabilizers(v, stab_rows, rng, n, rounds=extra_rounds)
        if verified(v, check_rows, stab_basis):
            return v
        raw = combine_from_mask(logicals, mask)
        if verified(raw, check_rows, stab_basis):
            return raw
        return None

    pop_limit = 72 if n < 1500 else 48
    generations = 120 if n < 1500 else 70
    if m > 180:
        pop_limit = min(pop_limit, 44)
        generations = min(generations, 55)
    if m <= 16:
        pop_limit = min(pop_limit, (1 << m) - 1)
        generations = min(generations, 35)

    population = {}
    seed_masks = []
    for i in range(min(m, pop_limit // 2)):
        seed_masks.append(1 << i)
    seen_seed_masks = set(seed_masks)
    attempts = 0
    while len(seed_masks) < pop_limit and attempts < pop_limit * 20:
        attempts += 1
        mask = random_nonzero_mask(rng, m)
        if mask not in seen_seed_masks:
            seed_masks.append(mask)
            seen_seed_masks.add(mask)

    best_v = None
    best_w = n + 1
    for mask in seed_masks:
        v = materialize(mask, extra_rounds=5)
        if v is None:
            continue
        w = v.bit_count()
        population[mask] = (w, v)
        if w < best_w:
            best_v, best_w = v, w

    if best_v is None:
        # Reliable fallback: quotient construction alone gives a verified
        # logical for positive-k valid CSS inputs.
        for v in logicals:
            if verified(v, check_rows, stab_basis):
                return v
        return None

    for gen in range(generations):
        ranked = sorted(population.items(), key=lambda kv: kv[1][0])
        survivors = ranked[: max(8, pop_limit // 3)]
        population = dict(survivors)

        weights = [1.0 / (1 + item[1][0]) for item in survivors]
        total = sum(weights)

        def pick():
            t = rng.random() * total
            acc = 0.0
            for item, wt in zip(survivors, weights):
                acc += wt
                if acc >= t:
                    return item[0]
            return survivors[-1][0]

        mutation_rate = 0.04 + 0.18 * (gen / max(1, generations - 1))
        attempts = 0
        while len(population) < pop_limit and attempts < pop_limit * 30:
            attempts += 1
            a = pick()
            b = pick()
            child = crossover_masks(a, b, m, rng)
            if rng.random() < 0.85:
                child = mutate_mask(child, m, rng, mutation_rate)
            if child in population:
                child = mutate_mask(child, m, rng, 1.0)
            v = materialize(child, extra_rounds=3)
            if v is None:
                continue
            w = v.bit_count()
            population[child] = (w, v)
            if w < best_w:
                best_v, best_w = v, w

    return best_v


def solve(hx_path, hz_path, seed):
    hx, nx = load_matrix(hx_path)
    hz, nz = load_matrix(hz_path)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1) for r in hx]
    hz = [r & ((1 << n) - 1) for r in hz]

    candidates = []
    # X logicals commute with Z checks and are modulo X stabilizers.
    vx = search_basis("x", hz, hx, n, seed)
    if vx is not None:
        candidates.append(("x", vx))
    # Z logicals commute with X checks and are modulo Z stabilizers.
    vz = search_basis("z", hx, hz, n, seed ^ 0x9E3779B97F4A7C15)
    if vz is not None:
        candidates.append(("z", vz))

    if not candidates:
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    basis, vec = min(candidates, key=lambda kv: kv[1].bit_count())
    return {
        "status": "completed",
        "basis": basis,
        "vector": [(vec >> i) & 1 for i in range(n)],
        "upper_bound": int(vec.bit_count()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    # Accepted for the contract; no side effects are required.
    _ = os.path.abspath(args.output_dir)
    try:
        result = solve(args.hx, args.hz, args.seed)
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
