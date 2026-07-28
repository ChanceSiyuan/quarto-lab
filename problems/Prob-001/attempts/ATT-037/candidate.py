#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def _matrix_payload(obj):
    if isinstance(obj, dict):
        if "dense_binary_matrix" in obj:
            return _matrix_payload(obj["dense_binary_matrix"])
        if "sparse_rows" in obj:
            return _matrix_payload(obj["sparse_rows"])
        if "matrix" in obj and isinstance(obj["matrix"], dict):
            return _matrix_payload(obj["matrix"])
    return obj


def load_matrix(text):
    src = text
    if text.startswith("@"):
        with open(text[1:], "r", encoding="utf-8") as f:
            src = f.read()
    elif os.path.exists(text):
        with open(text, "r", encoding="utf-8") as f:
            src = f.read()
    obj = _matrix_payload(json.loads(src))

    if isinstance(obj, dict) and "data" in obj:
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        data = obj["data"]
        if not data:
            return [], n
        if all(isinstance(r, list) for r in data):
            rows = data
        else:
            if n <= 0:
                raise ValueError("dense_binary_matrix requires n_cols")
            rows = [data[i:i + n] for i in range(0, len(data), n)]
        return [row_to_int(row, n) for row in rows], n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        out = []
        for row in obj["rows"]:
            v = 0
            for c in row:
                ci = int(c)
                if 0 <= ci < n:
                    v ^= 1 << ci
            out.append(v)
        return out, n

    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        return [row_to_int(row, n) for row in obj], n

    raise ValueError("unsupported matrix JSON format")


def row_to_int(row, n):
    v = 0
    for i, bit in enumerate(row[:n]):
        if int(bit) & 1:
            v |= 1 << i
    return v


def rref(rows, n):
    rows = [r for r in rows if r]
    rank = 0
    pivots = []
    for col in range(n):
        bit = 1 << col
        found = None
        for i in range(rank, len(rows)):
            if rows[i] & bit:
                found = i
                break
        if found is None:
            continue
        rows[rank], rows[found] = rows[found], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & bit):
                rows[i] ^= rows[rank]
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return rows[:rank], pivots


def reduce_by(v, basis, pivots):
    for row, pivot in zip(basis, pivots):
        if v & (1 << pivot):
            v ^= row
    return v


def in_span(v, basis, pivots):
    return reduce_by(v, basis, pivots) == 0


def nullspace_basis(rows, n):
    rb, pivots = rref(rows, n)
    pivot_set = set(pivots)
    basis = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, pivot in zip(rb, pivots):
            if row & (1 << free):
                v |= 1 << pivot
        basis.append(v)
    return basis


def logical_generators(check_rows, stab_rows, n):
    ns = nullspace_basis(check_rows, n)
    stab_basis, stab_pivots = rref(stab_rows, n)
    span_rows = list(stab_basis)
    span_pivots = list(stab_pivots)
    gens = []
    for v in sorted(ns, key=lambda x: (x.bit_count(), x)):
        if not in_span(v, span_rows, span_pivots):
            gens.append(v)
            span_rows, span_pivots = rref(span_rows + [v], n)
    return gens, stab_basis, stab_pivots


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def checked_witness(v, check_rows, stab_basis, stab_pivots):
    if not v:
        return False
    for row in check_rows:
        if (v & row).bit_count() & 1:
            return False
    return not in_span(v, stab_basis, stab_pivots)


def random_combo(items, rng, force_one=False):
    v = 0
    used = False
    for item in items:
        if rng.getrandbits(1):
            v ^= item
            used = True
    if force_one and items and not used:
        v ^= rng.choice(items)
    return v


def greedy_stabilizer_descent(v, stab_rows, rng, rounds):
    if not stab_rows:
        return v
    cur = v
    order = list(stab_rows)
    for _ in range(rounds):
        improved = False
        rng.shuffle(order)
        cur_w = cur.bit_count()
        for s in order:
            nv = cur ^ s
            nw = nv.bit_count()
            if nw < cur_w or (nw == cur_w and rng.random() < 0.02):
                cur, cur_w = nv, nw
                improved = True
        if not improved:
            break
    return cur


def evolve_basis(check_rows, stab_rows, n, seed, seconds=1.25):
    gens, stab_basis, stab_pivots = logical_generators(check_rows, stab_rows, n)
    if not gens:
        return None, stab_basis, stab_pivots

    rng = random.Random(seed)
    deadline = time.monotonic() + seconds
    stab_pool = sorted(set(stab_rows + stab_basis), key=lambda x: (x.bit_count(), x))
    stab_pool = [s for s in stab_pool if s]
    if len(stab_pool) > 384:
        light = stab_pool[:192]
        sampled = rng.sample(stab_pool[192:], 192)
        stab_pool = light + sampled

    # Fallback is a certified quotient-basis logical, lightly minimized inside
    # its stabilizer coset without changing its logical class.
    best = None
    for g in gens:
        v = greedy_stabilizer_descent(g, stab_pool, rng, 3)
        if checked_witness(v, check_rows, stab_basis, stab_pivots):
            if best is None or v.bit_count() < best.bit_count():
                best = v
    if best is None:
        best = gens[0]

    pop_size = min(96, max(24, 5 * len(gens) + 16))
    population = []
    for g in gens:
        population.append(greedy_stabilizer_descent(g, stab_pool, rng, 4))
    while len(population) < pop_size:
        logical = random_combo(gens, rng, force_one=True)
        noise = random_combo(stab_pool, rng, force_one=False)
        v = greedy_stabilizer_descent(logical ^ noise, stab_pool, rng, 3)
        population.append(v)

    generation = 0
    while time.monotonic() < deadline:
        scored = []
        for v in population:
            if checked_witness(v, check_rows, stab_basis, stab_pivots):
                scored.append((v.bit_count(), rng.random(), v))
                if v.bit_count() < best.bit_count():
                    best = v
        if not scored:
            population = [rng.choice(gens) for _ in range(pop_size)]
            continue
        scored.sort()
        elite_count = max(4, pop_size // 5)
        elites = [v for _, _, v in scored[:elite_count]]
        next_pop = elites[:]

        temp = max(0.05, 0.6 * (0.995 ** generation))
        while len(next_pop) < pop_size:
            a = rng.choice(elites)
            b = rng.choice(scored[:max(elite_count, len(scored) // 2)])[2]
            # Crossover in vector space, followed by a logical-coset mutation.
            child = a ^ b
            if not child or in_span(child, stab_basis, stab_pivots):
                child ^= rng.choice(gens)
            if rng.random() < 0.70:
                child ^= rng.choice(gens)
            flips = 1 + (rng.randrange(3) if rng.random() < temp else 0)
            for _ in range(flips):
                if stab_pool:
                    child ^= rng.choice(stab_pool)
            child = greedy_stabilizer_descent(child, stab_pool, rng, 2)
            if child and not in_span(child, stab_basis, stab_pivots):
                next_pop.append(child)
        population = next_pop
        generation += 1

    if checked_witness(best, check_rows, stab_basis, stab_pivots):
        return best, stab_basis, stab_pivots
    for g in gens:
        if checked_witness(g, check_rows, stab_basis, stab_pivots):
            return g, stab_basis, stab_pivots
    return None, stab_basis, stab_pivots


def solve(hx, hz, seed):
    hx_rows, nx = hx
    hz_rows, nz = hz
    n = max(nx, nz)
    hx_rows = [r & ((1 << n) - 1) for r in hx_rows]
    hz_rows = [r & ((1 << n) - 1) for r in hz_rows]

    # X logicals commute with Z checks and are nontrivial modulo X stabilizers;
    # Z logicals use the dual condition.
    candidates = []
    for offset, basis_name, check_rows, stab_rows in (
        (0, "x", hz_rows, hx_rows),
        (1, "z", hx_rows, hz_rows),
    ):
        seconds = 0.75 if n <= 96 else (1.25 if n <= 512 else 2.0)
        v, stab_basis, stab_pivots = evolve_basis(
            check_rows,
            stab_rows,
            n,
            seed ^ (0x9E3779B97F4A7C15 * (offset + 1)),
            seconds=seconds,
        )
        if v is not None and checked_witness(v, check_rows, stab_basis, stab_pivots):
            candidates.append((v.bit_count(), basis_name, v))

    if not candidates:
        return {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    candidates.sort(key=lambda item: (item[0], item[1]))
    weight, basis_name, vec = candidates[0]
    return {
        "status": "completed",
        "basis": basis_name,
        "vector": vector_to_list(vec, n),
        "upper_bound": int(weight),
    }


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    try:
        result = solve(load_matrix(args.hx), load_matrix(args.hz), args.seed)
    except Exception:
        result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
