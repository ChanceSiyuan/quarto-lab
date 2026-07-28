#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _matrix_to_rows(obj) -> Tuple[List[int], int]:
    if isinstance(obj, str):
        obj = _load_json(obj)
    if isinstance(obj, dict) and "matrix" in obj and isinstance(obj["matrix"], (dict, list)):
        obj = obj["matrix"]

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    rows: List[int] = []
    n_cols: Optional[int] = None

    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        n_cols = int(obj.get("n_cols", 0))
        if n_cols <= 0 and data:
            n_cols = len(data[0])
        for row in data:
            bits = 0
            for j, val in enumerate(row):
                if val & 1:
                    bits |= 1 << j
            rows.append(bits)
    elif isinstance(obj, dict) and "rows" in obj:
        data = obj["rows"]
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        for row in data:
            bits = 0
            for j in row:
                jj = int(j)
                if jj >= 0:
                    bits |= 1 << jj
                    if n_cols <= jj:
                        n_cols = jj + 1
            rows.append(bits)
    elif isinstance(obj, list):
        if not obj:
            return [], 0
        if all(isinstance(r, list) for r in obj):
            if all((not r) or all(isinstance(x, int) and x in (0, 1) for x in r) for r in obj):
                n_cols = max((len(r) for r in obj), default=0)
                for row in obj:
                    bits = 0
                    for j, val in enumerate(row):
                        if val & 1:
                            bits |= 1 << j
                    rows.append(bits)
            else:
                n_cols = 0
                for row in obj:
                    bits = 0
                    for j in row:
                        jj = int(j)
                        bits |= 1 << jj
                        n_cols = max(n_cols, jj + 1)
                    rows.append(bits)
        else:
            raise ValueError("matrix list must contain rows")
    else:
        raise ValueError("unsupported matrix format")

    assert n_cols is not None
    mask = (1 << n_cols) - 1 if n_cols > 0 else 0
    return [r & mask for r in rows if r & mask], n_cols


def _rref(rows: Sequence[int], n: int, order: Optional[Sequence[int]] = None) -> Tuple[List[int], List[int]]:
    work = [r for r in rows if r]
    piv_rows: List[int] = []
    piv_cols: List[int] = []
    cols = list(range(n)) if order is None else list(order)
    rank = 0
    for col in cols:
        bit = 1 << col
        pivot_at = -1
        for i in range(rank, len(work)):
            if work[i] & bit:
                pivot_at = i
                break
        if pivot_at < 0:
            continue
        work[rank], work[pivot_at] = work[pivot_at], work[rank]
        prow = work[rank]
        for i in range(len(work)):
            if i != rank and (work[i] & bit):
                work[i] ^= prow
        piv_rows.append(work[rank])
        piv_cols.append(col)
        rank += 1
        if rank == len(work):
            break
    return piv_rows, piv_cols


def _reduce_by_basis(v: int, basis: Sequence[int], pivots: Sequence[int]) -> int:
    x = v
    for row, col in zip(basis, pivots):
        if (x >> col) & 1:
            x ^= row
    return x


def _in_rowspace(v: int, basis: Sequence[int], pivots: Sequence[int]) -> bool:
    return _reduce_by_basis(v, basis, pivots) == 0


def _syndrome_zero(rows: Sequence[int], v: int) -> bool:
    for r in rows:
        if (r & v).bit_count() & 1:
            return False
    return True


def _nullspace_basis(rows: Sequence[int], n: int, order: Optional[Sequence[int]] = None) -> List[int]:
    rbasis, pivots = _rref(rows, n, order)
    pivot_set = set(pivots)
    if order is None:
        cols = list(range(n))
    else:
        cols = list(order)
    free_cols = [c for c in cols if c not in pivot_set]
    out: List[int] = []
    for f in free_cols:
        v = 1 << f
        for row, p in zip(rbasis, pivots):
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def _column_degrees(rows: Sequence[int], n: int) -> List[int]:
    deg = [0] * n
    for r in rows:
        x = r
        while x:
            lsb = x & -x
            deg[lsb.bit_length() - 1] += 1
            x ^= lsb
    return deg


def _bits(v: int) -> Iterable[int]:
    x = v
    while x:
        lsb = x & -x
        yield lsb.bit_length() - 1
        x ^= lsb


def _coset_descent(v: int, stab_rows: Sequence[int], rng: random.Random, limit: int = 80) -> int:
    cur = v
    cur_w = cur.bit_count()
    rows = [r for r in stab_rows if r]
    if not rows:
        return cur
    rows.sort(key=lambda x: x.bit_count())
    passes = 0
    while passes < limit:
        improved = False
        if passes & 3 == 3:
            rng.shuffle(rows)
        for r in rows:
            nw = (cur ^ r).bit_count()
            if nw < cur_w or (nw == cur_w and rng.random() < 0.015):
                cur ^= r
                cur_w = nw
                improved = True
        if not improved:
            break
        passes += 1
    return cur


def _verify(v: int, check_rows: Sequence[int], stab_basis: Sequence[int], stab_pivots: Sequence[int]) -> bool:
    return v != 0 and _syndrome_zero(check_rows, v) and not _in_rowspace(v, stab_basis, stab_pivots)


def _adaptive_kernel_search(
    check_rows: Sequence[int],
    stab_rows: Sequence[int],
    n: int,
    rng: random.Random,
) -> Optional[int]:
    stab_basis, stab_pivots = _rref(stab_rows, n)
    degrees = _column_degrees(check_rows, n)
    max_deg = max(max(degrees), 1) if degrees else 1
    attract = [0.0] * n
    fatigue = [0.0] * n
    best: Optional[int] = None
    best_w = n + 1

    if n <= 80:
        trials = 260
    elif n <= 240:
        trials = 170
    elif n <= 800:
        trials = 95
    else:
        trials = 45

    for t in range(trials):
        temp = max(0.05, 1.25 * (0.985 ** t))
        scored = []
        for c in range(n):
            base = degrees[c] / max_deg
            noise = -math.log(-math.log(max(1e-12, rng.random())))
            score = base + fatigue[c] - attract[c] + temp * noise
            scored.append((score, c))
        # Expensive or fatigued columns are consumed as pivots first, leaving
        # attractive columns free so single-free-variable kernel vectors tend
        # to be supported where previous low-weight attempts succeeded.
        order = [c for _, c in sorted(scored, reverse=True)]
        ns = _nullspace_basis(check_rows, n, order)
        if not ns:
            continue
        ns.sort(key=lambda v: (v.bit_count(), rng.random()))

        pool = ns[: min(len(ns), 10 + int(math.sqrt(n + 1)))]
        candidates: List[int] = []
        candidates.extend(pool[: min(8, len(pool))])
        for _ in range(min(10, len(pool) * 2)):
            v = 0
            take = 1 + (rng.random() < 0.35) + (rng.random() < 0.10)
            for b in rng.sample(pool, min(int(take), len(pool))):
                v ^= b
            if v:
                candidates.append(v)

        for cand in candidates:
            v = _coset_descent(cand, stab_rows, rng)
            w = v.bit_count()
            good_kernel = _syndrome_zero(check_rows, v)
            if good_kernel and _verify(v, check_rows, stab_basis, stab_pivots):
                if w < best_w:
                    best = v
                    old = best_w
                    best_w = w
                    reward = 0.18 if old == n + 1 else min(0.35, (old - w + 1) / max(8.0, old))
                    for c in _bits(v):
                        attract[c] += reward
                    if best_w <= 1:
                        return best
                else:
                    for c in _bits(v):
                        attract[c] += 0.015
            else:
                bump = 0.01 if good_kernel else 0.02
                for c in _bits(cand):
                    fatigue[c] += bump

        if t % 20 == 19:
            for c in range(n):
                attract[c] *= 0.88
                fatigue[c] *= 0.80

    return best


def _fallback_witness(
    check_rows: Sequence[int],
    stab_rows: Sequence[int],
    n: int,
    rng: random.Random,
) -> Optional[int]:
    stab_basis, stab_pivots = _rref(stab_rows, n)
    ns = _nullspace_basis(check_rows, n)
    if not ns:
        return None

    best: Optional[int] = None
    best_w = n + 1
    # Basis-derived fallback: find any kernel basis direction outside the
    # stabilizer span, then try a small randomized recombination pass.
    for b in sorted(ns, key=lambda x: x.bit_count()):
        v = _coset_descent(b, stab_rows, rng, limit=120)
        if _verify(v, check_rows, stab_basis, stab_pivots) and v.bit_count() < best_w:
            best, best_w = v, v.bit_count()

    pool = sorted(ns, key=lambda x: x.bit_count())[: min(len(ns), 32)]
    if pool:
        for _ in range(160):
            v = 0
            take = 1 + rng.randrange(min(6, len(pool)))
            for b in rng.sample(pool, take):
                v ^= b
            v = _coset_descent(v, stab_rows, rng, limit=120)
            if _verify(v, check_rows, stab_basis, stab_pivots) and v.bit_count() < best_w:
                best, best_w = v, v.bit_count()
    return best


def _solve_basis(
    basis_name: str,
    hx_rows: Sequence[int],
    hz_rows: Sequence[int],
    n: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    if basis_name == "x":
        check_rows, stab_rows = hz_rows, hx_rows
    else:
        check_rows, stab_rows = hx_rows, hz_rows
    v = _adaptive_kernel_search(check_rows, stab_rows, n, rng)
    if v is None:
        v = _fallback_witness(check_rows, stab_rows, n, rng)
    if v is None:
        return None
    stab_basis, stab_pivots = _rref(stab_rows, n)
    if _verify(v, check_rows, stab_basis, stab_pivots):
        return basis_name, v
    return None


def _vector_list(v: int, n: int) -> List[int]:
    return [int((v >> i) & 1) for i in range(n)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    try:
        hx_rows, nx = _matrix_to_rows(args.hx)
        hz_rows, nz = _matrix_to_rows(args.hz)
        n = max(nx, nz)
        if n <= 0:
            raise ValueError("empty code")
        mask = (1 << n) - 1
        hx_rows = [r & mask for r in hx_rows if r & mask]
        hz_rows = [r & mask for r in hz_rows if r & mask]

        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        attempts = ["x", "z"]
        rng.shuffle(attempts)
        found: List[Tuple[str, int]] = []
        for b in attempts:
            local = random.Random((args.seed + 0x9E3779B97F4A7C15 + (b == "z")) & ((1 << 64) - 1))
            ans = _solve_basis(b, hx_rows, hz_rows, n, local)
            if ans is not None:
                found.append(ans)

        if found:
            basis, vec = min(found, key=lambda item: (item[1].bit_count(), item[0]))
            out = {
                "status": "completed",
                "basis": basis,
                "vector": _vector_list(vec, n),
                "upper_bound": int(vec.bit_count()),
            }
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
