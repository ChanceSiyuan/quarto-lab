#!/usr/bin/env python3
import argparse
import bisect
import json
import os
import random
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
        data = obj.get("data", [])
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
        for r in obj.get("rows", []):
            x = 0
            for i in r:
                j = int(i)
                if j >= 0:
                    x |= 1 << j
                    if j + 1 > n:
                        n = j + 1
            rows.append(x)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def parity(x):
    return x.bit_count() & 1


def gf2_basis(rows):
    basis = {}
    for v in rows:
        x = v
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def gf2_reduce(v, basis):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_span(v, basis):
    return gf2_reduce(v, basis) == 0


def kernel_basis(rows, n):
    rows = [r & ((1 << n) - 1) for r in rows if r]
    piv = {}
    for r in rows:
        x = r
        while x:
            p = x.bit_length() - 1
            if p in piv:
                x ^= piv[p]
            else:
                piv[p] = x
                break
    for p in sorted(piv):
        for q in sorted(piv):
            if p != q and ((piv[q] >> p) & 1):
                piv[q] ^= piv[p]
    pivot_cols = sorted(piv.keys())
    free_cols = [c for c in range(n) if c not in piv]
    out = []
    for f in free_cols:
        v = 1 << f
        for p in pivot_cols:
            if (piv[p] >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome(v, checks):
    s = 0
    for i, r in enumerate(checks):
        if parity(v & r):
            s |= 1 << i
    return s


def column_syndromes(checks, n):
    cols = [0] * n
    for i, r in enumerate(checks):
        x = r
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            cols[j] |= 1 << i
            x ^= lsb
    return cols


def solve_columns(cols, target, allowed):
    basis = {}
    combo = {}
    for j in allowed:
        x = cols[j]
        c = 1 << j
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
                c ^= combo[p]
            else:
                basis[p] = x
                combo[p] = c
                break
    x = target
    c = 0
    while x:
        p = x.bit_length() - 1
        if p not in basis:
            return None
        x ^= basis[p]
        c ^= combo[p]
    return c


def restrict_rows(rows, cols):
    pos = {c: i for i, c in enumerate(cols)}
    out = []
    for r in rows:
        x = 0
        y = r
        while y:
            lsb = y & -y
            j = lsb.bit_length() - 1
            k = pos.get(j)
            if k is not None:
                x |= 1 << k
            y ^= lsb
        out.append(x)
    return out


def expand_vector(v, cols):
    out = 0
    i = 0
    x = v
    while x:
        if x & 1:
            out |= 1 << cols[i]
        x >>= 1
        i += 1
    return out


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def greedy_stabilizer_reduce(v, stab_rows, stab_basis, rng, rounds=3):
    if not v or in_span(v, stab_basis):
        return v
    cur = v
    rows = [r for r in stab_rows if r]
    rows.sort(key=lambda r: r.bit_count())
    for _ in range(rounds):
        changed = True
        while changed:
            changed = False
            for r in rows:
                w = cur ^ r
                if w.bit_count() < cur.bit_count() and not in_span(w, stab_basis):
                    cur = w
                    changed = True
        rng.shuffle(rows)
    return cur


def logical_basis(check_rows, stab_rows, n):
    stab_basis = gf2_basis(stab_rows)
    span = dict(stab_basis)
    out = []
    for v in sorted(kernel_basis(check_rows, n), key=lambda x: x.bit_count()):
        if gf2_reduce(v, span):
            out.append(v)
            span = gf2_basis(list(span.values()) + [v])
    return out


def random_projection_search(check_rows, stab_rows, n, rng, deadline):
    stab_basis = gf2_basis(stab_rows)
    colsyn = column_syndromes(check_rows, n)
    degrees = [colsyn[i].bit_count() for i in range(n)]
    active = [i for i in range(n) if degrees[i] > 0]
    zero_cols = [i for i in range(n) if degrees[i] == 0]
    candidates = []

    # Zero-check columns are immediate kernel projections; keep them as cheap seeds.
    for i in zero_cols:
        v = 1 << i
        if not in_span(v, stab_basis):
            candidates.append(v)

    if n == 0:
        return candidates
    max_trials = max(220, min(2600, 80 * max(1, n)))
    small = min(n, max(1, int((n ** 0.5) * 2) + 2))
    medium = min(n, max(small, int(n * 0.22) + 4))
    weights = [1.0 / (1 + degrees[i]) for i in range(n)]
    cumulative = []
    acc = 0.0
    for w in weights:
        acc += w
        cumulative.append(acc)

    seen_syndromes = {}
    order = list(range(n))
    rng.shuffle(order)
    for i in order:
        s = colsyn[i]
        j = seen_syndromes.get(s)
        if j is None:
            seen_syndromes[s] = i
        else:
            v = (1 << i) ^ (1 << j)
            if v and syndrome(v, check_rows) == 0 and not in_span(v, stab_basis):
                candidates.append(v)

    for t in range(max_trials):
        if time.time() > deadline:
            break
        if t % 3 == 0:
            size = rng.randint(1, min(n, small))
        elif t % 3 == 1:
            size = rng.randint(small, min(n, medium))
        else:
            size = rng.randint(1, min(n, max(small, n // 2)))

        # Random projection: low-degree columns are sampled more often, with
        # occasional high-degree perturbations to avoid LDPC-only tunnel vision.
        chosen = set()
        while len(chosen) < size:
            if active and rng.random() < 0.18:
                chosen.add(rng.choice(active))
            else:
                chosen.add(bisect.bisect_left(cumulative, rng.random() * cumulative[-1]))
        cols = sorted(chosen)
        kb = kernel_basis(restrict_rows(check_rows, cols), len(cols))
        if kb:
            rng.shuffle(kb)
            for u in sorted(kb[:12], key=lambda x: x.bit_count()):
                v = expand_vector(u, cols)
                if v and not in_span(v, stab_basis):
                    candidates.append(v)

        # Kernel lifting: choose a tiny projected support, then solve a random
        # repair set whose column syndromes cancel the projected syndrome.
        anchor_size = rng.randint(1, min(n, max(1, small // 2)))
        anchors = rng.sample(range(n), anchor_size)
        a = 0
        for j in anchors:
            a |= 1 << j
        target = syndrome(a, check_rows)
        if target:
            repair_pool_size = min(n, max(small, int(n * (0.18 + 0.34 * rng.random()))))
            repair = set(rng.sample(range(n), repair_pool_size))
            repair.difference_update(anchors)
            sol = solve_columns(colsyn, target, list(repair))
            if sol is not None:
                v = a ^ sol
                if v and syndrome(v, check_rows) == 0 and not in_span(v, stab_basis):
                    candidates.append(v)

    return candidates


def improve_by_logical_mixing(candidates, logicals, check_rows, stab_rows, n, rng, deadline):
    stab_basis = gf2_basis(stab_rows)
    pool = []
    for v in candidates + logicals:
        if v and syndrome(v, check_rows) == 0 and not in_span(v, stab_basis):
            pool.append(greedy_stabilizer_reduce(v, stab_rows, stab_basis, rng, 2))
    pool = sorted(set(pool), key=lambda x: x.bit_count())[:80]
    best = pool[0] if pool else 0

    # Randomly combine already verified logical directions, then descend within
    # the stabilizer coset. This is a fallback-friendly upper-bound heuristic,
    # not an exact coset search.
    trials = max(120, 40 * len(logicals))
    for _ in range(trials):
        if time.time() > deadline:
            break
        v = 0
        source = logicals if rng.random() < 0.65 else pool
        if not source:
            break
        reps = rng.randint(1, min(len(source), 5))
        for u in rng.sample(source, reps):
            v ^= u
        if not v or in_span(v, stab_basis):
            continue
        v = greedy_stabilizer_reduce(v, stab_rows, stab_basis, rng, 3)
        if syndrome(v, check_rows) == 0 and not in_span(v, stab_basis):
            pool.append(v)
            if not best or v.bit_count() < best.bit_count():
                best = v
    return best


def search_one(name, check_rows, stab_rows, n, rng, deadline):
    stab_basis = gf2_basis(stab_rows)
    logs = logical_basis(check_rows, stab_rows, n)
    if not logs:
        return None
    projected = random_projection_search(check_rows, stab_rows, n, rng, deadline)
    best = improve_by_logical_mixing(projected, logs, check_rows, stab_rows, n, rng, deadline)
    if not best:
        best = min(logs, key=lambda x: x.bit_count())
    best = greedy_stabilizer_reduce(best, stab_rows, stab_basis, rng, 4)
    if best and syndrome(best, check_rows) == 0 and not in_span(best, stab_basis):
        return {"basis": name, "vector": vector_to_list(best, n), "upper_bound": best.bit_count()}
    for v in logs:
        if v and syndrome(v, check_rows) == 0 and not in_span(v, stab_basis):
            return {"basis": name, "vector": vector_to_list(v, n), "upper_bound": v.bit_count()}
    return None


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
        mask = (1 << n) - 1 if n else 0
        hx = [r & mask for r in hx]
        hz = [r & mask for r in hz]
        rng = random.Random(args.seed)
        os.makedirs(args.output_dir, exist_ok=True)
        deadline = time.time() + 55.0

        # X logicals commute with Z checks and are nontrivial modulo X stabilizers.
        xres = search_one("x", hz, hx, n, rng, deadline)
        # Z logicals commute with X checks and are nontrivial modulo Z stabilizers.
        zres = search_one("z", hx, hz, n, rng, deadline)
        choices = [r for r in (xres, zres) if r is not None]
        if choices:
            res = min(choices, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
            out = {
                "status": "completed",
                "basis": res["basis"],
                "vector": res["vector"],
                "upper_bound": int(res["upper_bound"]),
            }
        else:
            out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
