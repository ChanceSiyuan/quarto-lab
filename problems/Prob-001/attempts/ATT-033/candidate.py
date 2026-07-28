#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_matrix_arg(value):
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            obj = json.load(f)
    else:
        obj = json.loads(value)
    return parse_matrix(obj)


def parse_matrix(obj):
    if isinstance(obj, dict) and "matrix" in obj:
        obj = obj["matrix"]
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for j, bit in enumerate(r[:n]):
                if bit & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        sparse = obj.get("rows") or []
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n == 0:
            n = 1 + max((c for r in sparse for c in r), default=-1)
        rows = []
        for r in sparse:
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    x |= 1 << c
            rows.append(x)
        return rows, n

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for j, bit in enumerate(r):
                if bit & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix format")


def lowbit_index(x):
    return (x & -x).bit_length() - 1


def row_echelon(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = lowbit_index(x)
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def row_reduce(x, basis):
    y = x
    while y:
        p = lowbit_index(y)
        b = basis.get(p)
        if b is None:
            break
        y ^= b
    return y


def in_rowspace(x, basis):
    return row_reduce(x, basis) == 0


def rref_rows(rows):
    basis = row_echelon(rows)
    pivots = sorted(basis)
    for p in sorted(pivots, reverse=True):
        row = basis[p]
        for q in pivots:
            if q != p and ((row >> q) & 1):
                row ^= basis[q]
        basis[p] = row
    return basis


def nullspace_basis(check_rows, n):
    rref = rref_rows(check_rows)
    pivots = set(rref)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rref.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def mat_vec_zero(rows, v):
    return all(((r & v).bit_count() & 1) == 0 for r in rows)


def mask_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def column_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        x = r
        while x:
            lb = x & -x
            deg[lb.bit_length() - 1] += 1
            x ^= lb
    return deg


def greedy_stabilizer_descent(v, stabilizers, rng, rounds=3):
    best = v
    best_w = best.bit_count()
    rows = [r for r in stabilizers if r]
    for _ in range(rounds):
        improved = False
        rng.shuffle(rows)
        for s in rows:
            w = (best ^ s).bit_count()
            if w < best_w:
                best ^= s
                best_w = w
                improved = True
        if not improved:
            break
    return best


def random_combo(vectors, rng, probs):
    v = 0
    used = False
    for b, p in zip(vectors, probs):
        if rng.random() < p:
            v ^= b
            used = True
    if not used and vectors:
        weights = [max(1.0e-6, p) for p in probs]
        total = sum(weights)
        t = rng.random() * total
        acc = 0.0
        for b, w in zip(vectors, weights):
            acc += w
            if acc >= t:
                v = b
                break
    return v


def fallback_witness(kernel_basis, stabilizer_basis, stabilizers, check_rows, n, rng):
    for b in sorted(kernel_basis, key=lambda x: x.bit_count()):
        v = greedy_stabilizer_descent(b, stabilizers, rng, rounds=5)
        if v and mat_vec_zero(check_rows, v) and not in_rowspace(v, stabilizer_basis):
            return v
        if b and mat_vec_zero(check_rows, b) and not in_rowspace(b, stabilizer_basis):
            return b
    return 0


def search_basis(name, check_rows, stabilizer_rows, n, rng):
    kernel_basis = nullspace_basis(check_rows, n)
    stabilizer_basis = row_echelon(stabilizer_rows)
    if not kernel_basis:
        return None

    deg = column_degrees(check_rows + stabilizer_rows, n)
    max_deg = max(deg, default=0)
    col_bias = [1.0 + (max_deg - d) / (1.0 + max_deg) for d in deg]

    free_scores = []
    for b in kernel_basis:
        total = 0.0
        x = b
        while x:
            lb = x & -x
            total += col_bias[lb.bit_length() - 1]
            x ^= lb
        free_scores.append(total / max(1, b.bit_count()))

    best = None
    best_w = n + 1

    def consider(v):
        nonlocal best, best_w, col_bias, free_scores
        if not v:
            return
        v = greedy_stabilizer_descent(v, stabilizer_rows, rng, rounds=4)
        if not mat_vec_zero(check_rows, v) or in_rowspace(v, stabilizer_basis):
            return
        w = v.bit_count()
        if w < best_w:
            best = v
            best_w = w
            for i in range(n):
                if (v >> i) & 1:
                    col_bias[i] = 0.88 * col_bias[i] + 0.35
                else:
                    col_bias[i] *= 0.998
            free_scores = []
            for b in kernel_basis:
                total = 0.0
                x = b
                while x:
                    lb = x & -x
                    total += col_bias[lb.bit_length() - 1]
                    x ^= lb
                free_scores.append(total / max(1, b.bit_count()))

    for b in sorted(kernel_basis, key=lambda x: x.bit_count())[: min(len(kernel_basis), 256)]:
        consider(b)

    iterations = min(9000, max(1200, 90 * len(kernel_basis) + 12 * n))
    for t in range(iterations):
        temp = 1.0 - 0.75 * (t / max(1, iterations - 1))
        lo = min(free_scores, default=0.0)
        hi = max(free_scores, default=1.0)
        span = max(1.0e-9, hi - lo)
        probs = []
        for s in free_scores:
            q = (s - lo) / span
            base = 0.015 + temp * (0.06 + 0.34 * q)
            probs.append(min(0.48, max(0.006, base)))
        v = random_combo(kernel_basis, rng, probs)
        if t % 11 == 0 and kernel_basis:
            for _ in range(rng.randrange(1, 4)):
                v ^= kernel_basis[rng.randrange(len(kernel_basis))]
        consider(v)

    if best is None:
        best = fallback_witness(kernel_basis, stabilizer_basis, stabilizer_rows, check_rows, n, rng)
    if best and mat_vec_zero(check_rows, best) and not in_rowspace(best, stabilizer_basis):
        return {"basis": name, "vector": mask_to_list(best, n), "upper_bound": best.bit_count()}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    try:
        hx, nx = load_matrix_arg(args.hx)
        hz, nz = load_matrix_arg(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        rng = random.Random(args.seed)

        results = []
        rx = search_basis("x", hz, hx, n, rng)
        if rx:
            results.append(rx)
        rz = search_basis("z", hx, hz, n, rng)
        if rz:
            results.append(rz)

        if results:
            ans = min(results, key=lambda r: (r["upper_bound"], r["basis"]))
            ans = {
                "status": "completed",
                "basis": ans["basis"],
                "vector": ans["vector"],
                "upper_bound": ans["upper_bound"],
            }
        else:
            ans = {"status": "failed", "basis": "x", "vector": [0] * n, "upper_bound": 0}
    except Exception:
        ans = {"status": "failed", "basis": "x", "vector": [], "upper_bound": 0}

    print(json.dumps(ans, separators=(",", ":")))


if __name__ == "__main__":
    main()
