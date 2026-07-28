#!/usr/bin/env python3
import argparse
import json
import random
import sys
from pathlib import Path


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
            x = 0
            for j, bit in enumerate(row):
                if int(bit) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            prev = -1
            for j in row:
                j = int(j)
                if j <= prev or j < 0 or j >= n:
                    raise ValueError("sparse row indices must be strictly increasing")
                x |= 1 << j
                prev = j
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def rref(rows, n):
    mat = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        bit = 1 << col
        pivot = None
        for i in range(rank, len(mat)):
            if mat[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        mat[rank], mat[pivot] = mat[pivot], mat[rank]
        for i in range(len(mat)):
            if i != rank and (mat[i] & bit):
                mat[i] ^= mat[rank]
        pivots.append(col)
        rank += 1
        if rank == len(mat):
            break
    return mat[:rank], pivots


def nullspace(rows, n):
    rr, pivots = rref(rows, n)
    pivot_set = set(pivots)
    basis = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        free_bit = 1 << free
        for row, pivot_col in zip(rr, pivots):
            if row & free_bit:
                v |= 1 << pivot_col
        basis.append(v)
    return basis


def add_to_span(basis, x):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def in_span(rows, x):
    basis = {}
    for row in rows:
        add_to_span(basis, row)
    return in_span_basis(basis, x)


def in_span_basis(basis, x):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        y ^= b
    return True


def logical_basis(check_rows, stabilizer_rows, n, rng):
    span = {}
    for row in stabilizer_rows:
        add_to_span(span, row)
    candidates = nullspace(check_rows, n)
    rng.shuffle(candidates)
    out = []
    for v in candidates:
        if v and add_to_span(span, v):
            out.append(v)
    return out


def syndrome_zero(rows, v):
    return all(((row & v).bit_count() & 1) == 0 for row in rows)


def verified(v, check_rows, stabilizer_basis):
    return v != 0 and syndrome_zero(check_rows, v) and not in_span_basis(stabilizer_basis, v)


def random_combo(vecs, rng, force_one=True):
    x = 0
    used = False
    for v in vecs:
        if rng.getrandbits(1):
            x ^= v
            used = True
    if force_one and not used and vecs:
        x = rng.choice(vecs)
    return x


def reduce_by_stabilizers(v, stabilizers, rng, passes):
    if not stabilizers:
        return v
    cur = v
    cur_w = cur.bit_count()
    rows = stabilizers[:]
    for t in range(passes):
        rng.shuffle(rows)
        improved = False
        for s in rows:
            w = (cur ^ s).bit_count()
            if w < cur_w or (w == cur_w and t > 0 and rng.random() < 0.015):
                cur ^= s
                improved = improved or w < cur_w
                cur_w = w
        if not improved and t >= 1:
            break
    return cur


def search_basis(name, check_rows, stabilizer_rows, n, seed):
    rng = random.Random(f"{seed}:{name}")
    stab = [r for r in stabilizer_rows if r]
    stab_span = {}
    for row in stab:
        add_to_span(stab_span, row)
    log_basis = logical_basis(check_rows, stab, n, rng)
    if not log_basis:
        return None

    weighted_stab = sorted(stab, key=lambda x: x.bit_count())
    if len(weighted_stab) > 1600:
        weighted_stab = weighted_stab[:1200] + rng.sample(weighted_stab[1200:], 400)

    best = None
    starts = log_basis[:]
    rng.shuffle(starts)

    iterations = max(350, min(4500, 70 * (len(log_basis).bit_length() + 1) + 3 * len(weighted_stab)))
    for i in range(iterations):
        if i < len(starts):
            v = starts[i]
        else:
            logical_terms = rng.randint(1, min(len(log_basis), 8))
            v = 0
            for item in rng.sample(log_basis, logical_terms):
                v ^= item
            if not v:
                v = random_combo(log_basis, rng)
            if weighted_stab:
                for s in rng.sample(weighted_stab, rng.randint(0, min(10, len(weighted_stab)))):
                    if rng.random() < 0.6:
                        v ^= s

        v = reduce_by_stabilizers(v, weighted_stab, rng, passes=3 + (i % 3))
        if verified(v, check_rows, stab_span):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    return best


def bits_to_list(v, n):
    return [1 if (v >> i) & 1 else 0 for i in range(n)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(Path(args.hx))
        hz, nz = load_matrix(Path(args.hz))
        if nx != nz:
            raise ValueError("hx and hz have different column counts")
        n = nx

        found = []
        x = search_basis("x", hz, hx, n, args.seed)
        if x is not None:
            found.append(("x", x))
        z = search_basis("z", hx, hz, n, args.seed)
        if z is not None:
            found.append(("z", z))

        if found:
            basis, vec = min(found, key=lambda item: item[1].bit_count())
            result = {
                "status": "completed",
                "basis": basis,
                "vector": bits_to_list(vec, n),
                "upper_bound": int(vec.bit_count()),
            }
        else:
            result = {"status": "failed", "basis": "", "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "failed", "basis": "", "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
