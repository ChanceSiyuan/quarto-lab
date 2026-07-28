#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        n_cols = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n_cols

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data", [])
        n_cols = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for i, b in enumerate(r[:n_cols]):
                if int(b) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n_cols

    if "rows" in obj:
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            x = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    x ^= 1 << c
                    if c + 1 > n_cols:
                        n_cols = c + 1
            rows.append(x)
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


def mask_to_list(x, n):
    return [(x >> i) & 1 for i in range(n)]


def weight(x):
    return x.bit_count()


def dot_parity(a, b):
    return (a & b).bit_count() & 1


def rowspace_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            y = basis.get(p)
            if y is None:
                basis[p] = x
                break
            x ^= y
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


def rref_low(rows):
    piv = {}
    for row in rows:
        x = row
        while x:
            lsb = x & -x
            p = lsb.bit_length() - 1
            y = piv.get(p)
            if y is None:
                piv[p] = x
                break
            x ^= y

    cols = sorted(piv)
    for p in cols:
        rp = piv[p]
        for q in cols:
            if q != p and ((piv[q] >> p) & 1):
                piv[q] ^= rp
    return piv


def nullspace_basis(check_rows, n):
    piv = rref_low([r & ((1 << n) - 1) for r in check_rows])
    pivot_cols = set(piv)
    free_cols = [i for i in range(n) if i not in pivot_cols]
    basis = []
    for f in free_cols:
        v = 1 << f
        for p, row in piv.items():
            if (row >> f) & 1:
                v |= 1 << p
        basis.append(v)
    return basis


def kernel_ok(v, checks):
    return all(dot_parity(v, r) == 0 for r in checks)


def verified(v, checks, stab_basis):
    return v != 0 and kernel_ok(v, checks) and not in_rowspace(v, stab_basis)


def greedy_coset_reduce(v, ordered_stabilizers, rng, passes=3):
    best = v
    best_w = weight(best)
    if not ordered_stabilizers:
        return best

    for _ in range(passes):
        changed = False
        ordered = ordered_stabilizers
        if rng.random() < 0.45:
            ordered = list(ordered_stabilizers)
            rng.shuffle(ordered)
        for s in ordered:
            cand = best ^ s
            cw = weight(cand)
            if cw < best_w or (cw == best_w and rng.random() < 0.03):
                best, best_w = cand, cw
                changed = True
        if not changed:
            break
    return best


def combine_indices(indices, basis):
    v = 0
    for i in indices:
        v ^= basis[i]
    return v


def choose_initials(ns_basis, checks, stab_basis, stabilizers, rng, limit):
    scored = []
    for v in ns_basis:
        if not in_rowspace(v, stab_basis):
            r = greedy_coset_reduce(v, stabilizers, rng, passes=2)
            if verified(r, checks, stab_basis):
                scored.append(r)

    order = sorted(range(len(ns_basis)), key=lambda i: weight(ns_basis[i]))
    pool = order[: min(len(order), 64)]
    for _ in range(limit):
        if not pool:
            break
        size = 1
        roll = rng.random()
        if roll < 0.45:
            size = 2
        elif roll < 0.70:
            size = 3
        elif roll < 0.84:
            size = 4
        inds = rng.sample(pool, min(size, len(pool)))
        v = combine_indices(inds, ns_basis)
        v = greedy_coset_reduce(v, stabilizers, rng, passes=2)
        if verified(v, checks, stab_basis):
            scored.append(v)
    return scored


def annealed_recombine(ns_basis, checks, stab_rows, stab_basis, rng, deadline):
    if not ns_basis:
        return None

    logical_indices = [i for i, v in enumerate(ns_basis) if not in_rowspace(v, stab_basis)]
    if not logical_indices:
        # Some nullspace bases can choose stabilizer-like generators first; random
        # combinations still expose a quotient representative when k > 0.
        logical_indices = list(range(len(ns_basis)))

    initials = choose_initials(ns_basis, checks, stab_basis, stab_rows, rng, 160)
    if not initials:
        for i in logical_indices:
            v = greedy_coset_reduce(ns_basis[i], stab_rows, rng, passes=3)
            if verified(v, checks, stab_basis):
                initials.append(v)
                break
    if not initials:
        return None

    best = min(initials, key=weight)
    current = best
    cur_w = weight(current)
    best_w = cur_w

    low_order = sorted(range(len(ns_basis)), key=lambda i: weight(ns_basis[i]))
    active_pool = low_order[: min(len(low_order), max(16, int(math.sqrt(len(low_order)) * 10)))]
    if not active_pool:
        active_pool = list(range(len(ns_basis)))

    steps = 0
    while time.monotonic() < deadline:
        steps += 1
        temp = max(0.05, 2.5 * (1.0 - min(0.98, steps / 9000.0)))
        cand = current

        # Annealed nullspace-basis mutation: mostly touch low-weight basis
        # elements, with occasional wider jumps to avoid staying in one coset.
        flips = 1
        r = rng.random()
        if r < 0.25:
            flips = 2
        elif r < 0.36:
            flips = 3 + rng.randrange(3)
        elif r < 0.42:
            flips = 6 + rng.randrange(10)

        for _ in range(flips):
            if rng.random() < 0.82:
                idx = rng.choice(active_pool)
            else:
                idx = rng.randrange(len(ns_basis))
            cand ^= ns_basis[idx]

        if rng.random() < 0.70:
            cand = greedy_coset_reduce(cand, stab_rows, rng, passes=1 + (rng.random() < 0.20))

        if not verified(cand, checks, stab_basis):
            if rng.random() < 0.20:
                current = rng.choice(initials)
                cur_w = weight(current)
            continue

        cw = weight(cand)
        if cw < best_w:
            best, best_w = cand, cw
            current, cur_w = cand, cw
            active_pool = low_order[: min(len(low_order), max(24, 2 * best_w + 24))]
            continue

        delta = cw - cur_w
        if delta <= 0 or rng.random() < math.exp(-delta / temp):
            current, cur_w = cand, cw

        if steps % 700 == 0 and initials:
            seed = rng.choice(initials)
            if rng.random() < 0.55 or weight(seed) < cur_w:
                current, cur_w = seed, weight(seed)

    return best


def search_orientation(name, checks, stabilizers, n, seed, time_slice):
    rng = random.Random((seed * 1315423911) ^ (0x58 if name == "x" else 0x9E))
    stab_basis = rowspace_basis(stabilizers)
    stabilizers = sorted((s for s in stabilizers if s), key=weight)
    ns_basis = nullspace_basis(checks, n)
    deadline = time.monotonic() + time_slice
    v = annealed_recombine(ns_basis, checks, stabilizers, stab_basis, rng, deadline)
    if v is not None and verified(v, checks, stab_basis):
        return name, v

    # Reliable basis-derived fallback: scan all single nullspace basis vectors,
    # then randomized combinations. This is still a witness search, not a
    # distance proof.
    for b in sorted(ns_basis, key=weight):
        if verified(b, checks, stab_basis):
            r = greedy_coset_reduce(b, stabilizers, rng, passes=4)
            return (name, r) if verified(r, checks, stab_basis) else (name, b)

    end = time.monotonic() + max(0.2, min(2.0, time_slice))
    while time.monotonic() < end and ns_basis:
        v = 0
        for i, b in enumerate(ns_basis):
            p = 0.10 if i < 64 else 0.03
            if rng.random() < p:
                v ^= b
        v = greedy_coset_reduce(v, stabilizers, rng, passes=3)
        if verified(v, checks, stab_basis):
            return name, v
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    if n <= 0:
        print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))
        return

    mask = (1 << n) - 1
    hx = [r & mask for r in hx]
    hz = [r & mask for r in hz]

    # X logicals commute with Z checks and are nontrivial modulo X stabilizers;
    # Z logicals use the dual condition.
    first = "x" if random.Random(args.seed).random() < 0.5 else "z"
    order = [first, "z" if first == "x" else "x"]
    results = []
    if n <= 256:
        total_budget = 2.0
    elif n <= 1024:
        total_budget = 4.0
    else:
        total_budget = 6.0
    for name in order:
        if name == "x":
            res = search_orientation("x", hz, hx, n, args.seed, total_budget / 2)
        else:
            res = search_orientation("z", hx, hz, n, args.seed, total_budget / 2)
        if res is not None:
            results.append(res)
            if weight(res[1]) <= 1:
                break

    if results:
        basis, vec = min(results, key=lambda item: weight(item[1]))
        out = {
            "status": "completed",
            "basis": basis,
            "vector": mask_to_list(vec, n),
            "upper_bound": weight(vec),
        }
    else:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))
        sys.exit(0)
