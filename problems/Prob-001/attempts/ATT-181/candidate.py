#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def project_path(path):
    root = os.path.realpath(os.getcwd())
    full = os.path.realpath(path)
    if full != root and not full.startswith(root + os.sep):
        raise ValueError("paths must stay inside the current project directory")
    return full


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            last = -1
            for i in row:
                i = int(i)
                if i <= last or i < 0 or i >= n:
                    raise ValueError("sparse_rows rows must be strictly increasing valid indices")
                x |= 1 << i
                last = i
            rows.append(x)
        return rows, n

    raise ValueError("unknown matrix JSON format")


def rref_rows(rows, n):
    rows = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        bit = 1 << col
        pivot = None
        for j in range(rank, len(rows)):
            if rows[j] & bit:
                pivot = j
                break
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for j in range(len(rows)):
            if j != rank and (rows[j] & bit):
                rows[j] ^= rows[rank]
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return rows[:rank], pivots


def reduce_by_rref(v, basis, pivots):
    for row, col in zip(basis, pivots):
        if (v >> col) & 1:
            v ^= row
    return v


def in_rowspace(v, basis, pivots):
    return reduce_by_rref(v, basis, pivots) == 0


def kernel_basis(check_rows, n):
    rr, pivots = rref_rows(check_rows, n)
    pivot_set = set(pivots)
    out = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, col in reversed(list(zip(rr, pivots))):
            if (row >> free) & 1:
                v |= 1 << col
        out.append(v)
    return out


def syndrome_zero(v, check_rows):
    for row in check_rows:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def solve_syndrome_from_rref(syndrome, rr, pivots):
    v = 0
    for i, col in enumerate(pivots):
        if (syndrome >> i) & 1:
            v |= 1 << col
    return v


def syndrome_bits(v, check_rows):
    s = 0
    for i, row in enumerate(check_rows):
        if (v & row).bit_count() & 1:
            s |= 1 << i
    return s


def minimize_preserving_kernel(v, pool, rng, passes):
    best = v
    best_w = best.bit_count()
    pool = [p for p in pool if p]
    for _ in range(passes):
        changed = False
        rng.shuffle(pool)
        for p in pool:
            candidate = best ^ p
            if candidate == 0:
                continue
            w = candidate.bit_count()
            if w < best_w:
                best = candidate
                best_w = w
                changed = True
        if not changed:
            break
    return best


def random_kernel_combo(kbasis, rng):
    if not kbasis:
        return 0
    v = 0
    # Bias toward sparse combinations, with an occasional denser draw.
    if rng.random() < 0.75:
        count = 1 + rng.randrange(min(len(kbasis), 12))
        for p in rng.sample(kbasis, count):
            v ^= p
    else:
        for p in kbasis:
            if rng.random() < 0.5:
                v ^= p
    return v


def best_for_basis(name, check_rows, stab_rows, n, rng, budget):
    stab_rr, stab_pivots = rref_rows(stab_rows, n)
    check_rr, check_pivots = rref_rows(check_rows, n)
    kbasis = kernel_basis(check_rows, n)
    if not kbasis:
        return None

    pool = list(stab_rr)
    pool.extend(kbasis)
    best = None
    best_w = n + 1

    def consider(v, polish=3):
        nonlocal best, best_w
        if v == 0:
            return
        v = minimize_preserving_kernel(v, pool, rng, polish)
        if v == 0 or not syndrome_zero(v, check_rows):
            return
        if in_rowspace(v, stab_rr, stab_pivots):
            return
        w = v.bit_count()
        if w < best_w:
            best = v
            best_w = w

    for v in kbasis:
        consider(v, 4)

    for row in check_rows:
        # A check-row complement often seeds useful low-density residuals.
        if row:
            mask = row
            v = 0
            while mask:
                b = mask & -mask
                if rng.random() < 0.5:
                    v |= b
                mask ^= b
            s = syndrome_bits(v, check_rr)
            consider(v ^ solve_syndrome_from_rref(s, check_rr, check_pivots), 3)

    for t in range(budget):
        if t & 1:
            v = random_kernel_combo(kbasis, rng)
        else:
            density = 0.015 + 0.18 * rng.random()
            v = 0
            for i in range(n):
                if rng.random() < density:
                    v |= 1 << i
            s = syndrome_bits(v, check_rr)
            v ^= solve_syndrome_from_rref(s, check_rr, check_pivots)
        consider(v, 2 if best is None else 1)

    if best is None:
        return None
    return {"basis": name, "vector_int": best, "upper_bound": best_w}


def vector_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    hx_path = project_path(args.hx)
    hz_path = project_path(args.hz)
    output_dir = project_path(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    hx, nx = load_matrix(hx_path)
    hz, nz = load_matrix(hz_path)
    if nx != nz:
        raise ValueError("hx and hz must have the same number of columns")
    n = nx

    # X logicals commute with Hz and are nontrivial modulo row(Hx);
    # Z logicals commute with Hx and are nontrivial modulo row(Hz).
    budget = max(512, min(12000, 64 * max(1, n)))
    bx = best_for_basis("x", hz, hx, n, rng, budget)
    bz = best_for_basis("z", hx, hz, n, rng, budget)
    candidates = [c for c in (bx, bz) if c is not None]

    if candidates:
        chosen = min(candidates, key=lambda c: (c["upper_bound"], 0 if c["basis"] == "x" else 1))
        result = {
            "status": "completed",
            "basis": chosen["basis"],
            "vector": vector_list(chosen["vector_int"], n),
            "upper_bound": chosen["upper_bound"],
        }
    else:
        result = {"status": "not_found", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _ = exc
        print(json.dumps({"status": "error", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
        sys.exit(1)
