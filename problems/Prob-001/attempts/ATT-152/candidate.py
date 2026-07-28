#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> Tuple[int, List[int]]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        n_cols = max((len(row) for row in obj), default=0)
        rows = []
        for row in obj:
            bits = 0
            for j, bit in enumerate(row):
                if bit:
                    bits |= 1 << j
            rows.append(bits)
        return n_cols, rows

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_cols = int(obj.get("n_cols", 0))
        rows = []
        for row in obj["data"]:
            bits = 0
            for j, bit in enumerate(row):
                if bit:
                    bits |= 1 << j
            rows.append(bits)
        return n_cols, rows

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for j in row:
                j = int(j)
                if j <= last:
                    raise ValueError(f"sparse row in {path} is not strictly increasing")
                if j < 0 or j >= n_cols:
                    raise ValueError(f"sparse column {j} out of range for {path}")
                bits |= 1 << j
                last = j
            rows.append(bits)
        return n_cols, rows

    raise ValueError(f"unsupported matrix JSON format: {path}")


def parity(x: int) -> int:
    return x.bit_count() & 1


def row_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for row in rows:
        x = row
        while x:
            pivot = x.bit_length() - 1
            if pivot in basis:
                x ^= basis[pivot]
            else:
                basis[pivot] = x
                break
    return basis


def in_rowspace(x: int, basis: Dict[int, int]) -> bool:
    y = x
    while y:
        pivot = y.bit_length() - 1
        row = basis.get(pivot)
        if row is None:
            return False
        y ^= row
    return True


def nullspace_basis(rows: Sequence[int], n_cols: int) -> List[int]:
    echelon = row_basis(rows)
    pivots = set(echelon)
    free_cols = [j for j in range(n_cols) if j not in pivots]
    out: List[int] = []

    for free in free_cols:
        v = 1 << free
        for pivot in sorted(pivots):
            row = echelon[pivot]
            if parity(row & v):
                v |= 1 << pivot
        out.append(v)
    return out


def kernel_ok(v: int, check_rows: Sequence[int]) -> bool:
    return all(parity(v & row) == 0 for row in check_rows)


def int_to_vector(v: int, n_cols: int) -> List[int]:
    return [(v >> j) & 1 for j in range(n_cols)]


def logical_directions(
    check_rows: Sequence[int],
    stabilizer_rows: Sequence[int],
    n_cols: int,
) -> Tuple[List[int], Dict[int, int]]:
    stab_basis = row_basis(stabilizer_rows)
    span = row_basis(stabilizer_rows)
    directions: List[int] = []

    for v in nullspace_basis(check_rows, n_cols):
        if v and not in_rowspace(v, span):
            directions.append(v)
            span = row_basis(list(span.values()) + [v])
    return directions, stab_basis


def commuting_stabilizers(
    stabilizer_rows: Sequence[int],
    check_rows: Sequence[int],
) -> List[int]:
    return [row for row in stabilizer_rows if row and kernel_ok(row, check_rows)]


def greedy_reduce(v: int, rows: Sequence[int], rng: random.Random, passes: int) -> int:
    if not rows:
        return v
    best = v
    best_w = best.bit_count()
    order = list(rows)
    for _ in range(passes):
        changed = False
        rng.shuffle(order)
        for row in order:
            trial = best ^ row
            wt = trial.bit_count()
            if wt < best_w:
                best = trial
                best_w = wt
                changed = True
        if not changed:
            break
    return best


def random_combo(rows: Sequence[int], rng: random.Random, nonzero: bool) -> int:
    if not rows:
        return 0
    v = 0
    chosen = False
    for row in rows:
        if rng.getrandbits(1):
            v ^= row
            chosen = True
    if nonzero and not chosen:
        v = rows[rng.randrange(len(rows))]
    return v


def search_basis(
    name: str,
    check_rows: Sequence[int],
    stabilizer_rows: Sequence[int],
    n_cols: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    directions, stab_basis = logical_directions(check_rows, stabilizer_rows, n_cols)
    if not directions:
        return None

    reduc_rows = commuting_stabilizers(stabilizer_rows, check_rows)
    iterations = min(7000, max(256, 10 * n_cols + 80 * len(directions) + 3 * len(reduc_rows)))
    perturb_rows = reduc_rows[:]
    best: Optional[int] = None

    seeds = directions[:]
    for _ in range(iterations):
        if rng.random() < 0.20:
            seed = directions[rng.randrange(len(directions))]
        else:
            seed = random_combo(directions, rng, nonzero=True)

        if perturb_rows and rng.random() < 0.55:
            flips = 1 + rng.randrange(min(12, len(perturb_rows)))
            for _ in range(flips):
                seed ^= perturb_rows[rng.randrange(len(perturb_rows))]
        seeds.append(seed)

    for seed in seeds:
        candidate = greedy_reduce(seed, reduc_rows, rng, passes=5)
        if (
            candidate
            and kernel_ok(candidate, check_rows)
            and not in_rowspace(candidate, stab_basis)
        ):
            if best is None or candidate.bit_count() < best.bit_count():
                best = candidate

    if best is None:
        return None
    return name, best


def emit(obj: dict) -> None:
    print(json.dumps(obj, separators=(",", ":")), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        n_x, hx_rows = load_matrix(args.hx)
        n_z, hz_rows = load_matrix(args.hz)
        n_cols = max(n_x, n_z)
        if n_x not in (0, n_cols) or n_z not in (0, n_cols):
            raise ValueError("HX and HZ have incompatible column counts")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        searches = [
            ("x", hz_rows, hx_rows),
            ("z", hx_rows, hz_rows),
        ]
        rng.shuffle(searches)

        best: Optional[Tuple[str, int]] = None
        for basis_name, check_rows, stabilizer_rows in searches:
            hit = search_basis(basis_name, check_rows, stabilizer_rows, n_cols, rng)
            if hit is not None and (best is None or hit[1].bit_count() < best[1].bit_count()):
                best = hit

        if best is None:
            emit({"status": "not_found", "basis": None, "vector": [], "upper_bound": None})
            return 0

        basis_name, vector = best
        emit(
            {
                "status": "completed",
                "basis": basis_name,
                "vector": int_to_vector(vector, n_cols),
                "upper_bound": vector.bit_count(),
            }
        )
        return 0
    except Exception as exc:
        emit({"status": "error", "basis": None, "vector": [], "upper_bound": None})
        return 1


if __name__ == "__main__":
    sys.exit(main())
