#!/usr/bin/env python3
import argparse
import json
import os
import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    rows: List[int] = []
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        for row in obj["data"]:
            bits = 0
            for j, value in enumerate(row):
                if int(value) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        for row in obj["rows"]:
            bits = 0
            last = -1
            for j in row:
                j = int(j)
                if j <= last or j < 0 or j >= n:
                    raise ValueError("invalid sparse row")
                bits |= 1 << j
                last = j
            rows.append(bits)
        return rows, n

    raise ValueError("unrecognized matrix JSON format")


def parity(x: int) -> int:
    return x.bit_count() & 1


def dot_zero(rows: Sequence[int], v: int) -> bool:
    return all(parity(r & v) == 0 for r in rows)


def vector_to_list(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def rref(rows: Iterable[int], n: int) -> Tuple[List[Tuple[int, int]], List[int]]:
    work = [r for r in rows if r]
    out: List[Tuple[int, int]] = []
    rank = 0
    for col in range(n):
        pivot_at = None
        mask = 1 << col
        for i in range(rank, len(work)):
            if work[i] & mask:
                pivot_at = i
                break
        if pivot_at is None:
            continue
        work[rank], work[pivot_at] = work[pivot_at], work[rank]
        prow = work[rank]
        for i in range(len(work)):
            if i != rank and (work[i] & mask):
                work[i] ^= prow
        out.append((col, work[rank]))
        rank += 1
        if rank == len(work):
            break
    pivots = [c for c, _ in out]
    return out, pivots


def row_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for value in rows:
        x = value
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def in_rowspace(basis: Dict[int, int], value: int) -> bool:
    x = value
    while x:
        p = x.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return False
        x ^= row
    return True


def random_kernel_vector(
    rng: random.Random,
    rref_rows: Sequence[Tuple[int, int]],
    pivot_cols: Sequence[int],
    n: int,
    density: float,
) -> int:
    pivot_set = set(pivot_cols)
    v = 0
    for col in range(n):
        if col not in pivot_set and rng.random() < density:
            v |= 1 << col
    for pivot, row in rref_rows:
        if parity((row ^ (1 << pivot)) & v):
            v |= 1 << pivot
        else:
            v &= ~(1 << pivot)
    return v


def column_syndromes(check_rows: Sequence[int], n: int) -> List[int]:
    cols = [0] * n
    for i, row in enumerate(check_rows):
        x = row
        while x:
            bit = x & -x
            cols[bit.bit_length() - 1] |= 1 << i
            x ^= bit
    return cols


def random_walk_kernel(
    rng: random.Random,
    cols: Sequence[int],
    n: int,
    steps: int,
    fanout: int,
) -> int:
    if n == 0:
        return 0
    v = 0
    syndrome = 0
    touched = False
    for _ in range(steps):
        if touched and syndrome == 0:
            return v
        best_col = rng.randrange(n)
        best_score = (syndrome ^ cols[best_col]).bit_count()
        for _ in range(fanout):
            col = rng.randrange(n)
            score = (syndrome ^ cols[col]).bit_count()
            if score < best_score or (score == best_score and rng.randrange(2) == 0):
                best_col, best_score = col, score
        v ^= 1 << best_col
        syndrome ^= cols[best_col]
        touched = True
        if syndrome == 0 and v:
            return v
        if rng.random() < 0.04:
            col = rng.randrange(n)
            v ^= 1 << col
            syndrome ^= cols[col]
    return v if syndrome == 0 else 0


def reduce_by_stabilizers(
    rng: random.Random,
    v: int,
    stabilizers: Sequence[int],
    rounds: int,
) -> int:
    if not v or not stabilizers:
        return v
    rows = [s for s in stabilizers if s]
    current = v
    current_w = current.bit_count()
    ordered = sorted(rows, key=int.bit_count)
    for _ in range(2):
        changed = False
        for row in ordered:
            candidate = current ^ row
            weight = candidate.bit_count()
            if candidate and weight < current_w:
                current, current_w = candidate, weight
                changed = True
        if not changed:
            break
    for _ in range(rounds):
        row = rows[rng.randrange(len(rows))]
        candidate = current ^ row
        weight = candidate.bit_count()
        if candidate and (weight < current_w or (weight == current_w and rng.random() < 0.03)):
            current, current_w = candidate, weight
    return current


def verify(
    v: int,
    n: int,
    kernel_checks: Sequence[int],
    stabilizer_basis: Dict[int, int],
) -> bool:
    if v == 0 or v >= (1 << n):
        return False
    return dot_zero(kernel_checks, v) and not in_rowspace(stabilizer_basis, v)


def search_basis(
    rng: random.Random,
    basis_name: str,
    kernel_checks: Sequence[int],
    stabilizers: Sequence[int],
    n: int,
) -> Optional[Tuple[str, int]]:
    rr, pivots = rref(kernel_checks, n)
    stab_basis = row_basis(stabilizers)
    cols = column_syndromes(kernel_checks, n)
    best: Optional[int] = None

    def consider(v: int) -> None:
        nonlocal best
        if not v:
            return
        v = reduce_by_stabilizers(rng, v, stabilizers, 300)
        if verify(v, n, kernel_checks, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    densities = [0.015, 0.03, 0.06, 0.10, 0.18, 0.30, 0.50]
    for _, row in rr:
        consider(row)
    for row in stabilizers[:64]:
        if row:
            consider(random_kernel_vector(rng, rr, pivots, n, 0.04) ^ row)

    samples = max(700, min(7000, 80 * max(1, n)))
    for i in range(samples):
        if i % 5 == 0:
            v = random_walk_kernel(rng, cols, n, max(16, 2 * n), min(28, max(4, n)))
        else:
            density = densities[rng.randrange(len(densities))]
            if rng.random() < 0.30:
                density = min(0.75, 1.0 / max(1, n) * rng.randrange(1, max(3, min(n, 12))))
            v = random_kernel_vector(rng, rr, pivots, n, density)
        consider(v)
        if best is not None and best.bit_count() <= 2:
            break

    return (basis_name, best) if best is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("hx and hz have different column counts")
    os.makedirs(args.output_dir, exist_ok=True)

    rng = random.Random(args.seed)
    n = nx
    attempts = [
        search_basis(random.Random(rng.randrange(1 << 63)), "x", hz, hx, n),
        search_basis(random.Random(rng.randrange(1 << 63)), "z", hx, hz, n),
    ]
    found = [item for item in attempts if item is not None]
    if found:
        basis_name, vector = min(found, key=lambda item: item[1].bit_count())
        result = {
            "status": "completed",
            "basis": basis_name,
            "vector": vector_to_list(vector, n),
            "upper_bound": vector.bit_count(),
        }
    else:
        result = {
            "status": "not_found",
            "basis": "x",
            "vector": [0] * n,
            "upper_bound": None,
        }
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
