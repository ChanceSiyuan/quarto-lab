#!/usr/bin/env python3
import argparse
import json
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> Tuple[int, List[int]]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"} <= set(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError(f"{path}: dense row has wrong length")
            bits = 0
            for j, val in enumerate(row):
                if val not in (0, 1, False, True):
                    raise ValueError(f"{path}: dense matrix is not binary")
                if int(val):
                    bits |= 1 << j
            rows.append(bits)
        return n_cols, rows

    if {"num_cols", "rows"} <= set(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            bits = 0
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError(f"{path}: sparse row indices are invalid")
                bits |= 1 << col
                last = col
            rows.append(bits)
        return n_cols, rows

    raise ValueError(f"{path}: unsupported matrix JSON format")


def weight(v: int) -> int:
    return v.bit_count()


def mat_vec_zero(rows: Sequence[int], v: int) -> bool:
    return all(((row & v).bit_count() & 1) == 0 for row in rows)


def rref(rows: Iterable[int], n_cols: int, col_order: Optional[Sequence[int]] = None) -> Tuple[List[int], List[int]]:
    work = [int(r) for r in rows if r]
    pivots: List[int] = []
    out: List[int] = []
    order = list(range(n_cols)) if col_order is None else list(col_order)
    rank = 0
    for col in order:
        bit = 1 << col
        pivot = None
        for i in range(rank, len(work)):
            if work[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        prow = work[rank]
        for i in range(len(work)):
            if i != rank and (work[i] & bit):
                work[i] ^= prow
        pivots.append(col)
        rank += 1
        if rank == len(work):
            break
    for i in range(rank):
        out.append(work[i])
    return out, pivots


def in_rowspace(v: int, basis_rows: Sequence[int], pivots: Sequence[int]) -> bool:
    x = int(v)
    for row, col in zip(basis_rows, pivots):
        if (x >> col) & 1:
            x ^= row
    return x == 0


def nullspace_basis(rows: Sequence[int], n_cols: int, rng: Optional[random.Random] = None) -> List[int]:
    order = list(range(n_cols))
    if rng is not None:
        rng.shuffle(order)
    rr, pivots = rref(rows, n_cols, order)
    pivot_set = set(pivots)
    pivot_to_row = dict(zip(pivots, rr))
    basis = []
    for free_col in range(n_cols):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        for pivot_col in pivots:
            if (pivot_to_row[pivot_col] >> free_col) & 1:
                v |= 1 << pivot_col
        basis.append(v)
    return basis


class XorBasis:
    def __init__(self) -> None:
        self.rows: Dict[int, int] = {}

    def reduce(self, v: int) -> int:
        x = int(v)
        while x:
            col = (x & -x).bit_length() - 1
            row = self.rows.get(col)
            if row is None:
                return x
            x ^= row
        return 0

    def add(self, v: int) -> bool:
        x = self.reduce(v)
        if not x:
            return False
        col = (x & -x).bit_length() - 1
        for p, row in list(self.rows.items()):
            if (row >> col) & 1:
                self.rows[p] = row ^ x
        self.rows[col] = x
        return True


def logical_seeds(kernel: Sequence[int], stabilizers: Sequence[int]) -> List[int]:
    span = XorBasis()
    for row in stabilizers:
        span.add(row)
    seeds = []
    for vec in sorted((v for v in kernel if v), key=weight):
        if span.add(vec):
            seeds.append(vec)
    return seeds


def reduce_coset(v: int, reducers: Sequence[int], rng: random.Random) -> int:
    best = int(v)
    best_w = weight(best)
    rows = list(reducers)
    rows.sort(key=weight)

    # Greedy local descent in the stabilizer coset. Row order is occasionally
    # shuffled so repeated starts can land in different local minima.
    for outer in range(5):
        if outer:
            rng.shuffle(rows)
        improved = True
        passes = 0
        while improved and passes < 8:
            improved = False
            passes += 1
            for row in rows:
                cand = best ^ row
                cand_w = weight(cand)
                if cand_w < best_w:
                    best, best_w = cand, cand_w
                    improved = True
    return best


def vector_to_list(v: int, n_cols: int) -> List[int]:
    return [int((v >> j) & 1) for j in range(n_cols)]


def verify_witness(
    v: int,
    check_rows: Sequence[int],
    stab_rr: Sequence[int],
    stab_pivots: Sequence[int],
) -> bool:
    return v != 0 and mat_vec_zero(check_rows, v) and not in_rowspace(v, stab_rr, stab_pivots)


def search_basis(
    name: str,
    n_cols: int,
    check_rows: Sequence[int],
    stab_rows: Sequence[int],
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    stab_rr, stab_pivots = rref(stab_rows, n_cols)
    reducers = sorted(set([r for r in stab_rows if r] + [r for r in stab_rr if r]), key=weight)

    kernels = [nullspace_basis(check_rows, n_cols)]
    for _ in range(3):
        kernels.append(nullspace_basis(check_rows, n_cols, rng))

    best: Optional[int] = None
    best_w: Optional[int] = None

    def consider(v: int) -> None:
        nonlocal best, best_w
        v = reduce_coset(v, reducers, rng) if reducers else v
        if verify_witness(v, check_rows, stab_rr, stab_pivots):
            w = weight(v)
            if best is None or w < best_w:  # type: ignore[operator]
                best, best_w = v, w

    seed_sets = [logical_seeds(kernel, stab_rows) for kernel in kernels]
    all_seeds = sorted(set(v for seeds in seed_sets for v in seeds), key=weight)
    if not all_seeds:
        return None

    for seed in all_seeds[: max(64, min(len(all_seeds), 256))]:
        consider(seed)

    attempts = min(30000, max(3000, 120 * n_cols + 900 * len(all_seeds)))
    stab_sample = reducers[: min(len(reducers), 256)]
    for _ in range(attempts):
        v = 0
        if len(all_seeds) <= 64:
            mask = rng.getrandbits(len(all_seeds))
            if mask == 0:
                mask = 1 << rng.randrange(len(all_seeds))
            j = 0
            while mask:
                if mask & 1:
                    v ^= all_seeds[j]
                mask >>= 1
                j += 1
        else:
            t = 1
            while t < 10 and rng.random() < 0.55:
                t += 1
            for seed in rng.sample(all_seeds, min(t, len(all_seeds))):
                v ^= seed

        if stab_sample:
            flips = rng.randrange(0, min(12, len(stab_sample)) + 1)
            for row in rng.sample(stab_sample, flips):
                v ^= row
        consider(v)

    if best is None:
        return None
    return name, best


def solve(hx_path: str, hz_path: str, seed: int, output_dir: str) -> Dict[str, object]:
    del output_dir
    n_x, hx_rows = load_matrix(hx_path)
    n_z, hz_rows = load_matrix(hz_path)
    if n_x != n_z:
        raise ValueError("Hx and Hz have different column counts")
    n_cols = n_x
    mask = (1 << n_cols) - 1
    hx_rows = [r & mask for r in hx_rows]
    hz_rows = [r & mask for r in hz_rows]

    rng = random.Random(seed)
    jobs = [
        ("x", hz_rows, hx_rows),
        ("z", hx_rows, hz_rows),
    ]
    rng.shuffle(jobs)

    found: List[Tuple[str, int]] = []
    for basis, checks, stabs in jobs:
        result = search_basis(basis, n_cols, checks, stabs, rng)
        if result is not None:
            found.append(result)

    if found:
        basis, vec = min(found, key=lambda item: (weight(item[1]), item[0]))
        return {
            "status": "completed",
            "basis": basis,
            "vector": vector_to_list(vec, n_cols),
            "upper_bound": weight(vec),
        }

    return {"status": "not_found", "basis": None, "vector": [], "upper_bound": None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        result = solve(args.hx, args.hz, args.seed, args.output_dir)
    except Exception:
        result = {"status": "error", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
