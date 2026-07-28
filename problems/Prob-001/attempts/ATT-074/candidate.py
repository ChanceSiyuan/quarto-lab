#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def _row_to_int(row):
    x = 0
    for i, b in enumerate(row):
        if int(b) & 1:
            x |= 1 << i
    return x


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        return [_row_to_int(r) for r in obj], n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or row list")

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            x = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    x |= 1 << c
                    if c + 1 > n:
                        n = c + 1
            rows.append(x)
        return rows, n

    if "data" in obj:
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        data = obj.get("data", [])
        if data and isinstance(data[0], list):
            if n == 0:
                n = max((len(r) for r in data), default=0)
            return [_row_to_int(r) for r in data], n
        if n <= 0:
            raise ValueError("dense_binary_matrix requires n_cols")
        rows = []
        for i in range(0, len(data), n):
            rows.append(_row_to_int(data[i:i + n]))
        return rows, n

    raise ValueError("unrecognized matrix format")


def mask_n(x, n):
    if n <= 0:
        return 0
    return x & ((1 << n) - 1)


def build_basis(rows):
    basis = {}
    for r in rows:
        x = int(r)
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                for q, y in list(basis.items()):
                    if q != p and ((y >> p) & 1):
                        basis[q] = y ^ x
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


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    rb = build_basis(mask_n(r, n) for r in rows if mask_n(r, n))
    pivots = set(rb)
    out = []
    for j in range(n):
        if j in pivots:
            continue
        v = 1 << j
        for p, row in rb.items():
            if (row >> j) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_bits(v, checks):
    s = 0
    for i, r in enumerate(checks):
        if ((v & r).bit_count() & 1):
            s |= 1 << i
    return s


def verified(v, kernel_rows, stab_basis):
    return v != 0 and syndrome_bits(v, kernel_rows) == 0 and not in_span(v, stab_basis)


def vector_list(v, n):
    return [int((v >> i) & 1) for i in range(n)]


def incidence(rows, n):
    col_checks = [[] for _ in range(n)]
    check_cols = []
    for i, r in enumerate(rows):
        cols = []
        x = r
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c < n:
                cols.append(c)
                col_checks[c].append(i)
            x ^= lsb
        check_cols.append(cols)
    return col_checks, check_cols


def random_cycle_seed(rng, col_checks, check_cols, n):
    if n == 0:
        return 0
    start = rng.randrange(n)
    col = start
    prev_check = -1
    seen = {col: 0}
    path = [col]
    max_steps = min(max(16, 3 * n), 600)
    for step in range(1, max_steps + 1):
        checks = [c for c in col_checks[col] if c != prev_check]
        if not checks:
            col = rng.randrange(n)
            prev_check = -1
            if col not in seen:
                seen[col] = len(path)
                path.append(col)
            continue
        chk = rng.choice(checks)
        cols = check_cols[chk]
        if len(cols) < 2:
            prev_check = chk
            continue
        nxt = rng.choice(cols)
        for _ in range(4):
            if nxt != col:
                break
            nxt = rng.choice(cols)
        if nxt == col:
            prev_check = chk
            continue
        col = nxt
        prev_check = chk
        if col in seen:
            seed = 0
            for c in path[seen[col]:]:
                seed ^= 1 << c
            if seed:
                return seed
        seen[col] = len(path)
        path.append(col)
    return 1 << start


def repair_to_kernel(seed, kernel_rows, col_checks, check_cols, n, rng, deadline):
    v = mask_n(seed, n)
    syn = syndrome_bits(v, kernel_rows)
    if syn == 0:
        return v
    best_v = v
    best_s = syn.bit_count()
    max_iter = max(80, 14 * max(1, n))
    for t in range(max_iter):
        if time.time() > deadline:
            break
        sw = syn.bit_count()
        if sw == 0:
            return v
        if sw < best_s:
            best_s = sw
            best_v = v

        pool = set()
        y = syn
        unsat = []
        while y:
            lsb = y & -y
            chk = lsb.bit_length() - 1
            unsat.append(chk)
            y ^= lsb
        rng.shuffle(unsat)
        for chk in unsat[:10]:
            cols = check_cols[chk]
            if len(cols) <= 32:
                pool.update(cols)
            elif cols:
                for _ in range(32):
                    pool.add(rng.choice(cols))
        for _ in range(8):
            pool.add(rng.randrange(n))

        best_cols = []
        best_delta = 10 ** 9
        for c in pool:
            deg = len(col_checks[c])
            hit = 0
            for chk in col_checks[c]:
                hit += (syn >> chk) & 1
            delta = deg - 2 * hit
            if delta < best_delta:
                best_delta = delta
                best_cols = [c]
            elif delta == best_delta:
                best_cols.append(c)

        if not best_cols:
            c = rng.randrange(n)
        elif best_delta < 0 or rng.random() < 0.08 / (1.0 + t / 60.0):
            c = rng.choice(best_cols)
        else:
            c = rng.choice(tuple(pool))
        v ^= 1 << c
        for chk in col_checks[c]:
            syn ^= 1 << chk
    return best_v if syndrome_bits(best_v, kernel_rows) == 0 else 0


def shrink_by_stabilizers(v, kernel_rows, stab_rows, stab_basis, rng, deadline):
    if not verified(v, kernel_rows, stab_basis):
        return 0
    rows = [r for r in stab_rows if r]
    rows.sort(key=lambda r: r.bit_count())
    best = v
    improved = True
    while improved and time.time() <= deadline:
        improved = False
        rng.shuffle(rows)
        rows.sort(key=lambda r: (r & best).bit_count() - ((r & ~best).bit_count()), reverse=True)
        for r in rows[: min(len(rows), 4000)]:
            u = best ^ r
            if u.bit_count() < best.bit_count() and verified(u, kernel_rows, stab_basis):
                best = u
                improved = True
    return best


def fallback_logical(kernel_rows, stab_rows, n, rng):
    ns = nullspace_basis(kernel_rows, n)
    stab_basis = build_basis(stab_rows)
    rng.shuffle(ns)
    for v in ns:
        v = mask_n(v, n)
        if verified(v, kernel_rows, stab_basis):
            return v
    span = list(ns)
    for _ in range(min(2000, 80 * max(1, len(span)))):
        v = 0
        for b in span:
            if rng.random() < 0.35:
                v ^= b
        if verified(v, kernel_rows, stab_basis):
            return v
    return 0


def search_basis(kernel_rows, stab_rows, n, seed, seconds):
    rng = random.Random(seed)
    kernel_rows = [mask_n(r, n) for r in kernel_rows]
    stab_rows = [mask_n(r, n) for r in stab_rows]
    stab_basis = build_basis(stab_rows)
    col_checks, check_cols = incidence(kernel_rows, n)
    deadline = time.time() + seconds

    best = 0
    base = fallback_logical(kernel_rows, stab_rows, n, rng)
    if base:
        best = shrink_by_stabilizers(base, kernel_rows, stab_rows, stab_basis, rng, deadline)

    ns = nullspace_basis(kernel_rows, n)
    attempts = 0
    while time.time() < deadline and attempts < max(60, 5 * max(1, n)):
        attempts += 1
        if attempts % 5 == 0 and ns:
            v = 0
            for b in ns:
                p = 0.18 if best == 0 else min(0.5, max(0.05, best.bit_count() / max(1, n)))
                if rng.random() < p:
                    v ^= b
        else:
            seed_v = random_cycle_seed(rng, col_checks, check_cols, n)
            if rng.random() < 0.5:
                for _ in range(rng.randrange(1, 5)):
                    seed_v ^= 1 << rng.randrange(n)
            v = repair_to_kernel(seed_v, kernel_rows, col_checks, check_cols, n, rng, deadline)
        if not verified(v, kernel_rows, stab_basis):
            if base and rng.random() < 0.5:
                v ^= base
            if not verified(v, kernel_rows, stab_basis):
                continue
        v = shrink_by_stabilizers(v, kernel_rows, stab_rows, stab_basis, rng, deadline)
        if v and (best == 0 or v.bit_count() < best.bit_count()):
            best = v
    return best if verified(best, kernel_rows, stab_basis) else 0


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
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        budget = 7.5
        x = search_basis(hz, hx, n, args.seed ^ 0x58A5C1C3, budget / 2.0)
        z = search_basis(hx, hz, n, args.seed ^ 0xA73D9B17, budget / 2.0)
        choices = []
        if x:
            choices.append(("x", x))
        if z:
            choices.append(("z", z))
        if choices:
            basis, v = min(choices, key=lambda item: item[1].bit_count())
            out = {
                "status": "completed",
                "basis": basis,
                "vector": vector_list(v, n),
                "upper_bound": int(v.bit_count()),
            }
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
