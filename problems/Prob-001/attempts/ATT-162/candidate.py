#!/usr/bin/env python3
import argparse
import json
import os
import random
from typing import Dict, Iterable, List, Optional, Tuple


def read_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if {"n_rows", "n_cols", "data"}.issubset(obj):
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if {"num_cols", "rows"}.issubset(obj):
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            x = 0
            last = -1
            for i in row:
                i = int(i)
                if i <= last or i < 0 or i >= n:
                    raise ValueError(f"invalid sparse row in {path}")
                x |= 1 << i
                last = i
            rows.append(x)
        return rows, n

    raise ValueError(f"unsupported matrix JSON format: {path}")


def add_to_basis(basis: Dict[int, int], row: int) -> bool:
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def row_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for row in rows:
        if row:
            add_to_basis(basis, row)
    return basis


def reduce_by_basis(x: int, basis: Dict[int, int]) -> int:
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return y
        y ^= b
    return 0


def in_rowspace(x: int, basis: Dict[int, int]) -> bool:
    return reduce_by_basis(x, basis) == 0


def reduced_echelon(rows: Iterable[int]) -> Dict[int, int]:
    basis = row_basis(rows)
    for p in sorted(basis):
        row = basis[p]
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
    return basis


def nullspace_basis(rows: Iterable[int], n_cols: int) -> List[int]:
    rref = reduced_echelon(rows)
    pivots = set(rref)
    out = []
    for free in range(n_cols):
        if free in pivots:
            continue
        v = 1 << free
        for p, row in rref.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def mat_vec_zero(rows: Iterable[int], v: int) -> bool:
    return all(((row & v).bit_count() & 1) == 0 for row in rows)


def to_bits(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def verify(v: int, check_rows: List[int], stab_basis: Dict[int, int]) -> bool:
    return v != 0 and mat_vec_zero(check_rows, v) and not in_rowspace(v, stab_basis)


def greedy_stabilizer_descent(
    v: int,
    check_rows: List[int],
    stab_rows: List[int],
    stab_basis: Dict[int, int],
    rng: random.Random,
    passes: int = 5,
) -> int:
    if not stab_rows:
        return v

    cur = v
    rows = [r for r in stab_rows if r]
    for _ in range(passes):
        if len(rows) <= 700:
            order = rows[:]
            rng.shuffle(order)
        else:
            order = rng.sample(rows, 700)
        improved = False
        cur_w = cur.bit_count()
        for row in order:
            nxt = cur ^ row
            nxt_w = nxt.bit_count()
            if nxt_w < cur_w and verify(nxt, check_rows, stab_basis):
                cur = nxt
                cur_w = nxt_w
                improved = True
        if not improved:
            break
    return cur


def random_kernel_combo(kernel: List[int], rng: random.Random) -> int:
    dim = len(kernel)
    if dim == 0:
        return 0
    v = 0
    if dim <= 256:
        mask = rng.getrandbits(dim)
        if mask == 0:
            mask = 1 << rng.randrange(dim)
        while mask:
            lsb = mask & -mask
            v ^= kernel[lsb.bit_length() - 1]
            mask ^= lsb
        return v

    count = 1 + rng.randrange(min(64, dim))
    for i in rng.sample(range(dim), count):
        v ^= kernel[i]
    return v


def search_one(
    label: str,
    check_rows: List[int],
    stab_rows: List[int],
    n: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    kernel = nullspace_basis(check_rows, n)
    if not kernel:
        return None

    stab_basis = row_basis(stab_rows)
    best: Optional[int] = None

    order = list(range(len(kernel)))
    rng.shuffle(order)
    proposals = [kernel[i] for i in order[: min(len(order), 256)]]
    proposals.extend(random_kernel_combo(kernel, rng) for _ in range(2500))

    for v in proposals:
        if not verify(v, check_rows, stab_basis):
            continue
        v = greedy_stabilizer_descent(v, check_rows, stab_rows, stab_basis, rng)
        if verify(v, check_rows, stab_basis) and (
            best is None or v.bit_count() < best.bit_count()
        ):
            best = v

    if best is None:
        return None

    for _ in range(350):
        v = best
        for row in rng.sample(stab_rows, min(len(stab_rows), rng.randrange(0, 9))):
            v ^= row
        v = greedy_stabilizer_descent(v, check_rows, stab_rows, stab_basis, rng, passes=3)
        if verify(v, check_rows, stab_basis) and v.bit_count() < best.bit_count():
            best = v

    return label, best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    hx, nx = read_matrix(args.hx)
    hz, nz = read_matrix(args.hz)
    if nx != nz:
        raise ValueError("hx and hz have different column counts")
    os.makedirs(args.output_dir, exist_ok=True)

    rng = random.Random(args.seed)
    searches = [
        search_one("x", hz, hx, nx, rng),
        search_one("z", hx, hz, nx, rng),
    ]
    witnesses = [w for w in searches if w is not None]

    if witnesses:
        basis, vec = min(witnesses, key=lambda item: item[1].bit_count())
        result = {
            "status": "completed",
            "basis": basis,
            "vector": to_bits(vec, nx),
            "upper_bound": int(vec.bit_count()),
        }
    else:
        result = {
            "status": "failed",
            "basis": None,
            "vector": [],
            "upper_bound": None,
        }

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
