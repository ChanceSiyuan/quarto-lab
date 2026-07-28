#!/usr/bin/env python3
import argparse
import json
import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as handle:
        obj = json.load(handle)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            mask = 0
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n_cols

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            mask = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing in range")
                mask |= 1 << col
                last = col
            rows.append(mask)
        return rows, n_cols

    raise ValueError("unrecognized matrix JSON format")


def rref(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for value in rows:
        x = int(value)
        while x:
            pivot = x.bit_length() - 1
            row = basis.get(pivot)
            if row is None:
                basis[pivot] = x
                break
            x ^= row

    for pivot in sorted(basis):
        row = basis[pivot]
        for other_pivot, other_row in list(basis.items()):
            if other_pivot != pivot and ((other_row >> pivot) & 1):
                basis[other_pivot] = other_row ^ row
    return basis


def reduce_by_basis(value: int, basis: Dict[int, int]) -> int:
    x = int(value)
    while x:
        pivot = x.bit_length() - 1
        row = basis.get(pivot)
        if row is None:
            return x
        x ^= row
    return 0


def in_rowspace(value: int, basis: Dict[int, int]) -> bool:
    return reduce_by_basis(value, basis) == 0


def kernel_basis(check_rows: Sequence[int], n_cols: int) -> List[int]:
    check_basis = rref(check_rows)
    pivots = set(check_basis)
    vectors: List[int] = []
    for free_col in range(n_cols):
        if free_col in pivots:
            continue
        vector = 1 << free_col
        for pivot, row in check_basis.items():
            if (row >> free_col) & 1:
                vector |= 1 << pivot
        vectors.append(vector)
    return vectors


def syndrome_zero(vector: int, checks: Sequence[int]) -> bool:
    for row in checks:
        if (vector & row).bit_count() & 1:
            return False
    return True


def verify(vector: int, check_rows: Sequence[int], stabilizer_basis: Dict[int, int]) -> bool:
    return vector != 0 and syndrome_zero(vector, check_rows) and not in_rowspace(vector, stabilizer_basis)


def greedy_reduce(
    vector: int,
    stabilizer_rows: Sequence[int],
    kernel_vectors: Sequence[int],
    stabilizer_basis: Dict[int, int],
    check_rows: Sequence[int],
    rng: random.Random,
    rounds: int,
) -> int:
    current = vector
    moves = [row for row in stabilizer_rows if row]
    # Kernel moves let the search jump to a different logical class; the
    # verification gate prevents collapsing into the stabilizer row-space.
    moves.extend(v for v in kernel_vectors if v)
    if not moves:
        return current

    for _ in range(rounds):
        changed = False
        rng.shuffle(moves)
        for move in moves:
            candidate = current ^ move
            if candidate and candidate.bit_count() <= current.bit_count():
                if verify(candidate, check_rows, stabilizer_basis):
                    current = candidate
                    changed = True
        if not changed:
            break
    return current


def random_kernel_vector(kernel_vectors: Sequence[int], rng: random.Random) -> int:
    value = 0
    for vector in kernel_vectors:
        if rng.getrandbits(1):
            value ^= vector
    if value == 0 and kernel_vectors:
        value = rng.choice(kernel_vectors)
    return value


def search_basis(
    basis_name: str,
    check_rows: Sequence[int],
    stabilizer_rows: Sequence[int],
    n_cols: int,
    seed: int,
) -> Optional[Tuple[str, int]]:
    rng = random.Random((seed << 8) ^ (17 if basis_name == "x" else 43))
    stabilizer_basis = rref(stabilizer_rows)
    kernels = kernel_basis(check_rows, n_cols)
    if not kernels:
        return None

    best: Optional[int] = None

    seeds: List[int] = []
    seeds.extend(kernels)
    # Low-density random combinations bias the search toward sparse witnesses.
    trials = max(256, min(8192, 64 * (len(kernels) + 1)))
    for i in range(trials):
        if i < len(kernels) * 4:
            width = 1 + (i % min(6, max(1, len(kernels))))
            value = 0
            for vector in rng.sample(kernels, min(width, len(kernels))):
                value ^= vector
            seeds.append(value)
        else:
            seeds.append(random_kernel_vector(kernels, rng))

    for value in seeds:
        if not verify(value, check_rows, stabilizer_basis):
            continue
        value = greedy_reduce(
            value,
            stabilizer_rows,
            kernels,
            stabilizer_basis,
            check_rows,
            rng,
            rounds=3,
        )
        if verify(value, check_rows, stabilizer_basis):
            if best is None or value.bit_count() < best.bit_count():
                best = value

    if best is None:
        return None
    return basis_name, best


def mask_to_list(mask: int, n_cols: int) -> List[int]:
    return [1 if (mask >> i) & 1 else 0 for i in range(n_cols)]


def main() -> None:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx_rows, hx_n = load_matrix(args.hx)
        hz_rows, hz_n = load_matrix(args.hz)
        if hx_n != hz_n:
            raise ValueError("Hx and Hz must have the same number of columns")
        n_cols = hx_n

        candidates = [
            search_basis("x", hz_rows, hx_rows, n_cols, args.seed),
            search_basis("z", hx_rows, hz_rows, n_cols, args.seed),
        ]
        candidates = [item for item in candidates if item is not None]

        if candidates:
            basis_name, vector = min(candidates, key=lambda item: item[1].bit_count())
            result = {
                "status": "completed",
                "basis": basis_name,
                "vector": mask_to_list(vector, n_cols),
                "upper_bound": int(vector.bit_count()),
            }
        else:
            result = {"status": "not_found", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "error", "basis": None, "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
