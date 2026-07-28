#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    rows = []
    n = None
    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", 0))
        for row in data:
            x = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    x ^= 1 << j
            rows.append(x)
    elif isinstance(obj, dict) and "rows" in obj:
        data = obj.get("rows") or []
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        for row in data:
            x = 0
            for j in row:
                jj = int(j)
                if 0 <= jj < n:
                    x ^= 1 << jj
            rows.append(x)
    elif isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        for row in obj:
            x = 0
            for j, bit in enumerate(row):
                if bit & 1:
                    x ^= 1 << j
            rows.append(x)
    else:
        raise ValueError("unsupported matrix JSON format")

    if n is None:
        n = 0
    mask = (1 << n) - 1 if n > 0 else 0
    return [r & mask for r in rows], n


def gf2_rref(rows):
    basis = {}
    for raw in rows:
        x = raw
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    for p in sorted(basis):
        bp = basis[p]
        for q in sorted(basis, reverse=True):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= bp
    return basis


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return y
        y ^= b
    return 0


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(check_rows, n):
    rref = gf2_rref(check_rows)
    pivots = set(rref.keys())
    free_cols = [j for j in range(n) if j not in pivots]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in rref.items():
            if (row >> f) & 1:
                v ^= 1 << p
        out.append(v)
    return out


def quotient_basis(kernel_basis, stabilizer_rows):
    span = gf2_rref(stabilizer_rows)
    reps = []
    for v in sorted(kernel_basis, key=lambda z: (z.bit_count(), z)):
        if v and not in_span(v, span):
            reps.append(v)
            x = reduce_by_basis(v, span)
            if x:
                span[x.bit_length() - 1] = x
    return reps


def syndrome_zero(v, check_rows):
    for r in check_rows:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def verified(v, check_rows, stabilizer_basis):
    return v != 0 and syndrome_zero(v, check_rows) and not in_span(v, stabilizer_basis)


def random_combo(vectors, rng):
    x = 0
    used = False
    for v in vectors:
        if rng.getrandbits(1):
            x ^= v
            used = True
    if not used and vectors:
        x = vectors[rng.randrange(len(vectors))]
    return x


def light_seed(logical_reps, rng):
    if not logical_reps:
        return 0
    dim = len(logical_reps)
    if dim <= 2:
        return random_combo(logical_reps, rng)
    # Bias toward small quotient combinations, with occasional dense samples.
    if rng.random() < 0.72:
        take = 1 + int(rng.expovariate(0.85))
        take = max(1, min(dim, take))
        idxs = rng.sample(range(dim), take)
        x = 0
        for i in idxs:
            x ^= logical_reps[i]
        return x
    return random_combo(logical_reps, rng)


def stochastic_coset_minimize(v, stab_rows, rng, deadline):
    if not stab_rows or time.monotonic() >= deadline:
        return v
    rows = [r for r in stab_rows if r]
    if not rows:
        return v
    rows.sort(key=lambda z: z.bit_count())
    cur = v
    cur_w = cur.bit_count()
    best = cur
    best_w = cur_w

    # Fast deterministic descent inside the stabilizer coset.
    improved = True
    rounds = 0
    while improved and rounds < 8 and time.monotonic() < deadline:
        improved = False
        rounds += 1
        for r in rows:
            w = (cur ^ r).bit_count()
            if w < cur_w:
                cur ^= r
                cur_w = w
                improved = True
                if w < best_w:
                    best = cur
                    best_w = w

    temp = max(1.0, best_w / 3.0)
    step = 0
    limit = 2500 + 28 * len(rows)
    while step < limit and time.monotonic() < deadline:
        step += 1
        r = rows[rng.randrange(len(rows))]
        cand = cur ^ r
        cw = cand.bit_count()
        delta = cw - cur_w
        if delta <= 0 or rng.random() < pow(2.718281828, -delta / temp):
            cur = cand
            cur_w = cw
            if cw < best_w:
                best = cand
                best_w = cw
        if step % 64 == 0:
            temp *= 0.92
            if temp < 0.25:
                cur = best
                cur_w = best_w
                temp = max(0.5, best_w / 6.0)
        if step % 257 == 0:
            cur = best
            cur_w = best_w
            for _ in range(1 + rng.randrange(4)):
                cur ^= rows[rng.randrange(len(rows))]
            cur_w = cur.bit_count()
    return best


def solve_basis(name, check_rows, stabilizer_rows, n, rng, deadline):
    stab_basis = gf2_rref(stabilizer_rows)
    k_basis = nullspace_basis(check_rows, n)
    reps = quotient_basis(k_basis, stabilizer_rows)
    if not reps:
        return None

    best = None
    for v in reps:
        cand = stochastic_coset_minimize(v, stabilizer_rows, rng, deadline)
        if verified(cand, check_rows, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand
    attempts = 0
    # Quotient-space sampling: every sample is a nonzero logical coset, then
    # stochastic minimization searches that coset for a lighter representative.
    while time.monotonic() < deadline and attempts < 700:
        attempts += 1
        v = light_seed(reps, rng)
        if not v:
            continue
        cand = stochastic_coset_minimize(v, stabilizer_rows, rng, deadline)
        if verified(cand, check_rows, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand
    if best is None:
        for v in reps:
            if verified(v, check_rows, stab_basis):
                best = v
                break
    if best is None:
        return None
    return {"basis": name, "bits": best, "weight": best.bit_count()}


def bits_to_list(x, n):
    return [int((x >> j) & 1) for j in range(n)]


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", required=True, type=int)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    try:
        hx, nx = parse_matrix(args.hx)
        hz, nz = parse_matrix(args.hz)
        n = max(nx, nz)
        if nx != n:
            hx = [r & ((1 << n) - 1) for r in hx]
        if nz != n:
            hz = [r & ((1 << n) - 1) for r in hz]

        rng = random.Random(args.seed)
        start = time.monotonic()
        # Keep runtime bounded while giving larger instances more room.
        budget = 5.0
        if n > 250:
            budget = 7.5
        if n > 900:
            budget = 10.0
        deadline = start + budget

        zx = solve_basis("x", hz, hx, n, rng, deadline)
        zz = solve_basis("z", hx, hz, n, rng, deadline)
        choices = [c for c in (zx, zz) if c is not None]
        if not choices:
            emit({"status": "failed", "basis": "x", "vector": [], "upper_bound": None})
            return 0
        best = min(choices, key=lambda c: (c["weight"], 0 if c["basis"] == "x" else 1))
        emit(
            {
                "status": "completed",
                "basis": best["basis"],
                "vector": bits_to_list(best["bits"], n),
                "upper_bound": best["weight"],
            }
        )
        return 0
    except Exception:
        emit({"status": "failed", "basis": "x", "vector": [], "upper_bound": None})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
