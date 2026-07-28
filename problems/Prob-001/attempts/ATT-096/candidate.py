#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def bits_iter(x):
    while x:
        lsb = x & -x
        yield lsb.bit_length() - 1
        x ^= lsb


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            v = 0
            for j, b in enumerate(r):
                if int(b) & 1:
                    v |= 1 << j
            rows.append(v)
        return rows, n

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj and "n_cols" in obj:
        n = int(obj["n_cols"])
        rows = []
        for r in obj["data"]:
            v = 0
            for j, b in enumerate(r):
                if int(b) & 1:
                    v |= 1 << j
            rows.append(v & ((1 << n) - 1 if n else 0))
        return rows, n

    if "rows" in obj and ("num_cols" in obj or "n_cols" in obj):
        n = int(obj.get("num_cols", obj.get("n_cols")))
        rows = []
        for r in obj["rows"]:
            v = 0
            if isinstance(r, dict):
                r = r.get("cols", r.get("indices", []))
            for j in r:
                jj = int(j)
                if 0 <= jj < n:
                    v |= 1 << jj
            rows.append(v)
        return rows, n

    raise ValueError("unrecognized matrix JSON format")


def make_reducer(rows):
    basis = {}
    for r in rows:
        x = int(r)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def reduce_with_basis(x, basis):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_span(x, basis):
    return reduce_with_basis(x, basis) == 0


def rref_rows(rows, n):
    basis = {}
    for r in rows:
        x = int(r) & ((1 << n) - 1 if n else 0)
        while x:
            lsb = x & -x
            p = lsb.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                for q, row in list(basis.items()):
                    if (row >> p) & 1:
                        basis[q] = row ^ x
                basis[p] = x
                break
    return basis


def kernel_basis(check_rows, n):
    rref = rref_rows(check_rows, n)
    pivots = set(rref)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rref.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def quotient_logicals(check_rows, stab_rows, n):
    span = make_reducer(stab_rows)
    reps = []
    for v in sorted(kernel_basis(check_rows, n), key=int.bit_count):
        if v and not in_span(v, span):
            reps.append(v)
            x = v
            while x:
                p = x.bit_length() - 1
                if p in span:
                    x ^= span[p]
                else:
                    span[p] = x
                    break
    return reps


def mat_vec_zero(rows, v):
    return all(((r & v).bit_count() & 1) == 0 for r in rows)


def verified(v, check_rows, stab_basis):
    return v != 0 and mat_vec_zero(check_rows, v) and not in_span(v, stab_basis)


def vector_list(v, n):
    return [1 if (v >> i) & 1 else 0 for i in range(n)]


def greedy_stabilizer_descent(v, stab_rows, rng, max_passes=10):
    if not stab_rows:
        return v
    rows = [r for r in stab_rows if r]
    cur = v
    for _ in range(max_passes):
        improved = False
        rng.shuffle(rows)
        base_w = cur.bit_count()
        best_delta = 0
        best_row = 0
        # First-improvement with a small best-of-window makes the descent less
        # deterministic without spending a full pass on every stabilizer row.
        window = min(len(rows), 256)
        start = rng.randrange(len(rows)) if rows else 0
        for i in range(len(rows)):
            r = rows[(start + i) % len(rows)]
            nw = (cur ^ r).bit_count()
            delta = nw - base_w
            if delta < best_delta:
                best_delta = delta
                best_row = r
                if i >= window:
                    break
        if best_row:
            cur ^= best_row
            improved = True
        if not improved:
            break
    return cur


def build_column_masks(stab_rows, n):
    masks = [0] * n
    for i, r in enumerate(stab_rows):
        for c in bits_iter(r):
            if c < n:
                masks[c] |= 1 << i
    return masks


def solve_gf2(equations, nvars, rng):
    rows = [e for e in equations if (e & ((1 << nvars) - 1)) or ((e >> nvars) & 1)]
    basis = {}
    rhs_bit = 1 << nvars
    for e in rows:
        x = e
        while x & (rhs_bit - 1):
            p = (x & -x).bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                for q, row in list(basis.items()):
                    if (row >> p) & 1:
                        basis[q] = row ^ x
                basis[p] = x
                break
        else:
            if (x >> nvars) & 1:
                return None

    sol = 0
    free_mask = ((1 << nvars) - 1)
    for p in basis:
        free_mask &= ~(1 << p)
    # Random free variables give different stabilizer representatives while
    # still forcing the selected coordinates to zero.
    for f in bits_iter(free_mask):
        if rng.getrandbits(1):
            sol |= 1 << f
    for p, row in sorted(basis.items(), reverse=True):
        parity = ((row & sol).bit_count() & 1) ^ ((row >> nvars) & 1)
        if parity:
            sol |= 1 << p
        else:
            sol &= ~(1 << p)
    return sol


def apply_row_combo(v, rows, combo):
    cur = v
    while combo:
        lsb = combo & -combo
        i = lsb.bit_length() - 1
        if i < len(rows):
            cur ^= rows[i]
        combo ^= lsb
    return cur


def erasure_representative_search(v, stab_rows, col_masks, rng, rounds):
    if not stab_rows or not col_masks:
        return v
    cur = v
    nvars = len(stab_rows)
    ones_cache = None
    for t in range(rounds):
        if cur == 0:
            break
        if ones_cache is None or t % 4 == 0:
            ones_cache = list(bits_iter(cur))
        if not ones_cache:
            break
        rng.shuffle(ones_cache)
        # Heavy-tailed erasure sizes: mostly modest repairs, sometimes an
        # aggressive projection that can jump to another part of the coset.
        cap = min(len(ones_cache), max(1, nvars), 384)
        if rng.random() < 0.18:
            k = rng.randint(1, cap)
        else:
            k = min(cap, 1 + int(rng.expovariate(1 / max(2.0, cap ** 0.5))))
        target = ones_cache[:k]
        equations = []
        for c in target:
            eq = col_masks[c]
            if (cur >> c) & 1:
                eq |= 1 << nvars
            equations.append(eq)
        sol = solve_gf2(equations, nvars, rng)
        if sol is None:
            continue
        cand = apply_row_combo(cur, stab_rows, sol)
        cand = greedy_stabilizer_descent(cand, stab_rows, rng, max_passes=4)
        if cand and cand.bit_count() <= cur.bit_count():
            cur = cand
            ones_cache = None
    return cur


def random_logical_seed(reps, rng):
    if len(reps) == 1:
        return reps[0]
    combo = 0
    # Sparse quotient combinations keep witnesses interpretable; occasional
    # dense mixes help when every basis representative is poorly conditioned.
    if rng.random() < 0.8:
        take = 1 + int(rng.expovariate(0.7))
        take = min(len(reps), max(1, take))
        for i in rng.sample(range(len(reps)), take):
            combo ^= reps[i]
    else:
        for r in reps:
            if rng.getrandbits(1):
                combo ^= r
        if combo == 0:
            combo = rng.choice(reps)
    return combo


def improve_basis(name, check_rows, stab_rows, n, seed, deadline):
    rng = random.Random((seed << 8) ^ (17 if name == "x" else 43) ^ n)
    stab_basis = make_reducer(stab_rows)
    reps = quotient_logicals(check_rows, stab_rows, n)
    if not reps:
        return None

    col_masks = build_column_masks(stab_rows, n) if stab_rows else []
    best = None

    def consider(v):
        nonlocal best
        if verified(v, check_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for r in reps:
        consider(greedy_stabilizer_descent(r, stab_rows[:], rng, max_passes=12))
    if best is None:
        for r in reps:
            consider(r)

    rounds = 0
    base_attempts = 80 + 12 * min(len(reps), 64)
    while time.monotonic() < deadline and rounds < base_attempts:
        seed_v = random_logical_seed(reps, rng)
        if best is not None and rng.random() < 0.35:
            seed_v ^= best
            if seed_v == 0:
                seed_v = random_logical_seed(reps, rng)
        cand = greedy_stabilizer_descent(seed_v, stab_rows[:], rng, max_passes=8)
        erounds = 8 if n < 2000 else 4
        cand = erasure_representative_search(cand, stab_rows, col_masks, rng, erounds)
        cand = greedy_stabilizer_descent(cand, stab_rows[:], rng, max_passes=8)
        consider(cand)
        rounds += 1

    if best is None:
        for r in reps:
            if verified(r, check_rows, stab_basis):
                best = r
                break
    return best


def run(args):
    hx, nx = parse_matrix(args.hx)
    hz, nz = parse_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1 if n else 0) for r in hx]
    hz = [r & ((1 << n) - 1 if n else 0) for r in hz]
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    start = time.monotonic()
    budget = 18.0
    deadline = start + budget
    z_wit = improve_basis("z", hx, hz, n, args.seed, start + budget * 0.50)
    x_wit = improve_basis("x", hz, hx, n, args.seed, deadline)

    choices = []
    if x_wit is not None:
        choices.append(("x", x_wit))
    if z_wit is not None:
        choices.append(("z", z_wit))
    if not choices:
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    basis, vec = min(choices, key=lambda item: (item[1].bit_count(), 0 if item[0] == "x" else 1))
    return {
        "status": "completed",
        "basis": basis,
        "vector": vector_list(vec, n),
        "upper_bound": int(vec.bit_count()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
