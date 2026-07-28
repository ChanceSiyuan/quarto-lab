#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import sys
import time


def bit_count(x):
    return x.bit_count()


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    rows, n = matrix_from_obj(obj)
    mask = (1 << n) - 1 if n > 0 else 0
    return [r & mask for r in rows if r & mask], n


def matrix_from_obj(obj):
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        return dense_rows(obj, n), n
    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or dense row list")

    if "dense_binary_matrix" in obj:
        return matrix_from_obj(obj["dense_binary_matrix"])
    if "sparse_rows" in obj:
        return matrix_from_obj(obj["sparse_rows"])
    if "matrix" in obj and isinstance(obj["matrix"], (dict, list)):
        return matrix_from_obj(obj["matrix"])

    if "data" in obj:
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        if n <= 0:
            n = max((len(r) for r in obj["data"]), default=0)
        return dense_rows(obj["data"], n), n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows_obj = obj["rows"]
        if n <= 0:
            n = 1 + max((max(r) for r in rows_obj if r), default=-1)
        return sparse_rows(rows_obj, n), n

    raise ValueError("unsupported matrix JSON format")


def dense_rows(data, n):
    out = []
    for row in data:
        v = 0
        for i, val in enumerate(row[:n]):
            if int(val) & 1:
                v ^= 1 << i
        out.append(v)
    return out


def sparse_rows(data, n):
    out = []
    for row in data:
        v = 0
        for col in row:
            c = int(col)
            if 0 <= c < n:
                v ^= 1 << c
        out.append(v)
    return out


class XorBasis:
    def __init__(self, rows=None):
        self.rows = {}
        if rows:
            for row in rows:
                self.add(row)

    def copy(self):
        other = XorBasis()
        other.rows = dict(self.rows)
        return other

    def reduce(self, x):
        while x:
            p = x.bit_length() - 1
            r = self.rows.get(p)
            if r is None:
                return x
            x ^= r
        return 0

    def contains(self, x):
        return self.reduce(x) == 0

    def add(self, x):
        x = self.reduce(x)
        if not x:
            return False
        p = x.bit_length() - 1
        for q, r in list(self.rows.items()):
            if (r >> p) & 1:
                self.rows[q] = r ^ x
        self.rows[p] = x
        return True

    def pivots(self):
        return set(self.rows.keys())


def kernel_basis(check_rows, n):
    rb = XorBasis(check_rows)
    pivots = rb.pivots()
    basis = []
    for c in range(n):
        if c in pivots:
            continue
        v = 1 << c
        for p, row in rb.rows.items():
            if (row >> c) & 1:
                v |= 1 << p
        basis.append(v)
    return basis


def dot_parity(a, b):
    return bit_count(a & b) & 1


def in_kernel(v, checks):
    for row in checks:
        if dot_parity(v, row):
            return False
    return True


def verified(v, checks, stabilizer_basis):
    return v != 0 and in_kernel(v, checks) and not stabilizer_basis.contains(v)


def logical_basis(check_rows, stabilizer_rows, n):
    stab_basis = XorBasis(stabilizer_rows)
    combined = stab_basis.copy()
    logs = []
    for v in kernel_basis(check_rows, n):
        if combined.reduce(v):
            logs.append(v)
            combined.add(v)
    return logs, stab_basis


def greedy_reduce(v, reducers, row_weights, rng, passes=8):
    if not reducers:
        return v
    cur = v
    cur_w = bit_count(cur)
    order = list(range(len(reducers)))
    for p in range(passes):
        if p:
            rng.shuffle(order)
        improved = False
        for i in order:
            r = reducers[i]
            inter = bit_count(cur & r)
            new_w = cur_w + row_weights[i] - 2 * inter
            if new_w < cur_w or (new_w == cur_w and p > 1 and rng.randrange(16) == 0):
                cur ^= r
                cur_w = new_w
                improved = True
        if not improved:
            break
    return cur


def randomized_cancel(v, reducers, rng, rounds):
    cur = v
    if not reducers:
        return cur
    one_bits = [i for i, r in enumerate(reducers) if r & cur]
    for _ in range(rounds):
        if not one_bits:
            break
        r = reducers[rng.choice(one_bits)]
        trial = cur ^ r
        if bit_count(trial) <= bit_count(cur) + rng.randrange(3):
            cur = trial
            one_bits = [i for i, rr in enumerate(reducers) if rr & cur]
    return cur


def vector_from_coeff(coeff, log_vectors):
    v = 0
    c = coeff
    while c:
        lsb = c & -c
        i = lsb.bit_length() - 1
        if i < len(log_vectors):
            v ^= log_vectors[i]
        c ^= lsb
    return v


def coeff_mask_for(k, rng, target=None):
    if k <= 0:
        return 0
    if target is None:
        target = 1 + int(rng.expovariate(0.8))
    target = max(1, min(k, target))
    coeff = 0
    for i in rng.sample(range(k), target):
        coeff |= 1 << i
    return coeff


def evolve_side(name, checks, stabilizers, n, seed, deadline):
    logs, stab_basis = logical_basis(checks, stabilizers, n)
    good_stabs = [r for r in stabilizers if r and in_kernel(r, checks)]
    good_stabs = sorted(set(good_stabs), key=bit_count)
    row_weights = [bit_count(r) for r in good_stabs]
    rng = random.Random(seed)

    if not logs:
        return None

    best = None
    best_w = n + 1

    def consider(coeff, raw):
        nonlocal best, best_w
        if raw == 0:
            return None
        v = randomized_cancel(raw, good_stabs[: min(len(good_stabs), 256)], rng, 3)
        v = greedy_reduce(v, good_stabs, row_weights, rng)
        if not verified(v, checks, stab_basis):
            v = raw
            if good_stabs:
                v = greedy_reduce(v, good_stabs, row_weights, rng, passes=3)
        if verified(v, checks, stab_basis):
            w = bit_count(v)
            if w < best_w:
                best, best_w = v, w
            return (coeff, v, w)
        return None

    population = []
    max_pop = min(96, max(24, 4 * int(math.sqrt(max(1, len(logs))) + 2)))

    ranked_logs = sorted(logs, key=bit_count)
    for i, v in enumerate(ranked_logs[: max_pop]):
        item = consider(1 << logs.index(v), v)
        if item:
            population.append(item)

    k = len(logs)
    init_budget = min(max_pop * 4, 80 + 4 * k)
    for _ in range(init_budget):
        if time.monotonic() > deadline:
            break
        size = 1 if rng.random() < 0.45 else 2 + rng.randrange(max(1, min(k, 8)))
        coeff = coeff_mask_for(k, rng, size)
        item = consider(coeff, vector_from_coeff(coeff, logs))
        if item:
            population.append(item)

    if not population:
        for v in logs:
            if verified(v, checks, stab_basis):
                return v
        return None

    population.sort(key=lambda x: x[2])
    population = population[:max_pop]

    # Population-based coset evolution: individuals carry logical-coordinate
    # masks; mutation flips logical directions, crossover xors two cosets, and
    # every offspring is locally minimized inside its stabilizer coset.
    stagnant = 0
    max_steps = 450 + 45 * min(k, 80) + 8 * min(n, 500)
    temp = 2.5
    for step in range(max_steps):
        if time.monotonic() > deadline:
            break
        if not population:
            break

        if rng.random() < 0.55 and len(population) >= 2:
            a = tournament(population, rng)
            b = tournament(population, rng)
            coeff = a[0] ^ b[0]
            if coeff == 0:
                coeff = a[0]
            if rng.random() < 0.7:
                flips = 1 + rng.randrange(1 + min(4, k - 1))
                for _ in range(flips):
                    coeff ^= 1 << rng.randrange(k)
            if coeff == 0:
                coeff = 1 << rng.randrange(k)
            raw = vector_from_coeff(coeff, logs)
        else:
            parent = tournament(population, rng)
            coeff = parent[0]
            raw = parent[1]
            flips = 1 + int(rng.expovariate(0.9))
            for _ in range(min(flips, max(1, k))):
                j = biased_log_index(logs, rng)
                coeff ^= 1 << j
                raw ^= logs[j]
            if coeff == 0:
                j = rng.randrange(k)
                coeff = 1 << j
                raw = logs[j]

        if good_stabs and rng.random() < 0.35:
            for _ in range(1 + rng.randrange(3)):
                raw ^= good_stabs[rng.randrange(min(len(good_stabs), max(1, len(good_stabs))))]

        item = consider(coeff, raw)
        if not item:
            continue

        worst = population[-1][2]
        accept = item[2] <= worst or rng.random() < math.exp(-(item[2] - worst) / max(0.25, temp))
        if accept:
            population.append(item)
            population.sort(key=lambda x: x[2])
            seen = set()
            uniq = []
            for entry in population:
                key = (entry[0], entry[1])
                if key not in seen:
                    seen.add(key)
                    uniq.append(entry)
            population = uniq[:max_pop]
            if item[2] <= best_w:
                stagnant = 0
            else:
                stagnant += 1
        else:
            stagnant += 1

        temp *= 0.997
        if stagnant > 120 and k > 1:
            stagnant = 0
            keep = population[: max(4, max_pop // 4)]
            population = keep
            for _ in range(max_pop - len(keep)):
                coeff = coeff_mask_for(k, rng)
                item = consider(coeff, vector_from_coeff(coeff, logs))
                if item:
                    population.append(item)
            population.sort(key=lambda x: x[2])
            population = population[:max_pop]

    if best is not None and verified(best, checks, stab_basis):
        return best

    for v in ranked_logs:
        if verified(v, checks, stab_basis):
            return v
    return None


def tournament(population, rng):
    sample = rng.sample(population, min(len(population), 4))
    sample.sort(key=lambda x: x[2])
    return sample[0]


def biased_log_index(logs, rng):
    k = len(logs)
    if k == 1:
        return 0
    # Prefer lighter logical basis directions while retaining full support.
    a = rng.randrange(k)
    b = rng.randrange(k)
    return a if bit_count(logs[a]) <= bit_count(logs[b]) else b


def int_to_vector(v, n):
    return [(v >> i) & 1 for i in range(n)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    try:
        hx, nx = parse_matrix(args.hx)
        hz, nz = parse_matrix(args.hz)
        n = max(nx, nz)
        if nx != n:
            hx = [r & ((1 << n) - 1) for r in hx]
        if nz != n:
            hz = [r & ((1 << n) - 1) for r in hz]

        os.makedirs(args.output_dir, exist_ok=True)
        deadline = time.monotonic() + 25.0

        x_wit = evolve_side("x", hz, hx, n, (args.seed << 1) ^ 0x9E3779B1, deadline)
        z_wit = evolve_side("z", hx, hz, n, (args.seed << 1) ^ 0x85EBCA77, deadline)

        choices = []
        if x_wit is not None:
            choices.append(("x", x_wit, bit_count(x_wit)))
        if z_wit is not None:
            choices.append(("z", z_wit, bit_count(z_wit)))
        if choices:
            basis, vec, wt = min(choices, key=lambda x: (x[2], x[0]))
            result = {
                "status": "completed",
                "basis": basis,
                "vector": int_to_vector(vec, n),
                "upper_bound": wt,
            }
        else:
            result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
