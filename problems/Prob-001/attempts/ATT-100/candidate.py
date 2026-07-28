#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def fail():
    print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))


def load_json_arg(value):
    if value == "-":
        return json.load(sys.stdin)
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(value)


def matrix_to_rows(obj):
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    rows = []
    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", len(data[0]) if data else 0))
        for row in data:
            mask = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    mask ^= 1 << j
            rows.append(mask)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        for row in obj.get("rows") or []:
            mask = 0
            for j in row:
                jj = int(j)
                if 0 <= jj < n:
                    mask ^= 1 << jj
            rows.append(mask)
        return rows, n

    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        for row in obj:
            mask = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    mask ^= 1 << j
            rows.append(mask)
        return rows, n

    raise ValueError("unsupported matrix format")


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = int(row)
        for p in sorted(basis.keys(), reverse=True):
            if (x >> p) & 1:
                x ^= basis[p]
        if x:
            p = x.bit_length() - 1
            for q, r in list(basis.items()):
                if (r >> p) & 1:
                    basis[q] = r ^ x
            basis[p] = x
    return basis


def reduce_with_basis(x, basis):
    x = int(x)
    for p in sorted(basis.keys(), reverse=True):
        if (x >> p) & 1:
            x ^= basis[p]
    return x


def in_span(x, basis):
    return reduce_with_basis(x, basis) == 0


def nullspace_basis(check_rows, n):
    rb = rref_basis(check_rows)
    pivots = set(rb.keys())
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v ^= 1 << p
        out.append(v)
    return out


def kernel_ok(v, check_rows):
    for row in check_rows:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def verified(v, check_rows, stab_basis):
    return v != 0 and kernel_ok(v, check_rows) and not in_span(v, stab_basis)


def rows_by_weight(rows):
    unique = sorted(set(int(r) for r in rows if r), key=lambda x: (x.bit_count(), x))
    return unique


def greedy_minimize(v, stab_rows, rng, deadline, rounds=2, sample_cap=384):
    if not stab_rows:
        return v
    cur = v
    rows = stab_rows
    if len(rows) > sample_cap:
        rows = rng.sample(rows, sample_cap)
    for _ in range(rounds):
        improved = True
        while improved and time.monotonic() < deadline:
            improved = False
            cw = cur.bit_count()
            best_delta = 0
            best = []
            scan = rows
            if len(stab_rows) > len(rows) and rng.random() < 0.35:
                scan = rng.sample(stab_rows, min(sample_cap, len(stab_rows)))
            for r in scan:
                delta = r.bit_count() - 2 * (cur & r).bit_count()
                if delta < best_delta:
                    best_delta = delta
                    best = [r]
                elif delta == best_delta and delta < 0 and len(best) < 16:
                    best.append(r)
            if best:
                cur ^= rng.choice(best)
                improved = True
    return cur


def annealed_coset_minimize(v, stab_rows, rng, deadline, intensity):
    best = v
    cur = v
    temp = 2.5
    limit = max(16, min(700, intensity))
    for step in range(limit):
        if time.monotonic() >= deadline:
            break
        if not stab_rows:
            break
        r = stab_rows[rng.randrange(len(stab_rows))]
        nxt = cur ^ r
        delta = nxt.bit_count() - cur.bit_count()
        if delta <= 0 or rng.random() < pow(2.718281828, -delta / max(0.15, temp)):
            cur = nxt
            if cur.bit_count() < best.bit_count():
                best = cur
        temp *= 0.992
        if (step & 31) == 31:
            cur = greedy_minimize(cur, stab_rows, rng, deadline, rounds=1)
            if cur.bit_count() < best.bit_count():
                best = cur
    return greedy_minimize(best, stab_rows, rng, deadline, rounds=2)


def quotient_generators(check_rows, stab_rows, n):
    stab_basis = rref_basis(stab_rows)
    span = dict(stab_basis)
    gens = []
    for kvec in sorted(nullspace_basis(check_rows, n), key=lambda x: (x.bit_count(), x)):
        if reduce_with_basis(kvec, span) != 0:
            gens.append(kvec)
            span = rref_basis(list(span.values()) + [kvec])
    return gens, stab_basis


def xor_many(vecs):
    out = 0
    for v in vecs:
        out ^= v
    return out


def search_side(name, check_rows, stab_rows, n, rng, deadline):
    gens, stab_basis = quotient_generators(check_rows, stab_rows, n)
    if not gens:
        return None

    stab_sorted = rows_by_weight(stab_rows)
    candidates = []
    for g in gens:
        candidates.append(g)

    # Small quotient spaces can be sampled broadly without becoming exact distance search:
    # the objective remains randomized coset-leader improvement, not proving optimality.
    if len(gens) <= 12:
        order = list(range(1, 1 << len(gens)))
        rng.shuffle(order)
        for mask in order[: min(len(order), 1800)]:
            v = 0
            for i, g in enumerate(gens):
                if (mask >> i) & 1:
                    v ^= g
            candidates.append(v)

    best = None
    def consider(v):
        nonlocal best
        if verified(v, check_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for v in candidates:
        if time.monotonic() >= deadline:
            break
        mv = greedy_minimize(v, stab_sorted, rng, deadline, rounds=3)
        consider(mv)

    attempts = 0
    max_attempts = 1200 + 80 * len(gens)
    weights = [1.0 / max(1, g.bit_count()) for g in gens]
    total_w = sum(weights)
    while time.monotonic() < deadline and attempts < max_attempts:
        attempts += 1
        if rng.random() < 0.55:
            target = 1 + int(rng.expovariate(1.0 / max(1.5, len(gens) / 5.0)))
            target = max(1, min(len(gens), target))
            idxs = set()
            while len(idxs) < target:
                pick = rng.random() * total_w
                acc = 0.0
                for i, w in enumerate(weights):
                    acc += w
                    if acc >= pick:
                        idxs.add(i)
                        break
            v = xor_many(gens[i] for i in idxs)
        else:
            v = rng.choice(gens)
            for _ in range(rng.randrange(1, min(len(gens), 7) + 1)):
                v ^= rng.choice(gens)
            if v == 0:
                v = rng.choice(gens)

        if stab_sorted and rng.random() < 0.45:
            for r in rng.sample(stab_sorted, min(len(stab_sorted), 1 + rng.randrange(6))):
                v ^= r

        mv = annealed_coset_minimize(v, stab_sorted, rng, deadline, 140 + 8 * len(stab_sorted))
        consider(mv)

    if best is None:
        for g in gens:
            if verified(g, check_rows, stab_basis):
                best = g
                break
    if best is None:
        return None
    return name, best


def vector_from_mask(mask, n):
    return [int((mask >> i) & 1) for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    try:
        hx, nx = matrix_to_rows(load_json_arg(args.hx))
        hz, nz = matrix_to_rows(load_json_arg(args.hz))
        n = max(nx, nz)
        if nx not in (0, n) or nz not in (0, n):
            fail()
            return
        rng = random.Random(args.seed)
        deadline = time.monotonic() + 24.0

        results = []
        # X logicals commute with Z checks modulo X stabilizers; Z logicals are dual.
        for name, check, stab in (("x", hz, hx), ("z", hx, hz)):
            side_deadline = time.monotonic() + max(0.25, (deadline - time.monotonic()) / 2.0)
            res = search_side(name, check, stab, n, rng, side_deadline)
            if res is not None:
                results.append(res)

        if not results and time.monotonic() < deadline:
            for name, check, stab in (("x", hz, hx), ("z", hx, hz)):
                res = search_side(name, check, stab, n, rng, deadline)
                if res is not None:
                    results.append(res)
                    break

        if not results:
            fail()
            return

        basis, mask = min(results, key=lambda t: (t[1].bit_count(), 0 if t[0] == "x" else 1))
        check = hz if basis == "x" else hx
        stab = hx if basis == "x" else hz
        if not verified(mask, check, rref_basis(stab)):
            fail()
            return
        vec = vector_from_mask(mask, n)
        print(json.dumps({"status": "completed", "basis": basis, "vector": vec, "upper_bound": int(mask.bit_count())}, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
