#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def rows_from_json(path: str) -> Tuple[List[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        return dense_to_bits(obj, n), n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or dense row list")

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        return dense_to_bits(data, n), n

    if "rows" in obj:
        rows = obj["rows"]
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = 1 + max((c for r in rows for c in r), default=-1)
        out = []
        for r in rows:
            x = 0
            for c in r:
                ci = int(c)
                if 0 <= ci < n:
                    x ^= 1 << ci
            out.append(x)
        return out, n

    raise ValueError("unsupported matrix JSON format")


def dense_to_bits(data: Sequence[Sequence[int]], n: int) -> List[int]:
    out = []
    for row in data:
        x = 0
        for i, v in enumerate(row[:n]):
            if int(v) & 1:
                x |= 1 << i
        out.append(x)
    return out


def normalize_width(rows: List[int], n: int) -> List[int]:
    if n <= 0:
        return rows
    mask = (1 << n) - 1
    return [r & mask for r in rows]


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


def reduced_row_basis(rows: Iterable[int]) -> Dict[int, int]:
    basis = row_basis(rows)
    for p in sorted(basis):
        rp = basis[p]
        for q in sorted(basis):
            if q > p and ((basis[q] >> p) & 1):
                basis[q] ^= rp
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


def kernel_basis(check_rows: Sequence[int], n: int) -> List[int]:
    piv = reduced_row_basis(check_rows)
    pivot_cols = set(piv)
    out: List[int] = []
    for free in range(n):
        if free in pivot_cols:
            continue
        v = 1 << free
        for p, row in piv.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v: int, checks: Sequence[int]) -> bool:
    for r in checks:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def bit_positions(x: int) -> List[int]:
    pos = []
    while x:
        lsb = x & -x
        pos.append(lsb.bit_length() - 1)
        x ^= lsb
    return pos


def vector_list(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def build_col_to_rows(rows: Sequence[int], n: int) -> List[List[int]]:
    adj: List[List[int]] = [[] for _ in range(n)]
    for ri, r in enumerate(rows):
        x = r
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c < n:
                adj[c].append(ri)
            x ^= lsb
    return adj


def candidate_rows_from_support(
    v: int,
    col_to_rows: Sequence[Sequence[int]],
    m: int,
    rng: random.Random,
    cap: int,
) -> List[int]:
    if m == 0:
        return []
    seen = set()
    cols = bit_positions(v)
    if len(cols) > 96:
        cols = rng.sample(cols, 96)
    for c in cols:
        for ri in col_to_rows[c]:
            seen.add(ri)
            if len(seen) >= cap:
                break
        if len(seen) >= cap:
            break
    while len(seen) < min(cap, m):
        seen.add(rng.randrange(m))
    return list(seen)


def perturb_near_graph(
    v: int,
    rows: Sequence[int],
    col_to_rows: Sequence[Sequence[int]],
    rng: random.Random,
    strength: int,
) -> int:
    m = len(rows)
    if m == 0:
        return v
    y = v
    frontier = candidate_rows_from_support(y, col_to_rows, m, rng, min(max(16, strength * 8), m))
    for _ in range(strength):
        if frontier and rng.random() < 0.8:
            ri = rng.choice(frontier)
        else:
            ri = rng.randrange(m)
        y ^= rows[ri]
        touched = bit_positions(rows[ri])
        if touched:
            c = rng.choice(touched)
            frontier.extend(col_to_rows[c][:16])
            if len(frontier) > 256:
                frontier = rng.sample(frontier, 256)
    return y


def greedy_polish(v: int, rows: Sequence[int], passes: int = 4) -> int:
    y = v
    for _ in range(passes):
        improved = False
        base_w = y.bit_count()
        for r in rows:
            z = y ^ r
            zw = z.bit_count()
            if zw < base_w:
                y = z
                base_w = zw
                improved = True
        if not improved:
            break
    return y


def tabu_descent(
    start: int,
    stab_rows: Sequence[int],
    col_to_rows: Sequence[Sequence[int]],
    rng: random.Random,
    n: int,
    budget: int,
) -> int:
    m = len(stab_rows)
    if m == 0:
        return start

    v = start
    best = start
    best_w = start.bit_count()
    tabu_until = [0] * m
    tenure_base = 7 + int(m ** 0.5)
    stale = 0
    cap = min(m, 160 if n < 1000 else 260)

    for it in range(max(1, budget)):
        cur_w = v.bit_count()
        rows = candidate_rows_from_support(v, col_to_rows, m, rng, cap)
        chosen = -1
        chosen_delta = 10**9
        chosen_w = 10**9

        for ri in rows:
            r = stab_rows[ri]
            nw = (v ^ r).bit_count()
            delta = nw - cur_w
            aspiration = nw < best_w
            if it < tabu_until[ri] and not aspiration:
                continue
            noisy_delta = delta + (1 if rng.random() < 0.025 else 0)
            if noisy_delta < chosen_delta or (noisy_delta == chosen_delta and nw < chosen_w):
                chosen = ri
                chosen_delta = noisy_delta
                chosen_w = nw

        if chosen >= 0 and (chosen_w <= cur_w or stale > 10):
            v ^= stab_rows[chosen]
            tabu_until[chosen] = it + tenure_base + rng.randrange(tenure_base + 1)
        else:
            strength = 2 + min(10, stale // 7)
            v = perturb_near_graph(v, stab_rows, col_to_rows, rng, strength)

        vw = v.bit_count()
        if vw < best_w:
            best = v
            best_w = vw
            stale = 0
        else:
            stale += 1

        if stale > 35:
            v = perturb_near_graph(best, stab_rows, col_to_rows, rng, 3 + rng.randrange(8))
            stale = 0

    return greedy_polish(best, stab_rows)


def logical_seeds(
    null_basis: Sequence[int],
    stab_basis: Dict[int, int],
    rng: random.Random,
    n: int,
) -> List[int]:
    seeds: List[int] = []
    shuffled = list(null_basis)
    rng.shuffle(shuffled)

    for v in sorted(shuffled, key=lambda x: x.bit_count())[: min(len(shuffled), 80)]:
        if v and not in_rowspace(v, stab_basis):
            seeds.append(v)

    nb = list(null_basis)
    trials = min(180, max(30, 4 * len(nb)))
    for _ in range(trials):
        if not nb:
            break
        y = 0
        take = 1 + rng.randrange(min(len(nb), max(2, min(16, n.bit_length() + 3))))
        for v in rng.sample(nb, take):
            if rng.random() < 0.75:
                y ^= v
        if y and not in_rowspace(y, stab_basis):
            seeds.append(y)

    uniq = []
    seen = set()
    for v in seeds:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def search_basis(
    name: str,
    checks: Sequence[int],
    stabilizers: Sequence[int],
    n: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    stab_basis = row_basis(stabilizers)
    null_basis = kernel_basis(checks, n)
    seeds = logical_seeds(null_basis, stab_basis, rng, n)
    if not seeds:
        return None

    stab_rows = [r for r in stabilizers if r]
    col_to_rows = build_col_to_rows(stab_rows, n)
    best = None
    best_w = 10**9
    ordered = sorted(seeds, key=lambda x: x.bit_count())
    max_seeds = min(len(ordered), 32)
    budget = max(60, min(1200, 12 * len(stab_rows) + 4 * n))

    for i, seed in enumerate(ordered[:max_seeds]):
        start = seed
        if i:
            start = perturb_near_graph(seed, stab_rows, col_to_rows, rng, 1 + rng.randrange(8))
        cand = tabu_descent(start, stab_rows, col_to_rows, rng, n, budget)
        if syndrome_zero(cand, checks) and not in_rowspace(cand, stab_basis):
            w = cand.bit_count()
            if w < best_w:
                best = cand
                best_w = w

    if best is None:
        for seed in ordered:
            if syndrome_zero(seed, checks) and not in_rowspace(seed, stab_basis):
                best = seed
                best_w = seed.bit_count()
                break

    if best is None:
        return None
    return name, best


def solve(hx_path: str, hz_path: str, seed: int) -> Dict[str, object]:
    hx, nx = rows_from_json(hx_path)
    hz, nz = rows_from_json(hz_path)
    n = max(nx, nz)
    hx = normalize_width(hx, n)
    hz = normalize_width(hz, n)
    rng = random.Random(seed)

    results = []
    for name, checks, stabilizers in (("x", hz, hx), ("z", hx, hz)):
        sub_rng = random.Random(rng.randrange(1 << 62))
        res = search_basis(name, checks, stabilizers, n, sub_rng)
        if res is not None:
            basis, v = res
            results.append((v.bit_count(), basis, v))

    if not results:
        return {"status": "failed", "basis": "", "vector": [], "upper_bound": None}

    _, basis, v = min(results, key=lambda t: (t[0], 0 if t[1] == "x" else 1))
    return {
        "status": "completed",
        "basis": basis,
        "vector": vector_list(v, n),
        "upper_bound": int(v.bit_count()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        os.makedirs(args.output_dir, exist_ok=True)
        result = solve(args.hx, args.hz, args.seed)
    except Exception:
        result = {"status": "failed", "basis": "", "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
