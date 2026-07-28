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
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    x |= 1 << i
            rows.append(x)
        return n, rows

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            last = -1
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n:
                    raise ValueError(f"invalid sparse row in {path}")
                x |= 1 << col
                last = col
            rows.append(x)
        return n, rows

    raise ValueError(f"unrecognized matrix JSON format in {path}")


def rref(rows: Iterable[int]) -> Tuple[List[int], List[int], Dict[int, int]]:
    basis: Dict[int, int] = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break

    pivots = sorted(basis.keys(), reverse=True)
    for p in pivots:
        row = basis[p]
        for q in pivots:
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row

    pivots = sorted(basis.keys())
    return [basis[p] for p in pivots], pivots, {p: basis[p] for p in pivots}


def reduce_by_basis(x: int, pivot_rows: Dict[int, int]) -> int:
    y = int(x)
    while y:
        p = y.bit_length() - 1
        row = pivot_rows.get(p)
        if row is None:
            return y
        y ^= row
    return 0


def in_rowspace(x: int, pivot_rows: Dict[int, int]) -> bool:
    return reduce_by_basis(x, pivot_rows) == 0


def kernel_basis(n: int, rows: Sequence[int]) -> List[int]:
    _, pivots, pivot_rows = rref(rows)
    pivot_set = set(pivots)
    out = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for p in pivots:
            if (pivot_rows[p] >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v: int, checks: Sequence[int]) -> bool:
    return all(((v & row).bit_count() & 1) == 0 for row in checks)


def combine(items: Sequence[int], rng: random.Random, p: float) -> int:
    x = 0
    used = False
    for item in items:
        if rng.random() < p:
            x ^= item
            used = True
    if not used and items:
        x = rng.choice(items)
    return x


def permute_bits(x: int, perm: Sequence[int]) -> int:
    y = 0
    z = x
    while z:
        lsb = z & -z
        old = lsb.bit_length() - 1
        y |= 1 << perm[old]
        z ^= lsb
    return y


def permute_rows(rows: Sequence[int], perm: Sequence[int]) -> List[int]:
    return [permute_bits(row, perm) for row in rows]


def greedy_reduce(v: int, stabilizers: Sequence[int], rng: random.Random, rounds: int) -> int:
    if not stabilizers:
        return v
    rows = list(stabilizers)
    best = v
    best_w = v.bit_count()
    for _ in range(rounds):
        x = v
        rng.shuffle(rows)
        improved = True
        passes = 0
        while improved and passes < 4:
            improved = False
            passes += 1
            for row in rows:
                y = x ^ row
                if y.bit_count() < x.bit_count():
                    x = y
                    improved = True
        w = x.bit_count()
        if w < best_w:
            best = x
            best_w = w
    return best


def logical_representatives(
    null_basis: Sequence[int], stabilizers: Sequence[int]
) -> Tuple[List[int], Dict[int, int]]:
    _, _, span = rref(stabilizers)
    reps: List[int] = []
    for v in null_basis:
        if not in_rowspace(v, span):
            reps.append(v)
            _, _, span = rref(list(stabilizers) + reps)
    return reps, rref(stabilizers)[2]


def search_basis(
    name: str,
    n: int,
    kernel_checks: Sequence[int],
    stabilizers: Sequence[int],
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    null = kernel_basis(n, kernel_checks)
    reps, stab_span = logical_representatives(null, stabilizers)
    if not reps:
        return None

    stab_rows, _, _ = rref(stabilizers)
    candidates: List[int] = []
    candidates.extend(reps)

    perm_trials = 18 if n <= 512 else 8 if n <= 2048 else 3
    for _ in range(perm_trials):
        perm = list(range(n))
        rng.shuffle(perm)
        inv = [0] * n
        for old, new in enumerate(perm):
            inv[new] = old
        pkernel = permute_rows(kernel_checks, perm)
        pstabs = permute_rows(stabilizers, perm)
        preps, _ = logical_representatives(kernel_basis(n, pkernel), pstabs)
        for rep in preps:
            x = permute_bits(rep, inv)
            if x and not in_rowspace(x, stab_span):
                candidates.append(x)

    samples = max(256, min(12000, 64 * len(reps) + 8 * n))
    for i in range(samples):
        if i < len(reps):
            x = reps[i]
        else:
            p = rng.choice((0.10, 0.18, 0.30, 0.50))
            x = combine(reps, rng, p)
        if x and not in_rowspace(x, stab_span):
            candidates.append(x)

    best = 0
    best_w = n + 1
    reduce_rounds = 3 if len(stab_rows) > 1500 else 8
    for x in candidates:
        y = greedy_reduce(x, stab_rows, rng, reduce_rounds)
        if y and syndrome_zero(y, kernel_checks) and not in_rowspace(y, stab_span):
            w = y.bit_count()
            if w < best_w:
                best = y
                best_w = w
                if best_w == 1:
                    break

    if best:
        return name, best
    return None


def vector_to_list(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def emit(status: str, basis, vector, upper_bound) -> None:
    print(
        json.dumps(
            {
                "status": status,
                "basis": basis,
                "vector": vector,
                "upper_bound": upper_bound,
            },
            separators=(",", ":"),
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        rng = random.Random(args.seed)
        nx, hx = load_matrix(args.hx)
        nz, hz = load_matrix(args.hz)
        if nx != nz:
            emit("failed", None, [], None)
            return 0
        n = nx

        choices = [
            ("x", hz, hx),  # X logicals commute with Z checks, modulo X stabilizers.
            ("z", hx, hz),  # Z logicals commute with X checks, modulo Z stabilizers.
        ]
        rng.shuffle(choices)

        found = []
        for basis_name, kernel_checks, stabilizers in choices:
            ans = search_basis(basis_name, n, kernel_checks, stabilizers, rng)
            if ans is not None:
                found.append(ans)

        if not found:
            emit("failed", None, [], None)
            return 0

        basis_name, witness = min(found, key=lambda item: item[1].bit_count())
        if basis_name == "x":
            ok = syndrome_zero(witness, hz) and not in_rowspace(witness, rref(hx)[2])
        else:
            ok = syndrome_zero(witness, hx) and not in_rowspace(witness, rref(hz)[2])
        if not ok:
            emit("failed", None, [], None)
            return 0

        emit("completed", basis_name, vector_to_list(witness, n), witness.bit_count())
        return 0
    except Exception:
        emit("failed", None, [], None)
        return 0


if __name__ == "__main__":
    sys.exit(main())
