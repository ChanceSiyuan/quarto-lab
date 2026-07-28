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
    if isinstance(obj, list):
        n_cols = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n_cols
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj.get("data", [])
        n_cols = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n_cols
    if "rows" in obj:
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            x = 0
            for c in r:
                ci = int(c)
                if 0 <= ci < n_cols:
                    x |= 1 << ci
            rows.append(x)
        return rows, n_cols
    raise ValueError("unsupported matrix JSON format")


def mask_n(n):
    return (1 << n) - 1 if n > 0 else 0


def rref_basis(rows, n):
    basis = {}
    for row in rows:
        x = row & mask_n(n)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        bp = basis[p]
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= bp
    return dict(sorted(basis.items(), reverse=True))


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return y
        y ^= b
    return 0


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    rb = rref_basis(rows, n)
    pivots = set(rb)
    free = [i for i in range(n) if i not in pivots]
    out = []
    for f in free:
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def quotient_logical_basis(kernel_basis, stab_rows, n):
    stab_basis = rref_basis(stab_rows, n)
    span = dict(stab_basis)
    logicals = []
    for v in sorted(kernel_basis, key=lambda z: (z.bit_count(), z)):
        r = reduce_by_basis(v, span)
        if r:
            logicals.append(v)
            p = r.bit_length() - 1
            span[p] = r
            # Keep the growing quotient reducer close to row echelon form.
            for q in list(span):
                if q != p and ((span[q] >> p) & 1):
                    span[q] ^= r
    return logicals, stab_basis


def mat_vec_zero(check_rows, v):
    for r in check_rows:
        if ((r & v).bit_count() & 1) != 0:
            return False
    return True


def verified(v, check_rows, stab_basis):
    return v != 0 and mat_vec_zero(check_rows, v) and not in_span(v, stab_basis)


def row_weights(rows):
    return [r.bit_count() for r in rows]


def greedy_stabilizer_descent(v, stab_rows, rng, passes=4):
    cur = v
    rows = [r for r in stab_rows if r]
    rows.sort(key=lambda r: (r.bit_count(), r))
    if len(rows) > 256:
        rows = rows[:128] + rng.sample(rows[128:], min(128, len(rows) - 128))
    for _ in range(passes):
        changed = False
        if rows:
            start = rng.randrange(len(rows))
            order = rows[start:] + rows[:start]
        else:
            order = rows
        for r in order:
            w0 = cur.bit_count()
            nxt = cur ^ r
            if nxt.bit_count() < w0:
                cur = nxt
                changed = True
        if not changed:
            break
    return cur


def stochastic_coset_minimize(v, stab_rows, check_rows, stab_basis, rng, deadline, max_steps=900):
    best = greedy_stabilizer_descent(v, stab_rows, rng, passes=6)
    if not verified(best, check_rows, stab_basis):
        best = v
    rows = [r for r in stab_rows if r]
    if not rows or best.bit_count() <= 1:
        return best
    rows.sort(key=lambda r: r.bit_count())
    light = rows[: min(len(rows), 96)]
    all_rows = rows[: min(len(rows), 512)]
    temp = max(1.0, best.bit_count() / 2.0)
    cur = best
    steps = 0
    while time.monotonic() < deadline and steps < max_steps:
        pool = light if rng.random() < 0.72 else all_rows
        trial = cur
        flips = 1
        if rng.random() < 0.20:
            flips += rng.randrange(1, 4)
        for _ in range(flips):
            trial ^= rng.choice(pool)
        trial = greedy_stabilizer_descent(trial, pool, rng, passes=2)
        dw = trial.bit_count() - cur.bit_count()
        if dw <= 0 or rng.random() < pow(2.718281828459045, -dw / max(0.25, temp)):
            cur = trial
        if verified(cur, check_rows, stab_basis) and cur.bit_count() < best.bit_count():
            best = cur
            if best.bit_count() <= 1:
                return best
        temp *= 0.9992
        if temp < 0.35:
            temp = max(0.35, best.bit_count() / 12.0)
            cur = best
        steps += 1
    return best


def low_weight_kernel_words(check_rows, n, rng, budget):
    # Random quotient projections: eliminate a shuffled pivot set and lift
    # sparse assignments on the remaining variables into the kernel.
    words = []
    rows = [r & mask_n(n) for r in check_rows if r]
    for _ in range(budget):
        perm = list(range(n))
        rng.shuffle(perm)
        inv = [0] * n
        for i, c in enumerate(perm):
            inv[c] = i
        prow = []
        for r in rows:
            x = 0
            y = r
            while y:
                lsb = y & -y
                c = lsb.bit_length() - 1
                x |= 1 << inv[c]
                y ^= lsb
            prow.append(x)
        rb = rref_basis(prow, n)
        free = [i for i in range(n) if i not in rb]
        if not free:
            continue
        picks = []
        for _j in range(4):
            k = 1 if rng.random() < 0.65 else 2 + rng.randrange(min(4, len(free)))
            fs = rng.sample(free, min(k, len(free)))
            z = 0
            for f in fs:
                z |= 1 << f
            for p, row in rb.items():
                if (row & z).bit_count() & 1:
                    z |= 1 << p
            v = 0
            y = z
            while y:
                lsb = y & -y
                pc = lsb.bit_length() - 1
                v |= 1 << perm[pc]
                y ^= lsb
            if v:
                picks.append(v)
        words.extend(picks)
    return words


def search_side(name, check_rows, stab_rows, n, rng, deadline):
    kb = nullspace_basis(check_rows, n)
    logicals, stab_basis = quotient_logical_basis(kb, stab_rows, n)
    if not logicals:
        return None

    candidates = []
    candidates.extend(logicals)
    for i, a in enumerate(logicals[:96]):
        candidates.append(a)
        for b in logicals[i + 1 : min(len(logicals), i + 17)]:
            if rng.random() < 0.45:
                candidates.append(a ^ b)

    best = None
    for v in candidates:
        if time.monotonic() >= deadline:
            break
        m = stochastic_coset_minimize(v, stab_rows, check_rows, stab_basis, rng, deadline)
        if verified(m, check_rows, stab_basis) and (best is None or m.bit_count() < best.bit_count()):
            best = m
            if best.bit_count() <= 1:
                return name, best

    # Required theme: sample the kernel quotient stochastically, then minimize
    # within each stabilizer coset.
    attempts = 0
    while time.monotonic() < deadline and attempts < 600:
        attempts += 1
        v = 0
        ordered = sorted(logicals, key=lambda z: z.bit_count())
        for g in ordered[: min(len(ordered), 160)]:
            p = 0.18
            if g.bit_count() <= (best.bit_count() if best else n + 1):
                p = 0.35
            if rng.random() < p:
                v ^= g
        if v == 0:
            v = rng.choice(logicals)
        m = stochastic_coset_minimize(v, stab_rows, check_rows, stab_basis, rng, deadline, max_steps=350)
        if verified(m, check_rows, stab_basis) and (best is None or m.bit_count() < best.bit_count()):
            best = m
            if best.bit_count() <= 1:
                return name, best

    if time.monotonic() < deadline:
        proj_budget = 8 if n > 256 else 16
        for v in low_weight_kernel_words(check_rows, n, rng, proj_budget):
            if time.monotonic() >= deadline:
                break
            if in_span(v, stab_basis):
                continue
            m = stochastic_coset_minimize(v, stab_rows, check_rows, stab_basis, rng, deadline, max_steps=450)
            if verified(m, check_rows, stab_basis) and (best is None or m.bit_count() < best.bit_count()):
                best = m
                if best.bit_count() <= 1:
                    return name, best

    if best is None:
        # Reliable fallback for positive-k inputs: the first quotient basis
        # vector is already in the kernel and outside the stabilizer span.
        for v in logicals:
            if verified(v, check_rows, stab_basis):
                best = greedy_stabilizer_descent(v, stab_rows, rng, passes=8)
                if not verified(best, check_rows, stab_basis):
                    best = v
                break
    if best is None:
        return None
    return name, best


def int_to_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & mask_n(n) for r in hx]
    hz = [r & mask_n(n) for r in hz]
    os.makedirs(args.output_dir, exist_ok=True)

    deadline = time.monotonic() + 25.0
    sides = [("x", hz, hx), ("z", hx, hz)]
    if rng.random() < 0.5:
        sides.reverse()

    best = None
    for name, check, stab in sides:
        side_deadline = min(deadline, time.monotonic() + 12.0)
        res = search_side(name, check, stab, n, rng, side_deadline)
        if res is not None:
            if best is None or res[1].bit_count() < best[1].bit_count():
                best = res

    if best is None:
        result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    else:
        basis, vec = best
        result = {
            "status": "completed",
            "basis": basis,
            "vector": int_to_bits(vec, n),
            "upper_bound": int(vec.bit_count()),
        }
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))
        sys.exit(0)
