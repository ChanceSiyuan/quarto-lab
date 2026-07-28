#!/usr/bin/env python3
import argparse
import json
import os
import random
from collections import deque


def rows_from_json(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", 0))
        if not n and data:
            n = max(len(r) for r in data)
        rows = []
        for r in data:
            x = 0
            for j, bit in enumerate(r):
                if bit & 1:
                    x ^= 1 << j
            rows.append(x)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for j in r:
                jj = int(j)
                if jj >= 0:
                    x ^= 1 << jj
                    if jj + 1 > n:
                        n = jj + 1
            rows.append(x)
        return rows, n

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for j, bit in enumerate(r):
                if bit & 1:
                    x ^= 1 << j
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def add_to_basis(basis, row):
    x = row
    while x:
        p = x.bit_length() - 1
        if p in basis:
            x ^= basis[p]
        else:
            basis[p] = x
            return True
    return False


def make_basis(rows):
    basis = {}
    for r in rows:
        add_to_basis(basis, r)
    return basis


def in_rowspace(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        y ^= b
    return True


def rref_low_pivots(rows, n):
    rows = [r for r in rows if r]
    pivot_order = []
    r = 0
    for c in range(n):
        bit = 1 << c
        sel = None
        for i in range(r, len(rows)):
            if rows[i] & bit:
                sel = i
                break
        if sel is None:
            continue
        rows[r], rows[sel] = rows[sel], rows[r]
        for i in range(len(rows)):
            if i != r and (rows[i] & bit):
                rows[i] ^= rows[r]
        pivot_order.append(c)
        r += 1
        if r == len(rows):
            break
    return {p: rows[i] for i, p in enumerate(pivot_order)}


def nullspace_basis(rows, n):
    piv = rref_low_pivots(rows, n)
    pivot_cols = set(piv)
    out = []
    for f in range(n):
        if f in pivot_cols:
            continue
        v = 1 << f
        for p, row in piv.items():
            if ((row >> f) & 1):
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, rows):
    for r in rows:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def verify(v, kernel_rows, stab_basis):
    return v != 0 and syndrome_zero(v, kernel_rows) and not in_rowspace(v, stab_basis)


def bit_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def row_indices(rows, n):
    check_to_vars = []
    var_to_checks = [[] for _ in range(n)]
    var_incidence = [0] * n
    for i, r in enumerate(rows):
        vs = []
        x = r
        while x:
            lsb = x & -x
            q = lsb.bit_length() - 1
            if q < n:
                vs.append(q)
                var_to_checks[q].append(i)
                var_incidence[q] ^= 1 << i
            x ^= lsb
        check_to_vars.append(vs)
    return check_to_vars, var_to_checks, var_incidence


def support_to_int(supp):
    v = 0
    for q in supp:
        v ^= 1 << q
    return v


def stabilizer_reduce(v, stab_rows, rng, passes=5):
    if not v:
        return v
    rows = [r for r in stab_rows if r]
    best = v
    improved = True
    p = 0
    while improved and p < passes:
        improved = False
        rng.shuffle(rows)
        for r in rows:
            w = best ^ r
            if w.bit_count() < best.bit_count():
                best = w
                improved = True
        p += 1
    return best


def solve_columns(columns, target):
    basis = {}
    for i, col in enumerate(columns):
        x = col
        sol = 1 << i
        while x:
            p = x.bit_length() - 1
            if p in basis:
                bx, bs = basis[p]
                x ^= bx
                sol ^= bs
            else:
                basis[p] = (x, sol)
                break
    x = target
    sol = 0
    while x:
        p = x.bit_length() - 1
        item = basis.get(p)
        if item is None:
            return None
        bx, bs = item
        x ^= bx
        sol ^= bs
    return sol


def bounded_repair(cluster, syndrome, check_to_vars, var_incidence, degrees, rng, limit):
    if syndrome == 0:
        return support_to_int(cluster)

    cand = set()
    s = syndrome
    while s:
        lsb = s & -s
        ci = lsb.bit_length() - 1
        for q in check_to_vars[ci]:
            cand.add(q)
        s ^= lsb

    for q in list(cluster):
        for ci_bit in bits_of_int(var_incidence[q]):
            for qq in check_to_vars[ci_bit]:
                cand.add(qq)

    ordered = list(cand)
    rng.shuffle(ordered)
    ordered.sort(key=lambda q: (0 if q not in cluster else 1, degrees[q], rng.random()))
    ordered = ordered[:limit]
    sol = solve_columns([var_incidence[q] for q in ordered], syndrome)
    if sol is None:
        return None
    v = support_to_int(cluster)
    for i, q in enumerate(ordered):
        if (sol >> i) & 1:
            v ^= 1 << q
    return v


def bits_of_int(x):
    while x:
        lsb = x & -x
        yield lsb.bit_length() - 1
        x ^= lsb


def greedy_parity_walk(v, var_to_checks, var_incidence, rng, max_steps):
    syn = 0
    for q in bits_of_int(v):
        syn ^= var_incidence[q]
    if syn == 0:
        return v

    n = len(var_to_checks)
    for _ in range(max_steps):
        if syn == 0:
            return v
        cand = set()
        # This slow path is only used after bounded repair misses, so a
        # randomized global sample is enough to shake loose parity repairs.
        sample = rng.sample(range(n), min(n, 96))
        cand.update(sample)
        best = []
        best_score = -10**9
        for q in cand:
            inc = var_incidence[q]
            if not inc:
                continue
            before = (syn & inc).bit_count()
            after = inc.bit_count() - before
            score = before - after
            if (v >> q) & 1:
                score += 0.15
            else:
                score -= 0.35
            if score > best_score:
                best_score = score
                best = [q]
            elif score == best_score:
                best.append(q)
        if not best:
            return None
        q = rng.choice(best)
        v ^= 1 << q
        syn ^= var_incidence[q]
    return v if syn == 0 else None


def cluster_candidates(kernel_rows, stab_rows, stab_basis, n, rng, rounds):
    check_to_vars, var_to_checks, var_incidence = row_indices(kernel_rows, n)
    degrees = [len(c) for c in var_to_checks]
    active = [q for q in range(n) if degrees[q] > 0]
    if not active:
        active = list(range(n))
    seed_pool = sorted(active, key=lambda q: (degrees[q], q))
    best = None

    for t in range(rounds):
        if t < min(len(seed_pool), max(8, rounds // 5)):
            seed = seed_pool[t % len(seed_pool)]
        else:
            weights = [1.0 / (1 + degrees[q]) for q in active]
            seed = rng.choices(active, weights=weights, k=1)[0]

        cluster = {seed}
        frontier = deque()
        seen = {seed}
        for ci in var_to_checks[seed]:
            vs = list(check_to_vars[ci])
            rng.shuffle(vs)
            for q in vs:
                if q != seed and q not in seen:
                    frontier.append(q)
                    seen.add(q)

        max_cluster = min(n, 2 + int(2.5 * (t % 17 + 1)) + rng.randrange(1, max(2, min(24, n + 1))))
        while frontier and len(cluster) < max_cluster:
            if rng.random() < 0.72:
                sample = [frontier.popleft() for _ in range(min(len(frontier), 5))]
                q = min(sample, key=lambda x: (degrees[x], rng.random()))
                for other in sample:
                    if other != q:
                        frontier.append(other)
            else:
                q = frontier.popleft()
            if q in cluster:
                continue
            cluster.add(q)
            for ci in var_to_checks[q]:
                vs = list(check_to_vars[ci])
                rng.shuffle(vs)
                for qq in vs:
                    if qq not in seen:
                        seen.add(qq)
                        frontier.append(qq)

        syn = 0
        for q in cluster:
            syn ^= var_incidence[q]

        repair_limit = min(n, 36 + (t % 5) * 20)
        v = bounded_repair(cluster, syn, check_to_vars, var_incidence, degrees, rng, repair_limit)
        if v is None and n <= 512:
            v = greedy_parity_walk(support_to_int(cluster), var_to_checks, var_incidence, rng, 80)
        if v is None:
            continue
        v = stabilizer_reduce(v, stab_rows, rng, passes=4)
        if verify(v, kernel_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    return best


def fallback_witness(kernel_rows, stab_rows, stab_basis, n, rng):
    ns = nullspace_basis(kernel_rows, n)
    best = None
    for v in ns:
        v = stabilizer_reduce(v, stab_rows, rng, passes=8)
        if verify(v, kernel_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    if best is not None:
        return best

    # Extremely unlikely with a positive-k CSS input, but random combinations
    # cover degenerate nullspace bases and malformed rank edge cases.
    for _ in range(2048):
        v = 0
        for b in ns:
            if rng.getrandbits(1):
                v ^= b
        v = stabilizer_reduce(v, stab_rows, rng, passes=8)
        if verify(v, kernel_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v
    return best


def search_basis(name, kernel_rows, stab_rows, n, rng):
    stab_basis = make_basis(stab_rows)
    fb = fallback_witness(kernel_rows, stab_rows, stab_basis, n, rng)
    best = fb

    rounds = 140
    if n <= 128:
        rounds = 220
    elif n >= 1000:
        rounds = 80
    cc = cluster_candidates(kernel_rows, stab_rows, stab_basis, n, rng, rounds)
    if cc is not None and (best is None or cc.bit_count() < best.bit_count()):
        best = cc

    if best is not None and verify(best, kernel_rows, stab_basis):
        return {"basis": name, "vector": best, "weight": best.bit_count()}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    try:
        hx, nx = rows_from_json(args.hx)
        hz, nz = rows_from_json(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]

        rng = random.Random(args.seed)
        results = []
        # X logicals commute with HZ and are nontrivial modulo rows of HX.
        rx = search_basis("x", hz, hx, n, random.Random(rng.randrange(1 << 62)))
        if rx is not None:
            results.append(rx)
        # Z logicals commute with HX and are nontrivial modulo rows of HZ.
        rz = search_basis("z", hx, hz, n, random.Random(rng.randrange(1 << 62)))
        if rz is not None:
            results.append(rz)

        if not results:
            out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
        else:
            results.sort(key=lambda r: (r["weight"], 0 if r["basis"] == "x" else 1))
            r = results[0]
            out = {
                "status": "completed",
                "basis": r["basis"],
                "vector": bit_list(r["vector"], n),
                "upper_bound": int(r["weight"]),
            }

        os.makedirs(args.output_dir, exist_ok=True)
        print(json.dumps(out, separators=(",", ":")))
    except Exception:
        # Preserve the one-object JSON contract even on malformed public input.
        print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))


if __name__ == "__main__":
    main()
