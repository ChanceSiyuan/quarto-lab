#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def fail():
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            x = 0
            for i, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or row list")

    if "dense_binary_matrix" in obj and isinstance(obj["dense_binary_matrix"], dict):
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj and isinstance(obj["sparse_rows"], dict):
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for i, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if "rows" in obj:
        sparse = obj.get("rows") or []
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = 1 + max((int(c) for r in sparse for c in r), default=-1)
        rows = []
        for r in sparse:
            x = 0
            for c in r:
                ci = int(c)
                if ci >= 0:
                    x ^= 1 << ci
            rows.append(x)
        return rows, n

    raise ValueError("unrecognized matrix format")


def row_echelon(rows, n):
    basis = {}
    for row in rows:
        x = row & ((1 << n) - 1 if n else 0)
        while x:
            p = (x & -x).bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = (y & -y).bit_length() - 1
        b = basis.get(p)
        if b is None:
            return y
        y ^= b
    return 0


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def rref_rows(rows, n):
    rows = [r & ((1 << n) - 1 if n else 0) for r in rows if r]
    out = []
    pivot_cols = []
    pos = 0
    for col in range(n):
        pivot = None
        for j in range(pos, len(rows)):
            if (rows[j] >> col) & 1:
                pivot = j
                break
        if pivot is None:
            continue
        rows[pos], rows[pivot] = rows[pivot], rows[pos]
        for j in range(len(rows)):
            if j != pos and ((rows[j] >> col) & 1):
                rows[j] ^= rows[pos]
        out.append(rows[pos])
        pivot_cols.append(col)
        pos += 1
        if pos == len(rows):
            break
    return out, pivot_cols


def kernel_basis(rows, n):
    rref, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    basis = []
    for f in free_cols:
        x = 1 << f
        for row, p in zip(rref, pivots):
            if (row >> f) & 1:
                x |= 1 << p
        basis.append(x)
    return basis


def quotient_generators(kernel, stabilizers, n):
    span = row_echelon(stabilizers, n)
    gens = []
    for v in sorted(kernel, key=lambda z: z.bit_count()):
        if v and not in_span(v, span):
            gens.append(v)
            span = row_echelon(list(span.values()) + [v], n)
    return gens


def xor_mask(gens, mask):
    x = 0
    m = mask
    while m:
        lsb = m & -m
        i = lsb.bit_length() - 1
        x ^= gens[i]
        m ^= lsb
    return x


def random_mask(rng, k):
    if k <= 0:
        return 0
    m = rng.getrandbits(k)
    if m == 0:
        m = 1 << rng.randrange(k)
    return m


def shrink_by_stabilizers(v, stab_rows, rng, passes=3, sample_cap=256):
    if not stab_rows:
        return v
    x = v
    rows = stab_rows
    for _ in range(passes):
        if len(rows) <= sample_cap:
            order = list(rows)
            rng.shuffle(order)
        else:
            order = [rows[rng.randrange(len(rows))] for _ in range(sample_cap)]
        changed = False
        wx = x.bit_count()
        for r in order:
            y = x ^ r
            wy = y.bit_count()
            if wy < wx or (wy == wx and rng.randrange(16) == 0):
                x, wx = y, wy
                changed = True
        if not changed:
            break
    return x


def certify(v, check_rows, stab_basis):
    if v == 0:
        return False
    for r in check_rows:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return not in_span(v, stab_basis)


def evolve_side(name, check_rows, stab_rows, n, seed, deadline):
    kern = kernel_basis(check_rows, n)
    gens = quotient_generators(kern, stab_rows, n)
    if not gens:
        return None

    rng = random.Random((seed ^ (0x9E3779B97F4A7C15 if name == "x" else 0xD1B54A32D192ED03)) & ((1 << 64) - 1))
    stab_basis = row_echelon(stab_rows, n)
    k = len(gens)
    pop_size = min(96, max(24, 4 * min(k, 16)))

    population = []
    seed_masks = [1 << i for i in range(min(k, pop_size // 2))]
    while len(seed_masks) < pop_size:
        seed_masks.append(random_mask(rng, k))

    best = None
    seen = set()
    for mask in seed_masks:
        v = shrink_by_stabilizers(xor_mask(gens, mask), stab_rows, rng, passes=5)
        if certify(v, check_rows, stab_basis):
            item = (v.bit_count(), mask, v)
            population.append(item)
            if best is None or item[0] < best[0]:
                best = item
        seen.add(mask)

    if best is None:
        return None

    rounds = 0
    max_rounds = 250 + 20 * min(n, 200) + 30 * min(k, 64)
    while rounds < max_rounds and time.monotonic() < deadline:
        rounds += 1
        population.sort(key=lambda t: t[0])
        population = population[:pop_size]

        elite = population[: max(4, pop_size // 5)]
        children = []
        attempts = pop_size
        while attempts > 0 and time.monotonic() < deadline:
            attempts -= 1
            if len(elite) >= 2 and rng.random() < 0.70:
                a = rng.choice(elite)[1]
                b = rng.choice(population)[1]
                mask = a ^ b
                if mask == 0:
                    mask = a
            else:
                mask = rng.choice(population)[1]

            flips = 1
            r = rng.random()
            if r < 0.05:
                flips = 3
            elif r < 0.20:
                flips = 2
            for _ in range(flips):
                mask ^= 1 << rng.randrange(k)
            if mask == 0:
                mask = 1 << rng.randrange(k)

            if mask in seen and rng.random() < 0.35:
                mask ^= random_mask(rng, k)
                if mask == 0:
                    mask = 1 << rng.randrange(k)
            seen.add(mask)

            v = xor_mask(gens, mask)
            if rng.random() < 0.25 and stab_rows:
                for _ in range(1 + rng.randrange(3)):
                    v ^= stab_rows[rng.randrange(len(stab_rows))]
            v = shrink_by_stabilizers(v, stab_rows, rng, passes=4)
            if certify(v, check_rows, stab_basis):
                item = (v.bit_count(), mask, v)
                children.append(item)
                if item[0] < best[0]:
                    best = item

        population.extend(children)
        if len(population) > 3 * pop_size:
            population.sort(key=lambda t: (t[0], rng.random()))
            population = population[:pop_size]

    return {"basis": name, "vector_int": best[2], "upper_bound": best[0]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1 if n else 0) for r in hx]
        hz = [r & ((1 << n) - 1 if n else 0) for r in hz]
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        overall_deadline = time.monotonic() + 12.0
        rx = evolve_side("x", hz, hx, n, int(args.seed), min(overall_deadline, time.monotonic() + 5.5))
        rz = evolve_side("z", hx, hz, n, int(args.seed) + 0xA5A5A5A5, min(overall_deadline, time.monotonic() + 5.5))
        choices = [r for r in (rx, rz) if r is not None]
        if not choices:
            fail()
            return
        best = min(choices, key=lambda r: r["upper_bound"])
        v = best["vector_int"]
        out = {
            "status": "completed",
            "basis": best["basis"],
            "vector": [int((v >> i) & 1) for i in range(n)],
            "upper_bound": int(best["upper_bound"]),
        }
        print(json.dumps(out, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
