#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for j, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        rows = []
        if data and isinstance(data[0], list):
            n = n or max((len(r) for r in data), default=0)
            for r in data:
                x = 0
                for j, v in enumerate(r):
                    if int(v) & 1:
                        x |= 1 << j
                rows.append(x)
        else:
            if n <= 0:
                raise ValueError("dense_binary_matrix requires n_cols")
            for i in range(0, len(data), n):
                x = 0
                for j, v in enumerate(data[i:i + n]):
                    if int(v) & 1:
                        x |= 1 << j
                rows.append(x)
        return rows, n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for j in r:
                jj = int(j)
                if jj >= 0:
                    x |= 1 << jj
                    if jj + 1 > n:
                        n = jj + 1
            rows.append(x)
        return rows, n
    raise ValueError("unrecognized matrix JSON format")


def mask_n(n):
    return (1 << n) - 1 if n > 0 else 0


def wt(x):
    return int(x.bit_count())


def rref(rows, n):
    a = [r & mask_n(n) for r in rows if r & mask_n(n)]
    pivots = []
    r = 0
    for c in range(n):
        p = None
        bit = 1 << c
        for i in range(r, len(a)):
            if a[i] & bit:
                p = i
                break
        if p is None:
            continue
        a[r], a[p] = a[p], a[r]
        for i in range(len(a)):
            if i != r and (a[i] & bit):
                a[i] ^= a[r]
        pivots.append(c)
        r += 1
        if r == len(a):
            break
    return a[:r], pivots


def kernel_basis(rows, n):
    rr, pivots = rref(rows, n)
    pivot_set = set(pivots)
    out = []
    for f in range(n):
        if f in pivot_set:
            continue
        v = 1 << f
        for i, p in enumerate(pivots):
            if rr[i] & (1 << f):
                v |= 1 << p
        out.append(v)
    return out


def add_to_basis(basis, v):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def reduce_by_basis(basis, v):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def make_basis(rows):
    basis = {}
    for r in rows:
        add_to_basis(basis, r)
    return basis


def in_rowspace(basis, v):
    return reduce_by_basis(basis, v) == 0


def syndrome(rows, v):
    s = 0
    for i, r in enumerate(rows):
        if wt(r & v) & 1:
            s |= 1 << i
    return s


def solve_syndrome(rows, n, syn, col_order):
    aug_bit = 1 << n
    a = []
    for i, r in enumerate(rows):
        a.append((r & mask_n(n)) | (aug_bit if ((syn >> i) & 1) else 0))
    pivots = []
    rr = 0
    for c in col_order:
        bit = 1 << c
        p = None
        for i in range(rr, len(a)):
            if a[i] & bit:
                p = i
                break
        if p is None:
            continue
        a[rr], a[p] = a[p], a[rr]
        for i in range(len(a)):
            if i != rr and (a[i] & bit):
                a[i] ^= a[rr]
        pivots.append(c)
        rr += 1
        if rr == len(a):
            break
    coeff_mask = mask_n(n)
    for row in a[rr:]:
        if (row & coeff_mask) == 0 and (row & aug_bit):
            return None
    x = 0
    for i, c in enumerate(pivots):
        if a[i] & aug_bit:
            x |= 1 << c
    return x


def column_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        x = r
        while x:
            lsb = x & -x
            deg[lsb.bit_length() - 1] += 1
            x ^= lsb
    return deg


def quotient_logicals(check_rows, stab_rows, n):
    stab_basis = make_basis(stab_rows)
    combined = dict(stab_basis)
    reps = []
    for v in sorted(kernel_basis(check_rows, n), key=wt):
        if reduce_by_basis(combined, v) != 0:
            reps.append(v)
            add_to_basis(combined, v)
    return reps, stab_basis


def minimize_by_stabilizers(v, stab_rows, rng, rounds=5):
    best = v
    rows = [r for r in stab_rows if r]
    rows.sort(key=wt)
    improved = True
    while improved:
        improved = False
        for r in rows:
            u = best ^ r
            if wt(u) < wt(best):
                best = u
                improved = True
    for _ in range(rounds):
        order = rows[:]
        rng.shuffle(order)
        cur = best
        temp = max(1, wt(best) // 3)
        for r in order:
            u = cur ^ r
            du = wt(u) - wt(cur)
            if du < 0 or (du <= temp and rng.randrange(8 * (temp + 1)) == 0):
                cur = u
        for r in rows:
            u = cur ^ r
            if wt(u) < wt(cur):
                cur = u
        if wt(cur) < wt(best):
            best = cur
    return best


def verify(v, check_rows, stab_basis, n):
    v &= mask_n(n)
    return v != 0 and syndrome(check_rows, v) == 0 and not in_rowspace(stab_basis, v)


def random_error(n, rng, deg):
    if n <= 0:
        return 0
    avg = sum(deg) / max(1, n)
    base = 1.0 / max(2.0, avg + 2.0)
    p = min(0.35, max(1.0 / max(1, n), base * rng.uniform(0.35, 1.65)))
    e = 0
    for j in range(n):
        local = p / (1.0 + 0.15 * deg[j])
        if rng.random() < local:
            e |= 1 << j
    if e == 0:
        e = 1 << rng.randrange(n)
    return e


def search_basis(label, check_rows, stab_rows, n, rng, deadline):
    reps, stab_basis = quotient_logicals(check_rows, stab_rows, n)
    best = None

    def consider(v):
        nonlocal best
        v = minimize_by_stabilizers(v & mask_n(n), stab_rows, rng)
        if verify(v, check_rows, stab_basis, n):
            if best is None or wt(v) < wt(best):
                best = v

    for v in reps:
        consider(v)
    if not reps:
        return None

    mix_trials = min(256, 16 + 8 * len(reps))
    for _ in range(mix_trials):
        v = 0
        for r in reps:
            if rng.getrandbits(1):
                v ^= r
        if v:
            consider(v)

    deg = column_degrees(check_rows, n)
    cols = list(range(n))
    trials = 0
    max_trials = max(80, min(2200, 28 * n + 60 * len(reps)))
    while trials < max_trials and time.monotonic() < deadline:
        trials += 1
        e = random_error(n, rng, deg)
        syn = syndrome(check_rows, e)
        order = cols[:]
        order.sort(key=lambda c: (deg[c] + rng.random() * (2.0 + 0.25 * deg[c])))
        c = solve_syndrome(check_rows, n, syn, order)
        if c is None:
            continue
        residual = e ^ c
        if residual:
            consider(residual)
        if best is not None and wt(best) <= 2:
            break
    return (label, best) if best is not None else None


def vector_list(v, n):
    return [int((v >> i) & 1) for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    try:
        hx, nx = parse_matrix(args.hx)
        hz, nz = parse_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & mask_n(n) for r in hx]
        hz = [r & mask_n(n) for r in hz]
        rng = random.Random(args.seed)
        os.makedirs(args.output_dir, exist_ok=True)
        deadline = time.monotonic() + 11.5

        found = []
        bx = search_basis("x", hz, hx, n, rng, deadline)
        if bx is not None:
            found.append(bx)
        bz = search_basis("z", hx, hz, n, rng, deadline)
        if bz is not None:
            found.append(bz)

        if found:
            basis, vec = min(found, key=lambda item: wt(item[1]))
            out = {
                "status": "completed",
                "basis": basis,
                "vector": vector_list(vec, n),
                "upper_bound": wt(vec),
            }
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
