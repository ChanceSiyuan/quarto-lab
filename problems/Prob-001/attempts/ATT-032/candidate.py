#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        return [row_to_int(r, n) for r in data], n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", obj.get("num_cols", max((len(r) for r in data), default=0))))
        return [row_to_int(r, n) for r in data], n
    if "rows" in obj:
        rows = obj.get("rows", [])
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n == 0:
            n = 1 + max((c for r in rows for c in r), default=-1)
        out = []
        for r in rows:
            v = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    v ^= 1 << c
            out.append(v)
        return out, n
    raise ValueError("unsupported matrix JSON format")


def row_to_int(row, n):
    v = 0
    for i, bit in enumerate(row):
        if i >= n:
            break
        if bit & 1:
            v |= 1 << i
    return v


class RowBasis:
    def __init__(self, rows=None):
        self.rows = {}
        if rows:
            for r in rows:
                self.add(r)

    def copy(self):
        b = RowBasis()
        b.rows = dict(self.rows)
        return b

    def reduce(self, x):
        while x:
            p = x.bit_length() - 1
            r = self.rows.get(p)
            if r is None:
                break
            x ^= r
        return x

    def add(self, x):
        x = self.reduce(x)
        if not x:
            return False
        p = x.bit_length() - 1
        for q, r in list(self.rows.items()):
            if (r >> p) & 1:
                self.rows[q] = r ^ x
        self.rows[p] = x
        return True

    def contains(self, x):
        return self.reduce(x) == 0

    def basis_rows(self):
        return list(self.rows.values())


def rank(rows):
    return len(RowBasis(rows).rows)


def nullspace_basis(rows, n):
    rb = RowBasis(rows)
    pivots = set(rb.rows.keys())
    free_cols = [c for c in range(n) if c not in pivots]
    basis = []
    for f in free_cols:
        x = 1 << f
        for p, r in rb.rows.items():
            if (r >> f) & 1:
                x |= 1 << p
        basis.append(x)
    return basis


def syndrome_zero(v, checks):
    for r in checks:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def verify(v, kernel_checks, stabilizer_basis):
    return v != 0 and syndrome_zero(v, kernel_checks) and not stabilizer_basis.contains(v)


def int_to_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


def greedy_coset_reduce(v, stab_rows, rng, rounds=4):
    if not stab_rows:
        return v
    cur = v
    rows = list(stab_rows)
    for t in range(rounds):
        if t:
            rng.shuffle(rows)
        improved = True
        while improved:
            improved = False
            cur_w = cur.bit_count()
            best = cur
            best_gain = 0
            scan = rows if t else sorted(rows, key=lambda r: (r.bit_count(), r))
            for r in scan:
                nr = cur ^ r
                gain = cur_w - nr.bit_count()
                if gain > best_gain or (gain == best_gain and gain > 0 and rng.random() < 0.2):
                    best = nr
                    best_gain = gain
            if best_gain > 0:
                cur = best
                improved = True
    return cur


def annealed_coset_reduce(v, stab_rows, rng, steps):
    if not stab_rows:
        return v
    cur = greedy_coset_reduce(v, stab_rows, rng, 2)
    best = cur
    rows = list(stab_rows)
    for i in range(steps):
        r = rows[rng.randrange(len(rows))]
        nxt = cur ^ r
        dw = nxt.bit_count() - cur.bit_count()
        temp = max(0.05, 2.5 * (1.0 - i / max(1, steps)))
        if dw <= 0 or rng.random() < pow(2.718281828, -dw / temp):
            cur = nxt
            if cur.bit_count() < best.bit_count():
                best = greedy_coset_reduce(cur, stab_rows, rng, 1)
                cur = best
    return best


def quotient_reps(kernel_basis, stabilizer_rows):
    combined = RowBasis(stabilizer_rows)
    reps = []
    for v in sorted(kernel_basis, key=lambda x: (x.bit_count(), x)):
        if combined.add(v):
            reps.append(v)
    return reps


def column_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        x = r
        while x:
            lsb = x & -x
            deg[lsb.bit_length() - 1] += 1
            x ^= lsb
    return deg


def solve_kernel_with_forced(kernel_rows, n, forced_mask):
    forced = [i for i in range(n) if (forced_mask >> i) & 1]
    if not forced:
        return 0
    equations = []
    rhs = []
    forced_parity = len(forced) & 1
    equations.append(forced_mask)
    rhs.append(forced_parity)
    for r in kernel_rows:
        equations.append(r)
        rhs.append(0)

    rows = []
    for a, b in zip(equations, rhs):
        rows.append(a | ((b & 1) << n))
    rb = {}
    for row in rows:
        x = row
        while x & ((1 << n) - 1):
            p = (x & ((1 << n) - 1)).bit_length() - 1
            if p in rb:
                x ^= rb[p]
            else:
                rb[p] = x
                break
    for x in rows:
        y = x
        while y & ((1 << n) - 1):
            p = (y & ((1 << n) - 1)).bit_length() - 1
            if p in rb:
                y ^= rb[p]
            else:
                break
        if (y & ((1 << n) - 1)) == 0 and ((y >> n) & 1):
            return 0
    sol = 0
    for p, row in rb.items():
        if (row >> n) & 1:
            sol |= 1 << p
    return sol


def randomized_search(name, kernel_rows, stabilizer_rows, n, rng, deadline):
    stab_basis = RowBasis(stabilizer_rows)
    ns = nullspace_basis(kernel_rows, n)
    reps = quotient_reps(ns, stabilizer_rows)
    if not reps:
        return None

    candidates = []
    for r in reps:
        candidates.append(r)
        candidates.append(greedy_coset_reduce(r, stabilizer_rows, rng, 5))

    best = None

    def submit(v):
        nonlocal best
        if v and verify(v, kernel_rows, stab_basis):
            v = greedy_coset_reduce(v, stabilizer_rows, rng, 3)
            if verify(v, kernel_rows, stab_basis):
                if best is None or v.bit_count() < best.bit_count():
                    best = v

    for c in candidates:
        submit(c)

    q = len(reps)
    deg = column_degrees(kernel_rows + stabilizer_rows, n)
    low_cols = sorted(range(n), key=lambda i: (deg[i], rng.random()))[: max(1, min(n, 32))]
    iter_budget = 3500 + 140 * q + 12 * n
    if n > 600:
        iter_budget = min(iter_budget, 9000)

    for it in range(iter_budget):
        if time.time() > deadline:
            break
        mode = it % 6
        v = 0
        if mode in (0, 1):
            p = 0.18 if mode == 0 else rng.uniform(1.0 / max(1, q), 0.55)
            for r in reps:
                if rng.random() < p:
                    v ^= r
            if v == 0:
                v = reps[rng.randrange(q)]
        elif mode == 2:
            center = reps[rng.randrange(q)]
            v = center
            flips = 1 + rng.randrange(min(q, 8))
            for _ in range(flips):
                if rng.random() < 0.65:
                    v ^= reps[rng.randrange(q)]
        elif mode == 3:
            a = reps[rng.randrange(q)]
            b = reps[rng.randrange(q)]
            v = a ^ b if a != b else a
            v = annealed_coset_reduce(v, stabilizer_rows, rng, 80)
        elif mode == 4:
            mask = 0
            for c in rng.sample(low_cols, min(len(low_cols), 1 + rng.randrange(min(10, len(low_cols))))):
                mask |= 1 << c
            lifted = solve_kernel_with_forced(kernel_rows, n, mask)
            v = lifted if lifted else reps[rng.randrange(q)]
        else:
            # Stabilizer-dithered quotient sample: jump within the same kernel,
            # then descend. This probes coset geometry differently from merely
            # combining logical representatives.
            v = reps[rng.randrange(q)]
            if q > 1 and rng.random() < 0.7:
                v ^= reps[rng.randrange(q)]
            for _ in range(min(len(stabilizer_rows), 12)):
                if stabilizer_rows and rng.random() < 0.5:
                    v ^= stabilizer_rows[rng.randrange(len(stabilizer_rows))]

        if mode != 3:
            if rng.random() < 0.35:
                v = annealed_coset_reduce(v, stabilizer_rows, rng, 45)
            else:
                v = greedy_coset_reduce(v, stabilizer_rows, rng, 4)
        submit(v)

    if best is None:
        for r in reps:
            if verify(r, kernel_rows, stab_basis):
                best = r
                break
    return (name, best) if best is not None else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        rng = random.Random(args.seed)
        os.makedirs(args.output_dir, exist_ok=True)

        deadline = time.time() + 25.0
        choices = []
        if n > 0:
            choices.append(randomized_search("x", hz, hx, n, rng, deadline))
            choices.append(randomized_search("z", hx, hz, n, rng, deadline))
        choices = [c for c in choices if c and c[1] is not None]
        if choices:
            basis, vec = min(choices, key=lambda c: (c[1].bit_count(), 0 if c[0] == "x" else 1))
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
