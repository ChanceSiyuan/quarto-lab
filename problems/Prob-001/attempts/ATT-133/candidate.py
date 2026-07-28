#!/usr/bin/env python3
import argparse
import json
import os
import random
from typing import Dict, Iterable, List, Optional, Tuple


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and {"n_rows", "n_cols", "data"} <= set(obj):
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            for j, val in enumerate(row):
                if int(val) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    if isinstance(obj, dict) and {"num_cols", "rows"} <= set(obj):
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            prev = -1
            for col in row:
                c = int(col)
                if c <= prev or c < 0 or c >= n:
                    raise ValueError("sparse row indices must be strictly increasing and in range")
                bits |= 1 << c
                prev = c
            rows.append(bits)
        return rows, n

    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        rows = []
        for row in obj:
            bits = 0
            for j, val in enumerate(row):
                if int(val) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    raise ValueError(f"unsupported matrix JSON format in {path}")


def reduce_by_basis(x: int, basis: Dict[int, int]) -> int:
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            break
        x ^= b
    return x


def row_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def in_rowspace(x: int, basis: Dict[int, int]) -> bool:
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows: List[int], n: int) -> List[int]:
    piv = row_basis(rows)
    # Convert the insertion basis to reduced echelon form so each pivot bit
    # appears in only one row before solving pivot variables from free ones.
    for p in sorted(piv):
        row = piv[p]
        for q in list(piv):
            if q != p and ((piv[q] >> p) & 1):
                piv[q] ^= row
    pivot_cols = set(piv)
    out = []
    for free in range(n):
        if free in pivot_cols:
            continue
        v = 1 << free
        # For each pivot row p = free_terms, make pivot variable cancel its free bit.
        for p, row in piv.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v: int, checks: List[int]) -> bool:
    for row in checks:
        if (row & v).bit_count() & 1:
            return False
    return True


def to_list(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def random_kernel_vector(ns: List[int], rng: random.Random) -> int:
    v = 0
    # Dense random combinations give broad coset coverage; force at least one term.
    touched = False
    for b in ns:
        if rng.getrandbits(1):
            v ^= b
            touched = True
    if not touched and ns:
        v = rng.choice(ns)
    return v


def improve_by_stabilizers(v: int, stabilizers: List[int], rng: random.Random, rounds: int) -> int:
    if not stabilizers:
        return v

    best = v
    current = v
    rows = [r for r in stabilizers if r]
    if not rows:
        return v

    for _ in range(rounds):
        rng.shuffle(rows)
        changed = True
        while changed:
            changed = False
            cw = current.bit_count()
            for row in rows:
                cand = current ^ row
                if cand and cand.bit_count() < cw:
                    current = cand
                    cw = cand.bit_count()
                    changed = True
        if current.bit_count() < best.bit_count():
            best = current
        # Small randomized stabilizer walk to escape a greedy local minimum.
        current = best
        for _j in range(1 + rng.randrange(min(8, len(rows)))):
            current ^= rng.choice(rows)
        if not current:
            current = best
    return best


def find_for_basis(
    kernel_checks: List[int],
    stabilizers: List[int],
    n: int,
    rng: random.Random,
    attempts: int,
) -> Optional[int]:
    ns = nullspace_basis(kernel_checks, n)
    if not ns:
        return None
    stab_basis = row_basis(stabilizers)
    best: Optional[int] = None

    for _ in range(attempts):
        v = random_kernel_vector(ns, rng)
        if not v or in_rowspace(v, stab_basis):
            continue
        v = improve_by_stabilizers(v, stabilizers, rng, rounds=3)
        if v and syndrome_zero(v, kernel_checks) and not in_rowspace(v, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        if nx != nz:
            raise ValueError("Hx and Hz must have the same number of columns")

        os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)
        attempts = max(256, min(8192, 64 * (n + 1)))

        x_wit = find_for_basis(hz, hx, n, rng, attempts)
        z_wit = find_for_basis(hx, hz, n, rng, attempts)

        choices = []
        if x_wit is not None:
            choices.append(("x", x_wit))
        if z_wit is not None:
            choices.append(("z", z_wit))

        if choices:
            basis, vec = min(choices, key=lambda item: (item[1].bit_count(), item[0]))
            result = {
                "status": "completed",
                "basis": basis,
                "vector": to_list(vec, n),
                "upper_bound": vec.bit_count(),
            }
        else:
            result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception as exc:
        result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
        try:
            os.makedirs(args.output_dir, exist_ok=True)
            with open(os.path.join(args.output_dir, "error.txt"), "w", encoding="utf-8") as f:
                f.write(str(exc) + "\n")
        except Exception:
            pass

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
