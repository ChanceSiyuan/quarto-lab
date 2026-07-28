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
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"}.issubset(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            if len(row) != n_cols:
                raise ValueError("dense row has wrong length")
            for i, value in enumerate(row):
                if value not in (0, 1, False, True):
                    raise ValueError("dense matrix contains a non-binary entry")
                if int(value):
                    bits |= 1 << i
            rows.append(bits)
        if len(rows) != int(obj["n_rows"]):
            raise ValueError("dense matrix row count mismatch")
        return n_cols, rows

    if {"num_cols", "rows"}.issubset(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return n_cols, rows

    raise ValueError("unrecognized matrix JSON format")


def rref_basis(rows):
    basis = {}
    for original in rows:
        row = int(original)
        while row:
            pivot = row.bit_length() - 1
            reducer = basis.get(pivot)
            if reducer is None:
                break
            row ^= reducer
        if not row:
            continue
        pivot = row.bit_length() - 1
        for other_pivot, other in list(basis.items()):
            if (other >> pivot) & 1:
                basis[other_pivot] = other ^ row
        basis[pivot] = row
    return dict(sorted(basis.items(), reverse=True))


def reduce_by_basis(vec, basis):
    out = int(vec)
    while out:
        pivot = out.bit_length() - 1
        reducer = basis.get(pivot)
        if reducer is None:
            break
        out ^= reducer
    return out


def in_rowspace(vec, basis):
    return reduce_by_basis(vec, basis) == 0


def nullspace_basis(n_cols, rows):
    rbasis = rref_basis(rows)
    pivots = set(rbasis)
    free_cols = [c for c in range(n_cols) if c not in pivots]
    out = []
    for free in free_cols:
        vec = 1 << free
        for pivot, row in rbasis.items():
            if (row >> free) & 1:
                vec |= 1 << pivot
        out.append(vec)
    return out


def syndrome_zero(vec, checks):
    for row in checks:
        if ((vec & row).bit_count() & 1) != 0:
            return False
    return True


def bit_list(vec, n_cols):
    return [(vec >> i) & 1 for i in range(n_cols)]


def random_kernel_vector(rng, kernel_basis, n_cols):
    if not kernel_basis:
        return 0
    vec = 0
    mode = rng.randrange(4)
    if mode == 0:
        terms = rng.randint(1, min(len(kernel_basis), max(1, 6)))
        for idx in rng.sample(range(len(kernel_basis)), terms):
            vec ^= kernel_basis[idx]
    elif mode == 1:
        p = min(0.5, max(1.0 / len(kernel_basis), rng.random() * 0.25 + 0.03))
        for base in kernel_basis:
            if rng.random() < p:
                vec ^= base
    elif mode == 2:
        target = rng.randrange(n_cols)
        choices = [b for b in kernel_basis if (b >> target) & 1] or kernel_basis
        terms = rng.randint(1, min(len(choices), max(1, 5)))
        for base in rng.sample(choices, terms):
            vec ^= base
    else:
        for base in kernel_basis:
            if rng.getrandbits(1):
                vec ^= base
    return vec


def descend_coset(vec, stabilizers, rng, deadline):
    current = vec
    if not current:
        return current
    rows = [r for r in stabilizers if r]
    rows.sort(key=int.bit_count)
    best = current

    passes = 8 + min(24, len(rows) // 8)
    for _ in range(passes):
        if time.monotonic() > deadline:
            break
        changed = False
        if rng.random() < 0.55:
            work = rows[:]
            rng.shuffle(work)
        else:
            work = rows
        for row in work:
            candidate = current ^ row
            if candidate and candidate.bit_count() < current.bit_count():
                current = candidate
                changed = True
                if current.bit_count() < best.bit_count():
                    best = current
        if not changed:
            break

    small = rows[: min(len(rows), 96)]
    for _ in range(256):
        if time.monotonic() > deadline or not small:
            break
        tweak = 0
        for row in rng.sample(small, rng.randint(1, min(4, len(small)))):
            tweak ^= row
        candidate = current ^ tweak
        if candidate and candidate.bit_count() <= current.bit_count():
            current = candidate
            for row in small:
                nxt = current ^ row
                if nxt and nxt.bit_count() < current.bit_count():
                    current = nxt
            if current.bit_count() < best.bit_count():
                best = current
    return best


def verified(vec, kernel_checks, stabilizer_basis):
    return bool(vec) and syndrome_zero(vec, kernel_checks) and not in_rowspace(vec, stabilizer_basis)


def search_basis(label, n_cols, kernel_checks, stabilizer_rows, rng, deadline):
    kernel = nullspace_basis(n_cols, kernel_checks)
    stabilizer_basis = rref_basis(stabilizer_rows)
    if len(kernel) <= len(stabilizer_basis):
        return None

    best = None
    seeds = sorted(kernel, key=int.bit_count)[: min(len(kernel), 128)]
    trials = 2500 + 60 * len(kernel) + 15 * len(stabilizer_rows)
    for trial in range(trials):
        if time.monotonic() > deadline:
            break
        if trial < len(seeds):
            vec = seeds[trial]
        else:
            vec = random_kernel_vector(rng, kernel, n_cols)
        if not vec or in_rowspace(vec, stabilizer_basis):
            continue
        vec = descend_coset(vec, stabilizer_rows, rng, deadline)
        if verified(vec, kernel_checks, stabilizer_basis):
            if best is None or vec.bit_count() < best.bit_count():
                best = vec
    if best is None:
        return None
    return {
        "status": "completed",
        "basis": label,
        "vector": bit_list(best, n_cols),
        "upper_bound": best.bit_count(),
    }


def main():
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    try:
        hx_n, hx_rows = load_matrix(args.hx)
        hz_n, hz_rows = load_matrix(args.hz)
        if hx_n != hz_n:
            raise ValueError("Hx and Hz have different column counts")
        n_cols = hx_n
        os.makedirs(args.output_dir, exist_ok=True)

        deadline = time.monotonic() + float(os.environ.get("CANDIDATE_TIME_LIMIT", "25"))
        order = [("x", hz_rows, hx_rows), ("z", hx_rows, hz_rows)]
        if rng.getrandbits(1):
            order.reverse()

        results = []
        for label, kernel_checks, stabilizers in order:
            result = search_basis(label, n_cols, kernel_checks, stabilizers, rng, deadline)
            if result is not None:
                results.append(result)
        if results:
            results.sort(key=lambda r: (r["upper_bound"], r["basis"]))
            print(json.dumps(results[0], separators=(",", ":")))
            return 0
    except Exception:
        pass

    print(json.dumps({"status": "not_found", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
