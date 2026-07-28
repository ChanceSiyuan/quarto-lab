#!/usr/bin/env python3
import argparse
import json
import random
import sys
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
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for inds in obj["rows"]:
            x = 0
            last = -1
            for i in inds:
                i = int(i)
                if i <= last or i < 0 or i >= n:
                    raise ValueError("invalid sparse row")
                x |= 1 << i
                last = i
            rows.append(x)
        return rows, n

    raise ValueError("unrecognized matrix JSON format")


def row_basis(rows):
    basis = {}
    for r in rows:
        x = int(r)
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def in_span(x, basis):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        x ^= b
    return True


def rref_rows(rows, n):
    rows = [int(r) for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        pivot = None
        for j in range(rank, len(rows)):
            if (rows[j] >> col) & 1:
                pivot = j
                break
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for j in range(len(rows)):
            if j != rank and ((rows[j] >> col) & 1):
                rows[j] ^= rows[rank]
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return rows[:rank], pivots


def kernel_basis(rows, n):
    rref, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    out = []
    for f in free_cols:
        x = 1 << f
        for row, p in zip(rref, pivots):
            if (row >> f) & 1:
                x |= 1 << p
        out.append(x)
    return out


def syndrome_zero(v, checks):
    for r in checks:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def bits_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def random_combo(vecs, rng, limit=None):
    if not vecs:
        return 0
    if limit is None or limit >= len(vecs):
        x = 0
        for v in vecs:
            if rng.getrandbits(1):
                x ^= v
        return x
    x = 0
    for i in rng.sample(range(len(vecs)), limit):
        x ^= vecs[i]
    return x


def reduce_by_stabilizers(v, stabilizers, rng, deadline):
    best = v
    best_w = best.bit_count()
    if best_w == 0 or not stabilizers:
        return best

    ordered = list(stabilizers)
    improved = True
    while improved and time.monotonic() < deadline:
        improved = False
        rng.shuffle(ordered)
        for s in ordered:
            w = (best ^ s).bit_count()
            if w < best_w:
                best ^= s
                best_w = w
                improved = True
                if best_w <= 1:
                    return best

    temp = best
    temp_w = best_w
    rounds = min(2500, 80 * max(1, len(stabilizers)))
    heat = 3
    for _ in range(rounds):
        if time.monotonic() >= deadline:
            break
        s = ordered[rng.randrange(len(ordered))]
        cand = temp ^ s
        cw = cand.bit_count()
        if cw <= temp_w or rng.randrange(100) < heat:
            temp, temp_w = cand, cw
            if cw < best_w:
                best, best_w = cand, cw
                heat = 3
        elif heat > 0:
            heat -= 1
    return best


def verified(v, commute_checks, stabilizer_basis):
    return v != 0 and syndrome_zero(v, commute_checks) and not in_span(v, stabilizer_basis)


def search_basis(name, commute_checks, stabilizers, n, rng, deadline):
    stab_basis = row_basis(stabilizers)
    kern = kernel_basis(commute_checks, n)
    logical_basis = [v for v in kern if not in_span(v, stab_basis)]
    if not logical_basis:
        return None

    candidates = sorted(logical_basis, key=int.bit_count)[: min(len(logical_basis), 96)]
    best = None
    best_w = n + 1

    def consider(v):
        nonlocal best, best_w
        if not verified(v, commute_checks, stab_basis):
            return
        w = v.bit_count()
        if w < best_w:
            best, best_w = v, w

    for v in candidates:
        if time.monotonic() >= deadline:
            break
        consider(reduce_by_stabilizers(v, stabilizers, rng, deadline))

    attempts = 0
    max_attempts = max(200, min(20000, 80 * max(1, len(kern)) + 25 * max(1, n)))
    while attempts < max_attempts and time.monotonic() < deadline:
        attempts += 1
        if attempts % 3 == 0 and logical_basis:
            v = random_combo(logical_basis, rng, limit=rng.randint(1, min(12, len(logical_basis))))
        else:
            v = random_combo(kern, rng, limit=None if len(kern) < 64 else rng.randint(1, 32))
        if in_span(v, stab_basis):
            continue
        v = reduce_by_stabilizers(v, stabilizers, rng, deadline)
        consider(v)
        if best_w <= 1:
            break

    if best is None:
        return None
    return {"basis": name, "vector": bits_to_list(best, n), "upper_bound": best_w}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("Hx and Hz have different column counts")
    n = nx

    rng = random.Random(args.seed)
    deadline = time.monotonic() + 8.0
    first = "x" if rng.getrandbits(1) else "z"
    order = [first, "z" if first == "x" else "x"]
    results = []
    for basis_name in order:
        if basis_name == "x":
            res = search_basis("x", hz, hx, n, rng, deadline)
        else:
            res = search_basis("z", hx, hz, n, rng, deadline)
        if res is not None:
            results.append(res)

    if results:
        result = min(results, key=lambda r: r["upper_bound"])
        out = {
            "status": "completed",
            "basis": result["basis"],
            "vector": result["vector"],
            "upper_bound": result["upper_bound"],
        }
    else:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))
