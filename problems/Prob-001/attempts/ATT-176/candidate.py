#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x ^= 1 << i
            rows.append(x)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            prev = -1
            for col in row:
                col = int(col)
                if col <= prev or col < 0 or col >= n:
                    raise ValueError("sparse row indices must be strictly increasing")
                x ^= 1 << col
                prev = col
            rows.append(x)
        return rows, n

    raise ValueError("unknown matrix JSON format")


def rref_basis(rows, n):
    pivots = {}
    for value in rows:
        x = int(value)
        while x:
            p = x.bit_length() - 1
            if p in pivots:
                x ^= pivots[p]
            else:
                pivots[p] = x
                break

    for p in sorted(pivots):
        row = pivots[p]
        for q in list(pivots):
            if q != p and ((pivots[q] >> p) & 1):
                pivots[q] ^= row

    return [pivots[p] for p in sorted(pivots, reverse=True)]


def reduce_by_basis(x, basis):
    y = int(x)
    for row in basis:
        if y and ((y >> (row.bit_length() - 1)) & 1):
            y ^= row
    return y


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def kernel_contains(rows, v):
    return all(((row & v).bit_count() & 1) == 0 for row in rows)


def nullspace_basis(rows, n):
    pivots = {}
    for row in rref_basis(rows, n):
        if row:
            pivots[row.bit_length() - 1] = row

    pivot_cols = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_cols]
    basis = []
    for free in free_cols:
        v = 1 << free
        for p, row in pivots.items():
            if (row >> free) & 1:
                v ^= 1 << p
        basis.append(v)
    return basis


def quotient_generators(kernel_basis, stabilizer_basis):
    span = list(stabilizer_basis)
    gens = []
    for v in sorted(kernel_basis, key=lambda x: x.bit_count()):
        if reduce_by_basis(v, span) != 0:
            gens.append(v)
            span = rref_basis(span + [v], max(v.bit_length(), 1))
    return gens


def random_stabilizer(rng, rows, max_terms):
    if not rows:
        return 0
    x = 0
    terms = rng.randint(1, min(max_terms, len(rows)))
    for idx in rng.sample(range(len(rows)), terms):
        x ^= rows[idx]
    return x


def reduce_weight_by_stabilizers(v, stabilizer_rows, rng, rounds):
    best = v
    cur = v
    rows = list(stabilizer_rows)
    for _ in range(rounds):
        rng.shuffle(rows)
        improved = False
        for row in rows:
            cand = cur ^ row
            if cand.bit_count() <= cur.bit_count():
                if cand.bit_count() < cur.bit_count():
                    improved = True
                cur = cand
        if cur.bit_count() < best.bit_count():
            best = cur
        if not improved:
            # A small randomized kick explores a nearby representative of the
            # same logical coset without making the search exhaustive.
            cur ^= random_stabilizer(rng, rows, 4)
    return best


def bits_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def search_basis(label, kernel_rows, stabilizer_rows, n, rng, deadline):
    stab_basis = rref_basis(stabilizer_rows, n)
    k_basis = nullspace_basis(kernel_rows, n)
    logicals = quotient_generators(k_basis, stab_basis)
    if not logicals:
        return None

    sparse_stabs = sorted([r for r in stabilizer_rows if r], key=lambda x: x.bit_count())
    best = None

    seed_candidates = list(logicals[: min(len(logicals), 64)])
    for v in seed_candidates:
        cand = reduce_weight_by_stabilizers(v, sparse_stabs, rng, 4)
        if not in_rowspace(cand, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    max_attempts = min(2500, max(250, 20 * n + 40 * len(logicals)))
    for attempts in range(1, max_attempts + 1):
        if time.monotonic() >= deadline:
            break
        v = 0
        if len(logicals) == 1:
            v = logicals[0]
        else:
            sample_size = rng.randint(1, min(len(logicals), 12))
            for idx in rng.sample(range(len(logicals)), sample_size):
                if rng.getrandbits(1):
                    v ^= logicals[idx]
            if v == 0:
                v = rng.choice(logicals)

        if sparse_stabs and rng.random() < 0.75:
            v ^= random_stabilizer(rng, sparse_stabs, 8)

        rounds = 2 + (attempts % 5)
        cand = reduce_weight_by_stabilizers(v, sparse_stabs, rng, rounds)
        if cand and not in_rowspace(cand, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    if best is None:
        return None

    if kernel_contains(kernel_rows, best) and not in_rowspace(best, stab_basis):
        return {
            "basis": label,
            "vector": bits_to_list(best, n),
            "upper_bound": best.bit_count(),
        }
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    rng = random.Random(args.seed)

    try:
        hx_rows, nx = load_matrix(args.hx)
        hz_rows, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("hx and hz must have the same number of columns")

        n = nx
        # X logicals are in ker(Hz) modulo row(Hx); Z logicals are in ker(Hx)
        # modulo row(Hz). Search both and keep the lighter verified witness.
        deadline = time.monotonic() + 2.5
        results = []
        half_deadline = time.monotonic() + 1.25
        x_result = search_basis("x", hz_rows, hx_rows, n, rng, half_deadline)
        if x_result is not None:
            results.append(x_result)
        z_result = search_basis("z", hx_rows, hz_rows, n, rng, deadline)
        if z_result is not None:
            results.append(z_result)

        if results:
            result = min(results, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
            status = "completed"
        else:
            result = {"basis": "x", "vector": [0] * n, "upper_bound": 0}
            status = "not_found"

        print(json.dumps({
            "status": status,
            "basis": result["basis"],
            "vector": result["vector"],
            "upper_bound": result["upper_bound"],
        }, separators=(",", ":")))
    except Exception:
        print(json.dumps({
            "status": "error",
            "basis": "x",
            "vector": [],
            "upper_bound": 0,
        }, separators=(",", ":")))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
