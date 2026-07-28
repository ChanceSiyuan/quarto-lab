#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    return parse_matrix(obj)


def parse_matrix(obj):
    if isinstance(obj, dict):
        if "dense_binary_matrix" in obj:
            return parse_matrix(obj["dense_binary_matrix"])
        if "sparse_rows" in obj:
            return parse_matrix(obj["sparse_rows"])
        if "data" in obj:
            data = obj.get("data") or []
            n = int(obj.get("n_cols", obj.get("num_cols", 0)))
            rows = []
            for row in data:
                bits = 0
                for i, val in enumerate(row):
                    if int(val) & 1:
                        bits |= 1 << i
                rows.append(bits)
                n = max(n, len(row))
            return rows, n
        if "rows" in obj:
            n = int(obj.get("num_cols", obj.get("n_cols", 0)))
            rows = []
            for row in obj.get("rows") or []:
                bits = 0
                for col in row:
                    c = int(col)
                    if c >= 0:
                        bits |= 1 << c
                        n = max(n, c + 1)
                rows.append(bits)
            return rows, n
    if isinstance(obj, list):
        rows = []
        n = 0
        for row in obj:
            bits = 0
            for i, val in enumerate(row):
                if int(val) & 1:
                    bits |= 1 << i
            rows.append(bits)
            n = max(n, len(row))
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def mask_n(n):
    return (1 << n) - 1 if n > 0 else 0


def normalize_rows(rows, n):
    m = mask_n(n)
    return [int(r) & m for r in rows if (int(r) & m) != 0]


def rref_with_pivots(rows, n):
    basis = {}
    for row in rows:
        x = row & mask_n(n)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    pivots = sorted(basis.keys(), reverse=True)
    for p in pivots:
        row = basis[p]
        for q in pivots:
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    pivots = sorted(basis.keys(), reverse=True)
    return [basis[p] for p in pivots], pivots


def rank_rows(rows, n):
    return len(rref_with_pivots(rows, n)[0])


def make_reducer(rows, n):
    rbasis, _ = rref_with_pivots(rows, n)
    by_pivot = {}
    for row in rbasis:
        by_pivot[row.bit_length() - 1] = row

    def reduce_vec(vec):
        x = vec & mask_n(n)
        while x:
            p = x.bit_length() - 1
            row = by_pivot.get(p)
            if row is None:
                return x
            x ^= row
        return 0

    return reduce_vec, rbasis


def in_rowspace(vec, rows, n):
    reduce_vec, _ = make_reducer(rows, n)
    return reduce_vec(vec) == 0


def nullspace_basis(check_rows, n):
    rrows, pivots_desc = rref_with_pivots(check_rows, n)
    pivot_set = set(pivots_desc)
    pivot_to_row = {p: r for p, r in zip(pivots_desc, rrows)}
    free_cols = [c for c in range(n) if c not in pivot_set]
    basis = []
    for f in free_cols:
        v = 1 << f
        for p in pivots_desc:
            if (pivot_to_row[p] >> f) & 1:
                v |= 1 << p
        basis.append(v)
    return basis


def syndrome_zero(vec, check_rows):
    for row in check_rows:
        if ((row & vec).bit_count() & 1) != 0:
            return False
    return True


def bits_to_list(vec, n):
    return [(vec >> i) & 1 for i in range(n)]


def certifies(vec, check_rows, stab_rows, n):
    return vec != 0 and syndrome_zero(vec, check_rows) and not in_rowspace(vec, stab_rows, n)


def certifies_with_reducer(vec, check_rows, stab_reduce):
    return vec != 0 and syndrome_zero(vec, check_rows) and stab_reduce(vec) != 0


def quotient_representatives(check_rows, stab_rows, n):
    kernel = nullspace_basis(check_rows, n)
    span_rows = list(stab_rows)
    reps = []
    current_rank = rank_rows(span_rows, n)
    for v in sorted(kernel, key=lambda x: (x.bit_count(), x)):
        new_rank = rank_rows(span_rows + [v], n)
        if new_rank > current_rank:
            reps.append(v)
            span_rows.append(v)
            current_rank = new_rank
    return reps


def luby_value(i):
    k = 1
    while (1 << k) - 1 < i:
        k += 1
    if i == (1 << k) - 1:
        return 1 << (k - 1)
    return luby_value(i - (1 << (k - 1)) + 1)


def random_logical_combo(reps, rng):
    v = 0
    while v == 0:
        for r in reps:
            if rng.getrandbits(1):
                v ^= r
    return v


def greedy_stabilizer_descent(vec, stab_rows, n, rng, steps, temperature):
    if not stab_rows:
        return vec
    v = vec & mask_n(n)
    weight = v.bit_count()
    rows = list(stab_rows)
    best = v
    best_w = weight
    stall = 0
    for t in range(max(1, steps)):
        if t == 0 or stall > len(rows):
            rng.shuffle(rows)
            stall = 0
        row = rows[t % len(rows)]
        nv = v ^ row
        nw = nv.bit_count()
        delta = nw - weight
        accept = delta <= 0
        if not accept and temperature > 0:
            # Bounded uphill moves help escape shallow stabilizer-coordinate traps.
            accept = rng.random() < temperature / (temperature + delta + 1.0)
        if accept:
            v, weight = nv, nw
            stall = 0
            if weight < best_w:
                best, best_w = v, weight
        else:
            stall += 1
    return best


def sparse_cluster_seed(logical, stab_rows, n, rng):
    if not stab_rows:
        return logical
    support = [i for i in range(n) if (logical >> i) & 1]
    if not support:
        return logical
    chosen = set(rng.sample(support, max(1, int(len(support) ** 0.5))))
    v = logical
    candidates = []
    for row in stab_rows:
        overlap = sum(1 for c in chosen if (row >> c) & 1)
        if overlap:
            candidates.append((overlap, row.bit_count(), row))
    candidates.sort(reverse=True)
    take = 1 + rng.randrange(max(1, min(8, len(candidates))))
    for _, _, row in candidates[:take]:
        if rng.random() < 0.65:
            v ^= row
    return v


def heavy_tail_search_for_basis(name, check_rows, stab_rows, n, rng, deadline, reps, stab_reduce):
    if not reps:
        return None
    best = min(reps, key=lambda x: (x.bit_count(), x))
    base_unit = max(16, min(128, n + len(stab_rows)))
    restart = 1
    while time.monotonic() < deadline:
        span = luby_value(restart)
        restart += 1
        budget = min(base_unit * span, 12000)
        v = random_logical_combo(reps, rng)
        if rng.random() < 0.55:
            v = sparse_cluster_seed(v, stab_rows, n, rng)
        temp = 0.35 / (1.0 + (restart % 7))
        v = greedy_stabilizer_descent(v, stab_rows, n, rng, budget, temp)
        if certifies_with_reducer(v, check_rows, stab_reduce) and (v.bit_count(), v) < (best.bit_count(), best):
            best = v
        # Intensify around the current best at the long restarts.
        if span >= 4 and time.monotonic() < deadline:
            v2 = greedy_stabilizer_descent(best, stab_rows, n, rng, budget // 2 + 1, 0.04)
            if certifies_with_reducer(v2, check_rows, stab_reduce) and (v2.bit_count(), v2) < (best.bit_count(), best):
                best = v2
    return name, best


def choose_witness(hx, hz, n, seed):
    rng = random.Random(seed)
    x_check, x_stab = hz, hx
    z_check, z_stab = hx, hz
    x_reps = quotient_representatives(x_check, x_stab, n)
    z_reps = quotient_representatives(z_check, z_stab, n)
    x_reduce, _ = make_reducer(x_stab, n)
    z_reduce, _ = make_reducer(z_stab, n)
    fallback = []
    if x_reps:
        fallback.append(("x", min(x_reps, key=lambda v: (v.bit_count(), v)), x_check, x_stab, x_reduce))
    if z_reps:
        fallback.append(("z", min(z_reps, key=lambda v: (v.bit_count(), v)), z_check, z_stab, z_reduce))
    if not fallback:
        return None

    best_basis, best_vec, best_check, best_stab, best_reduce = min(fallback, key=lambda t: (t[1].bit_count(), t[0]))
    # Keep runtime bounded while still giving heavy-tail restarts enough room.
    limit = 2.8 if n <= 400 else 4.5
    deadline = time.monotonic() + limit
    order = [
        ("x", x_check, x_stab, x_reps, x_reduce),
        ("z", z_check, z_stab, z_reps, z_reduce),
    ]
    rng.shuffle(order)
    while time.monotonic() < deadline:
        for name, check_rows, stab_rows, reps, stab_reduce in order:
            slice_deadline = min(deadline, time.monotonic() + 0.35)
            result = heavy_tail_search_for_basis(name, check_rows, stab_rows, n, rng, slice_deadline, reps, stab_reduce)
            if result is None:
                continue
            basis, vec = result
            if certifies_with_reducer(vec, check_rows, stab_reduce) and (vec.bit_count(), basis) < (best_vec.bit_count(), best_basis):
                best_basis, best_vec, best_check, best_stab, best_reduce = basis, vec, check_rows, stab_rows, stab_reduce
    if certifies_with_reducer(best_vec, best_check, best_reduce):
        return best_basis, best_vec
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    hx_rows, hx_n = load_matrix(args.hx)
    hz_rows, hz_n = load_matrix(args.hz)
    n = max(hx_n, hz_n)
    hx = normalize_rows(hx_rows, n)
    hz = normalize_rows(hz_rows, n)
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    result = choose_witness(hx, hz, n, args.seed)
    if result is None:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    else:
        basis, vec = result
        out = {
            "status": "completed",
            "basis": basis,
            "vector": bits_to_list(vec, n),
            "upper_bound": int(vec.bit_count()),
        }
    sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stdout.write(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")) + "\n")
