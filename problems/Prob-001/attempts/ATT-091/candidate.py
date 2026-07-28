#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def fail():
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
    sys.exit(0)


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data", [])
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        if data and all(isinstance(x, int) for x in data):
            if n <= 0:
                fail()
            data = [data[i:i + n] for i in range(0, len(data), n)]
        rows = []
        for row in data:
            bits = 0
            if n <= 0:
                n = len(row)
            for j, x in enumerate(row):
                if int(x) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for row in obj.get("rows", []):
            bits = 0
            for j in row:
                jj = int(j)
                if jj >= 0:
                    bits |= 1 << jj
                    if jj + 1 > n:
                        n = jj + 1
            rows.append(bits)
        return rows, n

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for row in obj:
            bits = 0
            for j, x in enumerate(row):
                if int(x) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    fail()


def trim_rows(rows, n):
    mask = (1 << n) - 1 if n > 0 else 0
    return [r & mask for r in rows if (r & mask) != 0]


def rref_basis(rows, n):
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
        row = basis[p]
        for q in sorted(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= row
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


def kernel_basis(rows, n):
    piv = rref_basis(rows, n)
    pivot_cols = set(piv.keys())
    out = []
    for f in range(n):
        if f in pivot_cols:
            continue
        v = 1 << f
        for p, row in piv.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def quotient_logicals(check_rows, stab_rows, n):
    stab_basis = rref_basis(stab_rows, n)
    span_basis = dict(stab_basis)
    logicals = []
    for v in sorted(kernel_basis(check_rows, n), key=int.bit_count):
        if v and not in_span(v, span_basis):
            logicals.append(v)
            span_basis = rref_basis(list(span_basis.values()) + [v], n)
    return logicals, stab_basis


def verified(v, check_rows, stab_basis):
    if v == 0:
        return False
    for r in check_rows:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return not in_span(v, stab_basis)


def greedy_descent(v, stab_rows, rng, passes=8, row_order=None):
    if not stab_rows:
        return v
    rows = row_order if row_order is not None else list(stab_rows)
    best = v
    best_w = v.bit_count()
    stale = 0
    for _ in range(passes):
        improved = False
        rng.shuffle(rows)
        for r in rows:
            u = best ^ r
            w = u.bit_count()
            if w < best_w:
                best, best_w = u, w
                improved = True
        if not improved:
            stale += 1
            if stale >= 2:
                break
    return best


def block_perturb_descent(v, stab_rows, n, rng, deadline):
    if not stab_rows:
        return v
    best = greedy_descent(v, stab_rows, rng, passes=10)
    best_w = best.bit_count()
    cur = best
    scales = [max(4, n // d) for d in (2, 3, 5, 8, 13, 21, 34)]
    scales += [min(n, s) for s in (8, 16, 32, 64) if s <= n]
    scales = sorted(set(s for s in scales if 1 <= s <= n), reverse=True)
    tries = 0
    while time.time() < deadline and tries < 900:
        tries += 1
        width = rng.choice(scales) if scales else n
        start = rng.randrange(0, max(1, n - width + 1))
        block_mask = ((1 << width) - 1) << start
        active = cur & block_mask
        candidates = [r for r in stab_rows if r & block_mask]
        if not candidates:
            continue
        candidates.sort(key=lambda r: ((r & active).bit_count(), -(r & ~block_mask).bit_count()), reverse=True)
        cap = min(len(candidates), 10 + (tries % 17))
        pulse = 0
        for r in candidates[:cap]:
            overlap = (r & active).bit_count()
            spill = (r & ~block_mask).bit_count()
            if overlap > spill or rng.random() < 0.18:
                pulse ^= r
                active ^= r & block_mask
        if pulse == 0:
            pulse = rng.choice(candidates)
        u = cur ^ pulse
        # The perturbation jumps to another point in the same logical coset; the
        # subsequent descent only accepts a verified low-weight representative.
        u = greedy_descent(u, stab_rows, rng, passes=6, row_order=candidates[:cap] + stab_rows)
        uw = u.bit_count()
        if uw < best_w or (uw == best_w and rng.random() < 0.08):
            cur = u
            if uw < best_w:
                best, best_w = u, uw
        elif rng.random() < 0.04:
            cur = u
    return best


def recombine_start(logicals, rng, limit):
    if not logicals:
        return 0
    take = min(len(logicals), limit)
    idxs = list(range(len(logicals)))
    idxs.sort(key=lambda i: logicals[i].bit_count())
    pool = idxs[:max(take, min(len(idxs), 12))]
    v = 0
    count = 1 + rng.randrange(min(5, len(pool)))
    for i in rng.sample(pool, count):
        v ^= logicals[i]
    return v


def search_basis(name, check_rows, stab_rows, n, rng, seconds):
    logicals, stab_basis = quotient_logicals(check_rows, stab_rows, n)
    if not logicals:
        return None
    deadline = time.time() + seconds
    seeds = sorted(logicals, key=int.bit_count)[:min(len(logicals), 24)]
    best = None
    best_w = n + 1
    for v in seeds:
        if time.time() >= deadline:
            break
        slice_deadline = min(deadline, time.time() + max(0.05, seconds / max(8, len(seeds) + 4)))
        u = block_perturb_descent(v, stab_rows, n, rng, slice_deadline)
        if verified(u, check_rows, stab_basis) and u.bit_count() < best_w:
            best, best_w = u, u.bit_count()
    rounds = 0
    while time.time() < deadline and rounds < 120:
        rounds += 1
        v = recombine_start(logicals, rng, 32)
        if v == 0 or in_span(v, stab_basis):
            continue
        if stab_rows:
            for r in rng.sample(stab_rows, min(len(stab_rows), 1 + rng.randrange(6))):
                v ^= r
        slice_deadline = min(deadline, time.time() + 0.12 + 0.002 * min(n, 500))
        u = block_perturb_descent(v, stab_rows, n, rng, slice_deadline)
        if verified(u, check_rows, stab_basis) and u.bit_count() < best_w:
            best, best_w = u, u.bit_count()
    if best is None:
        for v in logicals:
            if verified(v, check_rows, stab_basis):
                best, best_w = v, v.bit_count()
                break
    if best is None:
        return None
    return name, best, best_w


def bits_to_list(v, n):
    return [1 if ((v >> i) & 1) else 0 for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        hx = trim_rows(hx, n)
        hz = trim_rows(hz, n)
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
        rng = random.Random(args.seed)
        per_basis = 5.5 if n <= 512 else 8.0
        rx = search_basis("x", hz, hx, n, rng, per_basis)
        rz = search_basis("z", hx, hz, n, rng, per_basis)
        choices = [r for r in (rx, rz) if r is not None]
        if not choices:
            fail()
        basis, vec, ub = min(choices, key=lambda t: (t[2], 0 if t[0] == "x" else 1))
        check = hz if basis == "x" else hx
        stab = hx if basis == "x" else hz
        if not verified(vec, check, rref_basis(stab, n)):
            fail()
        print(json.dumps({
            "status": "completed",
            "basis": basis,
            "vector": bits_to_list(vec, n),
            "upper_bound": int(ub),
        }, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
