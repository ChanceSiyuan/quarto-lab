#!/usr/bin/env python3
import argparse
import json
import random
import sys


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        return [row_to_bits(r) for r in data], n
    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "rows" in obj and ("num_cols" in obj or "n_cols" in obj):
        n = int(obj.get("num_cols", obj.get("n_cols")))
        rows = []
        for r in obj["rows"]:
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    x ^= 1 << c
            rows.append(x)
        return rows, n

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        if data and all(isinstance(v, int) for v in data):
            if n <= 0:
                raise ValueError("flat dense data requires n_cols")
            return [row_to_bits(data[i:i + n]) for i in range(0, len(data), n)], n
        if n <= 0:
            n = max((len(r) for r in data), default=0)
        return [row_to_bits(r) for r in data], n

    if "matrix" in obj:
        data = obj["matrix"]
        n = int(obj.get("n_cols", obj.get("num_cols", 0))) or max((len(r) for r in data), default=0)
        return [row_to_bits(r) for r in data], n

    raise ValueError("unrecognized matrix JSON format")


def row_to_bits(row):
    x = 0
    for i, v in enumerate(row):
        if int(v) & 1:
            x |= 1 << i
    return x


def mask_n(n):
    return (1 << n) - 1 if n > 0 else 0


def weight(x):
    return int(x.bit_count())


def row_basis(rows):
    basis = {}
    for r in rows:
        r = int(r)
        while r:
            p = r.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = r
                break
            r ^= b
    return basis


def reduce_by_basis(x, basis):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            break
        x ^= b
    return x


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def rref_rows(rows, n):
    rows = [r & mask_n(n) for r in rows if r & mask_n(n)]
    out = []
    pivots = []
    rank = 0
    for col in range(n):
        bit = 1 << col
        sel = None
        for i in range(rank, len(rows)):
            if rows[i] & bit:
                sel = i
                break
        if sel is None:
            continue
        rows[rank], rows[sel] = rows[sel], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & bit):
                rows[i] ^= rows[rank]
        out.append(rows[rank])
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return out, pivots


def kernel_basis(rows, n):
    rref, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    basis = []
    for f in free_cols:
        v = 1 << f
        fb = 1 << f
        for row, p in zip(rref, pivots):
            if row & fb:
                v |= 1 << p
        basis.append(v)
    return basis


def syndrome(v, checks):
    s = 0
    for i, r in enumerate(checks):
        if (v & r).bit_count() & 1:
            s |= 1 << i
    return s


def column_syndromes(checks, n):
    cols = [0] * n
    for i, r in enumerate(checks):
        x = r
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c < n:
                cols[c] |= 1 << i
            x ^= lsb
    return cols


def syndrome_solver(checks, n):
    basis = {}
    for j, col in enumerate(column_syndromes(checks, n)):
        s = col
        combo = 1 << j
        while s:
            p = s.bit_length() - 1
            item = basis.get(p)
            if item is None:
                basis[p] = (s, combo)
                break
            s ^= item[0]
            combo ^= item[1]

    def solve(target):
        s = target
        combo = 0
        while s:
            p = s.bit_length() - 1
            item = basis.get(p)
            if item is None:
                return None
            s ^= item[0]
            combo ^= item[1]
        return combo & mask_n(n)

    return solve


def random_bits(rng, n, count):
    if count <= 0 or n <= 0:
        return 0
    count = min(count, n)
    v = 0
    for c in rng.sample(range(n), count):
        v |= 1 << c
    return v


def random_kernel_combo(rng, k_basis, max_terms=None):
    if not k_basis:
        return 0
    if max_terms is None:
        max_terms = max(1, min(len(k_basis), 1 + int(len(k_basis) ** 0.5)))
    terms = rng.randint(1, max_terms)
    v = 0
    for i in rng.sample(range(len(k_basis)), min(terms, len(k_basis))):
        v ^= k_basis[i]
    return v


def descend_coset(v, stab_rows, stab_basis_rows, rng, rounds=4):
    best = v
    improved = True
    for _ in range(rounds):
        if not improved:
            break
        improved = False
        rows = list(stab_rows)
        rng.shuffle(rows)
        rows += stab_basis_rows
        for r in rows:
            if r and weight(best ^ r) < weight(best):
                best ^= r
                improved = True
    for _ in range(min(64, 4 * len(stab_basis_rows) + 8)):
        t = best
        for r in rng.sample(stab_basis_rows, rng.randint(0, min(3, len(stab_basis_rows)))) if stab_basis_rows else []:
            t ^= r
        if weight(t) < weight(best):
            best = t
    return best


def logical_search(checks, stabilizers, n, rng, effort):
    stab_basis = row_basis(stabilizers)
    stab_basis_rows = list(stab_basis.values())
    k_basis = kernel_basis(checks, n)
    solve = syndrome_solver(checks, n)
    best = None

    def consider(v):
        nonlocal best
        v &= mask_n(n)
        if not v or syndrome(v, checks) != 0 or in_rowspace(v, stab_basis):
            return
        v = descend_coset(v, stabilizers, stab_basis_rows, rng)
        if syndrome(v, checks) == 0 and not in_rowspace(v, stab_basis):
            if best is None or weight(v) < weight(best):
                best = v

    # Reliable quotient fallback seeds.
    for b in sorted(k_basis, key=weight):
        consider(b)
    for _ in range(min(96, 8 + 3 * len(k_basis))):
        consider(random_kernel_combo(rng, k_basis))

    if n == 0:
        return best

    low_counts = list(range(1, min(n, 10) + 1))
    if n > 10:
        low_counts += [max(1, n // d) for d in (16, 12, 9, 7, 5)]
    low_counts = sorted(set(c for c in low_counts if 1 <= c <= n))

    for it in range(effort):
        c1 = low_counts[it % len(low_counts)]
        if rng.random() < 0.20:
            c1 = rng.randint(1, max(1, min(n, int(n ** 0.5) + 8)))
        err = random_bits(rng, n, c1)

        # Randomized decoder residual: solve a perturbed syndrome equation, so
        # err ^ corr is guaranteed to be in the check kernel when solving works.
        q_count = rng.choice((0, 1, 2, 3, max(1, n // 32), max(1, n // 16)))
        q = random_bits(rng, n, min(n, q_count))
        target = syndrome(err, checks) ^ syndrome(q, checks)
        corr0 = solve(target)
        if corr0 is None:
            continue
        residual = err ^ q ^ corr0
        consider(residual)

        if best is not None and it % 7 == 0:
            mixed = residual ^ best ^ random_kernel_combo(rng, k_basis, 3)
            consider(mixed)

    return best


def bits_to_list(v, n):
    return [1 if (v >> i) & 1 else 0 for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & mask_n(n) for r in hx]
    hz = [r & mask_n(n) for r in hz]
    rng = random.Random(args.seed)

    effort = max(200, min(2500, 900 + 12 * n))
    bx = logical_search(hz, hx, n, random.Random(rng.randrange(1 << 62)), effort)
    bz = logical_search(hx, hz, n, random.Random(rng.randrange(1 << 62)), effort)

    choices = []
    if bx is not None:
        choices.append(("x", bx))
    if bz is not None:
        choices.append(("z", bz))
    if choices:
        basis, vec = min(choices, key=lambda item: (weight(item[1]), 0 if item[0] == "x" else 1))
        out = {
            "status": "completed",
            "basis": basis,
            "vector": bits_to_list(vec, n),
            "upper_bound": weight(vec),
        }
    else:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _ = exc
        print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
        sys.exit(0)
