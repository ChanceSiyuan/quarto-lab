#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
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
            for j, v in enumerate(row):
                if v & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for row in obj.get("rows", []):
            x = 0
            for j in row:
                jj = int(j)
                if 0 <= jj < n:
                    x |= 1 << jj
            rows.append(x)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            break
        y ^= b
    return y


def insert_basis(basis, x):
    y = reduce_by_basis(x, basis)
    if not y:
        return False
    p = y.bit_length() - 1
    for q, b in list(basis.items()):
        if (b >> p) & 1:
            basis[q] = b ^ y
    basis[p] = y
    return True


def make_basis(rows):
    basis = {}
    for r in rows:
        insert_basis(basis, r)
    return basis


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def rref_rows(rows, n):
    a = [r for r in rows if r]
    rank = 0
    pivots = []
    for col in range(n):
        pivot = -1
        mask = 1 << col
        for i in range(rank, len(a)):
            if a[i] & mask:
                pivot = i
                break
        if pivot < 0:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        for i in range(len(a)):
            if i != rank and (a[i] & mask):
                a[i] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == len(a):
            break
    return a[:rank], pivots


def nullspace_basis(rows, n):
    rr, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    out = []
    for f in range(n):
        if f in pivot_set:
            continue
        x = 1 << f
        for row, p in zip(rr, pivots):
            if (row >> f) & 1:
                x |= 1 << p
        out.append(x)
    return out


def quotient_logicals(check_rows, stab_rows, n, cap=None):
    stab_basis = make_basis(stab_rows)
    span = dict(stab_basis)
    logicals = []
    for v in nullspace_basis(check_rows, n):
        if insert_basis(span, v):
            logicals.append(v)
            if cap is not None and len(logicals) >= cap:
                break
    return logicals, stab_basis


def rows_by_column(rows, n):
    cols = [[] for _ in range(n)]
    weights = []
    for r in rows:
        w = r.bit_count()
        weights.append(w)
        y = r
        while y:
            bit = y & -y
            c = bit.bit_length() - 1
            if c < n:
                cols[c].append(r)
            y ^= bit
    return cols, weights


def greedy_reduce(v, stab_rows, col_rows, rng, passes=4, noise=0.0):
    cur = v
    curw = cur.bit_count()
    order = list(stab_rows)
    for _ in range(passes):
        changed = False
        rng.shuffle(order)
        for r in order:
            nw = (cur ^ r).bit_count()
            if nw < curw or (nw == curw and noise > 0.0 and rng.random() < noise):
                cur ^= r
                curw = nw
                changed = True
        hot = []
        y = cur
        while y:
            bit = y & -y
            hot.append(bit.bit_length() - 1)
            y ^= bit
        rng.shuffle(hot)
        for c in hot:
            linked = list(col_rows[c]) if c < len(col_rows) else []
            rng.shuffle(linked)
            for r in linked[:32]:
                nw = (cur ^ r).bit_count()
                if nw < curw or (nw == curw and noise > 0.0 and rng.random() < noise * 0.5):
                    cur ^= r
                    curw = nw
                    changed = True
        if not changed:
            break
    return cur


def random_combo(vecs, rng, max_terms=None):
    if not vecs:
        return 0
    if max_terms is None:
        max_terms = len(vecs)
    k = rng.randint(1, max(1, min(len(vecs), max_terms)))
    idxs = rng.sample(range(len(vecs)), k)
    x = 0
    for i in idxs:
        x ^= vecs[i]
    return x


def verify(v, check_rows, stab_basis):
    if v == 0:
        return False
    for r in check_rows:
        if (r & v).bit_count() & 1:
            return False
    return not in_span(v, stab_basis)


def vector_list(v, n):
    return [int((v >> i) & 1) for i in range(n)]


def search_basis(name, check_rows, stab_rows, n, rng, deadline):
    logicals, stab_basis = quotient_logicals(check_rows, stab_rows, n)
    if not logicals:
        return None
    col_rows, _ = rows_by_column(stab_rows, n)
    pool = []
    for v in logicals:
        pool.append(greedy_reduce(v, stab_rows, col_rows, rng, passes=3, noise=0.0))
    pool.sort(key=lambda x: x.bit_count())
    best = None
    for v in pool[: max(1, min(len(pool), 64))]:
        if verify(v, check_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v
    if best is None:
        for v in logicals:
            if verify(v, check_rows, stab_basis):
                best = v
                break
    if best is None:
        return None

    rounds = 0
    max_terms = min(len(logicals), 10)
    while time.time() < deadline and rounds < 2500:
        rounds += 1
        if rng.random() < 0.55 and pool:
            seeds = pool[: min(len(pool), 32)]
            v = random_combo(seeds, rng, max_terms=min(len(seeds), 5))
        else:
            v = random_combo(logicals, rng, max_terms=max_terms)
        if rng.random() < 0.35:
            v ^= random_combo(logicals, rng, max_terms=min(len(logicals), 3))
        v = greedy_reduce(v, stab_rows, col_rows, rng, passes=5, noise=0.015)
        if verify(v, check_rows, stab_basis):
            pool.append(v)
            if v.bit_count() < best.bit_count():
                best = v
                if best.bit_count() <= 1:
                    break
            if len(pool) > 96:
                pool = sorted(set(pool), key=lambda x: x.bit_count())[:64]
    return name, best, best.bit_count()


def emit(status, basis=None, vector=None, upper_bound=None):
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
    os.makedirs(args.output_dir, exist_ok=True)
    rng = random.Random(args.seed)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    start = time.time()
    x_deadline = start + 4.5
    z_deadline = start + 9.0

    results = []
    xb = search_basis("x", hz, hx, n, rng, x_deadline)
    if xb is not None:
        results.append(xb)
    if time.time() < z_deadline:
        zb = search_basis("z", hx, hz, n, rng, z_deadline)
        if zb is not None:
            results.append(zb)

    if not results:
        emit("failed", None, None, None)
        return 0
    basis, v, w = min(results, key=lambda t: (t[2], 0 if t[0] == "x" else 1))
    emit("completed", basis, vector_list(v, n), w)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        emit("failed", None, None, None)
        raise SystemExit(0)
