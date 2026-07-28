#!/usr/bin/env python3
import argparse
import json
import random


def matrix_from_json(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"}.issubset(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            if len(row) != n_cols:
                raise ValueError("dense row has wrong length")
            for j, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix contains non-binary entry")
                if bit:
                    x |= 1 << j
            rows.append(x)
        return rows, n_cols

    if {"num_cols", "rows"}.issubset(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            x = 0
            for j in row:
                j = int(j)
                if j <= last or j < 0 or j >= n_cols:
                    raise ValueError("sparse row indices are not strictly increasing in range")
                x |= 1 << j
                last = j
            rows.append(x)
        return rows, n_cols

    raise ValueError("unrecognized matrix JSON format")


def add_to_basis(basis, row):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def echelon_basis(rows):
    basis = {}
    for row in rows:
        add_to_basis(basis, row)
    return basis


def rref_basis(rows):
    basis = echelon_basis(rows)
    for p in sorted(basis):
        row = basis[p]
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    return basis


def in_span(basis, row):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        x ^= b
    return True


def nullspace_basis(rows, n_cols):
    rref = rref_basis(rows)
    pivots = set(rref)
    out = []
    for f in range(n_cols):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rref.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def kernel_ok(check_rows, v):
    return all(((row & v).bit_count() & 1) == 0 for row in check_rows)


def bits(v, n_cols):
    return [(v >> j) & 1 for j in range(n_cols)]


def greedy_coset_reduce(v, stabilizer_rows, rng, rounds):
    if not stabilizer_rows:
        return v
    rows = list(stabilizer_rows)
    rows.sort(key=int.bit_count)
    best = v
    best_w = best.bit_count()

    for _ in range(rounds):
        cur = best
        cur_w = best_w
        if _:
            rng.shuffle(rows)
        changed = True
        passes = 0
        while changed and passes < 8:
            changed = False
            passes += 1
            for row in rows:
                nxt = cur ^ row
                nw = nxt.bit_count()
                if nw < cur_w:
                    cur = nxt
                    cur_w = nw
                    changed = True
        if cur_w < best_w:
            best = cur
            best_w = cur_w
    return best


def random_walk_reduce(v, stabilizer_rows, rng, steps):
    if not stabilizer_rows:
        return v
    cur = v
    cur_w = cur.bit_count()
    best = cur
    best_w = cur_w
    temperature = max(1.0, cur_w / 4.0)
    for t in range(steps):
        row = rng.choice(stabilizer_rows)
        nxt = cur ^ row
        nw = nxt.bit_count()
        delta = nw - cur_w
        if delta <= 0 or rng.random() < 2.0 ** (-delta / max(0.25, temperature)):
            cur = nxt
            cur_w = nw
            if nw < best_w:
                best = nxt
                best_w = nw
        if (t + 1) % 64 == 0:
            temperature *= 0.82
    return greedy_coset_reduce(best, stabilizer_rows, rng, 2)


def logical_representatives(kernel_rows, stabilizer_rows):
    stab_basis = echelon_basis(stabilizer_rows)
    span = dict(stab_basis)
    reps = []
    for v in kernel_rows:
        if add_to_basis(span, v):
            reps.append(v)
    return reps, stab_basis


def search_basis(name, commute_rows, stabilizer_rows, n_cols, rng):
    kernel = nullspace_basis(commute_rows, n_cols)
    reps, stab_basis = logical_representatives(kernel, stabilizer_rows)
    if not reps:
        return None

    reducer_rows = [r for r in stabilizer_rows if r] + list(echelon_basis(stabilizer_rows).values())
    reducer_rows = list(dict.fromkeys(reducer_rows))
    best = None
    best_w = n_cols + 1

    def consider(v, polish=True):
        nonlocal best, best_w
        if not v or in_span(stab_basis, v):
            return
        if polish:
            v = greedy_coset_reduce(v, reducer_rows, rng, 3)
        if not kernel_ok(commute_rows, v) or in_span(stab_basis, v):
            return
        w = v.bit_count()
        if 0 < w < best_w:
            best = v
            best_w = w

    for v in reps:
        consider(v)

    attempts = 900 + 20 * min(n_cols, 1000) + 80 * min(len(reps), 80)
    for i in range(attempts):
        v = 0
        if i % 5 == 0:
            take = 1 + rng.randrange(min(4, len(reps)))
            for j in rng.sample(range(len(reps)), take):
                v ^= reps[j]
        else:
            for rep in reps:
                if rng.getrandbits(1):
                    v ^= rep
            if v == 0:
                v = rng.choice(reps)

        if reducer_rows and i % 9 == 0:
            v = random_walk_reduce(v, reducer_rows, rng, 96)
            consider(v, polish=False)
        else:
            consider(v)

    if best is None:
        return None
    return {"basis": name, "vector": bits(best, n_cols), "upper_bound": best_w}


def solve(hx_path, hz_path, seed, output_dir):
    _ = output_dir
    hx, nx = matrix_from_json(hx_path)
    hz, nz = matrix_from_json(hz_path)
    if nx != nz:
        raise ValueError("Hx and Hz have different column counts")

    rng = random.Random(seed)
    choices = [
        search_basis("x", hz, hx, nx, rng),
        search_basis("z", hx, hz, nx, rng),
    ]
    choices = [c for c in choices if c is not None]
    if not choices:
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    best = min(choices, key=lambda c: (c["upper_bound"], c["basis"]))
    return {
        "status": "completed",
        "basis": best["basis"],
        "vector": best["vector"],
        "upper_bound": best["upper_bound"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        result = solve(args.hx, args.hz, args.seed, args.output_dir)
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
