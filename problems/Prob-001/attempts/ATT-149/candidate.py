#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        rows = []
        n_cols = 0
        for row in obj:
            bits = 0
            n_cols = max(n_cols, len(row))
            for j, val in enumerate(row):
                if int(val) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n_cols

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            for j, val in enumerate(row):
                if int(val) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n_cols

    if "num_cols" in obj and "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last:
                    raise ValueError("sparse row indices must be strictly increasing")
                if col < 0 or col >= n_cols:
                    raise ValueError("sparse row index out of bounds")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unrecognized matrix JSON format")


class RowSpace:
    def __init__(self, rows):
        self.basis = {}
        for row in rows:
            self.add(row)

    def add(self, value):
        x = value
        while x:
            lead = x.bit_length() - 1
            row = self.basis.get(lead)
            if row is None:
                self.basis[lead] = x
                return True
            x ^= row
        return False

    def reduce(self, value):
        x = value
        while x:
            lead = x.bit_length() - 1
            row = self.basis.get(lead)
            if row is None:
                return x
            x ^= row
        return 0

    def contains(self, value):
        return self.reduce(value) == 0


def kernel_basis(rows, n_cols):
    basis = {}
    for row in rows:
        x = row
        while x:
            lead = x.bit_length() - 1
            pivot = basis.get(lead)
            if pivot is None:
                basis[lead] = x
                break
            x ^= pivot

    pivots = set(basis)
    free_cols = [c for c in range(n_cols) if c not in pivots]
    out = []
    for free in free_cols:
        v = 1 << free
        for pivot_col in sorted(pivots):
            pivot_row = basis[pivot_col]
            rest = pivot_row & ~(1 << pivot_col)
            if (rest & v).bit_count() & 1:
                v |= 1 << pivot_col
        out.append(v)
    return out


def syndrome_zero(vector, checks):
    for row in checks:
        if (vector & row).bit_count() & 1:
            return False
    return True


def as_binary_list(vector, n_cols):
    return [(vector >> i) & 1 for i in range(n_cols)]


def randomized_kernel_mix(rng, kernel, ordered_kernel):
    if not kernel:
        return 0
    v = 0
    mode = rng.randrange(5)
    if mode == 0:
        limit = min(len(ordered_kernel), max(1, 16 + rng.randrange(48)))
        pool = ordered_kernel[:limit]
        take = 1 + rng.randrange(min(8, len(pool)))
        for row in rng.sample(pool, take):
            v ^= row
    elif mode == 1:
        take = 1 + rng.randrange(min(24, len(kernel)))
        for row in rng.sample(kernel, take):
            v ^= row
    else:
        p = min(0.5, max(0.02, 3.0 / max(1, len(kernel))))
        for row in kernel:
            if rng.random() < p:
                v ^= row
        if v == 0:
            v = rng.choice(kernel)
    return v


def stabilizer_descent(rng, start, stabilizers, seconds_limit, round_limit):
    if not stabilizers:
        return start

    rows = [r for r in stabilizers if r]
    if not rows:
        return start
    rows_by_weight = sorted(rows, key=int.bit_count)

    best = start
    current = start
    best_w = start.bit_count()
    current_w = best_w
    temperature = 1.5
    deadline = time.monotonic() + seconds_limit

    for round_no in range(round_limit):
        if time.monotonic() >= deadline:
            break

        if round_no % 7 == 0:
            scan = rows_by_weight[: min(len(rows_by_weight), 256)]
            if len(rows_by_weight) > len(scan):
                scan += rng.sample(rows_by_weight[len(scan):], min(256, len(rows_by_weight) - len(scan)))
        else:
            scan = rng.sample(rows, min(len(rows), 384))

        improved = False
        for row in scan:
            trial = current ^ row
            tw = trial.bit_count()
            delta = tw - current_w
            accept = delta <= 0 or rng.random() < temperature / (temperature + 16.0 + max(0, delta) ** 2)
            if accept:
                current = trial
                current_w = tw
                if tw < best_w:
                    best = trial
                    best_w = tw
                    improved = True

        if not improved and round_no % 9 == 8:
            current = best
            current_w = best_w
            for row in rng.sample(rows_by_weight, min(len(rows_by_weight), 12)):
                if rng.random() < 0.45:
                    current ^= row
            current_w = current.bit_count()
        temperature *= 0.992
        if temperature < 0.03:
            temperature = 0.03

    return best


def find_witness(label, kernel_checks, stabilizer_rows, n_cols, rng, time_budget):
    kernel = kernel_basis(kernel_checks, n_cols)
    if not kernel:
        return None

    stabilizer_space = RowSpace(stabilizer_rows)
    logical_space = RowSpace(stabilizer_rows)
    logical_seeds = []
    for row in kernel:
        if logical_space.add(row):
            if not stabilizer_space.contains(row):
                logical_seeds.append(row)

    ordered_kernel = sorted(kernel, key=int.bit_count)
    candidates = []
    for row in ordered_kernel[: min(len(ordered_kernel), 64)]:
        if row and not stabilizer_space.contains(row):
            candidates.append(row)
    candidates.extend(logical_seeds[:64])

    deadline = time.monotonic() + time_budget
    best = None
    best_w = n_cols + 1
    attempts = 0

    while time.monotonic() < deadline and attempts < 2500:
        attempts += 1
        if candidates and (attempts <= len(candidates) or rng.random() < 0.28):
            start = candidates[(attempts - 1) % len(candidates)]
        else:
            start = randomized_kernel_mix(rng, kernel, ordered_kernel)

        if start == 0 or stabilizer_space.contains(start):
            continue

        remaining = max(0.002, deadline - time.monotonic())
        refined = stabilizer_descent(
            rng,
            start,
            stabilizer_rows,
            min(0.08, remaining),
            32,
        )

        for candidate in (refined, start):
            if candidate == 0:
                continue
            if candidate.bit_count() >= best_w:
                continue
            if not syndrome_zero(candidate, kernel_checks):
                continue
            if stabilizer_space.contains(candidate):
                continue
            best = candidate
            best_w = candidate.bit_count()

    if best is None:
        return None
    return {
        "status": "completed",
        "basis": label,
        "vector": as_binary_list(best, n_cols),
        "upper_bound": best_w,
    }


def failure():
    return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}


def main():
    parser = argparse.ArgumentParser(description="Randomized CSS logical upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n_cols = max(nx, nz)
        mask = (1 << n_cols) - 1
        hx = [row & mask for row in hx]
        hz = [row & mask for row in hz]
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        order = ["x", "z"]
        if rng.randrange(2):
            order.reverse()

        results = []
        per_basis_seconds = 1.25
        for label in order:
            child = random.Random((args.seed << 8) ^ (0x9E3779B9 if label == "x" else 0x85EBCA6B))
            if label == "x":
                res = find_witness("x", hz, hx, n_cols, child, per_basis_seconds)
            else:
                res = find_witness("z", hx, hz, n_cols, child, per_basis_seconds)
            if res is not None:
                results.append(res)

        if results:
            results.sort(key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
            print(json.dumps(results[0], separators=(",", ":")))
        else:
            print(json.dumps(failure(), separators=(",", ":")))
    except Exception:
        print(json.dumps(failure(), separators=(",", ":")))


if __name__ == "__main__":
    main()
