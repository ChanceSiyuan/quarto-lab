#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_json_arg(value: str):
    if value == "-":
        return json.load(sys.stdin)  # type: ignore[name-defined]
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(value)


def parse_matrix(value: str) -> Tuple[List[int], int, int]:
    obj = load_json_arg(value)
    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            x = 0
            for j, bit in enumerate(r):
                if int(bit) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, len(rows), n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or row list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        data = obj["data"]
        if data and all(isinstance(r, list) for r in data):
            rows_data = data
        else:
            if n <= 0:
                raise ValueError("dense matrix needs n_cols")
            rows_data = [data[i : i + n] for i in range(0, len(data), n)]
        rows = []
        for r in rows_data:
            if n == 0:
                n = len(r)
            x = 0
            for j, bit in enumerate(r[:n]):
                if int(bit) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, len(rows), n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for inds in obj["rows"]:
            x = 0
            for j in inds:
                jj = int(j)
                if jj < 0:
                    raise ValueError("negative sparse column index")
                x |= 1 << jj
                if jj + 1 > n:
                    n = jj + 1
            rows.append(x)
        return rows, len(rows), n

    raise ValueError("unrecognized matrix format")


def parity(x: int) -> int:
    return x.bit_count() & 1


def syndrome(rows: Sequence[int], v: int) -> int:
    s = 0
    for i, r in enumerate(rows):
        if parity(r & v):
            s |= 1 << i
    return s


def add_to_high_basis(basis: Dict[int, int], v: int) -> bool:
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def make_high_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis: Dict[int, int] = {}
    for r in rows:
        add_to_high_basis(basis, r)
    return basis


def reduce_high(basis: Dict[int, int], v: int) -> int:
    x = v
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(basis: Dict[int, int], v: int) -> bool:
    return reduce_high(basis, v) == 0


def nullspace_basis(rows: Sequence[int], n: int) -> List[int]:
    mat = [r & ((1 << n) - 1) for r in rows if r]
    pivots: List[int] = []
    rank = 0
    for c in range(n):
        pivot = None
        for i in range(rank, len(mat)):
            if (mat[i] >> c) & 1:
                pivot = i
                break
        if pivot is None:
            continue
        mat[rank], mat[pivot] = mat[pivot], mat[rank]
        for i in range(len(mat)):
            if i != rank and ((mat[i] >> c) & 1):
                mat[i] ^= mat[rank]
        pivots.append(c)
        rank += 1
        if rank == len(mat):
            break

    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    out: List[int] = []
    for f in free_cols:
        v = 1 << f
        for i, p in enumerate(pivots):
            if (mat[i] >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def verify(v: int, check_rows: Sequence[int], stab_basis: Dict[int, int], n: int) -> bool:
    if v == 0 or (v >> n):
        return False
    return syndrome(check_rows, v) == 0 and not in_rowspace(stab_basis, v)


def int_to_bits(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def column_syndromes(check_rows: Sequence[int], n: int) -> List[int]:
    cols = [0] * n
    for i, row in enumerate(check_rows):
        x = row
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            if j < n:
                cols[j] |= 1 << i
            x ^= lsb
    return cols


def solve_syndrome_random(cols: Sequence[int], target: int, order: Sequence[int]) -> Optional[int]:
    basis: Dict[int, Tuple[int, int]] = {}
    for j in order:
        x = cols[j]
        combo = 1 << j
        while x:
            p = x.bit_length() - 1
            item = basis.get(p)
            if item is None:
                basis[p] = (x, combo)
                break
            x ^= item[0]
            combo ^= item[1]

    x = target
    combo = 0
    while x:
        p = x.bit_length() - 1
        item = basis.get(p)
        if item is None:
            return None
        x ^= item[0]
        combo ^= item[1]
    return combo


def random_error(n: int, rng: random.Random, col_weight: Sequence[int]) -> int:
    if n <= 0:
        return 0
    avg = sum(col_weight) / max(1, n)
    base = rng.choice([0.035, 0.055, 0.08, 0.12, 0.18])
    v = 0
    for j, w in enumerate(col_weight):
        rel = 1.0 / (1.0 + max(0.0, w - avg) * 0.35)
        if rng.random() < min(0.45, base * rel):
            v |= 1 << j
    if v == 0:
        v = 1 << rng.randrange(n)
    return v


def stabilizer_descent(
    v: int,
    stab_rows: Sequence[int],
    check_rows: Sequence[int],
    stab_basis: Dict[int, int],
    n: int,
    rng: random.Random,
    rounds: int,
) -> int:
    if not stab_rows:
        return v
    cur = v
    best = v
    best_w = v.bit_count()
    rows = [r & ((1 << n) - 1) for r in stab_rows if r]

    for t in range(rounds):
        improved = False
        rng.shuffle(rows)
        for r in rows:
            w0 = cur.bit_count()
            nxt = cur ^ r
            w1 = nxt.bit_count()
            if w1 < w0 or (w1 == w0 and rng.random() < 0.015):
                cur = nxt
                improved = improved or w1 < w0
                if w1 < best_w and verify(cur, check_rows, stab_basis, n):
                    best = cur
                    best_w = w1
        if not improved:
            # A small perturbation by stabilizers can escape a shallow local minimum
            # without changing the represented logical coset.
            for _ in range(1 + (t % 3)):
                cur ^= rows[rng.randrange(len(rows))]
            if cur.bit_count() > best_w + max(8, n // 18):
                cur = best
    return best


def quotient_representatives(
    kernel: Sequence[int], stab_basis: Dict[int, int], rng: random.Random, limit: int
) -> List[int]:
    span = dict(stab_basis)
    reps: List[int] = []
    ordered = list(kernel)
    ordered.sort(key=lambda x: (x.bit_count(), rng.random()))
    for v in ordered:
        if reduce_high(span, v) != 0:
            reps.append(v)
            add_to_high_basis(span, v)
            if len(reps) >= limit:
                break

    # Random combinations of kernel vectors often give a better coset seed than
    # the raw nullspace basis vector selected by elimination.
    attempts = min(600, 30 * max(1, len(kernel)))
    for _ in range(attempts):
        if len(reps) >= limit:
            break
        v = 0
        take = 1 + rng.randrange(min(6, max(1, len(kernel))))
        for j in rng.sample(range(len(kernel)), min(take, len(kernel))):
            v ^= kernel[j]
        if v and reduce_high(span, v) != 0:
            reps.append(v)
            add_to_high_basis(span, v)
    return reps


def search_basis(
    name: str,
    check_rows: Sequence[int],
    stab_rows: Sequence[int],
    n: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    stab_basis = make_high_basis(stab_rows)
    cols = column_syndromes(check_rows, n)
    col_w = [c.bit_count() for c in cols]
    best: Optional[int] = None

    residual_trials = 900 if n <= 256 else 420
    residual_trials = max(120, min(residual_trials, 12000 // max(1, n.bit_length())))
    for _ in range(residual_trials):
        e = random_error(n, rng, col_w)
        s = syndrome(check_rows, e)
        if s == 0:
            r = e
        else:
            order = list(range(n))
            # Perturbed residual decoding: columns touched by the sampled error
            # are made more likely but not forced, yielding varied same-syndrome
            # decodes whose difference is a kernel element.
            order.sort(
                key=lambda j: (
                    0 if ((e >> j) & 1 and rng.random() < 0.72) else 1,
                    col_w[j] + rng.random() * (2.5 + 0.03 * n),
                )
            )
            d = solve_syndrome_random(cols, s, order)
            if d is None:
                continue
            r = e ^ d
        if r and verify(r, check_rows, stab_basis, n):
            r = stabilizer_descent(r, stab_rows, check_rows, stab_basis, n, rng, 10)
            if verify(r, check_rows, stab_basis, n) and (
                best is None or r.bit_count() < best.bit_count()
            ):
                best = r

    kernel = nullspace_basis(check_rows, n)
    reps = quotient_representatives(kernel, stab_basis, rng, limit=48)
    for rep in reps:
        if verify(rep, check_rows, stab_basis, n):
            cand = stabilizer_descent(rep, stab_rows, check_rows, stab_basis, n, rng, 18)
            if verify(cand, check_rows, stab_basis, n) and (
                best is None or cand.bit_count() < best.bit_count()
            ):
                best = cand

    if best is None:
        return None
    return name, best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    try:
        hx, _, nx = parse_matrix(args.hx)
        hz, _, nz = parse_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        rng = random.Random(args.seed)

        choices = [
            search_basis("x", hz, hx, n, random.Random(rng.randrange(1 << 62))),
            search_basis("z", hx, hz, n, random.Random(rng.randrange(1 << 62))),
        ]
        choices = [c for c in choices if c is not None]
        if choices:
            basis, vec = min(choices, key=lambda item: item[1].bit_count())
            out = {
                "status": "completed",
                "basis": basis,
                "vector": int_to_bits(vec, n),
                "upper_bound": int(vec.bit_count()),
            }
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
