#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def load_json_arg(value):
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(value)


def parse_matrix(obj):
    if obj is None:
        return [], 0
    if isinstance(obj, dict):
        if "dense_binary_matrix" in obj:
            obj = obj["dense_binary_matrix"]
        elif "sparse_rows" in obj:
            obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", 0))
        if data and isinstance(data[0], int):
            if n <= 0:
                raise ValueError("flat dense matrix requires n_cols")
            data = [data[i:i + n] for i in range(0, len(data), n)]
        if n == 0 and data:
            n = len(data[0])
        rows = []
        for row in data:
            x = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    x ^= 1 << j
            rows.append(x)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for row in obj.get("rows") or []:
            x = 0
            for j in row:
                jj = int(j)
                if jj >= 0:
                    x ^= 1 << jj
            rows.append(x)
        if n == 0 and rows:
            n = max(r.bit_length() for r in rows)
        return rows, n

    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        rows = []
        for row in obj:
            x = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    x ^= 1 << j
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix format")


def clean_rows(rows, n):
    mask = (1 << n) - 1 if n else 0
    return [r & mask for r in rows if (r & mask) != 0]


def rref_rows(rows):
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
    for p in sorted(basis):
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= basis[p]
    pivots = sorted(basis, reverse=True)
    return [basis[p] for p in pivots], pivots


def reduce_by_basis(x, basis_rows, pivots):
    y = x
    for row, p in zip(basis_rows, pivots):
        if (y >> p) & 1:
            y ^= row
    return y


def in_span(x, basis_rows, pivots):
    return reduce_by_basis(x, basis_rows, pivots) == 0


def nullspace_basis(rows, n):
    rb, pivots = rref_rows(rows)
    pivot_set = set(pivots)
    free_cols = [j for j in range(n) if j not in pivot_set]
    out = []
    for f in free_cols:
        v = 1 << f
        for row, p in zip(rb, pivots):
            if (row >> f) & 1:
                v ^= 1 << p
        out.append(v)
    return out


def logical_basis(check_rows, stab_rows, n):
    kernel = nullspace_basis(check_rows, n)
    span_rows, pivots = rref_rows(stab_rows)
    logicals = []
    for v in kernel:
        trial_rows, trial_pivots = rref_rows(span_rows + logicals)
        if not in_span(v, trial_rows, trial_pivots):
            logicals.append(v)
    return logicals


def syndrome_zero(v, check_rows):
    for row in check_rows:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def verify(v, check_rows, stab_rows):
    if v == 0 or not syndrome_zero(v, check_rows):
        return False
    rb, pivots = rref_rows(stab_rows)
    return not in_span(v, rb, pivots)


def row_delta_weight(v, row):
    return (v ^ row).bit_count() - v.bit_count()


def greedy_sweep(v, rows, rng):
    order = list(rows)
    rng.shuffle(order)
    changed = True
    while changed:
        changed = False
        for row in order:
            if row and row_delta_weight(v, row) < 0:
                v ^= row
                changed = True
        if changed:
            rng.shuffle(order)
    return v


def coset_walk(start, stab_rows, rng, deadline, rounds):
    if not stab_rows:
        return start
    rows = [r for r in stab_rows if r]
    v = greedy_sweep(start, rows, rng)
    best = v
    temp0 = max(1.0, best.bit_count() / 3.0)
    limit = max(200, min(20000, rounds * max(1, len(rows))))
    for step in range(limit):
        if time.monotonic() > deadline:
            break
        row = rows[rng.randrange(len(rows))]
        cand = v ^ row
        dw = cand.bit_count() - v.bit_count()
        temp = temp0 * (1.0 - step / max(1, limit)) + 0.05
        accept = dw <= 0 or rng.random() < pow(2.718281828, -dw / temp)
        if accept:
            v = cand
            if v.bit_count() < best.bit_count():
                best = greedy_sweep(v, rows, rng)
                v = best
    return best


def combine_logicals(logicals, rng, max_terms):
    if not logicals:
        return 0
    idxs = list(range(len(logicals)))
    rng.shuffle(idxs)
    terms = 1 + rng.randrange(min(max_terms, len(logicals)))
    v = 0
    for i in idxs[:terms]:
        v ^= logicals[i]
    return v


def search_side(name, check_rows, stab_rows, n, rng, deadline):
    logs = logical_basis(check_rows, stab_rows, n)
    best = None
    best_w = n + 1

    seeds = list(logs)
    if logs:
        for _ in range(min(256, 24 * len(logs) + 64)):
            seeds.append(combine_logicals(logs, rng, max_terms=min(6, len(logs))))

    for seed in seeds:
        if time.monotonic() > deadline:
            break
        if seed == 0:
            continue
        v = coset_walk(seed, stab_rows, rng, deadline, rounds=12)
        if verify(v, check_rows, stab_rows):
            w = v.bit_count()
            if w < best_w:
                best, best_w = v, w

    return None if best is None else (name, best, best_w)


def int_to_bits(v, n):
    return [(v >> j) & 1 for j in range(n)]


def emit(status, basis, vector, upper_bound):
    print(json.dumps({
        "status": status,
        "basis": basis,
        "vector": vector,
        "upper_bound": upper_bound,
    }, separators=(",", ":")))


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    try:
        hx, nx = parse_matrix(load_json_arg(args.hx))
        hz, nz = parse_matrix(load_json_arg(args.hz))
        n = max(nx, nz)
        hx = clean_rows(hx, n)
        hz = clean_rows(hz, n)
        deadline = time.monotonic() + 25.0

        candidates = []
        # X logicals commute with Z checks and are quotiented by X stabilizers.
        xres = search_side("x", hz, hx, n, rng, deadline)
        if xres is not None:
            candidates.append(xres)
        zres = search_side("z", hx, hz, n, rng, deadline)
        if zres is not None:
            candidates.append(zres)

        if not candidates:
            emit("failed", None, [], None)
            return 0

        basis, vec, weight = min(candidates, key=lambda t: (t[2], 0 if t[0] == "x" else 1))
        check = hz if basis == "x" else hx
        stab = hx if basis == "x" else hz
        if not verify(vec, check, stab):
            emit("failed", None, [], None)
            return 0
        emit("completed", basis, int_to_bits(vec, n), weight)
        return 0
    except Exception:
        emit("failed", None, [], None)
        return 0


if __name__ == "__main__":
    sys.exit(main())
