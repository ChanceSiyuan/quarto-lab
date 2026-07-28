#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def fail():
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))


def read_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            mask = 0
            for i, v in enumerate(r):
                if int(v) & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            mask = 0
            for i, v in enumerate(r[:n]):
                if int(v) & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n

    if "rows" in obj:
        data = obj["rows"]
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = 1 + max((int(c) for r in data for c in r), default=-1)
        rows = []
        for r in data:
            mask = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    mask ^= 1 << c
            rows.append(mask)
        return rows, n

    raise ValueError("unknown matrix format")


def rank_basis(rows):
    basis = {}
    for x in rows:
        x = int(x)
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
    rows = [int(r) & ((1 << n) - 1) for r in rows if int(r)]
    pivots = []
    r = 0
    for c in range(n):
        pivot = None
        bit = 1 << c
        for i in range(r, len(rows)):
            if rows[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        rows[r], rows[pivot] = rows[pivot], rows[r]
        for i in range(len(rows)):
            if i != r and (rows[i] & bit):
                rows[i] ^= rows[r]
        pivots.append(c)
        r += 1
        if r == len(rows):
            break
    return rows[:r], pivots


def kernel_basis(rows, n):
    rr, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    out = []
    for f in free_cols:
        v = 1 << f
        for row, p in zip(rr, pivots):
            if row & (1 << f):
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, checks):
    for r in checks:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def vector_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def column_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        x = r
        while x:
            lsb = x & -x
            deg[lsb.bit_length() - 1] += 1
            x ^= lsb
    return deg


def weighted_sample_without_replacement(rng, weights, k):
    k = min(k, len(weights))
    keys = []
    for i, w in enumerate(weights):
        w = max(float(w), 1e-9)
        keys.append((rng.random() ** (1.0 / w), i))
    keys.sort(reverse=True)
    return [i for _, i in keys[:k]]


def compress_rows(rows, active, pos):
    out = []
    active_mask = 0
    for c in active:
        active_mask |= 1 << c
    for r in rows:
        x = r & active_mask
        y = 0
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            y |= 1 << pos[c]
            x ^= lsb
        out.append(y)
    return out


def lift_vector(v, active):
    out = 0
    x = v
    while x:
        lsb = x & -x
        out |= 1 << active[lsb.bit_length() - 1]
        x ^= lsb
    return out


def random_kernel_combo(rng, basis, max_terms=None):
    if not basis:
        return 0
    if max_terms is None:
        max_terms = max(1, min(len(basis), 1 + int(rng.expovariate(0.35))))
    v = 0
    for i in rng.sample(range(len(basis)), min(max_terms, len(basis))):
        v ^= basis[i]
    return v


def minimize_by_stabilizers(v, stabilizer_rows, rng, passes=6):
    if not v:
        return v
    rows = [r for r in stabilizer_rows if r]
    if not rows:
        return v
    best = v
    best_w = v.bit_count()

    ordered = sorted(rows, key=lambda r: r.bit_count())
    for _ in range(2):
        changed = False
        for r in ordered:
            u = v ^ r
            if u.bit_count() < v.bit_count():
                v = u
                changed = True
        if not changed:
            break
    if v.bit_count() < best_w:
        best, best_w = v, v.bit_count()

    for _ in range(passes):
        rng.shuffle(rows)
        temp = best
        for r in rows:
            u = temp ^ r
            uw = u.bit_count()
            tw = temp.bit_count()
            if uw < tw or (uw == tw and rng.random() < 0.03):
                temp = u
        tw = temp.bit_count()
        if temp and tw < best_w:
            best, best_w = temp, tw
    return best


def verified_candidate(v, n, check_rows, stab_basis):
    if v == 0:
        return False
    v &= (1 << n) - 1
    return syndrome_zero(v, check_rows) and not in_rowspace(v, stab_basis)


def search_one(label, check_rows, stabilizer_rows, n, rng, deadline):
    stab_basis = rank_basis(stabilizer_rows)
    best = None

    def submit(v):
        nonlocal best
        if not v:
            return
        v &= (1 << n) - 1
        if not syndrome_zero(v, check_rows):
            return
        v = minimize_by_stabilizers(v, stabilizer_rows, rng, passes=4)
        if verified_candidate(v, n, check_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    deg = column_degrees(check_rows, n)
    weights = [1.0 / (1.0 + d) for d in deg]
    zero_cols = [i for i, d in enumerate(deg) if d == 0]
    for c in zero_cols:
        submit(1 << c)

    # Random projection stage: sample coordinate windows, solve the projected
    # kernel exactly inside that window, then lift those projected vectors.
    rounds = max(80, min(700, 10 * n + 80))
    for t in range(rounds):
        if time.monotonic() > deadline:
            break
        if n == 0:
            break
        base = 4 + (t % 11) * 2
        span = max(1, min(n, base + int(rng.random() * max(1, n // 3 + 1))))
        if rng.random() < 0.18:
            span = min(n, max(1, int(rng.triangular(1, n, max(1, n // 5)))))
        active = weighted_sample_without_replacement(rng, weights, span)
        if zero_cols and rng.random() < 0.35:
            active = list(dict.fromkeys(rng.sample(zero_cols, min(len(zero_cols), max(1, span // 4))) + active))[:span]
        active.sort()
        pos = {c: i for i, c in enumerate(active)}
        proj = compress_rows(check_rows, active, pos)
        kb = kernel_basis(proj, len(active))
        if not kb:
            continue
        kb.sort(key=lambda x: x.bit_count())
        for b in kb[: min(8, len(kb))]:
            submit(lift_vector(b, active))
        for _ in range(min(10, 2 + len(kb))):
            submit(lift_vector(random_kernel_combo(rng, kb, max_terms=min(len(kb), 1 + rng.randrange(1, 5))), active))

    # Global kernel-lifting stage: combine nullspace generators sparsely and
    # reduce within the stabilizer coset. This is a witness search, not a
    # distance proof.
    kb_global = kernel_basis(check_rows, n)
    kb_global.sort(key=lambda x: (x.bit_count(), rng.random()))
    for b in kb_global[: min(80, len(kb_global))]:
        submit(b)
    for _ in range(max(80, min(600, 8 * len(kb_global) + 40))):
        if time.monotonic() > deadline:
            break
        terms = 1 + int(rng.expovariate(0.45))
        submit(random_kernel_combo(rng, kb_global, max_terms=min(len(kb_global), terms)))

    # Reliable basis-derived fallback for positive-k inputs.
    for b in kb_global:
        if verified_candidate(b, n, check_rows, stab_basis):
            submit(b)
            break

    return (label, best) if best is not None else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    try:
        hx, nx = read_matrix(args.hx)
        hz, nz = read_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        rng = random.Random(args.seed)
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        deadline = time.monotonic() + 25.0
        candidates = []
        sx = search_one("x", hz, hx, n, random.Random(rng.randrange(1 << 62)), deadline)
        if sx is not None:
            candidates.append(sx)
        sz = search_one("z", hx, hz, n, random.Random(rng.randrange(1 << 62)), deadline)
        if sz is not None:
            candidates.append(sz)

        if not candidates:
            fail()
            return

        basis, v = min(candidates, key=lambda item: (item[1].bit_count(), 0 if item[0] == "x" else 1))
        result = {
            "status": "completed",
            "basis": basis,
            "vector": vector_list(v, n),
            "upper_bound": int(v.bit_count()),
        }
        print(json.dumps(result, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
