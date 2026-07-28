#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            mask = 0
            if len(row) != n:
                raise ValueError("dense row has wrong length")
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            mask = 0
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n:
                    raise ValueError("sparse row indices must be strictly increasing")
                mask |= 1 << col
                last = col
            rows.append(mask)
        return rows, n

    raise ValueError("unrecognized matrix JSON format")


def popcount(x):
    return int(x).bit_count()


def rref_rows(rows):
    pivots = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if p in pivots:
                x ^= pivots[p]
            else:
                pivots[p] = x
                break

    ordered = sorted(pivots.items(), reverse=True)
    for p, row in ordered:
        x = row
        for q, other in ordered:
            if q != p and ((other >> p) & 1):
                pivots[q] = other ^ x
        ordered = sorted(pivots.items(), reverse=True)
    return [(p, pivots[p]) for p in sorted(pivots, reverse=True)]


def row_basis(rows):
    return [row for _, row in rref_rows(rows)]


def in_rowspace(v, basis):
    x = v
    for row in basis:
        if not x:
            return True
        p = row.bit_length() - 1
        if (x >> p) & 1:
            x ^= row
    return x == 0


def nullspace_basis(rows, n):
    rref = rref_rows(rows)
    pivot_cols = {p for p, _ in rref}
    free_cols = [c for c in range(n) if c not in pivot_cols]
    out = []
    for f in free_cols:
        x = 1 << f
        for p, row in rref:
            if (row >> f) & 1:
                x |= 1 << p
        out.append(x)
    return out


def mat_vec_zero(rows, v):
    return all((popcount(row & v) & 1) == 0 for row in rows)


def mask_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def random_combination(items, rng, density):
    x = 0
    used = False
    for item in items:
        if rng.random() < density:
            x ^= item
            used = True
    if not used and items:
        x = rng.choice(items)
    return x


def greedy_stabilizer_descent(v, stabilizers, rng, passes):
    if not stabilizers:
        return v
    cur = v
    cur_w = popcount(cur)
    rows = list(stabilizers)
    for _ in range(passes):
        changed = False
        rng.shuffle(rows)
        for row in rows:
            nxt = cur ^ row
            nxt_w = popcount(nxt)
            if nxt_w < cur_w or (nxt_w == cur_w and rng.random() < 0.015):
                cur, cur_w = nxt, nxt_w
                changed = True
        if not changed:
            break
    return cur


def verify_witness(v, check_rows, stabilizer_basis):
    return v != 0 and mat_vec_zero(check_rows, v) and not in_rowspace(v, stabilizer_basis)


def search_basis(name, check_rows, stabilizer_rows, n, rng, deadline):
    stabilizer_basis = row_basis(stabilizer_rows)
    kernel = nullspace_basis(check_rows, n)
    if not kernel:
        return None

    candidates = list(kernel)
    for _ in range(min(64, max(8, len(kernel) * 2))):
        density = rng.choice((0.08, 0.12, 0.18, 0.25, 0.35, 0.5))
        candidates.append(random_combination(kernel, rng, density))

    best = None
    best_w = n + 1

    def consider(v):
        nonlocal best, best_w
        v = greedy_stabilizer_descent(v, stabilizer_rows, rng, 10)
        if verify_witness(v, check_rows, stabilizer_basis):
            w = popcount(v)
            if w < best_w:
                best, best_w = v, w

    for v in candidates:
        consider(v)

    trials = 0
    max_trials = max(300, min(12000, 80 * (n + len(kernel) + len(stabilizer_rows) + 1)))
    while time.time() < deadline and trials < max_trials:
        trials += 1
        density = rng.betavariate(0.7, 3.0)
        density = max(1.0 / max(1, len(kernel)), min(0.65, density))
        v = random_combination(kernel, rng, density)

        # A few noisy stabilizer moves can jump between local minima in the same
        # logical coset before the deterministic weight descent cleans it up.
        for row in rng.sample(stabilizer_rows, min(len(stabilizer_rows), rng.randrange(0, 5))):
            if rng.random() < 0.5:
                v ^= row
        consider(v)

    if best is None:
        return None
    return {"basis": name, "vector": mask_to_list(best, n), "upper_bound": best_w}


def main():
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz have different numbers of columns")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        n = nx
        deadline = time.time() + 25.0
        basis_order = [("x", hz, hx), ("z", hx, hz)]
        rng.shuffle(basis_order)

        results = []
        for name, check_rows, stabilizer_rows in basis_order:
            result = search_basis(name, check_rows, stabilizer_rows, n, rng, deadline)
            if result is not None:
                results.append(result)

        if results:
            result = min(results, key=lambda r: (r["upper_bound"], r["basis"]))
            print(json.dumps({"status": "completed", **result}, separators=(",", ":")))
        else:
            print(json.dumps({"status": "not_found", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
    except Exception:
        print(json.dumps({"status": "error", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))


if __name__ == "__main__":
    main()
