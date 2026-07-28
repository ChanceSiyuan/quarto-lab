#!/usr/bin/env python3
import argparse
import json
import os
import random


def mask_from_indices(indices):
    v = 0
    for i in indices:
        j = int(i)
        if j >= 0:
            v ^= 1 << j
    return v


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = [mask_from_indices(i for i, b in enumerate(r) if int(b) & 1) for r in obj]
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or row list")

    if isinstance(obj.get("dense_binary_matrix"), dict):
        obj = obj["dense_binary_matrix"]
    if isinstance(obj.get("sparse_rows"), dict):
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", obj.get("num_cols", 0)) or 0)
        if data and all(isinstance(r, list) for r in data):
            if n <= 0:
                n = max(len(r) for r in data)
            rows = [mask_from_indices(i for i, b in enumerate(r[:n]) if int(b) & 1) for r in data]
            return rows, n
        if data and all(isinstance(x, int) for x in data) and n > 0:
            rows = []
            for start in range(0, len(data), n):
                chunk = data[start:start + n]
                if len(chunk) == n:
                    rows.append(mask_from_indices(i for i, b in enumerate(chunk) if int(b) & 1))
            return rows, n
        return [], n

    if "rows" in obj:
        sparse = obj.get("rows") or []
        n = int(obj.get("num_cols", obj.get("n_cols", 0)) or 0)
        if n <= 0:
            n = 1 + max((int(c) for r in sparse for c in r), default=-1)
        return [mask_from_indices(r) for r in sparse], n

    raise ValueError("unrecognized matrix JSON format")


def trim_rows(rows, n):
    mask = (1 << n) - 1 if n > 0 else 0
    return [r & mask for r in rows if (r & mask) != 0]


def rref_rows(rows, n):
    rows = trim_rows(rows, n)
    out = []
    pivots = []
    rank = 0
    for col in range(n):
        pivot = None
        for i in range(rank, len(rows)):
            if (rows[i] >> col) & 1:
                pivot = i
                break
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        p = rows[rank]
        for i in range(len(rows)):
            if i != rank and ((rows[i] >> col) & 1):
                rows[i] ^= p
        out.append(rows[rank])
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return out, pivots


def nullspace_basis(rows, n):
    rref, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    basis = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, piv in zip(rref, pivots):
            if (row >> free) & 1:
                v |= 1 << piv
        basis.append(v)
    return basis


def reduce_by_basis(v, basis):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            break
        x ^= b
    return x


def basis_insert(basis, v):
    x = reduce_by_basis(v, basis)
    if x == 0:
        return False
    p = x.bit_length() - 1
    for q, b in list(basis.items()):
        if (b >> p) & 1:
            basis[q] = b ^ x
    basis[p] = x
    return True


def make_basis(rows):
    basis = {}
    for r in rows:
        basis_insert(basis, r)
    return basis


def in_span(v, basis):
    return reduce_by_basis(v, basis) == 0


def logical_generators(kernel_rows, stabilizer_rows):
    span = make_basis(stabilizer_rows)
    gens = []
    for v in kernel_rows:
        if basis_insert(span, v):
            gens.append(v)
    return gens


def syndrome_zero(v, checks):
    for r in checks:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def verify(v, checks, stabilizers, stab_basis=None):
    if v == 0 or not syndrome_zero(v, checks):
        return False
    if stab_basis is None:
        stab_basis = make_basis(stabilizers)
    return not in_span(v, stab_basis)


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def greedy_stabilizer_descent(v, moves, rng, rounds=3):
    cur = v
    cur_w = cur.bit_count()
    if not moves:
        return cur
    order = list(moves)
    for _ in range(rounds):
        rng.shuffle(order)
        changed = False
        for m in order:
            nw = (cur ^ m).bit_count()
            if nw < cur_w:
                cur ^= m
                cur_w = nw
                changed = True
        if not changed:
            break
    return cur


def random_combo(items, rng, p=0.5):
    v = 0
    for x in items:
        if rng.random() < p:
            v ^= x
    return v


def weighted_random_move(items, weights, rng):
    if not items:
        return 0
    total = sum(weights)
    if total <= 0:
        return rng.choice(items)
    r = rng.random() * total
    acc = 0.0
    for x, w in zip(items, weights):
        acc += w
        if acc >= r:
            return x
    return items[-1]


def evolve_orientation(check_rows, stab_rows, n, rng):
    kernel = nullspace_basis(check_rows, n)
    gens = logical_generators(kernel, stab_rows)
    if not gens:
        return None

    stab_moves = trim_rows(stab_rows, n)
    if len(stab_moves) > 384:
        ordered = sorted(stab_moves, key=lambda x: x.bit_count())
        low = ordered[:256]
        rest = ordered[256:]
        stab_moves = low + rng.sample(rest, min(128, len(rest)))
    stab_basis = make_basis(stab_rows)
    all_moves = stab_moves + gens
    move_weights = [1.0 / (1 + m.bit_count()) for m in all_moves]
    stab_weights = [1.0 / (1 + m.bit_count()) for m in stab_moves]
    pop_size = min(64, max(20, 3 * len(gens) + 10))
    population = []

    for g in gens:
        population.append(greedy_stabilizer_descent(g, stab_moves, rng, rounds=4))

    attempts = 0
    while len(population) < pop_size and attempts < pop_size * 8:
        attempts += 1
        p = min(0.65, max(0.15, 2.0 / max(1, len(gens))))
        v = random_combo(gens, rng, p=p)
        if v == 0:
            v = rng.choice(gens)
        if stab_moves:
            for _ in range(rng.randrange(0, min(10, len(stab_moves)) + 1)):
                v ^= rng.choice(stab_moves)
        v = greedy_stabilizer_descent(v, stab_moves, rng, rounds=2)
        if not in_span(v, stab_basis):
            population.append(v)

    if not population:
        population = [gens[0]]

    best = min(population, key=lambda x: x.bit_count())
    iterations = 120 + 10 * min(n, 600) + 30 * min(max(1, len(gens)), 40)
    elite_count = min(16, max(4, pop_size // 5))
    tabu = {}

    for t in range(iterations):
        population.sort(key=lambda x: x.bit_count())
        if population[0].bit_count() < best.bit_count():
            best = population[0]

        elites = population[:elite_count]
        children = elites[:]
        temperature = 1.0 - (t / max(1, iterations - 1))

        while len(children) < pop_size:
            if len(elites) >= 2 and rng.random() < 0.35:
                a, b = rng.sample(elites, 2)
                v = a ^ b
                if v == 0 or in_span(v, stab_basis):
                    v ^= rng.choice(gens)
            else:
                v = rng.choice(elites)

            flips = 1 + rng.randrange(1 + int(5 * temperature) + max(1, len(gens)).bit_length())
            for _ in range(flips):
                if rng.random() < 0.55 and stab_moves:
                    v ^= weighted_random_move(stab_moves, stab_weights, rng)
                else:
                    v ^= rng.choice(gens)
                if all_moves and rng.random() < 0.15 * temperature:
                    v ^= weighted_random_move(all_moves, move_weights, rng)

            if stab_moves and rng.random() < 0.85:
                rounds = 1 + int(rng.random() < 0.35)
                v = greedy_stabilizer_descent(v, stab_moves, rng, rounds=rounds)

            if v != 0 and not in_span(v, stab_basis):
                seen = tabu.get(v, 0)
                tabu[v] = seen + 1
                if seen < 3 or rng.random() < 0.05:
                    children.append(v)

        population = children

    fallback = greedy_stabilizer_descent(gens[0], stab_moves, rng, rounds=6)
    if fallback.bit_count() < best.bit_count():
        best = fallback
    return best


def choose_witness(hx_rows, hz_rows, n, seed):
    rng = random.Random(seed)
    candidates = []

    x_w = evolve_orientation(hz_rows, hx_rows, n, rng)
    if x_w is not None and verify(x_w, hz_rows, hx_rows):
        candidates.append(("x", x_w))

    z_w = evolve_orientation(hx_rows, hz_rows, n, rng)
    if z_w is not None and verify(z_w, hx_rows, hz_rows):
        candidates.append(("z", z_w))

    if not candidates:
        for basis, checks, stabs in (("x", hz_rows, hx_rows), ("z", hx_rows, hz_rows)):
            gens = logical_generators(nullspace_basis(checks, n), stabs)
            for g in gens:
                if verify(g, checks, stabs):
                    candidates.append((basis, g))
                    break

    if not candidates:
        return None, None
    return min(candidates, key=lambda item: item[1].bit_count())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    try:
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
        hx, nx = parse_matrix(args.hx)
        hz, nz = parse_matrix(args.hz)
        n = max(nx, nz)
        hx = trim_rows(hx, n)
        hz = trim_rows(hz, n)

        basis, witness = choose_witness(hx, hz, n, args.seed)
        if witness is None:
            result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
        else:
            result = {
                "status": "completed",
                "basis": basis,
                "vector": vector_to_list(witness, n),
                "upper_bound": int(witness.bit_count()),
            }
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
