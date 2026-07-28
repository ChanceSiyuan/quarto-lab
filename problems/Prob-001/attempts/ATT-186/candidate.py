#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def fail():
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))


def read_matrix(path):
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
                raise ValueError("dense row length does not match n_cols")
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    mask |= 1 << i
            rows.append(mask)
        return int(obj["n_rows"]), n, rows

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for inds in obj["rows"]:
            last = -1
            mask = 0
            for raw in inds:
                i = int(raw)
                if i <= last or i < 0 or i >= n:
                    raise ValueError("sparse rows must be strictly increasing valid indices")
                mask |= 1 << i
                last = i
            rows.append(mask)
        return len(rows), n, rows

    raise ValueError("unsupported matrix JSON format")


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
    # Reduce above pivots to keep a canonical membership basis.
    for p in sorted(basis):
        row = basis[p]
        for q in sorted(basis):
            if q != p and q < p and ((row >> q) & 1):
                row ^= basis[q]
        basis[p] = row
    return basis


def in_span(mask, basis):
    x = int(mask)
    while x:
        p = x.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return False
        x ^= row
    return True


def nullspace_basis(rows, n_cols):
    pivot_rows = rref_basis(rows)
    pivots = set(pivot_rows)
    out = []
    for free in range(n_cols):
        if free in pivots:
            continue
        v = 1 << free
        for p, row in pivot_rows.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(checks, v):
    for row in checks:
        if ((row & v).bit_count() & 1) != 0:
            return False
    return True


def to_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


def verify(v, checks, stab_basis):
    return v != 0 and syndrome_zero(checks, v) and not in_span(v, stab_basis)


def stabilizer_descent(v, stab_rows, rng, passes=10):
    if not stab_rows:
        return v
    best = v
    best_w = v.bit_count()
    rows = list(stab_rows)
    for _ in range(passes):
        rng.shuffle(rows)
        changed = False
        for row in rows:
            nv = best ^ row
            nw = nv.bit_count()
            if nw < best_w:
                best, best_w = nv, nw
                changed = True
        if not changed:
            break
    return best


def random_kernel_vector(kernel, rng):
    m = len(kernel)
    if m == 0:
        return 0
    # Mix small information-set samples with denser samples. The small samples
    # often expose sparse logicals; dense samples keep the search from getting
    # trapped in only the displayed nullspace basis.
    r = rng.random()
    if r < 0.72:
        k = 1
        while k < m and rng.random() < 0.38:
            k += 1
        idxs = rng.sample(range(m), k)
    elif r < 0.90:
        k = rng.randint(1, min(m, 12))
        idxs = rng.sample(range(m), k)
    else:
        idxs = [i for i in range(m) if rng.getrandbits(1)]
        if not idxs:
            idxs = [rng.randrange(m)]
    v = 0
    for i in idxs:
        v ^= kernel[i]
    return v


def search_sector(label, checks, stab_rows, n, rng, deadline):
    kernel = nullspace_basis(checks, n)
    stab_basis = rref_basis(stab_rows)
    if not kernel:
        return None

    best = None
    best_w = n + 1

    def consider(v):
        nonlocal best, best_w
        v = stabilizer_descent(v, stab_rows, rng)
        if verify(v, checks, stab_basis):
            w = v.bit_count()
            if w < best_w:
                best, best_w = v, w

    order = list(kernel)
    rng.shuffle(order)
    for v in order[: min(len(order), 256)]:
        consider(v)

    attempts = 0
    min_attempts = 800
    max_attempts = max(2500, 120 * len(kernel), 20 * n)
    while attempts < max_attempts and (attempts < min_attempts or time.monotonic() < deadline):
        attempts += 1
        consider(random_kernel_vector(kernel, rng))

    if best is None:
        return None
    return {"basis": label, "vector": to_bits(best, n), "upper_bound": best_w}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        _, nx, hx = read_matrix(args.hx)
        _, nz, hz = read_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)
        deadline = time.monotonic() + 25.0

        sectors = [("x", hz, hx), ("z", hx, hz)]
        rng.shuffle(sectors)
        results = []
        for label, checks, stabs in sectors:
            got = search_sector(label, checks, stabs, nx, rng, deadline)
            if got is not None:
                results.append(got)

        if not results:
            fail()
            return
        best = min(results, key=lambda item: item["upper_bound"])
        print(json.dumps({"status": "completed", **best}, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
