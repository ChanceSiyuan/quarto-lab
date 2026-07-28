#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from collections import deque


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            x = 0
            for i, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for i, v in enumerate(r):
                if i < n and (int(v) & 1):
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    x |= 1 << c
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def weight(x):
    return int(x.bit_count())


def rref_dict(rows):
    piv = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            if p in piv:
                x ^= piv[p]
            else:
                piv[p] = x
                break

    keys = sorted(piv)
    for p in keys:
        prow = piv[p]
        for q in list(piv.keys()):
            if q != p and ((piv[q] >> p) & 1):
                piv[q] ^= prow
    return {p: r for p, r in piv.items() if r}


def in_rowspace(x, piv):
    y = int(x)
    while y:
        p = y.bit_length() - 1
        row = piv.get(p)
        if row is None:
            return False
        y ^= row
    return True


def nullspace_basis(rows, n):
    piv = rref_dict(rows)
    pivot_cols = set(piv)
    basis = []
    for f in range(n):
        if f in pivot_cols:
            continue
        v = 1 << f
        for p, row in piv.items():
            if (row >> f) & 1:
                v |= 1 << p
        basis.append(v)
    return basis


def mat_vec_zero(rows, v):
    for r in rows:
        if ((r & v).bit_count() & 1) != 0:
            return False
    return True


def verify(v, kernel_rows, stab_piv, n):
    if v <= 0 or (v >> n):
        return False
    return mat_vec_zero(kernel_rows, v) and not in_rowspace(v, stab_piv)


def int_to_vec(v, n):
    return [1 if ((v >> i) & 1) else 0 for i in range(n)]


def restricted_rows(rows, cols):
    pos = {c: i for i, c in enumerate(cols)}
    out = []
    for r in rows:
        x = 0
        y = r
        while y:
            lb = y & -y
            c = lb.bit_length() - 1
            j = pos.get(c)
            if j is not None:
                x |= 1 << j
            y ^= lb
        if x:
            out.append(x)
    return out


def lift(local_v, cols):
    v = 0
    j = 0
    x = local_v
    while x:
        lb = x & -x
        j = lb.bit_length() - 1
        v |= 1 << cols[j]
        x ^= lb
    return v


def row_supports(rows):
    supps = []
    for r in rows:
        s = []
        x = r
        while x:
            lb = x & -x
            s.append(lb.bit_length() - 1)
            x ^= lb
        supps.append(s)
    return supps


def build_check_index(rows, n):
    supps = row_supports(rows)
    col_checks = [[] for _ in range(n)]
    for i, s in enumerate(supps):
        for c in s:
            if 0 <= c < n:
                col_checks[c].append(i)
    return supps, col_checks


def greedy_stabilizer_reduce(v, stab_rows, kernel_rows, stab_piv, n, rng):
    if not verify(v, kernel_rows, stab_piv, n):
        return v
    rows = [r for r in stab_rows if r]
    rows.sort(key=weight)
    best = v
    improved = True
    while improved:
        improved = False
        order = rows[:]
        rng.shuffle(order)
        order.sort(key=lambda r: weight(best ^ r) - weight(best))
        for r in order:
            u = best ^ r
            if u and weight(u) < weight(best) and verify(u, kernel_rows, stab_piv, n):
                best = u
                improved = True
    return best


def try_cluster(cols, kernel_rows, stab_rows, stab_piv, n, rng):
    cols = sorted(cols)
    if not cols:
        return None
    local_rows = restricted_rows(kernel_rows, cols)
    ns = nullspace_basis(local_rows, len(cols))
    if not ns:
        return None

    probes = []
    if len(ns) <= 8:
        for mask in range(1, 1 << len(ns)):
            x = 0
            for i, b in enumerate(ns):
                if (mask >> i) & 1:
                    x ^= b
            probes.append(x)
    else:
        for b in ns:
            probes.append(b)
        for _ in range(96):
            x = 0
            take = 1 + rng.randrange(min(10, len(ns)))
            for i in rng.sample(range(len(ns)), take):
                x ^= ns[i]
            probes.append(x)

    best = None
    rng.shuffle(probes)
    probes.sort(key=weight)
    for x in probes[:160]:
        v = lift(x, cols)
        if verify(v, kernel_rows, stab_piv, n):
            v = greedy_stabilizer_reduce(v, stab_rows, kernel_rows, stab_piv, n, rng)
            if best is None or weight(v) < weight(best):
                best = v
    return best


def cluster_search(kernel_rows, stab_rows, n, rng):
    stab_piv = rref_dict(stab_rows)
    check_supps, col_checks = build_check_index(kernel_rows, n)
    degrees = [len(col_checks[c]) for c in range(n)]
    active = [c for c in range(n) if degrees[c] > 0]
    if not active:
        active = list(range(n))
    if not active:
        return None

    best = None
    max_size = min(n, max(18, int(4 * (sum(degrees) / max(1, n) + 1))))
    max_size = min(max_size, 96)
    attempts = min(900, max(160, 8 * n))

    seed_pool = sorted(range(n), key=lambda c: (degrees[c], c))
    seed_pool = seed_pool[: max(1, min(n, max(40, n // 3)))]

    for t in range(attempts):
        if best is not None and t > attempts // 3:
            max_size_now = min(max_size, max(8, weight(best) + 8))
        else:
            max_size_now = max_size

        seed = rng.choice(seed_pool) if rng.random() < 0.65 else rng.randrange(n)
        cluster = {seed}
        frontier = set()
        for chk in col_checks[seed]:
            frontier.update(check_supps[chk])
        frontier.discard(seed)

        target = rng.randint(4, max(4, max_size_now))
        while len(cluster) < target and frontier:
            candidates = list(frontier)
            candidates.sort(key=lambda c: (degrees[c], rng.random()))
            pick = candidates[0] if rng.random() < 0.72 else rng.choice(candidates[: min(12, len(candidates))])
            frontier.discard(pick)
            cluster.add(pick)
            for chk in col_checks[pick]:
                # Sparsity-aware repair: when a check is almost closed by the
                # current cluster, preferentially add its missing low-degree bits.
                supp = check_supps[chk]
                missing = [c for c in supp if c not in cluster]
                if len(missing) <= 2 and len(cluster) + len(missing) <= max_size_now:
                    cluster.update(missing)
                    for m in missing:
                        frontier.discard(m)
                for c in supp:
                    if c not in cluster:
                        frontier.add(c)

        trial_clusters = [cluster]
        boundary = set(cluster)
        for c in list(cluster):
            for chk in col_checks[c]:
                boundary.update(check_supps[chk])
        if len(boundary) <= max_size_now + 12:
            trial_clusters.append(boundary)

        for cols in trial_clusters:
            if len(cols) > max_size_now + 12:
                continue
            v = try_cluster(cols, kernel_rows, stab_rows, stab_piv, n, rng)
            if v is not None and (best is None or weight(v) < weight(best)):
                best = v
    return best


def random_basis_combine(ns, rowspace_piv, kernel_rows, stab_rows, n, rng, rounds):
    best = None
    if not ns:
        return None
    for b in sorted(ns, key=weight):
        if verify(b, kernel_rows, rowspace_piv, n):
            best = b if best is None or weight(b) < weight(best) else best
            break
    for _ in range(rounds):
        v = 0
        if rng.random() < 0.7:
            k = 1 + rng.randrange(min(len(ns), 12))
            picks = rng.sample(range(len(ns)), k)
        else:
            picks = [i for i in range(len(ns)) if rng.random() < 0.08]
            if not picks:
                picks = [rng.randrange(len(ns))]
        for i in picks:
            v ^= ns[i]
        if verify(v, kernel_rows, rowspace_piv, n):
            v = greedy_stabilizer_reduce(v, stab_rows, kernel_rows, rowspace_piv, n, rng)
            if best is None or weight(v) < weight(best):
                best = v
    return best


def fallback_logical(kernel_rows, stab_rows, n, rng):
    stab_piv = rref_dict(stab_rows)
    ns = nullspace_basis(kernel_rows, n)
    best = random_basis_combine(ns, stab_piv, kernel_rows, stab_rows, n, rng, 600)
    if best is not None:
        return best

    # Deterministic quotient fallback: scan prefixes of the kernel basis until
    # a vector outside the stabilizer row-space appears.
    v = 0
    for b in sorted(ns, key=weight):
        if verify(b, kernel_rows, stab_piv, n):
            return greedy_stabilizer_reduce(b, stab_rows, kernel_rows, stab_piv, n, rng)
        v ^= b
        if verify(v, kernel_rows, stab_piv, n):
            return greedy_stabilizer_reduce(v, stab_rows, kernel_rows, stab_piv, n, rng)
    return None


def solve_basis(name, kernel_rows, stab_rows, n, rng):
    stab_piv = rref_dict(stab_rows)
    best = cluster_search(kernel_rows, stab_rows, n, rng)
    if best is not None and verify(best, kernel_rows, stab_piv, n):
        return name, best
    best = fallback_logical(kernel_rows, stab_rows, n, rng)
    if best is not None and verify(best, kernel_rows, stab_piv, n):
        return name, best
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    try:
        hx, nx = parse_matrix(args.hx)
        hz, nz = parse_matrix(args.hz)
        n = max(nx, nz)
        os.makedirs(args.output_dir, exist_ok=True)

        results = []
        for name, kernel, stab in (("x", hz, hx), ("z", hx, hz)):
            b, v = solve_basis(name, kernel, stab, n, rng)
            if v is not None:
                results.append((weight(v), b, v))

        if results:
            _, basis, v = min(results, key=lambda item: item[0])
            out = {
                "status": "completed",
                "basis": basis,
                "vector": int_to_vec(v, n),
                "upper_bound": weight(v),
            }
        else:
            out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
