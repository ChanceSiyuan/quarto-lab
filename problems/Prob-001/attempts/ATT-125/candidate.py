#!/usr/bin/env python3
import argparse
import json
import random


def row_weight(x):
    return x.bit_count()


def parity(x):
    return x.bit_count() & 1


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    rows = []
    if isinstance(obj, dict) and {"n_rows", "n_cols", "data"} <= set(obj):
        n = int(obj["n_cols"])
        for row in obj["data"]:
            x = 0
            if len(row) != n:
                raise ValueError("dense row has wrong length")
            for j, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix is not binary")
                if bit:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if isinstance(obj, dict) and {"num_cols", "rows"} <= set(obj):
        n = int(obj["num_cols"])
        for inds in obj["rows"]:
            last = -1
            x = 0
            for j in inds:
                j = int(j)
                if j <= last or j < 0 or j >= n:
                    raise ValueError("sparse row indices are not strictly increasing")
                x |= 1 << j
                last = j
            rows.append(x)
        return rows, n

    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        for row in obj:
            if len(row) != n:
                raise ValueError("ragged dense matrix")
            x = 0
            for j, bit in enumerate(row):
                if bit:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def reduce_with_basis(x, basis):
    for p in sorted(basis):
        if (x >> p) & 1:
            x ^= basis[p]
    return x


def add_to_basis(x, basis):
    x = reduce_with_basis(x, basis)
    if x == 0:
        return False
    pivot = (x & -x).bit_length() - 1
    for p, row in list(basis.items()):
        if (row >> pivot) & 1:
            basis[p] = row ^ x
    basis[pivot] = x
    return True


def rref_basis(rows):
    basis = {}
    for row in rows:
        if row:
            add_to_basis(row, basis)
    return basis


def in_rowspace(x, basis):
    return reduce_with_basis(x, basis) == 0


def nullspace_basis(check_rows, n):
    checks = rref_basis(check_rows)
    pivots = set(checks)
    out = []
    for free_col in range(n):
        if free_col in pivots:
            continue
        x = 1 << free_col
        for p in sorted(checks, reverse=True):
            if parity(checks[p] & x):
                x |= 1 << p
        out.append(x)
    return out


def is_kernel(v, checks):
    return all(parity(v & row) == 0 for row in checks)


def logical_representatives(check_rows, stab_rows, n):
    kernel = nullspace_basis(check_rows, n)
    stab_basis = rref_basis(stab_rows)
    combined = dict(stab_basis)
    reps = []
    for v in kernel:
        reduced = reduce_with_basis(v, combined)
        if reduced and not in_rowspace(reduced, stab_basis):
            reps.append(reduced)
            add_to_basis(reduced, combined)
    return reps, stab_basis


def greedy_reduce(v, stabilizers, rng, rounds=8):
    if not stabilizers:
        return v
    best = v
    best_w = row_weight(best)
    rows = list(stabilizers)
    rows.sort(key=row_weight)
    for _ in range(rounds):
        changed = False
        rng.shuffle(rows)
        rows.sort(key=lambda r: (row_weight(best ^ r) - best_w, row_weight(r)))
        for row in rows:
            cand = best ^ row
            w = row_weight(cand)
            if w < best_w or (w == best_w and w > 0 and rng.random() < 0.015):
                best, best_w = cand, w
                changed = True
        if not changed:
            break
    return best


def random_logical_combo(reps, rng):
    v = 0
    while v == 0:
        for rep in reps:
            if rng.getrandbits(1):
                v ^= rep
    return v


def search_basis(name, check_rows, stab_rows, n, rng):
    reps, stab_basis = logical_representatives(check_rows, stab_rows, n)
    if not reps:
        return None

    stabilizers = [r for r in stab_rows if r]
    best = None
    best_w = n + 1

    seeds = list(reps)
    for rep in reps:
        seeds.append(greedy_reduce(rep, stabilizers, rng, rounds=12))

    k = len(reps)
    iterations = min(25000, max(1200, 120 * n + 500 * k))
    for t in range(iterations):
        if t < len(seeds):
            v = seeds[t]
        else:
            v = random_logical_combo(reps, rng)
            if stabilizers and rng.random() < 0.35:
                for _ in range(rng.randrange(1, min(6, len(stabilizers)) + 1)):
                    v ^= stabilizers[rng.randrange(len(stabilizers))]
        v = greedy_reduce(v, stabilizers, rng, rounds=6)
        w = row_weight(v)
        if 0 < w < best_w and is_kernel(v, check_rows) and not in_rowspace(v, stab_basis):
            best, best_w = v, w
            if best_w == 1:
                break

    if best is None:
        return None
    return {"basis": name, "vector_int": best, "upper_bound": best_w}


def int_to_bits(x, n):
    return [(x >> j) & 1 for j in range(n)]


def failure():
    return {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("HX and HZ have different column counts")
        n = nx
        rng = random.Random(args.seed)

        candidates = [
            search_basis("x", hz, hx, n, rng),
            search_basis("z", hx, hz, n, rng),
        ]
        candidates = [c for c in candidates if c is not None]
        if not candidates:
            result = failure()
        else:
            best = min(candidates, key=lambda c: (c["upper_bound"], c["basis"]))
            result = {
                "status": "completed",
                "basis": best["basis"],
                "vector": int_to_bits(best["vector_int"], n),
                "upper_bound": best["upper_bound"],
            }
    except Exception:
        result = failure()

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
