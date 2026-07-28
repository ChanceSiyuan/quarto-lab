#!/usr/bin/python3
import argparse
import json
import random
import sys
from collections import defaultdict, deque


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        data = obj
        n_cols = max((len(r) for r in data), default=0)
        return rows_to_bits(data, n_cols), n_cols
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj["data"]
        n_cols = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        return rows_to_bits(data, n_cols), n_cols
    if "rows" in obj:
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n_cols:
                    x ^= 1 << c
            rows.append(x)
        return rows, n_cols
    raise ValueError(f"unrecognized matrix format in {path}")


def rows_to_bits(data, n_cols):
    rows = []
    for r in data:
        x = 0
        for i, v in enumerate(r[:n_cols]):
            if int(v) & 1:
                x ^= 1 << i
        rows.append(x)
    return rows


def bit_positions(x):
    while x:
        lsb = x & -x
        yield lsb.bit_length() - 1
        x ^= lsb


def gf2_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return y
        y ^= b
    return 0


def in_rowspace(x, rows):
    return reduce_by_basis(x, gf2_basis(rows)) == 0


def rref_rows(rows, n):
    basis = gf2_basis(rows)
    pivots = sorted(basis, reverse=True)
    # Back-eliminate so each pivot column appears in exactly one basis row.
    for p in pivots:
        row = basis[p]
        for q in pivots:
            if q < p and ((row >> q) & 1):
                row ^= basis[q]
        basis[p] = row
    return basis


def nullspace_basis(rows, n):
    rref = rref_rows(rows, n)
    pivot_cols = set(rref)
    free_cols = [c for c in range(n) if c not in pivot_cols]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in rref.items():
            if (row >> f) & 1:
                v ^= 1 << p
        out.append(v)
    return out


def syndrome(checks, v):
    s = 0
    for i, row in enumerate(checks):
        if ((row & v).bit_count() & 1):
            s ^= 1 << i
    return s


def verify(v, kernel_checks, stabilizer_basis, n):
    if v == 0 or (v >> n):
        return False
    if syndrome(kernel_checks, v) != 0:
        return False
    return reduce_by_basis(v, stabilizer_basis) != 0


def vector_json(v, n):
    return [(v >> i) & 1 for i in range(n)]


def build_check_adjacency(checks, n):
    q_to_checks = [[] for _ in range(n)]
    row_bits = []
    for ri, row in enumerate(checks):
        cols = list(bit_positions(row))
        row_bits.append(cols)
        for c in cols:
            if c < n:
                q_to_checks[c].append(ri)
    q_adj = [set() for _ in range(n)]
    for cols in row_bits:
        if len(cols) <= 1:
            continue
        for c in cols:
            q_adj[c].update(d for d in cols if d != c)
    return q_to_checks, row_bits, [list(s) for s in q_adj]


def sparse_repair(v, syn, q_to_checks, n, rng, max_steps):
    cur = v
    s = syn
    used = cur
    for _ in range(max_steps):
        if s == 0:
            return cur
        bad = list(bit_positions(s))
        scores = []
        bad_set = set(bad)
        for q in range(n):
            if (used >> q) & 1:
                continue
            touched = q_to_checks[q]
            if not touched:
                continue
            fixes = sum(1 for r in touched if r in bad_set)
            hurts = len(touched) - fixes
            gain = fixes - hurts
            if fixes:
                scores.append((gain, fixes, -len(touched), rng.random(), q))
        if not scores:
            return None
        scores.sort(reverse=True)
        top = scores[: min(8, len(scores))]
        _, _, _, _, q = rng.choice(top[: max(1, min(3, len(top)))])
        cur ^= 1 << q
        used |= 1 << q
        for r in q_to_checks[q]:
            s ^= 1 << r
    return cur if s == 0 else None


def restricted_null_candidates(cluster, checks, n, rng, limit=24):
    cols = sorted(cluster)
    if not cols:
        return []
    local_index = {c: i for i, c in enumerate(cols)}
    local_rows = []
    for row in checks:
        lr = 0
        x = row
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c in local_index:
                lr ^= 1 << local_index[c]
            x ^= lsb
        if lr:
            local_rows.append(lr)
    loc_basis = nullspace_basis(local_rows, len(cols))
    rng.shuffle(loc_basis)
    candidates = []
    for b in loc_basis[:limit]:
        v = 0
        for i in bit_positions(b):
            v ^= 1 << cols[i]
        candidates.append(v)
    for _ in range(min(limit, max(0, len(loc_basis) * 2))):
        vloc = 0
        for b in loc_basis:
            if rng.random() < 0.35:
                vloc ^= b
        if vloc:
            v = 0
            for i in bit_positions(vloc):
                v ^= 1 << cols[i]
            candidates.append(v)
    return candidates


def connected_cluster_search(checks, stabilizers, stabilizer_basis, n, rng):
    q_to_checks, _, q_adj = build_check_adjacency(checks, n)
    degrees = [len(q_to_checks[q]) for q in range(n)]
    seeds = list(range(n))
    rng.shuffle(seeds)
    seeds.sort(key=lambda q: (degrees[q], rng.random()))
    best = None
    max_cluster = min(n, max(18, int((n or 1) ** 0.5 * 10)))
    for seed in seeds[: min(n, 80)]:
        cluster = {seed}
        frontier = deque([seed])
        while frontier and len(cluster) < max_cluster:
            q = frontier.popleft()
            neigh = list(q_adj[q])
            rng.shuffle(neigh)
            neigh.sort(key=lambda x: (degrees[x], rng.random()))
            for nb in neigh[:6]:
                if nb not in cluster:
                    cluster.add(nb)
                    frontier.append(nb)
                    if len(cluster) >= max_cluster:
                        break
            if len(cluster) >= 2:
                for cand in restricted_null_candidates(cluster, checks, n, rng, limit=8):
                    if verify(cand, checks, stabilizer_basis, n):
                        if best is None or cand.bit_count() < best.bit_count():
                            best = cand
                raw = 0
                for c in cluster:
                    if rng.random() < 0.55:
                        raw ^= 1 << c
                if raw:
                    repaired = sparse_repair(raw, syndrome(checks, raw), q_to_checks, n, rng, max_steps=max(8, len(cluster) * 3))
                    if repaired is not None and verify(repaired, checks, stabilizer_basis, n):
                        if best is None or repaired.bit_count() < best.bit_count():
                            best = repaired
        if best is not None and best.bit_count() <= max(1, max_cluster // 3):
            break
    return best


def quotient_fallback(checks, stabilizers, n, rng):
    stab_basis = gf2_basis(stabilizers)
    ns = nullspace_basis(checks, n)
    rng.shuffle(ns)
    span = dict(stab_basis)
    logicals = []
    for v in ns:
        if reduce_by_basis(v, span) != 0:
            logicals.append(v)
            span = gf2_basis(list(span.values()) + [v])
    best = None
    for v in logicals:
        if verify(v, checks, stab_basis, n):
            best = v if best is None or v.bit_count() < best.bit_count() else best
    # Random coset descent: add stabilizers and accepted logical combinations
    # only after the algebraic fallback has found a non-stabilizer kernel vector.
    pool = [r for r in stabilizers if r] + logicals
    for base in logicals[: max(1, min(12, len(logicals)))]:
        cur = base
        improved = True
        while improved:
            improved = False
            rng.shuffle(pool)
            for r in pool:
                nxt = cur ^ r
                if nxt and nxt.bit_count() < cur.bit_count() and verify(nxt, checks, stab_basis, n):
                    cur = nxt
                    improved = True
        for _ in range(160):
            trial = cur
            for r in pool:
                if rng.random() < 0.08:
                    trial ^= r
            if verify(trial, checks, stab_basis, n):
                if trial.bit_count() < cur.bit_count() or rng.random() < 0.05:
                    cur = trial
        if verify(cur, checks, stab_basis, n):
            best = cur if best is None or cur.bit_count() < best.bit_count() else best
    return best


def solve_basis(name, hx, hz, n, rng):
    if name == "x":
        checks, stabilizers = hz, hx
    else:
        checks, stabilizers = hx, hz
    stabilizer_basis = gf2_basis(stabilizers)
    best = connected_cluster_search(checks, stabilizers, stabilizer_basis, n, rng)
    fb = quotient_fallback(checks, stabilizers, n, rng)
    if fb is not None and (best is None or fb.bit_count() < best.bit_count()):
        best = fb
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        rng = random.Random(args.seed)
        bx = solve_basis("x", hx, hz, n, rng)
        bz = solve_basis("z", hx, hz, n, rng)
        choices = []
        if bx is not None:
            choices.append(("x", bx))
        if bz is not None:
            choices.append(("z", bz))
        if choices:
            basis, vec = min(choices, key=lambda t: (t[1].bit_count(), 0 if t[0] == "x" else 1))
            out = {
                "status": "completed",
                "basis": basis,
                "vector": vector_json(vec, n),
                "upper_bound": int(vec.bit_count()),
            }
        else:
            out = {"status": "not_found", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "error", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
