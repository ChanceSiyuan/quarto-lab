#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n_cols

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            last = -1
            for idx in row:
                idx = int(idx)
                if idx <= last or idx < 0 or idx >= n_cols:
                    raise ValueError("invalid sparse row")
                x |= 1 << idx
                last = idx
            rows.append(x)
        return rows, n_cols

    raise ValueError("unrecognized matrix JSON format")


def reduce_by(x, basis):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def insert_basis(basis, row):
    x = reduce_by(row, basis)
    if not x:
        return False
    p = x.bit_length() - 1
    for q, b in list(basis.items()):
        if q != p and ((b >> p) & 1):
            basis[q] = b ^ x
    basis[p] = x
    return True


def rref_basis(rows):
    basis = {}
    for row in rows:
        if row:
            insert_basis(basis, row)
    return basis


def nullspace_basis(rows, n_cols):
    basis = rref_basis(rows)
    pivots = set(basis)
    out = []
    for free_col in range(n_cols):
        if free_col in pivots:
            continue
        v = 1 << free_col
        for p, row in basis.items():
            if (row >> free_col) & 1:
                v |= 1 << p
        out.append(v)
    return out


def quotient_logicals(kernel_rows, stabilizer_rows, n_cols):
    kernel = nullspace_basis(kernel_rows, n_cols)
    span = rref_basis(stabilizer_rows)
    logicals = []
    for v in kernel:
        if reduce_by(v, span):
            logicals.append(v)
            insert_basis(span, v)
    return logicals, rref_basis(stabilizer_rows)


def in_kernel(v, rows):
    for row in rows:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def verified(v, kernel_rows, stabilizer_basis):
    return v != 0 and in_kernel(v, kernel_rows) and reduce_by(v, stabilizer_basis) != 0


def vector_to_list(v, n_cols):
    return [(v >> i) & 1 for i in range(n_cols)]


def greedy_reduce(v, stabilizers, rng, rounds):
    if not stabilizers:
        return v
    cur = v
    cur_w = cur.bit_count()
    for _ in range(rounds):
        if len(stabilizers) > 768:
            rows = rng.sample(stabilizers, 768)
        else:
            rows = list(stabilizers)
        rng.shuffle(rows)
        changed = False
        for row in rows:
            cand = cur ^ row
            w = cand.bit_count()
            if w < cur_w:
                cur = cand
                cur_w = w
                changed = True
        if not changed:
            break
    return cur


def random_logical_combo(logicals, rng):
    v = 0
    used = False
    for g in logicals:
        if rng.getrandbits(1):
            v ^= g
            used = True
    if not used:
        v = rng.choice(logicals)
    return v


def randomized_search(name, kernel_rows, stabilizer_rows, n_cols, rng):
    logicals, stabilizer_basis = quotient_logicals(kernel_rows, stabilizer_rows, n_cols)
    if not logicals:
        return None

    dense_stabs = [r for r in stabilizer_rows if r]
    reduced_stabs = list(stabilizer_basis.values())
    all_stabs = dense_stabs + [r for r in reduced_stabs if r not in dense_stabs]
    all_stabs.sort(key=int.bit_count)

    best = None

    def consider(v, rounds=3):
        nonlocal best
        v = greedy_reduce(v, all_stabs, rng, rounds)
        if verified(v, kernel_rows, stabilizer_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for g in logicals:
        consider(g, rounds=4)

    n_trials = 256 + 24 * len(logicals) + 2 * len(all_stabs)
    n_trials = max(384, min(6000, n_trials))
    for t in range(n_trials):
        v = random_logical_combo(logicals, rng)

        if all_stabs:
            if t & 1:
                for row in rng.sample(all_stabs, min(len(all_stabs), 1 + rng.randrange(8))):
                    v ^= row
            else:
                for row in rng.sample(all_stabs, min(len(all_stabs), 1 + rng.randrange(16))):
                    v ^= row

        consider(v, rounds=2 + (t % 3 == 0))

    if best is None:
        return None
    return {"basis": name, "vector": best, "upper_bound": best.bit_count()}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    os.makedirs(args.output_dir, exist_ok=True)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("Hx and Hz have different column counts")

    rng = random.Random(args.seed)
    searches = [
        ("x", hz, hx),
        ("z", hx, hz),
    ]
    rng.shuffle(searches)

    best = None
    for name, kernel_rows, stabilizer_rows in searches:
        result = randomized_search(name, kernel_rows, stabilizer_rows, nx, rng)
        if result is not None and (best is None or result["upper_bound"] < best["upper_bound"]):
            best = result

    if best is None:
        out = {"status": "not_found", "basis": "x", "vector": [0] * nx, "upper_bound": None}
    else:
        out = {
            "status": "completed",
            "basis": best["basis"],
            "vector": vector_to_list(best["vector"], nx),
            "upper_bound": best["upper_bound"],
        }

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main(sys.argv[1:])
