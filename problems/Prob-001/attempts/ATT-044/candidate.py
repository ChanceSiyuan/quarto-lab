#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        rows = obj
        n = max((len(r) for r in rows), default=0)
        return [row_to_int(r) for r in rows], n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", obj.get("num_cols", max((len(r) for r in data), default=0))))
        return [row_to_int(r) for r in data], n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        out = []
        for r in obj.get("rows", []):
            x = 0
            if isinstance(r, dict):
                r = r.get("cols", r.get("indices", []))
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    x ^= 1 << c
            out.append(x)
        return out, n
    raise ValueError("unsupported matrix JSON format")


def row_to_int(row):
    x = 0
    for i, v in enumerate(row):
        if int(v) & 1:
            x |= 1 << i
    return x


def weight(x):
    return int(x.bit_count())


def gf2_rank(rows):
    basis = {}
    for x in rows:
        x = int(x)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return len(basis)


def row_basis(rows):
    basis = {}
    for x in rows:
        insert_basis(basis, x)
    return basis


def insert_basis(basis, x):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        if p in basis:
            x ^= basis[p]
        else:
            basis[p] = x
            return True
    return False


def in_span_with_basis(basis, x):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        y = basis.get(p)
        if y is None:
            return False
        x ^= y
    return True


def kernel_basis(rows, n):
    rows = [r & ((1 << n) - 1) for r in rows if r]
    rref = {}
    for x in rows:
        while x:
            p = x.bit_length() - 1
            if p in rref:
                x ^= rref[p]
            else:
                rref[p] = x
                break
    for p in sorted(rref):
        for q in list(rref):
            if q != p and ((rref[q] >> p) & 1):
                rref[q] ^= rref[p]
    pivots = set(rref)
    basis = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rref.items():
            if (row >> f) & 1:
                v |= 1 << p
        basis.append(v)
    return basis


def syndrome_zero(rows, v):
    for r in rows:
        if ((r & v).bit_count() & 1) != 0:
            return False
    return True


def vector_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def logical_basis(kernel_rows, stab_rows, n):
    stab_basis = row_basis(stab_rows)
    span = dict(stab_basis)
    reps = []
    for v in kernel_basis(kernel_rows, n):
        if v and not in_span_with_basis(span, v):
            reps.append(v)
            insert_basis(span, v)
    return reps


def greedy_reduce(v, stab_rows, rng, rounds=10):
    if not v:
        return v
    rows = [r for r in stab_rows if r]
    rows.sort(key=weight)
    best = v
    for _ in range(rounds):
        cur = best
        order = rows[:]
        rng.shuffle(order)
        order.sort(key=lambda r: weight(cur ^ r) - weight(cur))
        changed = True
        passes = 0
        while changed and passes < 4:
            changed = False
            passes += 1
            for r in order:
                nr = cur ^ r
                if weight(nr) < weight(cur):
                    cur = nr
                    changed = True
        if weight(cur) < weight(best):
            best = cur
    return best


def columns_from_rows(rows, n):
    cols = [0] * n
    deg = [0] * n
    for ri, r in enumerate(rows):
        x = r
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            cols[c] |= 1 << ri
            deg[c] += 1
            x ^= lsb
    return cols, deg


def projected_candidate(kernel_rows, stab_rows, n, rng, deadline):
    stab_basis = row_basis(stab_rows)
    cols, deg = columns_from_rows(kernel_rows, n)
    order = list(range(n))
    order.sort(key=lambda c: (deg[c], c))
    best = None

    def accept(v):
        nonlocal best
        if not v or not syndrome_zero(kernel_rows, v) or in_span_with_basis(stab_basis, v):
            return
        v = greedy_reduce(v, stab_rows, rng, rounds=6)
        if v and syndrome_zero(kernel_rows, v) and not in_span_with_basis(stab_basis, v):
            if best is None or weight(v) < weight(best):
                best = v

    # Fast subset kernels over low-degree columns are the sharpest projection.
    sizes = []
    for s in (10, 14, 18, 24, 32, 48, 64, 96, 128):
        if s <= n:
            sizes.append(s)
    if n and n not in sizes:
        sizes.append(min(n, max(16, int(n ** 0.5) * 6)))

    it = 0
    while time.time() < deadline and it < 180:
        it += 1
        s = sizes[it % len(sizes)] if sizes else n
        pool_cut = min(n, max(s, int(0.25 * n) + s))
        low_pool = order[:pool_cut]
        chosen = set(rng.sample(low_pool, min(s, len(low_pool)))) if low_pool else set()
        # Mix in projected buckets: a variable can represent a random small mask,
        # so nullspace solutions lift from projection space back to physical qubits.
        masks = [1 << c for c in chosen]
        bucket_count = min(max(6, s // 3), max(6, n // 8 + 1))
        for _ in range(bucket_count):
            k = rng.choice((2, 2, 3, 4, 5))
            sample_pool = low_pool if rng.random() < 0.75 else list(range(n))
            if sample_pool:
                m = 0
                for c in rng.sample(sample_pool, min(k, len(sample_pool))):
                    m ^= 1 << c
                if m:
                    masks.append(m)
        if not masks:
            continue
        prow = []
        for r in kernel_rows:
            y = 0
            for j, m in enumerate(masks):
                if (r & m).bit_count() & 1:
                    y |= 1 << j
            if y:
                prow.append(y)
        kb = kernel_basis(prow, len(masks))
        if not kb:
            continue
        rng.shuffle(kb)
        trials = min(20, max(4, len(kb) * 2))
        for t in range(trials):
            y = 0
            if t < len(kb):
                y = kb[t]
            else:
                for b in kb:
                    if rng.random() < 0.35:
                        y ^= b
            v = 0
            z = y
            while z:
                lsb = z & -z
                j = lsb.bit_length() - 1
                v ^= masks[j]
                z ^= lsb
            accept(v)

    return best


def best_fallback(kernel_rows, stab_rows, n, rng):
    reps = logical_basis(kernel_rows, stab_rows, n)
    stab_basis = row_basis(stab_rows)
    best = None
    for v in reps:
        v = greedy_reduce(v, stab_rows, rng, rounds=14)
        if v and syndrome_zero(kernel_rows, v) and not in_span_with_basis(stab_basis, v):
            if best is None or weight(v) < weight(best):
                best = v
    return best


def solve(hx, hz, seed):
    hx_rows, nx = parse_matrix(hx)
    hz_rows, nz = parse_matrix(hz)
    n = max(nx, nz)
    mask = (1 << n) - 1 if n else 0
    hx_rows = [r & mask for r in hx_rows]
    hz_rows = [r & mask for r in hz_rows]
    rng = random.Random(seed)
    deadline = time.time() + float(os.environ.get("CANDIDATE_TIME_LIMIT", "25"))

    problems = [("x", hz_rows, hx_rows), ("z", hx_rows, hz_rows)]
    rng.shuffle(problems)
    best_basis = None
    best_vec = None

    for basis, kernel_rows, stab_rows in problems:
        v = projected_candidate(kernel_rows, stab_rows, n, rng, deadline)
        if v is not None and (best_vec is None or weight(v) < weight(best_vec)):
            best_basis, best_vec = basis, v

    # Reliable basis-derived fallback for any positive-k CSS input.
    for basis, kernel_rows, stab_rows in problems:
        v = best_fallback(kernel_rows, stab_rows, n, rng)
        if v is not None and (best_vec is None or weight(v) < weight(best_vec)):
            best_basis, best_vec = basis, v

    if best_vec is None:
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    return {
        "status": "completed",
        "basis": best_basis,
        "vector": vector_list(best_vec, n),
        "upper_bound": weight(best_vec),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()
    try:
        result = solve(args.hx, args.hz, args.seed)
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
