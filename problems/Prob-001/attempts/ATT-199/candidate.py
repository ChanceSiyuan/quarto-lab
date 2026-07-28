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
        rows = []
        for row in obj["data"]:
            bits = 0
            for i, value in enumerate(row):
                if value & 1:
                    bits |= 1 << i
            rows.append(bits)
        return rows, int(obj["n_cols"])
    if "num_cols" in obj and "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("invalid sparse row")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return rows, n_cols
    raise ValueError("unrecognized matrix JSON format")


def rank_basis(rows):
    basis = {}
    for value in rows:
        x = int(value)
        while x:
            pivot = x.bit_length() - 1
            if pivot in basis:
                x ^= basis[pivot]
            else:
                basis[pivot] = x
                break
    return basis


def in_rowspace(value, basis):
    x = int(value)
    while x:
        pivot = x.bit_length() - 1
        row = basis.get(pivot)
        if row is None:
            return False
        x ^= row
    return True


def kernel_basis(rows, n_cols):
    pivot_rows = {}
    pivot_cols = []
    for value in rows:
        x = int(value)
        while x:
            pivot = x.bit_length() - 1
            if pivot in pivot_rows:
                x ^= pivot_rows[pivot]
            else:
                pivot_rows[pivot] = x
                pivot_cols.append(pivot)
                break
    for pivot in sorted(pivot_rows):
        row = pivot_rows[pivot]
        for other in list(pivot_rows):
            if other > pivot and ((pivot_rows[other] >> pivot) & 1):
                pivot_rows[other] ^= row
    pivot_set = set(pivot_cols)
    out = []
    for free in range(n_cols):
        if free in pivot_set:
            continue
        vec = 1 << free
        for pivot, row in pivot_rows.items():
            if (row >> free) & 1:
                vec |= 1 << pivot
        out.append(vec)
    return out


def syndrome_zero(vec, checks):
    return all(((row & vec).bit_count() & 1) == 0 for row in checks)


def verified(vec, checks, stabilizer_basis):
    return vec != 0 and syndrome_zero(vec, checks) and not in_rowspace(vec, stabilizer_basis)


def to_list(vec, n_cols):
    return [(vec >> i) & 1 for i in range(n_cols)]


def random_combo(rng, basis, max_terms=None):
    if not basis:
        return 0
    if max_terms is None:
        x = 0
        for row in basis:
            if rng.getrandbits(1):
                x ^= row
        return x
    x = 0
    terms = rng.randint(1, min(max_terms, len(basis)))
    for idx in rng.sample(range(len(basis)), terms):
        x ^= basis[idx]
    return x


def improve(vec, null_moves, checks, stabilizer_basis, rng, deadline):
    if not verified(vec, checks, stabilizer_basis):
        return None
    current = vec
    current_w = vec.bit_count()
    temperature = 1.0
    rounds = 0
    while time.time() < deadline and rounds < 600:
        rounds += 1
        improved = False
        moves = rng.sample(null_moves, min(len(null_moves), 80)) if len(null_moves) > 80 else list(null_moves)
        rng.shuffle(moves)
        for move in moves:
            cand = current ^ move
            if cand == 0 or in_rowspace(cand, stabilizer_basis):
                continue
            weight = cand.bit_count()
            if weight < current_w or (weight == current_w and rng.random() < 0.08):
                current = cand
                current_w = weight
                improved = True
                break
            if weight > current_w and rng.random() < temperature / (60.0 + 12.0 * (weight - current_w)):
                current = cand
                current_w = weight
                improved = True
                break
        temperature *= 0.985
        if not improved and temperature < 0.02:
            break
    return current


def search_basis(name, checks, stabilizers, n_cols, rng, deadline):
    stabilizer_basis = rank_basis(stabilizers)
    null = kernel_basis(checks, n_cols)
    if not null:
        return None
    best = None
    candidates = []
    ordered = sorted(null, key=lambda x: x.bit_count())
    candidates.extend(ordered[:64])
    for i in range(min(len(ordered), 32)):
        for j in range(i + 1, min(len(ordered), i + 9, len(ordered))):
            candidates.append(ordered[i] ^ ordered[j])
    attempts = 0
    since_best = 0
    while time.time() < deadline:
        attempts += 1
        since_best += 1
        if best is not None and since_best > 180 and not candidates:
            break
        if candidates:
            cand = candidates.pop(0)
        elif attempts % 4:
            cand = random_combo(rng, null, max_terms=min(10, len(null)))
        else:
            cand = random_combo(rng, null)
        if not verified(cand, checks, stabilizer_basis):
            continue
        cand = improve(cand, null, checks, stabilizer_basis, rng, deadline) or cand
        if verified(cand, checks, stabilizer_basis) and (best is None or cand.bit_count() < best.bit_count()):
            best = cand
            since_best = 0
            if best.bit_count() <= 1:
                break
            if best.bit_count() <= 2 and not candidates:
                break
    if best is None:
        return None
    return {"basis": name, "vector": to_list(best, n_cols), "upper_bound": best.bit_count()}


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
            raise ValueError("Hx and Hz must have the same number of columns")
        os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)
        deadline = time.time() + float(os.environ.get("CANDIDATE_TIME_LIMIT", "2.0"))
        split = time.time() + 0.5 * (deadline - time.time())
        found = []
        x_result = search_basis("x", hz, hx, nx, rng, split)
        if x_result is not None:
            found.append(x_result)
        z_result = search_basis("z", hx, hz, nx, rng, deadline)
        if z_result is not None:
            found.append(z_result)
        if found:
            result = min(found, key=lambda item: item["upper_bound"])
            result = {
                "status": "completed",
                "basis": result["basis"],
                "vector": result["vector"],
                "upper_bound": result["upper_bound"],
            }
        else:
            result = {"status": "not_found", "basis": None, "vector": None, "upper_bound": None}
    except Exception:
        result = {"status": "error", "basis": None, "vector": None, "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
