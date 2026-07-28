#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def mask_from_indices(indices):
    x = 0
    for i in indices:
        if i >= 0:
            x |= 1 << i
    return x


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", 0))
        rows = []
        for row in data:
            x = 0
            if isinstance(row, int):
                x = int(row)
            else:
                for j, v in enumerate(row):
                    if int(v) & 1:
                        x |= 1 << j
            rows.append(x)
        if n == 0 and data:
            n = max([len(r) for r in data if not isinstance(r, int)] or [0])
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = [mask_from_indices([int(i) for i in row]) for row in (obj.get("rows") or [])]
        if n == 0 and rows:
            n = max(r.bit_length() for r in rows)
        return rows, n

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for row in obj:
            x = 0
            for j, v in enumerate(row):
                if int(v) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def add_reduced_basis_vector(basis, x):
    while x:
        p = x.bit_length() - 1
        y = basis.get(p)
        if y is None:
            for q, row in list(basis.items()):
                if (row >> p) & 1:
                    basis[q] = row ^ x
            basis[p] = x
            return True
        x ^= y
    return False


def reduced_basis(rows):
    basis = {}
    for row in rows:
        add_reduced_basis_vector(basis, row)
    return basis


def reduce_by_basis(x, basis):
    while x:
        p = x.bit_length() - 1
        y = basis.get(p)
        if y is None:
            return x
        x ^= y
    return 0


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    rb = reduced_basis(rows)
    pivots = set(rb)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, checks):
    for row in checks:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def verified(v, checks, stab_basis):
    return v != 0 and syndrome_zero(v, checks) and not in_rowspace(v, stab_basis)


def vector_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def greedy_descent(v, moves, checks, stab_basis, rng, passes=5):
    if not verified(v, checks, stab_basis):
        return None
    best = v
    best_w = v.bit_count()
    ordered = list({m for m in moves if m})
    for _ in range(passes):
        rng.shuffle(ordered)
        changed = False
        for m in ordered:
            u = best ^ m
            w = u.bit_count()
            if w < best_w and verified(u, checks, stab_basis):
                best, best_w = u, w
                changed = True
        if not changed:
            break
    return best


def build_neighborhood_moves(stab_rows, kernel_basis, n, rng):
    moves = []
    moves.extend(stab_rows)

    row_w = sorted((r.bit_count(), r) for r in stab_rows if r)
    moves.extend(r for _, r in row_w[: min(128, len(row_w))])

    # Multi-scale block moves in column order: collect rows touching random
    # windows, then xor a small random subset. These moves preserve the logical
    # coset when made from stabilizers, but cover larger support rearrangements
    # than single-row descent.
    scales = [2, 4, 8, 16, 32, 64]
    if n > 0 and stab_rows:
        by_col = [[] for _ in range(n)]
        for r in stab_rows:
            x = r
            while x:
                lsb = x & -x
                c = lsb.bit_length() - 1
                if c < n:
                    by_col[c].append(r)
                x ^= lsb
        for scale in scales:
            if scale > max(1, n * 2):
                continue
            trials = min(80, max(12, n // max(1, scale) + 6))
            width = min(n, scale)
            for _ in range(trials):
                start = rng.randrange(max(1, n - width + 1))
                pool = []
                for c in range(start, min(n, start + width)):
                    pool.extend(by_col[c])
                if not pool:
                    continue
                rng.shuffle(pool)
                x = 0
                for r in pool[: rng.randint(1, min(6, len(pool)))]:
                    x ^= r
                if x:
                    moves.append(x)

    # A few kernel-basis perturbations allow controlled jumps between logical
    # cosets; verification keeps only genuine logical witnesses.
    kb = sorted([b for b in kernel_basis if b], key=int.bit_count)
    moves.extend(kb[: min(96, len(kb))])
    return list({m for m in moves if m})


def deterministic_logical(kernel_basis, stab_basis, checks):
    for v in sorted(kernel_basis, key=int.bit_count):
        if verified(v, checks, stab_basis):
            return v

    # Incremental separation fallback: build a basis for the stabilizer rowspace
    # plus previously absorbed kernel vectors. The first independent kernel
    # vector is outside the stabilizer rowspace and is therefore logical.
    sep = dict(stab_basis)
    for v in sorted(kernel_basis, key=int.bit_count):
        if reduce_by_basis(v, sep) != 0:
            if verified(v, checks, stab_basis):
                return v
            add_reduced_basis_vector(sep, v)
    return None


def random_kernel_combo(kernel_basis, rng, max_terms=None):
    if not kernel_basis:
        return 0
    if max_terms is None:
        max_terms = min(len(kernel_basis), rng.choice([1, 2, 3, 4, 6, 8, 12]))
    k = rng.randint(1, max(1, max_terms))
    idxs = rng.sample(range(len(kernel_basis)), min(k, len(kernel_basis)))
    v = 0
    for i in idxs:
        v ^= kernel_basis[i]
    return v


def search_side(name, checks, stabs, n, rng, deadline):
    stab_basis = reduced_basis(stabs)
    kernel_basis = nullspace_basis(checks, n)
    if not kernel_basis:
        return None

    css_stab_moves = [r for r in stabs if r and syndrome_zero(r, checks)]
    seed = deterministic_logical(kernel_basis, stab_basis, checks)
    if seed is None:
        return None

    moves = build_neighborhood_moves(css_stab_moves, kernel_basis, n, rng)
    best = greedy_descent(seed, moves, checks, stab_basis, rng, passes=8) or seed
    best_w = best.bit_count()

    ordered_kernel = sorted(kernel_basis, key=int.bit_count)
    rounds = 0
    while time.monotonic() < deadline:
        rounds += 1
        if rounds % 5 == 0:
            v = best
            block = rng.choice([2, 4, 8, 16, 32, 64])
            if ordered_kernel:
                start = rng.randrange(len(ordered_kernel))
                for b in ordered_kernel[start : min(len(ordered_kernel), start + block)]:
                    if rng.random() < 0.35:
                        v ^= b
        else:
            v = random_kernel_combo(ordered_kernel, rng)

        if not verified(v, checks, stab_basis):
            continue

        # Multi-scale stabilizer perturbation before descent.
        if css_stab_moves:
            for scale in rng.sample([1, 2, 3, 5, 8, 13], 3):
                u = v
                for r in rng.sample(css_stab_moves, min(scale, len(css_stab_moves))):
                    u ^= r
                if verified(u, checks, stab_basis) and u.bit_count() <= v.bit_count() + scale:
                    v = u

        v = greedy_descent(v, moves, checks, stab_basis, rng, passes=4) or v
        w = v.bit_count()
        if w < best_w and verified(v, checks, stab_basis):
            best, best_w = v, w
            if best_w <= 1:
                break

    return {"basis": name, "vector": vector_list(best, n), "upper_bound": best_w}


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
        n = max(nx, nz, max((r.bit_length() for r in hx + hz), default=0))
        full_mask = (1 << n) - 1 if n >= 0 else 0
        hx = [r & full_mask for r in hx]
        hz = [r & full_mask for r in hz]

        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        if n <= 128:
            budget = 1.25
        elif n <= 512:
            budget = 3.0
        elif n <= 2048:
            budget = 6.0
        else:
            budget = 9.0

        # Search both CSS bases with independent randomized trajectories and
        # report the lower-weight verified upper-bound witness.
        zx_rng = random.Random(rng.randrange(1 << 62))
        xz_rng = random.Random(rng.randrange(1 << 62))
        start = time.monotonic()
        x_res = search_side("x", hz, hx, n, zx_rng, start + 0.5 * budget)
        z_res = search_side("z", hx, hz, n, xz_rng, start + budget)
        choices = [r for r in (x_res, z_res) if r is not None]
        if choices:
            ans = min(choices, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
            ans = {"status": "completed", **ans}
        else:
            ans = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        ans = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(ans, separators=(",", ":")))


if __name__ == "__main__":
    main()
