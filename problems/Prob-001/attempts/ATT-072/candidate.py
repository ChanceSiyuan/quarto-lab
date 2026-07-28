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
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows") or []:
            x = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    x |= 1 << c
                    if c + 1 > n:
                        n = c + 1
            rows.append(x)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def mask_n(n):
    return (1 << n) - 1 if n > 0 else 0


def bit_to_list(x, n):
    return [(x >> i) & 1 for i in range(n)]


def row_reduce(rows, n):
    a = [r & mask_n(n) for r in rows if r & mask_n(n)]
    rank = 0
    pivots = []
    m = len(a)
    for col in range(n):
        pivot = None
        bit = 1 << col
        for r in range(rank, m):
            if a[r] & bit:
                pivot = r
                break
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        for r in range(m):
            if r != rank and (a[r] & bit):
                a[r] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == m:
            break
    return a[:rank], pivots


def rank_of(rows, n):
    return len(row_reduce(rows, n)[0])


def xor_basis(rows, n):
    basis = {}
    full = mask_n(n)
    for r in rows:
        x = r & full
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def reduce_with_xor_basis(v, basis):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def add_to_xor_basis(v, basis):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def in_row_space(v, rows, n):
    if v == 0:
        return True
    return reduce_with_xor_basis(v & mask_n(n), xor_basis(rows, n)) == 0


def kernel_basis(check_rows, n):
    rref, pivots = row_reduce(check_rows, n)
    pivot_set = set(pivots)
    basis = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, pivot in zip(rref, pivots):
            if row & (1 << free):
                v |= 1 << pivot
        basis.append(v & mask_n(n))
    return basis


def commutes_with_all(v, check_rows):
    return all(((v & r).bit_count() & 1) == 0 for r in check_rows)


def verified(v, check_rows, stabilizer_rows, n):
    v &= mask_n(n)
    return v != 0 and commutes_with_all(v, check_rows) and not in_row_space(v, stabilizer_rows, n)


def logical_basis(check_rows, stabilizer_rows, n):
    selected = []
    span_basis = xor_basis(stabilizer_rows, n)
    for v in sorted(kernel_basis(check_rows, n), key=lambda z: (z.bit_count(), z)):
        if add_to_xor_basis(v, span_basis):
            selected.append(v)
    return selected


def column_scores(check_rows, stabilizer_rows, n, rng):
    cd = [0] * n
    sd = [0] * n
    for r in check_rows:
        x = r
        while x:
            lsb = x & -x
            cd[lsb.bit_length() - 1] += 1
            x ^= lsb
    for r in stabilizer_rows:
        x = r
        while x:
            lsb = x & -x
            sd[lsb.bit_length() - 1] += 1
            x ^= lsb
    rel = [1.0 + cd[i] + 0.35 * sd[i] + rng.random() * 0.25 for i in range(n)]
    # A small BP-style smoothing pass: variables sharing checks inherit some
    # reliability from their local parity neighborhoods.
    for _ in range(3):
        nxt = rel[:]
        for r in check_rows:
            cols = []
            x = r
            while x:
                lsb = x & -x
                cols.append(lsb.bit_length() - 1)
                x ^= lsb
            if not cols:
                continue
            avg = sum(rel[c] for c in cols) / len(cols)
            for c in cols:
                nxt[c] = 0.82 * nxt[c] + 0.18 * avg
        rel = nxt
    return rel


def reduce_by_stabilizers(v, stabilizer_rows, n, rng, rel=None, rounds=600):
    rows = [r & mask_n(n) for r in stabilizer_rows if r & mask_n(n)]
    if not rows:
        return v & mask_n(n)
    best = cur = v & mask_n(n)
    best_w = cur.bit_count()
    weights = []
    for r in rows:
        bias = 0.0
        if rel is not None:
            x = r
            while x:
                lsb = x & -x
                bias += 1.0 / max(rel[lsb.bit_length() - 1], 1e-6)
                x ^= lsb
        weights.append(bias + 1e-6)
    temp0 = 1.5
    stale = 0
    for step in range(rounds):
        cur_w = cur.bit_count()
        improving = []
        best_delta = 10 ** 9
        order = list(range(len(rows)))
        rng.shuffle(order)
        sample = order if len(order) <= 256 else order[:256]
        for idx in sample:
            r = rows[idx]
            delta = r.bit_count() - 2 * ((cur & r).bit_count())
            if delta < best_delta:
                best_delta = delta
                improving = [idx]
            elif delta == best_delta:
                improving.append(idx)
        if best_delta < 0:
            idx = rng.choice(improving)
            cur ^= rows[idx]
            stale = 0
        else:
            stale += 1
            if stale > 35:
                # Reliability-biased restart inside the same coset.
                cur = best
                for _ in range(1 + rng.randrange(4)):
                    idx = weighted_choice(weights, rng)
                    cur ^= rows[idx]
                stale = 0
            else:
                idx = weighted_choice(weights, rng)
                cand = cur ^ rows[idx]
                delta = cand.bit_count() - cur_w
                temp = temp0 / (1.0 + step / 80.0)
                if delta <= 0 or rng.random() < pow(2.718281828, -delta / max(temp, 1e-6)):
                    cur = cand
        cw = cur.bit_count()
        if cw < best_w:
            best = cur
            best_w = cw
    # Final deterministic descent over all stabilizers.
    cur = best
    changed = True
    while changed:
        changed = False
        for r in sorted(rows, key=lambda z: z.bit_count()):
            if (cur ^ r).bit_count() < cur.bit_count():
                cur ^= r
                changed = True
                if cur.bit_count() < best_w:
                    best = cur
                    best_w = cur.bit_count()
    return best & mask_n(n)


def weighted_choice(weights, rng):
    total = sum(weights)
    if total <= 0:
        return rng.randrange(len(weights))
    t = rng.random() * total
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if acc >= t:
            return i
    return len(weights) - 1


def random_kernel_sample(kbasis, rel, rng):
    if not kbasis:
        return 0
    n = len(rel)
    score = []
    for v in kbasis:
        s = 0.0
        x = v
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c < n:
                s += 1.0 / max(rel[c], 1e-6)
            x ^= lsb
        score.append(s + 1e-6)
    v = 0
    # Heavy-tailed number of free directions, biased toward unreliable columns.
    draws = 1 + int(rng.expovariate(0.45))
    for _ in range(min(draws, max(1, len(kbasis)))):
        v ^= kbasis[weighted_choice(score, rng)]
    if v == 0:
        v = rng.choice(kbasis)
    return v


def search_basis(name, check_rows, stabilizer_rows, n, seed):
    rng = random.Random(seed)
    rel = column_scores(check_rows, stabilizer_rows, n, rng)
    kbasis = kernel_basis(check_rows, n)
    lbasis = logical_basis(check_rows, stabilizer_rows, n)
    if not lbasis:
        return None
    stab_basis = xor_basis(stabilizer_rows, n)
    best = None
    deadline = time.time() + 8.0

    def verified_fast(v):
        v &= mask_n(n)
        return v != 0 and commutes_with_all(v, check_rows) and reduce_with_xor_basis(v, stab_basis) != 0

    def consider(v, rounds=500):
        nonlocal best
        v = reduce_by_stabilizers(v, stabilizer_rows, n, rng, rel, rounds)
        if verified_fast(v):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for v in lbasis:
        consider(v, 900)
    # Reliability-ordered randomized restarts: sample kernel vectors, keep only
    # non-stabilizer cosets, then minimize within the stabilizer coset.
    restarts = 450 if n < 300 else 220
    for i in range(restarts):
        if time.time() > deadline:
            break
        if i % 3 == 0:
            v = 0
            for b in lbasis:
                if rng.random() < 0.5:
                    v ^= b
            if v == 0:
                v = rng.choice(lbasis)
            if kbasis and rng.random() < 0.35:
                v ^= random_kernel_sample(kbasis, rel, rng)
        else:
            v = random_kernel_sample(kbasis, rel, rng)
        if verified_fast(v):
            consider(v, 240)

    # Reliable fallback: every independent quotient-basis element is a valid
    # logical coset representative; return the best verified reduced one.
    if best is None:
        for v in lbasis:
            vv = reduce_by_stabilizers(v, stabilizer_rows, n, rng, rel, 120)
            if verified_fast(vv):
                best = vv if best is None or vv.bit_count() < best.bit_count() else best
    return (name, best) if best is not None else None


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
        hx = [r & mask_n(n) for r in hx]
        hz = [r & mask_n(n) for r in hz]
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
        candidates = []
        sx = search_basis("x", hz, hx, n, (args.seed << 1) ^ 0x58A5)
        sz = search_basis("z", hx, hz, n, (args.seed << 1) ^ 0xA35D)
        if sx is not None:
            candidates.append(sx)
        if sz is not None:
            candidates.append(sz)
        if candidates:
            basis, vec = min(candidates, key=lambda t: (t[1].bit_count(), 0 if t[0] == "x" else 1))
            out = {
                "status": "completed",
                "basis": basis,
                "vector": bit_to_list(vec, n),
                "upper_bound": int(vec.bit_count()),
            }
        else:
            out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
