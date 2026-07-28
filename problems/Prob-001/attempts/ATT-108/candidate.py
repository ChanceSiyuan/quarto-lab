#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Tuple


def fail() -> None:
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))


def row_weight(x: int) -> int:
    return x.bit_count()


def parity(x: int) -> int:
    return x.bit_count() & 1


def parse_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    rows: List[int] = []
    if isinstance(obj, dict) and {"n_rows", "n_cols", "data"} <= set(obj):
        n = int(obj["n_cols"])
        data = obj["data"]
        if int(obj["n_rows"]) != len(data):
            raise ValueError("dense row count mismatch")
        for row in data:
            if len(row) != n:
                raise ValueError("dense row width mismatch")
            bits = 0
            for i, value in enumerate(row):
                if int(value) not in (0, 1):
                    raise ValueError("non-binary dense entry")
                if int(value):
                    bits |= 1 << i
            rows.append(bits)
        return rows, n

    if isinstance(obj, dict) and {"num_cols", "rows"} <= set(obj):
        n = int(obj["num_cols"])
        for row in obj["rows"]:
            bits = 0
            prev = -1
            for col in row:
                c = int(col)
                if c <= prev or c < 0 or c >= n:
                    raise ValueError("invalid sparse row")
                bits |= 1 << c
                prev = c
            rows.append(bits)
        return rows, n

    raise ValueError("unrecognized matrix format")


def echelon(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for row in rows:
        x = row
        while x:
            pivot = (x & -x).bit_length() - 1
            b = basis.get(pivot)
            if b is None:
                basis[pivot] = x
                break
            x ^= b
    return basis


def reduce_with_basis(x: int, basis: Dict[int, int]) -> int:
    y = x
    while y:
        pivot = (y & -y).bit_length() - 1
        b = basis.get(pivot)
        if b is None:
            return y
        y ^= b
    return 0


def in_rowspace(x: int, rows: Iterable[int]) -> bool:
    return reduce_with_basis(x, echelon(rows)) == 0


def nullspace_basis(rows: Iterable[int], n: int) -> List[int]:
    pivots = echelon(rows)
    pivot_cols = set(pivots)
    free_cols = [i for i in range(n) if i not in pivot_cols]
    out: List[int] = []
    ordered_pivots = sorted(pivots, reverse=True)
    for free in free_cols:
        v = 1 << free
        for p in ordered_pivots:
            row = pivots[p]
            if parity(row & ~(1 << p) & v):
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v: int, checks: Iterable[int]) -> bool:
    return all(parity(v & row) == 0 for row in checks)


def verify(v: int, kernel_checks: List[int], stabilizers: List[int]) -> bool:
    if v == 0:
        return False
    return syndrome_zero(v, kernel_checks) and not in_rowspace(v, stabilizers)


def to_vector(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def random_kernel_vector(kbasis: List[int], rng: random.Random) -> int:
    v = 0
    for row in kbasis:
        if rng.getrandbits(1):
            v ^= row
    if v == 0 and kbasis:
        v = rng.choice(kbasis)
    return v


def greedy_reduce(v: int, stabilizers: List[int], rng: random.Random, passes: int) -> int:
    if not stabilizers:
        return v
    rows = [r for r in stabilizers if r]
    rows.sort(key=row_weight)
    cur = v
    cur_w = row_weight(cur)
    for _ in range(passes):
        changed = False
        if len(rows) > 1:
            split = max(1, min(len(rows), len(rows) // 3 + 1))
            prefix = rows[:split]
            suffix = rows[split:]
            rng.shuffle(prefix)
            rng.shuffle(suffix)
            order = prefix + suffix
        else:
            order = rows
        for r in order:
            nxt = cur ^ r
            nxt_w = row_weight(nxt)
            if nxt_w < cur_w:
                cur, cur_w = nxt, nxt_w
                changed = True
        if not changed:
            break
    return cur


def improve_candidate(v: int, stabilizers: List[int], rng: random.Random, n: int) -> int:
    best = greedy_reduce(v, stabilizers, rng, 6)
    best_w = row_weight(best)
    if not stabilizers:
        return best

    restarts = min(64, max(8, n // 2))
    rows = [r for r in stabilizers if r]
    for _ in range(restarts):
        trial = v
        flips = 1 + rng.randrange(max(1, min(12, len(rows))))
        for _ in range(flips):
            trial ^= rng.choice(rows)
        trial = greedy_reduce(trial, rows, rng, 4)
        wt = row_weight(trial)
        if wt < best_w:
            best, best_w = trial, wt
    return best


def search_basis(
    label: str,
    kernel_checks: List[int],
    stabilizers: List[int],
    n: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    kbasis = nullspace_basis(kernel_checks, n)
    if not kbasis:
        return None

    candidates: List[int] = []
    shuffled = kbasis[:]
    rng.shuffle(shuffled)
    candidates.extend(shuffled)

    trials = min(4096, max(256, 16 * len(kbasis) + 8 * n))
    for _ in range(trials):
        candidates.append(random_kernel_vector(kbasis, rng))

    best: Optional[int] = None
    best_w: Optional[int] = None
    for cand in candidates:
        if cand == 0 or in_rowspace(cand, stabilizers):
            continue
        reduced = improve_candidate(cand, stabilizers, rng, n)
        if verify(reduced, kernel_checks, stabilizers):
            wt = row_weight(reduced)
            if best is None or best_w is None or wt < best_w:
                best, best_w = reduced, wt
                if wt == 1:
                    break
    if best is None:
        return None
    return label, best


def write_aux(output_dir: Optional[str], result: dict) -> None:
    if not output_dir:
        return
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "candidate_result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, separators=(",", ":"))
        f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    try:
        hx, nx = parse_matrix(args.hx)
        hz, nz = parse_matrix(args.hz)
        if nx != nz:
            raise ValueError("matrix width mismatch")
        n = nx
        rng = random.Random(args.seed)

        searches = [
            ("x", hz, hx),
            ("z", hx, hz),
        ]
        rng.shuffle(searches)

        best_label: Optional[str] = None
        best_vec: Optional[int] = None
        for label, kernel_checks, stabilizers in searches:
            hit = search_basis(label, kernel_checks, stabilizers, n, rng)
            if hit is None:
                continue
            hit_label, hit_vec = hit
            if best_vec is None or row_weight(hit_vec) < row_weight(best_vec):
                best_label, best_vec = hit_label, hit_vec

        if best_vec is None or best_label is None:
            result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
        else:
            result = {
                "status": "completed",
                "basis": best_label,
                "vector": to_vector(best_vec, n),
                "upper_bound": row_weight(best_vec),
            }
        write_aux(args.output_dir, result)
        print(json.dumps(result, separators=(",", ":")))
        return 0
    except Exception:
        fail()
        return 0


if __name__ == "__main__":
    sys.exit(main())
