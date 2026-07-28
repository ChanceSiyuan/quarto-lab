#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def fail(message: str = "") -> None:
    _ = message
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
    sys.exit(0)


def parse_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    rows: List[int] = []
    if all(k in obj for k in ("n_rows", "n_cols", "data")):
        n_cols = int(obj["n_cols"])
        data = obj["data"]
        if int(obj["n_rows"]) != len(data):
            fail("dense row count mismatch")
        for row in data:
            if len(row) != n_cols:
                fail("dense row width mismatch")
            bits = 0
            for i, value in enumerate(row):
                if int(value) & 1:
                    bits |= 1 << i
            rows.append(bits)
        return rows, n_cols

    if all(k in obj for k in ("num_cols", "rows")):
        n_cols = int(obj["num_cols"])
        for row in obj["rows"]:
            bits = 0
            prev = -1
            for col in row:
                col = int(col)
                if col <= prev or col < 0 or col >= n_cols:
                    fail("invalid sparse row")
                bits |= 1 << col
                prev = col
            rows.append(bits)
        return rows, n_cols

    fail("unknown matrix format")
    return [], 0


def lowbit_index(x: int) -> int:
    return (x & -x).bit_length() - 1


def reduce_by_basis(x: int, basis: Dict[int, int]) -> int:
    changed = True
    while x and changed:
        changed = False
        for p in sorted(basis):
            if (x >> p) & 1:
                y = x ^ basis[p]
                if y != x:
                    x = y
                    changed = True
    return x


def add_to_basis(x: int, basis: Dict[int, int]) -> bool:
    x = reduce_by_basis(x, basis)
    if x == 0:
        return False
    p = lowbit_index(x)
    for q, row in list(basis.items()):
        if (row >> p) & 1:
            basis[q] = row ^ x
    basis[p] = x
    return True


def row_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for row in rows:
        if row:
            add_to_basis(row, basis)
    return basis


def in_span(x: int, basis: Dict[int, int]) -> bool:
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows: Sequence[int], n_cols: int) -> List[int]:
    rb = row_basis(rows)
    pivots = set(rb)
    out: List[int] = []
    for free_col in range(n_cols):
        if free_col in pivots:
            continue
        v = 1 << free_col
        for p, row in rb.items():
            if (row >> free_col) & 1:
                v |= 1 << p
        out.append(v)
    return out


def quotient_kernel_basis(kernel: Sequence[int], stabilizers: Dict[int, int]) -> List[int]:
    residue_basis: Dict[int, int] = {}
    logicals: List[int] = []
    for v in sorted(kernel, key=lambda x: (x.bit_count(), x)):
        residue = reduce_by_basis(v, stabilizers)
        if residue and add_to_basis(residue, residue_basis):
            logicals.append(v)
    return logicals


def mat_vec_zero(rows: Sequence[int], v: int) -> bool:
    return all(((row & v).bit_count() & 1) == 0 for row in rows)


def verify(v: int, basis_name: str, hx: Sequence[int], hz: Sequence[int], bx: Dict[int, int], bz: Dict[int, int]) -> bool:
    if v == 0:
        return False
    if basis_name == "x":
        return mat_vec_zero(hz, v) and not in_span(v, bx)
    return mat_vec_zero(hx, v) and not in_span(v, bz)


def bits_to_list(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def random_combo(rng: random.Random, vecs: Sequence[int]) -> int:
    if not vecs:
        return 0
    dim = len(vecs)
    if rng.random() < 0.70:
        take = rng.randint(1, min(dim, 8))
        idxs = rng.sample(range(dim), take)
    else:
        idxs = [i for i in range(dim) if rng.getrandbits(1)]
        if not idxs:
            idxs = [rng.randrange(dim)]
    v = 0
    for i in idxs:
        v ^= vecs[i]
    return v


def improve_by_stabilizers(v: int, stabilizer_rows: Sequence[int], rng: random.Random, passes: int) -> int:
    if not stabilizer_rows:
        return v
    current = v
    current_w = current.bit_count()
    rows = [r for r in stabilizer_rows if r]
    for _ in range(passes):
        if len(rows) > 768:
            active = rng.sample(rows, 768)
        else:
            active = rows[:]
        rng.shuffle(active)
        changed = False
        for row in active:
            cand = current ^ row
            cand_w = cand.bit_count()
            if cand_w < current_w or (cand_w == current_w and rng.random() < 0.02):
                current, current_w = cand, cand_w
                changed = True
        if not changed:
            break
    return current


def search_one(
    basis_name: str,
    kernel_checks: Sequence[int],
    stabilizer_rows: Sequence[int],
    stabilizer_basis: Dict[int, int],
    verify_args: Tuple[Sequence[int], Sequence[int], Dict[int, int], Dict[int, int]],
    n: int,
    rng: random.Random,
) -> Optional[int]:
    kernel = nullspace_basis(kernel_checks, n)
    logicals = quotient_kernel_basis(kernel, stabilizer_basis)
    if not logicals:
        return None

    hx, hz, bx, bz = verify_args
    best: Optional[int] = None

    seeds = list(logicals)
    for v in seeds:
        cand = improve_by_stabilizers(v, stabilizer_rows, rng, 4)
        if verify(cand, basis_name, hx, hz, bx, bz):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    dim = len(logicals)
    iterations = max(400, min(7000, 180 * dim + 12 * len(stabilizer_rows) + 3 * n))
    for t in range(iterations):
        v = random_combo(rng, logicals)
        if v == 0:
            continue
        if t % 9 == 0 and stabilizer_rows:
            for row in rng.sample(list(stabilizer_rows), min(len(stabilizer_rows), rng.randint(1, min(12, len(stabilizer_rows))))):
                v ^= row
        cand = improve_by_stabilizers(v, stabilizer_rows, rng, 6)
        if verify(cand, basis_name, hx, hz, bx, bz):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    return best


def main() -> None:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    hx, nx = parse_matrix(args.hx)
    hz, nz = parse_matrix(args.hz)
    if nx != nz:
        fail("matrix width mismatch")
    os.makedirs(args.output_dir, exist_ok=True)

    rng = random.Random(args.seed)
    bx = row_basis(hx)
    bz = row_basis(hz)
    verify_args = (hx, hz, bx, bz)

    x_witness = search_one("x", hz, hx, bx, verify_args, nx, rng)
    z_witness = search_one("z", hx, hz, bz, verify_args, nx, rng)

    choices = []
    if x_witness is not None:
        choices.append(("x", x_witness))
    if z_witness is not None:
        choices.append(("z", z_witness))
    if not choices:
        fail("no witness")

    basis_name, witness = min(choices, key=lambda item: (item[1].bit_count(), item[0]))
    if not verify(witness, basis_name, hx, hz, bx, bz):
        fail("verification failed")

    result = {
        "status": "completed",
        "basis": basis_name,
        "vector": bits_to_list(witness, nx),
        "upper_bound": int(witness.bit_count()),
    }
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
