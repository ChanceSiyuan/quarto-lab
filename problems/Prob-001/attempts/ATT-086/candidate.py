#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import random
import sys
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
            for j, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or a list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", obj.get("num_cols", max((len(r) for r in data), default=0))))
        rows = []
        for r in data:
            x = 0
            for j, v in enumerate(r[:n]):
                if int(v) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if "rows" in obj:
        sparse = obj["rows"]
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n == 0:
            n = 1 + max((int(c) for r in sparse for c in r), default=-1)
        rows = []
        for r in sparse:
            x = 0
            for c in r:
                j = int(c)
                if 0 <= j < n:
                    x ^= 1 << j
            rows.append(x)
        return rows, n

    raise ValueError("unrecognized matrix format")


def add_to_basis(basis, x, n):
    for p in sorted(basis):
        if (x >> p) & 1:
            x ^= basis[p]
    if x == 0:
        return False
    low = x & -x
    p = low.bit_length() - 1
    for q in list(basis):
        if q != p and ((basis[q] >> p) & 1):
            basis[q] ^= x
    basis[p] = x
    return True


def make_basis(rows, n):
    basis = {}
    for r in rows:
        add_to_basis(basis, r, n)
    return basis


def reduce_by_basis(x, basis):
    for p in sorted(basis):
        if (x >> p) & 1:
            x ^= basis[p]
    return x


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def kernel_basis(check_rows, n):
    rb = make_basis(check_rows, n)
    pivots = set(rb)
    free_cols = [j for j in range(n) if j not in pivots]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def quotient_logicals(check_rows, stab_rows, n):
    stab_basis = make_basis(stab_rows, n)
    span = dict(stab_basis)
    logicals = []
    for v in kernel_basis(check_rows, n):
        if reduce_by_basis(v, span) != 0:
            logicals.append(v)
            add_to_basis(span, v, n)
    return logicals, stab_basis


def syndrome(v, col_syn):
    s = 0
    x = v
    while x:
        low = x & -x
        j = low.bit_length() - 1
        s ^= col_syn[j]
        x ^= low
    return s


def column_syndromes(rows, n):
    cols = [0] * n
    for i, r in enumerate(rows):
        x = r
        while x:
            low = x & -x
            j = low.bit_length() - 1
            if j < n:
                cols[j] |= 1 << i
            x ^= low
    return cols


def verify(v, check_rows, stab_basis, n):
    if v == 0 or (v >> n) != 0:
        return False
    for r in check_rows:
        if ((r & v).bit_count() & 1) != 0:
            return False
    return not in_span(v, stab_basis)


def random_combo(rows, rng, max_terms):
    if not rows:
        return 0
    terms = 1 + rng.randrange(max(1, max_terms))
    v = 0
    for _ in range(terms):
        v ^= rows[rng.randrange(len(rows))]
    return v


def coset_descent(v, check_rows, stab_rows, stab_basis, n, rng, end_time):
    if not verify(v, check_rows, stab_basis, n):
        return None
    best = v
    basis_rows = list(stab_basis.values())
    useful = sorted([r for r in basis_rows + list(stab_rows) if r], key=lambda z: z.bit_count())

    changed = True
    while changed and time.monotonic() < end_time:
        changed = False
        rng.shuffle(useful)
        useful.sort(key=lambda r: (best ^ r).bit_count() - best.bit_count())
        for r in useful:
            w = best ^ r
            if w and w.bit_count() < best.bit_count() and verify(w, check_rows, stab_basis, n):
                best = w
                changed = True

    trials = 800 + 8 * n
    max_terms = 3 if n < 200 else 5
    for _ in range(trials):
        if time.monotonic() >= end_time:
            break
        r = random_combo(useful, rng, max_terms)
        w = best ^ r
        if w and w.bit_count() < best.bit_count() and verify(w, check_rows, stab_basis, n):
            best = w
    return best


def weighted_subset(cols, weights, rng, max_size):
    if not cols:
        return 0
    size = 1 + rng.randrange(max(1, max_size))
    v = 0
    for _ in range(size):
        total = sum(weights[j] for j in cols)
        t = rng.random() * total
        acc = 0.0
        chosen = cols[-1]
        for j in cols:
            acc += weights[j]
            if acc >= t:
                chosen = j
                break
        v ^= 1 << chosen
    return v


def mitm_improve(base, check_rows, stab_rows, stab_basis, n, rng, end_time):
    col_syn = column_syndromes(check_rows, n)
    col_deg = [col_syn[j].bit_count() for j in range(n)]
    support = [j for j in range(n) if (base >> j) & 1]
    nonsupport = [j for j in range(n) if not ((base >> j) & 1)]
    if not support:
        return base

    best = base
    rounds = 18 if n < 600 else 10
    for _ in range(rounds):
        if time.monotonic() >= end_time:
            break

        rng.shuffle(support)
        rng.shuffle(nonsupport)
        keep_s = min(len(support), max(12, int(2.5 * (best.bit_count() ** 0.5)) + 10))
        keep_o = min(len(nonsupport), max(16, keep_s * 3))
        pool = support[:keep_s] + nonsupport[:keep_o]
        if len(pool) < 2:
            continue
        rng.shuffle(pool)
        mid = len(pool) // 2
        left, right = pool[:mid], pool[mid:]

        weights = {}
        for j in pool:
            w = 1.0 / (1.0 + col_deg[j])
            if (best >> j) & 1:
                w *= 5.0
            weights[j] = w

        table = {}
        samples = min(3500, 600 + 18 * n)
        max_size = 5 if n < 300 else 4
        for _i in range(samples):
            m = weighted_subset(left, weights, rng, max_size)
            s = syndrome(m, col_syn)
            old = table.get(s)
            if old is None or (best ^ m).bit_count() < (best ^ old).bit_count():
                table[s] = m

        for _i in range(samples):
            if time.monotonic() >= end_time:
                break
            rmask = weighted_subset(right, weights, rng, max_size)
            lmask = table.get(syndrome(rmask, col_syn))
            if lmask is None:
                continue
            cycle = lmask ^ rmask
            if cycle == 0:
                continue
            cand = best ^ cycle
            if cand and cand.bit_count() < best.bit_count() and verify(cand, check_rows, stab_basis, n):
                improved = coset_descent(cand, check_rows, stab_rows, stab_basis, n, rng, end_time)
                if improved is not None and improved.bit_count() <= cand.bit_count():
                    cand = improved
                if cand.bit_count() < best.bit_count():
                    best = cand
                    support = [j for j in range(n) if (best >> j) & 1]
                    nonsupport = [j for j in range(n) if not ((best >> j) & 1)]
    return best


def solve_side(name, check_rows, stab_rows, n, rng, end_time):
    logicals, stab_basis = quotient_logicals(check_rows, stab_rows, n)
    if not logicals:
        return None
    logicals.sort(key=lambda v: v.bit_count())

    seeds = logicals[: min(len(logicals), 16)]
    # Random quotient mixtures create additional starting cosets without
    # exhaustively scanning the quotient space.
    for _ in range(min(48, 4 * len(logicals) + 8)):
        v = 0
        for b in logicals:
            if rng.random() < min(0.35, 3.0 / max(1, len(logicals))):
                v ^= b
        if v and not in_span(v, stab_basis):
            seeds.append(v)

    best = None
    for v in seeds:
        if time.monotonic() >= end_time:
            break
        if not verify(v, check_rows, stab_basis, n):
            continue
        v = coset_descent(v, check_rows, stab_rows, stab_basis, n, rng, end_time) or v
        v = mitm_improve(v, check_rows, stab_rows, stab_basis, n, rng, end_time)
        v = coset_descent(v, check_rows, stab_rows, stab_basis, n, rng, end_time) or v
        if verify(v, check_rows, stab_basis, n):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    if best is None:
        for v in logicals:
            if verify(v, check_rows, stab_basis, n):
                best = v
                break
    if best is None:
        return None
    return {"basis": name, "vector_int": best, "upper_bound": best.bit_count()}


def bits_list(v, n):
    return [1 if ((v >> j) & 1) else 0 for j in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1) for r in hx]
    hz = [r & ((1 << n) - 1) for r in hz]

    try:
        seed = int(args.seed)
    except ValueError:
        seed = int.from_bytes(hashlib.sha256(args.seed.encode("utf-8")).digest()[:8], "little")
    rng = random.Random(seed)
    end_time = time.monotonic() + 10.0

    results = []
    order = [("x", hz, hx), ("z", hx, hz)]
    if rng.randrange(2):
        order.reverse()
    for name, check_rows, stab_rows in order:
        res = solve_side(name, check_rows, stab_rows, n, rng, end_time)
        if res is not None:
            results.append(res)

    if results:
        results.sort(key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
        r = results[0]
        out = {
            "status": "completed",
            "basis": r["basis"],
            "vector": bits_list(r["vector_int"], n),
            "upper_bound": int(r["upper_bound"]),
        }
    else:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
