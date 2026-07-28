#!/usr/bin/env python3
import argparse
import json
import math
import random
import sys
import time


def row_to_int(row, n_hint=0):
    if isinstance(row, int):
        return row
    if isinstance(row, str):
        s = row.strip()
        if all(c in "01" for c in s):
            v = 0
            for i, c in enumerate(s):
                if c == "1":
                    v |= 1 << i
            return v
        raise ValueError("unsupported string row")
    v = 0
    for i, x in enumerate(row):
        if int(x) & 1:
            v |= 1 << i
    return v


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        n = max((len(r) if not isinstance(r, int) else r.bit_length()) for r in obj) if obj else 0
        return [row_to_int(r) for r in obj], n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or list")

    if "dense_binary_matrix" in obj and isinstance(obj["dense_binary_matrix"], dict):
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj and isinstance(obj["sparse_rows"], dict):
        obj = obj["sparse_rows"]

    typ = obj.get("type") or obj.get("format") or obj.get("kind")
    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols") or obj.get("num_cols") or 0)
        if n == 0 and data:
            n = max(len(r) if not isinstance(r, int) else r.bit_length() for r in data)
        return [row_to_int(r, n) for r in data], n

    if "rows" in obj:
        rows = obj["rows"]
        n = int(obj.get("num_cols") or obj.get("n_cols") or 0)
        if n == 0 and rows:
            row_max = []
            for r in rows:
                if isinstance(r, int):
                    row_max.append(r.bit_length() - 1)
                else:
                    row_max.append(max(r) if r else -1)
            n = 1 + max(row_max)
        out = []
        for r in rows:
            if isinstance(r, int):
                out.append(r)
            else:
                v = 0
                for c in r:
                    c = int(c)
                    if c >= 0:
                        v |= 1 << c
                out.append(v)
        return out, n

    if typ in ("dense_binary_matrix", "dense"):
        return [row_to_int(r) for r in obj.get("matrix", [])], int(obj.get("n_cols", 0))
    raise ValueError("unrecognized matrix format")


def mask_n(n):
    return (1 << n) - 1 if n > 0 else 0


def weight(x):
    return x.bit_count()


def rref_rows(rows, n):
    rows = [r & mask_n(n) for r in rows if r]
    rank = 0
    pivots = []
    for col in range(n):
        bit = 1 << col
        sel = None
        for i in range(rank, len(rows)):
            if rows[i] & bit:
                sel = i
                break
        if sel is None:
            continue
        rows[rank], rows[sel] = rows[sel], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & bit):
                rows[i] ^= rows[rank]
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return rows[:rank], pivots


def nullspace_basis(check_rows, n):
    rr, pivots = rref_rows(check_rows, n)
    pivot_set = set(pivots)
    basis = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        fbit = 1 << free
        for row, piv in zip(rr, pivots):
            if row & fbit:
                v |= 1 << piv
        basis.append(v & mask_n(n))
    return basis


def reducer_basis(rows, n):
    basis = {}
    for r in rows:
        x = r & mask_n(n)
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
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


def syndrome_zero(v, checks):
    for r in checks:
        if (v & r).bit_count() & 1:
            return False
    return True


def verify(v, checks, stab_basis):
    return v != 0 and syndrome_zero(v, checks) and not in_rowspace(v, stab_basis)


def greedy_descent(v, stab_rows, checks, stab_basis, rng, passes=5, focus_mask=None):
    if not verify(v, checks, stab_basis):
        return None
    cur = v
    cur_w = weight(cur)
    rows = [r for r in stab_rows if r]
    for _ in range(passes):
        changed = False
        scored = []
        for r in rows:
            if focus_mask is not None and not (r & focus_mask):
                continue
            overlap = (cur & r).bit_count()
            gain = 2 * overlap - weight(r)
            if gain > 0:
                scored.append((gain, rng.random(), r))
        if not scored:
            break
        scored.sort(reverse=True)
        for _, __, r in scored:
            nv = cur ^ r
            nw = weight(nv)
            if nw < cur_w:
                cur, cur_w = nv, nw
                changed = True
        if not changed:
            break
    return cur if verify(cur, checks, stab_basis) else None


def combine_basis(null_basis, rng, max_terms=None, bias=0.35):
    if not null_basis:
        return 0
    v = 0
    order = list(range(len(null_basis)))
    rng.shuffle(order)
    if max_terms is None:
        max_terms = max(1, int(1 + rng.expovariate(1.0 / max(1.0, len(order) * bias))))
    for i in order[: min(len(order), max_terms)]:
        if rng.random() < bias or v == 0:
            v ^= null_basis[i]
    return v


def make_block_mask(cols):
    m = 0
    for c in cols:
        m |= 1 << c
    return m


def block_perturb(v, stab_rows, n, rng, scale):
    if not stab_rows or n == 0:
        return v, None
    support = [i for i in range(n) if (v >> i) & 1]
    nonsupport = [i for i in range(n) if not ((v >> i) & 1)]
    rng.shuffle(support)
    rng.shuffle(nonsupport)
    take_s = min(len(support), max(1, scale // 2))
    take_n = min(len(nonsupport), max(0, scale - take_s))
    cols = support[:take_s] + nonsupport[:take_n]
    if not cols:
        cols = [rng.randrange(n)]
    bmask = make_block_mask(cols)

    touched = []
    for r in stab_rows:
        inter = (r & bmask).bit_count()
        if inter:
            touched.append((inter, (r & v).bit_count(), rng.random(), r))
    if not touched:
        return v, bmask
    touched.sort(reverse=True)
    limit = min(len(touched), max(4, 2 * scale + int(math.sqrt(len(stab_rows) + 1))))
    cur = v
    for _, __, ___, r in touched[:limit]:
        # Prefer rows that disturb the selected block, while retaining enough
        # randomness to jump between nearby stabilizer representatives.
        p = 0.18 + 0.55 * ((r & bmask).bit_count() / max(1, weight(r)))
        if rng.random() < min(0.85, p):
            cur ^= r
    return cur, bmask


def candidate_stream(null_basis, stab_rows, n, rng):
    by_weight = sorted(null_basis, key=weight)
    for v in by_weight:
        yield v
    for i in range(min(len(by_weight), 32)):
        for j in range(i + 1, min(len(by_weight), i + 9, len(by_weight))):
            yield by_weight[i] ^ by_weight[j]
    rounds = max(80, min(900, 12 * n + 25 * len(null_basis)))
    for t in range(rounds):
        if t % 5 == 0 and by_weight:
            k = 1 + (t // 5) % min(10, len(by_weight))
            v = 0
            pool = by_weight[: min(len(by_weight), 48)]
            rng.shuffle(pool)
            for b in pool[:k]:
                v ^= b
            yield v
        else:
            yield combine_basis(null_basis, rng, bias=rng.uniform(0.12, 0.55))


def search_basis(name, checks, stabs, n, seed, deadline):
    rng = random.Random((seed << 7) ^ (0x9E3779B97F4A7C15 if name == "x" else 0xD1B54A32D192ED03))
    checks = [r & mask_n(n) for r in checks if r]
    stabs = [r & mask_n(n) for r in stabs if r]
    stab_basis = reducer_basis(stabs, n)
    null_basis = nullspace_basis(checks, n)
    if not null_basis:
        return None

    best = None
    best_w = n + 1

    def consider(v, passes=6, focus=None):
        nonlocal best, best_w
        v &= mask_n(n)
        if not verify(v, checks, stab_basis):
            return
        v = greedy_descent(v, stabs, checks, stab_basis, rng, passes=passes, focus_mask=focus)
        if v is None or not verify(v, checks, stab_basis):
            return
        w = weight(v)
        if w < best_w:
            best, best_w = v, w

    # Reliable fallback: at least one nullspace basis vector is outside the
    # stabilizer space whenever this CSS side has positive logical dimension.
    for v in null_basis:
        consider(v, passes=8)

    for v in candidate_stream(null_basis, stabs, n, rng):
        if time.monotonic() > deadline:
            break
        consider(v, passes=5)
        base = best if best is not None and rng.random() < 0.65 else v
        if not verify(base & mask_n(n), checks, stab_basis):
            continue
        scales = [1, 2, 3, 5, 8, 13, 21, 34]
        max_scale = max(1, min(n, scales[(rng.randrange(len(scales)))]))
        pv, bmask = block_perturb(base, stabs, n, rng, max_scale)
        consider(pv, passes=4, focus=bmask)

    if best is None:
        # Deterministic quotient scan over cumulative nullspace combinations.
        v = 0
        for b in sorted(null_basis, key=lambda x: (weight(x), x)):
            v ^= b
            consider(v, passes=10)
            if best is not None:
                break
    return best


def int_to_bits(v, n):
    return [1 if ((v >> i) & 1) else 0 for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=False, default=None)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz, max((r.bit_length() for r in hx + hz), default=0))
        deadline = time.monotonic() + 18.0

        results = []
        vx = search_basis("x", hz, hx, n, args.seed, deadline)
        if vx is not None:
            results.append(("x", vx, weight(vx)))
        vz = search_basis("z", hx, hz, n, args.seed ^ 0xA5A5A5A5, deadline)
        if vz is not None:
            results.append(("z", vz, weight(vz)))

        if results:
            basis, vec, ub = min(results, key=lambda x: (x[2], x[0]))
            out = {
                "status": "completed",
                "basis": basis,
                "vector": int_to_bits(vec, n),
                "upper_bound": ub,
            }
        else:
            out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
