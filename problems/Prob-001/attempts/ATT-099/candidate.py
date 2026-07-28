#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from collections import deque


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            mask = 0
            for i, bit in enumerate(r):
                if bit & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        rows = []
        for r in obj["data"]:
            mask = 0
            for i, bit in enumerate(r[:n]):
                if int(bit) & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            mask = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    mask ^= 1 << c
            rows.append(mask)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def popcount(x):
    return x.bit_count()


def iter_bits(x):
    while x:
        b = x & -x
        yield b.bit_length() - 1
        x ^= b


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                for q, y in list(basis.items()):
                    if (y >> p) & 1:
                        basis[q] = y ^ x
                basis[p] = x
                break
            x ^= b
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
    rb = rref_basis(rows)
    pivots = set(rb)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v |= 1 << p
        if v:
            out.append(v)
    return out


def syndrome_zero(v, checks):
    for r in checks:
        if popcount(v & r) & 1:
            return False
    return True


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def restricted_null_vectors(checks, col_checks, cols, n, rng, max_basis=18, tries=42):
    if not cols:
        return []
    pos = {c: i for i, c in enumerate(cols)}
    touched = set()
    for c in cols:
        touched.update(col_checks[c])

    restricted = []
    for ri in touched:
        row = checks[ri]
        m = 0
        x = row
        while x:
            b = x & -x
            c = b.bit_length() - 1
            j = pos.get(c)
            if j is not None:
                m |= 1 << j
            x ^= b
        if m:
            restricted.append(m)

    ns = nullspace_basis(restricted, len(cols))
    if not ns:
        return []
    ns.sort(key=popcount)
    pool = ns[:max_basis]

    local = []
    local.extend(pool[: min(len(pool), 6)])
    for _ in range(tries):
        k = 1 + int(rng.expovariate(0.55)) if len(pool) > 1 else 1
        k = min(k, len(pool))
        v = 0
        for b in rng.sample(pool, k):
            v ^= b
        if v:
            local.append(v)

    out = []
    for lv in local:
        gv = 0
        for j in iter_bits(lv):
            if j < len(cols):
                gv |= 1 << cols[j]
        if gv and gv < (1 << n):
            out.append(gv)
    return out


def build_check_index(checks, n):
    col_checks = [[] for _ in range(n)]
    check_cols = []
    for ri, row in enumerate(checks):
        cols = list(iter_bits(row))
        check_cols.append(cols)
        for c in cols:
            if c < n:
                col_checks[c].append(ri)
    return col_checks, check_cols


def grow_cluster(seed, col_checks, check_cols, col_degree, n, rng, target):
    chosen = {seed}
    frontier = []
    seen = {seed}

    def add_neighbors(c):
        for ri in col_checks[c]:
            cols = check_cols[ri]
            if len(cols) > 80:
                sample = rng.sample(cols, 80)
            else:
                sample = cols
            for nb in sample:
                if nb not in seen:
                    seen.add(nb)
                    frontier.append(nb)

    add_neighbors(seed)
    while len(chosen) < target and frontier:
        best_i = None
        best_score = None
        sample_count = min(len(frontier), 16)
        for _ in range(sample_count):
            i = rng.randrange(len(frontier))
            c = frontier[i]
            shared = 0
            for ri in col_checks[c]:
                cols = check_cols[ri]
                if any(x in chosen for x in cols[:100]):
                    shared += 1
            score = 3 * col_degree[c] - 5 * shared + rng.random()
            if best_score is None or score < best_score:
                best_score = score
                best_i = i
        c = frontier.pop(best_i)
        if c in chosen:
            continue
        chosen.add(c)
        add_neighbors(c)

    if len(chosen) < target:
        while len(chosen) < target and len(chosen) < n:
            chosen.add(rng.randrange(n))
    return sorted(chosen)


def stabilizer_descent(v, stab_rows, checks, stab_basis, rng, passes=4):
    if not v:
        return v
    rows = [r for r in stab_rows if r]
    rows.sort(key=popcount)
    for _ in range(passes):
        changed = False
        if rows:
            start = rng.randrange(len(rows))
            order = rows[start:] + rows[:start]
        else:
            order = []
        for r in order:
            w = v ^ r
            if popcount(w) < popcount(v) and syndrome_zero(w, checks):
                v = w
                changed = True
        if not changed:
            break
    return v


def fallback_logical(checks, stab_basis, n, rng):
    ns = nullspace_basis(checks, n)
    rng.shuffle(ns)
    ns.sort(key=popcount)

    best = None
    augmented = dict(stab_basis)
    for b in ns:
        if not in_rowspace(b, stab_basis):
            if best is None or popcount(b) < popcount(best):
                best = b
        rem = reduce_by_basis(b, augmented)
        if rem:
            p = rem.bit_length() - 1
            for q, y in list(augmented.items()):
                if (y >> p) & 1:
                    augmented[q] = y ^ rem
            augmented[p] = rem

    pool = ns[: min(len(ns), 24)]
    for _ in range(220):
        if not pool:
            break
        v = 0
        for b in pool:
            if rng.random() < 0.22:
                v ^= b
        if v and not in_rowspace(v, stab_basis):
            if best is None or popcount(v) < popcount(best):
                best = v
    return best


def search_basis(name, checks, stab_rows, n, rng):
    stab_basis = rref_basis(stab_rows)
    col_checks, check_cols = build_check_index(checks, n)
    col_degree = [len(x) for x in col_checks]
    seeds = list(range(n))
    rng.shuffle(seeds)
    seeds.sort(key=lambda c: (col_degree[c], rng.random()))

    best = None

    max_cluster = min(n, max(10, int(2.5 * (sum(col_degree) / max(1, n) + 1)) + 12))
    schedule = sorted(set([4, 6, 8, 10, 14, 18, 24, 32, 48, 64, 96, max_cluster]))
    schedule = [s for s in schedule if 1 <= s <= n]

    budget = min(max(80, 10 * n), 1600)
    for t in range(budget):
        seed = seeds[t % len(seeds)] if seeds else rng.randrange(n)
        if t and t % max(1, len(seeds)) == 0:
            rng.shuffle(seeds)
        target = schedule[(t // max(1, len(seeds))) % len(schedule)]
        if rng.random() < 0.25:
            target = rng.choice(schedule)
        cols = grow_cluster(seed, col_checks, check_cols, col_degree, n, rng, target)

        for cand in restricted_null_vectors(checks, col_checks, cols, n, rng):
            if not syndrome_zero(cand, checks):
                continue
            if in_rowspace(cand, stab_basis):
                continue
            cand = stabilizer_descent(cand, stab_rows, checks, stab_basis, rng)
            if cand and syndrome_zero(cand, checks) and not in_rowspace(cand, stab_basis):
                if best is None or popcount(cand) < popcount(best):
                    best = cand

    fb = fallback_logical(checks, stab_basis, n, rng)
    if fb:
        fb = stabilizer_descent(fb, stab_rows, checks, stab_basis, rng, passes=6)
        if syndrome_zero(fb, checks) and not in_rowspace(fb, stab_basis):
            if best is None or popcount(fb) < popcount(best):
                best = fb

    return (name, best) if best else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    hx, nx = parse_matrix(args.hx)
    hz, nz = parse_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1) for r in hx]
    hz = [r & ((1 << n) - 1) for r in hz]

    rng = random.Random(args.seed)
    bx = search_basis("x", hz, hx, n, random.Random(rng.randrange(1 << 62)))
    bz = search_basis("z", hx, hz, n, random.Random(rng.randrange(1 << 62)))

    choices = [x for x in (bx, bz) if x and x[1]]
    if choices:
        basis, vec = min(choices, key=lambda item: (popcount(item[1]), 0 if item[0] == "x" else 1))
        out = {
            "status": "completed",
            "basis": basis,
            "vector": vector_to_list(vec, n),
            "upper_bound": popcount(vec),
        }
    else:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
        sys.exit(0)
