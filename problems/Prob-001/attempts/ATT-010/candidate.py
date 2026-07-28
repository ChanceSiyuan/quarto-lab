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
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    rows: List[int] = []
    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", 0))
        if n <= 0 and data:
            n = len(data[0])
        for row in data:
            v = 0
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    v |= 1 << i
            rows.append(v)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        for row in obj.get("rows") or []:
            v = 0
            for j in row:
                jj = int(j)
                if jj >= 0:
                    v |= 1 << jj
            rows.append(v)
            if n <= 0 and row:
                n = max(n, max(int(j) for j in row) + 1)
        return rows, n

    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        for row in obj:
            v = 0
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    v |= 1 << i
            rows.append(v)
        return rows, n

    raise ValueError(f"unsupported matrix format in {path}")


def parity(x: int) -> int:
    return x.bit_count() & 1


class Span:
    def __init__(self, rows: Iterable[int] = ()):
        self.basis: Dict[int, int] = {}
        for r in rows:
            self.add(r)

    def reduce(self, v: int) -> int:
        while v:
            p = v.bit_length() - 1
            b = self.basis.get(p)
            if b is None:
                return v
            v ^= b
        return 0

    def contains(self, v: int) -> bool:
        return self.reduce(v) == 0

    def add(self, v: int) -> bool:
        v = self.reduce(v)
        if not v:
            return False
        p = v.bit_length() - 1
        for q, b in list(self.basis.items()):
            if (b >> p) & 1:
                self.basis[q] = b ^ v
        self.basis[p] = v
        return True

    def rows(self) -> List[int]:
        return list(self.basis.values())


def rref_with_transform(rows: Sequence[int], n: int) -> Tuple[List[int], List[int], List[int]]:
    work = [r for r in rows]
    trans = [1 << i for i in range(len(work))]
    pivots: List[int] = []
    rank = 0
    for col in range(n):
        hit = -1
        for i in range(rank, len(work)):
            if (work[i] >> col) & 1:
                hit = i
                break
        if hit < 0:
            continue
        work[rank], work[hit] = work[hit], work[rank]
        trans[rank], trans[hit] = trans[hit], trans[rank]
        for i in range(len(work)):
            if i != rank and ((work[i] >> col) & 1):
                work[i] ^= work[rank]
                trans[i] ^= trans[rank]
        pivots.append(col)
        rank += 1
        if rank == len(work):
            break
    return work[:rank], pivots, trans[:rank]


class KernelRepair:
    def __init__(self, checks: Sequence[int], n: int):
        self.checks = list(checks)
        self.n = n
        self.rref, self.pivots, self.trans = rref_with_transform(self.checks, n)
        self.pivot_set = set(self.pivots)
        self.free_cols = [i for i in range(n) if i not in self.pivot_set]

    def syndrome_mask(self, v: int) -> int:
        s = 0
        for i, r in enumerate(self.checks):
            if parity(r & v):
                s |= 1 << i
        return s

    def in_kernel(self, v: int) -> bool:
        return self.syndrome_mask(v) == 0

    def repair(self, v: int, rng: random.Random, free_rate: float = 0.0) -> int:
        s = self.syndrome_mask(v)
        x = 0
        if free_rate > 0.0 and self.free_cols:
            for col in self.free_cols:
                if rng.random() < free_rate:
                    x |= 1 << col
        for row, pivot, t in zip(self.rref, self.pivots, self.trans):
            rhs = parity(t & s)
            if parity(row & x) ^ rhs:
                x |= 1 << pivot
        return v ^ x

    def kernel_basis(self) -> List[int]:
        basis: List[int] = []
        for free in self.free_cols:
            v = 1 << free
            for row, pivot in zip(self.rref, self.pivots):
                if (row >> free) & 1:
                    v |= 1 << pivot
            basis.append(v)
        return basis


def bit_positions(v: int) -> List[int]:
    out: List[int] = []
    while v:
        lsb = v & -v
        out.append(lsb.bit_length() - 1)
        v ^= lsb
    return out


def build_adjacency(rows: Sequence[int], n: int) -> Tuple[List[List[int]], List[List[int]]]:
    check_to_q = [bit_positions(r) for r in rows]
    q_to_check: List[List[int]] = [[] for _ in range(n)]
    for ci, qs in enumerate(check_to_q):
        for q in qs:
            if 0 <= q < n:
                q_to_check[q].append(ci)
    return check_to_q, q_to_check


def greedy_stabilizer_reduce(v: int, stab_rows: Sequence[int], rng: random.Random, rounds: int = 5) -> int:
    if not v:
        return v
    rows = [r for r in stab_rows if r]
    rows.sort(key=lambda r: r.bit_count())
    best = v
    for _ in range(rounds):
        changed = True
        if len(rows) > 1:
            rng.shuffle(rows)
        while changed:
            changed = False
            current_w = best.bit_count()
            for r in rows:
                cand = best ^ r
                if cand.bit_count() < current_w:
                    best = cand
                    current_w = cand.bit_count()
                    changed = True
        rows.sort(key=lambda r: (best ^ r).bit_count() - best.bit_count())
    return best


def verified(v: int, repairer: KernelRepair, stab_span: Span) -> bool:
    return v != 0 and repairer.in_kernel(v) and not stab_span.contains(v)


def candidate_from_seed(
    seed: int,
    repairer: KernelRepair,
    stab_rows: Sequence[int],
    stab_span: Span,
    rng: random.Random,
    free_rate: float,
) -> Optional[int]:
    v = repairer.repair(seed, rng, free_rate)
    v = greedy_stabilizer_reduce(v, stab_rows, rng)
    if verified(v, repairer, stab_span):
        return v
    return None


def quotient_logicals(repairer: KernelRepair, stab_rows: Sequence[int], rng: random.Random) -> List[int]:
    span = Span(stab_rows)
    logicals: List[int] = []
    kb = repairer.kernel_basis()
    rng.shuffle(kb)
    for b in kb:
        if not span.contains(b):
            span.add(b)
            logicals.append(b)
    return logicals


def random_basis_mix(logicals: Sequence[int], rng: random.Random) -> int:
    if not logicals:
        return 0
    v = 0
    count = 1 + rng.randrange(min(6, len(logicals)))
    for i in rng.sample(range(len(logicals)), count):
        v ^= logicals[i]
    if v == 0:
        v = rng.choice(logicals)
    return v


def cycle_seed(
    check_to_q: Sequence[Sequence[int]],
    q_to_check: Sequence[Sequence[int]],
    rng: random.Random,
    max_steps: int,
) -> int:
    if not check_to_q:
        return 0
    start = rng.randrange(len(check_to_q))
    cur = start
    support = 0
    seen = {cur}
    for _ in range(max_steps):
        qs = check_to_q[cur]
        if not qs:
            break
        q = rng.choice(qs)
        support ^= 1 << q
        nxts = [c for c in q_to_check[q] if c != cur]
        if not nxts:
            break
        nxt = rng.choice(nxts)
        if nxt in seen:
            qs2 = check_to_q[nxt]
            if qs2:
                support ^= 1 << rng.choice(qs2)
            break
        seen.add(nxt)
        cur = nxt
    return support


def trapping_seed(
    check_to_q: Sequence[Sequence[int]],
    q_to_check: Sequence[Sequence[int]],
    n: int,
    rng: random.Random,
    steps: int,
) -> int:
    if n <= 0:
        return 0
    support = 1 << rng.randrange(n)
    unsat = set(q_to_check[(support & -support).bit_length() - 1])
    frontier = set()
    for c in unsat:
        frontier.update(check_to_q[c])
    for _ in range(steps):
        if not frontier:
            q = rng.randrange(n)
        else:
            sample = rng.sample(list(frontier), min(len(frontier), 18))
            q = max(
                sample,
                key=lambda a: (
                    sum(1 for c in q_to_check[a] if c in unsat),
                    -len(q_to_check[a]),
                    rng.random(),
                ),
            )
        support ^= 1 << q
        for c in q_to_check[q]:
            if c in unsat:
                unsat.remove(c)
            else:
                unsat.add(c)
                frontier.update(check_to_q[c])
        if len(unsat) <= 2 and rng.random() < 0.35:
            break
    return support


def search_basis(
    name: str,
    kernel_checks: Sequence[int],
    stabilizers: Sequence[int],
    n: int,
    rng: random.Random,
) -> Optional[Tuple[str, int]]:
    repairer = KernelRepair(kernel_checks, n)
    stab_span = Span(stabilizers)
    stab_rows = list(stabilizers) + stab_span.rows()
    logicals = quotient_logicals(repairer, stabilizers, rng)
    if not logicals:
        return None

    check_to_q, q_to_check = build_adjacency(kernel_checks, n)
    best: Optional[int] = None

    def consider(v: Optional[int]) -> None:
        nonlocal best
        if v is None:
            return
        if best is None or v.bit_count() < best.bit_count():
            best = v

    for b in logicals[: min(len(logicals), 96)]:
        consider(candidate_from_seed(b, repairer, stab_rows, stab_span, rng, 0.0))

    attempts = max(240, min(2600, 18 * n + 32 * len(logicals) + 6 * len(kernel_checks)))
    for t in range(attempts):
        mode = rng.randrange(10)
        if mode < 3:
            seed = cycle_seed(check_to_q, q_to_check, rng, 4 + rng.randrange(10))
        elif mode < 7:
            seed = trapping_seed(check_to_q, q_to_check, n, rng, 2 + rng.randrange(14))
        else:
            seed = random_basis_mix(logicals, rng)
            if rng.random() < 0.55:
                seed ^= trapping_seed(check_to_q, q_to_check, n, rng, 1 + rng.randrange(8))

        if best is not None and seed.bit_count() > max(8, 3 * best.bit_count()) and rng.random() < 0.7:
            seed &= (1 << n) - 1
        free_rate = 0.0 if mode >= 7 else rng.choice((0.0, 0.01, 0.025, 0.05))
        consider(candidate_from_seed(seed, repairer, stab_rows, stab_span, rng, free_rate))

    if best is None:
        for b in logicals:
            v = greedy_stabilizer_reduce(b, stab_rows, rng, rounds=8)
            if verified(v, repairer, stab_span):
                consider(v)

    return (name, best) if best is not None else None


def vector_list(v: int, n: int) -> List[int]:
    return [(v >> i) & 1 for i in range(n)]


def emit(status: str, basis, vector, upper_bound) -> None:
    print(json.dumps({
        "status": status,
        "basis": basis,
        "vector": vector,
        "upper_bound": upper_bound,
    }, separators=(",", ":")))


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)

        searches = [
            ("x", hz, hx),
            ("z", hx, hz),
        ]
        rng.shuffle(searches)
        best: Optional[Tuple[str, int]] = None
        for basis, kernel_checks, stabilizers in searches:
            got = search_basis(basis, kernel_checks, stabilizers, n, rng)
            if got is not None and (best is None or got[1].bit_count() < best[1].bit_count()):
                best = got

        if best is None:
            emit("failed", None, [], None)
            return 0
        basis, v = best
        emit("completed", basis, vector_list(v, n), v.bit_count())
        return 0
    except Exception:
        emit("failed", None, [], None)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
