#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def row_weight(x):
    return int(x.bit_count())


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            v = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    v |= 1 << i
            rows.append(v)
        return rows, n

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            v = 0
            for i, b in enumerate(r[:n]):
                if int(b) & 1:
                    v |= 1 << i
            rows.append(v)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows") or []:
            v = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    v |= 1 << c
            rows.append(v)
        return rows, n

    raise ValueError("unknown matrix JSON format")


def rref(rows, n):
    a = [r & ((1 << n) - 1) for r in rows if r]
    rank = 0
    pivots = []
    m = len(a)
    for col in range(n):
        pivot = -1
        bit = 1 << col
        for i in range(rank, m):
            if a[i] & bit:
                pivot = i
                break
        if pivot < 0:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        pr = a[rank]
        for i in range(m):
            if i != rank and (a[i] & bit):
                a[i] ^= pr
        pivots.append(col)
        rank += 1
        if rank == m:
            break
    return a[:rank], pivots


def elimination_basis(rows):
    basis = {}
    for r in rows:
        x = r
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def in_rowspace(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        y ^= b
    return True


def nullspace_basis(rows, n):
    rr, pivots = rref(rows, n)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    out = []
    for f in free_cols:
        v = 1 << f
        for row, p in zip(rr, pivots):
            if row & (1 << f):
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(rows, v):
    for r in rows:
        if ((r & v).bit_count() & 1) != 0:
            return False
    return True


def verify(v, check_rows, stab_basis):
    return v != 0 and syndrome_zero(check_rows, v) and not in_rowspace(v, stab_basis)


def bits_to_list(v, n):
    return [1 if (v >> i) & 1 else 0 for i in range(n)]


def reduce_by_stabilizers(v, stab_rows, rng, rounds=4):
    if not stab_rows:
        return v
    rows = [r for r in stab_rows if r]
    rows.sort(key=row_weight)
    cur = v
    cur_w = row_weight(cur)
    for _ in range(rounds):
        changed = False
        if len(rows) > 1:
            head = rows[: min(len(rows), 64)]
            tail = rows[min(len(rows), 64) :]
            rng.shuffle(head)
            order = head + tail
        else:
            order = rows
        for r in order:
            nv = cur ^ r
            nw = row_weight(nv)
            if nw < cur_w:
                cur, cur_w = nv, nw
                changed = True
        if not changed:
            break
    return cur


def solve_gf2(equations, rhs, d, rng):
    rows = []
    for m, b in zip(equations, rhs):
        if m:
            rows.append([m, b & 1])
        elif b & 1:
            return None

    rank = 0
    pivots = []
    mlen = len(rows)
    for col in range(d):
        bit = 1 << col
        pivot = -1
        for i in range(rank, mlen):
            if rows[i][0] & bit:
                pivot = i
                break
        if pivot < 0:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        pm, pb = rows[rank]
        for i in range(mlen):
            if i != rank and (rows[i][0] & bit):
                rows[i][0] ^= pm
                rows[i][1] ^= pb
        pivots.append(col)
        rank += 1
        if rank == mlen:
            break

    pivot_set = set(pivots)
    sol = 0
    # Random free coefficients keep the method heuristic while the projected
    # equations impose the sampled support sketch.
    for c in range(d):
        if c not in pivot_set and rng.getrandbits(1):
            sol |= 1 << c
    for mask, b in rows[:rank]:
        p = (mask & -mask).bit_length() - 1
        if ((mask & sol).bit_count() & 1) ^ b:
            sol ^= 1 << p
    return sol


def lift_combo(coeffs, kernel_basis):
    v = 0
    c = coeffs
    while c:
        lsb = c & -c
        i = lsb.bit_length() - 1
        v ^= kernel_basis[i]
        c ^= lsb
    return v


def coordinate_masks(kernel_basis, n):
    masks = [0] * n
    for i, v in enumerate(kernel_basis):
        x = v
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            masks[c] |= 1 << i
            x ^= lsb
    return masks


def consider(best, basis_name, v, n, check_rows, stab_basis):
    if verify(v, check_rows, stab_basis):
        w = row_weight(v)
        if best is None or w < best[0]:
            return (w, basis_name, v)
    return best


def search_basis(basis_name, check_rows, stab_rows, n, rng, deadline):
    stab_basis = elimination_basis(stab_rows)
    kbas = nullspace_basis(check_rows, n)
    if not kbas:
        return None

    best = None

    # Basis-derived fallback: for positive-k inputs, some kernel basis vector
    # must lie outside the stabilizer row-space if this logical sector exists.
    for v in sorted(kbas, key=row_weight)[: min(len(kbas), 160)]:
        rv = reduce_by_stabilizers(v, stab_rows, rng, rounds=5)
        best = consider(best, basis_name, rv, n, check_rows, stab_basis)
        best = consider(best, basis_name, v, n, check_rows, stab_basis)

    d = len(kbas)
    cmasks = coordinate_masks(kbas, n)
    weights = [row_weight(v) for v in kbas]

    # Random projection and kernel lifting.  A sampled coordinate sketch says
    # which coordinates should be zero and selects one anchor coordinate that
    # must be one; solving the projected system gives kernel coefficients that
    # lift to a full commuting operator.
    tries = 0
    max_tries = 1200 if n <= 600 else 650
    if d > 900:
        max_tries = min(max_tries, 420)

    nonzero_coords = [i for i, m in enumerate(cmasks) if m]
    if not nonzero_coords:
        return best
    coord_degree = [(cmasks[i].bit_count(), i) for i in nonzero_coords]
    coord_degree.sort(reverse=True)
    high_degree = [i for _, i in coord_degree[: max(8, min(len(coord_degree), n // 3 + 1))]]

    while tries < max_tries and time.monotonic() < deadline:
        tries += 1
        anchor = rng.choice(nonzero_coords if tries % 3 else high_degree)
        budget = min(len(nonzero_coords), max(4, min(d + 1, 24 + int(3 * (tries ** 0.5)))))
        if best is not None:
            budget = min(len(nonzero_coords), max(4, min(budget + best[0] // 2, d + 1)))
        protected = set(rng.sample(nonzero_coords, min(budget, len(nonzero_coords))))
        protected.add(anchor)

        equations = []
        rhs = []
        for c in protected:
            equations.append(cmasks[c])
            rhs.append(1 if c == anchor else 0)

        coeffs = solve_gf2(equations, rhs, d, rng)
        if coeffs is None:
            continue
        v = lift_combo(coeffs, kbas)
        if v == 0:
            continue

        # Light randomized kernel-basis perturbations explore nearby projected
        # lifts before stabilizer descent.
        candidates = [v]
        for _ in range(2):
            u = v
            flips = 1 + rng.randrange(1 + min(7, max(1, d // 16)))
            for _ in range(flips):
                if rng.random() < 0.7:
                    idx = min(range(d), key=lambda j: weights[j] + rng.randrange(17))
                else:
                    idx = rng.randrange(d)
                u ^= kbas[idx]
            candidates.append(u)

        for u in candidates:
            u = reduce_by_stabilizers(u, stab_rows, rng, rounds=5)
            best = consider(best, basis_name, u, n, check_rows, stab_basis)

    # Full fallback over every kernel basis vector if the early bounded pass did
    # not find the sector witness.
    if best is None:
        for v in kbas:
            rv = reduce_by_stabilizers(v, stab_rows, rng, rounds=3)
            best = consider(best, basis_name, rv, n, check_rows, stab_basis)
            best = consider(best, basis_name, v, n, check_rows, stab_basis)
            if best is not None:
                break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1) for r in hx]
    hz = [r & ((1 << n) - 1) for r in hz]

    deadline = time.monotonic() + 25.0
    best = None
    sectors = [("x", hz, hx), ("z", hx, hz)]
    if rng.getrandbits(1):
        sectors.reverse()
    for name, check, stab in sectors:
        found = search_basis(name, check, stab, n, rng, deadline)
        if found is not None and (best is None or found[0] < best[0]):
            best = found

    if best is None:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    else:
        w, name, v = best
        result = {
            "status": "completed",
            "basis": name,
            "vector": bits_to_list(v, n),
            "upper_bound": w,
        }
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
