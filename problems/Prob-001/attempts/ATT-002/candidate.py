#!/usr/bin/env python3
import argparse
import json
import os
import random


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            bits = 0
            for j, x in enumerate(r):
                if int(x) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            bits = 0
            for j, x in enumerate(r[:n]):
                if int(x) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            bits = 0
            for j in r:
                jj = int(j)
                if jj < 0:
                    raise ValueError("negative sparse column index")
                bits ^= 1 << jj
                if jj + 1 > n:
                    n = jj + 1
            rows.append(bits)
        return rows, n

    raise ValueError("unrecognized matrix format")


def parity(x):
    return x.bit_count() & 1


def rref(rows, n):
    rows = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        pivot = None
        mask = 1 << col
        for i in range(rank, len(rows)):
            if rows[i] & mask:
                pivot = i
                break
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & mask):
                rows[i] ^= rows[rank]
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return rows[:rank], pivots


def rank_of(rows, n):
    return len(rref(rows, n)[1])


def in_span(v, basis, pivots):
    x = v
    for row, col in zip(basis, pivots):
        if x & (1 << col):
            x ^= row
    return x == 0


def nullspace_basis(rows, n):
    rb, pivots = rref(rows, n)
    pivot_set = set(pivots)
    out = []
    for free_col in range(n):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        for row, pcol in zip(rb, pivots):
            if row & (1 << free_col):
                v |= 1 << pcol
        out.append(v)
    return out


def quotient_logical_basis(check_rows, stab_rows, n):
    kernel = nullspace_basis(check_rows, n)
    span_rows, span_pivots = rref(stab_rows, n)
    logicals = []
    for v in sorted(kernel, key=lambda x: (x.bit_count(), x)):
        if not in_span(v, span_rows, span_pivots):
            logicals.append(v)
            span_rows, span_pivots = rref(span_rows + [v], n)
    return logicals


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def syndrome(v, check_rows):
    s = 0
    for i, r in enumerate(check_rows):
        if parity(v & r):
            s |= 1 << i
    return s


def build_columns(check_rows, n):
    cols = [0] * n
    for i, row in enumerate(check_rows):
        x = row
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            cols[j] |= 1 << i
            x ^= lsb
    return cols


def syndrome_solver_basis(columns, m):
    rows = []
    for bit in range(m):
        row = 0
        for j, col in enumerate(columns):
            if col & (1 << bit):
                row |= 1 << j
        row |= 1 << (len(columns) + bit)
        rows.append(row)
    rb, pivots = rref(rows, len(columns) + m)
    return rb, pivots


def solve_syndrome(target, rb, pivots, n):
    x = 0
    for row, col in zip(rb, pivots):
        if col >= n:
            if parity((row >> n) & target):
                return None
            continue
        if parity((row >> n) & target):
            x |= 1 << col
    return x


def greedy_decode(target, columns, rng, max_steps):
    syn = target
    corr = 0
    if syn == 0:
        return 0
    active = [i for i, c in enumerate(columns) if c]
    for _ in range(max_steps):
        if syn == 0:
            return corr
        cur = syn.bit_count()
        best_gain = -10**9
        best = []
        sample_size = min(len(active), 96)
        if sample_size == len(active):
            sample = active
        else:
            sample = rng.sample(active, sample_size)
        for j in sample:
            ns = syn ^ columns[j]
            gain = cur - ns.bit_count()
            if gain > best_gain:
                best_gain = gain
                best = [j]
            elif gain == best_gain:
                best.append(j)
        if not best or (best_gain < 0 and rng.random() > 0.08):
            j = rng.choice(active)
        else:
            j = rng.choice(best)
        syn ^= columns[j]
        corr ^= 1 << j
    return corr if syn == 0 else None


def reduce_by_rows(v, rows, rng, passes=5):
    rows = [r for r in rows if r]
    best = v
    order = list(range(len(rows)))
    for _ in range(passes):
        improved = False
        rng.shuffle(order)
        for idx in order:
            nv = best ^ rows[idx]
            if nv.bit_count() < best.bit_count():
                best = nv
                improved = True
        if not improved:
            break
    return best


def verify(v, check_rows, stab_basis, stab_pivots):
    return v != 0 and syndrome(v, check_rows) == 0 and not in_span(v, stab_basis, stab_pivots)


def search_basis(name, check_rows, stab_rows, n, seed, effort_scale=1):
    rng = random.Random((seed << 8) ^ (17 if name == "x" else 53) ^ n)
    stab_basis, stab_pivots = rref(stab_rows, n)
    logicals = quotient_logical_basis(check_rows, stab_rows, n)
    if not logicals:
        return None

    best = None

    def consider(v):
        nonlocal best
        v = reduce_by_rows(v, stab_rows + stab_basis, rng, passes=6)
        if verify(v, check_rows, stab_basis, stab_pivots):
            if best is None or (v.bit_count(), v) < (best.bit_count(), best):
                best = v

    for v in logicals:
        consider(v)

    columns = build_columns(check_rows, n)
    solver_rows, solver_pivots = syndrome_solver_basis(columns, len(check_rows))
    base_trials = 180 + 18 * min(n, 300)
    trials = max(220, base_trials * effort_scale)
    max_steps = max(24, min(3 * n + 20, 900))

    for t in range(trials):
        if logicals and rng.random() < 0.55:
            e = rng.choice(logicals)
            for u in logicals:
                if rng.random() < 0.20:
                    e ^= u
        else:
            p = min(0.35, max(2.0 / max(n, 1), 0.015 + 0.12 * rng.random()))
            e = 0
            for j in range(n):
                if rng.random() < p:
                    e ^= 1 << j
            if e == 0:
                e = 1 << rng.randrange(n)

        target = syndrome(e, check_rows)
        corr = greedy_decode(target, columns, rng, max_steps)
        if corr is None or (t % 5 == 0):
            exact_corr = solve_syndrome(target, solver_rows, solver_pivots, n)
            if exact_corr is not None and (corr is None or exact_corr.bit_count() <= corr.bit_count() + 3):
                corr = exact_corr
        if corr is None:
            continue

        residual = e ^ corr
        if residual:
            consider(residual)
        if best is not None and best.bit_count() <= 1:
            break

    if best is None:
        for v in logicals:
            if verify(v, check_rows, stab_basis, stab_pivots):
                best = v
                break
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
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        os.makedirs(args.output_dir, exist_ok=True)

        candidates = []
        x = search_basis("x", hz, hx, n, args.seed)
        if x is not None:
            candidates.append(("x", x))
        z = search_basis("z", hx, hz, n, args.seed)
        if z is not None:
            candidates.append(("z", z))

        if not candidates:
            emit("no_witness", None, None, None)
            return 0

        basis, v = min(candidates, key=lambda item: (item[1].bit_count(), item[0], item[1]))
        emit("completed", basis, vector_to_list(v, n), v.bit_count())
        return 0
    except Exception:
        emit("error", None, None, None)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
