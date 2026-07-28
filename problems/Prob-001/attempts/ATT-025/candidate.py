#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import sys
import time


def fail(message="no_verified_witness"):
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
    sys.exit(0)


def row_from_indices(indices):
    v = 0
    for j in indices:
        if j >= 0:
            v ^= 1 << j
    return v


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for j, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", obj.get("num_cols", max((len(r) for r in data), default=0))))
        rows = []
        for r in data:
            x = 0
            for j, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = [row_from_indices(r) for r in obj.get("rows", [])]
        if n == 0:
            n = max((x.bit_length() for x in rows), default=0)
        return rows, n

    raise ValueError("unrecognized matrix JSON format")


def mask_n(n):
    return (1 << n) - 1 if n > 0 else 0


def reduce_by_basis(v, basis):
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            break
        x ^= b
    return x


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    # Make the representation closer to reduced row echelon form. This is not
    # needed for membership, but it makes nullspace vectors noticeably lighter.
    pivots = sorted(basis)
    for p in pivots:
        for q in pivots:
            if q > p and ((basis[q] >> p) & 1):
                basis[q] ^= basis[p]
    return basis


def in_span(v, basis):
    return reduce_by_basis(v, basis) == 0


def nullspace_basis(check_rows, n):
    rb = rref_basis(check_rows)
    pivots = set(rb)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v & mask_n(n))
    return out


def logical_representatives(kernel_basis, stab_rows):
    ext = rref_basis(stab_rows)
    reps = []
    for v in sorted(kernel_basis, key=lambda x: (x.bit_count(), x.bit_length())):
        if v and reduce_by_basis(v, ext) != 0:
            reps.append(v)
            ext = rref_basis(list(ext.values()) + [v])
    return reps


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def syndrome_zero(v, check_rows):
    return all(((v & r).bit_count() & 1) == 0 for r in check_rows)


def verified(v, n, check_rows, stab_basis):
    v &= mask_n(n)
    return v != 0 and syndrome_zero(v, check_rows) and not in_span(v, stab_basis)


def greedy_reduce(v, stabilizers, check_rows, stab_basis, n, passes=3):
    if not verified(v, n, check_rows, stab_basis):
        return v
    cur = v & mask_n(n)
    rows = [r & mask_n(n) for r in stabilizers if r]
    for _ in range(passes):
        improved = False
        rows.sort(key=lambda r: ((cur ^ r).bit_count() - cur.bit_count(), r.bit_count()))
        for r in rows:
            nv = cur ^ r
            if nv.bit_count() < cur.bit_count() and verified(nv, n, check_rows, stab_basis):
                cur = nv
                improved = True
        if not improved:
            break
    return cur


def random_combination(items, rng, min_terms=1, max_terms=None):
    if not items:
        return 0
    m = len(items)
    if max_terms is None:
        max_terms = m
    k = rng.randint(min_terms, max(min_terms, min(max_terms, m)))
    idxs = rng.sample(range(m), k)
    v = 0
    for i in idxs:
        v ^= items[i]
    return v


def annealed_search(check_rows, stab_rows, n, seed, seconds):
    rng = random.Random(seed)
    stab_basis = rref_basis(stab_rows)
    ker = nullspace_basis(check_rows, n)
    reps = logical_representatives(ker, stab_rows)
    if not reps:
        return None

    stabilizers = sorted([r & mask_n(n) for r in stab_rows if r], key=lambda x: x.bit_count())
    useful_stabs = stabilizers[: min(len(stabilizers), 512)]
    all_kernel = sorted([v for v in ker if v], key=lambda x: x.bit_count())
    light_kernel = all_kernel[: min(len(all_kernel), 256)]

    candidates = []
    for r in reps:
        candidates.append(r)
    for r in reps:
        candidates.append(greedy_reduce(r, useful_stabs, check_rows, stab_basis, n, passes=4))
    for i in range(min(len(reps), 32)):
        for j in range(i + 1, min(len(reps), 32)):
            candidates.append(reps[i] ^ reps[j])

    best = None
    for v in candidates:
        v &= mask_n(n)
        if verified(v, n, check_rows, stab_basis):
            v = greedy_reduce(v, useful_stabs, check_rows, stab_basis, n, passes=4)
            if best is None or v.bit_count() < best.bit_count():
                best = v
    if best is None:
        return None
    if best.bit_count() <= 1:
        return best

    deadline = time.monotonic() + seconds
    restarts = 0
    max_rep_terms = max(1, min(len(reps), 10))
    temp0 = max(1.0, best.bit_count() / 2.0)

    while time.monotonic() < deadline:
        restarts += 1
        if restarts % 5 == 0:
            state = random_combination(reps, rng, 1, max_rep_terms)
        else:
            state = reps[rng.randrange(len(reps))]
        state = greedy_reduce(state, useful_stabs, check_rows, stab_basis, n, passes=2)
        if not verified(state, n, check_rows, stab_basis):
            continue
        cur_w = state.bit_count()
        steps = 80 + 8 * int(math.sqrt(max(1, n)))
        for t in range(steps):
            if time.monotonic() >= deadline:
                break
            frac = t / max(1, steps - 1)
            temp = max(0.05, temp0 * (1.0 - frac) + 0.05 * frac)
            proposal = state

            roll = rng.random()
            if roll < 0.50 and useful_stabs:
                # Stabilizer toggles preserve the logical class and can expose
                # a lighter representative of the same verified witness.
                for _ in range(1 + (rng.random() < 0.20) + (rng.random() < 0.05)):
                    proposal ^= useful_stabs[rng.randrange(len(useful_stabs))]
            elif roll < 0.82 and light_kernel:
                # Kernel-basis mutation changes the logical class but preserves
                # commutation. Rejecting stabilizers keeps the output valid.
                proposal ^= light_kernel[rng.randrange(len(light_kernel))]
            else:
                proposal ^= random_combination(reps, rng, 1, max_rep_terms)

            proposal &= mask_n(n)
            if not verified(proposal, n, check_rows, stab_basis):
                continue
            pw = proposal.bit_count()
            delta = pw - cur_w
            if delta <= 0 or rng.random() < math.exp(-delta / temp):
                state = proposal
                cur_w = pw
                if rng.random() < 0.30:
                    state = greedy_reduce(state, useful_stabs, check_rows, stab_basis, n, passes=1)
                    cur_w = state.bit_count()
                if cur_w < best.bit_count():
                    best = state
                    if best.bit_count() <= 1:
                        return best

    return greedy_reduce(best, useful_stabs, check_rows, stab_basis, n, passes=5)


def solve_basis(name, hx, hz, n, seed, seconds):
    if name == "x":
        check_rows, stab_rows = hz, hx
    else:
        check_rows, stab_rows = hx, hz
    v = annealed_search(check_rows, stab_rows, n, seed, seconds)
    if v is None:
        return None
    stab_basis = rref_basis(stab_rows)
    if verified(v, n, check_rows, stab_basis):
        return v & mask_n(n)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
    except Exception:
        fail()

    n = max(nx, nz)
    hx = [r & mask_n(n) for r in hx]
    hz = [r & mask_n(n) for r in hz]
    if n <= 0:
        fail()
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    # Split a short deterministic budget across the two CSS bases. The
    # independent verifier below is the only gate for printing "completed".
    total_seconds = 5.0
    first = "x" if random.Random(args.seed).random() < 0.5 else "z"
    order = [first, "z" if first == "x" else "x"]
    results = []
    start = time.monotonic()
    for i, basis in enumerate(order):
        elapsed = time.monotonic() - start
        remaining = max(2.0, total_seconds - elapsed)
        budget = remaining if i == len(order) - 1 else max(2.0, remaining * 0.55)
        v = solve_basis(basis, hx, hz, n, args.seed + 1009 * (i + 1), budget)
        if v is not None:
            results.append((v.bit_count(), basis, v))
            if v.bit_count() <= 1:
                break

    if not results:
        fail()

    _, basis, v = min(results, key=lambda x: (x[0], x[1]))
    out = {
        "status": "completed",
        "basis": basis,
        "vector": vector_to_list(v, n),
        "upper_bound": int(v.bit_count()),
    }
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
