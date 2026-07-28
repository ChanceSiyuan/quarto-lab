#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
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

    if "data" in obj and "n_cols" in obj:
        n = int(obj["n_cols"])
        data = obj["data"]
        rows = []
        if data and all(not isinstance(x, list) for x in data):
            if n <= 0:
                return [], 0
            data = [data[i:i + n] for i in range(0, len(data), n)]
        for r in data:
            x = 0
            for i, b in enumerate(r[:n]):
                if int(b) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if "rows" in obj and ("num_cols" in obj or "n_cols" in obj):
        n = int(obj.get("num_cols", obj.get("n_cols")))
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


def parity(x):
    return x.bit_count() & 1


def add_to_basis(basis, row):
    x = row
    while x:
        p = x.bit_length() - 1
        if p in basis:
            x ^= basis[p]
        else:
            for q, r in list(basis.items()):
                if (r >> p) & 1:
                    basis[q] = r ^ x
            basis[p] = x
            return True
    return False


def rref_basis(rows):
    basis = {}
    for r in rows:
        if r:
            add_to_basis(basis, r)
    return basis


def in_span(row, basis):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        x ^= b
    return True


def nullspace_basis(rows, n):
    basis = rref_basis(rows)
    pivots = set(basis)
    free = [i for i in range(n) if i not in pivots]
    out = []
    for f in free:
        v = 1 << f
        for p, r in basis.items():
            if (r >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(checks, v):
    for r in checks:
        if parity(r & v):
            return False
    return True


def verified(checks, stabilizers, v):
    if not v:
        return False
    return syndrome_zero(checks, v) and not in_span(v, rref_basis(stabilizers))


def quotient_logicals(checks, stabilizers, n):
    stab_basis = rref_basis(stabilizers)
    span = dict(stab_basis)
    logicals = []
    for k in sorted(nullspace_basis(checks, n), key=lambda x: (x.bit_count(), x)):
        if k and not in_span(k, span):
            logicals.append(k)
            add_to_basis(span, k)
    return logicals


def row_columns(row):
    cols = []
    x = row
    while x:
        lsb = x & -x
        cols.append(lsb.bit_length() - 1)
        x ^= lsb
    return cols


def build_reliability(checks, stabilizers, n, rng, current):
    deg = [0] * n
    for r in checks:
        x = r
        while x:
            lsb = x & -x
            deg[lsb.bit_length() - 1] += 2
            x ^= lsb
    for r in stabilizers:
        x = r
        while x:
            lsb = x & -x
            deg[lsb.bit_length() - 1] += 1
            x ^= lsb

    rel = [0.0] * n
    for i in range(n):
        channel = 0.65 if ((current >> i) & 1) else -0.15
        prior = 1.0 / math.sqrt(1.0 + deg[i])
        rel[i] = abs(channel + prior + rng.gauss(0.0, 0.75))

    # A few zero-syndrome min-sum style check updates: bits participating in
    # checks whose other bits look reliable become reliable themselves.
    for _ in range(2):
        nxt = rel[:]
        for r in checks:
            cols = row_columns(r)
            if len(cols) < 2:
                continue
            vals = sorted((rel[c], c) for c in cols)
            m1, c1 = vals[0]
            m2 = vals[1][0]
            for c in cols:
                nxt[c] += 0.08 * (m2 if c == c1 else m1)
        rel = nxt
    return rel


def weighted_gain(row, v, rel, cols_cache):
    gain = 0.0
    for c in cols_cache[row]:
        if (v >> c) & 1:
            gain += rel[c]
        else:
            gain -= rel[c]
    return gain


def minimize_coset(start, checks, stabilizers, n, rng, deadline):
    usable = [r for r in stabilizers if r and syndrome_zero(checks, r)]
    if not usable:
        return start

    cols_cache = {r: row_columns(r) for r in usable}
    v = start
    best = v

    # Plain greedy descent is the reliable first pass.
    improved = True
    while improved and time.time() < deadline:
        improved = False
        rng.shuffle(usable)
        for r in usable:
            nv = v ^ r
            if nv.bit_count() < v.bit_count():
                v = nv
                improved = True
                if v.bit_count() < best.bit_count():
                    best = v

    # Reliability-ordered restarts accept weighted-improving moves and
    # occasional neutral/uphill moves to escape greedy traps.
    restarts = 18 + min(42, max(0, n // 8))
    for t in range(restarts):
        if time.time() >= deadline:
            break
        v = start
        rel = build_reliability(checks, usable, n, rng, v)
        temperature = 0.35 + 0.08 * (t % 7)
        for _ in range(2 + min(10, len(usable) // 6)):
            if time.time() >= deadline:
                break
            scored = []
            for r in usable:
                g = weighted_gain(r, v, rel, cols_cache)
                d = (v ^ r).bit_count() - v.bit_count()
                jitter = rng.random() * (0.25 + temperature)
                scored.append((-(g - 0.25 * d + jitter), r))
            scored.sort()
            moved = False
            for _, r in scored[: max(8, min(len(scored), 64))]:
                nv = v ^ r
                d = nv.bit_count() - v.bit_count()
                g = weighted_gain(r, v, rel, cols_cache)
                if d < 0 or g > temperature or rng.random() < math.exp(-max(0, d) / (1.0 + temperature)):
                    v = nv
                    moved = True
                    if v.bit_count() < best.bit_count():
                        best = v
                    break
            if not moved:
                break
            if rng.random() < 0.35:
                rel = build_reliability(checks, usable, n, rng, v)
    return best


def search_basis(name, checks, stabilizers, n, rng, deadline):
    logicals = quotient_logicals(checks, stabilizers, n)
    if not logicals:
        return None

    candidates = []
    for g in logicals[: min(len(logicals), 64)]:
        candidates.append(g)

    rounds = 80 + min(220, 8 * len(logicals) + n)
    for _ in range(rounds):
        if time.time() >= deadline:
            break
        v = 0
        # Heavy-tailed subset size gives both single-generator and broad
        # quotient probes without enumerating the logical space.
        p = min(0.55, max(0.08, 1.0 / (1.0 + rng.expovariate(1.0))))
        for g in logicals:
            if rng.random() < p:
                v ^= g
        if v == 0:
            v = rng.choice(logicals)
        candidates.append(v)

    best = None
    for c in sorted(candidates, key=lambda x: (x.bit_count(), rng.random())):
        if time.time() >= deadline:
            break
        v = minimize_coset(c, checks, stabilizers, n, rng, deadline)
        if verified(checks, stabilizers, v):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    # Guaranteed basis-derived fallback for positive-k inputs.
    if best is None:
        for g in logicals:
            if verified(checks, stabilizers, g):
                best = g
                break

    if best is None:
        return None
    return {"basis": name, "vector_int": best, "upper_bound": best.bit_count()}


def int_to_bits(v, n):
    return [1 if ((v >> i) & 1) else 0 for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    mask = (1 << n) - 1 if n > 0 else 0
    hx = [r & mask for r in hx]
    hz = [r & mask for r in hz]
    os.makedirs(args.output_dir, exist_ok=True)

    deadline = time.time() + 24.0
    results = []
    order = [("x", hz, hx), ("z", hx, hz)]
    if rng.random() < 0.5:
        order.reverse()
    for name, checks, stabs in order:
        res = search_basis(name, checks, stabs, n, rng, deadline)
        if res is not None:
            results.append(res)

    if results:
        best = min(results, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
        out = {
            "status": "completed",
            "basis": best["basis"],
            "vector": int_to_bits(best["vector_int"], n),
            "upper_bound": best["upper_bound"],
        }
    else:
        out = {"status": "failed", "basis": "x", "vector": [0] * n, "upper_bound": 0}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        n = 0
        print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": 0}, separators=(",", ":")))
