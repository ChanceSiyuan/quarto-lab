#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for i, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for i, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            x = 0
            for i in r:
                j = int(i)
                if j >= 0:
                    x ^= 1 << j
                    if j + 1 > n:
                        n = j + 1
            rows.append(x)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def rref(rows, n):
    rows = [r for r in rows if r]
    pivots = []
    rank = 0
    for col in range(n):
        bit = 1 << col
        sel = None
        for i in range(rank, len(rows)):
            if rows[i] & bit:
                sel = i
                break
        if sel is None:
            continue
        rows[rank], rows[sel] = rows[sel], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] & bit):
                rows[i] ^= rows[rank]
        pivots.append(col)
        rank += 1
        if rank == len(rows):
            break
    return rows[:rank], pivots


def reduce_by_basis(v, basis, pivots):
    x = v
    for row, col in zip(basis, pivots):
        if x & (1 << col):
            x ^= row
    return x


def in_rowspace(v, basis, pivots):
    return reduce_by_basis(v, basis, pivots) == 0


def nullspace_basis(rows, n):
    rb, pivots = rref(rows, n)
    pivot_set = set(pivots)
    out = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, col in reversed(list(zip(rb, pivots))):
            if ((row >> free) & 1) and not ((v >> col) & 1):
                v |= 1 << col
        out.append(v)
    return out


def gf2_rank(rows, n):
    return len(rref(rows, n)[0])


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def weight(v):
    return v.bit_count()


def css_ok(hx_rows, hz_rows, n):
    if n <= 0:
        return False
    for x in hx_rows:
        for z in hz_rows:
            if (x & z).bit_count() & 1:
                return False
    return True


def verified(v, kernel_rows, stab_basis, stab_pivots):
    return v != 0 and not in_rowspace(v, stab_basis, stab_pivots) and all(((v & r).bit_count() & 1) == 0 for r in kernel_rows)


def logical_seeds(kernel_basis, stab_basis, stab_pivots, n):
    seeds = []
    residue_basis = []
    residue_pivots = []
    for b in sorted(kernel_basis, key=weight):
        rem = reduce_by_basis(b, stab_basis, stab_pivots)
        if rem and reduce_by_basis(rem, residue_basis, residue_pivots):
            seeds.append(b)
            residue_basis, residue_pivots = rref(residue_basis + [rem], n)
    return seeds


def greedy_polish(v, toggles, stab_basis, stab_pivots, kernel_rows, rng, passes=3):
    best = v
    cur = v
    for _ in range(passes):
        improved = False
        order = toggles[:]
        rng.shuffle(order)
        for t in order:
            nv = cur ^ t
            if weight(nv) < weight(cur) and verified(nv, kernel_rows, stab_basis, stab_pivots):
                cur = nv
                improved = True
        if weight(cur) < weight(best):
            best = cur
        if not improved:
            break
    return best


def random_combo(items, rng, p):
    v = 0
    for x in items:
        if rng.random() < p:
            v ^= x
    return v


def search_basis(name, kernel_rows, stab_rows, n, seed, deadline):
    rng = random.Random((seed ^ (0x9E3779B97F4A7C15 if name == "x" else 0xD1B54A32D192ED03)) & ((1 << 64) - 1))
    stab_basis, stab_pivots = rref(stab_rows, n)
    k_basis = nullspace_basis(kernel_rows, n)
    seeds = logical_seeds(k_basis, stab_basis, stab_pivots, n)
    if not seeds:
        return None

    low_kernel = sorted([b for b in k_basis if b], key=weight)[: min(len(k_basis), 160)]
    low_stab = sorted([s for s in stab_rows if s], key=weight)[: min(len(stab_rows), 240)]
    toggles = []
    seen = set()
    for x in low_stab + low_kernel + seeds:
        if x and x not in seen:
            toggles.append(x)
            seen.add(x)

    candidates = []
    for s in seeds:
        if verified(s, kernel_rows, stab_basis, stab_pivots):
            candidates.append(s)
        candidates.append(greedy_polish(s, toggles, stab_basis, stab_pivots, kernel_rows, rng, passes=5))

    best = min((c for c in candidates if verified(c, kernel_rows, stab_basis, stab_pivots)), key=weight, default=None)
    if best is None:
        for b in k_basis:
            if verified(b, kernel_rows, stab_basis, stab_pivots):
                best = b
                break
    if best is None:
        return None
    if weight(best) <= 1:
        return best

    # Annealed low-weight nullspace basis recombination.  The state always stays
    # in the kernel; verification is applied before a state can become incumbent.
    population = sorted(set(c for c in candidates if verified(c, kernel_rows, stab_basis, stab_pivots)), key=weight)[:48]
    if not population:
        population = [best]
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        if attempts % 17 == 0 and len(population) >= 2:
            a, b = rng.sample(population, 2)
            cur = a ^ b ^ random_combo(seeds, rng, 0.22)
            if not verified(cur, kernel_rows, stab_basis, stab_pivots):
                cur ^= rng.choice(seeds)
        else:
            cur = rng.choice(population) if population else best
            if rng.random() < 0.65:
                cur ^= random_combo(seeds, rng, min(0.5, 1.8 / max(1, len(seeds))))
            if rng.random() < 0.85:
                cur ^= random_combo(low_kernel, rng, min(0.18, 5.0 / max(1, len(low_kernel))))
        if not verified(cur, kernel_rows, stab_basis, stab_pivots):
            continue

        temp0 = max(1.0, 0.22 * max(1, weight(cur)))
        steps = 16 + min(96, n // 2)
        for step in range(steps):
            if time.monotonic() >= deadline:
                break
            pool = toggles if toggles else k_basis
            t = rng.choice(pool)
            nv = cur ^ t
            if not verified(nv, kernel_rows, stab_basis, stab_pivots):
                continue
            dw = weight(nv) - weight(cur)
            temp = temp0 * (1.0 - step / max(1, steps)) + 0.08
            if dw <= 0 or rng.random() < math.exp(-dw / temp):
                cur = nv
                if weight(cur) < weight(best):
                    best = cur
                    if weight(best) <= 1:
                        return best

        cur = greedy_polish(cur, toggles, stab_basis, stab_pivots, kernel_rows, rng, passes=2)
        if verified(cur, kernel_rows, stab_basis, stab_pivots):
            if weight(cur) < weight(best):
                best = cur
                if weight(best) <= 1:
                    return best
            population.append(cur)
            population = sorted(set(population), key=weight)[:64]

    best = greedy_polish(best, toggles, stab_basis, stab_pivots, kernel_rows, rng, passes=8)
    return best if verified(best, kernel_rows, stab_basis, stab_pivots) else None


def emit(status, basis=None, vector=None, upper_bound=None):
    print(json.dumps({
        "status": status,
        "basis": basis,
        "vector": vector,
        "upper_bound": upper_bound,
    }, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        if not css_ok(hx, hz, n):
            emit("failed", None, [], None)
            return 0

        # Scale the budget mildly with dimension, but keep a dependable fallback
        # available through direct logical nullspace seeds even for short runs.
        budget = min(11.5, max(2.0, 0.018 * n + 0.0015 * (len(hx) + len(hz)) * max(1, n).bit_length()))
        end = time.monotonic() + budget
        mid = time.monotonic() + budget * 0.52

        # X logicals commute with Z checks and are nontrivial modulo X stabilizers.
        bx = search_basis("x", hz, hx, n, args.seed, mid)
        # Z logicals commute with X checks and are nontrivial modulo Z stabilizers.
        bz = search_basis("z", hx, hz, n, args.seed, end)

        choices = []
        if bx is not None:
            choices.append(("x", bx))
        if bz is not None:
            choices.append(("z", bz))
        if not choices:
            emit("failed", None, [], None)
            return 0
        basis, vec = min(choices, key=lambda kv: weight(kv[1]))
        emit("completed", basis, vector_to_list(vec, n), weight(vec))
        return 0
    except Exception:
        emit("failed", None, [], None)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
