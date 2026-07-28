#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def load_matrix_arg(value):
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            obj = json.load(f)
    else:
        obj = json.loads(value)
    return parse_matrix(obj)


def parse_matrix(obj):
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", 0))
        rows = []
        for row in data:
            x = 0
            for i, bit in enumerate(row):
                if bit:
                    x |= 1 << i
            rows.append(x)
        if n == 0 and data:
            n = len(data[0])
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for cols in obj.get("rows", []):
            x = 0
            for c in cols:
                c = int(c)
                if c >= 0:
                    x |= 1 << c
            rows.append(x)
        return rows, n

    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        rows = []
        for row in obj:
            x = 0
            for i, bit in enumerate(row):
                if bit:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def rref_rows(rows):
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
    for p in sorted(basis):
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= basis[p]
    return basis


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        row = basis.get(p)
        if row is None:
            break
        y ^= row
    return y


def independent_append(rows, basis, x):
    r = reduce_by_basis(x, basis)
    if r == 0:
        return False
    p = r.bit_length() - 1
    basis[p] = r
    for q in list(basis):
        if q != p and ((basis[q] >> p) & 1):
            basis[q] ^= r
    rows.append(x)
    return True


def nullspace_basis(rows, n):
    rr = rref_rows(rows)
    pivots = set(rr)
    free_cols = [c for c in range(n) if c not in pivots]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in rr.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def in_kernel(v, checks):
    for row in checks:
        if (row & v).bit_count() & 1:
            return False
    return True


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def verified(v, checks, stab_basis):
    return v != 0 and in_kernel(v, checks) and reduce_by_basis(v, stab_basis) != 0


def logical_basis(kernel_rows, stab_rows):
    stab_basis = rref_rows(stab_rows)
    span = dict(stab_basis)
    logs = []
    for v in sorted(kernel_rows, key=lambda x: (x.bit_count(), x)):
        independent_append(logs, span, v)
    return logs, stab_basis


def greedy_stabilizer_descent(v, stabilizers, rng, passes=5):
    cur = v
    cur_w = cur.bit_count()
    rows = list(stabilizers)
    for _ in range(passes):
        rng.shuffle(rows)
        improved = False
        for s in rows:
            nxt = cur ^ s
            w = nxt.bit_count()
            if w < cur_w or (w == cur_w and rng.random() < 0.015):
                cur, cur_w = nxt, w
                improved = True
        if not improved:
            break
    return cur


def random_logical_combo(logs, rng):
    if not logs:
        return 0, 0
    coeff = 0
    v = 0
    # Heavy-tailed subset sizes: often sparse, sometimes broad.
    if rng.random() < 0.70:
        t = 1 + int(rng.expovariate(0.8)) % min(len(logs), 12)
        idxs = rng.sample(range(len(logs)), min(t, len(logs)))
    else:
        idxs = [i for i in range(len(logs)) if rng.random() < 0.5]
        if not idxs:
            idxs = [rng.randrange(len(logs))]
    for i in idxs:
        coeff ^= 1 << i
        v ^= logs[i]
    return coeff, v


def materialize(coeff, logs):
    v = 0
    i = 0
    c = coeff
    while c:
        if c & 1:
            v ^= logs[i]
        c >>= 1
        i += 1
    return v


def evolve_witness(checks, stabilizers, n, seed, millis):
    rng = random.Random(seed)
    kernel = nullspace_basis(checks, n)
    logs, stab_basis = logical_basis(kernel, stabilizers)
    if not logs:
        return None, None

    stab_ind = list(rref_rows(stabilizers).values())
    pop_size = max(24, min(96, 10 + 3 * len(logs)))
    population = []

    def polish(coeff):
        if coeff == 0:
            coeff = 1 << rng.randrange(len(logs))
        v = materialize(coeff, logs)
        # Random coset representative before descent encourages distinct basins.
        if stab_ind:
            flips = 1 + int(rng.expovariate(0.55)) % min(len(stab_ind), 20)
            for j in rng.sample(range(len(stab_ind)), min(flips, len(stab_ind))):
                if rng.random() < 0.75:
                    v ^= stab_ind[j]
        v = greedy_stabilizer_descent(v, stab_ind, rng, passes=6)
        return coeff, v, v.bit_count()

    # Basis-derived fallback seeds guarantee a verified positive-k witness.
    for i in range(len(logs)):
        population.append(polish(1 << i))
        if len(population) >= pop_size:
            break
    while len(population) < pop_size:
        coeff, _ = random_logical_combo(logs, rng)
        population.append(polish(coeff))

    best = min(population, key=lambda item: item[2])
    if verified(best[1], checks, stab_basis) and best[2] <= 1:
        return best[1], best[2]
    deadline = time.monotonic() + millis / 1000.0
    rounds = 0
    while time.monotonic() < deadline:
        population.sort(key=lambda item: item[2])
        if population[0][2] < best[2]:
            best = population[0]
            if verified(best[1], checks, stab_basis) and best[2] <= 1:
                return best[1], best[2]
        elites = population[: max(4, pop_size // 4)]
        children = elites[:]

        while len(children) < pop_size:
            a = rng.choice(elites)
            b = rng.choice(population[: max(8, pop_size // 2)])
            if rng.random() < 0.62:
                mask = 0
                for i in range(len(logs)):
                    if rng.random() < 0.5:
                        mask |= 1 << i
                coeff = (a[0] & mask) ^ (b[0] & ~mask)
            else:
                coeff = a[0] ^ b[0]

            # Mutate in quotient coordinates. Nonzero coeff means a logical coset.
            mut_p = min(0.45, 1.0 / max(2, len(logs)) + 0.03)
            for i in range(len(logs)):
                if rng.random() < mut_p:
                    coeff ^= 1 << i
            if coeff == 0:
                coeff = 1 << rng.randrange(len(logs))
            children.append(polish(coeff))

        population = children
        rounds += 1
        if rounds % 10 == 0 and stab_ind:
            # Inject same-coset shakeups of the current champion.
            coeff = best[0]
            for _ in range(min(8, pop_size // 5)):
                population[-1 - _] = polish(coeff)

    final = min(population + [best], key=lambda item: item[2])
    if verified(final[1], checks, stab_basis):
        return final[1], final[2]

    # Defensive fallback: the quotient basis was constructed outside rowspace.
    for v in logs:
        if verified(v, checks, stab_basis):
            return v, v.bit_count()
    return None, None


def solve(hx, hz, seed):
    hx_rows, nx = hx
    hz_rows, nz = hz
    n = max(nx, nz)
    hx_rows = [r & ((1 << n) - 1) for r in hx_rows]
    hz_rows = [r & ((1 << n) - 1) for r in hz_rows]

    # Split time across bases. These are upper-bound witness searches only.
    budgets = [("x", hz_rows, hx_rows, seed ^ 0x58, 1350),
               ("z", hx_rows, hz_rows, seed ^ 0x5A, 1350)]
    results = []
    for basis, checks, stabs, s, ms in budgets:
        v, w = evolve_witness(checks, stabs, n, s, ms)
        if v is not None:
            results.append((w, basis, v))
            if w <= 1:
                break

    if not results:
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    w, basis, v = min(results, key=lambda item: (item[0], item[1]))
    return {
        "status": "completed",
        "basis": basis,
        "vector": vector_to_list(v, n),
        "upper_bound": int(w),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        result = solve(load_matrix_arg(args.hx), load_matrix_arg(args.hz), int(args.seed))
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
