#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def bit_positions(x):
    while x:
        lb = x & -x
        yield lb.bit_length() - 1
        x ^= lb


def parse_matrix_arg(value):
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(value)


def dense_row_to_bits(row):
    if isinstance(row, str):
        row = row.strip()
        return sum((1 << i) for i, ch in enumerate(row) if ch == "1")
    bits = 0
    for i, v in enumerate(row):
        if int(v) & 1:
            bits |= 1 << i
    return bits


def load_matrix(value):
    obj = parse_matrix_arg(value)
    if isinstance(obj, dict) and "matrix" in obj:
        obj = obj["matrix"]
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict):
        if "data" in obj:
            data = obj.get("data") or []
            rows = [dense_row_to_bits(r) for r in data]
            n = int(obj.get("n_cols", obj.get("num_cols", max((len(r) for r in data), default=0))))
            return rows, n
        if "rows" in obj:
            sparse = obj.get("rows") or []
            n = int(obj.get("num_cols", obj.get("n_cols", 0)))
            if n == 0:
                n = 1 + max((max(r) for r in sparse if r), default=-1)
            rows = []
            for r in sparse:
                bits = 0
                for c in r:
                    c = int(c)
                    if c >= 0:
                        bits |= 1 << c
                rows.append(bits)
            return rows, n
    if isinstance(obj, list):
        rows = [dense_row_to_bits(r) for r in obj]
        n = max((len(r) for r in obj if hasattr(r, "__len__")), default=0)
        return rows, n
    raise ValueError("unsupported matrix format")


def rref(rows, n):
    a = [r & ((1 << n) - 1) for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        pivot = None
        mask = 1 << col
        for i in range(rank, len(a)):
            if a[i] & mask:
                pivot = i
                break
        if pivot is None:
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
    rr, pivots = rref(rows, n)
    pivot_set = set(pivots)
    basis = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, p in zip(rr, pivots):
            if row & (1 << free):
                v |= 1 << p
        if v:
            basis.append(v)
    return basis


def add_to_basis(basis, row):
    x = row
    while x:
        p = (x & -x).bit_length() - 1
        if p not in basis:
            basis[p] = x
            return True
        x ^= basis[p]
    return False


def reduce_by_basis(row, basis):
    x = row
    while x:
        p = (x & -x).bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def make_basis(rows):
    basis = {}
    for r in rows:
        add_to_basis(basis, r)
    return basis


def in_rowspace(row, rows):
    return reduce_by_basis(row, make_basis(rows)) == 0


def logical_basis_from(kernel, stabilizers):
    span = make_basis(stabilizers)
    logical = []
    for v in sorted(kernel, key=lambda x: (x.bit_count(), x)):
        if reduce_by_basis(v, span):
            logical.append(v)
            add_to_basis(span, v)
    return logical


def permute_rows(rows, inv_perm):
    out = []
    for r in rows:
        nr = 0
        for c in bit_positions(r):
            nr |= 1 << inv_perm[c]
        out.append(nr)
    return out


def unpermute_vec(v, perm):
    out = 0
    for j in bit_positions(v):
        out |= 1 << perm[j]
    return out


def randomized_kernel_bases(rows, n, rng, count):
    yield nullspace_basis(rows, n)
    for _ in range(max(0, count - 1)):
        perm = list(range(n))
        rng.shuffle(perm)
        inv = [0] * n
        for j, c in enumerate(perm):
            inv[c] = j
        yield [unpermute_vec(v, perm) for v in nullspace_basis(permute_rows(rows, inv), n)]


def verified(v, commute_rows, stabilizers):
    if v == 0:
        return False
    for r in commute_rows:
        if (v & r).bit_count() & 1:
            return False
    return not in_rowspace(v, stabilizers)


def polish(v, stabilizers, rng, n, budget):
    if not stabilizers:
        return v
    rows = [s for s in stabilizers if s]
    rows.sort(key=lambda x: x.bit_count())
    cur = v

    row_cap = 96 if n > 600 else max(80, min(256, n + 48))
    limit_rows = rows[: min(len(rows), row_cap)]
    for _ in range(2):
        changed = False
        order = limit_rows[:]
        rng.shuffle(order)
        for s in order:
            nv = cur ^ s
            if nv.bit_count() < cur.bit_count():
                cur = nv
                changed = True
        if not changed:
            break

    for _ in range(budget):
        t = 1
        roll = rng.random()
        if roll < 0.18:
            t = 2
        elif roll < 0.23:
            t = 3
        s = 0
        for _j in range(t):
            s ^= rng.choice(rows)
        nv = cur ^ s
        if nv.bit_count() < cur.bit_count():
            cur = nv
    return cur


def column_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        for c in bit_positions(r):
            if c < n:
                deg[c] += 1
    return deg


def random_logical_combo(logicals, rng, deg=None):
    m = len(logicals)
    if m == 1:
        return logicals[0]
    r = rng.random()
    if r < 0.45:
        k = 1
    elif r < 0.75:
        k = 2
    elif r < 0.92:
        k = 3
    else:
        k = rng.randint(1, min(m, 8))

    if deg and rng.random() < 0.45:
        scored = []
        for v in logicals:
            score = sum(deg[c] for c in bit_positions(v)) / max(1, v.bit_count())
            scored.append((score + rng.random() * 0.25, v))
        pool = [v for _s, v in sorted(scored)[: max(k, min(m, 12))]]
        picks = rng.sample(pool, min(k, len(pool)))
    else:
        picks = rng.sample(logicals, min(k, m))
    v = 0
    for p in picks:
        v ^= p
    return v


def search_one_basis(name, commute_rows, stabilizers, n, rng):
    deg = column_degrees(commute_rows + stabilizers, n)
    best = None
    best_w = n + 1
    seen = set()

    basis_count = 1 if n > 900 else 3
    for kernel in randomized_kernel_bases(commute_rows, n, rng, basis_count):
        logicals = logical_basis_from(kernel, stabilizers)
        if not logicals:
            continue
        logicals = sorted(set(logicals), key=lambda x: (x.bit_count(), x))

        seeds = logicals[: min(len(logicals), 48)]
        for i in range(min(len(logicals), 20)):
            for j in range(i + 1, min(len(logicals), i + 8, 28)):
                seeds.append(logicals[i] ^ logicals[j])

        iterations = min(12000, max(1600, 28 * n + 320 * len(logicals)))
        for idx in range(iterations + len(seeds)):
            if idx < len(seeds):
                cand = seeds[idx]
            else:
                cand = random_logical_combo(logicals, rng, deg)
            if cand in seen:
                continue
            seen.add(cand)
            cand = polish(cand, stabilizers, rng, n, budget=10 if n < 600 else 4)
            if cand.bit_count() < best_w and verified(cand, commute_rows, stabilizers):
                best = cand
                best_w = cand.bit_count()
                if best_w <= 1:
                    return name, best

    return (name, best) if best is not None else (name, None)


def vector_list(v, n):
    return [1 if (v >> i) & 1 else 0 for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    rng = random.Random(args.seed)

    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    mask = (1 << n) - 1
    hx = [r & mask for r in hx]
    hz = [r & mask for r in hz]

    candidates = []
    bx, vx = search_one_basis("x", hz, hx, n, rng)
    if vx is not None:
        candidates.append((vx.bit_count(), bx, vx))
    bz, vz = search_one_basis("z", hx, hz, n, rng)
    if vz is not None:
        candidates.append((vz.bit_count(), bz, vz))

    if candidates:
        _w, basis, vec = min(candidates, key=lambda t: (t[0], t[1]))
        out = {
            "status": "completed",
            "basis": basis,
            "vector": vector_list(vec, n),
            "upper_bound": int(vec.bit_count()),
        }
    else:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
