#!/usr/bin/env python3
import argparse
import json
import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            v = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    v |= 1 << i
            rows.append(v)
        return rows, n_cols

    if isinstance(obj, dict) and "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            v = 0
            prev = -1
            for col in row:
                c = int(col)
                if c <= prev or c < 0 or c >= n_cols:
                    raise ValueError(f"invalid sparse row in {path}")
                v |= 1 << c
                prev = c
            rows.append(v)
        return rows, n_cols

    raise ValueError(f"unsupported matrix JSON format: {path}")


def parity(x: int) -> int:
    return x.bit_count() & 1


def in_kernel(v: int, checks: Sequence[int]) -> bool:
    return all(parity(v & row) == 0 for row in checks)


def rref(rows: Iterable[int], n_cols: int) -> Tuple[List[int], List[int]]:
    mat = [r & ((1 << n_cols) - 1) for r in rows if r]
    pivot_cols: List[int] = []
    rank = 0
    for col in range(n_cols):
        pivot = None
        bit = 1 << col
        for i in range(rank, len(mat)):
            if mat[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        mat[rank], mat[pivot] = mat[pivot], mat[rank]
        prow = mat[rank]
        for i in range(len(mat)):
            if i != rank and (mat[i] & bit):
                mat[i] ^= prow
        pivot_cols.append(col)
        rank += 1
        if rank == len(mat):
            break
    return mat[:rank], pivot_cols


def kernel_basis(rows: Sequence[int], n_cols: int) -> List[int]:
    rr, pivots = rref(rows, n_cols)
    pivot_set = set(pivots)
    basis = []
    for free_col in range(n_cols):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        fbit = 1 << free_col
        for row, pivot_col in zip(rr, pivots):
            if row & fbit:
                v |= 1 << pivot_col
        basis.append(v)
    return basis


def reduce_by_basis(v: int, basis: Dict[int, int]) -> int:
    while v:
        p = v.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return v
        v ^= b
    return 0


def add_to_basis(v: int, basis: Dict[int, int]) -> bool:
    v = reduce_by_basis(v, basis)
    if not v:
        return False
    basis[v.bit_length() - 1] = v
    return True


def rowspace_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for row in rows:
        add_to_basis(row, basis)
    return basis


def in_rowspace(v: int, basis: Dict[int, int]) -> bool:
    return reduce_by_basis(v, basis) == 0


def xor_random_combo(rng: random.Random, vecs: Sequence[int], p: float) -> int:
    v = 0
    for row in vecs:
        if rng.random() < p:
            v ^= row
    return v


def greedy_reduce(v: int, rows: Sequence[int], rng: random.Random, rounds: int) -> int:
    if not rows:
        return v
    current = v
    current_w = current.bit_count()
    order = list(rows)
    for _ in range(rounds):
        rng.shuffle(order)
        changed = False
        for row in order:
            cand = current ^ row
            cand_w = cand.bit_count()
            if cand_w < current_w or (cand_w == current_w and rng.random() < 0.02):
                current = cand
                current_w = cand_w
                changed = True
        if not changed:
            break
    return current


def logical_seed_basis(kernel: Sequence[int], stabilizers: Dict[int, int], rng: random.Random) -> List[int]:
    augmented = dict(stabilizers)
    seeds: List[int] = []
    order = list(kernel)
    rng.shuffle(order)
    for v in order:
        if reduce_by_basis(v, augmented):
            seeds.append(v)
            add_to_basis(v, augmented)
    return seeds


def search_basis(
    checks: Sequence[int],
    stabilizer_rows: Sequence[int],
    n_cols: int,
    rng: random.Random,
) -> Optional[int]:
    kernel = kernel_basis(checks, n_cols)
    stabilizers = rowspace_basis(stabilizer_rows)
    seeds = logical_seed_basis(kernel, stabilizers, rng)
    if not seeds:
        return None

    safe_stabilizers = [row for row in stabilizer_rows if row and in_kernel(row, checks)]
    safe_stabilizers.sort(key=lambda x: x.bit_count())
    if len(safe_stabilizers) > 4096:
        safe_stabilizers = safe_stabilizers[:2048] + rng.sample(safe_stabilizers[2048:], 2048)

    candidates: List[int] = list(seeds)
    sparse_kernel = sorted(kernel, key=lambda x: x.bit_count())[: min(len(kernel), 256)]
    candidates.extend(sparse_kernel)

    best: Optional[int] = None
    attempts = max(300, min(6000, 80 * (len(seeds) + 1) + 8 * n_cols))
    for t in range(attempts):
        if t < len(candidates):
            v = candidates[t]
        elif t & 1:
            p = rng.uniform(0.08, 0.5)
            v = xor_random_combo(rng, seeds, p)
        else:
            p = rng.uniform(0.03, 0.22)
            v = xor_random_combo(rng, kernel, p)

        if not v:
            continue
        if safe_stabilizers:
            rounds = 2 + (t % 5)
            v = greedy_reduce(v, safe_stabilizers, rng, rounds)
        if not v or in_rowspace(v, stabilizers) or not in_kernel(v, checks):
            continue
        if best is None or v.bit_count() < best.bit_count():
            best = v

    if best is None:
        for seed in seeds:
            if seed and not in_rowspace(seed, stabilizers) and in_kernel(seed, checks):
                best = seed if best is None or seed.bit_count() < best.bit_count() else best
    return best


def vector_to_list(v: int, n_cols: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n_cols)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("Hx and Hz must have the same number of columns")

    rng = random.Random(args.seed)
    searches = [("x", hz, hx), ("z", hx, hz)]
    rng.shuffle(searches)

    best_basis: Optional[str] = None
    best_vec: Optional[int] = None
    for basis, checks, stabilizers in searches:
        v = search_basis(checks, stabilizers, nx, rng)
        if v is None:
            continue
        if best_vec is None or v.bit_count() < best_vec.bit_count():
            best_basis = basis
            best_vec = v

    if best_basis is None or best_vec is None:
        result = {"status": "not_found", "basis": None, "vector": None, "upper_bound": None}
    else:
        result = {
            "status": "completed",
            "basis": best_basis,
            "vector": vector_to_list(best_vec, nx),
            "upper_bound": best_vec.bit_count(),
        }
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
