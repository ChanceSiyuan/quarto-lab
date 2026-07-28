#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def read_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        return [row_to_mask(r, n) for r in data], n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", obj.get("num_cols", max((len(r) for r in data), default=0))))
        return [row_to_mask(r, n) for r in data], n
    if "rows" in obj:
        rows = obj.get("rows", [])
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        masks = []
        for r in rows:
            mask = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    mask ^= 1 << c
            masks.append(mask)
        return masks, n
    raise ValueError(f"unrecognized matrix JSON format: {path}")


def row_to_mask(row, n):
    mask = 0
    for i, v in enumerate(row[:n]):
        if int(v) & 1:
            mask |= 1 << i
    return mask


def parity(x):
    return x.bit_count() & 1


def rank_rows(rows, n):
    basis = {}
    for x in rows:
        x &= (1 << n) - 1
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return len(basis)


def rowspace_basis(rows, n):
    basis = {}
    for x in rows:
        x &= (1 << n) - 1
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def in_rowspace(x, basis):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        x ^= b
    return True


def kernel_basis(checks, n):
    rows = [r & ((1 << n) - 1) for r in checks if r]
    piv = {}
    for r in rows:
        x = r
        while x:
            p = x.bit_length() - 1
            if p in piv:
                x ^= piv[p]
            else:
                piv[p] = x
                break
    pivot_cols = set(piv)
    free_cols = [c for c in range(n) if c not in pivot_cols]
    basis = []
    for f in free_cols:
        v = 1 << f
        for p in sorted(piv):
            if parity(piv[p] & v):
                v |= 1 << p
        basis.append(v)
    return basis


def syndrome(v, checks):
    s = 0
    for i, r in enumerate(checks):
        if parity(v & r):
            s |= 1 << i
    return s


def column_syndromes(checks, n):
    cols = [0] * n
    for i, r in enumerate(checks):
        x = r
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            cols[j] |= 1 << i
            x ^= lsb
    return cols


def solve_syndrome_random(cols, target, n, m, rng, weights=None):
    if target == 0:
        return 0
    order = list(range(n))
    if weights is None:
        rng.shuffle(order)
    else:
        jittered = [(weights[j] + rng.random() * 0.75, rng.random(), j) for j in order]
        jittered.sort(reverse=True)
        order = [j for _, _, j in jittered]

    equations = []
    for i in range(m):
        eq = 0
        for pos, j in enumerate(order):
            if (cols[j] >> i) & 1:
                eq |= 1 << pos
        if (target >> i) & 1:
            eq |= 1 << n
        equations.append(eq)

    pivots = []
    row = 0
    for col in range(n):
        sel = None
        bit = 1 << col
        for r in range(row, m):
            if equations[r] & bit:
                sel = r
                break
        if sel is None:
            continue
        equations[row], equations[sel] = equations[sel], equations[row]
        for r in range(m):
            if r != row and (equations[r] & bit):
                equations[r] ^= equations[row]
        pivots.append((row, col))
        row += 1
        if row == m:
            break

    varmask = (1 << n) - 1
    for eq in equations:
        if (eq & varmask) == 0 and ((eq >> n) & 1):
            return None

    pivot_cols = {c for _, c in pivots}
    sol_perm = 0
    free_prob = rng.choice((0.015, 0.03, 0.06, 0.10, 0.16))
    for c in range(n):
        if c not in pivot_cols and rng.random() < free_prob:
            sol_perm |= 1 << c
    for r, c in reversed(pivots):
        rhs = (equations[r] >> n) & 1
        tail = equations[r] & varmask & ~(1 << c)
        if parity(tail & sol_perm) ^ rhs:
            sol_perm |= 1 << c
        else:
            sol_perm &= ~(1 << c)

    sol = 0
    x = sol_perm
    while x:
        lsb = x & -x
        pos = lsb.bit_length() - 1
        sol |= 1 << order[pos]
        x ^= lsb
    return sol


def vector_from_mask(v, n):
    return [(v >> i) & 1 for i in range(n)]


def is_logical(v, checks, stab_basis):
    return v != 0 and syndrome(v, checks) == 0 and not in_rowspace(v, stab_basis)


def logical_basis(checks, stabilizers, n):
    stab_basis = rowspace_basis(stabilizers, n)
    out = []
    span = dict(stab_basis)
    for v in sorted(kernel_basis(checks, n), key=lambda x: x.bit_count()):
        if not in_rowspace(v, span):
            out.append(v)
            y = v
            while y:
                p = y.bit_length() - 1
                if p in span:
                    y ^= span[p]
                else:
                    span[p] = y
                    break
    return out


def reduce_by_stabilizers(v, stabilizers, checks, stab_basis, rng, deadline):
    if not is_logical(v, checks, stab_basis):
        return None
    rows = [r for r in stabilizers if r]
    best = v
    improved = True
    while improved and time.monotonic() < deadline:
        improved = False
        rng.shuffle(rows)
        for r in rows:
            w = best ^ r
            if w and w.bit_count() < best.bit_count() and is_logical(w, checks, stab_basis):
                best = w
                improved = True
    temp = 2.5
    cur = best
    for _ in range(min(2500, 80 * max(1, len(rows)))):
        if time.monotonic() >= deadline or not rows:
            break
        r = rng.choice(rows)
        w = cur ^ r
        if not w:
            continue
        dw = w.bit_count() - cur.bit_count()
        if dw <= 0 or rng.random() < pow(2.718281828, -dw / max(0.15, temp)):
            cur = w
            if cur.bit_count() < best.bit_count() and is_logical(cur, checks, stab_basis):
                best = cur
        temp *= 0.997
    return best


def coordinate_scores(cols, checks, stabilizers, n):
    scores = []
    stab_touch = [0] * n
    for r in stabilizers:
        x = r
        while x:
            lsb = x & -x
            stab_touch[lsb.bit_length() - 1] += 1
            x ^= lsb
    for j in range(n):
        scores.append(cols[j].bit_count() + 0.25 * stab_touch[j])
    return scores


def search_basis(name, checks, stabilizers, n, seed, deadline):
    rng = random.Random((seed << 8) ^ (0x58 if name == "x" else 0x5A))
    stab_basis = rowspace_basis(stabilizers, n)
    logs = logical_basis(checks, stabilizers, n)
    if not logs:
        return None

    best = None
    for v in logs:
        r = reduce_by_stabilizers(v, stabilizers, checks, stab_basis, rng, deadline)
        if r is not None and (best is None or r.bit_count() < best.bit_count()):
            best = r

    cols = column_syndromes(checks, n)
    scores = coordinate_scores(cols, checks, stabilizers, n)
    logical_mix = 0
    for v in logs:
        if rng.random() < 0.5:
            logical_mix ^= v
    if logical_mix == 0:
        logical_mix = min(logs, key=lambda x: x.bit_count())

    rounds = 0
    while time.monotonic() < deadline and rounds < 900:
        rounds += 1
        p = rng.choice((0.025, 0.04, 0.06, 0.09, 0.13, 0.18))
        e = 0
        for j in range(n):
            bias = 1.0 / (1.0 + scores[j])
            if rng.random() < min(0.5, p * (0.35 + 1.8 * bias)):
                e |= 1 << j
        if rounds % 3 == 0:
            e ^= rng.choice(logs)
        elif rounds % 5 == 0:
            e ^= logical_mix
        syn = syndrome(e, checks)
        corr = solve_syndrome_random(cols, syn, n, len(checks), rng, scores)
        if corr is None:
            continue
        residual = e ^ corr
        if not is_logical(residual, checks, stab_basis):
            if logs and rng.random() < 0.7:
                residual ^= rng.choice(logs)
            else:
                continue
        r = reduce_by_stabilizers(residual, stabilizers, checks, stab_basis, rng, deadline)
        if r is not None and (best is None or r.bit_count() < best.bit_count()):
            best = r
    return best


def emit(status, basis=None, vector=None, upper_bound=None):
    print(json.dumps({
        "status": status,
        "basis": basis,
        "vector": vector,
        "upper_bound": upper_bound,
    }, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    try:
        hx, nx = read_matrix(args.hx)
        hz, nz = read_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        deadline = time.monotonic() + 25.0

        candidates = []
        x = search_basis("x", hz, hx, n, args.seed, deadline)
        if x is not None:
            candidates.append(("x", x))
        z = search_basis("z", hx, hz, n, args.seed, deadline)
        if z is not None:
            candidates.append(("z", z))

        if not candidates:
            emit("failed", None, None, None)
            return 0
        basis, vec = min(candidates, key=lambda t: (t[1].bit_count(), 0 if t[0] == "x" else 1))
        emit("completed", basis, vector_from_mask(vec, n), vec.bit_count())
        return 0
    except Exception:
        emit("failed", None, None, None)
        return 0


if __name__ == "__main__":
    sys.exit(main())
