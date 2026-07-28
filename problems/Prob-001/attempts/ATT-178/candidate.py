#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_matrix(path: str) -> List[int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            mask = 0
            for j, bit in enumerate(row):
                if int(bit) & 1:
                    mask ^= 1 << j
            rows.append(mask & ((1 << n_cols) - 1))
        return rows

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            mask = 0
            last = -1
            for j in row:
                j = int(j)
                if j <= last or j < 0 or j >= n_cols:
                    raise ValueError(f"invalid sparse row in {path}")
                mask ^= 1 << j
                last = j
            rows.append(mask)
        return rows

    raise ValueError(f"unrecognized matrix format in {path}")


def matrix_ncols(path: str) -> int:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "n_cols" in obj:
        return int(obj["n_cols"])
    if "num_cols" in obj:
        return int(obj["num_cols"])
    raise ValueError(f"unrecognized matrix format in {path}")


def rref_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for value in rows:
        x = int(value)
        while x:
            p = x.bit_length() - 1
            if p not in basis:
                basis[p] = x
                break
            x ^= basis[p]
    return basis


def in_rowspace(value: int, basis: Dict[int, int]) -> bool:
    x = int(value)
    while x:
        p = x.bit_length() - 1
        row = basis.get(p)
        if row is None:
            return False
        x ^= row
    return True


def rank(rows: Iterable[int]) -> int:
    return len(rref_basis(rows))


def nullspace_basis(checks: Sequence[int], n: int) -> List[int]:
    pivots = rref_basis(checks)
    pivot_cols = set(pivots)
    free_cols = [j for j in range(n) if j not in pivot_cols]
    out = []
    for free in free_cols:
        v = 1 << free
        for p in sorted(pivots):
            row = pivots[p] ^ (1 << p)
            if (row & v).bit_count() & 1:
                v ^= 1 << p
        out.append(v)
    return out


def kernel_ok(v: int, checks: Sequence[int]) -> bool:
    return all(((v & row).bit_count() & 1) == 0 for row in checks)


def to_bits(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def random_combo(rng: random.Random, basis: Sequence[int]) -> int:
    v = 0
    for row in basis:
        if rng.getrandbits(1):
            v ^= row
    if v == 0 and basis:
        v = rng.choice(basis)
    return v


def sparse_combo(rng: random.Random, basis: Sequence[int], terms: int) -> int:
    if not basis:
        return 0
    v = 0
    for row in rng.sample(list(basis), min(terms, len(basis))):
        v ^= row
    return v


def reduce_by_rows(v: int, rows: Sequence[int], passes: int = 3) -> int:
    cur = v
    cur_w = cur.bit_count()
    ordered = sorted([r for r in rows if r], key=lambda x: x.bit_count())
    for _ in range(passes):
        changed = False
        for row in ordered:
            nxt = cur ^ row
            nxt_w = nxt.bit_count()
            if nxt_w < cur_w:
                cur, cur_w = nxt, nxt_w
                changed = True
        if not changed:
            break
    return cur


def improve_coset(
    rng: random.Random,
    start: int,
    stabilizers: Sequence[int],
    rounds: int,
) -> int:
    best = reduce_by_rows(start, stabilizers, 4)
    best_w = best.bit_count()
    rows = [r for r in stabilizers if r]
    if not rows:
        return best

    for _ in range(rounds):
        trial = best
        for _ in range(1 + rng.randrange(4)):
            trial ^= rng.choice(rows)
        trial = reduce_by_rows(trial, rows, 2)
        w = trial.bit_count()
        if 0 < w < best_w:
            best, best_w = trial, w
    return best


def search_basis(
    rng: random.Random,
    name: str,
    kernel_checks: Sequence[int],
    stabilizers: Sequence[int],
    n: int,
) -> Optional[Tuple[str, int]]:
    ns = nullspace_basis(kernel_checks, n)
    if not ns:
        return None

    stab_basis = rref_basis(stabilizers)
    if rank(ns) <= rank(stabilizers):
        # There may still be a logical if the supplied matrices are inconsistent,
        # so let membership checks below decide rather than treating this as exact.
        pass

    candidates: List[int] = []
    candidates.extend(ns)
    for terms in (2, 3, 4, 6, 8):
        for _ in range(min(128, 8 * max(1, len(ns)))):
            candidates.append(sparse_combo(rng, ns, terms))

    best = 0
    best_w = n + 1
    budget = max(1600, min(40000, 200 * max(1, len(ns))))
    for i in range(budget):
        if i < len(candidates):
            v = candidates[i]
        else:
            v = random_combo(rng, ns)
        if v == 0 or in_rowspace(v, stab_basis):
            continue
        v = improve_coset(rng, v, stabilizers, 12)
        if v and not in_rowspace(v, stab_basis) and kernel_ok(v, kernel_checks):
            w = v.bit_count()
            if w < best_w:
                best, best_w = v, w

    if best:
        return name, best
    return None


def emit(status: str, basis: Optional[str], vector: Sequence[int], upper_bound: Optional[int]) -> None:
    print(
        json.dumps(
            {
                "status": status,
                "basis": basis,
                "vector": list(vector),
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
        hx = load_matrix(args.hx)
        hz = load_matrix(args.hz)
        n = matrix_ncols(args.hx)
        if matrix_ncols(args.hz) != n:
            raise ValueError("hx and hz have different column counts")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        searches = [
            ("x", hz, hx),
            ("z", hx, hz),
        ]
        rng.shuffle(searches)

        found: List[Tuple[str, int]] = []
        for basis, kernel_checks, stabilizers in searches:
            hit = search_basis(rng, basis, kernel_checks, stabilizers, n)
            if hit is not None:
                found.append(hit)

        if found:
            basis, v = min(found, key=lambda item: item[1].bit_count())
            checks = hz if basis == "x" else hx
            stabs = hx if basis == "x" else hz
            if kernel_ok(v, checks) and not in_rowspace(v, rref_basis(stabs)):
                emit("completed", basis, to_bits(v, n), v.bit_count())
                return 0

        emit("failed", "x", [0] * n, None)
        return 0
    except Exception as exc:
        sys.stderr.write(f"candidate.py error: {exc}\n")
        emit("failed", "x", [], None)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
