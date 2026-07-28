#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        rows = obj
        n_cols = max((len(r) for r in rows), default=0)
        return rows_to_bits(rows, n_cols), n_cols

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_cols = int(obj.get("n_cols", 0))
        data = obj.get("data", [])
        return rows_to_bits(data, n_cols), n_cols

    if "rows" in obj:
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        bits = []
        for row in obj.get("rows", []):
            x = 0
            last = -1
            for c in row:
                c = int(c)
                if c <= last or c < 0 or c >= n_cols:
                    raise ValueError(f"invalid sparse row in {path}")
                x |= 1 << c
                last = c
            bits.append(x)
        return bits, n_cols

    raise ValueError(f"unrecognized matrix JSON format: {path}")


def rows_to_bits(rows, n_cols):
    bits = []
    for row in rows:
        if len(row) != n_cols:
            raise ValueError("dense row length does not match n_cols")
        x = 0
        for i, v in enumerate(row):
            if int(v) & 1:
                x |= 1 << i
        bits.append(x)
    return bits


def rank_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        for q in sorted(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= basis[p]
    return basis


def reduce_with_basis(x, basis):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(x, rows):
    return reduce_with_basis(x, rank_basis(rows)) == 0


def kernel_basis(rows, n_cols):
    rb = rank_basis(rows)
    pivots = set(rb)
    out = []
    for f in range(n_cols):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def commutes(v, checks):
    return all(((v & row).bit_count() & 1) == 0 for row in checks)


def verified(v, checks, stabilizers):
    return v != 0 and commutes(v, checks) and not in_rowspace(v, stabilizers)


def bits_to_list(v, n_cols):
    return [(v >> i) & 1 for i in range(n_cols)]


def random_combo(items, rng, max_terms):
    if not items:
        return 0
    terms = rng.randint(1, max(1, min(max_terms, len(items))))
    v = 0
    for i in rng.sample(range(len(items)), terms):
        v ^= items[i]
    return v


def improve_by_stabilizers(v, stabilizers, rng, deadline):
    if not stabilizers:
        return v

    current = v
    current_w = current.bit_count()
    ordered = list(stabilizers)

    changed = True
    passes = 0
    while changed and passes < 4 and time.monotonic() < deadline:
        changed = False
        passes += 1
        rng.shuffle(ordered)
        for row in ordered:
            trial = current ^ row
            tw = trial.bit_count()
            if tw < current_w:
                current, current_w = trial, tw
                changed = True

    limit = min(2500, 120 + 20 * len(stabilizers))
    for _ in range(limit):
        if time.monotonic() >= deadline:
            break
        trial = current ^ random_combo(ordered, rng, max_terms=8)
        tw = trial.bit_count()
        if tw <= current_w:
            current, current_w = trial, tw
    return current


def seed_witnesses(kernel, checks, stabilizers, rng, deadline):
    stab_basis = rank_basis(stabilizers)
    seeds = []

    shuffled = list(kernel)
    rng.shuffle(shuffled)
    for v in shuffled[: min(len(shuffled), 256)]:
        if v and commutes(v, checks) and reduce_with_basis(v, stab_basis) != 0:
            seeds.append(v)

    attempts = min(5000, max(200, 80 * max(1, len(kernel))))
    for _ in range(attempts):
        if time.monotonic() >= deadline:
            break
        v = random_combo(kernel, rng, max_terms=18)
        if v and reduce_with_basis(v, stab_basis) != 0:
            seeds.append(v)
            if len(seeds) >= 96:
                break
    return seeds


def search_basis(name, checks, stabilizers, n_cols, rng, seconds):
    deadline = time.monotonic() + seconds
    kernel = kernel_basis(checks, n_cols)
    if not kernel:
        return None

    best = None
    best_w = n_cols + 1
    for seed in seed_witnesses(kernel, checks, stabilizers, rng, deadline):
        if time.monotonic() >= deadline:
            break
        v = improve_by_stabilizers(seed, stabilizers, rng, deadline)
        if verified(v, checks, stabilizers):
            w = v.bit_count()
            if w < best_w:
                best, best_w = v, w

    if best is None:
        return None
    return {"basis": name, "vector": bits_to_list(best, n_cols), "upper_bound": best_w}


def emit(obj):
    print(json.dumps(obj, separators=(",", ":")), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different numbers of columns")

        rng = random.Random(args.seed)
        bases = [("x", hz, hx), ("z", hx, hz)]
        rng.shuffle(bases)

        results = []
        for name, checks, stabilizers in bases:
            found = search_basis(name, checks, stabilizers, nx, rng, seconds=6.0)
            if found is not None:
                results.append(found)

        if results:
            best = min(results, key=lambda r: r["upper_bound"])
            emit(
                {
                    "status": "completed",
                    "basis": best["basis"],
                    "vector": best["vector"],
                    "upper_bound": best["upper_bound"],
                }
            )
        else:
            emit({"status": "not_found", "basis": None, "vector": [], "upper_bound": None})
    except Exception as exc:
        print(f"candidate error: {exc}", file=sys.stderr)
        emit({"status": "error", "basis": None, "vector": [], "upper_bound": None})


if __name__ == "__main__":
    main()
