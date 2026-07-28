#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_json_arg(value):
    if value == "-":
        return json.load(sys.stdin)
    with open(value, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_matrix(obj):
    if isinstance(obj, dict):
        if "dense_binary_matrix" in obj:
            obj = obj["dense_binary_matrix"]
        elif "sparse_rows" in obj:
            obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", 0))
        rows = []
        if not data:
            return [], n
        if data and all(isinstance(x, int) for x in data):
            if n <= 0:
                raise ValueError("dense data requires n_cols")
            for i in range(0, len(data), n):
                r = 0
                for j, bit in enumerate(data[i:i + n]):
                    if bit & 1:
                        r |= 1 << j
                rows.append(r)
        else:
            if n <= 0:
                n = max((len(row) for row in data), default=0)
            for row in data:
                r = 0
                for j, bit in enumerate(row):
                    if int(bit) & 1:
                        r |= 1 << j
                rows.append(r)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for inds in obj["rows"]:
            r = 0
            for j in inds:
                jj = int(j)
                if jj >= 0:
                    r |= 1 << jj
                    if jj + 1 > n:
                        n = jj + 1
            rows.append(r)
        return rows, n

    if isinstance(obj, list):
        n = max((len(row) for row in obj), default=0)
        rows = []
        for row in obj:
            r = 0
            for j, bit in enumerate(row):
                if int(bit) & 1:
                    r |= 1 << j
            rows.append(r)
        return rows, n

    raise ValueError("unsupported matrix format")


def pivot_of(x):
    return x.bit_length() - 1


def row_reduce(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = pivot_of(x)
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def reduce_by_basis(x, basis):
    while x:
        p = pivot_of(x)
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(check_rows, n):
    rb = row_reduce(check_rows)
    pivots = set(rb)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p in sorted(rb):
            row = rb[p]
            if ((row & ~(1 << p) & v).bit_count() & 1) != 0:
                v |= 1 << p
        out.append(v)
    return out


def quotient_logical_basis(kernel_basis, stab_basis):
    span = dict(stab_basis)
    logicals = []
    for v in kernel_basis:
        if reduce_by_basis(v, span):
            logicals.append(v)
            x = v
            while x:
                p = pivot_of(x)
                b = span.get(p)
                if b is None:
                    span[p] = x
                    break
                x ^= b
    return logicals


def syndrome_zero(v, checks):
    for r in checks:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def verified(v, checks, stab_basis):
    return v != 0 and syndrome_zero(v, checks) and not in_span(v, stab_basis)


def as_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


def combine_basis(basis, mask):
    v = 0
    i = 0
    m = mask
    while m:
        if m & 1:
            v ^= basis[i]
        i += 1
        m >>= 1
    return v


def random_nonzero_mask(rng, size):
    if size <= 0:
        return 0
    m = rng.getrandbits(size)
    if m == 0:
        m = 1 << rng.randrange(size)
    return m


def greedy_descent(v, stab_rows, rng, passes=6, sample_limit=512):
    if not stab_rows:
        return v
    rows = list(stab_rows)
    best = v
    for _ in range(passes):
        improved = False
        if len(rows) > sample_limit:
            scan = rng.sample(rows, sample_limit)
        else:
            scan = rows[:]
            rng.shuffle(scan)
        bw = best.bit_count()
        for s in scan:
            cand = best ^ s
            cw = cand.bit_count()
            if cw < bw:
                best = cand
                bw = cw
                improved = True
        if not improved:
            break
    return best


def sparse_repair(v, stab_rows, rng, width=96, rounds=10):
    """Random local stabilizer recombination around the current support."""
    if not stab_rows:
        return v
    best = v
    for _ in range(rounds):
        active = [s for s in stab_rows if s & best]
        pool = active if active else stab_rows
        if len(pool) > width:
            pool = rng.sample(pool, width)
        cand = best
        temp = best
        for _j in range(min(len(pool), 24)):
            s = pool[rng.randrange(len(pool))]
            trial = temp ^ s
            # Allow neutral/slightly bad moves to cross shallow barriers.
            if trial.bit_count() <= temp.bit_count() + rng.randrange(3):
                temp = trial
                if temp.bit_count() < cand.bit_count():
                    cand = temp
        cand = greedy_descent(cand, stab_rows, rng, passes=3)
        if cand.bit_count() < best.bit_count():
            best = cand
    return best


def make_individual(mask, logical_basis, stab_rows, rng):
    v = combine_basis(logical_basis, mask)
    if stab_rows:
        flips = 1 + rng.randrange(min(16, len(stab_rows)))
        for _ in range(flips):
            v ^= stab_rows[rng.randrange(len(stab_rows))]
    v = greedy_descent(v, stab_rows, rng, passes=5)
    v = sparse_repair(v, stab_rows, rng, rounds=4)
    return {"mask": mask, "vec": v, "w": v.bit_count()}


def crossover_mask(a, b, k, rng):
    if k <= 1:
        return 1
    mode = rng.randrange(4)
    if mode == 0:
        m = a["mask"] ^ b["mask"]
    elif mode == 1:
        cut = rng.randrange(1, k)
        low = (1 << cut) - 1
        m = (a["mask"] & low) | (b["mask"] & ~low)
    elif mode == 2:
        chooser = rng.getrandbits(k)
        m = (a["mask"] & chooser) | (b["mask"] & ~chooser)
    else:
        m = a["mask"] if a["w"] <= b["w"] else b["mask"]
    mut_bits = 1 + (rng.randrange(3) == 0)
    for _ in range(mut_bits):
        m ^= 1 << rng.randrange(k)
    m &= (1 << k) - 1
    if m == 0:
        m = 1 << rng.randrange(k)
    return m


def search_one(check_rows, stab_rows, n, seed, effort_scale):
    rng = random.Random(seed)
    stab_basis = row_reduce(stab_rows)
    kernel_basis = nullspace_basis(check_rows, n)
    logical_basis = quotient_logical_basis(kernel_basis, stab_basis)
    if not logical_basis:
        return None

    # Reliable basis-derived seed witnesses. This is also the positive-k fallback.
    best = None
    for v0 in logical_basis:
        v = greedy_descent(v0, stab_rows, rng, passes=8)
        v = sparse_repair(v, stab_rows, rng, rounds=6)
        if verified(v, check_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    k = len(logical_basis)
    pop_size = min(96, max(18, 4 * k + 10))
    generations = max(24, min(260, effort_scale // max(1, pop_size)))
    population = []
    seen = set()
    for i in range(pop_size):
        mask = (1 << i) if i < k else random_nonzero_mask(rng, k)
        ind = make_individual(mask, logical_basis, stab_rows, rng)
        if verified(ind["vec"], check_rows, stab_basis):
            if ind["vec"] not in seen:
                population.append(ind)
                seen.add(ind["vec"])
                if best is None or ind["w"] < best.bit_count():
                    best = ind["vec"]

    if not population and best is not None:
        population = [{"mask": 1, "vec": best, "w": best.bit_count()}]

    for _ in range(generations):
        if not population:
            break
        population.sort(key=lambda z: z["w"])
        elite_count = max(1, min(len(population), max(2, pop_size // 4)))
        next_pop = population[:elite_count]

        attempts = 0
        max_attempts = pop_size * 12
        while len(next_pop) < pop_size and attempts < max_attempts:
            attempts += 1
            a = rng.choice(population[:max(elite_count, len(population) // 2)])
            b = rng.choice(population)
            mask = crossover_mask(a, b, k, rng)
            child = make_individual(mask, logical_basis, stab_rows, rng)

            # Representative-level crossover: mix the actual verified supports
            # with the child's logical class, then descend inside the same coset.
            if rng.randrange(3) == 0:
                mix = child["vec"] ^ (a["vec"] & b["vec"])
                if syndrome_zero(mix, check_rows) and not in_span(mix, stab_basis):
                    mix = greedy_descent(mix, stab_rows, rng, passes=4)
                    if mix.bit_count() < child["w"]:
                        child = {"mask": mask, "vec": mix, "w": mix.bit_count()}

            if verified(child["vec"], check_rows, stab_basis):
                if child["vec"] not in seen:
                    next_pop.append(child)
                    seen.add(child["vec"])
                    if best is None or child["w"] < best.bit_count():
                        best = child["vec"]
            elif rng.randrange(5) == 0:
                fallback_mask = random_nonzero_mask(rng, k)
                child = make_individual(fallback_mask, logical_basis, stab_rows, rng)
                if verified(child["vec"], check_rows, stab_basis) and child["vec"] not in seen:
                    next_pop.append(child)
                    seen.add(child["vec"])
                    if best is None or child["w"] < best.bit_count():
                        best = child["vec"]

        if len(next_pop) == elite_count:
            break

        population = next_pop[:pop_size]

    if best is not None and verified(best, check_rows, stab_basis):
        return best
    # Last-resort deterministic basis fallback.
    for v0 in logical_basis:
        if verified(v0, check_rows, stab_basis):
            return v0
    return None


def choose_witness(hx_rows, hz_rows, n, seed):
    candidates = []
    # X logical: kernel of Hz modulo rowspace Hx.
    vx = search_one(hz_rows, hx_rows, n, seed ^ 0x584c4f47, effort_scale=9000)
    if vx is not None:
        candidates.append(("x", vx))
    # Z logical: kernel of Hx modulo rowspace Hz.
    vz = search_one(hx_rows, hz_rows, n, seed ^ 0x5a4c4f47, effort_scale=9000)
    if vz is not None:
        candidates.append(("z", vz))
    if not candidates:
        return None, None
    # Prefer the lower upper bound; tie-break reproducibly by seed.
    candidates.sort(key=lambda t: (t[1].bit_count(), (seed + (t[0] == "z")) & 1))
    return candidates[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    try:
        hx_rows, nx = parse_matrix(load_json_arg(args.hx))
        hz_rows, nz = parse_matrix(load_json_arg(args.hz))
        n = max(nx, nz)
        hx_rows = [r & ((1 << n) - 1) for r in hx_rows]
        hz_rows = [r & ((1 << n) - 1) for r in hz_rows]

        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        basis, vec = choose_witness(hx_rows, hz_rows, n, int(args.seed))
        if vec is None:
            out = {"status": "no_witness", "basis": None, "vector": [], "upper_bound": None}
        else:
            checks = hz_rows if basis == "x" else hx_rows
            stabs = hx_rows if basis == "x" else hz_rows
            if not verified(vec, checks, row_reduce(stabs)):
                out = {"status": "invalid", "basis": None, "vector": [], "upper_bound": None}
            else:
                bits = as_bits(vec, n)
                out = {
                    "status": "completed",
                    "basis": basis,
                    "vector": bits,
                    "upper_bound": int(sum(bits)),
                }
    except Exception:
        out = {"status": "error", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
