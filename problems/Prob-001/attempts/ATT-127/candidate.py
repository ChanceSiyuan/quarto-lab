#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def fail():
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))


def row_to_int(row, n_cols):
    x = 0
    prev = -1
    for c in row:
        if not isinstance(c, int) or c < 0 or c >= n_cols or c <= prev:
            raise ValueError("invalid sparse row")
        x |= 1 << c
        prev = c
    return x


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
        for r in obj["data"]:
            if len(r) != n:
                raise ValueError("dense row length mismatch")
            x = 0
            for i, b in enumerate(r):
                if b not in (0, 1, False, True):
                    raise ValueError("dense matrix is not binary")
                if b:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        return [row_to_int(r, n) for r in obj["rows"]], n

    raise ValueError("unrecognized matrix format")


def dot_parity(row, vec):
    return (row & vec).bit_count() & 1


def in_kernel(check_rows, vec):
    return all(dot_parity(r, vec) == 0 for r in check_rows)


def reduce_by_basis(vec, basis):
    x = vec
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def add_to_basis(basis, vec):
    x = reduce_by_basis(vec, basis)
    if not x:
        return 0
    p = x.bit_length() - 1
    for q, b in list(basis.items()):
        if (b >> p) & 1:
            basis[q] = b ^ x
    basis[p] = x
    return x


def make_basis(rows):
    basis = {}
    for r in rows:
        if r:
            add_to_basis(basis, r)
    return basis


def rref(rows, n_cols):
    a = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n_cols):
        bit = 1 << col
        pivot = None
        for i in range(rank, len(a)):
            if a[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        for i in range(len(a)):
            if i != rank and (a[i] & bit):
                a[i] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == len(a):
            break
    return a[:rank], pivots


def nullspace_basis(rows, n_cols):
    rr, pivots = rref(rows, n_cols)
    pivot_set = set(pivots)
    out = []
    for free in range(n_cols):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, piv in zip(rr, pivots):
            if (row >> free) & 1:
                v |= 1 << piv
        out.append(v)
    return out


def int_to_bits(vec, n_cols):
    return [(vec >> i) & 1 for i in range(n_cols)]


def verify(vec, n_cols, check_rows, stabilizer_basis):
    if vec <= 0 or vec >= (1 << n_cols):
        return False
    return in_kernel(check_rows, vec) and reduce_by_basis(vec, stabilizer_basis) != 0


def greedy_reduce(vec, stabilizers, check_rows, stabilizer_basis, n_cols, rng):
    best = vec
    best_w = vec.bit_count()
    rows = list(stabilizers)
    for _ in range(6):
        rng.shuffle(rows)
        changed = False
        for s in rows:
            cand = best ^ s
            w = cand.bit_count()
            if w and w < best_w and verify(cand, n_cols, check_rows, stabilizer_basis):
                best, best_w = cand, w
                changed = True
        if not changed:
            break
    return best


def logical_representatives(check_rows, stabilizer_rows, n_cols, rng):
    stab_in_kernel = [s for s in stabilizer_rows if s and in_kernel(check_rows, s)]
    stab_basis = make_basis(stabilizer_rows)
    quotient_basis = dict(stab_basis)
    reps = []
    kernel = nullspace_basis(check_rows, n_cols)
    rng.shuffle(kernel)
    for k in kernel:
        added = add_to_basis(quotient_basis, k)
        if added and reduce_by_basis(added, stab_basis) != 0 and in_kernel(check_rows, added):
            reps.append(added)
    return reps, stab_in_kernel, stab_basis


def search_one(name, check_rows, stabilizer_rows, n_cols, rng):
    reps, stabilizers, stab_basis = logical_representatives(check_rows, stabilizer_rows, n_cols, rng)
    if not reps:
        return None

    best = None
    best_w = n_cols + 1

    def consider(v):
        nonlocal best, best_w
        v = greedy_reduce(v, stabilizers, check_rows, stab_basis, n_cols, rng)
        if verify(v, n_cols, check_rows, stab_basis):
            w = v.bit_count()
            if w < best_w:
                best, best_w = v, w

    for r in reps:
        consider(r)

    trials = max(3000, min(40000, 300 * (n_cols + len(reps) + len(stabilizers))))
    for _ in range(trials):
        v = 0
        while v == 0:
            for r in reps:
                if rng.getrandbits(1):
                    v ^= r
        if stabilizers:
            p = min(0.35, 8.0 / max(1, len(stabilizers)))
            for s in stabilizers:
                if rng.random() < p:
                    v ^= s
        consider(v)

    if best is None:
        return None
    return {"basis": name, "vector": int_to_bits(best, n_cols), "upper_bound": best_w}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("HX and HZ column counts differ")
        os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)
        found = []
        x = search_one("x", hz, hx, nx, rng)
        if x is not None:
            found.append(x)
        z = search_one("z", hx, hz, nx, rng)
        if z is not None:
            found.append(z)
        if not found:
            fail()
            return
        found.sort(key=lambda r: (r["upper_bound"], r["basis"]))
        chosen = found[0]
        out = {
            "status": "completed",
            "basis": chosen["basis"],
            "vector": chosen["vector"],
            "upper_bound": chosen["upper_bound"],
        }
        print(json.dumps(out, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
