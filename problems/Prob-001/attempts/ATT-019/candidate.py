#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time
from collections import deque


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
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
        data = obj.get("data", [])
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for i, v in enumerate(r):
                if int(v) & 1:
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
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def reduce_with_basis(x, basis):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(x, rows):
    return reduce_with_basis(x, gf2_basis(rows)) == 0


def rank_rows(rows):
    return len(gf2_basis(rows))


def gf2_reduced_basis(rows):
    basis = gf2_basis(rows)
    for p in sorted(basis.keys()):
        row = basis[p]
        for q in list(basis.keys()):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    return basis


def kernel_basis(rows, n):
    basis = gf2_reduced_basis(rows)
    pivots = sorted(basis.keys())
    pivot_set = set(pivots)
    free_cols = [i for i in range(n) if i not in pivot_set]
    out = []
    for f in free_cols:
        x = 1 << f
        for p in pivots:
            if (basis[p] >> f) & 1:
                x |= 1 << p
        out.append(x)
    return out


def syndrome(v, checks):
    s = 0
    for i, r in enumerate(checks):
        if ((v & r).bit_count() & 1) != 0:
            s |= 1 << i
    return s


def verify(v, checks, stabilizers, stab_basis=None):
    if v == 0 or syndrome(v, checks) != 0:
        return False
    if stab_basis is None:
        stab_basis = gf2_basis(stabilizers)
    return reduce_with_basis(v, stab_basis) != 0


def vector_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def build_column_data(checks, stabilizers, n):
    col_checks = [0] * n
    for ri, row in enumerate(checks):
        for c in bit_positions(row):
            if c < n:
                col_checks[c] |= 1 << ri
    check_to_cols = [list(bit_positions(r & ((1 << n) - 1))) for r in checks]
    col_stab_degree = [0] * n
    for row in stabilizers:
        for c in bit_positions(row):
            if c < n:
                col_stab_degree[c] += 1
    return col_checks, check_to_cols, col_stab_degree


def connected_cluster(seed, rng, col_checks, check_to_cols, n, max_size):
    seen = {seed}
    q = deque([seed])
    while q and len(seen) < max_size:
        c = q.popleft()
        nbrs = set()
        for chk in bit_positions(col_checks[c]):
            cols = check_to_cols[chk]
            if len(cols) <= 80:
                nbrs.update(cols)
            elif cols:
                nbrs.update(rng.sample(cols, min(12, len(cols))))
        nbrs.discard(c)
        nbrs = [x for x in nbrs if x not in seen]
        rng.shuffle(nbrs)
        for nb in nbrs[: max(1, 4 + rng.randrange(8))]:
            seen.add(nb)
            q.append(nb)
            if len(seen) >= max_size:
                break
    return list(seen)


def repair_to_kernel(v, checks, col_checks, rng, n, allowed=None, max_steps=2000):
    s = syndrome(v, checks)
    if s == 0:
        return v
    allowed_list = list(allowed) if allowed is not None else list(range(n))
    if not allowed_list:
        allowed_list = list(range(n))
    best_seen = s.bit_count()
    stagnant = 0
    for _ in range(max_steps):
        if s == 0:
            return v
        cur = s.bit_count()
        best_cols = []
        best_delta = -10**9
        sample = allowed_list
        if len(sample) > 160:
            hot = set()
            for chk in bit_positions(s):
                if chk < len(checks):
                    row = checks[chk]
                    for c in bit_positions(row):
                        hot.add(c)
                        if len(hot) > 120:
                            break
                if len(hot) > 120:
                    break
            sample = list(hot) if hot else rng.sample(allowed_list, 160)
            if len(sample) > 180:
                sample = rng.sample(sample, 180)
        for c in sample:
            ns = s ^ col_checks[c]
            delta = cur - ns.bit_count()
            if delta > best_delta:
                best_delta = delta
                best_cols = [c]
            elif delta == best_delta:
                best_cols.append(c)
        if best_delta <= 0:
            stagnant += 1
            if stagnant > 12 and len(allowed_list) < n:
                allowed_list = list(range(n))
            c = rng.choice(best_cols if best_cols else allowed_list)
        else:
            stagnant = 0
            c = rng.choice(best_cols)
        v ^= 1 << c
        s ^= col_checks[c]
        if s.bit_count() < best_seen:
            best_seen = s.bit_count()
            stagnant = 0
    return v if syndrome(v, checks) == 0 else None


def stabilizer_descent(v, checks, stabilizers, rng, n, stab_basis=None):
    if stab_basis is None:
        stab_basis = gf2_basis(stabilizers)
    if not verify(v, checks, stabilizers, stab_basis):
        return None
    rows = [r for r in stabilizers if r]
    improved = True
    passes = 0
    while improved and passes < 8:
        passes += 1
        improved = False
        rng.shuffle(rows)
        for r in rows:
            nv = v ^ r
            if nv and nv.bit_count() < v.bit_count() and verify(nv, checks, stabilizers, stab_basis):
                v = nv
                improved = True
        pairs = min(300, len(rows) * 2)
        for _ in range(pairs):
            if len(rows) < 2:
                break
            a, b = rng.sample(rows, 2)
            nv = v ^ a ^ b
            if nv and nv.bit_count() < v.bit_count() and verify(nv, checks, stabilizers, stab_basis):
                v = nv
                improved = True
    return v


def fallback_witness(checks, stabilizers, n, rng):
    kb = kernel_basis(checks, n)
    stab_basis = gf2_basis(stabilizers)
    logicals = []
    span_basis = dict(stab_basis)
    for v in sorted(kb, key=lambda x: x.bit_count()):
        rem = reduce_with_basis(v, span_basis)
        if rem:
            logicals.append(v)
            p = rem.bit_length() - 1
            span_basis[p] = rem
    if not logicals:
        return None
    best = None
    for v in logicals:
        if verify(v, checks, stabilizers, stab_basis):
            d = stabilizer_descent(v, checks, stabilizers, rng, n, stab_basis)
            if d is not None and (best is None or d.bit_count() < best.bit_count()):
                best = d
    for _ in range(min(512, 32 * max(1, len(logicals)))):
        v = 0
        for b in logicals:
            if rng.getrandbits(1):
                v ^= b
        if v and verify(v, checks, stabilizers, stab_basis):
            d = stabilizer_descent(v, checks, stabilizers, rng, n, stab_basis)
            if d is not None and (best is None or d.bit_count() < best.bit_count()):
                best = d
    return best


def cluster_search(checks, stabilizers, n, seed, time_budget):
    rng = random.Random(seed)
    col_checks, check_to_cols, col_stab_degree = build_column_data(checks, stabilizers, n)
    stab_basis = gf2_basis(stabilizers)
    columns = list(range(n))
    columns.sort(key=lambda c: (col_checks[c].bit_count(), col_stab_degree[c], rng.random()))
    best = None
    start = time.time()
    attempts = 0
    while time.time() - start < time_budget and attempts < 1800:
        attempts += 1
        if attempts <= len(columns):
            seed_col = columns[attempts - 1]
        else:
            seed_col = rng.choice(columns) if columns else 0
        if n == 0:
            break
        cap = max(4, min(n, 6 + int((attempts ** 0.55)) + rng.randrange(max(2, min(n, 24)))))
        cluster = connected_cluster(seed_col, rng, col_checks, check_to_cols, n, cap)
        rng.shuffle(cluster)
        take = 1 + rng.randrange(max(1, min(len(cluster), 10)))
        support = cluster[:take]
        v = 0
        for c in support:
            v ^= 1 << c
        allowed = set(cluster)
        for c in cluster:
            for chk in bit_positions(col_checks[c]):
                if chk < len(check_to_cols):
                    cols = check_to_cols[chk]
                    if len(cols) <= 40:
                        allowed.update(cols)
                    elif cols:
                        allowed.update(rng.sample(cols, min(10, len(cols))))
        repaired = repair_to_kernel(v, checks, col_checks, rng, n, allowed=allowed, max_steps=250 + 4 * len(allowed))
        if repaired is None:
            continue
        if verify(repaired, checks, stabilizers, stab_basis):
            d = stabilizer_descent(repaired, checks, stabilizers, rng, n, stab_basis)
            if d is not None and (best is None or d.bit_count() < best.bit_count()):
                best = d
        elif stabilizers:
            # A repaired cluster often lands in a nearby stabilizer.  Nudge it by
            # sparse stabilizer rows and repair again to probe adjacent cosets.
            for row in rng.sample(stabilizers, min(len(stabilizers), 3)):
                repaired2 = repair_to_kernel(repaired ^ row, checks, col_checks, rng, n, allowed=allowed, max_steps=200)
                if repaired2 is not None and verify(repaired2, checks, stabilizers, stab_basis):
                    d = stabilizer_descent(repaired2, checks, stabilizers, rng, n, stab_basis)
                    if d is not None and (best is None or d.bit_count() < best.bit_count()):
                        best = d
    return best


def solve_basis(name, checks, stabilizers, n, seed, time_budget):
    rng = random.Random(seed ^ (0x9E3779B97F4A7C15 if name == "z" else 0xD1B54A32D192ED03))
    best = cluster_search(checks, stabilizers, n, rng.randrange(1 << 62), time_budget * 0.65)
    fb = fallback_witness(checks, stabilizers, n, rng)
    if fb is not None and (best is None or fb.bit_count() < best.bit_count()):
        best = fb
    return best


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
        mask = (1 << n) - 1 if n > 0 else 0
        hx = [r & mask for r in hx]
        hz = [r & mask for r in hz]

        os.makedirs(args.output_dir, exist_ok=True)
        seed = int(args.seed)
        start = time.time()
        # X logicals commute with Z checks and are modulo X stabilizers; Z is dual.
        x = solve_basis("x", hz, hx, n, seed, 7.0)
        elapsed = time.time() - start
        z_budget = max(2.0, 10.0 - elapsed)
        z = solve_basis("z", hx, hz, n, seed + 1, z_budget)

        choices = []
        if x is not None and verify(x, hz, hx):
            choices.append(("x", x))
        if z is not None and verify(z, hx, hz):
            choices.append(("z", z))
        if choices:
            basis, v = min(choices, key=lambda item: item[1].bit_count())
            result = {
                "status": "completed",
                "basis": basis,
                "vector": vector_list(v, n),
                "upper_bound": int(v.bit_count()),
            }
        else:
            result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
