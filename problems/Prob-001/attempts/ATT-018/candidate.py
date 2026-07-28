#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def _row_from_dense(row) -> int:
    if isinstance(row, str):
        x = 0
        for i, ch in enumerate(row.strip()):
            if ch == "1":
                x |= 1 << i
        return x
    x = 0
    for i, v in enumerate(row):
        if int(v) & 1:
            x |= 1 << i
    return x


def load_matrix(arg: str) -> Tuple[List[int], int]:
    if os.path.exists(arg):
        with open(arg, "r", encoding="utf-8") as f:
            obj = json.load(f)
    else:
        obj = json.loads(arg)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        n = int(obj.get("n_cols", 0))
        rows = [_row_from_dense(r) for r in obj.get("data", [])]
        if n <= 0:
            n = max([r.bit_length() for r in rows] + [0])
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for rr in obj.get("rows", []):
            x = 0
            for c in rr:
                ci = int(c)
                if ci >= 0:
                    x |= 1 << ci
            rows.append(x)
        if n <= 0:
            n = max([r.bit_length() for r in rows] + [0])
        return rows, n

    if isinstance(obj, list):
        rows = [_row_from_dense(r) for r in obj]
        n = max([len(r) if not isinstance(r, str) else len(r.strip()) for r in obj] + [0])
        return rows, n

    raise ValueError("unsupported matrix JSON format")


class RowSpace:
    def __init__(self, rows: Iterable[int] = ()):
        self.basis: Dict[int, int] = {}
        for r in rows:
            self.add(r)

    def reduce(self, x: int) -> int:
        while x:
            p = x.bit_length() - 1
            b = self.basis.get(p)
            if b is None:
                return x
            x ^= b
        return 0

    def contains(self, x: int) -> bool:
        return self.reduce(x) == 0

    def add(self, x: int) -> bool:
        x = self.reduce(x)
        if not x:
            return False
        p = x.bit_length() - 1
        for q, b in list(self.basis.items()):
            if (b >> p) & 1:
                self.basis[q] = b ^ x
        self.basis[p] = x
        return True


class LinearSystem:
    def __init__(self, rows: Sequence[int], n: int):
        self.rows = list(rows)
        self.n = n
        self.m = len(rows)
        self.rref: Dict[int, Tuple[int, int]] = {}
        for i, r0 in enumerate(rows):
            r = r0
            t = 1 << i
            changed = True
            while changed:
                changed = False
                while r:
                    p = r.bit_length() - 1
                    item = self.rref.get(p)
                    if item is None:
                        break
                    r ^= item[0]
                    t ^= item[1]
                    changed = True
                if not r:
                    break
            if not r:
                continue
            p = r.bit_length() - 1
            for q, (br, bt) in list(self.rref.items()):
                if (br >> p) & 1:
                    self.rref[q] = (br ^ r, bt ^ t)
            self.rref[p] = (r, t)
        self.pivots = sorted(self.rref.keys(), reverse=True)
        self.pivot_set = set(self.pivots)

    def syndrome(self, v: int) -> int:
        s = 0
        for i, r in enumerate(self.rows):
            if ((r & v).bit_count() & 1) != 0:
                s |= 1 << i
        return s

    def in_kernel(self, v: int) -> bool:
        return self.syndrome(v) == 0

    def solve(self, syndrome: int, free_mask: int = 0) -> Optional[int]:
        x = trim_to_n(free_mask, self.n)
        for p, (row, trans) in self.rref.items():
            bit = ((trans & syndrome).bit_count() ^ (row & x).bit_count()) & 1
            if bit != 0:
                x |= 1 << p
            else:
                x &= ~(1 << p)
        if self.syndrome(x) == syndrome:
            return x
        return None

    def nullspace_basis(self) -> List[int]:
        out = []
        for f in range(self.n):
            if f in self.pivot_set:
                continue
            v = 1 << f
            for p, (row, _trans) in self.rref.items():
                if (row >> f) & 1:
                    v |= 1 << p
            out.append(v)
        return out


def bits_to_list(v: int, n: int) -> List[int]:
    return [int((v >> i) & 1) for i in range(n)]


def trim_to_n(v: int, n: int) -> int:
    return v & ((1 << n) - 1) if n > 0 else 0


def build_column_syndromes(check_rows: Sequence[int], n: int) -> List[int]:
    cols = [0] * n
    for r_i, row in enumerate(check_rows):
        x = row
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c < n:
                cols[c] |= 1 << r_i
            x ^= lsb
    return cols


def verify(v: int, n: int, check: LinearSystem, stab: RowSpace) -> bool:
    v = trim_to_n(v, n)
    return v != 0 and check.in_kernel(v) and not stab.contains(v)


def descend(v: int, n: int, stab_rows: Sequence[int], check: LinearSystem, stab: RowSpace, rng: random.Random) -> int:
    v = trim_to_n(v, n)
    if not verify(v, n, check, stab):
        return v
    rows = [trim_to_n(r, n) for r in stab_rows if trim_to_n(r, n)]
    current_w = v.bit_count()
    improved = True
    passes = 0
    while improved and passes < 8:
        improved = False
        passes += 1
        rng.shuffle(rows)
        for r in rows:
            u = v ^ r
            uw = u.bit_count()
            if uw < current_w and verify(u, n, check, stab):
                v, current_w = u, uw
                improved = True
    if len(rows) >= 2:
        for _ in range(min(400, 20 * len(rows))):
            r = 0
            for _j in range(1 + rng.randrange(min(5, len(rows)))):
                r ^= rows[rng.randrange(len(rows))]
            u = v ^ r
            if u.bit_count() < current_w and verify(u, n, check, stab):
                v, current_w = u, u.bit_count()
    return v


def biased_error(n: int, rng: random.Random, hot: Sequence[int], cold: Sequence[int], scale: int) -> int:
    if n <= 0:
        return 0
    v = 0
    mode = rng.random()
    if mode < 0.55 and hot:
        w = 1 + rng.randrange(max(1, min(len(hot), scale)))
        for c in rng.sample(list(hot), min(w, len(hot))):
            v ^= 1 << c
    elif mode < 0.85:
        w = 1 + rng.randrange(max(1, min(n, scale * 2)))
        for c in rng.sample(range(n), min(w, n)):
            v ^= 1 << c
    else:
        pool = list(cold) if cold else list(range(n))
        w = 1 + rng.randrange(max(1, min(len(pool), scale)))
        for c in rng.sample(pool, min(w, len(pool))):
            v ^= 1 << c
    return v


def search_side(name: str, n: int, check_rows: Sequence[int], stab_rows: Sequence[int], rng: random.Random) -> Optional[int]:
    check = LinearSystem(check_rows, n)
    stab = RowSpace(trim_to_n(r, n) for r in stab_rows)
    col_syn = build_column_syndromes(check_rows, n)
    degrees = [c.bit_count() for c in col_syn]
    order = sorted(range(n), key=lambda i: (degrees[i], rng.random()))
    hot = order[: max(1, n // 3)]
    cold = order[max(0, 2 * n // 3):]

    best: Optional[int] = None

    def keep(v: int) -> None:
        nonlocal best
        v = descend(v, n, stab_rows, check, stab, rng)
        if verify(v, n, check, stab) and (best is None or v.bit_count() < best.bit_count()):
            best = v

    # Basis-derived logicals provide the reliability fallback, then randomized
    # residual decoding tries to find a lighter representative in the coset.
    kernel_basis = check.nullspace_basis()
    rng.shuffle(kernel_basis)
    for b in kernel_basis:
        if verify(b, n, check, stab):
            keep(b)
            break

    if kernel_basis:
        for _ in range(min(600, 20 * len(kernel_basis) + 80)):
            v = 0
            draws = 1 + rng.randrange(min(8, len(kernel_basis)))
            for _j in range(draws):
                v ^= kernel_basis[rng.randrange(len(kernel_basis))]
            if verify(v, n, check, stab):
                keep(v)

    scale = max(2, min(32, int(n ** 0.5) + 2))
    iters = max(350, min(2500, 18 * n + 120))
    for t in range(iters):
        e = biased_error(n, rng, hot, cold, scale + (t % 7))
        s = 0
        x = e
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            s ^= col_syn[c]
            x ^= lsb
        free_trials = [0, e]
        if hot:
            hot_mask = 0
            for c in rng.sample(list(hot), min(len(hot), 1 + rng.randrange(max(1, min(len(hot), scale))))):
                if (e >> c) & 1:
                    hot_mask |= 1 << c
            free_trials.append(hot_mask)
        if t % 5 == 0:
            noisy = e
            for c in rng.sample(range(n), min(n, 1 + rng.randrange(max(1, scale)))):
                noisy ^= 1 << c
            free_trials.append(noisy)
        for free_mask in free_trials:
            corr = check.solve(s, free_mask)
            if corr is None:
                continue
            residual = trim_to_n(e ^ corr, n)
            if residual and verify(residual, n, check, stab):
                keep(residual)
        if best is not None and best.bit_count() <= 1:
            break

    return best


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
        n = max(nx, nz)
        hx = [trim_to_n(r, n) for r in hx]
        hz = [trim_to_n(r, n) for r in hz]
        rng = random.Random(args.seed)

        candidates = []
        xw = search_side("x", n, hz, hx, rng)
        if xw is not None:
            candidates.append(("x", xw))
        zw = search_side("z", n, hx, hz, rng)
        if zw is not None:
            candidates.append(("z", zw))

        if candidates:
            basis, vec = min(candidates, key=lambda item: (item[1].bit_count(), 0 if item[0] == "x" else 1))
            result = {
                "status": "completed",
                "basis": basis,
                "vector": bits_to_list(vec, n),
                "upper_bound": int(vec.bit_count()),
            }
        else:
            result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
