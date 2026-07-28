#!/usr/bin/env python3
"""Randomized CSS logical witness search.

This entrypoint reports only verified upper-bound witnesses. It never claims
that the reported weight is the exact CSS distance.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from typing import Iterable


def project_path(path: str) -> str:
    root = os.path.abspath(os.getcwd())
    full = os.path.abspath(path)
    if os.path.commonpath([root, full]) != root:
        raise ValueError("path outside current project directory")
    return full


def load_matrix(path: str) -> tuple[list[int], int]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and {"n_rows", "n_cols", "data"} <= set(obj):
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n:
                raise ValueError(f"{path}: dense row has wrong length")
            x = 0
            for i, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError(f"{path}: non-binary entry")
                if bit:
                    x |= 1 << i
            rows.append(x)
        if len(rows) != int(obj["n_rows"]):
            raise ValueError(f"{path}: n_rows does not match data")
        return rows, n

    if isinstance(obj, dict) and {"num_cols", "rows"} <= set(obj):
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            x = 0
            for col in row:
                col = int(col)
                if col <= last or col < 0 or col >= n:
                    raise ValueError(f"{path}: sparse rows must be strictly increasing")
                x |= 1 << col
                last = col
            rows.append(x)
        return rows, n

    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        rows = []
        for row in obj:
            if len(row) != n:
                raise ValueError(f"{path}: ragged dense matrix")
            x = 0
            for i, bit in enumerate(row):
                if bit not in (0, 1, False, True):
                    raise ValueError(f"{path}: non-binary entry")
                if bit:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    raise ValueError(f"{path}: unsupported matrix JSON format")


def rref_rows(rows: Iterable[int], n: int) -> tuple[list[int], list[int]]:
    mat = [r for r in rows if r]
    pivots: list[int] = []
    rank = 0
    for col in range(n):
        pivot = None
        mask = 1 << col
        for r in range(rank, len(mat)):
            if mat[r] & mask:
                pivot = r
                break
        if pivot is None:
            continue
        mat[rank], mat[pivot] = mat[pivot], mat[rank]
        for r in range(len(mat)):
            if r != rank and (mat[r] & mask):
                mat[r] ^= mat[rank]
        pivots.append(col)
        rank += 1
        if rank == len(mat):
            break
    return mat[:rank], pivots


def nullspace_basis(rows: Iterable[int], n: int) -> list[int]:
    rref, pivots = rref_rows(rows, n)
    pivot_set = set(pivots)
    basis = []
    for free in range(n):
        if free in pivot_set:
            continue
        x = 1 << free
        for row, pivot in zip(rref, pivots):
            if row & (1 << free):
                x |= 1 << pivot
        basis.append(x)
    return basis


def rowspace_basis(rows: Iterable[int]) -> dict[int, int]:
    basis: dict[int, int] = {}
    for row in rows:
        x = row
        while x:
            pivot = x.bit_length() - 1
            if pivot in basis:
                x ^= basis[pivot]
            else:
                basis[pivot] = x
                break
    return basis


def in_rowspace(x: int, basis: dict[int, int]) -> bool:
    while x:
        pivot = x.bit_length() - 1
        row = basis.get(pivot)
        if row is None:
            return False
        x ^= row
    return True


def kernel_ok(x: int, checks: Iterable[int]) -> bool:
    return all(((x & row).bit_count() & 1) == 0 for row in checks)


def random_span_vector(vectors: list[int], rng: random.Random) -> int:
    x = 0
    # Sparse combinations often give better starting points than fully dense
    # sums, but occasional dense mixtures help move between quotient classes.
    p = rng.choice((0.08, 0.12, 0.18, 0.25, 0.5))
    for v in vectors:
        if rng.random() < p:
            x ^= v
    if x == 0 and vectors:
        x = rng.choice(vectors)
    return x


def greedy_reduce(x: int, moves: list[int], rng: random.Random, rounds: int) -> int:
    if not x:
        return x
    best = x
    best_w = x.bit_count()
    ordered = list(moves)

    for _ in range(rounds):
        cur = best
        improved = True
        while improved:
            improved = False
            rng.shuffle(ordered)
            for move in ordered:
                nxt = cur ^ move
                if nxt and nxt.bit_count() < cur.bit_count():
                    cur = nxt
                    improved = True
        w = cur.bit_count()
        if w < best_w:
            best, best_w = cur, w
    return best


def fallback_logical(kernel_basis: list[int], stab_basis: dict[int, int]) -> int:
    span: dict[int, int] = dict(stab_basis)
    for v in kernel_basis:
        x = v
        while x:
            pivot = x.bit_length() - 1
            row = span.get(pivot)
            if row is None:
                return v
            x ^= row
    return 0


def search_basis(
    name: str,
    kernel_checks: list[int],
    stabilizers: list[int],
    n: int,
    rng: random.Random,
) -> tuple[str, int] | None:
    kernel_basis = nullspace_basis(kernel_checks, n)
    stab_space = rowspace_basis(stabilizers)
    moves = [m for m in stabilizers + kernel_basis if m]
    trials = max(256, min(20000, 80 * max(1, n) + 200 * max(1, len(kernel_basis))))
    reduce_rounds = 2 if n > 2500 else 5

    best = 0
    best_w = n + 1
    seeds: list[int] = []
    for v in kernel_basis:
        if v and not in_rowspace(v, stab_space):
            seeds.append(v)
    fb = fallback_logical(kernel_basis, stab_space)
    if fb:
        seeds.append(fb)

    for t in range(trials + len(seeds)):
        cand = seeds[t] if t < len(seeds) else random_span_vector(kernel_basis, rng)
        if not cand or in_rowspace(cand, stab_space):
            continue
        cand = greedy_reduce(cand, moves, rng, reduce_rounds)
        if cand and not in_rowspace(cand, stab_space) and kernel_ok(cand, kernel_checks):
            w = cand.bit_count()
            if w < best_w:
                best, best_w = cand, w

    if best:
        return name, best
    return None


def vector_bits(x: int, n: int) -> list[int]:
    return [(x >> i) & 1 for i in range(n)]


def emit(status: str, basis: str | None, vector: list[int], upper_bound: int | None) -> None:
    print(
        json.dumps(
            {
                "status": status,
                "basis": basis,
                "vector": vector,
                "upper_bound": upper_bound,
            },
            separators=(",", ":"),
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Randomized CSS upper-bound witness search")
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(project_path(args.hx))
        hz, nz = load_matrix(project_path(args.hz))
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        os.makedirs(project_path(args.output_dir), exist_ok=True)
        rng = random.Random(args.seed)

        candidates = []
        for item in (
            search_basis("x", hz, hx, nx, rng),
            search_basis("z", hx, hz, nx, rng),
        ):
            if item is not None:
                candidates.append(item)

        if not candidates:
            emit("not_found", None, [], None)
            return 0

        basis, witness = min(candidates, key=lambda item: item[1].bit_count())
        if basis == "x":
            valid = kernel_ok(witness, hz) and not in_rowspace(witness, rowspace_basis(hx))
        else:
            valid = kernel_ok(witness, hx) and not in_rowspace(witness, rowspace_basis(hz))
        if not valid:
            emit("not_found", None, [], None)
            return 0

        emit("completed", basis, vector_bits(witness, nx), witness.bit_count())
        return 0
    except Exception:
        emit("error", None, [], None)
        return 0


if __name__ == "__main__":
    sys.exit(main())
