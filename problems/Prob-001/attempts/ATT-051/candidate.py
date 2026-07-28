#!/usr/bin/env python3
import argparse
import json
import random
import sys
from collections import deque


def fail():
    print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))
    sys.exit(0)


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for row in data:
            m = 0
            for j, v in enumerate(row):
                if int(v) & 1:
                    m ^= 1 << j
            rows.append(m)
        return rows, n
    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n == 0:
            n = max((max(r) + 1 for r in obj["rows"] if r), default=0)
        rows = []
        for row in obj["rows"]:
            m = 0
            for j in row:
                j = int(j)
                if 0 <= j < n:
                    m ^= 1 << j
            rows.append(m)
        return rows, n
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for row in obj:
            m = 0
            for j, v in enumerate(row):
                if int(v) & 1:
                    m ^= 1 << j
            rows.append(m)
        return rows, n
    raise ValueError("unsupported matrix JSON")


def rank_basis(rows):
    basis = {}
    for x in rows:
        x = int(x)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def in_span(x, basis):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        x ^= b
    return True


def kernel_basis(rows, n):
    piv = rank_basis(rows)
    pivot_cols = set(piv)
    out = []
    for f in range(n):
        if f in pivot_cols:
            continue
        v = 1 << f
        for p in sorted(piv):
            row = piv[p]
            if (row & v).bit_count() & 1:
                v ^= 1 << p
        out.append(v)
    return out


def syndrome(mask, check_rows):
    s = 0
    for i, row in enumerate(check_rows):
        if (mask & row).bit_count() & 1:
            s |= 1 << i
    return s


def columns_as_syndromes(check_rows, n):
    cols = [0] * n
    col_checks = [[] for _ in range(n)]
    check_cols = [[] for _ in check_rows]
    for i, row in enumerate(check_rows):
        x = row
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            cols[j] |= 1 << i
            col_checks[j].append(i)
            check_cols[i].append(j)
            x ^= lsb
    return cols, col_checks, check_cols


def solve_column_subset(col_syn, indices, target):
    if target == 0:
        return 0
    basis = {}
    comb = {}
    for j in indices:
        v = col_syn[j]
        c = 1 << j
        while v:
            p = v.bit_length() - 1
            if p in basis:
                v ^= basis[p]
                c ^= comb[p]
            else:
                basis[p] = v
                comb[p] = c
                break
    v = target
    c = 0
    while v:
        p = v.bit_length() - 1
        if p not in basis:
            return None
        v ^= basis[p]
        c ^= comb[p]
    return c


def vector_from_mask(mask, n):
    return [(mask >> i) & 1 for i in range(n)]


def is_kernel(mask, check_rows):
    for row in check_rows:
        if (mask & row).bit_count() & 1:
            return False
    return True


def verified(mask, check_rows, stab_basis):
    return mask != 0 and is_kernel(mask, check_rows) and not in_span(mask, stab_basis)


def greedy_stabilizer_reduce(mask, stab_rows, check_rows, stab_basis, rounds=3):
    if not verified(mask, check_rows, stab_basis):
        return mask
    rows = [r for r in stab_rows if r]
    if not rows:
        return mask
    cur = mask
    for _ in range(rounds):
        changed = False
        random.shuffle(rows)
        rows.sort(key=lambda r: ((cur ^ r).bit_count() - cur.bit_count(), r.bit_count()))
        for r in rows:
            nxt = cur ^ r
            if nxt and nxt.bit_count() < cur.bit_count() and verified(nxt, check_rows, stab_basis):
                cur = nxt
                changed = True
        if not changed:
            break
    return cur


def bfs_cluster(seed, col_checks, check_cols, rng, max_cols, jitter=0.35):
    chosen = {seed}
    q = deque([seed])
    while q and len(chosen) < max_cols:
        c = q.popleft()
        checks = list(col_checks[c])
        rng.shuffle(checks)
        for chk in checks:
            neigh = list(check_cols[chk])
            neigh.sort(key=lambda x: len(col_checks[x]) + rng.random() * jitter)
            for nb in neigh:
                if nb not in chosen and rng.random() < 0.82:
                    chosen.add(nb)
                    q.append(nb)
                    if len(chosen) >= max_cols:
                        break
            if len(chosen) >= max_cols:
                break
    return list(chosen)


def expand_columns(cols, col_checks, check_cols, rng, hops):
    seen = set(cols)
    frontier = set(cols)
    for _ in range(hops):
        nxt = set()
        for c in frontier:
            for chk in col_checks[c]:
                for nb in check_cols[chk]:
                    if nb not in seen:
                        seen.add(nb)
                        nxt.add(nb)
        frontier = nxt
        if not frontier:
            break
    out = list(seen)
    rng.shuffle(out)
    return out


def randomized_cluster_search(check_rows, stab_rows, n, rng, budget):
    stab_basis = rank_basis(stab_rows)
    col_syn, col_checks, check_cols = columns_as_syndromes(check_rows, n)
    all_cols = list(range(n))
    degrees = [len(col_checks[i]) for i in range(n)]
    seeds = sorted(all_cols, key=lambda i: (degrees[i], rng.random()))
    best = None
    global_limit = min(n, 700)
    for t in range(budget):
        if t < len(seeds):
            seed = seeds[t]
        else:
            weights = [1.0 / (1 + degrees[i]) for i in all_cols]
            seed = rng.choices(all_cols, weights=weights, k=1)[0]
        base = 2 + (t % 11)
        span = 1 << min(7, (t // max(1, n)) % 8)
        max_cols = min(n, base + rng.randrange(1, max(2, span + 1)))
        cluster = bfs_cluster(seed, col_checks, check_cols, rng, max_cols)
        if not cluster:
            continue
        mask = 0
        for c in cluster:
            if rng.random() < 0.68:
                mask ^= 1 << c
        if mask == 0:
            mask = 1 << seed
        target = syndrome(mask, check_rows)
        candidate = mask
        if target:
            repair_pool = expand_columns(cluster, col_checks, check_cols, rng, 1 + (t % 3))
            if len(repair_pool) > global_limit:
                repair_pool = repair_pool[:global_limit]
            fix = solve_column_subset(col_syn, repair_pool, target)
            if fix is None and n <= global_limit:
                fix = solve_column_subset(col_syn, all_cols, target)
            if fix is None:
                continue
            candidate ^= fix
        if verified(candidate, check_rows, stab_basis):
            candidate = greedy_stabilizer_reduce(candidate, stab_rows, check_rows, stab_basis, 2)
            if best is None or candidate.bit_count() < best.bit_count():
                best = candidate
                if best.bit_count() <= 2:
                    break
    return best


def fallback_logical(check_rows, stab_rows, n, rng):
    stab_basis = rank_basis(stab_rows)
    kb = kernel_basis(check_rows, n)
    best = None
    acc = 0
    for v in sorted(kb, key=lambda x: x.bit_count()):
        acc ^= v
        for cand in (v, acc):
            if verified(cand, check_rows, stab_basis):
                cand = greedy_stabilizer_reduce(cand, stab_rows, check_rows, stab_basis, 4)
                if best is None or cand.bit_count() < best.bit_count():
                    best = cand
    if best is not None:
        return best
    for _ in range(max(64, 8 * len(kb))):
        cand = 0
        for v in kb:
            if rng.getrandbits(1):
                cand ^= v
        if verified(cand, check_rows, stab_basis):
            cand = greedy_stabilizer_reduce(cand, stab_rows, check_rows, stab_basis, 4)
            if best is None or cand.bit_count() < best.bit_count():
                best = cand
    return best


def choose_witness(hx, hz, n, seed):
    rng = random.Random(seed)
    choices = []
    # X logicals commute with Z checks and are quotiented by X stabilizers.
    for name, checks, stabs in (("x", hz, hx), ("z", hx, hz)):
        rank_checks = len(rank_basis(checks))
        rank_stabs = len(rank_basis(stabs))
        if n - rank_checks - rank_stabs <= 0:
            continue
        budget = min(2500, max(300, 30 * n + 8 * len(checks)))
        found = randomized_cluster_search(checks, stabs, n, random.Random(rng.randrange(1 << 62)), budget)
        fb = fallback_logical(checks, stabs, n, random.Random(rng.randrange(1 << 62)))
        for cand in (found, fb):
            if cand is not None and verified(cand, checks, rank_basis(stabs)):
                choices.append((cand.bit_count(), rng.random(), name, cand))
    if not choices:
        return None
    choices.sort(key=lambda x: (x[0], x[1]))
    return choices[0][2], choices[0][3]


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
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        ans = choose_witness(hx, hz, n, args.seed)
        if ans is None:
            fail()
        basis, mask = ans
        out = {
            "status": "completed",
            "basis": basis,
            "vector": vector_from_mask(mask, n),
            "upper_bound": int(mask.bit_count()),
        }
        print(json.dumps(out, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
