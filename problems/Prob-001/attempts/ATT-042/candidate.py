#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from collections import deque


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", 0))
        rows = []
        for row in data:
            x = 0
            if n == 0:
                n = len(row)
            for j, bit in enumerate(row):
                if bit & 1:
                    x ^= 1 << j
            rows.append(x)
        return rows, n
    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for cols in obj.get("rows", []):
            x = 0
            for j in cols:
                j = int(j)
                if j >= 0:
                    x ^= 1 << j
                    if j + 1 > n:
                        n = j + 1
            rows.append(x)
        return rows, n
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for row in obj:
            x = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    x ^= 1 << j
            rows.append(x)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def weight(x):
    return int(x.bit_count())


def parity(x):
    return x.bit_count() & 1


def rref(rows):
    basis = {}
    for v in rows:
        x = int(v)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= basis[p]
    return basis


def reduce_by_basis(x, basis):
    y = int(x)
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            break
        y ^= b
    return y


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    rb = rref(rows)
    pivots = set(rb)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        x = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                x ^= 1 << p
        out.append(x)
    return out


def syndrome(v, checks):
    s = 0
    for i, row in enumerate(checks):
        if parity(v & row):
            s ^= 1 << i
    return s


def column_syndromes(rows, n):
    cols = [0] * n
    for i, row in enumerate(rows):
        x = row
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            cols[j] ^= 1 << i
            x ^= lsb
    return cols


def solve_column_combination(target, col_syn):
    # Finds some qubit set with the requested syndrome, if one exists.
    basis = {}
    comb = {}
    for j, s in enumerate(col_syn):
        x = s
        c = 1 << j
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
                c ^= comb[p]
            else:
                basis[p] = x
                comb[p] = c
                break
    x = target
    c = 0
    while x:
        p = x.bit_length() - 1
        if p not in basis:
            return None
        x ^= basis[p]
        c ^= comb[p]
    return c


def bit_positions(x):
    while x:
        lsb = x & -x
        yield lsb.bit_length() - 1
        x ^= lsb


def build_adjacency(checks, n):
    var_to_checks = [[] for _ in range(n)]
    check_to_vars = [[] for _ in checks]
    for i, row in enumerate(checks):
        for j in bit_positions(row):
            if j < n:
                check_to_vars[i].append(j)
                var_to_checks[j].append(i)
    return var_to_checks, check_to_vars


def find_cycle_seed(start, var_to_checks, check_to_vars, rng, max_nodes=80):
    parent = {("v", start): None}
    q = deque([("v", start)])
    while q and len(parent) < max_nodes:
        typ, idx = q.popleft()
        if typ == "v":
            neigh = [("c", c) for c in var_to_checks[idx]]
        else:
            vs = check_to_vars[idx][:]
            rng.shuffle(vs)
            neigh = [("v", v) for v in vs]
        rng.shuffle(neigh)
        for node in neigh:
            if parent.get((typ, idx)) == node:
                continue
            if node in parent:
                a = path_to_root((typ, idx), parent)
                b = path_to_root(node, parent)
                return support_from_cycle(a, b)
            parent[node] = (typ, idx)
            q.append(node)
    return 1 << start


def path_to_root(node, parent):
    p = []
    while node is not None:
        p.append(node)
        node = parent[node]
    return p


def support_from_cycle(a, b):
    seen = set(a)
    meet = next((x for x in b if x in seen), None)
    nodes = []
    for x in a:
        nodes.append(x)
        if x == meet:
            break
    tail = []
    for x in b:
        tail.append(x)
        if x == meet:
            break
    nodes.extend(reversed(tail[:-1]))
    s = 0
    for typ, idx in nodes:
        if typ == "v":
            s ^= 1 << idx
    return s


def grow_trapping_seed(n, var_to_checks, check_to_vars, rng, steps):
    deg = [len(v) for v in var_to_checks]
    start = min(rng.sample(range(n), min(n, 12)), key=lambda j: (deg[j], rng.random()))
    support = 1 << start
    odd = set(var_to_checks[start])
    frontier = set()
    for c in odd:
        frontier.update(check_to_vars[c])
    frontier.discard(start)
    for _ in range(steps):
        if not frontier:
            break
        sample = rng.sample(list(frontier), min(len(frontier), 24))
        def score(j):
            touched = var_to_checks[j]
            fixes = sum(1 for c in touched if c in odd)
            creates = len(touched) - fixes
            return (creates - fixes, deg[j], rng.random())
        j = min(sample, key=score)
        support ^= 1 << j
        for c in var_to_checks[j]:
            if c in odd:
                odd.remove(c)
            else:
                odd.add(c)
            frontier.update(check_to_vars[c])
        for v in list(bit_positions(support)):
            frontier.discard(v)
        if not odd and weight(support) > 0:
            break
    return support


def minimize_by_stabilizers(v, stabilizers, rng, passes=6):
    if not stabilizers:
        return v
    cur = v
    rows = [r for r in stabilizers if r]
    for t in range(passes):
        rng.shuffle(rows)
        changed = False
        for r in rows:
            nr = cur ^ r
            if nr and (weight(nr) < weight(cur) or (t > 2 and weight(nr) == weight(cur) and rng.random() < 0.04)):
                cur = nr
                changed = True
        if not changed:
            break
    return cur


def logical_fallback(null_basis, stab_basis, stabilizers, rng):
    best = None
    span_basis = dict(stab_basis)
    logicals = []
    for v in sorted(null_basis, key=weight):
        rem = reduce_by_basis(v, span_basis)
        if rem:
            logicals.append(v)
            span_basis = rref(list(span_basis.values()) + [v])
    pool = logicals or null_basis[:]
    for v in pool:
        cand = minimize_by_stabilizers(v, stabilizers, rng, passes=10)
        if cand and not in_rowspace(cand, stab_basis):
            if best is None or weight(cand) < weight(best):
                best = cand
    for _ in range(min(256, 16 * max(1, len(pool)))):
        x = 0
        for v in pool:
            if rng.random() < 0.35:
                x ^= v
        if x:
            x = minimize_by_stabilizers(x, stabilizers, rng, passes=8)
            if x and not in_rowspace(x, stab_basis):
                if best is None or weight(x) < weight(best):
                    best = x
    return best


def search_basis(name, commute_checks, stabilizers, n, rng, budget):
    stab_basis = rref(stabilizers)
    null_basis = nullspace_basis(commute_checks, n)
    if not null_basis:
        return None
    col_syn = column_syndromes(commute_checks, n)
    var_to_checks, check_to_vars = build_adjacency(commute_checks, n)
    best = None

    def consider(seed):
        nonlocal best
        repair = solve_column_combination(syndrome(seed, commute_checks), col_syn)
        if repair is None:
            return
        cand = seed ^ repair
        cand = minimize_by_stabilizers(cand, stabilizers, rng, passes=7)
        if cand and syndrome(cand, commute_checks) == 0 and not in_rowspace(cand, stab_basis):
            if best is None or weight(cand) < weight(best):
                best = cand

    low_degree = sorted(range(n), key=lambda j: len(var_to_checks[j]) + rng.random())[:max(1, min(n, 32))]
    for j in low_degree:
        consider(1 << j)
    for _ in range(budget):
        if rng.random() < 0.55 and n:
            j = rng.randrange(n)
            seed = find_cycle_seed(j, var_to_checks, check_to_vars, rng)
        else:
            seed = grow_trapping_seed(n, var_to_checks, check_to_vars, rng, rng.randint(2, max(3, min(18, n))))
        if rng.random() < 0.25:
            for _k in range(rng.randint(1, 3)):
                seed ^= 1 << rng.randrange(n)
        consider(seed)
    fb = logical_fallback(null_basis, stab_basis, stabilizers, rng)
    if fb is not None and syndrome(fb, commute_checks) == 0:
        if best is None or weight(fb) < weight(best):
            best = fb
    return best


def to_list(v, n):
    return [(v >> j) & 1 for j in range(n)]


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
        rng = random.Random(args.seed)
        os.makedirs(args.output_dir, exist_ok=True)
        budget = 140 + min(260, 5 * n)
        bx = search_basis("x", hz, hx, n, random.Random(rng.randrange(1 << 62)), budget)
        bz = search_basis("z", hx, hz, n, random.Random(rng.randrange(1 << 62)), budget)
        choices = []
        if bx is not None:
            choices.append(("x", bx, hz, rref(hx)))
        if bz is not None:
            choices.append(("z", bz, hx, rref(hz)))
        choices = [c for c in choices if syndrome(c[1], c[2]) == 0 and not in_rowspace(c[1], c[3])]
        if choices:
            basis, vec, _checks, _stab = min(choices, key=lambda c: (weight(c[1]), 0 if c[0] == "x" else 1))
            out = {"status": "completed", "basis": basis, "vector": to_list(vec, n), "upper_bound": weight(vec)}
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
