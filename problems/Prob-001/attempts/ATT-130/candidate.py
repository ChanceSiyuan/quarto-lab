#!/usr/bin/env python3
import argparse
import json
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    rows = []
    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        for row in obj["data"]:
            bits = 0
            for i, value in enumerate(row):
                if int(value) & 1:
                    bits |= 1 << i
            rows.append(bits)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        for row in obj["rows"]:
            bits = 0
            last = -1
            for i in row:
                i = int(i)
                if i <= last or i < 0 or i >= n:
                    raise ValueError("invalid sparse row")
                bits |= 1 << i
                last = i
            rows.append(bits)
        return rows, n

    raise ValueError("unrecognized matrix JSON format")


def insert_reduced(basis, row):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            for q, y in list(basis.items()):
                if q != p and ((y >> p) & 1):
                    basis[q] = y ^ x
            return True
        x ^= b
    return False


def row_basis(rows):
    basis = {}
    for row in rows:
        if row:
            insert_reduced(basis, row)
    return basis


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return y
        y ^= b
    return 0


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    rb = row_basis(rows)
    pivots = set(rb)
    free_cols = [i for i in range(n) if i not in pivots]
    out = []
    for f in free_cols:
        x = 1 << f
        for p in sorted(pivots):
            row = rb[p]
            if ((row & ~(1 << p) & x).bit_count() & 1):
                x |= 1 << p
        out.append(x)
    return out


def quotient_generators(kernel_rows, stabilizer_basis):
    q_basis = {}
    q_gen = {}
    gens = []
    for row in kernel_rows:
        v = row
        r = reduce_by_basis(v, stabilizer_basis)
        while r:
            p = r.bit_length() - 1
            b = q_basis.get(p)
            if b is None:
                q_basis[p] = r
                q_gen[p] = v
                gens.append(v)
                for q, y in list(q_basis.items()):
                    if q != p and ((y >> p) & 1):
                        q_basis[q] = y ^ r
                        q_gen[q] ^= v
                break
            r ^= b
            v ^= q_gen[p]
    return gens


def syndrome_zero(v, checks):
    for row in checks:
        if ((row & v).bit_count() & 1):
            return False
    return True


def certify(v, kernel_checks, stabilizer_basis):
    return v != 0 and syndrome_zero(v, kernel_checks) and not in_rowspace(v, stabilizer_basis)


def int_to_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


def greedy_reduce(v, stabilizers, kernel_checks, stabilizer_basis, rng, deadline):
    if not stabilizers:
        return v
    cur = v
    cur_w = cur.bit_count()
    order = list(stabilizers)
    improved = True
    passes = 0
    while improved and passes < 10 and time.monotonic() < deadline:
        improved = False
        passes += 1
        rng.shuffle(order)
        for s in order:
            cand = cur ^ s
            w = cand.bit_count()
            if w < cur_w and certify(cand, kernel_checks, stabilizer_basis):
                cur = cand
                cur_w = w
                improved = True
    return cur


def random_stabilizer_mix(v, stabilizers, rng):
    cur = v
    if not stabilizers:
        return cur
    count = 1 + rng.randrange(min(len(stabilizers), 24))
    for s in rng.sample(stabilizers, count):
        if rng.getrandbits(1):
            cur ^= s
    return cur


def search_side(label, kernel_checks, stabilizer_rows, n, rng, deadline):
    stab_basis = row_basis(stabilizer_rows)
    kernel = nullspace_basis(kernel_checks, n)
    logical_gens = quotient_generators(kernel, stab_basis)
    if not logical_gens:
        return None

    stabilizers = [s for s in stabilizer_rows if s]
    candidates = list(logical_gens)
    best = None
    best_w = n + 1

    def try_candidate(v):
        nonlocal best, best_w
        if not certify(v, kernel_checks, stab_basis):
            return
        v = greedy_reduce(v, stabilizers, kernel_checks, stab_basis, rng, deadline)
        w = v.bit_count()
        if w < best_w:
            best = v
            best_w = w

    for v in candidates:
        if time.monotonic() >= deadline:
            break
        try_candidate(v)

    k = len(logical_gens)
    base_iters = 1500 + 80 * min(n, 1000) + 250 * min(k, 80)
    max_iters = max(2500, min(base_iters, 120000))
    temp = max(1, k // 3)
    for i in range(max_iters):
        if time.monotonic() >= deadline:
            break
        if best_w <= 1:
            break
        v = 0
        if i < k:
            v = logical_gens[i]
        else:
            picks = 1 + rng.randrange(max(1, min(k, temp + 1)))
            for g in rng.sample(logical_gens, picks):
                v ^= g
            if rng.random() < 0.70:
                v = random_stabilizer_mix(v, stabilizers, rng)
        try_candidate(v)
        if i and i % 2000 == 0 and temp < k:
            temp += 1

    if best is None:
        return None
    return {"basis": label, "vector": int_to_bits(best, n), "upper_bound": best_w}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz have different column counts")
        n = nx
        deadline = time.monotonic() + 18.0
        sides = [
            search_side("x", hz, hx, n, rng, deadline),
            search_side("z", hx, hz, n, rng, deadline),
        ]
        hits = [s for s in sides if s is not None]
        if not hits:
            result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
        else:
            hit = min(hits, key=lambda s: (s["upper_bound"], 0 if s["basis"] == "x" else 1))
            result = {
                "status": "completed",
                "basis": hit["basis"],
                "vector": hit["vector"],
                "upper_bound": hit["upper_bound"],
            }
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
