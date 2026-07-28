#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as handle:
        obj = json.load(handle)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_cols" in obj and "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            if len(row) != n_cols:
                raise ValueError(f"dense row length {len(row)} != n_cols {n_cols}")
            for i, value in enumerate(row):
                if value not in (0, 1, False, True):
                    raise ValueError("matrix entries must be binary")
                if value:
                    bits |= 1 << i
            rows.append(bits)
        return n_cols, rows

    if "num_cols" in obj and "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            bits = 0
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("sparse rows must be strictly increasing valid columns")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return n_cols, rows

    raise ValueError("unsupported matrix JSON format")


def pivot_basis(rows):
    basis = {}
    for value in rows:
        x = value
        while x:
            pivot = x.bit_length() - 1
            if pivot not in basis:
                for other_pivot, other in list(basis.items()):
                    if (other >> pivot) & 1:
                        basis[other_pivot] = other ^ x
                basis[pivot] = x
                break
            x ^= basis[pivot]
    return basis


def reduce_by_basis(value, basis):
    x = value
    while x:
        pivot = x.bit_length() - 1
        row = basis.get(pivot)
        if row is None:
            break
        x ^= row
    return x


def in_span(value, basis):
    return reduce_by_basis(value, basis) == 0


def nullspace_basis(check_rows, n_cols):
    pivots = pivot_basis(check_rows)
    pivot_cols = set(pivots)
    out = []
    for free_col in range(n_cols):
        if free_col in pivot_cols:
            continue
        v = 1 << free_col
        for pivot, row in pivots.items():
            if (row >> free_col) & 1:
                v |= 1 << pivot
        out.append(v)
    return out


def syndrome_zero(vector, checks):
    for row in checks:
        if (vector & row).bit_count() & 1:
            return False
    return True


def logical_generators(kernel_basis, stabilizers):
    span = pivot_basis(stabilizers)
    logicals = []
    for row in kernel_basis:
        if reduce_by_basis(row, span) != 0:
            logicals.append(row)
            span = pivot_basis(list(span.values()) + [row])
    return logicals


def random_combo(rows, rng, force_nonempty=False):
    value = 0
    used = False
    for row in rows:
        if rng.getrandbits(1):
            value ^= row
            used = True
    if force_nonempty and rows and not used:
        value ^= rows[rng.randrange(len(rows))]
    return value


def greedy_reduce(value, stabilizers, rng, passes):
    if not stabilizers:
        return value
    current = value
    current_w = current.bit_count()
    rows = list(stabilizers)
    for _ in range(passes):
        rng.shuffle(rows)
        changed = False
        for row in rows:
            candidate = current ^ row
            weight = candidate.bit_count()
            if weight < current_w or (weight == current_w and rng.randrange(32) == 0):
                if weight <= current_w:
                    current = candidate
                    current_w = weight
                    changed = True
        if not changed:
            break
    return current


def coordinate_descent(value, stabilizers, n_cols, rng, steps):
    if not stabilizers:
        return value
    incidence = [[] for _ in range(n_cols)]
    for row in stabilizers:
        x = row
        while x:
            lsb = x & -x
            incidence[lsb.bit_length() - 1].append(row)
            x ^= lsb

    current = value
    current_w = current.bit_count()
    for _ in range(steps):
        ones = []
        x = current
        while x:
            lsb = x & -x
            ones.append(lsb.bit_length() - 1)
            x ^= lsb
        if not ones:
            break
        rng.shuffle(ones)
        improved = False
        for col in ones[: min(len(ones), 24)]:
            rows = incidence[col]
            if not rows:
                continue
            sample_size = min(len(rows), 48)
            for row in rng.sample(rows, sample_size):
                candidate = current ^ row
                weight = candidate.bit_count()
                if weight < current_w:
                    current = candidate
                    current_w = weight
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    return current


def verified(vector, commute_checks, stabilizers):
    return (
        vector != 0
        and syndrome_zero(vector, commute_checks)
        and not in_span(vector, pivot_basis(stabilizers))
    )


def search_basis(name, commute_checks, stabilizers, n_cols, rng):
    kernel = nullspace_basis(commute_checks, n_cols)
    logicals = logical_generators(kernel, stabilizers)
    if not logicals:
        return None

    best = None
    attempts = max(256, min(8192, 96 * len(logicals) + 8 * len(stabilizers) + 4 * n_cols))
    stab_basis_rows = list(pivot_basis(stabilizers).values())
    all_stabilizers = list(stabilizers) + stab_basis_rows

    seeds = list(logicals)
    rng.shuffle(seeds)
    for base in seeds[: min(len(seeds), 128)]:
        attempts += 1
        candidate = base ^ random_combo(stab_basis_rows, rng)
        candidate = greedy_reduce(candidate, all_stabilizers, rng, 6)
        candidate = coordinate_descent(candidate, all_stabilizers, n_cols, rng, 64)
        candidate = greedy_reduce(candidate, all_stabilizers, rng, 3)
        if verified(candidate, commute_checks, stabilizers):
            if best is None or candidate.bit_count() < best.bit_count():
                best = candidate

    for _ in range(attempts):
        logical_part = random_combo(logicals, rng, force_nonempty=True)
        candidate = logical_part ^ random_combo(stab_basis_rows, rng)
        if all_stabilizers and rng.randrange(3) == 0:
            for row in rng.sample(all_stabilizers, min(len(all_stabilizers), rng.randrange(1, 9))):
                candidate ^= row
        candidate = greedy_reduce(candidate, all_stabilizers, rng, 8)
        candidate = coordinate_descent(candidate, all_stabilizers, n_cols, rng, 96)
        candidate = greedy_reduce(candidate, all_stabilizers, rng, 4)
        if verified(candidate, commute_checks, stabilizers):
            if best is None or candidate.bit_count() < best.bit_count():
                best = candidate

    if best is None:
        return None
    return {"basis": name, "vector_int": best, "upper_bound": best.bit_count()}


def bits_to_list(value, n_cols):
    return [int((value >> i) & 1) for i in range(n_cols)]


def main():
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    n_x, hx = load_matrix(args.hx)
    n_z, hz = load_matrix(args.hz)
    if n_x != n_z:
        raise ValueError("hx and hz must have the same number of columns")
    n_cols = n_x
    rng = random.Random(args.seed)

    results = []
    x_result = search_basis("x", hz, hx, n_cols, rng)
    if x_result is not None:
        results.append(x_result)
    z_result = search_basis("z", hx, hz, n_cols, rng)
    if z_result is not None:
        results.append(z_result)

    if results:
        best = min(results, key=lambda item: (item["upper_bound"], item["basis"]))
        output = {
            "status": "completed",
            "basis": best["basis"],
            "vector": bits_to_list(best["vector_int"], n_cols),
            "upper_bound": best["upper_bound"],
        }
    else:
        output = {
            "status": "not_found",
            "basis": "x",
            "vector": [0] * n_cols,
            "upper_bound": None,
        }

    print(json.dumps(output, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _ = exc
        print(json.dumps({"status": "error", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))
        sys.exit(1)
