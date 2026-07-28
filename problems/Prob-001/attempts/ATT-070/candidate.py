#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_matrix_arg(value):
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(value)


def matrix_to_masks(obj):
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for row in obj:
            mask = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("matrix must be a JSON object or row list")

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for row in data:
            mask = 0
            for i, bit in enumerate(row[:n]):
                if bit & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n

    if "rows" in obj:
        sparse = obj["rows"]
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = max((max(r) + 1 for r in sparse if r), default=0)
        rows = []
        for row in sparse:
            mask = 0
            for col in row:
                c = int(col)
                if 0 <= c < n:
                    mask |= 1 << c
            rows.append(mask)
        return rows, n

    raise ValueError("unsupported matrix format")


def rref_low(rows, n):
    a = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        bit = 1 << col
        pivot = None
        for i in range(rank, len(a)):
            if a[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        for i in range(len(a)):
            if i != rank and (a[i] & bit):
                a[i] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == len(a):
            break
    return a[:rank], pivots


def nullspace_basis(rows, n):
    rr, pivots = rref_low(rows, n)
    pivot_set = set(pivots)
    basis = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        free_bit = 1 << free
        for row, piv in zip(rr, pivots):
            if row & free_bit:
                v |= 1 << piv
        basis.append(v)
    return basis


def add_to_high_basis(basis, v):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def in_span_high(basis, v):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        x ^= b
    return True


def high_basis(rows):
    basis = {}
    for r in rows:
        add_to_high_basis(basis, r)
    return basis


def kernel_ok(check_rows, v):
    return all(((r & v).bit_count() & 1) == 0 for r in check_rows)


def verified(check_rows, stab_basis, v):
    return v != 0 and kernel_ok(check_rows, v) and not in_span_high(stab_basis, v)


def logical_basis(check_rows, stab_rows, n):
    span = high_basis(stab_rows)
    out = []
    for v in nullspace_basis(check_rows, n):
        if not in_span_high(span, v):
            out.append(v)
            add_to_high_basis(span, v)
    return out


def greedy_reduce(v, stab_rows, rng, rounds=3):
    rows = [r for r in stab_rows if r]
    if not rows:
        return v
    cur = v
    for _ in range(rounds):
        improved = False
        rng.shuffle(rows)
        rows.sort(key=lambda r: ((cur & r).bit_count() * 2 - r.bit_count()), reverse=True)
        for r in rows:
            nxt = cur ^ r
            if nxt.bit_count() < cur.bit_count():
                cur = nxt
                improved = True
        if not improved:
            break
    return cur


def random_sum(rows, rng, p_num=1, p_den=2):
    mask = 0
    for r in rows:
        if rng.randrange(p_den) < p_num:
            mask ^= r
    return mask


def projection(mask, coords):
    key = 0
    for i, c in enumerate(coords):
        if mask >> c & 1:
            key |= 1 << i
    return key


def mitm_reduce(v, stab_rows, n, rng, sample_budget):
    rows = [r for r in high_basis(stab_rows).values() if r]
    if not rows:
        return v
    cur = greedy_reduce(v, rows, rng, 4)
    best = cur
    best_w = cur.bit_count()

    trials = max(3, min(12, sample_budget // 700))
    per_side = max(96, min(2400, sample_budget // trials))
    all_cols = list(range(n))

    for _ in range(trials):
        rng.shuffle(rows)
        mid = len(rows) // 2
        left = rows[:mid]
        right = rows[mid:]

        hot = [i for i in range(n) if (best >> i) & 1]
        rng.shuffle(hot)
        if len(hot) < min(64, n):
            hot_set = set(hot)
            fill = [c for c in all_cols if c not in hot_set]
            rng.shuffle(fill)
            hot.extend(fill[: max(0, min(64, n) - len(hot))])
        coords = hot[: min(64, n)]

        table = {}
        for i in range(per_side):
            if i == 0:
                a = 0
            else:
                den = rng.choice((2, 3, 4, 5))
                a = random_sum(left, rng, 1, den)
            key = projection(a, coords)
            old = table.get(key)
            if old is None or a.bit_count() < old.bit_count():
                table[key] = a

        for i in range(per_side):
            if i == 0:
                b = 0
            else:
                den = rng.choice((2, 3, 4, 5))
                b = random_sum(right, rng, 1, den)
            want = projection(cur ^ b, coords)
            probes = [want]
            if len(coords) >= 8:
                for _j in range(3):
                    probes.append(want ^ (1 << rng.randrange(len(coords))))
            for key in probes:
                a = table.get(key)
                if a is None:
                    continue
                cand = cur ^ a ^ b
                w = cand.bit_count()
                if 0 < w < best_w:
                    best, best_w = cand, w
                    cur = greedy_reduce(best, rows, rng, 2)
                    if cur.bit_count() < best_w:
                        best, best_w = cur, cur.bit_count()
    return greedy_reduce(best, rows, rng, 3)


def candidate_logicals(logs, rng, limit):
    cands = sorted(logs, key=lambda x: x.bit_count())[: min(len(logs), 12)]
    if not logs:
        return cands
    small = sorted(logs, key=lambda x: x.bit_count())[: min(len(logs), 10)]
    for i in range(len(small)):
        for j in range(i + 1, len(small)):
            cands.append(small[i] ^ small[j])
    for _ in range(limit):
        v = 0
        den = rng.choice((2, 3, 4))
        for g in logs:
            if rng.randrange(den) == 0:
                v ^= g
        if v:
            cands.append(v)
    return cands


def search_basis(name, check_rows, stab_rows, n, rng):
    stab_span = high_basis(stab_rows)
    logs = logical_basis(check_rows, stab_rows, n)
    best = None
    best_w = None

    rank_hint = len(high_basis(stab_rows))
    combo_limit = 24 if n <= 512 else 12
    for v in candidate_logicals(logs, rng, combo_limit):
        if not verified(check_rows, stab_span, v):
            continue
        budget = 2800 if n <= 512 else 1400
        if rank_hint > 800:
            budget //= 2
        cand = mitm_reduce(v, stab_rows, n, rng, budget)
        cand = greedy_reduce(cand, list(stab_span.values()), rng, 3)
        if verified(check_rows, stab_span, cand):
            w = cand.bit_count()
            if best is None or w < best_w:
                best, best_w = cand, w

    if best is None:
        for v in logs:
            if verified(check_rows, stab_span, v):
                best, best_w = v, v.bit_count()
                break

    if best is None:
        return None
    return {"basis": name, "mask": best, "weight": best_w}


def mask_to_list(mask, n):
    return [1 if (mask >> i) & 1 else 0 for i in range(n)]


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    try:
        hx_rows, nx = matrix_to_masks(load_matrix_arg(args.hx))
        hz_rows, nz = matrix_to_masks(load_matrix_arg(args.hz))
        n = max(nx, nz)
        full = (1 << n) - 1 if n else 0
        hx_rows = [r & full for r in hx_rows]
        hz_rows = [r & full for r in hz_rows]

        rng = random.Random(args.seed)
        results = [
            search_basis("x", hz_rows, hx_rows, n, rng),
            search_basis("z", hx_rows, hz_rows, n, rng),
        ]
        results = [r for r in results if r is not None]
        if not results:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
        else:
            best = min(results, key=lambda r: (r["weight"], 0 if r["basis"] == "x" else 1))
            if best["basis"] == "x":
                ok = verified(hz_rows, high_basis(hx_rows), best["mask"])
            else:
                ok = verified(hx_rows, high_basis(hz_rows), best["mask"])
            if ok:
                out = {
                    "status": "completed",
                    "basis": best["basis"],
                    "vector": mask_to_list(best["mask"], n),
                    "upper_bound": best["weight"],
                }
            else:
                out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
