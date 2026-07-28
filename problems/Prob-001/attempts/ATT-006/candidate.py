#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def load_css_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        return [dense_row_to_int(r, n) for r in data], n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or row list")

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", obj.get("num_cols", max((len(r) for r in data), default=0))))
        return [dense_row_to_int(r, n) for r in data], n

    if "rows" in obj:
        rows = obj["rows"]
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = 1 + max((max(r) for r in rows if r), default=-1)
        return [sparse_row_to_int(r) for r in rows], n

    raise ValueError("unsupported matrix JSON format")


def dense_row_to_int(row, n):
    x = 0
    for i, bit in enumerate(row[:n]):
        if int(bit) & 1:
            x |= 1 << i
    return x


def sparse_row_to_int(row):
    x = 0
    for j in row:
        if int(j) >= 0:
            x ^= 1 << int(j)
    return x


def build_rref(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                for q, b in list(basis.items()):
                    if (x >> q) & 1:
                        x ^= b
                for q, b in list(basis.items()):
                    if (b >> p) & 1:
                        basis[q] = b ^ x
                basis[p] = x
                break
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


def kernel_basis(check_rows, n):
    rref = build_rref(check_rows)
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


def syndrome_is_zero(v, check_rows):
    for row in check_rows:
        if ((row & v).bit_count() & 1) != 0:
            return False
    return True


def verified_logical(v, check_rows, stabilizer_basis):
    return v != 0 and syndrome_is_zero(v, check_rows) and not in_rowspace(v, stabilizer_basis)


def int_to_vector(v, n):
    return [(v >> i) & 1 for i in range(n)]


def column_syndromes(check_rows, n):
    cols = [0] * n
    for r, row in enumerate(check_rows):
        x = row
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c < n:
                cols[c] |= 1 << r
            x ^= lsb
    return cols


def random_combo(rng, columns, max_size, weighted=True):
    n = len(columns)
    if n == 0:
        return 0
    size = rng.randint(1, min(max_size, n))
    if weighted and rng.random() < 0.72:
        # Bias toward locally sparse columns without making the search deterministic.
        pool = sorted(range(n), key=lambda i: (columns[i].bit_count(), rng.random()))
        span = max(size, min(n, 12 + 4 * size + int(rng.random() * max(1, n // 3))))
        picks = rng.sample(pool[:span], size)
    else:
        picks = rng.sample(range(n), size)
    v = 0
    for c in picks:
        v ^= 1 << c
    return v


def remit_search(check_rows, stab_basis, n, rng, deadline):
    cols = column_syndromes(check_rows, n)
    best = None
    best_w = n + 1

    # Randomized meet-in-the-middle: sample small partial supports, match equal
    # check syndromes, and verify only assembled kernel candidates.
    rounds = 9 if n < 400 else 6
    table_cap = 2200 if n < 700 else 1300
    probe_cap = 4200 if n < 700 else 2300
    max_half = 4 if n < 250 else 3

    for _ in range(rounds):
        if time.monotonic() > deadline:
            break
        table = {}
        for _ in range(table_cap):
            a = random_combo(rng, cols, max_half)
            syn = combo_syndrome(a, cols)
            old = table.get(syn)
            if old is None or a.bit_count() < old.bit_count():
                table[syn] = a

        for _ in range(probe_cap):
            if time.monotonic() > deadline:
                break
            b = random_combo(rng, cols, max_half)
            a = table.get(combo_syndrome(b, cols))
            if a is None:
                continue
            v = a ^ b
            w = v.bit_count()
            if 0 < w < best_w and verified_logical(v, check_rows, stab_basis):
                best = v
                best_w = w
    return best


def combo_syndrome(v, cols):
    syn = 0
    x = v
    while x:
        lsb = x & -x
        c = lsb.bit_length() - 1
        syn ^= cols[c]
        x ^= lsb
    return syn


def quotient_fallback(check_rows, stab_basis, n, rng):
    kb = kernel_basis(check_rows, n)
    best = None
    best_w = n + 1

    for v in kb:
        if verified_logical(v, check_rows, stab_basis):
            w = v.bit_count()
            if w < best_w:
                best, best_w = v, w

    # Some logical directions are sums of nullspace basis vectors even when each
    # single basis vector reduces into the stabilizer span.
    acc = 0
    order = list(kb)
    rng.shuffle(order)
    for v in order:
        acc ^= v
        if verified_logical(acc, check_rows, stab_basis):
            if acc.bit_count() < best_w:
                best, best_w = acc, acc.bit_count()
            break
    return best


def stabilize_descent(v, check_rows, stabilizer_rows, stabilizer_basis, rng, deadline):
    if v is None:
        return None
    best = v
    rows = [r for r in stabilizer_rows if r]
    if not rows:
        return best
    row_weights = {r: r.bit_count() for r in rows}
    passes = 0
    while passes < 24 and time.monotonic() <= deadline:
        passes += 1
        changed = False
        rng.shuffle(rows)
        for s in rows:
            cand = best ^ s
            if cand.bit_count() < best.bit_count() and verified_logical(cand, check_rows, stabilizer_basis):
                best = cand
                changed = True
        if not changed:
            # Try a few paired stabilizer moves, prioritizing sparse rows.
            sparse = sorted(rows, key=lambda r: (row_weights[r], rng.random()))[: min(len(rows), 80)]
            for _ in range(min(300, len(sparse) * 8)):
                a = rng.choice(sparse)
                b = rng.choice(sparse)
                cand = best ^ a ^ b
                if cand.bit_count() < best.bit_count() and verified_logical(cand, check_rows, stabilizer_basis):
                    best = cand
                    changed = True
                    break
        if not changed:
            break
    return best


def solve_basis(name, check_rows, stabilizer_rows, n, rng, deadline):
    stab_basis = build_rref(stabilizer_rows)
    candidates = []
    mitm = remit_search(check_rows, stab_basis, n, rng, deadline)
    if mitm is not None:
        candidates.append(mitm)
    fb = quotient_fallback(check_rows, stab_basis, n, rng)
    if fb is not None:
        candidates.append(fb)

    best = None
    for v in candidates:
        v = stabilize_descent(v, check_rows, stabilizer_rows, stab_basis, rng, deadline)
        if verified_logical(v, check_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v
    return name, best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    hx_rows, nx = load_css_matrix(args.hx)
    hz_rows, nz = load_css_matrix(args.hz)
    n = max(nx, nz)
    hx_rows = [r & ((1 << n) - 1) for r in hx_rows]
    hz_rows = [r & ((1 << n) - 1) for r in hz_rows]
    os.makedirs(args.output_dir, exist_ok=True)

    deadline = time.monotonic() + 28.0
    found = []
    found.append(solve_basis("x", hz_rows, hx_rows, n, rng, deadline))
    found.append(solve_basis("z", hx_rows, hz_rows, n, rng, deadline))
    found = [(b, v) for b, v in found if v is not None]

    if found:
        basis, vec = min(found, key=lambda item: (item[1].bit_count(), 0 if item[0] == "x" else 1))
        result = {
            "status": "completed",
            "basis": basis,
            "vector": int_to_vector(vec, n),
            "upper_bound": int(vec.bit_count()),
        }
    else:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
