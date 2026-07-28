#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            x = 0
            if len(row) != n:
                raise ValueError(f"dense row has length {len(row)}, expected {n}")
            for i, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if bit:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            x = 0
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n:
                    raise ValueError("sparse row indices must be strictly increasing")
                x |= 1 << col
                last = col
            rows.append(x)
        return rows, n

    raise ValueError("unrecognized matrix JSON format")


def rref(rows: Iterable[int], n: int) -> Tuple[List[int], List[int]]:
    basis: Dict[int, int] = {}
    for row in rows:
        x = int(row)
        while x:
            p = (x & -x).bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                for q, y in list(basis.items()):
                    if q != p and ((y >> p) & 1):
                        basis[q] = y ^ x
                break
    pivots = sorted(basis)
    return [basis[p] for p in pivots], pivots


def reduce_by_basis(x: int, basis_rows: Sequence[int], pivots: Sequence[int]) -> int:
    for row, p in zip(basis_rows, pivots):
        if (x >> p) & 1:
            x ^= row
    return x


def in_rowspace(x: int, basis_rows: Sequence[int], pivots: Sequence[int]) -> bool:
    return reduce_by_basis(x, basis_rows, pivots) == 0


def kernel_basis(check_rows: Sequence[int], n: int) -> List[int]:
    rows, pivots = rref(check_rows, n)
    pivot_set = set(pivots)
    out = []
    for free_col in range(n):
        if free_col in pivot_set:
            continue
        v = 1 << free_col
        for row, p in zip(rows, pivots):
            if (row >> free_col) & 1:
                v |= 1 << p
        out.append(v)
    return out


def dot_parity(a: int, b: int) -> int:
    return (a & b).bit_count() & 1


def in_kernel(v: int, checks: Sequence[int]) -> bool:
    return all(dot_parity(v, row) == 0 for row in checks)


def bits_to_list(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def random_kernel_vector(kbasis: Sequence[int], rng: random.Random) -> int:
    v = 0
    for b in kbasis:
        if rng.getrandbits(1):
            v ^= b
    if v == 0 and kbasis:
        v = rng.choice(kbasis)
    return v


def greedy_stabilizer_descent(
    v: int,
    stabilizers: Sequence[int],
    checks: Sequence[int],
    stab_basis: Sequence[int],
    stab_pivots: Sequence[int],
    rng: random.Random,
    passes: int,
) -> int:
    best = v
    best_w = v.bit_count()
    rows = [r for r in stabilizers if r]

    for _ in range(passes):
        cur = best
        cur_w = best_w
        rng.shuffle(rows)
        changed = True
        while changed:
            changed = False
            for row in rows:
                nxt = cur ^ row
                nw = nxt.bit_count()
                if nw < cur_w and in_kernel(nxt, checks) and not in_rowspace(nxt, stab_basis, stab_pivots):
                    cur = nxt
                    cur_w = nw
                    changed = True
        if cur_w < best_w:
            best = cur
            best_w = cur_w

    return best


def search_basis(
    name: str,
    checks: Sequence[int],
    stabilizers: Sequence[int],
    n: int,
    seed: int,
) -> Optional[Tuple[str, int]]:
    rng = random.Random((seed << 8) ^ (17 if name == "x" else 43))
    stab_basis, stab_pivots = rref(stabilizers, n)
    kbasis = kernel_basis(checks, n)
    if not kbasis:
        return None

    # Try individual kernel generators first, then random sums. This is still
    # a witness search over kernel/coset samples, not an exact distance search.
    trials: List[int] = list(kbasis)
    trials.extend(random_kernel_vector(kbasis, rng) for _ in range(max(256, 20 * len(kbasis))))

    best = None
    best_w = n + 1
    for raw in trials:
        if raw == 0 or in_rowspace(raw, stab_basis, stab_pivots):
            continue
        cand = greedy_stabilizer_descent(
            raw, stabilizers, checks, stab_basis, stab_pivots, rng, passes=4
        )
        if cand and in_kernel(cand, checks) and not in_rowspace(cand, stab_basis, stab_pivots):
            w = cand.bit_count()
            if w < best_w:
                best = cand
                best_w = w

    if best is None:
        return None
    return name, best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different numbers of columns")
        n = nx
        os.makedirs(args.output_dir, exist_ok=True)

        found = []
        x = search_basis("x", hz, hx, n, args.seed)
        if x is not None:
            found.append(x)
        z = search_basis("z", hx, hz, n, args.seed)
        if z is not None:
            found.append(z)

        if found:
            basis, vec = min(found, key=lambda item: item[1].bit_count())
            result = {
                "status": "completed",
                "basis": basis,
                "vector": bits_to_list(vec, n),
                "upper_bound": vec.bit_count(),
            }
        else:
            result = {"status": "failed", "basis": "x", "vector": [0] * n, "upper_bound": None}
    except Exception:
        result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
