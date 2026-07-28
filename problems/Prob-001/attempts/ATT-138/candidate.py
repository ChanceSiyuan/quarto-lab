#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> Tuple[int, List[int]]:
    with open(path, "r", encoding="utf-8") as handle:
        obj = json.load(handle)

    if isinstance(obj, list):
        n_cols = max((len(row) for row in obj), default=0)
        rows = []
        for row in obj:
            bits = 0
            for j, value in enumerate(row):
                if value & 1:
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
            for j, value in enumerate(row):
                if value & 1:
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
                    raise ValueError(f"sparse column {j} outside [0, {n_cols})")
                bits |= 1 << j
                last = j
            rows.append(bits)
        return n_cols, rows

    raise ValueError(f"unsupported matrix JSON format: {path}")


def pivot_of(x: int) -> int:
    return (x & -x).bit_length() - 1


def rref_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for row in rows:
        x = int(row)
        for p in sorted(basis):
            if (x >> p) & 1:
                x ^= basis[p]
        if not x:
            continue
        p = pivot_of(x)
        for q in list(basis):
            if (basis[q] >> p) & 1:
                basis[q] ^= x
        basis[p] = x
    return dict(sorted(basis.items()))


def reduce_by_basis(x: int, basis: Dict[int, int]) -> int:
    y = int(x)
    for p in sorted(basis):
        if (y >> p) & 1:
            y ^= basis[p]
    return y


def in_rowspace(x: int, basis: Dict[int, int]) -> bool:
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(check_rows: Sequence[int], n_cols: int) -> List[int]:
    rref = rref_basis(check_rows)
    pivots = set(rref)
    out: List[int] = []
    for free_col in range(n_cols):
        if free_col in pivots:
            continue
        v = 1 << free_col
        for p, row in rref.items():
            if (row >> free_col) & 1:
                v |= 1 << p
        out.append(v)
    return out


def quotient_representatives(kernel: Sequence[int], stabilizers: Dict[int, int]) -> List[int]:
    q_residue: Dict[int, int] = {}
    q_rep: Dict[int, int] = {}
    for v in kernel:
        residue = reduce_by_basis(v, stabilizers)
        rep = v
        for p in sorted(q_residue):
            if (residue >> p) & 1:
                residue ^= q_residue[p]
                rep ^= q_rep[p]
        if residue:
            p = pivot_of(residue)
            for q in list(q_residue):
                if (q_residue[q] >> p) & 1:
                    q_residue[q] ^= residue
                    q_rep[q] ^= rep
            q_residue[p] = residue
            q_rep[p] = rep
    return [q_rep[p] for p in sorted(q_rep)]


def syndrome_zero(v: int, checks: Sequence[int]) -> bool:
    for row in checks:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def verified(v: int, kernel_checks: Sequence[int], stabilizer_basis: Dict[int, int]) -> bool:
    return v != 0 and syndrome_zero(v, kernel_checks) and not in_rowspace(v, stabilizer_basis)


def greedy_sparsify(
    v: int,
    stabilizer_rows: Sequence[int],
    rng: random.Random,
    passes: int,
) -> int:
    cur = v
    rows = [r for r in stabilizer_rows if r]
    for _ in range(passes):
        changed = False
        rng.shuffle(rows)
        for row in rows:
            nxt = cur ^ row
            if nxt.bit_count() < cur.bit_count():
                cur = nxt
                changed = True
        if not changed:
            break
    return cur


def random_logical_combo(reps: Sequence[int], rng: random.Random) -> int:
    q = len(reps)
    if q == 1:
        return reps[0]
    mode = rng.randrange(4)
    if mode == 0:
        weight = 1
    elif mode == 1:
        weight = min(q, 2 + rng.randrange(min(q, 6)))
    elif mode == 2:
        weight = 1
        while weight < q and rng.random() < 0.55:
            weight += 1
    else:
        weight = rng.randrange(1, q + 1)
    v = 0
    for idx in rng.sample(range(q), weight):
        v ^= reps[idx]
    return v


def search_basis(
    basis_name: str,
    kernel_checks: Sequence[int],
    stabilizer_rows: Sequence[int],
    n_cols: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    stabilizer_basis = rref_basis(stabilizer_rows)
    kernel = nullspace_basis(kernel_checks, n_cols)
    reps = quotient_representatives(kernel, stabilizer_basis)
    if not reps:
        return None

    reducer_rows = list(stabilizer_rows) + list(stabilizer_basis.values())
    best: Optional[int] = None
    trials = min(25000, max(1500, 80 * n_cols + 250 * len(reps)))
    pass_count = 2 if len(reducer_rows) > 2500 else 4

    seeds = list(reps)
    for _ in range(trials):
        seeds.append(random_logical_combo(reps, rng))

    for candidate in seeds:
        candidate = greedy_sparsify(candidate, reducer_rows, rng, pass_count)
        if verified(candidate, kernel_checks, stabilizer_basis):
            if best is None or candidate.bit_count() < best.bit_count():
                best = candidate

    if best is None:
        return None
    return basis_name, best


def bits_to_list(v: int, n_cols: int) -> List[int]:
    return [(v >> j) & 1 for j in range(n_cols)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        nx, hx = load_matrix(args.hx)
        nz, hz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different numbers of columns")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        searches = [("x", hz, hx), ("z", hx, hz)]
        rng.shuffle(searches)

        best: Optional[Tuple[str, int]] = None
        for basis_name, kernel_checks, stabilizer_rows in searches:
            found = search_basis(basis_name, kernel_checks, stabilizer_rows, nx, rng)
            if found is None:
                continue
            if best is None or found[1].bit_count() < best[1].bit_count():
                best = found

        if best is None:
            result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
        else:
            basis_name, vector = best
            result = {
                "status": "completed",
                "basis": basis_name,
                "vector": bits_to_list(vector, nx),
                "upper_bound": vector.bit_count(),
            }
    except Exception as exc:
        result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
        debug_path = None
        try:
            os.makedirs(args.output_dir, exist_ok=True)
            debug_path = os.path.join(args.output_dir, "candidate_error.txt")
            with open(debug_path, "w", encoding="utf-8") as handle:
                handle.write(str(exc) + "\n")
        except Exception:
            pass

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
