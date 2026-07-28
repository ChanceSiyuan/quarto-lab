#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def fail():
    print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))


def read_matrix_arg(value):
    text = value
    if value.startswith("@"):
        with open(value[1:], "r", encoding="utf-8") as f:
            text = f.read()
    elif os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            text = f.read()
    obj = json.loads(text)
    if isinstance(obj, list):
        if not obj:
            return [], 0
        n = len(obj[0])
        rows = []
        for row in obj:
            bits = 0
            for j, b in enumerate(row):
                if int(b) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "rows" in obj and ("num_cols" in obj or "n_cols" in obj):
        n = int(obj.get("num_cols", obj.get("n_cols")))
        rows = []
        for row in obj["rows"]:
            bits = 0
            for j in row:
                jj = int(j)
                if 0 <= jj < n:
                    bits |= 1 << jj
            rows.append(bits)
        return rows, n
    if "data" in obj and "n_cols" in obj:
        n = int(obj["n_cols"])
        data = obj["data"]
        rows = []
        if data and all(isinstance(r, (list, tuple)) for r in data):
            for row in data:
                bits = 0
                for j, b in enumerate(row[:n]):
                    if int(b) & 1:
                        bits |= 1 << j
                rows.append(bits)
        else:
            flat = [int(x) & 1 for x in data]
            for i in range(0, len(flat), n):
                bits = 0
                for j, b in enumerate(flat[i:i + n]):
                    if b:
                        bits |= 1 << j
                rows.append(bits)
        return rows, n
    raise ValueError("unsupported matrix format")


def popcount(x):
    return x.bit_count()


def rows_dot_zero(check_rows, v):
    for r in check_rows:
        if popcount(r & v) & 1:
            return False
    return True


def reduce_by_basis(v, basis):
    x = v
    while x:
        hb = x.bit_length() - 1
        b = basis.get(hb)
        if b is None:
            return x
        x ^= b
    return 0


def build_row_basis(rows):
    basis = {}
    for row in rows:
        x = reduce_by_basis(row, basis)
        if x:
            basis[x.bit_length() - 1] = x
    return basis


def in_rowspace(v, basis):
    return reduce_by_basis(v, basis) == 0


def rref_rows(rows, n):
    a = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        pivot = None
        for i in range(rank, len(a)):
            if (a[i] >> col) & 1:
                pivot = i
                break
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        for i in range(len(a)):
            if i != rank and ((a[i] >> col) & 1):
                a[i] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == len(a):
            break
    return a[:rank], pivots


def kernel_basis(rows, n):
    rref, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    out = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for i, p in enumerate(pivots):
            if (rref[i] >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def logical_basis(kernel, stabilizers):
    stab_basis = build_row_basis(stabilizers)
    span = dict(stab_basis)
    logicals = []
    for v in sorted(kernel, key=lambda x: (popcount(x), x)):
        if reduce_by_basis(v, span):
            logicals.append(v)
            x = reduce_by_basis(v, span)
            span[x.bit_length() - 1] = x
    return logicals, stab_basis


def bits_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def adjacency_from_rows(rows, n):
    adj = [set() for _ in range(n)]
    for r in rows:
        cols = []
        x = r
        while x:
            lsb = x & -x
            cols.append(lsb.bit_length() - 1)
            x ^= lsb
        if 1 < len(cols) <= 80:
            for i, c in enumerate(cols):
                adj[c].update(cols[:i])
                adj[c].update(cols[i + 1:])
    return [list(s) for s in adj]


def greedy_coset_descent(v, stabilizers, rng, passes):
    if not stabilizers:
        return v
    cur = v
    rows = list(stabilizers)
    for _ in range(passes):
        improved = False
        rng.shuffle(rows)
        for r in rows:
            nv = cur ^ r
            if popcount(nv) < popcount(cur):
                cur = nv
                improved = True
        if not improved:
            break
    return cur


def focused_walk(v, stabilizers, adj, rng, deadline):
    cur = greedy_coset_descent(v, stabilizers, rng, 6)
    best = cur
    if not stabilizers:
        return best
    incident = {}
    for r in stabilizers:
        x = r
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            incident.setdefault(c, []).append(r)
            x ^= lsb
    temperature = 2.5
    stale = 0
    while time.monotonic() < deadline:
        support = []
        x = cur
        while x:
            lsb = x & -x
            support.append(lsb.bit_length() - 1)
            x ^= lsb
        if support and rng.random() < 0.75:
            c = rng.choice(support)
            pool = incident.get(c, stabilizers)
            row = rng.choice(pool)
        else:
            row = rng.choice(stabilizers)
        nxt = cur ^ row
        delta = popcount(nxt) - popcount(cur)
        if delta <= 0 or rng.random() < pow(2.718281828459045, -delta / max(0.05, temperature)):
            cur = nxt
            if rng.random() < 0.25 and adj:
                cur = neighbor_nudge(cur, incident, adj, rng)
            cur = greedy_coset_descent(cur, stabilizers, rng, 2)
            stale += 1
            if popcount(cur) < popcount(best):
                best = cur
                stale = 0
        else:
            stale += 1
        temperature *= 0.997
        if stale > 180:
            cur = best
            temperature = 1.0 + 2.0 * rng.random()
            stale = 0
    return best


def neighbor_nudge(v, incident, adj, rng):
    support = []
    x = v
    while x:
        lsb = x & -x
        support.append(lsb.bit_length() - 1)
        x ^= lsb
    if not support:
        return v
    c = rng.choice(support)
    neigh = adj[c] if c < len(adj) else []
    if neigh:
        c = rng.choice(neigh)
    rows = incident.get(c)
    if not rows:
        return v
    return v ^ rng.choice(rows)


def minimize_candidate(v, logicals, stabilizers, adj, rng, deadline):
    best = focused_walk(v, stabilizers, adj, rng, deadline)
    # Syndrome-preserving translations by alternate logical representatives
    # explore nearby nonzero logical cosets, then each coset is walked through
    # its stabilizer orbit.
    while time.monotonic() < deadline:
        trial = best
        flips = 1 + rng.randrange(min(4, max(1, len(logicals))))
        for _ in range(flips):
            trial ^= rng.choice(logicals)
        if trial:
            local_deadline = min(deadline, time.monotonic() + 0.01)
            trial = focused_walk(trial, stabilizers, adj, rng, local_deadline)
            if trial and popcount(trial) < popcount(best):
                best = trial
    return best


def verify(v, n, checks, stab_basis):
    mask = (1 << n) - 1
    return 0 < v <= mask and rows_dot_zero(checks, v) and not in_rowspace(v, stab_basis)


def search_one(name, checks, stabilizers, n, seed, seconds):
    rng = random.Random(seed)
    kern = kernel_basis(checks, n)
    logicals, stab_basis = logical_basis(kern, stabilizers)
    if not logicals:
        return None
    adj = adjacency_from_rows(stabilizers + checks, n)
    deadline = time.monotonic() + seconds
    seeds = list(logicals)
    for _ in range(min(64, 8 * len(logicals) + 8)):
        v = 0
        for g in logicals:
            if rng.random() < 0.35:
                v ^= g
        if v:
            seeds.append(v)
    best = None
    for v in sorted(seeds, key=lambda x: (popcount(x), rng.random())):
        if time.monotonic() >= deadline:
            break
        local_deadline = min(deadline, time.monotonic() + max(0.015, seconds / max(4, len(seeds))))
        cand = minimize_candidate(v, logicals, stabilizers, adj, rng, local_deadline)
        if verify(cand, n, checks, stab_basis):
            if best is None or popcount(cand) < popcount(best):
                best = cand
    if best is None:
        # Reliable basis-derived fallback: logical_basis already selected
        # kernel vectors that increase span beyond the stabilizer row space.
        for v in logicals:
            cand = greedy_coset_descent(v, stabilizers, rng, 10)
            if verify(cand, n, checks, stab_basis):
                best = cand
                break
    if best is None:
        return None
    return {"basis": name, "vector": bits_to_list(best, n), "upper_bound": popcount(best)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()
    try:
        hx, nx = read_matrix_arg(args.hx)
        hz, nz = read_matrix_arg(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        os.makedirs(args.output_dir, exist_ok=True)
        per_basis = 0.75
        xres = search_one("x", hz, hx, n, args.seed ^ 0x58A5, per_basis)
        zres = search_one("z", hx, hz, n, args.seed ^ 0x5A17, per_basis)
        choices = [r for r in (xres, zres) if r is not None]
        if not choices:
            fail()
            return
        best = min(choices, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
        print(json.dumps({"status": "completed", **best}, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
