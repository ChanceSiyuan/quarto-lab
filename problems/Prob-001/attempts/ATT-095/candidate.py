#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        return rows_to_ints(data, n), n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        if data and all(isinstance(x, int) for x in data):
            if n <= 0:
                raise ValueError("flat dense matrix requires n_cols")
            data = [data[i:i + n] for i in range(0, len(data), n)]
        elif n <= 0:
            n = max((len(r) for r in data), default=0)
        return rows_to_ints(data, n), n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = 1 + max((c for r in obj["rows"] for c in r), default=-1)
        out = []
        for r in obj["rows"]:
            v = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    v ^= 1 << c
            if v:
                out.append(v)
        return out, n
    raise ValueError("unknown matrix format")


def rows_to_ints(data, n):
    out = []
    for row in data:
        v = 0
        for i, bit in enumerate(row[:n]):
            if bit & 1:
                v |= 1 << i
        if v:
            out.append(v)
    return out


def rref(rows, n):
    rows = [r for r in rows if r]
    piv_rows = []
    pivots = []
    rank = 0
    for col in range(n):
        bit = 1 << col
        pivot_at = -1
        for i in range(rank, len(rows)):
            if rows[i] & bit:
                pivot_at = i
                break
        if pivot_at < 0:
            continue
        rows[rank], rows[pivot_at] = rows[pivot_at], rows[rank]
        p = rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & bit):
                rows[i] ^= p
        piv_rows.append(p)
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return piv_rows, pivots


def reduce_by_rref(v, piv_rows, pivots):
    for row, col in zip(piv_rows, pivots):
        if (v >> col) & 1:
            v ^= row
    return v


def nullspace_basis(rows, n):
    rr, pivots = rref(rows, n)
    pivot_set = set(pivots)
    basis = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, col in zip(rr, pivots):
            if (row >> free) & 1:
                v |= 1 << col
        basis.append(v)
    return basis


def quotient_logicals(check_rows, stab_rows, n):
    ns = nullspace_basis(check_rows, n)
    srr, spiv = rref(stab_rows, n)
    qrr = []
    qpiv = []
    reps = []
    for v in ns:
        rem = reduce_by_rref(v, srr, spiv)
        rem2 = reduce_by_rref(rem, qrr, qpiv)
        if rem2:
            p = (rem2 & -rem2).bit_length() - 1
            for i, row in enumerate(qrr):
                if (row >> p) & 1:
                    qrr[i] ^= rem2
            qrr.append(rem2)
            qpiv.append(p)
            order = sorted(range(len(qpiv)), key=lambda i: qpiv[i])
            qrr = [qrr[i] for i in order]
            qpiv = [qpiv[i] for i in order]
            reps.append(v)
    return reps, srr, spiv


def verified(v, check_rows, stab_rref, stab_pivots):
    if not v:
        return False
    for row in check_rows:
        if (v & row).bit_count() & 1:
            return False
    return reduce_by_rref(v, stab_rref, stab_pivots) != 0


def row_score(v, wv, row, rw):
    return wv + rw - 2 * (v & row).bit_count()


def luby(i):
    k = 1
    while (1 << k) - 1 < i:
        k += 1
    if i == (1 << k) - 1:
        return 1 << (k - 1)
    return luby(i - (1 << (k - 1)) + 1)


def make_row_pool(stab_rows, n):
    rr, _ = rref(stab_rows, n)
    pool = list(dict.fromkeys([r for r in stab_rows + rr if r]))
    pool.sort(key=lambda x: x.bit_count())
    return pool


def greedy_descent(v, pool, rng, budget):
    if not pool:
        return v
    wv = v.bit_count()
    light = pool[:min(len(pool), 512)]
    for _ in range(budget):
        candidates = []
        if len(pool) <= 768:
            candidates = pool
        else:
            candidates.extend(light[:96])
            candidates.extend(pool[rng.randrange(len(pool))] for _ in range(192))
        best = v
        best_w = wv
        ties = 0
        for row in candidates:
            nw = row_score(v, wv, row, row.bit_count())
            if nw < best_w:
                best = v ^ row
                best_w = nw
                ties = 1
            elif nw == best_w and nw < wv:
                ties += 1
                if rng.randrange(ties) == 0:
                    best = v ^ row
        if best_w >= wv:
            break
        v, wv = best, best_w
    return v


def random_combo(items, rng, mandatory=None, extra_scale=1.0):
    if mandatory is None:
        v = 0
    else:
        v = mandatory
    if not items:
        return v
    u = max(1e-12, rng.random())
    extras = int(min(len(items), (u ** -0.55 - 1.0) * extra_scale))
    for _ in range(extras):
        v ^= items[rng.randrange(len(items))]
    if v == 0:
        v = items[rng.randrange(len(items))]
    return v


def search_basis(name, check_rows, stab_rows, n, seed, deadline):
    reps, srr, spiv = quotient_logicals(check_rows, stab_rows, n)
    if not reps:
        return None
    pool = make_row_pool(stab_rows, n)
    rng = random.Random((seed << 8) ^ (17 if name == "x" else 43) ^ n)
    best = None
    for rep in reps:
        v = greedy_descent(rep, pool, rng, 96)
        if verified(v, check_rows, srr, spiv) and (best is None or v.bit_count() < best.bit_count()):
            best = v
    restart = 1
    while time.monotonic() < deadline:
        span = luby(restart)
        restart += 1
        base = reps[rng.randrange(len(reps))]
        v = random_combo(reps, rng, mandatory=base, extra_scale=1.7)
        if pool:
            flips = min(len(pool), max(1, int(span * (1 + rng.random() * 3))))
            for _ in range(flips):
                if rng.random() < 0.72:
                    row = pool[min(len(pool) - 1, int(rng.random() ** 2 * len(pool)))]
                else:
                    row = pool[rng.randrange(len(pool))]
                v ^= row
        budget = min(1536, 24 + 12 * span)
        v = greedy_descent(v, pool, rng, budget)
        if verified(v, check_rows, srr, spiv) and (best is None or v.bit_count() < best.bit_count()):
            best = v
    if best is None:
        for rep in reps:
            if verified(rep, check_rows, srr, spiv):
                best = rep
                break
    return best


def int_to_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


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
        budget = min(6.0, max(1.5, 0.002 * n + 0.0003 * (len(hx) + len(hz))))
        start = time.monotonic()
        bx = search_basis("x", hz, hx, n, args.seed, start + 0.5 * budget)
        bz = search_basis("z", hx, hz, n, args.seed + 1000003, start + budget)
        choices = []
        if bx is not None:
            choices.append(("x", bx))
        if bz is not None:
            choices.append(("z", bz))
        if choices:
            basis, vec = min(choices, key=lambda t: (t[1].bit_count(), 0 if t[0] == "x" else 1))
            out = {
                "status": "completed",
                "basis": basis,
                "vector": int_to_bits(vec, n),
                "upper_bound": vec.bit_count(),
            }
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
