#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys


def parity(x):
    return x.bit_count() & 1


def rows_to_ints(data, n_cols=None):
    rows = []
    if data is None:
        return [], int(n_cols or 0)
    if n_cols is None:
        n_cols = 0
        for row in data:
            if isinstance(row, int):
                n_cols = max(n_cols, row.bit_length())
            elif row:
                n_cols = max(n_cols, len(row))
    n_cols = int(n_cols)
    for row in data:
        if isinstance(row, int):
            rows.append(row & ((1 << n_cols) - 1 if n_cols else 0))
        else:
            v = 0
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    v |= 1 << i
            rows.append(v)
    return rows, n_cols


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        return rows_to_ints(obj)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        return rows_to_ints(obj.get("data", []), obj.get("n_cols", obj.get("num_cols")))
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for row in obj.get("rows", []):
            v = 0
            for j in row:
                jj = int(j)
                if 0 <= jj < n:
                    v |= 1 << jj
            rows.append(v)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


class GF2Basis:
    def __init__(self, rows=None, n=0):
        self.n = n
        self.by_pivot = {}
        if rows:
            for row in rows:
                self.add(row)

    def reduce(self, row):
        x = row
        while x:
            p = x.bit_length() - 1
            b = self.by_pivot.get(p)
            if b is None:
                break
            x ^= b
        return x

    def add(self, row):
        x = self.reduce(row)
        if not x:
            return False
        p = x.bit_length() - 1
        for q, b in list(self.by_pivot.items()):
            if (b >> p) & 1:
                self.by_pivot[q] = b ^ x
        self.by_pivot[p] = x
        return True

    def contains(self, row):
        return self.reduce(row) == 0

    def rank(self):
        return len(self.by_pivot)

    def rows(self):
        return list(self.by_pivot.values())


class KernelLifter:
    def __init__(self, check_rows, n):
        self.n = n
        self.basis = GF2Basis(check_rows, n)
        self.pivots = set(self.basis.by_pivot)
        self.free_cols = [i for i in range(n) if i not in self.pivots]
        self.free_mask = 0
        for i in self.free_cols:
            self.free_mask |= 1 << i

    def lift(self, free_bits):
        x = free_bits & self.free_mask
        for p, row in self.basis.by_pivot.items():
            if parity((row ^ (1 << p)) & x):
                x |= 1 << p
            else:
                x &= ~(1 << p)
        return x

    def kernel_basis(self):
        return [self.lift(1 << i) for i in self.free_cols]


def syndrome_zero(rows, v):
    for row in rows:
        if parity(row & v):
            return False
    return True


def vector_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def column_degrees(rows, n):
    deg = [0] * n
    for row in rows:
        x = row
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            if j < n:
                deg[j] += 1
            x ^= lsb
    return deg


def logical_representatives(check_rows, stab_rows, n):
    lifter = KernelLifter(check_rows, n)
    stab_basis = GF2Basis(stab_rows, n)
    quotient = GF2Basis(n=n)
    reps = []
    for kvec in lifter.kernel_basis():
        residue = stab_basis.reduce(kvec)
        if residue and quotient.add(residue):
            reps.append(kvec)
    return lifter, stab_basis, reps


def minimize_by_stabilizers(v, stab_rows, rng, rounds=4):
    cur = v
    rows = [r for r in stab_rows if r]
    if not rows:
        return cur
    best_w = cur.bit_count()
    for _ in range(rounds):
        improved = False
        rng.shuffle(rows)
        for row in rows:
            cand = cur ^ row
            w = cand.bit_count()
            if w < best_w or (w == best_w and rng.random() < 0.03):
                cur = cand
                best_w = w
                improved = True
        if not improved:
            break
    return cur


def verified(v, check_rows, stab_basis):
    return bool(v) and syndrome_zero(check_rows, v) and not stab_basis.contains(v)


def random_projected_lift_search(check_rows, stab_rows, n, seed):
    rng = random.Random(seed)
    lifter, stab_basis, reps = logical_representatives(check_rows, stab_rows, n)
    if not reps:
        return None

    stab_list = stab_basis.rows()
    best = None

    def consider(v, descent_rounds=5):
        nonlocal best
        if not verified(v, check_rows, stab_basis):
            return
        v = minimize_by_stabilizers(v, stab_list, rng, descent_rounds)
        if verified(v, check_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for rep in reps:
        consider(rep, 8)

    free_cols = lifter.free_cols
    if not free_cols:
        return best

    deg = column_degrees(check_rows + stab_rows, n)
    free_len = len(free_cols)
    rep_free = [r & lifter.free_mask for r in reps]
    iterations = min(9000, max(900, 70 * (len(reps) + 1) + 18 * free_len))
    base_sizes = [
        max(1, int(free_len ** 0.5)),
        max(1, free_len // 16),
        max(1, free_len // 8),
        max(1, free_len // 4),
    ]

    for t in range(iterations):
        anchor = rep_free[rng.randrange(len(rep_free))]
        scores = []
        for c in free_cols:
            abit = (anchor >> c) & 1
            score = rng.random() / (1.0 + deg[c]) + (0.35 if abit else 0.0)
            scores.append((score, c))
        m = min(free_len, max(1, int(rng.choice(base_sizes) * rng.uniform(0.7, 1.8))))
        scores.sort(reverse=True)
        selected = [c for _, c in scores[:m]]

        free_bits = 0
        mix_count = 1 + (rng.randrange(3) if len(rep_free) > 1 else 0)
        for _ in range(mix_count):
            free_bits ^= rep_free[rng.randrange(len(rep_free))]
        proj_mask = 0
        for c in selected:
            proj_mask |= 1 << c
        free_bits &= proj_mask

        # The projection is deliberately noisy: it keeps lifted candidates near
        # low-degree coordinates while allowing escapes from the sampled coset.
        noise_p = 0.015 + 0.10 * (1.0 - (t / max(1, iterations)))
        for c in selected:
            if rng.random() < noise_p:
                free_bits ^= 1 << c
        if free_bits == 0:
            free_bits = 1 << selected[rng.randrange(len(selected))]

        consider(lifter.lift(free_bits), 4)

        if best is not None and best.bit_count() <= 2:
            break

    return best


def solve(hx_rows, hz_rows, n, seed):
    choices = [
        ("x", hz_rows, hx_rows, seed ^ 0x58A5),
        ("z", hx_rows, hz_rows, seed ^ 0xA35A),
    ]
    best = None
    for basis, check, stab, s in choices:
        v = random_projected_lift_search(check, stab, n, s)
        if v is not None:
            item = (v.bit_count(), basis, v)
            if best is None or item[0] < best[0]:
                best = item
    return best


def emit(obj):
    print(json.dumps(obj, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    try:
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
        hx_rows, nx = load_matrix(args.hx)
        hz_rows, nz = load_matrix(args.hz)
        n = max(nx, nz)
        hx_rows = [r & ((1 << n) - 1) for r in hx_rows]
        hz_rows = [r & ((1 << n) - 1) for r in hz_rows]

        ans = solve(hx_rows, hz_rows, n, int(args.seed))
        if ans is None:
            emit({"status": "failed", "basis": "x", "vector": [], "upper_bound": None})
            return 0
        w, basis, v = ans
        emit({"status": "completed", "basis": basis, "vector": vector_list(v, n), "upper_bound": w})
        return 0
    except Exception:
        emit({"status": "failed", "basis": "x", "vector": [], "upper_bound": None})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
