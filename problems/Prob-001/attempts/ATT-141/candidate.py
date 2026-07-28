#!/usr/bin/env python3
import argparse
import json
import os
import random
from typing import Iterable, List, Optional, Sequence, Tuple


def fail() -> None:
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"}.issubset(obj):
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n_cols:
                raise ValueError("dense row has wrong length")
            bits = 0
            for i, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix is not binary")
                if int(bit):
                    bits |= 1 << i
            rows.append(bits)
        return rows, n_cols

    if {"num_cols", "rows"}.issubset(obj):
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            prev = -1
            bits = 0
            for col in row:
                c = int(col)
                if c <= prev or c < 0 or c >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing and in range")
                bits |= 1 << c
                prev = c
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


def row_reduce(rows: Iterable[int]) -> dict:
    basis = {}
    for value in rows:
        x = int(value)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def in_span(value: int, basis: dict) -> bool:
    x = int(value)
    while x:
        p = x.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return False
        x ^= row
    return True


def kernel_basis(check_rows: Sequence[int], n_cols: int) -> List[int]:
    basis = row_reduce(check_rows)
    pivots = set(basis)
    free_cols = [i for i in range(n_cols) if i not in pivots]
    out = []
    for free in free_cols:
        v = 1 << free
        for pivot in sorted(pivots):
            if (basis[pivot] & v).bit_count() & 1:
                v |= 1 << pivot
        out.append(v)
    return out


def syndrome_zero(value: int, checks: Sequence[int]) -> bool:
    return all(((value & row).bit_count() & 1) == 0 for row in checks)


def to_bits(value: int, n_cols: int) -> List[int]:
    return [(value >> i) & 1 for i in range(n_cols)]


def reduce_by_stabilizers(value: int, stabilizers: Sequence[int], rng: random.Random, rounds: int) -> int:
    v = value
    rows = [r for r in stabilizers if r]
    rows.sort(key=int.bit_count)

    improved = True
    while improved:
        improved = False
        for row in rows:
            nv = v ^ row
            if nv.bit_count() < v.bit_count():
                v = nv
                improved = True

    if not rows:
        return v

    for _ in range(rounds):
        sample = rows[:]
        rng.shuffle(sample)
        changed = False
        for row in sample:
            nv = v ^ row
            if nv.bit_count() <= v.bit_count() and (nv.bit_count() < v.bit_count() or rng.randrange(8) == 0):
                v = nv
                changed = True
        if changed:
            improved = True
            while improved:
                improved = False
                for row in rows:
                    nv = v ^ row
                    if nv.bit_count() < v.bit_count():
                        v = nv
                        improved = True
    return v


def logical_generators(kernel_rows: Sequence[int], stabilizer_rows: Sequence[int], n_cols: int) -> List[int]:
    span = row_reduce(stabilizer_rows)
    gens = []
    for v in kernel_basis(kernel_rows, n_cols):
        if v and not in_span(v, span):
            gens.append(v)
            span = row_reduce(list(span.values()) + [v])
    return gens


def random_combo(gens: Sequence[int], rng: random.Random) -> int:
    k = len(gens)
    if k == 1:
        return gens[0]
    mode = rng.randrange(4)
    if mode == 0:
        idxs = [rng.randrange(k)]
    elif mode == 1:
        a = rng.randrange(k)
        b = rng.randrange(k)
        idxs = [a, b] if a != b else [a]
    elif mode == 2:
        size = 1 + min(k - 1, int(rng.expovariate(0.7)))
        idxs = rng.sample(range(k), size)
    else:
        idxs = [i for i in range(k) if rng.getrandbits(1)]
        if not idxs:
            idxs = [rng.randrange(k)]
    v = 0
    for i in idxs:
        v ^= gens[i]
    return v


def search_basis(
    name: str,
    kernel_rows: Sequence[int],
    stabilizer_rows: Sequence[int],
    n_cols: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    stab_basis = row_reduce(stabilizer_rows)
    gens = logical_generators(kernel_rows, stabilizer_rows, n_cols)
    if not gens:
        return None

    best = None
    rounds = 2 + min(20, len(stabilizer_rows) // 8)

    seeds = list(gens)
    for i in range(min(len(gens), 64)):
        for j in range(i + 1, min(len(gens), i + 17)):
            seeds.append(gens[i] ^ gens[j])

    trial_budget = max(512, min(20000, 80 * (n_cols + len(gens) + len(stabilizer_rows))))
    for t in range(trial_budget + len(seeds)):
        v = seeds[t] if t < len(seeds) else random_combo(gens, rng)
        v = reduce_by_stabilizers(v, stabilizer_rows, rng, rounds)
        if not v:
            continue
        if not syndrome_zero(v, kernel_rows):
            continue
        if in_span(v, stab_basis):
            continue
        if best is None or v.bit_count() < best.bit_count():
            best = v
            if best.bit_count() <= 1:
                break

    if best is None:
        return None
    return name, best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        candidates = []
        order = [("x", hz, hx), ("z", hx, hz)]
        if rng.getrandbits(1):
            order.reverse()
        for basis_name, kernel_rows, stabilizer_rows in order:
            found = search_basis(basis_name, kernel_rows, stabilizer_rows, nx, rng)
            if found is not None:
                candidates.append(found)

        if not candidates:
            fail()
            return

        basis, value = min(candidates, key=lambda item: item[1].bit_count())
        vector = to_bits(value, nx)
        print(
            json.dumps(
                {
                    "status": "completed",
                    "basis": basis,
                    "vector": vector,
                    "upper_bound": int(value.bit_count()),
                },
                separators=(",", ":"),
            )
        )
    except Exception:
        fail()


if __name__ == "__main__":
    main()
