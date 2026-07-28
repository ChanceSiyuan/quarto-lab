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
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            mask = 0
            if len(row) != n_cols:
                raise ValueError(f"{path}: dense row has wrong length")
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    mask |= 1 << i
            rows.append(mask)
        return n_cols, rows

    if "num_cols" in obj and "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            mask = 0
            for idx in row:
                idx = int(idx)
                if idx <= last or idx < 0 or idx >= n_cols:
                    raise ValueError(f"{path}: sparse row is not strictly increasing")
                mask |= 1 << idx
                last = idx
            rows.append(mask)
        return n_cols, rows

    raise ValueError(f"{path}: unsupported matrix JSON format")


def rref(rows, n):
    rows = [r for r in rows if r]
    out = []
    pivots = []
    rank = 0
    for col in range(n):
        pivot_at = None
        bit = 1 << col
        for i in range(rank, len(rows)):
            if rows[i] & bit:
                pivot_at = i
                break
        if pivot_at is None:
            continue
        rows[rank], rows[pivot_at] = rows[pivot_at], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & bit):
                rows[i] ^= rows[rank]
        out.append(rows[rank])
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return out, pivots


def reduce_by_basis(v, basis, pivots):
    for row, pivot in zip(basis, pivots):
        if v & (1 << pivot):
            v ^= row
    return v


def in_rowspace(v, basis, pivots):
    return reduce_by_basis(v, basis, pivots) == 0


def add_to_basis(v, basis, pivots):
    v = reduce_by_basis(v, basis, pivots)
    if v == 0:
        return False
    pivot = (v & -v).bit_length() - 1
    for i, row in enumerate(basis):
        if row & (1 << pivot):
            basis[i] = row ^ v
    insert_at = 0
    while insert_at < len(pivots) and pivots[insert_at] < pivot:
        insert_at += 1
    basis.insert(insert_at, v)
    pivots.insert(insert_at, pivot)
    return True


def nullspace_basis(check_rows, n):
    basis, pivots = rref(check_rows, n)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    out = []
    for free in free_cols:
        v = 1 << free
        for row, pivot in zip(basis, pivots):
            if row & (1 << free):
                v |= 1 << pivot
        out.append(v)
    return out


def syndrome_zero(v, check_rows):
    return all(((v & row).bit_count() & 1) == 0 for row in check_rows)


def verify(v, check_rows, stab_basis, stab_pivots):
    return v != 0 and syndrome_zero(v, check_rows) and not in_rowspace(v, stab_basis, stab_pivots)


def bits_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def greedy_coset_reduce(v, stab_rows, rng, passes):
    if not stab_rows:
        return v
    rows = [r for r in stab_rows if r]
    rows.sort(key=lambda x: x.bit_count())
    best = v
    best_w = v.bit_count()
    for p in range(passes):
        if p:
            rng.shuffle(rows)
        changed = False
        for row in rows:
            cand = best ^ row
            w = cand.bit_count()
            if w < best_w or (w == best_w and rng.random() < 0.03):
                best = cand
                best_w = w
                changed = True
        if not changed and p >= 1:
            break
    return best


def quotient_generators(kernel, stab_rows, n):
    span_basis, span_pivots = rref(stab_rows, n)
    logicals = []
    for v in sorted(kernel, key=lambda x: x.bit_count()):
        if add_to_basis(v, span_basis, span_pivots):
            logicals.append(v)
    return logicals


def random_combo(vectors, rng, density=None):
    if not vectors:
        return 0
    if density is None:
        density = rng.choice((0.08, 0.15, 0.25, 0.5))
    v = 0
    used = False
    for row in vectors:
        if rng.random() < density:
            v ^= row
            used = True
    if not used:
        v = rng.choice(vectors)
    return v


def search_basis(name, check_rows, stab_rows, n, rng, deadline):
    stab_basis, stab_pivots = rref(stab_rows, n)
    kernel = nullspace_basis(check_rows, n)
    logicals = quotient_generators(kernel, stab_rows, n)
    if not logicals:
        return None

    best = None
    best_w = n + 1

    seeds = logicals[:]
    for g in logicals[: min(len(logicals), 32)]:
        seeds.append(greedy_coset_reduce(g, stab_rows, rng, 8))

    iteration = 0
    while time.monotonic() < deadline:
        iteration += 1
        if seeds:
            v = seeds.pop()
        else:
            # Random quotient element, then random stabilizer displacement and
            # greedy descent inside that stabilizer coset.
            q = random_combo(logicals, rng)
            if stab_rows and rng.random() < 0.65:
                q ^= random_combo(stab_rows, rng, rng.choice((0.03, 0.08, 0.15)))
            v = greedy_coset_reduce(q, stab_rows, rng, rng.choice((3, 5, 8, 13)))

        if verify(v, check_rows, stab_basis, stab_pivots):
            w = v.bit_count()
            if w < best_w:
                best = v
                best_w = w

        if iteration > 250 and best is not None and len(logicals) <= 2:
            break

    if best is None:
        return None
    return {"basis": name, "vector": bits_list(best, n), "upper_bound": best_w}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    nx, hx = read_matrix(args.hx)
    nz, hz = read_matrix(args.hz)
    if nx != nz:
        raise ValueError("Hx and Hz have different numbers of physical qubits")
    n = nx
    os.makedirs(args.output_dir, exist_ok=True)

    # Keep runtime bounded but allow enough randomized polishing for moderate
    # LDPC instances. Certification is performed independently after search.
    deadline = time.monotonic() + float(os.environ.get("CANDIDATE_TIME_LIMIT", "25"))
    order = ["x", "z"]
    rng.shuffle(order)
    results = []
    for basis in order:
        if time.monotonic() >= deadline:
            break
        if basis == "x":
            result = search_basis("x", hz, hx, n, rng, deadline)
        else:
            result = search_basis("z", hx, hz, n, rng, deadline)
        if result is not None:
            results.append(result)

    if results:
        result = min(results, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
        out = {
            "status": "completed",
            "basis": result["basis"],
            "vector": result["vector"],
            "upper_bound": result["upper_bound"],
        }
    else:
        out = {"status": "not_found", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "error", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))
        sys.exit(0)
