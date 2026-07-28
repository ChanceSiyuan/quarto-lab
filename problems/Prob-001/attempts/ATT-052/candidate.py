#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time


def popcount(x):
    return x.bit_count()


def parity(x):
    return x.bit_count() & 1


def rows_from_public_json(obj):
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            v = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    v |= 1 << i
            rows.append(v)
        return rows, n

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            v = 0
            for i, b in enumerate(r[:n]):
                if int(b) & 1:
                    v |= 1 << i
            rows.append(v)
        return rows, n

    if "rows" in obj:
        data = obj["rows"]
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = 1 + max((max(r) for r in data if r), default=-1)
        rows = []
        for r in data:
            v = 0
            for j in r:
                jj = int(j)
                if 0 <= jj < n:
                    v ^= 1 << jj
            rows.append(v)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        return rows_from_public_json(json.load(f))


class GF2Basis:
    def __init__(self, rows=()):
        self.basis = {}
        for r in rows:
            self.add(r)

    def copy(self):
        other = GF2Basis()
        other.basis = dict(self.basis)
        return other

    def reduce(self, v):
        while v:
            p = v.bit_length() - 1
            b = self.basis.get(p)
            if b is None:
                break
            v ^= b
        return v

    def add(self, v):
        v = self.reduce(v)
        if not v:
            return False
        self.basis[v.bit_length() - 1] = v
        return True

    def contains(self, v):
        return self.reduce(v) == 0

    def rows(self):
        return list(self.basis.values())


def rref_low(rows, n):
    a = [r & ((1 << n) - 1) for r in rows if r]
    rank = 0
    pivots = []
    m = len(a)
    for col in range(n):
        pivot = None
        mask = 1 << col
        for i in range(rank, m):
            if a[i] & mask:
                pivot = i
                break
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        for i in range(m):
            if i != rank and (a[i] & mask):
                a[i] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == m:
            break
    return a[:rank], pivots


def nullspace_basis(check_rows, n):
    rref, pivots = rref_low(check_rows, n)
    pivot_set = set(pivots)
    out = []
    for f in range(n):
        if f in pivot_set:
            continue
        v = 1 << f
        bit = 1 << f
        for row, p in zip(rref, pivots):
            if row & bit:
                v |= 1 << p
        out.append(v)
    return out


def quotient_logical_basis(check_rows, stab_rows, n, rng):
    ns = nullspace_basis(check_rows, n)
    if not ns:
        return []

    stab_basis = GF2Basis(stab_rows)
    combined = stab_basis.copy()

    ordered = sorted(ns, key=popcount)
    tail = ordered[:]
    rng.shuffle(tail)
    ordered = ordered[: min(32, len(ordered))] + tail

    logicals = []
    seen = set()
    for v in ordered:
        if v in seen:
            continue
        seen.add(v)
        if combined.add(v):
            logicals.append(v)
    return logicals


def make_stabilizer_pool(stab_rows, n, rng, limit=2600):
    base = [r for r in stab_rows if r]
    if not base:
        return []

    reduced = GF2Basis(base).rows()
    pool = list({*base, *reduced})
    light = sorted(pool, key=popcount)[: min(180, len(pool))]

    # Quotient-space coset descent benefits from small stabilizer combinations:
    # they are still in the same coset but can expose cancellations unavailable
    # to single-row greedy descent.
    pair_budget = min(1200, max(100, 6 * len(light)))
    for _ in range(pair_budget):
        a = rng.choice(light)
        b = rng.choice(light)
        s = a ^ b
        if s:
            pool.append(s)

    if len(light) >= 3:
        for _ in range(min(500, 3 * len(light))):
            s = rng.choice(light) ^ rng.choice(light) ^ rng.choice(light)
            if s:
                pool.append(s)

    pool = list(set(pool))
    pool.sort(key=popcount)
    return pool[:limit]


def greedy_coset_descent(v, pool, rng, passes=4, randomized=True):
    best = v
    best_w = popcount(best)
    work = pool[:]
    for _ in range(passes):
        if randomized:
            rng.shuffle(work)
        changed = False
        for s in work:
            u = v ^ s
            uw = popcount(u)
            if uw < popcount(v):
                v = u
                changed = True
                if uw < best_w:
                    best, best_w = u, uw
        if not changed:
            break
    return best


def annealed_coset_minimize(v, pool, rng, deadline):
    if not pool:
        return v
    cur = greedy_coset_descent(v, pool, rng, passes=3, randomized=True)
    best = cur
    best_w = popcount(cur)
    steps = 0
    while time.monotonic() < deadline and steps < 9000:
        steps += 1
        s = rng.choice(pool)
        nxt = cur ^ s
        cw = popcount(cur)
        nw = popcount(nxt)
        temp = max(0.03, 1.2 * (1.0 - steps / 9000.0))
        accept = nw <= cw or rng.random() < pow(2.718281828, -(nw - cw) / max(1.0, temp * max(1, best_w)))
        if accept:
            cur = nxt
            if nw <= best_w + 2 and (steps & 15) == 0:
                cur = greedy_coset_descent(cur, pool, rng, passes=2, randomized=True)
                nw = popcount(cur)
            if nw < best_w:
                best, best_w = cur, nw
    return greedy_coset_descent(best, pool, rng, passes=5, randomized=False)


def verify(v, check_rows, stab_rows):
    if not v:
        return False
    for r in check_rows:
        if parity(r & v):
            return False
    return not GF2Basis(stab_rows).contains(v)


def sample_logical(logicals, rng, trial):
    k = len(logicals)
    if k == 1:
        return logicals[0]
    v = 0
    if trial < k:
        return logicals[trial]
    if trial < 2 * k:
        a = trial - k
        b = rng.randrange(k - 1)
        if b >= a:
            b += 1
        return logicals[a] ^ logicals[b]

    # Sparse quotient samples dominate early; occasional denser samples help
    # when the light representative is hidden by cancellations among logicals.
    p = rng.choice((0.18, 0.28, 0.40, 0.55))
    while v == 0:
        for g in logicals:
            if rng.random() < p:
                v ^= g
    return v


def search_basis(name, check_rows, stab_rows, n, seed, seconds):
    rng = random.Random((seed << 8) ^ (17 if name == "x" else 53))
    logicals = quotient_logical_basis(check_rows, stab_rows, n, rng)
    if not logicals:
        return None

    pool = make_stabilizer_pool(stab_rows, n, rng)
    deadline = time.monotonic() + seconds
    best = None
    best_w = n + 1

    trials = 0
    min_trials = min(96, max(18, 5 * len(logicals)))
    max_trials = min(520, max(min_trials, 72 + 8 * len(logicals)))
    while trials < max_trials and (time.monotonic() < deadline or trials < min_trials):
        v = sample_logical(logicals, rng, trials)
        if not v:
            trials += 1
            continue
        if trials < len(logicals):
            u = greedy_coset_descent(v, pool, rng, passes=6, randomized=False)
        else:
            local_deadline = min(deadline, time.monotonic() + 0.006)
            u = annealed_coset_minimize(v, pool, rng, local_deadline)
        if verify(u, check_rows, stab_rows):
            w = popcount(u)
            if w < best_w:
                best, best_w = u, w
        trials += 1

    if best is None:
        # Linear-algebra fallback: quotient basis elements are already valid
        # logical representatives before coset minimization.
        for v in logicals:
            if verify(v, check_rows, stab_rows):
                w = popcount(v)
                if w < best_w:
                    best, best_w = v, w

    if best is None:
        return None
    return {"basis": name, "int_vector": best, "upper_bound": best_w}


def int_to_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]

        start = time.monotonic()
        # Keep runtime bounded but give both quotient searches a chance.
        total = 18.0
        x = search_basis("x", hz, hx, n, args.seed, total * 0.48)
        elapsed = time.monotonic() - start
        z = search_basis("z", hx, hz, n, args.seed, max(2.0, total - elapsed))
        candidates = [c for c in (x, z) if c is not None]
        if not candidates:
            result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
        else:
            best = min(candidates, key=lambda c: c["upper_bound"])
            result = {
                "status": "completed",
                "basis": best["basis"],
                "vector": int_to_bits(best["int_vector"], n),
                "upper_bound": int(best["upper_bound"]),
            }
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
