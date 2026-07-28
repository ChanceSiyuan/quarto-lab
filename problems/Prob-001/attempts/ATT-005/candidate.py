#!/usr/bin/env python3
import argparse
import json
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        return [row_to_bits(r, n) for r in obj], n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        n = int(obj.get("n_cols", 0))
        data = obj.get("data", [])
        if data and all(isinstance(x, int) for x in data):
            rows = [data[i : i + n] for i in range(0, len(data), n)]
        else:
            rows = data
        return [row_to_bits(r, n) for r in rows], n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        out = []
        for row in obj.get("rows", []):
            bits = 0
            for c in row:
                c = int(c)
                if 0 <= c < n:
                    bits |= 1 << c
            out.append(bits)
        return out, n
    raise ValueError("unsupported matrix JSON format")


def row_to_bits(row, n):
    bits = 0
    for i, v in enumerate(row[:n]):
        if int(v) & 1:
            bits |= 1 << i
    return bits


def rref(rows, n):
    a = [int(r) for r in rows if r]
    rank = 0
    pivots = []
    for col in range(n):
        bit = 1 << col
        pivot = None
        for i in range(rank, len(a)):
            if a[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        for i in range(len(a)):
            if i != rank and (a[i] & bit):
                a[i] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == len(a):
            break
    return a[:rank], pivots


def reduction_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def reduce_with_basis(x, basis):
    while x:
        p = x.bit_length() - 1
        row = basis.get(p)
        if row is None:
            break
        x ^= row
    return x


def kernel_basis(rows, n):
    rr, pivots = rref(rows, n)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    out = []
    for f in free_cols:
        v = 1 << f
        for row, p in zip(rr, pivots):
            if row & (1 << f):
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, checks):
    for row in checks:
        if (v & row).bit_count() & 1:
            return False
    return True


def verified(v, commute_rows, stab_basis):
    return v != 0 and syndrome_zero(v, commute_rows) and reduce_with_basis(v, stab_basis) != 0


def independent_logicals(commute_rows, stab_rows, n):
    stab_basis = reduction_basis(stab_rows)
    quotient_basis = {}
    reps = []
    for v in kernel_basis(commute_rows, n):
        r = reduce_with_basis(v, stab_basis)
        if r == 0:
            continue
        rr = reduce_with_basis(r, quotient_basis)
        if rr:
            quotient_basis[rr.bit_length() - 1] = rr
            reps.append(v)
    return reps, stab_basis


def bits_to_list(v, n):
    return [1 if (v >> i) & 1 else 0 for i in range(n)]


def greedy_stabilizer_descent(v, stab_rows, rng, deadline, max_passes=6):
    if not stab_rows:
        return v
    rows = list(stab_rows)
    best_w = v.bit_count()
    for _ in range(max_passes):
        if time.monotonic() > deadline:
            break
        improved = False
        rng.shuffle(rows)
        gains = []
        for s in rows:
            nv = v ^ s
            nw = nv.bit_count()
            if nw < best_w:
                gains.append((best_w - nw, nv, nw))
        if not gains:
            break
        gains.sort(reverse=True, key=lambda x: x[0])
        top = gains[: min(4, len(gains))]
        _, v, best_w = top[rng.randrange(len(top))]
    return v


def random_logical_combo(reps, rng):
    v = 0
    while v == 0:
        for r in reps:
            if rng.getrandbits(1):
                v ^= r
    return v


def mutate(v, reps, stab_rows, rng, deadline):
    if reps and rng.random() < 0.28:
        flips = 1 + rng.randrange(min(4, len(reps)))
        for _ in range(flips):
            v ^= reps[rng.randrange(len(reps))]
    if stab_rows:
        flips = 1 + int(rng.expovariate(0.7))
        flips = min(flips, max(1, len(stab_rows)))
        for _ in range(flips):
            v ^= stab_rows[rng.randrange(len(stab_rows))]
    return greedy_stabilizer_descent(v, stab_rows, rng, deadline, max_passes=4)


def search_side(label, commute_rows, stab_rows, n, rng, deadline):
    reps, stab_basis = independent_logicals(commute_rows, stab_rows, n)
    if not reps:
        return None

    dense_stabs = [r for r in stab_rows if r]
    seeds = []
    for r in reps:
        seeds.append(r)
    for _ in range(min(48, 4 * len(reps) + 16)):
        seeds.append(random_logical_combo(reps, rng))

    pop = []
    seen = set()
    for s in seeds:
        if time.monotonic() > deadline:
            break
        v = greedy_stabilizer_descent(s, dense_stabs, rng, deadline, max_passes=8)
        if verified(v, commute_rows, stab_basis) and v not in seen:
            seen.add(v)
            pop.append(v)

    if not pop:
        for r in reps:
            if verified(r, commute_rows, stab_basis):
                return label, r, r.bit_count()
        return None

    pop.sort(key=lambda x: x.bit_count())
    pop_limit = min(72, max(24, 3 * len(pop)))
    best = pop[0]

    gen = 0
    stagnant = 0
    while time.monotonic() < deadline and gen < 600:
        gen += 1
        old_best = best.bit_count()
        children = []
        elite = pop[: max(2, min(10, len(pop) // 4))]
        for e in elite:
            children.append(e)
        attempts = pop_limit
        while attempts > 0 and time.monotonic() < deadline:
            attempts -= 1
            if len(pop) >= 2 and rng.random() < 0.45:
                a = pop[rng.randrange(len(pop))]
                b = pop[rng.randrange(len(pop))]
                child = a ^ b
                if child == 0 or reduce_with_basis(child, stab_basis) == 0:
                    child ^= reps[rng.randrange(len(reps))]
            else:
                child = pop[rng.randrange(len(pop))]
            child = mutate(child, reps, dense_stabs, rng, deadline)
            if verified(child, commute_rows, stab_basis):
                children.append(child)
        if not children:
            break
        merged = {}
        for v in pop + children:
            merged[v] = v.bit_count()
        pop = sorted(merged, key=lambda x: (merged[x], rng.random()))[:pop_limit]
        if pop[0].bit_count() < best.bit_count():
            best = pop[0]
        stagnant = stagnant + 1 if best.bit_count() >= old_best else 0
        if stagnant >= 80 and len(reps) <= 2:
            break

    return label, best, best.bit_count()


def solve(hx, hz, n, seed):
    rng = random.Random(seed)
    deadline = time.monotonic() + 28.0
    sides = [
        ("x", hz, hx),
        ("z", hx, hz),
    ]
    rng.shuffle(sides)
    results = []
    for label, commute, stab in sides:
        if time.monotonic() > deadline:
            break
        res = search_side(label, commute, stab, n, rng, deadline)
        if res is not None:
            results.append(res)
    if not results:
        return None
    results.sort(key=lambda x: (x[2], 0 if x[0] == "x" else 1))
    return results[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", required=True, type=int)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        if nx not in (0, n) or nz not in (0, n):
            raise ValueError("Hx and Hz have different column counts")
        result = solve(hx, hz, n, args.seed)
        if result is None:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
        else:
            basis, v, w = result
            out = {"status": "completed", "basis": basis, "vector": bits_to_list(v, n), "upper_bound": w}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
