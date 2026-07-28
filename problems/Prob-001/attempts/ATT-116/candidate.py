#!/usr/bin/env python3
"""Randomized CSS logical-operator upper-bound witness search."""

import argparse
import json
import os
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if {"n_rows", "n_cols", "data"} <= obj.keys():
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            if len(row) != n_cols:
                raise ValueError("dense row length does not match n_cols")
            for j, value in enumerate(row):
                if value not in (0, 1, False, True):
                    raise ValueError("matrix entries must be binary")
                if int(value):
                    bits |= 1 << j
            rows.append(bits)
        return rows, n_cols

    if {"num_cols", "rows"} <= obj.keys():
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            previous = -1
            for value in row:
                j = int(value)
                if j <= previous or j < 0 or j >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing column indices")
                bits |= 1 << j
                previous = j
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


def rref_rows(rows):
    """Return reduced independent rows and their pivot columns over GF(2)."""
    basis = {}
    for row in rows:
        x = int(row)
        while x:
            pivot = x.bit_length() - 1
            y = basis.get(pivot)
            if y is None:
                basis[pivot] = x
                break
            x ^= y

    for pivot in sorted(basis):
        row = basis[pivot]
        for other_pivot in sorted(basis):
            if other_pivot != pivot and ((basis[other_pivot] >> pivot) & 1):
                basis[other_pivot] ^= row

    pivots = sorted(basis, reverse=True)
    return [basis[p] for p in pivots], pivots


def reduce_by_rref(vector, basis_rows):
    x = int(vector)
    for row in basis_rows:
        pivot = row.bit_length() - 1
        if (x >> pivot) & 1:
            x ^= row
    return x


def in_rowspace(vector, basis_rows):
    return reduce_by_rref(vector, basis_rows) == 0


def nullspace_basis(check_rows, n_cols):
    rref, pivots = rref_rows(check_rows)
    pivot_set = set(pivots)
    free_cols = [j for j in range(n_cols) if j not in pivot_set]
    out = []
    for free in free_cols:
        v = 1 << free
        for row, pivot in zip(rref, pivots):
            if (row >> free) & 1:
                v |= 1 << pivot
        out.append(v)
    return out


def vector_to_list(vector, n_cols):
    return [(vector >> j) & 1 for j in range(n_cols)]


def syndrome_zero(vector, check_rows):
    return all(((vector & row).bit_count() & 1) == 0 for row in check_rows)


def css_valid_for_basis(vector, basis_name, hx_rows, hz_rows, hx_rref, hz_rref):
    if vector == 0:
        return False
    if basis_name == "x":
        return syndrome_zero(vector, hz_rows) and not in_rowspace(vector, hx_rref)
    return syndrome_zero(vector, hx_rows) and not in_rowspace(vector, hz_rref)


def quotient_generators(kernel_basis, stabilizer_rref):
    """Extract independent non-stabilizer kernel directions modulo stabilizers."""
    span = list(stabilizer_rref)
    span_rref, _ = rref_rows(span)
    gens = []
    for v in sorted(kernel_basis, key=lambda x: (x.bit_count(), x)):
        if not in_rowspace(v, span_rref):
            gens.append(v)
            span.append(v)
            span_rref, _ = rref_rows(span)
    return gens


def random_combo(rng, vectors, p_num=1, p_den=2):
    x = 0
    for v in vectors:
        if rng.randrange(p_den) < p_num:
            x ^= v
    return x


def greedy_reduce_with_rows(vector, rows, rng, passes=5):
    v = vector
    current = v.bit_count()
    ordered = list(rows)
    for _ in range(passes):
        changed = False
        rng.shuffle(ordered)
        for row in ordered:
            candidate = v ^ row
            weight = candidate.bit_count()
            if weight < current:
                v = candidate
                current = weight
                changed = True
        if not changed:
            break
    return v


def diversify_by_noisy_descent(vector, stabilizer_rows, rng, rounds):
    v = vector
    best = v
    best_weight = v.bit_count()
    if not stabilizer_rows:
        return best
    for _ in range(rounds):
        trial = v
        flips = 1 + rng.randrange(min(8, len(stabilizer_rows)))
        for row in rng.sample(stabilizer_rows, flips):
            trial ^= row
        trial = greedy_reduce_with_rows(trial, stabilizer_rows, rng, passes=3)
        weight = trial.bit_count()
        if weight < best_weight:
            best = trial
            best_weight = weight
            v = trial
        elif rng.randrange(8) == 0:
            v = trial
    return best


def search_one_basis(name, commute_rows, stabilizer_rows, n_cols, rng, deadline):
    stabilizer_rref, _ = rref_rows(stabilizer_rows)
    kernel_basis = nullspace_basis(commute_rows, n_cols)
    logical_gens = quotient_generators(kernel_basis, stabilizer_rref)
    if not logical_gens:
        return None

    candidates = []
    candidates.extend(logical_gens)
    for g in logical_gens:
        candidates.append(greedy_reduce_with_rows(g, stabilizer_rows, rng, passes=8))

    rounds = max(300, min(8000, 80 * (n_cols + len(logical_gens) + 1)))
    for t in range(rounds):
        if time.monotonic() > deadline:
            break
        if t % 5 == 0:
            base_pool = logical_gens
            p_num, p_den = 1, max(2, min(8, len(base_pool)))
        elif t % 5 == 1 and len(kernel_basis) <= 256:
            base_pool = kernel_basis
            p_num, p_den = 1, 2
        else:
            base_pool = logical_gens
            p_num, p_den = 1, 2

        v = random_combo(rng, base_pool, p_num, p_den)
        if v == 0 and logical_gens:
            v = rng.choice(logical_gens)
        v = greedy_reduce_with_rows(v, stabilizer_rows, rng, passes=5)
        v = diversify_by_noisy_descent(v, stabilizer_rows, rng, rounds=2)
        candidates.append(v)

    best = None
    best_weight = None
    for v in candidates:
        if v and syndrome_zero(v, commute_rows) and not in_rowspace(v, stabilizer_rref):
            w = v.bit_count()
            if best is None or w < best_weight:
                best = v
                best_weight = w
    if best is None:
        return None
    return {"basis": name, "vector": vector_to_list(best, n_cols), "upper_bound": best_weight}


def emit(obj):
    print(json.dumps(obj, separators=(",", ":")), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)

    hx_rows, hx_cols = load_matrix(args.hx)
    hz_rows, hz_cols = load_matrix(args.hz)
    if hx_cols != hz_cols:
        raise ValueError("Hx and Hz must have the same number of columns")
    n_cols = hx_cols

    hx_rref, _ = rref_rows(hx_rows)
    hz_rref, _ = rref_rows(hz_rows)
    deadline = time.monotonic() + float(os.environ.get("CANDIDATE_TIME_LIMIT", "25"))

    results = []
    order = ["x", "z"]
    rng.shuffle(order)
    for basis_name in order:
        if basis_name == "x":
            result = search_one_basis("x", hz_rows, hx_rows, n_cols, rng, deadline)
        else:
            result = search_one_basis("z", hx_rows, hz_rows, n_cols, rng, deadline)
        if result is not None:
            vector_int = sum(bit << i for i, bit in enumerate(result["vector"]))
            if css_valid_for_basis(vector_int, result["basis"], hx_rows, hz_rows, hx_rref, hz_rref):
                results.append(result)

    if results:
        best = min(results, key=lambda item: (item["upper_bound"], item["basis"]))
        emit({"status": "completed", **best})
    else:
        emit({"status": "no_witness", "basis": None, "vector": [], "upper_bound": None})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit({"status": "error", "basis": None, "vector": [], "upper_bound": None})
