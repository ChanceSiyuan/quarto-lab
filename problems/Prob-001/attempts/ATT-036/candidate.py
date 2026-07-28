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
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", obj.get("num_cols", max((len(r) for r in data), default=0))))
        rows = []
        for r in data:
            x = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            x = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    x |= 1 << c
            rows.append(x)
        if n == 0:
            n = max((r.bit_length() for r in rows), default=0)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def parity(x):
    return x.bit_count() & 1


def syndrome_zero(v, checks):
    for r in checks:
        if parity(v & r):
            return False
    return True


def rref(rows):
    piv = {}
    for x in rows:
        x = int(x)
        while x:
            p = x.bit_length() - 1
            y = piv.get(p)
            if y is None:
                piv[p] = x
                break
            x ^= y
    for p in sorted(piv):
        row = piv[p]
        for q in sorted(piv, reverse=True):
            if q != p and ((piv[q] >> p) & 1):
                piv[q] ^= row
    return piv


def reduce_with(v, piv):
    x = int(v)
    while x:
        p = x.bit_length() - 1
        y = piv.get(p)
        if y is None:
            return x
        x ^= y
    return 0


def in_span(v, piv):
    return reduce_with(v, piv) == 0


def nullspace_basis(rows, n):
    piv = rref(rows)
    pivot_cols = set(piv)
    basis = []
    for f in range(n):
        if f in pivot_cols:
            continue
        v = 1 << f
        for p, row in piv.items():
            if (row >> f) & 1:
                v |= 1 << p
        basis.append(v)
    return basis


def quotient_reps(kernel_rows, stabilizer_rows, n):
    k_basis = nullspace_basis(kernel_rows, n)
    span_rows = [x for x in stabilizer_rows if x]
    span = rref(span_rows)
    reps = []
    for v in k_basis:
        rem = reduce_with(v, span)
        if rem:
            reps.append(rem)
            span_rows.append(rem)
            span = rref(span_rows)
    return reps


def verified(v, kernel_rows, stabilizer_piv, n):
    mask = (1 << n) - 1 if n else 0
    v &= mask
    return v != 0 and syndrome_zero(v, kernel_rows) and not in_span(v, stabilizer_piv)


def int_to_list(v, n):
    return [int((v >> i) & 1) for i in range(n)]


def mixed_generators(stabilizer_rows, rng, limit):
    base = [x for x in stabilizer_rows if x]
    gens = list(base)
    if not base:
        return gens
    rounds = min(limit, max(8, 3 * len(base)))
    for _ in range(rounds):
        x = 0
        take = 1 + rng.randrange(min(5, len(base)))
        for _ in range(take):
            x ^= base[rng.randrange(len(base))]
        if x:
            gens.append(x)
    gens.sort(key=lambda z: z.bit_count())
    return gens[:limit]


def coset_minimize(v, stabilizer_rows, rng, deadline, n):
    best = v
    best_w = v.bit_count()
    gens = mixed_generators(stabilizer_rows, rng, 4096)
    if not gens:
        return best

    cur = v
    cur_w = best_w
    temp = 2.0
    passes = 0
    stagnant = 0
    while time.monotonic() < deadline and passes < 80 and stagnant < 12:
        improved = False
        rng.shuffle(gens)
        for g in gens:
            nw = (cur ^ g).bit_count()
            delta = nw - cur_w
            if delta < 0 or (delta <= 2 and rng.random() < 0.035 * temp):
                cur ^= g
                cur_w = nw
                if cur_w < best_w:
                    best = cur
                    best_w = cur_w
                    improved = True
                    if best_w <= 1:
                        return best
        if improved:
            stagnant = 0
        else:
            stagnant += 1
            if rng.random() < 0.55:
                cur = best
                cur_w = best_w
                for _ in range(1 + rng.randrange(3)):
                    cur ^= gens[rng.randrange(len(gens))]
                cur_w = cur.bit_count()
        temp *= 0.88
        passes += 1
    return best


def sample_quotient(reps, rng):
    m = len(reps)
    if m == 1:
        return reps[0]
    x = 0
    mode = rng.randrange(5)
    if mode == 0:
        order = sorted(range(m), key=lambda i: reps[i].bit_count())
        take = 1 + rng.randrange(min(m, 6))
        for i in order[:take]:
            if rng.random() < 0.7:
                x ^= reps[i]
    elif mode == 1:
        take = 1 + int(rng.expovariate(0.55)) % m
        for _ in range(take):
            x ^= reps[rng.randrange(m)]
    else:
        p = min(0.5, max(1.0 / m, rng.uniform(0.08, 0.32)))
        for r in reps:
            if rng.random() < p:
                x ^= r
    if x == 0:
        x = reps[rng.randrange(m)]
    return x


def search_basis(name, kernel_rows, stabilizer_rows, n, rng, seconds):
    reps = quotient_reps(kernel_rows, stabilizer_rows, n)
    if not reps:
        return None
    stab_piv = rref(stabilizer_rows)
    deadline = time.monotonic() + seconds
    best = None
    best_w = n + 1

    seeds = sorted(reps, key=lambda z: z.bit_count())
    attempts = 0
    while time.monotonic() < deadline and attempts < 180:
        if attempts < len(seeds):
            v = seeds[attempts]
        else:
            v = sample_quotient(reps, rng)
        local_deadline = min(deadline, time.monotonic() + max(0.015, seconds / 20.0))
        v = coset_minimize(v, stabilizer_rows, rng, local_deadline, n)
        if verified(v, kernel_rows, stab_piv, n):
            w = v.bit_count()
            if w < best_w:
                best = v
                best_w = w
        attempts += 1

    if best is None:
        for v in seeds:
            if verified(v, kernel_rows, stab_piv, n):
                best = v
                best_w = v.bit_count()
                break
    if best is None:
        return None
    return {"basis": name, "vector": int_to_list(best, n), "upper_bound": best_w}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz, max((r.bit_length() for r in hx + hz), default=0))
    mask = (1 << n) - 1 if n else 0
    hx = [r & mask for r in hx]
    hz = [r & mask for r in hz]

    os.makedirs(args.output_dir, exist_ok=True)

    # X logicals are ker(HZ) modulo row(HX); Z logicals are ker(HX) modulo row(HZ).
    per_side = 1.8
    choices = [
        ("x", hz, hx),
        ("z", hx, hz),
    ]
    if rng.randrange(2):
        choices.reverse()

    best = None
    for name, kernel, stabilizer in choices:
        got = search_basis(name, kernel, stabilizer, n, rng, per_side)
        if got is not None and (best is None or got["upper_bound"] < best["upper_bound"]):
            best = got

    if best is None:
        out = {"status": "failed", "basis": "x", "vector": [0] * n, "upper_bound": None}
    else:
        out = {
            "status": "completed",
            "basis": best["basis"],
            "vector": best["vector"],
            "upper_bound": best["upper_bound"],
        }
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
        print(json.dumps(out, separators=(",", ":")))
