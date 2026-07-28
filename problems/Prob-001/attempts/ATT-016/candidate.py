#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time


def row_weight(x):
    return int(x.bit_count())


def lowest_bit_index(x):
    return (x & -x).bit_length() - 1


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

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

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or a list of rows")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data") or []
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
        data = obj.get("rows") or []
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n <= 0:
            n = 1 + max((max(r) for r in data if r), default=-1)
        rows = []
        for r in data:
            v = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    v |= 1 << c
            rows.append(v)
        return rows, n

    raise ValueError("unrecognized matrix format")


def rref_low(rows, n):
    basis = {}
    mask = (1 << n) - 1 if n else 0
    for row in rows:
        v = row & mask
        while v:
            p = lowest_bit_index(v)
            b = basis.get(p)
            if b is None:
                break
            v ^= b
        if not v:
            continue
        p = lowest_bit_index(v)
        for q, b in list(basis.items()):
            if (b >> p) & 1:
                basis[q] = b ^ v
        basis[p] = v
    pivots = sorted(basis)
    return [(p, basis[p]) for p in pivots]


def reduce_by_rref(v, rref):
    w = v
    changed = True
    while changed and w:
        changed = False
        for p, row in rref:
            if (w >> p) & 1:
                w ^= row
                changed = True
    return w


def in_rowspace(v, rref):
    return reduce_by_rref(v, rref) == 0


def kernel_basis(check_rows, n):
    rref = rref_low(check_rows, n)
    pivots = {p for p, _ in rref}
    free_cols = [c for c in range(n) if c not in pivots]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in rref:
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out, rref


def columns_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        v = r
        while v:
            lb = v & -v
            deg[lb.bit_length() - 1] += 1
            v ^= lb
    return deg


def bit_list(v, n):
    return [int((v >> i) & 1) for i in range(n)]


def zero_syndrome(v, check_rows):
    for r in check_rows:
        if row_weight(v & r) & 1:
            return False
    return True


def verify(v, check_rows, stab_rref):
    return v != 0 and zero_syndrome(v, check_rows) and not in_rowspace(v, stab_rref)


def greedy_coset_descent(v, stab_rows, rng, passes=18):
    if not stab_rows:
        return v
    rows = [r for r in stab_rows if r]
    best = v
    best_w = row_weight(best)
    order = rows[:]
    for _ in range(passes):
        improved = False
        rng.shuffle(order)
        for r in order:
            cand = best ^ r
            cw = row_weight(cand)
            if cw < best_w or (cw == best_w and rng.random() < 0.015):
                best, best_w = cand, cw
                improved = True
        if not improved:
            break
    return best


def focused_stabilizer_shake(v, stab_rows, rng, rounds):
    if not stab_rows:
        return v
    cur = v
    rows = stab_rows[:]
    for _ in range(rounds):
        w = row_weight(cur)
        touching = [r for r in rows if row_weight(r & cur) * 3 >= max(1, row_weight(r))]
        pool = touching if touching else rows
        r = rng.choice(pool)
        cand = cur ^ r
        if row_weight(cand) <= w + rng.randint(0, 2):
            cur = cand
    return cur


def make_sampler(kernel, check_rows, stab_rows, n):
    deg_c = columns_degrees(check_rows, n)
    deg_s = columns_degrees(stab_rows, n)
    scores = []
    for v in kernel:
        cols = bit_list(v, n)
        support = [i for i, b in enumerate(cols) if b]
        if support:
            score = sum(1.0 / (1 + deg_c[i] + 0.35 * deg_s[i]) for i in support) / len(support)
        else:
            score = 0.0
        scores.append(score)
    total = sum(scores)
    if total <= 0:
        weights = [1.0 / max(1, row_weight(v)) for v in kernel]
    else:
        weights = scores
    return weights


def weighted_pick(items, weights, rng):
    s = sum(weights)
    if s <= 0:
        return rng.randrange(len(items))
    t = rng.random() * s
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if acc >= t:
            return i
    return len(items) - 1


def random_kernel_combo(kernel, weights, rng, mode):
    m = len(kernel)
    if m == 0:
        return 0
    v = 0
    if mode == 0:
        target = 1 + int(rng.expovariate(1.0 / max(1.0, min(8.0, m / 6.0))))
        for _ in range(min(m, target)):
            v ^= kernel[weighted_pick(kernel, weights, rng)]
    elif mode == 1:
        p = min(0.5, max(0.03, 2.5 / m))
        for b in kernel:
            if rng.random() < p:
                v ^= b
        if v == 0:
            v = rng.choice(kernel)
    elif mode == 2:
        idxs = sorted(range(m), key=lambda i: (row_weight(kernel[i]), -weights[i]))
        window = idxs[: max(1, min(m, 24))]
        for i in window:
            if rng.random() < 0.25:
                v ^= kernel[i]
        if v == 0:
            v = kernel[rng.choice(window)]
    else:
        trials = 1 + rng.randrange(min(m, 10))
        for _ in range(trials):
            v ^= rng.choice(kernel)
    return v


def search_basis(name, check_rows, stab_rows, n, rng, deadline):
    stab_rref = rref_low(stab_rows, n)
    kernel, check_rref = kernel_basis(check_rows, n)
    if not kernel:
        return None

    weights = make_sampler(kernel, check_rows, stab_rows, n)
    candidates = []

    for b in sorted(kernel, key=row_weight)[: min(len(kernel), 96)]:
        if not in_rowspace(b, stab_rref):
            candidates.append(b)
            candidates.append(greedy_coset_descent(b, stab_rows, rng, passes=28))

    attempts = 900 + 45 * min(n, 400) + 12 * min(len(kernel), 500)
    best = None
    best_w = 10**18

    def consider(v):
        nonlocal best, best_w
        v = greedy_coset_descent(v, stab_rows, rng, passes=20)
        if verify(v, check_rows, stab_rref):
            w = row_weight(v)
            if w < best_w:
                best, best_w = v, w

    for v in candidates:
        consider(v)

    for t in range(attempts):
        if time.monotonic() > deadline:
            break
        mode = t % 4
        v = random_kernel_combo(kernel, weights, rng, mode)
        if v == 0 or in_rowspace(v, stab_rref):
            continue
        if t % 5 == 0:
            v = focused_stabilizer_shake(v, stab_rows, rng, rounds=1 + (t % 7))
        consider(v)

    if best is not None:
        return name, best, best_w

    # Reliable basis-derived fallback for positive-k CSS inputs.
    for b in kernel:
        if verify(b, check_rows, stab_rref):
            b = greedy_coset_descent(b, stab_rows, rng, passes=30)
            if verify(b, check_rows, stab_rref):
                return name, b, row_weight(b)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    hx, nx = parse_matrix(args.hx)
    hz, nz = parse_matrix(args.hz)
    n = max(nx, nz)
    mask = (1 << n) - 1 if n else 0
    hx = [r & mask for r in hx]
    hz = [r & mask for r in hz]

    deadline = time.monotonic() + 25.0
    searches = [
        ("x", hz, hx),
        ("z", hx, hz),
    ]
    rng.shuffle(searches)

    best = None
    for name, check_rows, stab_rows in searches:
        res = search_basis(name, check_rows, stab_rows, n, rng, deadline)
        if res is None:
            continue
        if best is None or res[2] < best[2]:
            best = res

    if best is None:
        result = {"status": "failed", "basis": "x", "vector": [0] * n, "upper_bound": 0}
    else:
        basis, vec, wt = best
        result = {
            "status": "completed",
            "basis": basis,
            "vector": bit_list(vec, n),
            "upper_bound": wt,
        }
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": 0}, separators=(",", ":")))
        sys.exit(0)
