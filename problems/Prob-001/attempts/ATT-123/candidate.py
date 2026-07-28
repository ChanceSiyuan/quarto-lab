#!/usr/bin/env python3
import argparse
import json
import random
import time


def fail(reason="no_witness"):
    return {"status": reason, "basis": None, "vector": [], "upper_bound": None}


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            for i, value in enumerate(row):
                if value & 1:
                    bits |= 1 << i
            rows.append(bits)
        return rows, n_cols

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("invalid sparse row")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


def rref(rows):
    rows = [r for r in rows if r]
    basis = {}
    for value in rows:
        x = value
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
    pivots = sorted(basis)
    return [(p, basis[p]) for p in pivots]


def reduce_by_rref(value, rr):
    x = value
    for p, row in reversed(rr):
        if (x >> p) & 1:
            x ^= row
    return x


def in_rowspace(value, rr):
    return reduce_by_rref(value, rr) == 0


def nullspace_basis(rows, n_cols):
    rr = rref(rows)
    pivots = {p for p, _ in rr}
    free_cols = [c for c in range(n_cols) if c not in pivots]
    basis = []
    for free in free_cols:
        v = 1 << free
        for p, row in rr:
            if (row >> free) & 1:
                v |= 1 << p
        basis.append(v)
    return basis


def syndrome_zero(rows, value):
    return all(((row & value).bit_count() & 1) == 0 for row in rows)


def vector_from_bits(value, n_cols):
    return [(value >> i) & 1 for i in range(n_cols)]


def low_weight_coset_representative(value, stabilizers, rng, passes):
    v = value
    rows = [r for r in stabilizers if r]
    rng.shuffle(rows)

    for _ in range(passes):
        changed = False
        rng.shuffle(rows)
        current = v.bit_count()
        for row in rows:
            candidate = v ^ row
            cw = candidate.bit_count()
            if cw < current or (cw == current and rng.random() < 0.015):
                v = candidate
                current = cw
                changed = True
        if not changed:
            break
    return v


def logical_basis(kernel_basis, stabilizers):
    span = rref(stabilizers)
    out = []
    current_rows = list(stabilizers)
    for v in kernel_basis:
        if not in_rowspace(v, span):
            out.append(v)
            current_rows.append(v)
            span = rref(current_rows)
    return out


def search_one(name, commute_rows, stabilizer_rows, n_cols, rng, time_limit):
    stab_rr = rref(stabilizer_rows)
    kernel = nullspace_basis(commute_rows, n_cols)
    logs = logical_basis(kernel, stabilizer_rows)
    if not logs:
        return None

    deadline = time.monotonic() + time_limit
    best = None

    seeds = list(logs)
    rng.shuffle(seeds)
    attempts = 0

    while time.monotonic() < deadline and attempts < 14000:
        attempts += 1
        if attempts <= len(seeds):
            v = seeds[attempts - 1]
        else:
            v = 0
            # Bias toward small random combinations, but occasionally mix broadly.
            if rng.random() < 0.72:
                take = 1 + int(rng.expovariate(0.65))
                take = min(take, len(logs))
                for item in rng.sample(logs, take):
                    v ^= item
            else:
                for item in logs:
                    if rng.getrandbits(1):
                        v ^= item
                if v == 0:
                    v = rng.choice(logs)

        v = low_weight_coset_representative(v, stabilizer_rows, rng, 4)
        if v and syndrome_zero(commute_rows, v) and not in_rowspace(v, stab_rr):
            weight = v.bit_count()
            if best is None or weight < best[0]:
                best = (weight, v)
                if weight <= 1:
                    break

    if best is None:
        return None
    return {"status": "completed", "basis": name, "vector": vector_from_bits(best[1], n_cols), "upper_bound": best[0]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz column counts differ")

        rng = random.Random(args.seed)
        # X logicals are in ker(Hz) modulo row(Hx); Z logicals are in ker(Hx) modulo row(Hz).
        per_basis_limit = 4.5
        candidates = [
            search_one("x", hz, hx, nx, rng, per_basis_limit),
            search_one("z", hx, hz, nx, rng, per_basis_limit),
        ]
        candidates = [c for c in candidates if c is not None]
        if not candidates:
            result = fail()
        else:
            result = min(candidates, key=lambda c: (c["upper_bound"], c["basis"]))

        print(json.dumps(result, separators=(",", ":")))
    except Exception:
        print(json.dumps(fail("error"), separators=(",", ":")))


if __name__ == "__main__":
    main()
