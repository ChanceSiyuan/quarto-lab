#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            mask = 0
            for i, bit in enumerate(r):
                if bit & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            mask = 0
            for i, bit in enumerate(r[:n]):
                if bit & 1:
                    mask |= 1 << i
            rows.append(mask)
        return rows, n

    if "rows" in obj:
        sparse = obj.get("rows") or []
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        if n == 0:
            n = 1 + max((c for r in sparse for c in r), default=-1)
        rows = []
        for r in sparse:
            mask = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    mask ^= 1 << c
            rows.append(mask)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def add_to_basis(basis, x):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is not None:
            x ^= b
            continue
        for q, y in list(basis.items()):
            if (y >> p) & 1:
                basis[q] = y ^ x
        basis[p] = x
        return True
    return False


def make_basis(rows):
    basis = {}
    for r in rows:
        add_to_basis(basis, r)
    return basis


def reduce_by_basis(x, basis):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def kernel_basis(check_rows, n):
    rref = make_basis(check_rows)
    pivots = set(rref)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rref.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def parity(x):
    return x.bit_count() & 1


def in_kernel(v, checks):
    return all(parity(v & r) == 0 for r in checks)


def verified(v, checks, stab_basis):
    return v != 0 and in_kernel(v, checks) and not in_span(v, stab_basis)


def vector_from_mask(v, n):
    return [(v >> i) & 1 for i in range(n)]


def quotient_reps(checks, stabilizers, n):
    kb = kernel_basis(checks, n)
    span = make_basis(stabilizers)
    reps = []
    for v in sorted(kb, key=lambda x: (x.bit_count(), x)):
        if reduce_by_basis(v, span) != 0:
            reps.append(v)
            add_to_basis(span, v)
    return reps, kb


def greedy_descent(v, stab_rows, passes=3):
    cur = v
    cur_w = cur.bit_count()
    ordered = sorted([r for r in stab_rows if r], key=lambda x: x.bit_count())
    for _ in range(passes):
        changed = False
        for r in ordered:
            nv = cur ^ r
            nw = nv.bit_count()
            if nw < cur_w:
                cur, cur_w = nv, nw
                changed = True
        if not changed:
            break
    return cur


def random_logical_combo(rng, reps):
    v = 0
    used = False
    for r in reps:
        if rng.getrandbits(1):
            v ^= r
            used = True
    if not used and reps:
        v = rng.choice(reps)
    return v


def walk_coset(rng, start, stab_rows, checks, stab_basis, deadline):
    cur = greedy_descent(start, stab_rows, 5)
    if not verified(cur, checks, stab_basis):
        cur = start
    best = cur
    best_w = best.bit_count()
    rows = [r for r in stab_rows if r]
    if not rows:
        return best

    row_weights = [max(1, r.bit_count()) for r in rows]
    temp = 2.0
    stale = 0
    while time.time() < deadline:
        r = rng.choice(rows)
        nxt = cur ^ r
        cw = cur.bit_count()
        nw = nxt.bit_count()
        accept = nw <= cw
        if not accept:
            accept = rng.random() < min(0.35, pow(2.718281828, -(nw - cw) / max(0.15, temp)))
        if accept:
            cur = nxt
            if nw < best_w and verified(nxt, checks, stab_basis):
                best, best_w = nxt, nw
                stale = 0
            else:
                stale += 1
        else:
            stale += 1

        if stale > 40:
            cur = greedy_descent(best ^ rng.choice(rows), rows, 3)
            stale = 0
        temp *= 0.999

        # A small burst tries products of two stabilizers. This keeps the
        # syndrome fixed while crossing single-row local minima.
        if rng.random() < 0.08:
            a = rng.randrange(len(rows))
            b = rng.randrange(len(rows))
            hop = cur ^ rows[a] ^ rows[b]
            hop = greedy_descent(hop, rows, 2)
            if verified(hop, checks, stab_basis) and hop.bit_count() <= cur.bit_count() + rng.randrange(3):
                cur = hop
                if hop.bit_count() < best_w:
                    best, best_w = hop, hop.bit_count()

    return best


def search_basis(name, checks, stabilizers, n, rng, budget_seconds):
    stab_basis = make_basis(stabilizers)
    reps, kb = quotient_reps(checks, stabilizers, n)
    if not reps:
        return None

    starts = list(reps)
    for _ in range(min(32, max(8, 2 * len(reps)))):
        starts.append(random_logical_combo(rng, reps))
    for v in sorted(kb, key=lambda x: x.bit_count())[: min(24, len(kb))]:
        if verified(v, checks, stab_basis):
            starts.append(v)

    best = None
    deadline = time.time() + budget_seconds
    i = 0
    while time.time() < deadline and starts:
        start = starts[i % len(starts)]
        if i >= len(starts):
            start = random_logical_combo(rng, reps)
        cand = walk_coset(rng, start, stabilizers, checks, stab_basis, min(deadline, time.time() + 0.035))
        if verified(cand, checks, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand
                if best.bit_count() == 1:
                    break
        i += 1
    if best is None:
        for v in reps:
            if verified(v, checks, stab_basis):
                best = v
                break
    if best is None:
        return None
    return {"basis": name, "vector": vector_from_mask(best, n), "upper_bound": best.bit_count()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    mask_n = (1 << n) - 1 if n else 0
    hx = [r & mask_n for r in hx]
    hz = [r & mask_n for r in hz]

    os.makedirs(args.output_dir, exist_ok=True)

    # X logicals commute with Z checks and are quotiented by X stabilizers.
    # Z logicals commute with X checks and are quotiented by Z stabilizers.
    first = "x" if rng.getrandbits(1) else "z"
    plans = [first, "z" if first == "x" else "x"]
    results = []
    for b in plans:
        if b == "x":
            res = search_basis("x", hz, hx, n, rng, 1.35)
        else:
            res = search_basis("z", hx, hz, n, rng, 1.35)
        if res is not None:
            results.append(res)
            if res["upper_bound"] == 1:
                break

    if results:
        ans = min(results, key=lambda r: (r["upper_bound"], 0 if r["basis"] == first else 1))
        ans = {"status": "completed", **ans}
    else:
        ans = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(ans, separators=(",", ":")))


if __name__ == "__main__":
    main()
