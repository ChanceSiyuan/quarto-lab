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
            v = 0
            if len(row) != n:
                raise ValueError(f"{path}: dense row has length {len(row)}, expected {n}")
            for i, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError(f"{path}: dense matrix contains a non-binary entry")
                if bit:
                    v |= 1 << i
            rows.append(v)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            prev = -1
            v = 0
            for col in row:
                col = int(col)
                if col <= prev or col < 0 or col >= n:
                    raise ValueError(f"{path}: sparse rows must be strictly increasing indices")
                prev = col
                v |= 1 << col
            rows.append(v)
        return rows, n

    raise ValueError(f"{path}: unknown matrix JSON format")


def rref_rows(rows):
    basis = {}
    for raw in rows:
        v = int(raw)
        while v:
            p = v.bit_length() - 1
            if p not in basis:
                basis[p] = v
                break
            v ^= basis[p]
    # Canonicalize enough to make reductions stable.
    for p in sorted(basis):
        row = basis[p]
        for q in sorted(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    return basis


def reduce_by_basis(v, basis):
    v = int(v)
    while v:
        p = v.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return v
        v ^= row
    return 0


def in_rowspace(v, basis):
    return reduce_by_basis(v, basis) == 0


def kernel_basis(check_rows, n):
    rref = rref_rows(check_rows)
    pivots = set(rref)
    out = []
    for free in range(n):
        if free in pivots:
            continue
        v = 1 << free
        for p, row in rref.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, rows):
    for row in rows:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def int_to_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


def random_kernel_vector(rng, basis, max_terms):
    if not basis:
        return 0
    count = rng.randint(1, min(max_terms, len(basis)))
    v = 0
    for b in rng.sample(basis, count):
        v ^= b
    return v


def greedy_reduce(v, stab_rows, rng, passes):
    if not stab_rows:
        return v
    best = v
    best_w = v.bit_count()
    order = list(stab_rows)
    for _ in range(passes):
        changed = False
        rng.shuffle(order)
        for row in order:
            u = best ^ row
            w = u.bit_count()
            if w < best_w or (w == best_w and rng.random() < 0.015):
                best, best_w = u, w
                changed = True
        if not changed:
            break
    return best


def anneal_reduce(v, stab_rows, rng, steps):
    if not stab_rows:
        return v
    cur = v
    cur_w = v.bit_count()
    best = cur
    best_w = cur_w
    for t in range(steps):
        row = stab_rows[rng.randrange(len(stab_rows))]
        nxt = cur ^ row
        nxt_w = nxt.bit_count()
        if nxt_w <= cur_w:
            accept = True
        else:
            temp = max(0.05, 1.5 * (1.0 - (t / max(1, steps))))
            accept = rng.random() < pow(2.718281828, -(nxt_w - cur_w) / temp)
        if accept:
            cur, cur_w = nxt, nxt_w
            if 0 < cur_w < best_w:
                best, best_w = cur, cur_w
    return best


def verified(v, n, check_rows, stab_basis):
    mask = (1 << n) - 1
    return v != 0 and (v & ~mask) == 0 and syndrome_zero(v, check_rows) and not in_rowspace(v, stab_basis)


def search_basis(name, check_rows, stab_rows, n, seed):
    rng = random.Random((seed << 8) ^ (17 if name == "x" else 41))
    kbasis = kernel_basis(check_rows, n)
    stab_basis = rref_rows(stab_rows)
    local_stabs = [row for row in stab_rows if syndrome_zero(row, check_rows)]
    candidates = []

    for b in kbasis:
        if not in_rowspace(b, stab_basis):
            candidates.append(b)

    # Random information-set style mixtures of nullspace generators. This is
    # heuristic witness search, followed by stabilizer-coset weight reduction.
    trials = max(300, min(9000, 180 * max(1, n)))
    max_terms = max(1, min(len(kbasis), int(max(2, n ** 0.5)) + 3))
    deadline = time.monotonic() + float(os.environ.get("CANDIDATE_TIME_LIMIT", "25"))
    best = None
    best_w = n + 1

    def consider(v, extra=False):
        nonlocal best, best_w
        if v == 0 or in_rowspace(v, stab_basis):
            return
        local = greedy_reduce(v, local_stabs, rng, 4 if not extra else 8)
        if extra:
            local = anneal_reduce(local, local_stabs, rng, max(200, 12 * len(local_stabs)))
            local = greedy_reduce(local, local_stabs, rng, 8)
        if verified(local, n, check_rows, stab_basis):
            w = local.bit_count()
            if w < best_w:
                best, best_w = local, w

    for c in candidates:
        consider(c, extra=True)

    for t in range(trials):
        if time.monotonic() > deadline:
            break
        v = random_kernel_vector(rng, kbasis, max_terms)
        if rng.random() < 0.35 and candidates:
            v ^= rng.choice(candidates)
        consider(v, extra=(t % 17 == 0))

    return best, best_w


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
            raise ValueError("Hx and Hz have different numbers of columns")
        n = nx

        bx, wx = search_basis("x", hz, hx, n, args.seed)
        bz, wz = search_basis("z", hx, hz, n, args.seed)

        if bx is not None and (bz is None or wx <= wz):
            result = {"status": "completed", "basis": "x", "vector": int_to_bits(bx, n), "upper_bound": wx}
        elif bz is not None:
            result = {"status": "completed", "basis": "z", "vector": int_to_bits(bz, n), "upper_bound": wz}
        else:
            result = {"status": "not_found", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "error", "basis": "x", "vector": [], "upper_bound": None}

    os.makedirs(args.output_dir, exist_ok=True)
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
