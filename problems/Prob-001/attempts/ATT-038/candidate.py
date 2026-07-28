#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def parity(x):
    return x.bit_count() & 1


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            v = 0
            for i, b in enumerate(r):
                if int(b) & 1:
                    v |= 1 << i
            rows.append(v)
        return rows, n

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n = int(obj.get("n_cols", 0))
        rows = []
        for r in obj["data"]:
            v = 0
            if n == 0:
                n = len(r)
            for i, b in enumerate(r):
                if int(b) & 1:
                    v |= 1 << i
            rows.append(v)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            v = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    v ^= 1 << c
                    if c + 1 > n:
                        n = c + 1
            rows.append(v)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def add_to_basis(basis, row):
    row = int(row)
    while row:
        p = row.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = row
            return True
        row ^= b
    return False


def make_basis(rows):
    basis = {}
    for r in rows:
        add_to_basis(basis, r)
    return basis


def in_span(row, basis):
    row = int(row)
    while row:
        p = row.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        row ^= b
    return True


def nullspace_basis(check_rows, n):
    rb = make_basis(check_rows)
    pivots = set(rb)
    free_cols = [i for i in range(n) if i not in pivots]
    out = []
    for f in free_cols:
        x = 1 << f
        for p in sorted(pivots):
            r = rb[p] & ~(1 << p)
            if parity(r & x):
                x |= 1 << p
        out.append(x)
    return out


def kernel_ok(v, check_rows):
    return all(parity(v & r) == 0 for r in check_rows)


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def verified(v, check_rows, stab_basis):
    return v != 0 and kernel_ok(v, check_rows) and not in_span(v, stab_basis)


def greedy_stabilizer_descent(v, stabs, rng, rounds=3):
    if not stabs:
        return v
    best = v
    best_w = v.bit_count()
    rows = sorted((s for s in stabs if s), key=int.bit_count)

    for _ in range(rounds):
        changed = False
        for s in rows:
            u = best ^ s
            w = u.bit_count()
            if w < best_w:
                best, best_w = u, w
                changed = True
        if not changed:
            break

    # A short randomized pass lets larger rows unlock later greedy reductions.
    temp = best
    temp_w = best_w
    limit = min(800, 30 * len(rows) + 80)
    for _ in range(limit):
        s = rows[rng.randrange(len(rows))]
        u = temp ^ s
        w = u.bit_count()
        if w <= temp_w or rng.random() < 0.015:
            temp, temp_w = u, w
            for s2 in rows[: min(len(rows), 80)]:
                z = temp ^ s2
                zw = z.bit_count()
                if zw < temp_w:
                    temp, temp_w = z, zw
            if temp_w < best_w:
                best, best_w = temp, temp_w
    return best


def quotient_logicals(check_rows, stab_rows, n):
    ns = nullspace_basis(check_rows, n)
    ns.sort(key=lambda x: (x.bit_count(), x))
    ext = make_basis(stab_rows)
    logicals = []
    for v in ns:
        trial = dict(ext)
        if add_to_basis(trial, v):
            logicals.append(v)
            ext = trial
    return logicals


def random_combo(indices, vecs, rng, max_terms):
    if not indices:
        return 0, 0
    rmax = min(max_terms, len(indices))
    r = 1 + int(rng.random() ** 1.8 * rmax)
    chosen = rng.sample(indices, r)
    v = 0
    c = 0
    for idx in chosen:
        v ^= vecs[idx]
        c ^= 1 << idx
    return v, c


def hot_coordinate_mask(vecs, n, rng, cap):
    freq = [0] * n
    for v in vecs:
        x = v
        while x:
            lsb = x & -x
            freq[lsb.bit_length() - 1] += 1
            x ^= lsb
    order = list(range(n))
    rng.shuffle(order)
    order.sort(key=lambda i: freq[i], reverse=True)
    mask = 0
    for i in order[: min(cap, n)]:
        if freq[i] > 0:
            mask |= 1 << i
    return mask


def mitm_support_assembly(logicals, stabs, check_rows, stab_basis, n, rng, deadline):
    if not logicals:
        return None

    reduced = [greedy_stabilizer_descent(v, stabs, rng, rounds=2) for v in logicals]
    best = None
    for v in reduced:
        if verified(v, check_rows, stab_basis):
            if best is None or v.bit_count() < best.bit_count():
                best = v

    k = len(reduced)
    width = min(k, 34)
    base_order = list(range(k))
    base_order.sort(key=lambda i: reduced[i].bit_count())

    passes = 0
    while time.time() < deadline and passes < 36:
        passes += 1
        elite = base_order[: min(k, max(8, width // 2))]
        rest = base_order[min(k, max(8, width // 2)) :]
        rng.shuffle(rest)
        chosen = (elite + rest)[:width]
        rng.shuffle(chosen)
        mid = len(chosen) // 2
        left = chosen[:mid]
        right = chosen[mid:]

        mask = hot_coordinate_mask([reduced[i] for i in chosen], n, rng, 56)
        table = {}
        samples = 1200 if n < 2000 else 700

        table[0] = (0, 0, 0)
        for _ in range(samples):
            v, c = random_combo(left, reduced, rng, 6)
            sig = v & mask
            w = v.bit_count()
            old = table.get(sig)
            if old is None or w < old[0]:
                table[sig] = (w, v, c)

        probes = [(0, 0)]
        for _ in range(samples):
            probes.append(random_combo(right, reduced, rng, 6))

        for rv, rc in probes:
            hit = table.get(rv & mask)
            if hit is None:
                continue
            _, lv, lc = hit
            if (lc ^ rc) == 0:
                continue
            cand = lv ^ rv
            cand = greedy_stabilizer_descent(cand, stabs, rng, rounds=2)
            if verified(cand, check_rows, stab_basis):
                if best is None or cand.bit_count() < best.bit_count():
                    best = cand

        # Inject a few fresh logical mixtures so later passes are not confined
        # to the same complement basis representatives.
        for _ in range(80):
            v, c = random_combo(base_order[: min(k, 64)], reduced, rng, 9)
            if c:
                v = greedy_stabilizer_descent(v, stabs, rng, rounds=2)
                if verified(v, check_rows, stab_basis):
                    if best is None or v.bit_count() < best.bit_count():
                        best = v

    return best


def search_basis(name, check_rows, stab_rows, n, rng, deadline):
    stab_basis = make_basis(stab_rows)
    stabs = list(stab_basis.values())
    logicals = quotient_logicals(check_rows, stab_rows, n)
    if not logicals:
        return None

    best = mitm_support_assembly(logicals, stabs, check_rows, stab_basis, n, rng, deadline)

    # Reliable basis-derived fallback: any complement vector is a verified
    # logical after certification, and stabilizer descent only changes its coset.
    for v in logicals:
        cand = greedy_stabilizer_descent(v, stabs, rng, rounds=4)
        if verified(cand, check_rows, stab_basis):
            if best is None or cand.bit_count() < best.bit_count():
                best = cand

    if best is None:
        return None
    return {"basis": name, "vector": vector_to_list(best, n), "upper_bound": best.bit_count()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    mask = (1 << n) - 1 if n else 0
    hx = [r & mask for r in hx]
    hz = [r & mask for r in hz]

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    deadline = time.time() + 8.5
    results = []
    # X logicals commute with Z checks and are nontrivial modulo X stabilizers.
    xres = search_basis("x", hz, hx, n, rng, deadline)
    if xres is not None:
        results.append(xres)
    zres = search_basis("z", hx, hz, n, rng, deadline)
    if zres is not None:
        results.append(zres)

    if results:
        results.sort(key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
        out = {"status": "completed", **results[0]}
    else:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))
