#!/usr/bin/env python3
import argparse
import json
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            x = 0
            for j, b in enumerate(r):
                if b & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or dense row list")

    if "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for j, b in enumerate(r):
                if j >= n:
                    break
                if b & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if "rows" in obj:
        sparse = obj.get("rows") or []
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n == 0:
            n = 1 + max((c for r in sparse for c in r), default=-1)
        rows = []
        for r in sparse:
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    x |= 1 << c
            rows.append(x)
        return rows, n

    raise ValueError("matrix JSON must use data/n_cols or rows/num_cols")


def weight(x):
    return x.bit_count()


def parity(x):
    return x.bit_count() & 1


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = reduce_by_basis(row, basis)
        if not x:
            continue
        p = x.bit_length() - 1
        basis[p] = x
        for q, y in list(basis.items()):
            if q != p and ((y >> p) & 1):
                basis[q] = y ^ x
    return basis


def reduce_by_basis(x, basis):
    for p in sorted(basis.keys(), reverse=True):
        if (x >> p) & 1:
            x ^= basis[p]
    return x


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def kernel_basis(check_rows, n):
    eq_basis = rref_basis(check_rows)
    pivots = set(eq_basis.keys())
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in eq_basis.items():
            if parity(row & v):
                v |= 1 << p
        out.append(v)
    return out


def add_independent(x, basis):
    y = reduce_by_basis(x, basis)
    if y == 0:
        return False
    p = y.bit_length() - 1
    basis[p] = y
    for q, z in list(basis.items()):
        if q != p and ((z >> p) & 1):
            basis[q] = z ^ y
    return True


def logical_representatives(check_rows, stab_rows, n):
    stab_basis = rref_basis(stab_rows)
    quotient_basis = {}
    reps = []
    for v in kernel_basis(check_rows, n):
        residue = reduce_by_basis(v, stab_basis)
        if residue and add_independent(residue, quotient_basis):
            reps.append(v)
    return reps, stab_basis


def verifies(v, check_rows, stab_basis):
    if v == 0:
        return False
    for row in check_rows:
        if parity(row & v):
            return False
    return not in_rowspace(v, stab_basis)


def greedy_descent(v, stab_rows):
    improved = True
    while improved:
        improved = False
        best = v
        best_w = weight(v)
        for r in stab_rows:
            u = v ^ r
            wu = weight(u)
            if wu < best_w:
                best = u
                best_w = wu
        if best != v:
            v = best
            improved = True
    return v


def luby(i):
    k = 1
    while (1 << k) - 1 < i:
        k += 1
    if i == (1 << k) - 1:
        return 1 << (k - 1)
    return luby(i - (1 << (k - 1)) + 1)


def random_combo(items, rng, force_nonempty=True):
    if not items:
        return 0
    x = 0
    used = False
    for item in items:
        if rng.getrandbits(1):
            x ^= item
            used = True
    if force_nonempty and not used:
        x = rng.choice(items)
    return x


def randomized_heavytail_search(reps, check_rows, stab_rows, stab_basis, n, rng, deadline):
    if not reps:
        return None

    clean_stabs = sorted({r for r in stab_rows if r}, key=weight)
    best = None
    best_w = n + 1

    # Reliable basis-derived fallback: each quotient basis representative is a
    # valid logical coset, then stabilizer descent only changes its representative.
    for rep in reps:
        cand = greedy_descent(rep, clean_stabs)
        if verifies(cand, check_rows, stab_basis) and weight(cand) < best_w:
            best = cand
            best_w = weight(cand)
            if best_w <= 1:
                return best

    if not clean_stabs:
        return best

    unit = max(8, min(96, len(clean_stabs) + max(1, n // 8)))
    restart = 1
    while time.monotonic() < deadline:
        budget = unit * luby(restart)
        restart += 1

        # Heavy-tail restarts alternate between a logical-basis draw and a
        # known good coset, then randomize inside the stabilizer coset.
        if best is not None and rng.random() < 0.45:
            v = best
        else:
            v = random_combo(reps, rng, True)

        flips = 1 + rng.randrange(max(1, min(len(clean_stabs), 2 * unit)))
        for _ in range(flips):
            v ^= rng.choice(clean_stabs)

        plateau = 0
        for _ in range(budget):
            if time.monotonic() >= deadline:
                break
            r = rng.choice(clean_stabs)
            u = v ^ r
            dw = weight(u) - weight(v)
            if dw < 0 or (dw == 0 and rng.random() < 0.08):
                v = u
                plateau = 0
            else:
                plateau += 1

            if plateau > len(clean_stabs):
                # A short randomized first-improvement sweep lets long Luby
                # runs escape unlucky single-row sampling without enumerating
                # candidate supports.
                sample = clean_stabs[:]
                rng.shuffle(sample)
                moved = False
                wv = weight(v)
                for s in sample[: min(len(sample), unit)]:
                    u = v ^ s
                    if weight(u) < wv:
                        v = u
                        moved = True
                        break
                if not moved:
                    v ^= rng.choice(clean_stabs)
                plateau = 0

            if weight(v) < best_w and verifies(v, check_rows, stab_basis):
                best = v
                best_w = weight(v)
                if best_w <= 1:
                    return best

        cand = greedy_descent(v, clean_stabs[: min(len(clean_stabs), 512)])
        if weight(cand) < best_w and verifies(cand, check_rows, stab_basis):
            best = cand
            best_w = weight(cand)

    return best


def bits_to_list(x, n):
    return [(x >> i) & 1 for i in range(n)]


def solve(hx_rows, hz_rows, n, seed):
    rng = random.Random(seed)
    work = n + len(hx_rows) + len(hz_rows)
    total_seconds = min(6.0, max(1.25, 0.0015 * work + 0.75))
    deadline = time.monotonic() + total_seconds
    searches = [
        ("x", hz_rows, hx_rows),
        ("z", hx_rows, hz_rows),
    ]
    rng.shuffle(searches)

    best_basis = None
    best_vec = None
    best_w = n + 1

    for name, check_rows, stab_rows in searches:
        reps, stab_basis = logical_representatives(check_rows, stab_rows, n)
        per_basis_deadline = min(deadline, time.monotonic() + total_seconds / 2.0)
        cand = randomized_heavytail_search(
            reps, check_rows, stab_rows, stab_basis, n, rng, per_basis_deadline
        )
        if cand is not None and verifies(cand, check_rows, stab_basis):
            wc = weight(cand)
            if wc < best_w:
                best_basis = name
                best_vec = cand
                best_w = wc
                if best_w <= 1:
                    break

    if best_vec is None:
        # Last-resort deterministic pass for valid positive-k inputs if the
        # time-sliced randomized phase ended before reaching one basis.
        for name, check_rows, stab_rows in [("x", hz_rows, hx_rows), ("z", hx_rows, hz_rows)]:
            reps, stab_basis = logical_representatives(check_rows, stab_rows, n)
            for rep in reps:
                cand = greedy_descent(rep, sorted({r for r in stab_rows if r}, key=weight))
                if verifies(cand, check_rows, stab_basis):
                    wc = weight(cand)
                    if wc < best_w:
                        best_basis = name
                        best_vec = cand
                        best_w = wc

    if best_vec is None:
        return {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    return {
        "status": "completed",
        "basis": best_basis,
        "vector": bits_to_list(best_vec, n),
        "upper_bound": best_w,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    hx_rows, nx = load_matrix(args.hx)
    hz_rows, nz = load_matrix(args.hz)
    n = max(nx, nz)
    mask = (1 << n) - 1 if n > 0 else 0
    hx_rows = [r & mask for r in hx_rows]
    hz_rows = [r & mask for r in hz_rows]

    result = solve(hx_rows, hz_rows, n, args.seed)
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
