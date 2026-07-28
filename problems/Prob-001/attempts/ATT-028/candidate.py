#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def die_result():
    print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))
    sys.exit(0)


def load_json_arg(value):
    stripped = value.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(value)
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(value)


def matrix_to_rows(obj):
    if isinstance(obj, list):
        data = obj
        n_cols = max((len(r) for r in data), default=0)
        return [row_list_to_int(r) for r in data], n_cols

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj["data"]
        n_cols = int(obj.get("n_cols", obj.get("num_cols", max((len(r) for r in data), default=0))))
        return [row_list_to_int(r) for r in data], n_cols

    if "rows" in obj:
        rows = obj["rows"]
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n_cols == 0:
            n_cols = 1 + max((c for r in rows for c in r), default=-1)
        out = []
        for r in rows:
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n_cols:
                    x ^= 1 << c
            out.append(x)
        return out, n_cols

    raise ValueError("unsupported matrix JSON")


def row_list_to_int(row):
    x = 0
    for i, b in enumerate(row):
        if int(b) & 1:
            x |= 1 << i
    return x


def int_to_bits(x, n):
    return [(x >> i) & 1 for i in range(n)]


def lowbit_index(x):
    return (x & -x).bit_length() - 1


def gf2_rref_basis(rows):
    basis = {}
    for row in rows:
        x = int(row)
        while x:
            p = lowbit_index(x)
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                for q, y in list(basis.items()):
                    if q != p and ((y >> p) & 1):
                        basis[q] = y ^ x
                break
    return basis


def reduce_by_basis(x, basis):
    x = int(x)
    while x:
        p = lowbit_index(x)
        y = basis.get(p)
        if y is None:
            return x
        x ^= y
    return 0


def in_rowspace(x, rows):
    return reduce_by_basis(x, gf2_rref_basis(rows)) == 0


def kernel_basis(check_rows, n):
    rref = gf2_rref_basis(check_rows)
    pivots = set(rref.keys())
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


def independent_rows(rows):
    return list(gf2_rref_basis(rows).values())


def logical_representatives(check_rows, stab_rows, n):
    stab_basis = gf2_rref_basis(stab_rows)
    quotient_basis = {}
    reps = []
    for v in kernel_basis(check_rows, n):
        residue = reduce_by_basis(v, stab_basis)
        if not residue:
            continue
        r = reduce_by_basis(residue, quotient_basis)
        if r:
            reps.append(v)
            p = lowbit_index(r)
            quotient_basis[p] = r
            for q, y in list(quotient_basis.items()):
                if q != p and ((y >> p) & 1):
                    quotient_basis[q] = y ^ r
    return reps


def syndrome_zero(v, check_rows):
    for row in check_rows:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def verify(v, check_rows, stab_rows):
    return v != 0 and syndrome_zero(v, check_rows) and not in_rowspace(v, stab_rows)


def greedy_descent(v, stab_generators, rng, passes=5, mask=None):
    if not stab_generators:
        return v
    rows = list(stab_generators)
    best = v
    best_w = best.bit_count()
    for _ in range(passes):
        rng.shuffle(rows)
        changed = False
        for r in rows:
            nv = best ^ r
            if mask is None:
                old_score = best_w
                new_score = nv.bit_count()
            else:
                old_score = (best & mask).bit_count() * 4 + best_w
                new_score = (nv & mask).bit_count() * 4 + nv.bit_count()
            if new_score < old_score:
                best = nv
                best_w = best.bit_count()
                changed = True
        if not changed:
            break
    return best


def sparse_random_combo(items, rng, max_terms):
    if not items:
        return 0
    terms = 1 + rng.randrange(max(1, min(max_terms, len(items))))
    idxs = rng.sample(range(len(items)), terms)
    v = 0
    for i in idxs:
        v ^= items[i]
    return v


def projection_mask(n, rng, focus=None):
    if n <= 0:
        return 0
    keep_num = rng.randint(max(1, n // 8), max(1, min(n, (3 * n) // 4)))
    mask = 0
    if focus and rng.random() < 0.55:
        coords = [i for i in range(n) if (focus >> i) & 1]
        rng.shuffle(coords)
        for i in coords[: max(1, min(len(coords), keep_num // 2 + 1))]:
            mask |= 1 << i
    while mask.bit_count() < keep_num:
        mask |= 1 << rng.randrange(n)
    return mask


def projected_lift_search(reps, stab_generators, n, rng):
    best = None
    max_terms = 1 if len(reps) <= 1 else min(8, len(reps))

    seeds = []
    for r in reps[: min(len(reps), 64)]:
        seeds.append(r)
    for _ in range(min(96, 8 * max(1, len(reps)))):
        seeds.append(sparse_random_combo(reps, rng, max_terms))

    for seed in seeds:
        if seed == 0:
            continue
        v = greedy_descent(seed, stab_generators, rng, passes=6)
        if best is None or v.bit_count() < best.bit_count():
            best = v

    rounds = 220 if n <= 512 else 120
    if len(stab_generators) > 800:
        rounds = min(rounds, 80)

    for _ in range(rounds):
        if best is not None and rng.random() < 0.45:
            seed = best ^ sparse_random_combo(reps, rng, max_terms)
        else:
            seed = sparse_random_combo(reps, rng, max_terms)
        if seed == 0:
            continue

        mask = projection_mask(n, rng, best)
        v = greedy_descent(seed, stab_generators, rng, passes=4, mask=mask)

        # Lift from the projected optimum and polish in the full coordinate space.
        if stab_generators and rng.random() < 0.50:
            v ^= sparse_random_combo(stab_generators, rng, min(5, len(stab_generators)))
            v = greedy_descent(v, stab_generators, rng, passes=3, mask=mask)
        v = greedy_descent(v, stab_generators, rng, passes=7)

        if best is None or v.bit_count() < best.bit_count():
            best = v
    return best


def solve_basis(name, hx_rows, hz_rows, n, rng):
    if name == "x":
        check_rows, stab_rows = hz_rows, hx_rows
    else:
        check_rows, stab_rows = hx_rows, hz_rows

    reps = logical_representatives(check_rows, stab_rows, n)
    if not reps:
        return None

    # Raw stabilizer rows are useful descent moves; the independent rows keep
    # the full span represented even when raw input contains redundant checks.
    seen = set()
    stab_generators = []
    for r in list(stab_rows) + independent_rows(stab_rows):
        if r and r not in seen:
            seen.add(r)
            stab_generators.append(r)
    cand = projected_lift_search(reps, stab_generators, n, rng)
    if cand is None:
        cand = reps[0]
    cand = greedy_descent(cand, stab_generators, rng, passes=10)

    # Reliable fallback: every quotient representative is a verified logical;
    # choose the best one after stabilizer descent if the randomized lift missed.
    best = cand if verify(cand, check_rows, stab_rows) else None
    for r in reps:
        v = greedy_descent(r, stab_generators, rng, passes=8)
        if verify(v, check_rows, stab_rows) and (best is None or v.bit_count() < best.bit_count()):
            best = v
    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    try:
        hx_rows, nx = matrix_to_rows(load_json_arg(args.hx))
        hz_rows, nz = matrix_to_rows(load_json_arg(args.hz))
        n = max(nx, nz)
        hx_rows = [r & ((1 << n) - 1) for r in hx_rows]
        hz_rows = [r & ((1 << n) - 1) for r in hz_rows]
        rng = random.Random(args.seed)

        best_basis = None
        best_vec = None
        for basis in ("x", "z"):
            # Split RNG streams so changing one basis search does not fully
            # reshuffle the other.
            subrng = random.Random((args.seed + 1000003) ^ (17 if basis == "x" else 53))
            v = solve_basis(basis, hx_rows, hz_rows, n, subrng)
            if v is not None and (best_vec is None or v.bit_count() < best_vec.bit_count()):
                best_basis, best_vec = basis, v

        if best_vec is None:
            die_result()

        result = {
            "status": "completed",
            "basis": best_basis,
            "vector": int_to_bits(best_vec, n),
            "upper_bound": int(best_vec.bit_count()),
        }
        print(json.dumps(result, separators=(",", ":")))
    except Exception:
        die_result()


if __name__ == "__main__":
    main()
