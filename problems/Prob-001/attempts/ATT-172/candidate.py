#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def load_matrix(value: str) -> Tuple[List[int], int]:
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            obj = json.load(f)
    else:
        obj = json.loads(value)

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n_cols = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            bits = 0
            for j, x in enumerate(row):
                if int(x) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n_cols

    if "rows" in obj:
        n_cols = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            bits = 0
            last = -1
            for j in row:
                j = int(j)
                if j <= last or j < 0 or j >= n_cols:
                    raise ValueError("sparse row indices must be strictly increasing")
                bits |= 1 << j
                last = j
            rows.append(bits)
        return rows, n_cols

    raise ValueError("unsupported matrix JSON format")


def parity(x: int) -> int:
    return x.bit_count() & 1


def build_basis(rows: Iterable[int]) -> Dict[int, int]:
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


def reduce_with_basis(x: int, basis: Dict[int, int]) -> int:
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(x: int, basis: Dict[int, int]) -> bool:
    return reduce_with_basis(x, basis) == 0


def nullspace_basis(rows: Sequence[int], n_cols: int) -> List[int]:
    # RREF-like elimination with high-bit pivots.  This is used to generate
    # kernel samples, not to certify or optimize a minimum distance.
    basis = build_basis(rows)
    pivots = set(basis)
    free_cols = [j for j in range(n_cols) if j not in pivots]
    out: List[int] = []
    for f in free_cols:
        v = 1 << f
        for p in sorted(pivots):
            row = basis[p]
            if parity((row ^ (1 << p)) & v):
                v |= 1 << p
        out.append(v)
    return out


def quotient_generators(kernel: Sequence[int], stabilizers: Sequence[int]) -> List[int]:
    stab_basis = build_basis(stabilizers)
    combined = dict(stab_basis)
    logicals: List[int] = []
    for v in sorted(kernel, key=lambda x: (x.bit_count(), x.bit_length())):
        r = reduce_with_basis(v, combined)
        if r:
            logicals.append(v)
            combined[r.bit_length() - 1] = r
    return logicals


def xor_sample(vectors: Sequence[int], rng: random.Random, p: float) -> int:
    x = 0
    used = False
    for v in vectors:
        if rng.random() < p:
            x ^= v
            used = True
    if not used and vectors:
        x = rng.choice(vectors)
    return x


def greedy_stabilizer_reduce(v: int, stabilizers: Sequence[int], rng: random.Random) -> int:
    if not stabilizers:
        return v
    cur = v
    rows = list(stabilizers)
    no_gain_rounds = 0
    while no_gain_rounds < 3:
        rng.shuffle(rows)
        improved = False
        cur_w = cur.bit_count()
        for s in rows:
            y = cur ^ s
            wy = y.bit_count()
            if wy < cur_w:
                cur = y
                cur_w = wy
                improved = True
        no_gain_rounds = 0 if improved else no_gain_rounds + 1
    return cur


def random_walk_reduce(
    v: int,
    stabilizers: Sequence[int],
    commute_rows: Sequence[int],
    stab_basis: Dict[int, int],
    rng: random.Random,
    steps: int,
) -> int:
    best = greedy_stabilizer_reduce(v, stabilizers, rng)
    cur = best
    if not stabilizers:
        return best
    temp = 2.0
    for t in range(max(0, steps)):
        s = rng.choice(stabilizers)
        y = cur ^ s
        delta = y.bit_count() - cur.bit_count()
        if delta <= 0 or rng.random() < (0.03 if delta <= temp else 0.0):
            cur = y
            if cur.bit_count() < best.bit_count() and verify(cur, commute_rows, stab_basis):
                best = cur
        if (t + 1) % 64 == 0:
            cur = greedy_stabilizer_reduce(cur, stabilizers, rng)
            if cur.bit_count() < best.bit_count() and verify(cur, commute_rows, stab_basis):
                best = cur
            temp *= 0.85
    return best


def verify(v: int, commute_rows: Sequence[int], stab_basis: Dict[int, int]) -> bool:
    if v == 0:
        return False
    for row in commute_rows:
        if parity(v & row):
            return False
    return not in_rowspace(v, stab_basis)


def bits_to_list(v: int, n_cols: int) -> List[int]:
    return [(v >> j) & 1 for j in range(n_cols)]


def search_basis(
    basis_name: str,
    commute_rows: Sequence[int],
    stabilizer_rows: Sequence[int],
    n_cols: int,
    rng: random.Random,
    seed_offset: int,
) -> Optional[Tuple[str, int]]:
    kernel = nullspace_basis(commute_rows, n_cols)
    logicals = quotient_generators(kernel, stabilizer_rows)
    if not logicals:
        return None

    stab_basis = build_basis(stabilizer_rows)
    stabilizers = [s for s in stabilizer_rows if s]
    best: Optional[int] = None

    def consider(v: int, effort: int) -> None:
        nonlocal best
        v = greedy_stabilizer_reduce(v, stabilizers, rng)
        v = random_walk_reduce(v, stabilizers, commute_rows, stab_basis, rng, effort)
        if verify(v, commute_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for g in logicals[: min(len(logicals), 64)]:
        consider(g, 128)

    density_choices = [0.02, 0.04, 0.08, 0.125, 0.2, 0.33, 0.5]
    trials = max(256, min(6000, 80 * len(logicals) + 8 * n_cols + seed_offset))
    for i in range(trials):
        p = density_choices[i % len(density_choices)]
        v = xor_sample(logicals, rng, p)
        if best is not None and v.bit_count() > max(8, 4 * best.bit_count()):
            # A light randomized thinning of very dense logical combinations.
            v ^= xor_sample(logicals, rng, min(0.5, p * 2.0))
        consider(v, 32 if i < trials // 2 else 8)

    return (basis_name, best) if best is not None else None


def result(status: str, basis: str, vector: Sequence[int], upper_bound) -> None:
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
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz must have the same number of columns")
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        searches = [
            ("x", hz, hx, 17),
            ("z", hx, hz, 53),
        ]
        rng.shuffle(searches)

        best: Optional[Tuple[str, int]] = None
        for name, commute, stabilizers, offset in searches:
            found = search_basis(name, commute, stabilizers, nx, rng, offset)
            if found is not None:
                if best is None or found[1].bit_count() < best[1].bit_count():
                    best = found

        if best is None:
            result("failed", "x", [], None)
            return 0

        basis_name, vec = best
        result("completed", basis_name, bits_to_list(vec, nx), vec.bit_count())
        return 0
    except Exception:
        result("failed", "x", [], None)
        return 0


if __name__ == "__main__":
    sys.exit(main())
