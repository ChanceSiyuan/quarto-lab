#!/usr/bin/env python3
"""Randomized CSS logical witness upper-bound search.

The search samples non-stabilizer kernel cosets and heuristically reduces
weight by adding stabilizer generators. It certifies only the returned witness,
not the minimum distance.
"""

import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


Rows = List[int]


def emit(status: str, basis: str, vector: Sequence[int], upper_bound) -> None:
    print(
        json.dumps(
            {
                "status": status,
                "basis": basis,
                "vector": list(vector),
                "upper_bound": upper_bound,
            },
            separators=(",", ":"),
        )
    )


def row_from_bits(bits: Sequence[int]) -> int:
    value = 0
    for i, bit in enumerate(bits):
        if bit:
            value |= 1 << i
    return value


def load_matrix(path: str) -> Tuple[Rows, int]:
    with open(path, "r", encoding="utf-8") as handle:
        obj = json.load(handle)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= obj.keys():
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError("dense row has wrong length")
            rows.append(row_from_bits([int(x) & 1 for x in row]))
        if len(rows) != int(obj["n_rows"]):
            raise ValueError("dense row count mismatch")
        return rows, n_cols

    if {"num_cols", "rows"} <= obj.keys():
        n_cols = int(obj["num_cols"])
        rows = []
        for sparse in obj["rows"]:
            last = -1
            value = 0
            for col in sparse:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("sparse row indices must be increasing")
                value |= 1 << col
                last = col
            rows.append(value)
        return rows, n_cols

    raise ValueError("unrecognized matrix JSON format")


def reduce_with_basis(row: int, basis: Dict[int, int]) -> int:
    while row:
        pivot = row.bit_length() - 1
        reducer = basis.get(pivot)
        if reducer is None:
            return row
        row ^= reducer
    return 0


def insert_high_basis(row: int, basis: Dict[int, int]) -> bool:
    row = reduce_with_basis(row, basis)
    if row == 0:
        return False
    basis[row.bit_length() - 1] = row
    return True


def make_high_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for row in rows:
        if row:
            insert_high_basis(row, basis)
    return basis


def in_rowspace(row: int, space_basis: Dict[int, int]) -> bool:
    return reduce_with_basis(row, space_basis) == 0


def rref_rows(rows: Sequence[int], n_cols: int) -> Tuple[Rows, List[int]]:
    mat = [row for row in rows if row]
    pivot_cols: List[int] = []
    r = 0
    for col in range(n_cols):
        bit = 1 << col
        found = None
        for i in range(r, len(mat)):
            if mat[i] & bit:
                found = i
                break
        if found is None:
            continue
        mat[r], mat[found] = mat[found], mat[r]
        for i in range(len(mat)):
            if i != r and (mat[i] & bit):
                mat[i] ^= mat[r]
        pivot_cols.append(col)
        r += 1
        if r == len(mat):
            break
    return mat[:r], pivot_cols


def kernel_basis(check_rows: Sequence[int], n_cols: int) -> Rows:
    piv_rows, piv_cols = rref_rows(check_rows, n_cols)
    piv_set = set(piv_cols)
    basis = []
    for free_col in range(n_cols):
        if free_col in piv_set:
            continue
        vec = 1 << free_col
        free_bit = 1 << free_col
        for row, pivot_col in zip(piv_rows, piv_cols):
            if row & free_bit:
                vec |= 1 << pivot_col
        basis.append(vec)
    return basis


def syndrome_zero(vec: int, checks: Sequence[int]) -> bool:
    return all(((vec & row).bit_count() & 1) == 0 for row in checks)


def bits_to_list(vec: int, n_cols: int) -> List[int]:
    return [(vec >> i) & 1 for i in range(n_cols)]


def quotient_representatives(
    ker_basis: Sequence[int], stabilizers: Sequence[int], rng: random.Random
) -> Rows:
    current = make_high_basis(stabilizers)
    reps = []
    shuffled = list(ker_basis)
    rng.shuffle(shuffled)
    for vec in shuffled:
        trial = reduce_with_basis(vec, current)
        if trial:
            insert_high_basis(trial, current)
            reps.append(trial)
    return reps


def random_xor(rows: Sequence[int], rng: random.Random, force_nonempty: bool) -> int:
    if not rows:
        return 0
    value = 0
    used = False
    for row in rows:
        if rng.getrandbits(1):
            value ^= row
            used = True
    if force_nonempty and not used:
        value = rows[rng.randrange(len(rows))]
    return value


def greedy_descent(vec: int, stabilizers: Sequence[int], rng: random.Random) -> int:
    rows = [row for row in stabilizers if row]
    if not rows:
        return vec
    current = vec
    current_w = current.bit_count()
    # Alternate structured and shuffled passes. This is a heuristic coset
    # descent, not enumeration of the coset.
    ordered = sorted(rows, key=int.bit_count)
    for pass_idx in range(10):
        changed = False
        scan = ordered[:] if pass_idx % 2 == 0 else rows[:]
        if pass_idx % 2:
            rng.shuffle(scan)
        for row in scan:
            nxt = current ^ row
            nxt_w = nxt.bit_count()
            if nxt_w < current_w:
                current = nxt
                current_w = nxt_w
                changed = True
        if not changed:
            break
    return current


def perturb_and_descend(
    vec: int, stabilizers: Sequence[int], rng: random.Random, trials: int
) -> int:
    best = greedy_descent(vec, stabilizers, rng)
    best_w = best.bit_count()
    if not stabilizers:
        return best
    for _ in range(trials):
        trial = best
        flips = 1 + rng.randrange(min(8, max(1, len(stabilizers))))
        for _ in range(flips):
            trial ^= stabilizers[rng.randrange(len(stabilizers))]
        trial = greedy_descent(trial, stabilizers, rng)
        trial_w = trial.bit_count()
        if 0 < trial_w < best_w:
            best = trial
            best_w = trial_w
    return best


def verify(vec: int, basis: str, hx: Sequence[int], hz: Sequence[int]) -> bool:
    if vec == 0:
        return False
    if basis == "x":
        return syndrome_zero(vec, hz) and not in_rowspace(vec, make_high_basis(hx))
    return syndrome_zero(vec, hx) and not in_rowspace(vec, make_high_basis(hz))


def search_basis(
    label: str,
    kernel_checks: Sequence[int],
    stabilizers: Sequence[int],
    n_cols: int,
    seed: int,
) -> Optional[int]:
    rng = random.Random((seed << 8) ^ (17 if label == "x" else 91))
    ker = kernel_basis(kernel_checks, n_cols)
    reps = quotient_representatives(ker, stabilizers, rng)
    if not reps:
        return None

    best: Optional[int] = None
    best_w = n_cols + 1
    rounds = max(96, min(768, 32 * len(reps) + 4 * len(stabilizers)))
    stab_trials = max(8, min(96, len(stabilizers) // 2 + 8))

    candidates: Rows = list(reps)
    for rep in reps[: min(len(reps), 32)]:
        candidates.append(rep ^ random_xor(stabilizers, rng, force_nonempty=False))

    for idx in range(rounds):
        if idx < len(candidates):
            vec = candidates[idx]
        else:
            vec = random_xor(reps, rng, force_nonempty=True)
            if stabilizers and rng.random() < 0.75:
                vec ^= random_xor(stabilizers, rng, force_nonempty=False)
        vec = perturb_and_descend(vec, stabilizers, rng, stab_trials)
        weight = vec.bit_count()
        if 0 < weight < best_w:
            best = vec
            best_w = weight
            if best_w == 1:
                break
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz must have the same number of columns")
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        found = []
        x_vec = search_basis("x", hz, hx, nx, args.seed)
        if x_vec is not None and verify(x_vec, "x", hx, hz):
            found.append(("x", x_vec))
        z_vec = search_basis("z", hx, hz, nx, args.seed)
        if z_vec is not None and verify(z_vec, "z", hx, hz):
            found.append(("z", z_vec))

        if not found:
            emit("not_found", "x", [], None)
            return 0

        label, vec = min(found, key=lambda item: (item[1].bit_count(), item[0]))
        emit("completed", label, bits_to_list(vec, nx), vec.bit_count())
        return 0
    except Exception:
        emit("error", "x", [], None)
        return 0


if __name__ == "__main__":
    sys.exit(main())
