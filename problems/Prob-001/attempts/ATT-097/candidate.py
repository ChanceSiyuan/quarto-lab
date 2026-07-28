#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def fail():
    print(json.dumps({"status": "failed", "basis": None, "vector": None, "upper_bound": None}, separators=(",", ":")))


def load_json_arg(value):
    if value == "-":
        return json.load(sys.stdin)
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(value)


def matrix_to_rows(obj):
    if obj is None:
        return [], 0
    if isinstance(obj, dict):
        if "dense_binary_matrix" in obj:
            obj = obj["dense_binary_matrix"]
        elif "sparse_rows" in obj:
            obj = obj["sparse_rows"]
    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", 0))
        rows = []
        for row in data:
            bits = 0
            for j, x in enumerate(row[:n]):
                if int(x) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n
    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for row in obj.get("rows") or []:
            bits = 0
            for j in row:
                jj = int(j)
                if 0 <= jj < n:
                    bits |= 1 << jj
            rows.append(bits)
        return rows, n
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for row in obj:
            bits = 0
            for j, x in enumerate(row):
                if int(x) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n
    raise ValueError("unsupported matrix format")


def parity(x):
    return x.bit_count() & 1


def build_row_basis(rows):
    basis = {}
    for r in rows:
        x = int(r)
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def reduce_by_basis(x, basis):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def rref_rows(rows, n):
    a = [r for r in rows if r]
    rank = 0
    pivots = []
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
    rref, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    out = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, pivot in zip(rref, pivots):
            if parity(row & v):
                v |= 1 << pivot
        out.append(v)
    return out


def permute_rows(rows, order):
    out = []
    for r in rows:
        x = 0
        for new_j, old_j in enumerate(order):
            if (r >> old_j) & 1:
                x |= 1 << new_j
        out.append(x)
    return out


def unpermute_vec(v, order):
    x = 0
    while v:
        lsb = v & -v
        j = lsb.bit_length() - 1
        x |= 1 << order[j]
        v ^= lsb
    return x


def ordered_nullspace(rows, n, order):
    return [unpermute_vec(v, order) for v in nullspace_basis(permute_rows(rows, order), n)]


def verify(v, check_rows, stab_basis):
    if not v:
        return False
    for r in check_rows:
        if parity(v & r):
            return False
    return not in_rowspace(v, stab_basis)


def bit_list(v, n):
    return [(v >> j) & 1 for j in range(n)]


def column_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        x = r
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            if j < n:
                deg[j] += 1
            x ^= lsb
    return deg


def weighted_order(rng, weights):
    keys = [rng.random() ** (1.0 / max(w, 1.0e-9)) for w in weights]
    return sorted(range(len(weights)), key=lambda j: keys[j], reverse=True)


def random_combo(rng, vecs, probs=None, min_take=1):
    if not vecs:
        return 0
    v = 0
    taken = 0
    if probs is None:
        p = min(0.5, max(0.08, 3.0 / max(1, len(vecs))))
        for b in vecs:
            if rng.random() < p:
                v ^= b
                taken += 1
    else:
        for b, p in zip(vecs, probs):
            if rng.random() < p:
                v ^= b
                taken += 1
    if taken < min_take:
        v = rng.choice(vecs)
    return v


def improve_by_pool(v, pool, check_rows, stab_basis, passes=4):
    if not verify(v, check_rows, stab_basis):
        return None
    best = v
    for _ in range(passes):
        changed = False
        for s in sorted(pool, key=lambda x: (x.bit_count(), x)):
            u = best ^ s
            if u.bit_count() < best.bit_count() and verify(u, check_rows, stab_basis):
                best = u
                changed = True
        if not changed:
            break
    return best


def find_for_basis(name, check_rows, stab_rows, n, rng, deadline):
    stab_basis = build_row_basis(stab_rows)
    base_ns = nullspace_basis(check_rows, n)
    if not base_ns:
        return None

    best = None
    pool = list(stab_rows)

    # Reliable quotient fallback: a nullspace basis vector outside the stabilizer
    # row space is already a valid logical representative for positive k.
    for v in sorted(base_ns, key=lambda x: x.bit_count()):
        if verify(v, check_rows, stab_basis):
            u = improve_by_pool(v, pool, check_rows, stab_basis, passes=3)
            if u is not None and (best is None or u.bit_count() < best.bit_count()):
                best = u

    deg_check = column_degrees(check_rows, n)
    deg_stab = column_degrees(stab_rows, n)
    bias = [1.0 / (1.0 + deg_check[j] + 0.35 * deg_stab[j]) for j in range(n)]
    if best is not None:
        x = best
        while x:
            lsb = x & -x
            bias[lsb.bit_length() - 1] *= 1.8
            x ^= lsb

    attempts = 0
    stagnant = 0
    while time.monotonic() < deadline and attempts < 220:
        attempts += 1
        order = weighted_order(rng, bias)
        ns = ordered_nullspace(check_rows, n, order)
        if not ns:
            continue
        # Score basis vectors by current adaptive column bias and weight. This
        # keeps the randomized information set search biased toward columns that
        # repeatedly survive in good witnesses while still exploring new pivots.
        scored = []
        for b in ns:
            s = 0.0
            x = b
            while x:
                lsb = x & -x
                s += bias[lsb.bit_length() - 1]
                x ^= lsb
            scored.append(s / max(1, b.bit_count()))
        order_basis = sorted(range(len(ns)), key=lambda i: scored[i], reverse=True)
        front = [ns[i] for i in order_basis[: max(4, min(len(ns), 48))]]
        probs = [min(0.42, max(0.04, 0.10 + 0.22 * scored[i] / (scored[order_basis[0]] + 1.0e-12))) for i in order_basis[: len(front)]]
        candidates = []
        candidates.extend(front[: min(12, len(front))])
        for _ in range(10):
            candidates.append(random_combo(rng, front, probs))
        if len(ns) <= 80:
            for _ in range(4):
                candidates.append(random_combo(rng, ns))
        for v in candidates:
            if not verify(v, check_rows, stab_basis):
                continue
            u = improve_by_pool(v, pool + front[:16], check_rows, stab_basis, passes=2)
            if u is None:
                continue
            if best is None or u.bit_count() < best.bit_count():
                best = u
                stagnant = 0
                y = u
                support = set()
                while y:
                    lsb = y & -y
                    support.add(lsb.bit_length() - 1)
                    y ^= lsb
                for j in range(n):
                    if j in support:
                        bias[j] = min(10.0, bias[j] * 1.35 + 0.05)
                    else:
                        bias[j] = max(1.0e-4, bias[j] * 0.995)
            else:
                stagnant += 1
        if stagnant > 40:
            for j in range(n):
                bias[j] = 0.75 * bias[j] + 0.25 / (1.0 + deg_check[j] + 0.35 * deg_stab[j])
            stagnant = 0
    if best is None:
        return None
    return name, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    try:
        hx, nx = matrix_to_rows(load_json_arg(args.hx))
        hz, nz = matrix_to_rows(load_json_arg(args.hz))
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        deadline = time.monotonic() + 28.0
        results = []
        rx = find_for_basis("x", hz, hx, n, rng, deadline)
        if rx is not None:
            results.append(rx)
        rz = find_for_basis("z", hx, hz, n, rng, deadline)
        if rz is not None:
            results.append(rz)
        if not results:
            fail()
            return
        basis, vec = min(results, key=lambda item: (item[1].bit_count(), 0 if item[0] == "x" else 1))
        check_rows = hz if basis == "x" else hx
        stab_rows = hx if basis == "x" else hz
        if not verify(vec, check_rows, build_row_basis(stab_rows)):
            fail()
            return
        print(json.dumps({
            "status": "completed",
            "basis": basis,
            "vector": bit_list(vec, n),
            "upper_bound": int(vec.bit_count()),
        }, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
