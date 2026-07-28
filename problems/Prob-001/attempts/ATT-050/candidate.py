#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", 0))
        if n <= 0 and data:
            n = max(len(r) for r in data)
        rows = []
        for r in data:
            bits = 0
            for j, v in enumerate(r):
                if int(v) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            bits = 0
            for j in r:
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
        for r in obj:
            bits = 0
            for j, v in enumerate(r):
                if int(v) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def weight(x):
    return int(x.bit_count())


def bit_positions(x):
    while x:
        lsb = x & -x
        yield lsb.bit_length() - 1
        x ^= lsb


def rref(rows):
    basis = [int(r) for r in rows if r]
    rank = 0
    pivots = []
    m = len(basis)
    col = 0
    while rank < m:
        pivot_i = -1
        pivot_col = None
        best = None
        for i in range(rank, m):
            if basis[i]:
                c = basis[i].bit_length() - 1
                if best is None or c > best:
                    best = c
                    pivot_i = i
                    pivot_col = c
        if pivot_i < 0:
            break
        basis[rank], basis[pivot_i] = basis[pivot_i], basis[rank]
        pbit = 1 << pivot_col
        for i in range(m):
            if i != rank and (basis[i] & pbit):
                basis[i] ^= basis[rank]
        pivots.append(pivot_col)
        rank += 1
        col += 1
    return basis[:rank], pivots


def reduce_by_basis(x, basis, pivots):
    y = int(x)
    for row, p in zip(basis, pivots):
        if (y >> p) & 1:
            y ^= row
    return y


def in_rowspace(x, basis, pivots):
    return reduce_by_basis(x, basis, pivots) == 0


def kernel_basis(check_rows, n):
    rb, piv = rref(check_rows)
    pivot_set = set(piv)
    out = []
    for f in range(n):
        if f in pivot_set:
            continue
        v = 1 << f
        for row, p in zip(rb, piv):
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome(v, rows):
    s = 0
    for i, r in enumerate(rows):
        if weight(v & r) & 1:
            s |= 1 << i
    return s


def vector_to_list(v, n):
    return [1 if ((v >> i) & 1) else 0 for i in range(n)]


def column_syndromes(rows, n):
    cols = [0] * n
    degrees = [0] * n
    for i, r in enumerate(rows):
        bit = 1 << i
        for c in bit_positions(r):
            if c < n:
                cols[c] ^= bit
                degrees[c] += 1
    return cols, degrees


def quotient_logicals(kbasis, stab_basis, stab_pivots):
    logicals = []
    quotient_basis = list(stab_basis)
    quotient_pivots = list(stab_pivots)
    for v in sorted(kbasis, key=weight):
        if not in_rowspace(v, quotient_basis, quotient_pivots):
            logicals.append(v)
            quotient_basis, quotient_pivots = rref(quotient_basis + [v])
    return logicals


def random_combo(rng, vecs, max_terms=None, p=None):
    if not vecs:
        return 0
    if p is None:
        if max_terms is None:
            max_terms = min(len(vecs), 1 + int(len(vecs) ** 0.5))
        terms = rng.randint(1, max_terms)
        idxs = rng.sample(range(len(vecs)), min(terms, len(vecs)))
        v = 0
        for i in idxs:
            v ^= vecs[i]
        return v
    v = 0
    for x in vecs:
        if rng.random() < p:
            v ^= x
    return v


def greedy_decode_syndrome(target_s, col_syn, degrees, rng, limit):
    """Randomized bit-flip decoder for H x = target_s."""
    residual = target_s
    corr = 0
    if residual == 0:
        return 0
    active = residual.bit_count()
    n = len(col_syn)
    order = list(range(n))
    for step in range(limit):
        best_score = None
        best_cols = []
        if step & 7 == 0:
            rng.shuffle(order)
        sample_all = active <= 32 or n <= 256 or (step % 5 == 0)
        candidates = order if sample_all else rng.sample(order, min(n, 96))
        for c in candidates:
            cs = col_syn[c]
            if not cs:
                continue
            hit = (residual & cs).bit_count()
            miss = degrees[c] - hit
            jitter = rng.random() * 0.45
            score = 2.0 * hit - miss - 0.015 * degrees[c] + jitter
            if best_score is None or score > best_score:
                best_score = score
                best_cols = [c]
            elif score == best_score:
                best_cols.append(c)
        if best_score is None or best_score <= 0.0:
            c = rng.randrange(n)
        else:
            c = rng.choice(best_cols)
        corr ^= 1 << c
        residual ^= col_syn[c]
        new_active = residual.bit_count()
        if new_active == 0:
            return corr
        if new_active > active + 6 and rng.random() < 0.35:
            # A perturbative step can escape short cycles, but keep it sparse.
            c2 = rng.randrange(n)
            corr ^= 1 << c2
            residual ^= col_syn[c2]
            new_active = residual.bit_count()
            if new_active == 0:
                return corr
        active = new_active
    return None


def local_stabilizer_descent(v, stab_rows, rng, rounds):
    if not stab_rows:
        return v
    rows = sorted([r for r in stab_rows if r], key=weight)
    cur = v
    cur_w = weight(cur)
    stale = 0
    for t in range(rounds):
        improved = False
        if t % 11 == 0:
            rng.shuffle(rows)
        for r in rows:
            nw = weight(cur ^ r)
            if nw < cur_w or (nw == cur_w and rng.random() < 0.015):
                cur ^= r
                cur_w = nw
                improved = True
        if improved:
            stale = 0
            continue
        stale += 1
        if stale >= 2:
            # Try a two-row residual move. It often removes decoder artifacts
            # that no single stabilizer row can improve.
            changed = False
            tries = min(256, len(rows) * 3)
            for _ in range(tries):
                a = rng.choice(rows)
                b = rng.choice(rows)
                r = a ^ b
                if r and weight(cur ^ r) < cur_w:
                    cur ^= r
                    cur_w = weight(cur)
                    changed = True
                    break
            if not changed:
                break
            stale = 0
    return cur


def verify(v, check_rows, stab_basis, stab_pivots):
    return v != 0 and syndrome(v, check_rows) == 0 and not in_rowspace(v, stab_basis, stab_pivots)


def search_basis(name, check_rows, stab_rows, n, rng, deadline):
    stab_basis, stab_pivots = rref(stab_rows)
    kbasis = kernel_basis(check_rows, n)
    logicals = quotient_logicals(kbasis, stab_basis, stab_pivots)
    if not logicals:
        return None

    best = None

    def consider(v):
        nonlocal best
        if not verify(v, check_rows, stab_basis, stab_pivots):
            return
        v2 = local_stabilizer_descent(v, stab_rows + stab_basis, rng, 4)
        if verify(v2, check_rows, stab_basis, stab_pivots):
            v = v2
        if best is None or weight(v) < weight(best):
            best = v

    for v in sorted(logicals, key=weight)[: min(len(logicals), 32)]:
        consider(local_stabilizer_descent(v, stab_rows + stab_basis, rng, 8))

    col_syn, degrees = column_syndromes(check_rows, n)
    base_pool = sorted(logicals + kbasis, key=weight)[: min(96, len(logicals) + len(kbasis))]
    rounds = 0
    max_rounds = 520 if n <= 512 else 220
    while time.time() < deadline and rounds < max_rounds:
        rounds += 1
        if rounds % 3 == 0:
            seed_log = random_combo(rng, logicals, max_terms=min(4, len(logicals)))
        else:
            seed_log = rng.choice(logicals)
        perturb = 0
        if base_pool and rng.random() < 0.55:
            perturb ^= random_combo(rng, base_pool, max_terms=min(6, len(base_pool)))
        flips = 1 + int(rng.expovariate(0.45))
        flips = min(flips, max(1, min(n, 24)))
        for _ in range(flips):
            perturb ^= 1 << rng.randrange(n)
        noisy = seed_log ^ perturb
        s = syndrome(noisy, check_rows)
        corr = greedy_decode_syndrome(s, col_syn, degrees, rng, limit=max(24, min(3 * n + 10, 1800)))
        if corr is None:
            continue
        residual = noisy ^ corr
        if verify(residual, check_rows, stab_basis, stab_pivots):
            consider(residual)
        else:
            # If the residual decoded into a stabilizer class, reattach a known
            # logical and keep the decoder-shaped error pattern as perturbation.
            consider(residual ^ seed_log)

    if best is None:
        for v in logicals:
            if verify(v, check_rows, stab_basis, stab_pivots):
                best = v
                break
    if best is None:
        return None
    return {"basis": name, "vector": vector_to_list(best, n), "upper_bound": weight(best)}


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
    n = max(nx, nz)
    mask = (1 << n) - 1 if n > 0 else 0
    hx = [r & mask for r in hx]
    hz = [r & mask for r in hz]

    os.makedirs(args.output_dir, exist_ok=True)
    deadline = time.time() + 7.0
    results = []
    order = [("x", hz, hx), ("z", hx, hz)]
    if rng.random() < 0.5:
        order.reverse()
    for name, check, stab in order:
        if time.time() >= deadline:
            break
        res = search_basis(name, check, stab, n, rng, deadline)
        if res is not None:
            results.append(res)

    if results:
        ans = min(results, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
        out = {
            "status": "completed",
            "basis": ans["basis"],
            "vector": ans["vector"],
            "upper_bound": ans["upper_bound"],
        }
    else:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
