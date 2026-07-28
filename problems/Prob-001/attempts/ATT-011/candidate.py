#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _looks_like_path(s):
    return isinstance(s, str) and os.path.exists(s)


def load_matrix_arg(arg):
    obj = _read_json(arg) if _looks_like_path(arg) else json.loads(arg)
    return parse_matrix(obj)


def parse_matrix(obj):
    if isinstance(obj, list):
        if not obj:
            return [], 0
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            b = 0
            for i, x in enumerate(r):
                if int(x) & 1:
                    b |= 1 << i
            rows.append(b)
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("matrix must be JSON object or list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        if not n and data:
            n = max(len(r) for r in data)
        rows = []
        for r in data:
            b = 0
            for i, x in enumerate(r):
                if int(x) & 1:
                    b |= 1 << i
            rows.append(b)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            b = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    b ^= 1 << c
                    if c + 1 > n:
                        n = c + 1
            rows.append(b)
        return rows, n

    raise ValueError("unrecognized matrix JSON format")


def mask_n(n):
    return (1 << n) - 1 if n > 0 else 0


def dot_parity(a, b):
    return (a & b).bit_count() & 1


class RowSpace:
    def __init__(self, rows=()):
        self.basis = {}
        for r in rows:
            self.add(r)

    def add(self, row):
        x = row
        while x:
            p = x.bit_length() - 1
            y = self.basis.get(p)
            if y is None:
                self.basis[p] = x
                return True
            x ^= y
        return False

    def reduce(self, row):
        x = row
        while x:
            p = x.bit_length() - 1
            y = self.basis.get(p)
            if y is None:
                return x
            x ^= y
        return 0

    def contains(self, row):
        return self.reduce(row) == 0

    def rank(self):
        return len(self.basis)


def rref_rows(rows, n):
    rows = [r & mask_n(n) for r in rows if r & mask_n(n)]
    pivots = []
    i = 0
    for col in range(n):
        pivot = None
        bit = 1 << col
        for j in range(i, len(rows)):
            if rows[j] & bit:
                pivot = j
                break
        if pivot is None:
            continue
        rows[i], rows[pivot] = rows[pivot], rows[i]
        for j in range(len(rows)):
            if j != i and (rows[j] & bit):
                rows[j] ^= rows[i]
        pivots.append(col)
        i += 1
        if i == len(rows):
            break
    return rows[:i], pivots


def nullspace_basis(check_rows, n):
    rref, pivots = rref_rows(check_rows, n)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n) if c not in pivot_set]
    basis = []
    for f in free_cols:
        v = 1 << f
        for row, p in zip(rref, pivots):
            if row & (1 << f):
                v |= 1 << p
        basis.append(v & mask_n(n))
    return basis


def in_kernel(v, checks):
    for r in checks:
        if dot_parity(v, r):
            return False
    return True


def verified(v, checks, stabilizers):
    return v != 0 and in_kernel(v, checks) and not RowSpace(stabilizers).contains(v)


def bit_positions(x):
    while x:
        lsb = x & -x
        yield lsb.bit_length() - 1
        x ^= lsb


def vector_list(v, n):
    return [1 if (v >> i) & 1 else 0 for i in range(n)]


def quotient_logical_seeds(kernel_basis, stabilizers, limit=48):
    combined = RowSpace(stabilizers)
    seeds = []
    for b in sorted((x for x in kernel_basis if x), key=lambda z: z.bit_count()):
        rem = combined.reduce(b)
        if rem:
            seeds.append(b)
            combined.add(b)
            if len(seeds) >= limit:
                break
    return seeds


def greedy_descent(v, rows, rng, rounds=5):
    if not rows:
        return v
    cur = v
    order = list(range(len(rows)))
    for _ in range(rounds):
        improved = False
        rng.shuffle(order)
        cw = cur.bit_count()
        for idx in order:
            nv = cur ^ rows[idx]
            nw = nv.bit_count()
            if nw and nw < cw:
                cur, cw = nv, nw
                improved = True
        if not improved:
            break
    return cur


def build_row_neighbors(rows, n):
    col_rows = {}
    for i, r in enumerate(rows):
        for c in bit_positions(r):
            col_rows.setdefault(c, []).append(i)
    neighbors = [set() for _ in rows]
    for ids in col_rows.values():
        if len(ids) <= 1:
            continue
        for i in ids:
            neighbors[i].update(j for j in ids if j != i)
    return [list(s) for s in neighbors]


def random_block(rows, neighbors, rng, scale):
    if not rows:
        return 0
    start = rng.randrange(len(rows))
    seen = {start}
    frontier = [start]
    while frontier and len(seen) < scale:
        u = frontier.pop(rng.randrange(len(frontier)))
        ns = neighbors[u] if u < len(neighbors) else []
        if ns:
            rng.shuffle(ns)
            for v in ns[: max(1, min(len(ns), scale - len(seen)))]:
                if v not in seen:
                    seen.add(v)
                    frontier.append(v)
                    if len(seen) >= scale:
                        break
        elif len(seen) < scale:
            seen.add(rng.randrange(len(rows)))
    x = 0
    for i in seen:
        if rng.random() < 0.65:
            x ^= rows[i]
    if x == 0:
        x = rows[start]
    return x


def combine_random(seeds, rng, max_terms):
    if not seeds:
        return 0
    count = rng.randint(1, min(max_terms, len(seeds)))
    chosen = rng.sample(seeds, count)
    x = 0
    for s in chosen:
        x ^= s
    return x


def search_basis(label, checks, stabilizers, n, rng, deadline):
    k_basis = nullspace_basis(checks, n)
    seeds = quotient_logical_seeds(k_basis, stabilizers, limit=64)
    if not seeds:
        return None

    stab_rows = [r & mask_n(n) for r in stabilizers if r & mask_n(n)]
    neighbors = build_row_neighbors(stab_rows, n) if stab_rows else []
    candidates = []
    for s in seeds[:24]:
        candidates.append(greedy_descent(s, stab_rows, rng, rounds=8))
    for _ in range(min(24, len(seeds) * 2)):
        candidates.append(greedy_descent(combine_random(seeds, rng, 4), stab_rows, rng, rounds=6))

    best = None
    for c in candidates:
        if verified(c, checks, stabilizers):
            if best is None or c.bit_count() < best.bit_count():
                best = c
    if best is None:
        for s in seeds:
            if verified(s, checks, stabilizers):
                best = s
                break
    if best is None:
        return None
    if not stab_rows or best.bit_count() <= 1:
        return (label, best)

    scales = [1, 2, 3, 5, 8, 13, 21, 34]
    stagnant = 0
    iterations = 0
    max_iters = 800 + 35 * min(len(stab_rows), 200)
    while iterations < max_iters and time.time() < deadline:
        iterations += 1
        if iterations % 97 == 0:
            base = combine_random(seeds, rng, 6)
        else:
            base = best
        pert = 0
        bursts = 1 + (rng.randrange(3) if stagnant > 30 else 0)
        for _ in range(bursts):
            scale = rng.choice(scales)
            pert ^= random_block(stab_rows, neighbors, rng, min(scale, max(1, len(stab_rows)))) if stab_rows else 0
        trial = base ^ pert
        if trial == 0:
            continue
        trial = greedy_descent(trial, stab_rows, rng, rounds=4 + min(8, stagnant // 20))
        if verified(trial, checks, stabilizers) and trial.bit_count() < best.bit_count():
            best = trial
            stagnant = 0
        else:
            stagnant += 1
        if best.bit_count() <= 1:
            break
    return (label, best)


def normalize_n(hx_rows, hx_n, hz_rows, hz_n):
    n = max(hx_n, hz_n)
    if n == 0:
        for r in hx_rows + hz_rows:
            n = max(n, r.bit_length())
    m = mask_n(n)
    return [r & m for r in hx_rows], [r & m for r in hz_rows], n


def compatible(hx_rows, hz_rows):
    for x in hx_rows:
        for z in hz_rows:
            if dot_parity(x, z):
                return False
    return True


def emit(status, basis, vector, upper_bound):
    print(json.dumps({
        "status": status,
        "basis": basis,
        "vector": vector,
        "upper_bound": upper_bound,
    }, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    try:
        hx_rows, hx_n = load_matrix_arg(args.hx)
        hz_rows, hz_n = load_matrix_arg(args.hz)
        hx_rows, hz_rows, n = normalize_n(hx_rows, hx_n, hz_rows, hz_n)
        if not compatible(hx_rows, hz_rows):
            emit("failed", None, [], None)
            return 0

        rng = random.Random(args.seed)
        rank_hx = RowSpace(hx_rows).rank()
        rank_hz = RowSpace(hz_rows).rank()
        k_est = n - rank_hx - rank_hz
        if k_est <= 0:
            emit("failed", None, [], None)
            return 0

        deadline = time.time() + 4.0
        bases = [("x", hz_rows, hx_rows), ("z", hx_rows, hz_rows)]
        if rng.random() < 0.5:
            bases.reverse()

        found = []
        for label, checks, stabs in bases:
            remaining = max(1.0, deadline - time.time())
            sub_deadline = time.time() + remaining / (2 if not found else 1)
            ans = search_basis(label, checks, stabs, n, rng, sub_deadline)
            if ans is not None:
                found.append(ans)
                if ans[1].bit_count() <= 1:
                    break

        if not found:
            emit("failed", None, [], None)
            return 0

        basis, vec = min(found, key=lambda t: (t[1].bit_count(), 0 if t[0] == "x" else 1))
        checks, stabs = (hz_rows, hx_rows) if basis == "x" else (hx_rows, hz_rows)
        if not verified(vec, checks, stabs):
            emit("failed", None, [], None)
            return 0
        emit("completed", basis, vector_list(vec, n), vec.bit_count())
        return 0
    except Exception:
        emit("failed", None, [], None)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
