#!/usr/bin/env python3
import argparse
import json
import os
import random
from typing import Iterable, List, Optional, Tuple


class LinearBasis:
    def __init__(self) -> None:
        self.rows = {}

    def reduce(self, value: int) -> int:
        x = value
        while x:
            pivot = x.bit_length() - 1
            row = self.rows.get(pivot)
            if row is None:
                break
            x ^= row
        return x

    def contains(self, value: int) -> bool:
        return self.reduce(value) == 0

    def add(self, value: int) -> bool:
        x = self.reduce(value)
        if x == 0:
            return False
        pivot = x.bit_length() - 1
        for p, row in list(self.rows.items()):
            if (row >> pivot) & 1:
                self.rows[p] = row ^ x
        self.rows[pivot] = x
        return True


def load_matrix(path: str) -> Tuple[int, List[int]]:
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)

    if "dense_binary_matrix" in raw:
        raw = raw["dense_binary_matrix"]
    if "sparse_rows" in raw:
        raw = raw["sparse_rows"]

    rows: List[int] = []
    if {"n_rows", "n_cols", "data"}.issubset(raw):
        n = int(raw["n_cols"])
        for row in raw["data"]:
            bits = 0
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    bits |= 1 << i
            rows.append(bits)
        return n, rows

    if {"num_cols", "rows"}.issubset(raw):
        n = int(raw["num_cols"])
        for row in raw["rows"]:
            bits = 0
            last = -1
            for col in row:
                c = int(col)
                if c <= last or c < 0 or c >= n:
                    raise ValueError("sparse row indices must be strictly increasing and in range")
                bits |= 1 << c
                last = c
            rows.append(bits)
        return n, rows

    raise ValueError("matrix JSON must use dense_binary_matrix or sparse_rows format")


def dot_parity(a: int, b: int) -> int:
    return (a & b).bit_count() & 1


def nullspace_basis(rows: Iterable[int], n: int) -> List[int]:
    basis = LinearBasis()
    for row in rows:
        basis.add(row)

    pivots = set(basis.rows)
    free_cols = [i for i in range(n) if i not in pivots]
    result: List[int] = []
    for free in free_cols:
        vec = 1 << free
        for pivot, row in basis.rows.items():
            if (row >> free) & 1:
                vec |= 1 << pivot
        result.append(vec)
    return result


def rowspace_basis(rows: Iterable[int]) -> LinearBasis:
    basis = LinearBasis()
    for row in rows:
        basis.add(row)
    return basis


def logical_generators(check_rows: List[int], stabilizer_rows: List[int], n: int) -> List[int]:
    span = rowspace_basis(stabilizer_rows)
    logicals: List[int] = []
    for vec in nullspace_basis(check_rows, n):
        if span.add(vec):
            logicals.append(vec)
    return logicals


def verify(vec: int, check_rows: List[int], stabilizer_basis: LinearBasis) -> bool:
    if vec == 0:
        return False
    if any(dot_parity(vec, row) for row in check_rows):
        return False
    return not stabilizer_basis.contains(vec)


def greedy_reduce(vec: int, stabilizer_rows: List[int], rng: random.Random, rounds: int) -> int:
    if not stabilizer_rows:
        return vec
    current = vec
    rows = list(stabilizer_rows)
    for _ in range(rounds):
        improved = False
        rng.shuffle(rows)
        for row in rows:
            trial = current ^ row
            if trial and trial.bit_count() < current.bit_count():
                current = trial
                improved = True
        if not improved:
            break
    return current


def random_logical_combo(gens: List[int], rng: random.Random) -> int:
    if len(gens) == 1:
        return gens[0]

    # Bias toward small combinations, but occasionally mix broadly to escape
    # the coordinate shape of the nullspace basis.
    if rng.random() < 0.75:
        count = 1
        while count < len(gens) and rng.random() < 0.35:
            count += 1
        picks = rng.sample(gens, count)
    else:
        picks = [g for g in gens if rng.getrandbits(1)]
        if not picks:
            picks = [rng.choice(gens)]

    value = 0
    for gen in picks:
        value ^= gen
    return value


def search_basis(
    label: str,
    check_rows: List[int],
    stabilizer_rows: List[int],
    n: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    stab_basis = rowspace_basis(stabilizer_rows)
    gens = logical_generators(check_rows, stabilizer_rows, n)
    if not gens:
        return None

    best: Optional[int] = None
    budget = max(600, min(25000, 120 * (len(gens) + len(stabilizer_rows) + 1)))
    reduce_rounds = 2 + min(8, len(stabilizer_rows) // 20)

    seeds = list(gens)
    for _ in range(budget):
        seeds.append(random_logical_combo(gens, rng))

    for vec in seeds:
        candidate = greedy_reduce(vec, stabilizer_rows, rng, reduce_rounds)
        if verify(candidate, check_rows, stab_basis):
            if best is None or candidate.bit_count() < best.bit_count():
                best = candidate

        # Try a few neutral stabilizer perturbations before another greedy
        # descent; this is a randomized coset walk, not an exact minimization.
        if stabilizer_rows and rng.random() < 0.4:
            noisy = vec
            for row in rng.sample(stabilizer_rows, min(len(stabilizer_rows), 1 + rng.randrange(4))):
                noisy ^= row
            candidate = greedy_reduce(noisy, stabilizer_rows, rng, reduce_rounds)
            if verify(candidate, check_rows, stab_basis):
                if best is None or candidate.bit_count() < best.bit_count():
                    best = candidate

    if best is None:
        return None
    return label, best


def vector_to_list(vec: int, n: int) -> List[int]:
    return [(vec >> i) & 1 for i in range(n)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    nx, hx = load_matrix(args.hx)
    nz, hz = load_matrix(args.hz)
    if nx != nz:
        raise ValueError("hx and hz must have the same number of columns")
    n = nx

    rng = random.Random(args.seed)
    attempts = [
        search_basis("x", hz, hx, n, rng),
        search_basis("z", hx, hz, n, rng),
    ]
    witnesses = [item for item in attempts if item is not None]

    if witnesses:
        basis, vec = min(witnesses, key=lambda item: item[1].bit_count())
        result = {
            "status": "completed",
            "basis": basis,
            "vector": vector_to_list(vec, n),
            "upper_bound": vec.bit_count(),
        }
    else:
        result = {
            "status": "not_found",
            "basis": "x",
            "vector": [],
            "upper_bound": None,
        }

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
