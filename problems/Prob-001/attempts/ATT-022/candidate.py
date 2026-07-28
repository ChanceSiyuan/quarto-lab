#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time


def read_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for j, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        n = int(obj.get("n_cols", 0))
        rows = []
        for r in obj.get("data", []):
            x = 0
            for j, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << j
            rows.append(x)
        if n == 0:
            n = max((r.bit_length() for r in rows), default=0)
        return rows, n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            x = 0
            for j in r:
                jj = int(j)
                if jj >= 0:
                    x ^= 1 << jj
            rows.append(x)
        if n == 0:
            n = max((r.bit_length() for r in rows), default=0)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def mask_n(x, n):
    if n <= 0:
        return 0
    return x & ((1 << n) - 1)


def rref_basis(rows, n):
    basis = {}
    for raw in rows:
        x = mask_n(int(raw), n)
        while x:
            p = x.bit_length() - 1
            y = basis.get(p)
            if y is None:
                basis[p] = x
                break
            x ^= y
    pivots = sorted(basis.keys(), reverse=True)
    for p in pivots:
        row = basis[p]
        for q in pivots:
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    return basis


def reduce_by_basis(x, basis):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        y = basis.get(p)
        if y is None:
            return x
        x ^= y
    return 0


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    rb = rref_basis(rows, n)
    pivots = set(rb.keys())
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def column_syndromes(rows, n):
    cols = [0] * n
    for i, r in enumerate(rows):
        x = mask_n(r, n)
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            cols[j] |= 1 << i
            x ^= lsb
    return cols


def syndrome(v, rows):
    s = 0
    for i, r in enumerate(rows):
        if ((v & r).bit_count() & 1):
            s |= 1 << i
    return s


def vector_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def css_verified(v, kernel_checks, stabilizer_basis, n):
    v = mask_n(v, n)
    return v != 0 and syndrome(v, kernel_checks) == 0 and not in_rowspace(v, stabilizer_basis)


def greedy_reduce(v, stabilizer_rows, stabilizer_basis, kernel_checks, n, rng, rounds=4):
    v = mask_n(v, n)
    rows = [mask_n(r, n) for r in stabilizer_rows if mask_n(r, n)]
    best = v
    for _ in range(rounds):
        changed = True
        order = rows[:]
        rng.shuffle(order)
        cur = best
        while changed:
            changed = False
            for r in order:
                w = cur ^ r
                if w.bit_count() < cur.bit_count():
                    cur = w
                    changed = True
        if css_verified(cur, kernel_checks, stabilizer_basis, n) and cur.bit_count() < best.bit_count():
            best = cur
    return best


def random_subset_from_pool(pool, cols, rng, max_take):
    if not pool:
        return 0, 0
    k = rng.randint(1, min(max_take, len(pool)))
    support = 0
    syn = 0
    for j in rng.sample(pool, k):
        support ^= 1 << j
        syn ^= cols[j]
    return support, syn


def mitm_search(kernel_checks, stabilizer_rows, stabilizer_basis, n, rng, deadline):
    cols = column_syndromes(kernel_checks, n)
    weights = [c.bit_count() for c in cols]
    quiet = [i for i, w in enumerate(weights) if w <= 2]
    active = [i for i, w in enumerate(weights) if w > 0]
    all_cols = list(range(n))
    best = None
    pools = []
    if quiet:
        pools.append(quiet)
    if active:
        pools.append(active)
    pools.append(all_cols)

    for pool in pools:
        if time.time() >= deadline:
            break
        for _restart in range(18):
            if time.time() >= deadline:
                break
            shuffled = pool[:]
            rng.shuffle(shuffled)
            mid = len(shuffled) // 2
            left = shuffled[:mid] or shuffled
            right = shuffled[mid:] or shuffled
            table = {}
            samples = min(5500, max(600, 45 * max(1, len(pool))))
            max_take = 1 if len(pool) <= 4 else min(7, max(2, len(pool) // 5))
            for _ in range(samples):
                sup, syn = random_subset_from_pool(left, cols, rng, max_take)
                old = table.get(syn)
                if old is None or sup.bit_count() < old.bit_count():
                    table[syn] = sup
            for _ in range(samples):
                sup_r, syn = random_subset_from_pool(right, cols, rng, max_take)
                sup_l = table.get(syn)
                if sup_l is None:
                    continue
                cand = sup_l ^ sup_r
                if cand == 0 or syndrome(cand, kernel_checks) != 0:
                    continue
                if not in_rowspace(cand, stabilizer_basis):
                    cand = greedy_reduce(cand, stabilizer_rows, stabilizer_basis, kernel_checks, n, rng, rounds=2)
                    if css_verified(cand, kernel_checks, stabilizer_basis, n):
                        if best is None or cand.bit_count() < best.bit_count():
                            best = cand
    return best


def quotient_fallback(kernel_checks, stabilizer_rows, stabilizer_basis, n, rng):
    ns = nullspace_basis(kernel_checks, n)
    best = None
    logical_seeds = []
    # A basis-derived quotient scan is the reliability backstop: it finds a
    # non-stabilizer kernel vector whenever the corresponding CSS dimension is positive.
    for v in ns:
        rem = reduce_by_basis(v, stabilizer_basis)
        if rem and css_verified(v, kernel_checks, stabilizer_basis, n):
            logical_seeds.append(v)
            cand = greedy_reduce(v, stabilizer_rows, stabilizer_basis, kernel_checks, n, rng, rounds=6)
            if best is None or cand.bit_count() < best.bit_count():
                best = cand
    if logical_seeds:
        logical_seeds = sorted(logical_seeds, key=lambda x: x.bit_count())[:160]
        for _ in range(min(900, 35 * len(logical_seeds))):
            take = rng.randint(1, min(10, len(logical_seeds)))
            combo = 0
            for v in rng.sample(logical_seeds, take):
                combo ^= v
            if css_verified(combo, kernel_checks, stabilizer_basis, n):
                cand = greedy_reduce(combo, stabilizer_rows, stabilizer_basis, kernel_checks, n, rng, rounds=3)
                if best is None or cand.bit_count() < best.bit_count():
                    best = cand
    if best is not None:
        return best
    combo = 0
    for v in ns:
        combo ^= v
        if css_verified(combo, kernel_checks, stabilizer_basis, n):
            return greedy_reduce(combo, stabilizer_rows, stabilizer_basis, kernel_checks, n, rng, rounds=6)
    return None


def logical_for_basis(which, hx, hz, n, rng, deadline):
    if which == "x":
        kernel_checks, stabilizer_rows = hz, hx
    else:
        kernel_checks, stabilizer_rows = hx, hz
    stabilizer_basis = rref_basis(stabilizer_rows, n)
    best = mitm_search(kernel_checks, stabilizer_rows, stabilizer_basis, n, rng, deadline)
    fb = quotient_fallback(kernel_checks, stabilizer_rows, stabilizer_basis, n, rng)
    if fb is not None and (best is None or fb.bit_count() < best.bit_count()):
        best = fb
    if best is not None and css_verified(best, kernel_checks, stabilizer_basis, n):
        return best
    return None


def emit(status, basis, vector, upper_bound):
    print(json.dumps({
        "status": status,
        "basis": basis,
        "vector": vector,
        "upper_bound": upper_bound,
    }, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    try:
        hx, nx = read_matrix(args.hx)
        hz, nz = read_matrix(args.hz)
        n = max(nx, nz)
        hx = [mask_n(r, n) for r in hx]
        hz = [mask_n(r, n) for r in hz]
        deadline = time.time() + 8.0
        choices = ["x", "z"]
        rng.shuffle(choices)
        found = []
        for b in choices:
            v = logical_for_basis(b, hx, hz, n, rng, deadline)
            if v is not None:
                found.append((v.bit_count(), b, v))
        if found:
            _, b, v = min(found, key=lambda t: (t[0], t[1]))
            emit("completed", b, vector_list(v, n), v.bit_count())
        else:
            emit("not_found", choices[0], [0] * n, None)
    except Exception:
        emit("error", "x", [], None)


if __name__ == "__main__":
    main()
