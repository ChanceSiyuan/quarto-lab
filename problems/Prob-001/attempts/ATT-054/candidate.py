#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def _row_to_int(row, n_cols: Optional[int] = None) -> Tuple[int, int]:
    if isinstance(row, str):
        bits = [1 if c == "1" else 0 for c in row.strip()]
    else:
        bits = [int(x) & 1 for x in row]
    n = len(bits) if n_cols is None else n_cols
    value = 0
    for i, bit in enumerate(bits[:n]):
        if bit:
            value |= 1 << i
    return value, n


def load_matrix(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        n = int(obj.get("n_cols", 0))
        rows = []
        for row in obj["data"]:
            value, width = _row_to_int(row, n if n else None)
            rows.append(value)
            n = max(n, width)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for sparse in obj["rows"]:
            value = 0
            for col in sparse:
                c = int(col)
                if c >= 0:
                    value ^= 1 << c
                    n = max(n, c + 1)
            rows.append(value)
        return rows, n

    if isinstance(obj, list):
        n = 0
        rows = []
        for row in obj:
            value, width = _row_to_int(row)
            rows.append(value)
            n = max(n, width)
        return rows, n

    raise ValueError(f"unsupported matrix JSON format: {path}")


def add_to_basis(basis: Dict[int, int], value: int) -> bool:
    x = value
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def make_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for row in rows:
        add_to_basis(basis, row)
    return basis


def reduce_by_basis(value: int, basis: Dict[int, int]) -> int:
    x = value
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(value: int, rows: Sequence[int]) -> bool:
    return reduce_by_basis(value, make_basis(rows)) == 0


def kernel_basis(check_rows: Sequence[int], n: int) -> List[int]:
    basis = make_basis(check_rows)
    pivot_cols = set(basis.keys())
    out = []
    for free in range(n):
        if free in pivot_cols:
            continue
        v = 1 << free
        for p in sorted(basis):
            row = basis[p]
            if ((row & ~(1 << p) & v).bit_count() & 1) != 0:
                v |= 1 << p
        out.append(v)
    return out


def syndrome(value: int, check_rows: Sequence[int]) -> int:
    s = 0
    for i, row in enumerate(check_rows):
        if ((value & row).bit_count() & 1) != 0:
            s |= 1 << i
    return s


def columns_as_syndromes(check_rows: Sequence[int], n: int) -> List[int]:
    cols = [0] * n
    for r, row in enumerate(check_rows):
        x = row
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c < n:
                cols[c] |= 1 << r
            x ^= lsb
    return cols


def vector_to_list(value: int, n: int) -> List[int]:
    return [(value >> i) & 1 for i in range(n)]


def verify(value: int, check_rows: Sequence[int], stab_rows: Sequence[int]) -> bool:
    return value != 0 and syndrome(value, check_rows) == 0 and not in_rowspace(value, stab_rows)


def reduce_weight_with_stabilizers(value: int, stab_rows: Sequence[int], rng: random.Random, rounds: int = 7) -> int:
    if value == 0:
        return value
    rows = [r for r in make_basis(stab_rows).values() if r]
    if not rows:
        return value

    best = value
    best_w = value.bit_count()
    ordered = rows[:]
    for rep in range(rounds):
        if rep:
            rng.shuffle(ordered)
        cur = best if rep < 2 else value
        improved = True
        passes = 0
        while improved and passes < 3:
            improved = False
            passes += 1
            for row in ordered:
                cand = cur ^ row
                if cand.bit_count() < cur.bit_count():
                    cur = cand
                    improved = True
        cw = cur.bit_count()
        if cw < best_w and cur:
            best, best_w = cur, cw
    return best


def random_coset_polish(value: int, stab_rows: Sequence[int], rng: random.Random, trials: int) -> int:
    rows = [r for r in make_basis(stab_rows).values() if r]
    best = value
    best_w = value.bit_count()
    if not rows:
        return best
    for _ in range(trials):
        cur = value
        # Heavy-tailed small stabilizer perturbations expose cheaper representatives.
        flips = 1 + int(rng.expovariate(0.7))
        for _j in range(min(flips, len(rows))):
            cur ^= rows[rng.randrange(len(rows))]
        cur = reduce_weight_with_stabilizers(cur, rows, rng, rounds=2)
        cw = cur.bit_count()
        if cur and cw < best_w:
            best, best_w = cur, cw
    return best


def biased_column_pool(cols: Sequence[int], n: int, rng: random.Random, focus: int) -> List[int]:
    weights = [(cols[i].bit_count(), i) for i in range(n)]
    weights.sort()
    low = [i for _w, i in weights[: max(1, min(n, focus))]]
    all_cols = list(range(n))
    pool = []
    for i in all_cols:
        if rng.random() < 0.35:
            pool.append(i)
    pool.extend(rng.sample(low, k=min(len(low), max(1, focus // 2))))
    if not pool:
        pool = all_cols
    rng.shuffle(pool)
    return list(dict.fromkeys(pool))


def mitm_random_search(
    check_rows: Sequence[int],
    stab_rows: Sequence[int],
    n: int,
    rng: random.Random,
    time_scale: int,
) -> Optional[int]:
    cols = columns_as_syndromes(check_rows, n)
    best: Optional[int] = None
    best_w = n + 1
    if n == 0:
        return None

    restarts = max(12, min(72, 18 + n // 5))
    for r in range(restarts):
        focus = max(8, min(n, 12 + (r % 6) * 6 + n // 12))
        pool = biased_column_pool(cols, n, rng, focus)
        if len(pool) < 2:
            continue
        split = len(pool) // 2
        left, right = pool[:split], pool[split:]
        max_piece = 1 + (r % 4)
        samples = max(160, min(3200, time_scale * (24 + 3 * n)))

        table: Dict[int, Tuple[int, int]] = {}
        table[0] = (0, 0)
        for _ in range(samples):
            k = 1 + min(max_piece, int(rng.expovariate(0.9)))
            k = min(k, len(left))
            vec = 0
            syn = 0
            for c in rng.sample(left, k):
                vec ^= 1 << c
                syn ^= cols[c]
            w = vec.bit_count()
            old = table.get(syn)
            if old is None or w < old[1]:
                table[syn] = (vec, w)

        for _ in range(samples):
            k = 1 + min(max_piece, int(rng.expovariate(0.9)))
            k = min(k, len(right))
            vec = 0
            syn = 0
            for c in rng.sample(right, k):
                vec ^= 1 << c
                syn ^= cols[c]
            mate = table.get(syn)
            if mate is None:
                continue
            cand = vec ^ mate[0]
            if cand == 0 or cand.bit_count() >= best_w:
                continue
            if verify(cand, check_rows, stab_rows):
                cand = random_coset_polish(cand, stab_rows, rng, trials=24)
                if verify(cand, check_rows, stab_rows):
                    cw = cand.bit_count()
                    if cw < best_w:
                        best, best_w = cand, cw
    return best


def fallback_logical(check_rows: Sequence[int], stab_rows: Sequence[int], n: int, rng: random.Random) -> Optional[int]:
    stab_basis = make_basis(stab_rows)
    nulls = kernel_basis(check_rows, n)
    logicals = []
    span = dict(stab_basis)
    for v in sorted(nulls, key=lambda x: x.bit_count()):
        if add_to_basis(span, v):
            logicals.append(v)

    best = None
    best_w = n + 1
    for v in logicals:
        if verify(v, check_rows, stab_rows):
            cand = random_coset_polish(v, stab_rows, rng, trials=max(64, min(512, 8 * n)))
            if verify(cand, check_rows, stab_rows) and cand.bit_count() < best_w:
                best, best_w = cand, cand.bit_count()

    if logicals:
        for _ in range(max(128, min(1200, 16 * n))):
            cand = 0
            for v in logicals:
                if rng.random() < 0.35:
                    cand ^= v
            if cand == 0:
                cand = logicals[rng.randrange(len(logicals))]
            cand = random_coset_polish(cand, stab_rows, rng, trials=10)
            if verify(cand, check_rows, stab_rows) and cand.bit_count() < best_w:
                best, best_w = cand, cand.bit_count()
    return best


def search_basis(name: str, check_rows: Sequence[int], stab_rows: Sequence[int], n: int, seed: int) -> Optional[Tuple[str, int]]:
    rng = random.Random((seed * 1315423911) ^ (0x9E3779B97F4A7C15 if name == "x" else 0xD1B54A32D192ED03))
    best = mitm_random_search(check_rows, stab_rows, n, rng, time_scale=1)
    fb = fallback_logical(check_rows, stab_rows, n, rng)
    if fb is not None and (best is None or fb.bit_count() < best.bit_count()):
        best = fb
    if best is None:
        return None
    best = reduce_weight_with_stabilizers(best, stab_rows, rng, rounds=10)
    if verify(best, check_rows, stab_rows):
        return name, best
    return None


def emit(status: str, basis, vector, upper_bound) -> None:
    print(json.dumps({"status": status, "basis": basis, "vector": vector, "upper_bound": upper_bound}, separators=(",", ":")))


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        candidates = []
        x = search_basis("x", hz, hx, n, args.seed)
        if x is not None:
            candidates.append(x)
        z = search_basis("z", hx, hz, n, args.seed)
        if z is not None:
            candidates.append(z)

        if not candidates:
            emit("failed", None, [], None)
            return 0

        basis, value = min(candidates, key=lambda item: (item[1].bit_count(), 0 if item[0] == "x" else 1))
        emit("completed", basis, vector_to_list(value, n), value.bit_count())
        return 0
    except Exception:
        # Preserve the one-object stdout contract even for malformed inputs.
        emit("failed", None, [], None)
        return 0


if __name__ == "__main__":
    sys.exit(main())
