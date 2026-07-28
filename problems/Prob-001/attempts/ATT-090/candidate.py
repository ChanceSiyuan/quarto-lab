#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time
from collections import defaultdict, deque


def popcount(x):
    return int(x.bit_count())


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", 0))
        if n <= 0 and data:
            n = max(len(r) for r in data)
        rows = []
        for r in data:
            m = 0
            for i, bit in enumerate(r):
                if bit & 1:
                    m |= 1 << i
            rows.append(m)
        return rows, n
    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            m = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    m |= 1 << c
                    if c + 1 > n:
                        n = c + 1
            rows.append(m)
        return rows, n
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            m = 0
            for i, bit in enumerate(r):
                if bit & 1:
                    m |= 1 << i
            rows.append(m)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def add_to_basis(basis, row):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def make_basis(rows):
    basis = {}
    for r in rows:
        if r:
            add_to_basis(basis, r)
    return basis


def in_span(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        y ^= b
    return True


def rref_rows(rows, n):
    rows = [r for r in rows if r]
    out = []
    pivots = []
    r = 0
    for c in range(n):
        bit = 1 << c
        piv = None
        for i in range(r, len(rows)):
            if rows[i] & bit:
                piv = i
                break
        if piv is None:
            continue
        rows[r], rows[piv] = rows[piv], rows[r]
        for i in range(len(rows)):
            if i != r and (rows[i] & bit):
                rows[i] ^= rows[r]
        out.append(rows[r])
        pivots.append(c)
        r += 1
        if r == len(rows):
            break
    return out, pivots


def nullspace(rows, n):
    rr, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    by_pivot = {p: row for p, row in zip(pivots, rr)}
    basis = []
    for f in range(n):
        if f in pivot_set:
            continue
        x = 1 << f
        for p in reversed(pivots):
            if by_pivot[p] & (1 << f):
                x |= 1 << p
        basis.append(x)
    return basis


def kernel_ok(v, check_rows):
    for r in check_rows:
        if popcount(v & r) & 1:
            return False
    return True


def verify(v, check_rows, stab_basis):
    return v != 0 and kernel_ok(v, check_rows) and not in_span(v, stab_basis)


def logical_reps(check_rows, stab_rows, n):
    ns = nullspace(check_rows, n)
    span = make_basis(stab_rows)
    reps = []
    for v in ns:
        if not in_span(v, span):
            reps.append(v)
            add_to_basis(span, v)
    return reps


def weighted_cost(v, target, n):
    allmask = (1 << n) - 1
    return popcount(v & target) + 4 * popcount(v & (allmask ^ target))


def polish_with_stabilizers(v, stab_rows, rng, n, target=None, passes=4):
    rows = [r for r in stab_rows if r]
    if not rows:
        return v
    cur = v
    for _ in range(passes):
        rng.shuffle(rows)
        changed = False
        for s in rows:
            nxt = cur ^ s
            if target is None:
                better = popcount(nxt) < popcount(cur)
            else:
                better = (
                    weighted_cost(nxt, target, n),
                    popcount(nxt),
                ) < (
                    weighted_cost(cur, target, n),
                    popcount(cur),
                )
            if better:
                cur = nxt
                changed = True
        if not changed:
            break
    return cur


def tanner_adjacency(check_rows, n, max_check_degree=80):
    var_checks = [[] for _ in range(n)]
    check_vars = []
    for ci, row in enumerate(check_rows):
        vs = []
        x = row
        while x:
            lb = x & -x
            v = lb.bit_length() - 1
            vs.append(v)
            var_checks[v].append(ci)
            x ^= lb
        check_vars.append(vs)
    return var_checks, check_vars, max_check_degree


def neighbor_vars(v, var_checks, check_vars, max_check_degree):
    seen = set()
    for c in var_checks[v]:
        vs = check_vars[c]
        if len(vs) > max_check_degree:
            continue
        for u in vs:
            if u != v and u not in seen:
                seen.add(u)
                yield u


def make_cycle_targets(var_checks, check_vars, n, rng, budget=256):
    pair_checks = defaultdict(list)
    for ci, vs in enumerate(check_vars):
        if 2 <= len(vs) <= 40:
            if len(vs) > 14:
                vs = rng.sample(vs, 14)
            for i in range(len(vs)):
                a = vs[i]
                for b in vs[i + 1:]:
                    if a > b:
                        a, b = b, a
                    key = (a, b)
                    if len(pair_checks[key]) < 3:
                        pair_checks[key].append(ci)
    targets = []
    for (a, b), cs in pair_checks.items():
        if len(cs) >= 2:
            mask = (1 << a) | (1 << b)
            for c in cs[:2]:
                for v in check_vars[c]:
                    mask |= 1 << v
            targets.append(mask)
    rng.shuffle(targets)
    if len(targets) > budget:
        targets = targets[:budget]
    while len(targets) < min(budget, max(8, n)):
        start = rng.randrange(n) if n else 0
        q = deque([start])
        seen = {start}
        limit = rng.randint(4, min(max(4, n), 24))
        while q and len(seen) < limit:
            v = q.popleft()
            ns = list(neighbor_vars(v, var_checks, check_vars, 80))
            rng.shuffle(ns)
            for u in ns[:8]:
                if u not in seen:
                    seen.add(u)
                    q.append(u)
                if len(seen) >= limit:
                    break
        mask = 0
        for v in seen:
            mask |= 1 << v
        if mask:
            targets.append(mask)
    return targets


def local_kernel_candidates(target, check_rows, n, rng, max_vars=56, tries=10):
    cols = []
    x = target
    while x:
        lb = x & -x
        cols.append(lb.bit_length() - 1)
        x ^= lb
    if len(cols) < 2:
        return []
    if len(cols) > max_vars:
        cols = rng.sample(cols, max_vars)
    col_index = {c: i for i, c in enumerate(cols)}
    local_rows = []
    support_mask = 0
    for c in cols:
        support_mask |= 1 << c
    for r in check_rows:
        rr = r & support_mask
        if rr:
            m = 0
            y = rr
            while y:
                lb = y & -y
                m |= 1 << col_index[lb.bit_length() - 1]
                y ^= lb
            local_rows.append(m)
    ns = nullspace(local_rows, len(cols))
    out = []
    for b in ns[:24]:
        g = 0
        y = b
        while y:
            lb = y & -y
            g |= 1 << cols[lb.bit_length() - 1]
            y ^= lb
        out.append(g)
    if ns:
        for _ in range(tries):
            g_local = 0
            for b in ns:
                if rng.random() < 0.35:
                    g_local ^= b
            if g_local:
                g = 0
                y = g_local
                while y:
                    lb = y & -y
                    g |= 1 << cols[lb.bit_length() - 1]
                    y ^= lb
                out.append(g)
    return out


def search_basis(name, check_rows, stab_rows, n, seed):
    rng = random.Random(seed)
    stab_basis = make_basis(stab_rows)
    reps = logical_reps(check_rows, stab_rows, n)
    if not reps:
        return None
    best = None

    def consider(v):
        nonlocal best
        if verify(v, check_rows, stab_basis):
            v = polish_with_stabilizers(v, stab_rows, rng, n, None, 6)
            if verify(v, check_rows, stab_basis):
                if best is None or popcount(v) < popcount(best):
                    best = v

    for r in reps:
        consider(r)
        consider(polish_with_stabilizers(r, stab_rows, rng, n, None, 8))

    var_checks, check_vars, max_deg = tanner_adjacency(check_rows, n)
    targets = make_cycle_targets(var_checks, check_vars, n, rng, 192)

    deadline = time.time() + 18.0
    for target in targets:
        if time.time() > deadline:
            break
        for cand in local_kernel_candidates(target, check_rows, n, rng):
            consider(cand)
        for r in rng.sample(reps, min(len(reps), 6)):
            biased = polish_with_stabilizers(r, stab_rows, rng, n, target, 5)
            consider(biased)

    rounds = 0
    while time.time() <= deadline and rounds < 360:
        rounds += 1
        v = 0
        take = 1 + int(rng.expovariate(0.85))
        for r in rng.sample(reps, min(len(reps), take)):
            v ^= r
        if not v:
            continue
        if targets and rng.random() < 0.7:
            target = rng.choice(targets)
            v = polish_with_stabilizers(v, stab_rows, rng, n, target, 4)
        consider(v)

    if best is None:
        for r in reps:
            if verify(r, check_rows, stab_basis):
                best = r
                break
    if best is None:
        return None
    return {"basis": name, "vector": [(best >> i) & 1 for i in range(n)], "upper_bound": popcount(best)}


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()
    hx, nx = parse_matrix(args.hx)
    hz, nz = parse_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1) for r in hx]
    hz = [r & ((1 << n) - 1) for r in hz]

    results = []
    xres = search_basis("x", hz, hx, n, args.seed ^ 0x58C1C3)
    if xres is not None:
        results.append(xres)
    zres = search_basis("z", hx, hz, n, args.seed ^ 0xA93B7D)
    if zres is not None:
        results.append(zres)
    if results:
        results.sort(key=lambda d: (d["upper_bound"], d["basis"]))
        out = results[0]
        emit({"status": "completed", "basis": out["basis"], "vector": out["vector"], "upper_bound": out["upper_bound"]})
    else:
        emit({"status": "failed", "basis": None, "vector": [], "upper_bound": None})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit({"status": "failed", "basis": None, "vector": [], "upper_bound": None})
