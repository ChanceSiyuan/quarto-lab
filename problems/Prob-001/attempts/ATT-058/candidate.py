#!/usr/bin/env python3
import argparse
import json
import os
import random
import time
from collections import deque


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
        if not n and data:
            n = max(len(r) for r in data)
        rows = []
        for r in data:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x ^= 1 << i
            rows.append(x)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    x ^= 1 << c
            rows.append(x)
        if not n:
            n = 1 + max((c for r in obj["rows"] for c in r), default=-1)
        return rows, n

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x ^= 1 << i
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def row_reduce(rows):
    piv = {}
    for value in rows:
        x = int(value)
        while x:
            p = x.bit_length() - 1
            y = piv.get(p)
            if y is None:
                piv[p] = x
                break
            x ^= y
    # Normalize so every pivot appears in only one basis row. This makes
    # membership tests and coordinate construction deterministic.
    for p in sorted(piv):
        for q in sorted(piv):
            if q != p and ((piv[q] >> p) & 1):
                piv[q] ^= piv[p]
    return piv


def reduce_by_pivots(x, piv):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        y = piv.get(p)
        if y is None:
            return x
        x ^= y
    return 0


def in_span(x, piv):
    return reduce_by_pivots(x, piv) == 0


def nullspace_basis(rows, n):
    piv = row_reduce(rows)
    pivot_cols = set(piv)
    basis = []
    for free in range(n):
        if free in pivot_cols:
            continue
        x = 1 << free
        for p, row in piv.items():
            if (row >> free) & 1:
                x ^= 1 << p
        basis.append(x)
    return basis


def syndrome_zero(x, checks):
    for r in checks:
        if ((x & r).bit_count() & 1) != 0:
            return False
    return True


def bit_list(x, n):
    return [(x >> i) & 1 for i in range(n)]


def columns_from_rows(rows, n):
    cols = [[] for _ in range(n)]
    for ri, row in enumerate(rows):
        x = row
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c < n:
                cols[c].append(ri)
            x ^= lsb
    return cols


def build_check_graph(cols, m, rng, max_edges_per_var=10):
    graph = [[] for _ in range(m)]
    for v, checks in enumerate(cols):
        d = len(checks)
        if d < 2:
            continue
        pairs = []
        if d * (d - 1) // 2 <= max_edges_per_var:
            for i in range(d):
                for j in range(i + 1, d):
                    pairs.append((checks[i], checks[j]))
        else:
            local = checks[:]
            rng.shuffle(local)
            for i in range(min(max_edges_per_var, d)):
                pairs.append((local[i], local[(i + 1) % d]))
        for a, b in pairs:
            graph[a].append((b, v))
            graph[b].append((a, v))
    return graph


def find_cycle_seed(graph, rng, max_depth):
    m = len(graph)
    if m == 0:
        return 0
    starts = [i for i, e in enumerate(graph) if e]
    if not starts:
        return 0
    start = rng.choice(starts)
    first_edges = graph[start][:]
    rng.shuffle(first_edges)
    for mid, first_var in first_edges[:8]:
        q = deque([(mid, -1, 0, 0)])
        seen = {(mid, first_var)}
        while q:
            node, prev_var, mask, depth = q.popleft()
            if depth >= max_depth:
                continue
            nbrs = graph[node][:]
            rng.shuffle(nbrs)
            for nxt, var in nbrs[:24]:
                if var == first_var or var == prev_var:
                    continue
                newmask = mask ^ (1 << var)
                if nxt == start:
                    return newmask ^ (1 << first_var)
                key = (nxt, var)
                if key not in seen:
                    seen.add(key)
                    q.append((nxt, var, newmask, depth + 1))
    return 0


def repair_to_kernel(mask, checks, cols, n, rng, max_steps):
    odd = set()
    for i, r in enumerate(checks):
        if ((mask & r).bit_count() & 1) != 0:
            odd.add(i)
    if not odd:
        return mask

    for _ in range(max_steps):
        if not odd:
            return mask
        sample = list(odd)
        rng.shuffle(sample)
        best = None
        best_score = None
        for chk in sample[: min(12, len(sample))]:
            row = checks[chk]
            candidates = []
            x = row
            while x:
                lsb = x & -x
                candidates.append(lsb.bit_length() - 1)
                x ^= lsb
            if not candidates:
                continue
            rng.shuffle(candidates)
            for v in candidates[:24]:
                toggled = cols[v]
                removes = sum(1 for c in toggled if c in odd)
                score = removes - (len(toggled) - removes) - 0.025 * (((mask >> v) & 1) * -1 + 1)
                if best is None or score > best_score:
                    best = v
                    best_score = score
        if best is None:
            break
        mask ^= 1 << best
        for c in cols[best]:
            if c in odd:
                odd.remove(c)
            else:
                odd.add(c)
    return mask if not odd else 0


def greedy_coset_reduce(x, stab_rows, protected, rng, passes=4):
    if not x:
        return x
    rows = [r for r in stab_rows if r and not (r & protected)]
    all_rows = [r for r in stab_rows if r]
    cur = x
    for _ in range(passes):
        changed = False
        rng.shuffle(rows)
        for r in rows:
            y = cur ^ r
            if y.bit_count() < cur.bit_count():
                cur = y
                changed = True
        if not changed:
            break
    for temp in (2.0, 1.2, 0.7):
        rng.shuffle(all_rows)
        for r in all_rows[: min(len(all_rows), 256)]:
            y = cur ^ r
            dy = y.bit_count() - cur.bit_count()
            if dy <= 0 or rng.random() < pow(2.718281828, -dy / temp) * 0.02:
                cur = y
    for _ in range(2):
        changed = False
        rng.shuffle(all_rows)
        for r in all_rows:
            y = cur ^ r
            if y.bit_count() < cur.bit_count():
                cur = y
                changed = True
        if not changed:
            break
    return cur


def logical_from_nullspace(target_rows, stab_rows, n, rng):
    stab_piv = row_reduce(stab_rows)
    ns = nullspace_basis(target_rows, n)
    best = 0
    for b in ns:
        if b and not in_span(b, stab_piv):
            y = greedy_coset_reduce(b, stab_rows, 0, rng, passes=6)
            if y and not in_span(y, stab_piv) and (not best or y.bit_count() < best.bit_count()):
                best = y
    for _ in range(min(800, 40 + 8 * len(ns))):
        x = 0
        for b in ns:
            if rng.getrandbits(1):
                x ^= b
        if x and not in_span(x, stab_piv):
            y = greedy_coset_reduce(x, stab_rows, 0, rng, passes=4)
            if y and not in_span(y, stab_piv) and (not best or y.bit_count() < best.bit_count()):
                best = y
    return best


def cycle_trap_search(target_rows, stab_rows, n, rng, deadline):
    stab_piv = row_reduce(stab_rows)
    cols = columns_from_rows(target_rows, n)
    graph = build_check_graph(cols, len(target_rows), rng)
    best = 0
    seeds = []

    for v, checks in enumerate(cols):
        if 1 <= len(checks) <= 3:
            seeds.append(1 << v)
    rng.shuffle(seeds)
    seeds = seeds[:128]

    rounds = 0
    while time.time() < deadline and rounds < 1600:
        rounds += 1
        if rng.random() < 0.55:
            mask = find_cycle_seed(graph, rng, max_depth=4 + (rounds % 7))
        elif seeds:
            mask = 0
            for s in rng.sample(seeds, min(len(seeds), rng.randint(1, 5))):
                mask ^= s
            mask = repair_to_kernel(mask, target_rows, cols, n, rng, max_steps=80)
        else:
            mask = 0

        if not mask or not syndrome_zero(mask, target_rows):
            continue
        if in_span(mask, stab_piv):
            # Escape a stabilizer cycle by joining it with one or two nearby
            # repaired trapping-set seeds while preserving the target syndrome.
            for _ in range(2):
                extra = 0
                if seeds:
                    for s in rng.sample(seeds, min(len(seeds), rng.randint(1, 4))):
                        extra ^= s
                extra = repair_to_kernel(extra, target_rows, cols, n, rng, max_steps=60)
                if extra and syndrome_zero(extra, target_rows):
                    mask ^= extra
        if mask and syndrome_zero(mask, target_rows) and not in_span(mask, stab_piv):
            y = greedy_coset_reduce(mask, stab_rows, 0, rng, passes=3)
            if y and syndrome_zero(y, target_rows) and not in_span(y, stab_piv):
                if not best or y.bit_count() < best.bit_count():
                    best = y
    return best


def solve_basis(name, target_rows, stab_rows, n, rng, deadline):
    candidates = []
    cyc = cycle_trap_search(target_rows, stab_rows, n, rng, deadline)
    if cyc:
        candidates.append(cyc)
    fb = logical_from_nullspace(target_rows, stab_rows, n, rng)
    if fb:
        candidates.append(fb)
    stab_piv = row_reduce(stab_rows)
    valid = [
        x for x in candidates
        if x and syndrome_zero(x, target_rows) and not in_span(x, stab_piv)
    ]
    if not valid:
        return None
    return name, min(valid, key=lambda z: z.bit_count())


def emit(status, basis, vector, upper_bound):
    print(json.dumps({
        "status": status,
        "basis": basis,
        "vector": vector,
        "upper_bound": upper_bound,
    }, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        os.makedirs(args.output_dir, exist_ok=True)

        deadline = time.time() + 18.0
        answers = []
        bx = solve_basis("x", hz, hx, n, rng, deadline)
        if bx:
            answers.append(bx)
        bz = solve_basis("z", hx, hz, n, rng, deadline)
        if bz:
            answers.append(bz)

        if not answers:
            emit("failed", None, [], None)
            return 0
        basis, vec = min(answers, key=lambda item: item[1].bit_count())
        emit("completed", basis, bit_list(vec, n), vec.bit_count())
        return 0
    except Exception:
        emit("failed", None, [], None)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
