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
                    raise ValueError("sparse row indices must be strictly increasing in range")
                x |= 1 << i
                last = i
            rows.append(x)
        return rows, n
    raise ValueError("unknown matrix JSON format")


def rref(rows):
    basis = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            y = basis.get(p)
            if y is None:
                basis[p] = x
                break
            x ^= y
    for p in sorted(basis):
        row = basis[p]
        for q in sorted(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    return basis


def reduce_by_basis(x, basis):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        y = basis.get(p)
        if y is None:
            return x
        x ^= y
    return 0


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def kernel_basis(check_rows, n):
    piv = rref(check_rows)
    pivot_cols = set(piv)
    out = []
    for f in range(n):
        if f in pivot_cols:
            continue
        v = 1 << f
        for p, row in piv.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def quotient_basis(kernel_rows, stabilizer_rows):
    span = rref(stabilizer_rows)
    logicals = []
    for v in sorted(kernel_rows, key=int.bit_count):
        if not in_span(v, span):
            logicals.append(v)
            span = rref(list(span.values()) + [v])
    return logicals


def syndrome_zero(v, checks):
    return all(((v & row).bit_count() & 1) == 0 for row in checks)


def verified(v, checks, stabilizer_basis):
    return v != 0 and syndrome_zero(v, checks) and not in_span(v, stabilizer_basis)


def greedy_reduce(v, stabilizers, rng, rounds):
    if not stabilizers:
        return v
    cur = v
    cur_w = cur.bit_count()
    order = list(stabilizers)
    for _ in range(rounds):
        rng.shuffle(order)
        changed = False
        for s in order:
            y = cur ^ s
            wy = y.bit_count()
            if wy < cur_w or (wy == cur_w and rng.randrange(32) == 0):
                cur, cur_w = y, wy
                changed = True
        if not changed:
            break
    return cur


def random_stabilizer_mix(stabilizers, rng, max_terms):
    if not stabilizers or max_terms <= 0:
        return 0
    k = rng.randint(1, max_terms)
    x = 0
    for _ in range(k):
        x ^= stabilizers[rng.randrange(len(stabilizers))]
    return x


def hunt_basis(name, checks, stabilizers, n, rng, deadline):
    stab_basis = rref(stabilizers)
    kbas = kernel_basis(checks, n)
    lbas = quotient_basis(kbas, stabilizers)
    if not lbas:
        return None

    stab_sorted = sorted((s for s in stabilizers if s), key=int.bit_count)
    best = None
    seeds = list(lbas)
    seeds.extend(v ^ random_stabilizer_mix(stab_sorted, rng, min(12, len(stab_sorted))) for v in lbas)

    for v in seeds:
        cand = greedy_reduce(v, stab_sorted, rng, 6)
        if verified(cand, checks, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    lcount = len(lbas)
    tries = 0
    max_tries = max(800, 220 * (lcount + 1))
    while time.monotonic() < deadline and tries < max_tries:
        tries += 1
        if tries % 7 == 0:
            v = min(lbas, key=int.bit_count)
        else:
            v = 0
            # Bias toward small random logical combinations, but occasionally
            # sample wider sums to move between quotient-space regions.
            if rng.random() < 0.82:
                terms = 1 + int(rng.expovariate(0.9))
                terms = min(terms, max(1, min(lcount, 8)))
                for _ in range(terms):
                    v ^= lbas[rng.randrange(lcount)]
            else:
                for b in lbas:
                    if rng.getrandbits(1):
                        v ^= b
                if v == 0:
                    v = lbas[rng.randrange(lcount)]

        if stab_sorted and rng.random() < 0.72:
            v ^= random_stabilizer_mix(stab_sorted, rng, min(16, len(stab_sorted)))
        cand = greedy_reduce(v, stab_sorted, rng, 4 + (tries & 3))
        if verified(cand, checks, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    if best is None:
        return None
    return name, best


def as_binary_list(v, n):
    return [int((v >> i) & 1) for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("Hx and Hz column counts differ")
    os.makedirs(args.output_dir, exist_ok=True)

    rng = random.Random(args.seed)
    n = nx
    deadline = time.monotonic() + 1.85
    basis_order = ["x", "z"]
    rng.shuffle(basis_order)
    found = []

    for basis in basis_order:
        if basis == "x":
            got = hunt_basis("x", hz, hx, n, rng, deadline)
        else:
            got = hunt_basis("z", hx, hz, n, rng, deadline)
        if got is not None:
            found.append(got)

    if found:
        basis, vec = min(found, key=lambda item: item[1].bit_count())
        out = {
            "status": "completed",
            "basis": basis,
            "vector": as_binary_list(vec, n),
            "upper_bound": int(vec.bit_count()),
        }
    else:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
