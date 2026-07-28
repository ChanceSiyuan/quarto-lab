#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_rows = int(obj["n_rows"])
        n_cols = int(obj["n_cols"])
        data = obj["data"]
        rows = []
        if len(data) != n_rows:
            raise ValueError("dense matrix row count does not match n_rows")
        for row in data:
            if len(row) != n_cols:
                raise ValueError("dense matrix row width does not match n_cols")
            bits = 0
            for j, val in enumerate(row):
                if val not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if int(val) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return n_rows, n_cols, rows

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for inds in obj["rows"]:
            prev = -1
            bits = 0
            for raw in inds:
                j = int(raw)
                if j <= prev or j < 0 or j >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing and in range")
                bits |= 1 << j
                prev = j
            rows.append(bits)
        return len(rows), n_cols, rows

    raise ValueError("unrecognized matrix JSON format")


def rref_basis(rows):
    basis = {}
    for raw in rows:
        x = int(raw)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        row = basis[p]
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    return basis


def reduce_with_basis(x, basis):
    y = int(x)
    while y:
        p = y.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return y
        y ^= row
    return 0


def in_span(x, basis):
    return reduce_with_basis(x, basis) == 0


def add_to_basis_inplace(basis, x):
    y = reduce_with_basis(x, basis)
    if not y:
        return False
    p = y.bit_length() - 1
    basis[p] = y
    for q in list(basis):
        if q != p and ((basis[q] >> p) & 1):
            basis[q] ^= y
    return True


def kernel_basis(check_rows, n_cols):
    piv = rref_basis(check_rows)
    pivot_cols = set(piv)
    free_cols = [j for j in range(n_cols) if j not in pivot_cols]
    out = []
    for f in free_cols:
        x = 1 << f
        for p, row in piv.items():
            if (row >> f) & 1:
                x |= 1 << p
        out.append(x)
    return out


def syndrome_zero(x, check_rows):
    return all(((x & row).bit_count() & 1) == 0 for row in check_rows)


def bits_to_list(x, n):
    return [(x >> j) & 1 for j in range(n)]


def greedy_stabilizer_descent(x, stab_rows, rng, rounds):
    if not stab_rows:
        return x
    cur = x
    cur_w = cur.bit_count()
    rows = list(stab_rows)
    for _ in range(rounds):
        rng.shuffle(rows)
        improved = False
        for s in rows:
            y = cur ^ s
            yw = y.bit_count()
            if yw < cur_w or (yw == cur_w and rng.random() < 0.03):
                cur, cur_w = y, yw
                improved = True
        if not improved:
            break
    return cur


def localized_kernel_vector(seed, check_rows, n_cols, rng):
    """Repair a random sparse seed to a kernel vector using pivot equations."""
    piv = rref_basis(check_rows)
    pivot_cols = set(piv)
    x = seed
    for p in pivot_cols:
        x &= ~(1 << p)
    for p, row in piv.items():
        parity = ((x & row).bit_count() & 1)
        if parity:
            x |= 1 << p
    if x == 0:
        frees = [j for j in range(n_cols) if j not in pivot_cols]
        if frees:
            x = 1 << rng.choice(frees)
            for p in pivot_cols:
                x &= ~(1 << p)
            for p, row in piv.items():
                if ((x & row).bit_count() & 1):
                    x |= 1 << p
    return x


def logical_generators(check_rows, stab_rows, n_cols, rng):
    ker = kernel_basis(check_rows, n_cols)
    rng.shuffle(ker)
    span = rref_basis(stab_rows)
    gens = []
    for v in ker:
        if not in_span(v, span):
            gens.append(v)
            add_to_basis_inplace(span, v)
    return gens


def search_basis(name, check_rows, stab_rows, n_cols, rng):
    stab_basis = rref_basis(stab_rows)
    gens = logical_generators(check_rows, stab_rows, n_cols, rng)
    if not gens:
        return None

    best = None

    def consider(v):
        nonlocal best
        if v and syndrome_zero(v, check_rows) and not in_span(v, stab_basis):
            v = greedy_stabilizer_descent(v, stab_rows, rng, 10)
            if syndrome_zero(v, check_rows) and not in_span(v, stab_basis):
                if best is None or v.bit_count() < best.bit_count():
                    best = v

    for g in gens:
        consider(g)

    n_gens = len(gens)
    trials = max(600, min(20000, 1200 + 120 * n_gens + 20 * n_cols))
    for t in range(trials):
        if t % 5 == 0:
            k = 1 + int(rng.expovariate(0.7))
            k = min(k, n_gens)
            idxs = rng.sample(range(n_gens), k)
        else:
            p = min(0.5, max(1.5 / max(n_gens, 1), rng.random() * 0.25))
            idxs = [i for i in range(n_gens) if rng.random() < p]
            if not idxs:
                idxs = [rng.randrange(n_gens)]
        v = 0
        for i in idxs:
            v ^= gens[i]

        if t % 3 == 0:
            target = max(1, int(rng.expovariate(1.0 / max(2, n_cols // 24))))
            seed = 0
            for j in rng.sample(range(n_cols), min(n_cols, target)):
                seed |= 1 << j
            repaired = localized_kernel_vector(seed, check_rows, n_cols, rng)
            if repaired and not in_span(repaired, stab_basis):
                v ^= repaired

        consider(v)

    if best is None:
        return None
    return {
        "status": "completed",
        "basis": name,
        "vector": bits_to_list(best, n_cols),
        "upper_bound": best.bit_count(),
    }


def main():
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    try:
        _, nx, hx = load_matrix(args.hx)
        _, nz, hz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz have different numbers of columns")

        candidates = [
            search_basis("x", hz, hx, nx, rng),
            search_basis("z", hx, hz, nx, rng),
        ]
        candidates = [c for c in candidates if c is not None]
        if candidates:
            result = min(candidates, key=lambda c: c["upper_bound"])
        else:
            result = {"status": "not_found", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "error", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
