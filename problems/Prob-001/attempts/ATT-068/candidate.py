#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def fail():
    print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", 0))
        if n <= 0 and data:
            n = max(len(r) for r in data)
        rows = []
        for r in data:
            v = 0
            for j, bit in enumerate(r):
                if bit & 1:
                    v |= 1 << j
            rows.append(v)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for cols in obj["rows"]:
            v = 0
            for c in cols:
                c = int(c)
                if c >= 0:
                    v |= 1 << c
                    if c + 1 > n:
                        n = c + 1
            rows.append(v)
        return rows, n

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            v = 0
            for j, bit in enumerate(r):
                if bit & 1:
                    v |= 1 << j
            rows.append(v)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def trim_rows(rows, n):
    mask = (1 << n) - 1 if n > 0 else 0
    return [r & mask for r in rows if (r & mask) != 0]


def rref(rows, n):
    basis = {}
    mask = (1 << n) - 1 if n > 0 else 0
    for row in rows:
        x = row & mask
        while True:
            changed = False
            for p in sorted(basis):
                if (x >> p) & 1:
                    x ^= basis[p]
                    changed = True
            if not changed:
                break
        if x:
            p = (x & -x).bit_length() - 1
            basis[p] = x
            for q, y in list(basis.items()):
                if q != p and ((y >> p) & 1):
                    basis[q] = y ^ x
    pivots = sorted(basis)
    return pivots, [basis[p] for p in pivots]


def reduce_with(v, pivots, basis_rows):
    x = v
    for p, row in zip(pivots, basis_rows):
        if (x >> p) & 1:
            x ^= row
    return x


def nullspace_basis(rows, n):
    pivots, rb = rref(rows, n)
    pivot_set = set(pivots)
    out = []
    for f in range(n):
        if f in pivot_set:
            continue
        v = 1 << f
        for p, row in zip(pivots, rb):
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def in_kernel(v, check_rows):
    for row in check_rows:
        if ((row & v).bit_count() & 1) != 0:
            return False
    return True


def verified(v, check_rows, stab_pivots, stab_rref_rows):
    return v != 0 and in_kernel(v, check_rows) and reduce_with(v, stab_pivots, stab_rref_rows) != 0


def quotient_logicals(check_rows, stab_rows, n):
    ns = nullspace_basis(check_rows, n)
    sp, sr = rref(stab_rows, n)
    span_rows = list(sr)
    span_pivots = list(sp)
    logicals = []
    for v in ns:
        rem_s = reduce_with(v, sp, sr)
        if rem_s == 0:
            continue
        rem_all = reduce_with(rem_s, span_pivots, span_rows)
        if rem_all == 0:
            continue
        logicals.append(rem_s)
        span_pivots, span_rows = rref(span_rows + [rem_s], n)
    return logicals, sp, sr


def greedy_minimize(v, moves):
    cur = v
    improved = True
    while improved:
        improved = False
        cw = cur.bit_count()
        best = cur
        best_w = cw
        for row in moves:
            nv = cur ^ row
            nw = nv.bit_count()
            if nw < best_w:
                best = nv
                best_w = nw
        if best_w < cw:
            cur = best
            improved = True
    return cur


def stochastic_coset_minimize(v, ordered, rng, deadline, rounds=10):
    if not ordered:
        return v
    best = greedy_minimize(v, ordered[: min(len(ordered), 900)])
    cur = best
    for r in range(rounds):
        if time.monotonic() > deadline:
            break
        rows = ordered[:]
        rng.shuffle(rows)
        if len(rows) > 1200:
            rows = rows[:1200]
        temp = max(0.15, 2.0 * (1.0 - r / max(1, rounds)))
        for row in rows:
            old_w = cur.bit_count()
            nv = cur ^ row
            new_w = nv.bit_count()
            delta = new_w - old_w
            if delta <= 0 or rng.random() < pow(2.718281828459045, -delta / temp) * 0.015:
                cur = nv
                if new_w < best.bit_count():
                    best = cur
        cur = greedy_minimize(cur, ordered[: min(len(ordered), 700)])
        if cur.bit_count() < best.bit_count():
            best = cur
        if rng.random() < 0.35:
            cur = best
    return best


def xor_combo(vecs, idxs):
    v = 0
    for i in idxs:
        v ^= vecs[i]
    return v


def sample_logical(logicals, rng):
    m = len(logicals)
    if m == 1:
        return logicals[0]
    mode = rng.random()
    if mode < 0.45:
        t = 1
        while t < min(m, 12) and rng.random() < 0.58:
            t += 1
        return xor_combo(logicals, rng.sample(range(m), t))
    if mode < 0.82:
        t = rng.randint(1, min(m, 32))
        return xor_combo(logicals, rng.sample(range(m), t))
    v = 0
    p = rng.uniform(0.08, 0.45)
    any_bit = False
    for g in logicals:
        if rng.random() < p:
            v ^= g
            any_bit = True
    if not any_bit:
        v = logicals[rng.randrange(m)]
    return v


def search_basis(name, check_rows, stab_rows, n, rng, deadline):
    logicals, sp, sr = quotient_logicals(check_rows, stab_rows, n)
    if not logicals:
        return None

    moves = sorted(set(r for r in trim_rows(stab_rows, n) if in_kernel(r, check_rows)), key=lambda x: x.bit_count())
    candidates = []
    for g in sorted(logicals, key=lambda x: x.bit_count())[: min(len(logicals), 96)]:
        candidates.append(g)

    best = None
    seen = set()
    max_samples = 260 if n <= 1500 else 120
    i = 0
    while i < max_samples and time.monotonic() < deadline:
        if i < len(candidates):
            v = candidates[i]
        else:
            v = sample_logical(logicals, rng)
        i += 1
        if v in seen:
            continue
        seen.add(v)
        if not verified(v, check_rows, sp, sr):
            continue
        mv = stochastic_coset_minimize(v, moves, rng, deadline)
        if not verified(mv, check_rows, sp, sr):
            mv = greedy_minimize(v, moves)
        if verified(mv, check_rows, sp, sr):
            if best is None or mv.bit_count() < best.bit_count():
                best = mv

    if best is None:
        for g in logicals:
            mv = greedy_minimize(g, moves)
            if verified(mv, check_rows, sp, sr):
                best = mv
                break
    if best is None:
        return None
    return name, best


def bits_to_list(v, n):
    return [1 if ((v >> i) & 1) else 0 for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        hx = trim_rows(hx, n)
        hz = trim_rows(hz, n)
        os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)
        deadline = time.monotonic() + 10.0

        order = ["x", "z"]
        if rng.random() < 0.5:
            order.reverse()
        results = []
        for b in order:
            if b == "x":
                res = search_basis("x", hz, hx, n, rng, deadline)
            else:
                res = search_basis("z", hx, hz, n, rng, deadline)
            if res is not None:
                results.append(res)
        if not results:
            fail()
            return
        basis, vec = min(results, key=lambda item: item[1].bit_count())
        out = {
            "status": "completed",
            "basis": basis,
            "vector": bits_to_list(vec, n),
            "upper_bound": int(vec.bit_count()),
        }
        print(json.dumps(out, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
