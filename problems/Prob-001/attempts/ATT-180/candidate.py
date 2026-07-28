#!/usr/bin/env python3
import argparse
import json
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

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if {"num_cols", "rows"} <= set(obj):
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            last = -1
            for i in row:
                i = int(i)
                if i <= last or i < 0 or i >= n:
                    raise ValueError(f"invalid sparse row in {path}")
                x |= 1 << i
                last = i
            rows.append(x)
        return rows, n

    raise ValueError(f"unrecognized matrix JSON format: {path}")


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = int(row)
        for p in sorted(basis):
            if (x >> p) & 1:
                x ^= basis[p]
        if x:
            p = (x & -x).bit_length() - 1
            for q, y in list(basis.items()):
                if (y >> p) & 1:
                    basis[q] = y ^ x
            basis[p] = x
    return basis


def reduce_by_basis(x, basis):
    x = int(x)
    for p in sorted(basis):
        if (x >> p) & 1:
            x ^= basis[p]
    return x


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def kernel_basis(check_rows, n):
    eqs = rref_basis(check_rows)
    pivots = set(eqs)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in eqs.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, check_rows):
    for row in check_rows:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def to_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


def randomized_kernel_vector(null_basis, rng):
    v = 0
    # Biased sparse masks often expose lighter representatives than fully
    # uniform masks, while the fallback bit keeps the draw nonzero.
    p = rng.choice((0.08, 0.12, 0.18, 0.25, 0.35, 0.50))
    for b in null_basis:
        if rng.random() < p:
            v ^= b
    if v == 0 and null_basis:
        v = rng.choice(null_basis)
    return v


def descend_weight(v, stabilizers, rng, deadline):
    cur = v
    cur_w = cur.bit_count()
    rows = [r for r in stabilizers if r]
    if not rows:
        return cur

    # Deterministic first-improvement passes, shuffled per restart.
    for _ in range(10):
        if time.monotonic() >= deadline:
            return cur
        improved = False
        rng.shuffle(rows)
        for r in rows:
            w = (cur ^ r).bit_count()
            if w < cur_w:
                cur ^= r
                cur_w = w
                improved = True
        if not improved:
            break

    # Small randomized kicks followed by greedy acceptance. This searches the
    # stabilizer coset without enumerating it.
    best = cur
    best_w = cur_w
    trials = min(700, 12 * len(rows) + 120)
    for _ in range(trials):
        if time.monotonic() >= deadline:
            break
        cand = cur
        for _ in range(rng.randint(1, min(4, len(rows)))):
            cand ^= rng.choice(rows)
        cand_w = cand.bit_count()
        if cand_w <= cur_w or rng.random() < 0.01:
            cur = cand
            cur_w = cand_w
            if cand_w < best_w:
                best = cand
                best_w = cand_w
    return best


def search_basis(name, check_rows, stabilizer_rows, n, rng, deadline):
    null = kernel_basis(check_rows, n)
    stab_basis = rref_basis(stabilizer_rows)

    best = None
    best_w = n + 1

    def consider(v):
        nonlocal best, best_w
        if time.monotonic() >= deadline:
            return
        if v == 0 or in_rowspace(v, stab_basis):
            return
        v = descend_weight(v, stabilizer_rows, rng, deadline)
        if v != 0 and syndrome_zero(v, check_rows) and not in_rowspace(v, stab_basis):
            w = v.bit_count()
            if w < best_w:
                best = v
                best_w = w

    # Include low-weight row-reduced nullspace basis vectors first, then random
    # sparse combinations. This is a heuristic ordering, not a minimum search.
    for v in sorted(null, key=lambda x: x.bit_count())[: min(len(null), 256)]:
        consider(v)

    attempts = min(1800, max(500, 35 * max(1, len(null))))
    light = sorted(null, key=lambda x: x.bit_count())[: min(len(null), 96)]
    for i in range(attempts):
        if time.monotonic() >= deadline:
            break
        if light and (i % 3) == 0:
            v = 0
            for _ in range(rng.randint(1, min(5, len(light)))):
                v ^= rng.choice(light)
        else:
            v = randomized_kernel_vector(null, rng)
        consider(v)

    if best is None:
        return None
    return {"basis": name, "vector": to_bits(best, n), "upper_bound": best_w}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        n = nx
        rng = random.Random(args.seed)
        deadline = time.monotonic() + 4.5

        results = []
        x_result = search_basis("x", hz, hx, n, rng, deadline)
        if x_result is not None:
            results.append(x_result)
        z_result = search_basis("z", hx, hz, n, rng, deadline)
        if z_result is not None:
            results.append(z_result)

        if results:
            result = min(results, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
            out = {
                "status": "completed",
                "basis": result["basis"],
                "vector": result["vector"],
                "upper_bound": result["upper_bound"],
            }
        else:
            out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
