#!/usr/bin/env python3
import argparse
import json
import random
import time


def read_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n_cols = max((len(r) for r in data), default=0)
        return rows_from_dense(data, n_cols), n_cols

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or dense row list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj["data"]
        n_cols = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        return rows_from_dense(data, n_cols), n_cols

    if "rows" in obj:
        rows = obj["rows"]
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n_cols <= 0:
            n_cols = 1 + max((max(r) for r in rows if r), default=-1)
        return rows_from_sparse(rows, n_cols), n_cols

    raise ValueError("unrecognized matrix format")


def rows_from_dense(data, n_cols):
    out = []
    for row in data:
        x = 0
        for i, bit in enumerate(row[:n_cols]):
            if bit & 1:
                x |= 1 << i
        if x:
            out.append(x)
    return out


def rows_from_sparse(data, n_cols):
    mask = (1 << n_cols) - 1 if n_cols > 0 else 0
    out = []
    for row in data:
        x = 0
        for c in row:
            c = int(c)
            if 0 <= c < n_cols:
                x |= 1 << c
        x &= mask
        if x:
            out.append(x)
    return out


def parity(x):
    return x.bit_count() & 1


def rref_basis(rows):
    basis = {}
    for row in rows:
        add_to_basis(row, basis)
    return basis


def add_to_basis(row, basis):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            for q, y in list(basis.items()):
                if (y >> p) & 1:
                    basis[q] = y ^ x
            basis[p] = x
            return True
        x ^= b
    return False


def reduce_by_basis(x, basis):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def kernel_basis(check_rows, n_cols):
    basis = rref_basis(check_rows)
    pivots = set(basis)
    free_cols = [c for c in range(n_cols) if c not in pivots]
    out = []
    for f in free_cols:
        x = 1 << f
        for p, row in basis.items():
            if (row >> f) & 1:
                x |= 1 << p
        out.append(x)
    return out


def quotient_logical_reps(check_rows, stab_rows, n_cols):
    span = rref_basis(stab_rows)
    reps = []
    for v in kernel_basis(check_rows, n_cols):
        if not in_rowspace(v, span):
            reps.append(v)
            add_to_basis(v, span)
    return reps


def verifies(v, check_rows, stab_basis):
    if v == 0:
        return False
    for row in check_rows:
        if parity(v & row):
            return False
    return not in_rowspace(v, stab_basis)


def luby(i):
    k = 1
    while (1 << k) - 1 < i:
        k += 1
    if i == (1 << k) - 1:
        return 1 << (k - 1)
    return luby(i - (1 << (k - 1)) + 1)


def greedy_reduce(v, stab_rows, rng, passes):
    if not stab_rows:
        return v
    best = v
    best_w = v.bit_count()
    order = list(stab_rows)
    for _ in range(passes):
        rng.shuffle(order)
        changed = False
        for row in order:
            y = best ^ row
            wy = y.bit_count()
            if wy < best_w:
                best, best_w = y, wy
                changed = True
        if not changed:
            break
    return best


def random_logical_combo(reps, rng):
    v = reps[rng.randrange(len(reps))]
    # Heavy-tailed subset sizes without making the common case too dense.
    extra_cap = min(len(reps) - 1, 1 << rng.randrange(0, min(6, max(1, len(reps))).bit_length()))
    for _ in range(extra_cap):
        if rng.random() < 0.35:
            v ^= reps[rng.randrange(len(reps))]
    if v == 0:
        v = reps[rng.randrange(len(reps))]
    return v


def perturb_with_stabilizers(v, stab_rows, rng, budget):
    if not stab_rows:
        return v
    t = min(len(stab_rows), max(1, budget))
    # Most restarts get a modest perturbation; Luby spikes occasionally go deep.
    count = 1 + rng.randrange(t)
    for _ in range(count):
        v ^= stab_rows[rng.randrange(len(stab_rows))]
    return v


def one_basis_search(name, check_rows, stab_rows, n_cols, rng, deadline):
    stab_basis = rref_basis(stab_rows)
    reps = quotient_logical_reps(check_rows, stab_rows, n_cols)
    if not reps:
        return None
    incident = [[] for _ in range(n_cols)]
    for row in stab_rows:
        x = row
        while x:
            lsb = x & -x
            incident[lsb.bit_length() - 1].append(row)
            x ^= lsb

    best = None
    best_w = n_cols + 1

    seeds = sorted(reps, key=int.bit_count)[: min(len(reps), 24)]
    for v in seeds:
        y = greedy_reduce(v, stab_rows, rng, 4)
        if verifies(y, check_rows, stab_basis) and y.bit_count() < best_w:
            best, best_w = y, y.bit_count()
            if best_w == 1:
                return name, best, best_w

    restart = 1
    base = 3 if n_cols < 256 else 2
    while time.monotonic() < deadline:
        span = luby(restart)
        v = random_logical_combo(reps, rng)
        v = perturb_with_stabilizers(v, stab_rows, rng, span * base)
        y = greedy_reduce(v, stab_rows, rng, 1 + min(18, span))

        # A second phase tries to knock out currently occupied coordinates by
        # sampling stabilizers incident on them, but only accepts real progress.
        local_best = y
        local_w = y.bit_count()
        for _ in range(min(64, span * 8)):
            if local_w <= 1 or not stab_rows:
                break
            bit = rng.randrange(n_cols)
            if ((local_best >> bit) & 1) == 0:
                continue
            bucket = incident[bit]
            if not bucket:
                continue
            row = bucket[rng.randrange(len(bucket))]
            z = local_best ^ row
            wz = z.bit_count()
            if wz < local_w or (wz == local_w and rng.random() < 0.03):
                local_best, local_w = z, wz
        y = local_best

        if verifies(y, check_rows, stab_basis) and local_w < best_w:
            best, best_w = y, local_w
            if best_w == 1:
                return name, best, best_w
        restart += 1

    if best is None:
        for v in reps:
            if verifies(v, check_rows, stab_basis):
                best = v
                best_w = v.bit_count()
                break
    if best is None:
        return None
    return name, best, best_w


def vector_to_list(v, n_cols):
    return [(v >> i) & 1 for i in range(n_cols)]


def solve(hx, hz, seed):
    if hx[1] != hz[1]:
        raise ValueError("hx and hz have different column counts")
    n_cols = hx[1]
    rng = random.Random(seed)
    deadline = time.monotonic() + 3.5

    # Z logicals commute with X checks and are nontrivial modulo Z stabilizers.
    jobs = [
        ("z", hx[0], hz[0]),
        ("x", hz[0], hx[0]),
    ]
    rng.shuffle(jobs)

    best = None
    for name, checks, stabs in jobs:
        remaining = max(0.5, deadline - time.monotonic())
        sub_deadline = time.monotonic() + remaining / (2 if best is None else 1)
        ans = one_basis_search(name, checks, stabs, n_cols, rng, sub_deadline)
        if ans is not None and (best is None or ans[2] < best[2]):
            best = ans

    # Reliable fallback: if time was consumed unevenly, still derive and verify
    # the first available logical representative in either basis.
    if best is None:
        for name, checks, stabs in jobs:
            ans = one_basis_search(name, checks, stabs, n_cols, rng, time.monotonic())
            if ans is not None:
                best = ans
                break

    if best is None:
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    basis, v, w = best
    return {
        "status": "completed",
        "basis": basis,
        "vector": vector_to_list(v, n_cols),
        "upper_bound": int(w),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    try:
        result = solve(read_matrix(args.hx), read_matrix(args.hz), args.seed)
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
