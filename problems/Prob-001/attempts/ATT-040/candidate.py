#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj.get("data") or []
        n = int(obj.get("n_cols", 0))
        rows = []
        for row in data:
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x |= 1 << i
            rows.append(x)
        if n == 0 and data:
            n = len(data[0])
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for row in obj.get("rows") or []:
            x = 0
            for j in row:
                jj = int(j)
                if jj >= 0:
                    x |= 1 << jj
            rows.append(x)
        return rows, n

    if isinstance(obj, list):
        n = len(obj[0]) if obj else 0
        rows = []
        for row in obj:
            x = 0
            for i, bit in enumerate(row):
                if bit & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def rref_dict(rows):
    basis = {}
    for row in rows:
        x = int(row)
        for p in sorted(basis, reverse=True):
            if (x >> p) & 1:
                x ^= basis[p]
        if x:
            p = x.bit_length() - 1
            for q, old in list(basis.items()):
                if (old >> p) & 1:
                    basis[q] = old ^ x
            basis[p] = x
    return basis


def reduce_by_basis(x, basis):
    x = int(x)
    for p in sorted(basis, reverse=True):
        if (x >> p) & 1:
            x ^= basis[p]
    return x


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    basis = rref_dict(rows)
    pivots = set(basis)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in basis.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def quotient_logical_generators(kernel_basis, stab_basis):
    residual_basis = {}
    gens = []
    for v in kernel_basis:
        r = reduce_by_basis(v, stab_basis)
        x = r
        for p in sorted(residual_basis, reverse=True):
            if (x >> p) & 1:
                x ^= residual_basis[p]
        if x:
            p = x.bit_length() - 1
            for q, old in list(residual_basis.items()):
                if (old >> p) & 1:
                    residual_basis[q] = old ^ x
            residual_basis[p] = x
            gens.append(v)
    return gens


def mat_vec_zero(rows, v):
    for row in rows:
        if ((row & v).bit_count() & 1) != 0:
            return False
    return True


def bits_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def column_degrees(rows, n):
    deg = [0] * n
    for row in rows:
        x = row
        while x:
            lsb = x & -x
            deg[lsb.bit_length() - 1] += 1
            x ^= lsb
    return deg


def support_indices(v):
    out = []
    x = v
    while x:
        lsb = x & -x
        out.append(lsb.bit_length() - 1)
        x ^= lsb
    return out


def bp_reliability(rows, n, rng, iterations=5):
    """Small min-sum style reliability pass used only to bias restarts."""
    if n == 0:
        return []
    deg = column_degrees(rows, n)
    priors = [rng.gauss(0.0, 0.65) - 0.08 * deg[i] for i in range(n)]
    check_supp = [support_indices(r) for r in rows if r]
    var_to_checks = [[] for _ in range(n)]
    for ci, supp in enumerate(check_supp):
        for j in supp:
            var_to_checks[j].append(ci)

    c2v = {}
    v2c = {}
    for ci, supp in enumerate(check_supp):
        for j in supp:
            v2c[(j, ci)] = priors[j]
            c2v[(ci, j)] = 0.0

    for _ in range(iterations):
        for ci, supp in enumerate(check_supp):
            vals = [v2c[(j, ci)] for j in supp]
            if not vals:
                continue
            signs = 1.0
            absvals = []
            for val in vals:
                if val < 0:
                    signs *= -1.0
                absvals.append(abs(val))
            m1 = min(absvals)
            for j, val in zip(supp, vals):
                s = signs * (-1.0 if val < 0 else 1.0)
                c2v[(ci, j)] = 0.72 * s * m1
        for j in range(n):
            for ci in var_to_checks[j]:
                msg = priors[j]
                for ck in var_to_checks[j]:
                    if ck != ci:
                        msg += c2v[(ck, j)]
                v2c[(j, ci)] = max(-8.0, min(8.0, msg))

    rel = []
    for j in range(n):
        val = priors[j]
        for ci in var_to_checks[j]:
            val += c2v[(ci, j)]
        # Low check degree and small absolute belief mean "unreliable"; prefer it.
        rel.append(abs(val) + 0.13 * deg[j] + rng.random() * 0.025)
    return rel


def weighted_score(v, rel):
    score = 0.0
    x = v
    while x:
        lsb = x & -x
        score += rel[lsb.bit_length() - 1]
        x ^= lsb
    return score


def greedy_coset_reduce(v, stab_rows, rel, rng, passes=4):
    if not stab_rows:
        return v
    cur = v
    cur_w = cur.bit_count()
    cur_s = weighted_score(cur, rel)
    rows = list(stab_rows)
    for _ in range(passes):
        rng.shuffle(rows)
        improved = False
        for row in rows:
            nv = cur ^ row
            nw = nv.bit_count()
            if nw > cur_w:
                continue
            ns = weighted_score(nv, rel)
            if nw < cur_w or ns + 1.0e-9 < cur_s:
                cur, cur_w, cur_s = nv, nw, ns
                improved = True
        if not improved:
            break
    return cur


def random_logical_combo(gens, rel, rng):
    if len(gens) == 1:
        return gens[0]
    weights = []
    for g in gens:
        supp = support_indices(g)
        if not supp:
            weights.append(0.1)
            continue
        avg_rel = sum(rel[i] for i in supp) / len(supp)
        weights.append(1.0 / (0.2 + avg_rel))
    v = 0
    chosen = False
    scale = sum(weights) / max(1, len(weights))
    for g, w in zip(gens, weights):
        p = min(0.82, max(0.08, 0.34 * w / (scale + 1.0e-12)))
        if rng.random() < p:
            v ^= g
            chosen = True
    if not chosen:
        v = gens[rng.randrange(len(gens))]
    return v


def verified(v, commute_rows, stab_basis):
    return v != 0 and mat_vec_zero(commute_rows, v) and not in_rowspace(v, stab_basis)


def search_basis(name, commute_rows, stab_rows, n, rng, deadline):
    stab_basis = rref_dict(stab_rows)
    kernel = nullspace_basis(commute_rows, n)
    gens = quotient_logical_generators(kernel, stab_basis)
    if not gens:
        return None

    stab_rref_rows = list({r for r in stab_rows if r} | set(stab_basis.values()))
    best = None

    # Reliable fallback: quotient basis representatives are logical whenever k>0.
    for g in gens:
        if verified(g, commute_rows, stab_basis):
            if best is None or g.bit_count() < best.bit_count():
                best = g

    rounds = 48 + 8 * min(len(gens), 40) + min(120, n)
    for t in range(rounds):
        if time.monotonic() > deadline:
            break
        rel = bp_reliability(commute_rows, n, rng, iterations=3 + (t % 4))
        starts = [random_logical_combo(gens, rel, rng)]
        if best is not None and rng.random() < 0.45:
            starts.append(best)
        if rng.random() < 0.25:
            starts.append(gens[rng.randrange(len(gens))])
        for start in starts:
            cand = greedy_coset_reduce(start, stab_rref_rows, rel, rng, passes=3 + (t % 3))
            if verified(cand, commute_rows, stab_basis):
                if best is None or cand.bit_count() < best.bit_count():
                    best = cand

    if best is None:
        return None
    return {"basis": name, "vector": bits_to_list(best, n), "upper_bound": best.bit_count()}


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
    if nx != n:
        hx = [r & ((1 << n) - 1) for r in hx]
    if nz != n:
        hz = [r & ((1 << n) - 1) for r in hz]

    os.makedirs(args.output_dir, exist_ok=True)
    deadline = time.monotonic() + 8.0

    results = []
    # X logicals commute with HZ and are nontrivial modulo HX.
    xres = search_basis("x", hz, hx, n, rng, deadline)
    if xres is not None:
        results.append(xres)
    # Z logicals commute with HX and are nontrivial modulo HZ.
    zres = search_basis("z", hx, hz, n, rng, deadline)
    if zres is not None:
        results.append(zres)

    if results:
        best = min(results, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
        out = {
            "status": "completed",
            "basis": best["basis"],
            "vector": best["vector"],
            "upper_bound": best["upper_bound"],
        }
    else:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
