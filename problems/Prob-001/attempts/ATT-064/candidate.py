#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def bit_count(x):
    return x.bit_count()


def rows_to_basis(rows):
    basis = {}
    for x in rows:
        y = int(x)
        while y:
            p = y.bit_length() - 1
            if p in basis:
                y ^= basis[p]
            else:
                basis[p] = y
                break
    return basis


def reduce_by_basis(x, basis):
    y = int(x)
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return y
        y ^= b
    return 0


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def rank_rows(rows):
    return len(rows_to_basis(rows))


def kernel_basis(check_rows, n):
    basis = rows_to_basis(check_rows)
    pivots = set(basis.keys())
    free_cols = [c for c in range(n) if c not in pivots]
    out = []
    for f in free_cols:
        v = 1 << f
        # Because each reduced row has pivot p and may contain free columns,
        # setting one free variable determines pivot variables independently.
        for p, row in sorted(basis.items()):
            if (bit_count(row & v) & 1):
                v |= 1 << p
        out.append(v)
    return out


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            x = 0
            for i, v in enumerate(r):
                if int(v) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "rows" in obj and ("num_cols" in obj or "n_cols" in obj):
        n = int(obj.get("num_cols", obj.get("n_cols")))
        rows = []
        for r in obj["rows"]:
            x = 0
            for c in r:
                ci = int(c)
                if 0 <= ci < n:
                    x |= 1 << ci
            rows.append(x)
        return rows, n

    if "data" in obj:
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        data = obj["data"]
        rows = []
        if data and all(isinstance(r, list) for r in data):
            if n <= 0:
                n = max((len(r) for r in data), default=0)
            for r in data:
                x = 0
                for i, v in enumerate(r[:n]):
                    if int(v) & 1:
                        x |= 1 << i
                rows.append(x)
        else:
            if n <= 0:
                raise ValueError("flat dense data requires n_cols")
            for start in range(0, len(data), n):
                x = 0
                for i, v in enumerate(data[start:start + n]):
                    if int(v) & 1:
                        x |= 1 << i
                rows.append(x)
        return rows, n

    raise ValueError("unrecognized matrix JSON format")


def verify(v, check_rows, stab_basis):
    if v == 0:
        return False
    for r in check_rows:
        if bit_count(r & v) & 1:
            return False
    return not in_span(v, stab_basis)


def logical_generators(check_rows, stab_rows, n):
    ns = kernel_basis(check_rows, n)
    span = rows_to_basis(stab_rows)
    gens = []
    for v in sorted(ns, key=bit_count):
        if v and not in_span(v, span):
            gens.append(v)
            span = rows_to_basis(list(span.values()) + [v])
    return gens


def greedy_reduce(v, reducers, check_rows, stab_basis, deadline, rng):
    cur = v
    improved = True
    passes = 0
    while improved and time.time() < deadline and passes < 20:
        improved = False
        passes += 1
        order = list(reducers)
        rng.shuffle(order)
        order.sort(key=lambda r: bit_count(cur ^ r))
        for r in order:
            nv = cur ^ r
            if bit_count(nv) < bit_count(cur) and verify(nv, check_rows, stab_basis):
                cur = nv
                improved = True
    return cur


def anneal_reduce(v, reducers, check_rows, stab_basis, deadline, rng, steps):
    cur = v
    best = v
    cw = bit_count(cur)
    bw = cw
    if not reducers:
        return best
    for t in range(steps):
        if time.time() >= deadline:
            break
        r = reducers[rng.randrange(len(reducers))]
        nv = cur ^ r
        nw = bit_count(nv)
        delta = nw - cw
        temp = max(0.05, 2.5 * (1.0 - t / max(1, steps)))
        if delta <= 0 or rng.random() < pow(2.718281828, -delta / temp):
            if verify(nv, check_rows, stab_basis):
                cur, cw = nv, nw
                if nw < bw:
                    best, bw = nv, nw
    return best


def make_reducers(stab_rows, rng, deadline):
    base = [r for r in stab_rows if r]
    base.sort(key=bit_count)
    keep = base[: min(len(base), 512)]
    reducers = list(keep)
    target = min(2500, max(200, 8 * len(keep)))
    attempts = 0
    max_attempts = max(200, 6 * target)
    while len(reducers) < target and keep and attempts < max_attempts and time.time() < deadline:
        attempts += 1
        a = keep[rng.randrange(len(keep))]
        b = keep[rng.randrange(len(keep))]
        x = a ^ b
        if len(keep) > 2 and rng.random() < 0.35:
            x ^= keep[rng.randrange(len(keep))]
        if x:
            reducers.append(x)
    reducers.sort(key=bit_count)
    return reducers[:2500]


def candidate_search(name, check_rows, stab_rows, n, rng, deadline):
    stab_basis = rows_to_basis(stab_rows)
    gens = logical_generators(check_rows, stab_rows, n)
    if not gens:
        return None
    reducers = make_reducers(stab_rows, rng, deadline)
    best = None

    def consider(v):
        nonlocal best
        if verify(v, check_rows, stab_basis):
            v = greedy_reduce(v, reducers, check_rows, stab_basis, deadline, rng)
            if best is None or bit_count(v) < bit_count(best):
                best = v

    for g in gens:
        consider(g)

    lg = len(gens)
    rounds = 0
    max_rounds = 400 + 60 * min(lg, 32)
    while time.time() < deadline and rounds < max_rounds:
        rounds += 1
        if rng.random() < 0.55:
            idxs = [rng.randrange(lg)]
            extra = 1 + int(rng.random() < 0.35) + int(rng.random() < 0.12)
            for _ in range(extra):
                idxs.append(rng.randrange(lg))
        else:
            p = min(0.5, max(1.0 / max(1, lg), rng.expovariate(4.0)))
            idxs = [i for i in range(lg) if rng.random() < p]
            if not idxs:
                idxs = [rng.randrange(lg)]
        v = 0
        for i in idxs:
            v ^= gens[i]
        if reducers:
            for _ in range(rng.randrange(0, 4)):
                v ^= reducers[rng.randrange(len(reducers))]
        if verify(v, check_rows, stab_basis):
            v = anneal_reduce(v, reducers, check_rows, stab_basis, deadline, rng, 80)
            consider(v)

    if best is None:
        for g in gens:
            if verify(g, check_rows, stab_basis):
                best = g
                break
    return (name, best) if best is not None else None


def bits_to_list(v, n):
    return [int((v >> i) & 1) for i in range(n)]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args(argv)

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    hx, nx = parse_matrix(args.hx)
    hz, nz = parse_matrix(args.hz)
    n = max(nx, nz)
    mask = (1 << n) - 1 if n > 0 else 0
    hx = [r & mask for r in hx]
    hz = [r & mask for r in hz]
    rng = random.Random(args.seed)
    deadline = time.time() + 28.0

    options = []
    # X logicals commute with HZ and are not in row(HX); Z logicals vice versa.
    for label, check, stab in (("x", hz, hx), ("z", hx, hz)):
        res = candidate_search(label, check, stab, n, rng, deadline)
        if res is not None:
            options.append(res)

    if options:
        basis, vec = min(options, key=lambda item: bit_count(item[1]))
        out = {
            "status": "completed",
            "basis": basis,
            "vector": bits_to_list(vec, n),
            "upper_bound": bit_count(vec),
        }
    else:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
