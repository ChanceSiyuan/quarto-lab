#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time


def read_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        return [row_to_int(r) for r in data], n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        return [row_to_int(r) for r in data], n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    x ^= 1 << c
            rows.append(x)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def row_to_int(row):
    x = 0
    for i, v in enumerate(row):
        if int(v) & 1:
            x |= 1 << i
    return x


def int_to_list(x, n):
    return [(x >> i) & 1 for i in range(n)]


def gf2_rref(rows):
    basis = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    for p in sorted(basis):
        bp = basis[p]
        for q in list(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= bp
    return basis


def in_rowspace(x, basis):
    y = int(x)
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        y ^= b
    return True


def nullspace_basis(check_rows, n):
    rref = gf2_rref(check_rows)
    pivots = set(rref)
    free_cols = [c for c in range(n) if c not in pivots]
    out = []
    for f in free_cols:
        v = 1 << f
        for p, row in rref.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome_zero(v, checks):
    for r in checks:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def verified(v, checks, stabilizer_basis):
    return v != 0 and syndrome_zero(v, checks) and not in_rowspace(v, stabilizer_basis)


def row_weight_key(x):
    return (x.bit_count(), x)


def greedy_descent(v, stab_rows, checks, stab_basis, rng, passes=5):
    if not stab_rows:
        return v if verified(v, checks, stab_basis) else 0
    cur = v
    rows = list(stab_rows)
    rows.sort(key=row_weight_key)
    for _ in range(passes):
        improved = False
        if rng.random() < 0.35:
            rng.shuffle(rows)
        for r in rows:
            nxt = cur ^ r
            if nxt.bit_count() < cur.bit_count():
                cur = nxt
                improved = True
        if not improved:
            break
    return cur if verified(cur, checks, stab_basis) else v


def build_row_neighborhoods(stab_rows):
    col_to_rows = {}
    supports = []
    for i, r in enumerate(stab_rows):
        cols = []
        x = r
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            cols.append(c)
            col_to_rows.setdefault(c, []).append(i)
            x ^= lsb
        supports.append(cols)
    neigh = []
    for cols in supports:
        s = set()
        for c in cols:
            s.update(col_to_rows.get(c, ()))
        neigh.append(list(s))
    return supports, neigh


def perturb_blocks(v, stab_rows, supports, neigh, rng, scale):
    if not stab_rows:
        return v
    active = []
    for i, cols in enumerate(supports):
        ov = 0
        for c in cols:
            ov += (v >> c) & 1
        if ov:
            active.append((ov, i))
    if active and rng.random() < 0.80:
        active.sort(reverse=True)
        seed_idx = active[rng.randrange(min(len(active), 16))][1]
    else:
        seed_idx = rng.randrange(len(stab_rows))
    chosen = {seed_idx}
    frontier = [seed_idx]
    while len(chosen) < scale and frontier:
        i = frontier.pop(rng.randrange(len(frontier)))
        ns = neigh[i] if i < len(neigh) else []
        rng.shuffle(ns)
        for j in ns[: max(2, scale)]:
            if j not in chosen:
                chosen.add(j)
                frontier.append(j)
                if len(chosen) >= scale:
                    break
    while len(chosen) < scale and len(chosen) < len(stab_rows):
        chosen.add(rng.randrange(len(stab_rows)))
    out = v
    for i in chosen:
        # Favor rows that remove current support, but keep some heat for escape.
        ov = (out & stab_rows[i]).bit_count()
        rw = stab_rows[i].bit_count()
        p = 0.30 + 0.50 * (ov / rw if rw else 0.0)
        if rng.random() < p:
            out ^= stab_rows[i]
    return out


def quotient_seeds(null_basis, stab_basis, checks, limit):
    seeds = []
    acc = 0
    for b in sorted(null_basis, key=row_weight_key):
        if verified(b, checks, stab_basis):
            seeds.append(b)
        acc ^= b
        if verified(acc, checks, stab_basis):
            seeds.append(acc)
        if len(seeds) >= limit:
            break
    return seeds


def random_logical(null_basis, stab_basis, checks, rng):
    if not null_basis:
        return 0
    for _ in range(64):
        v = 0
        # Sparse-to-moderate combinations usually expose lighter logicals than
        # dense nullspace sums while still changing quotient sectors.
        p = rng.choice((0.08, 0.13, 0.21, 0.34, 0.50))
        for b in null_basis:
            if rng.random() < p:
                v ^= b
        if verified(v, checks, stab_basis):
            return v
    for b in null_basis:
        if verified(b, checks, stab_basis):
            return b
    return 0


def search_basis(name, checks, stabilizers, n, seed):
    rng = random.Random((seed << 7) ^ (0x58 if name == "x" else 0x9E))
    stab_basis = gf2_rref(stabilizers)
    null_basis = nullspace_basis(checks, n)
    seeds = quotient_seeds(null_basis, stab_basis, checks, 96)
    if not seeds:
        v = random_logical(null_basis, stab_basis, checks, rng)
        if v:
            seeds = [v]
    if not seeds:
        return None

    stab_rows = [r for r in stabilizers if r]
    stab_rows.sort(key=row_weight_key)
    supports, neigh = build_row_neighborhoods(stab_rows)

    best = None
    deadline = time.monotonic() + 8.0
    scales = [1, 2, 3, 5, 8, 13, 21, 34]

    def consider(v):
        nonlocal best
        if verified(v, checks, stab_basis):
            v = greedy_descent(v, stab_rows, checks, stab_basis, rng)
            if best is None or v.bit_count() < best.bit_count():
                best = v

    for s in seeds:
        consider(s)
    rounds = 260 + 18 * min(len(null_basis), 80) + 8 * min(len(stab_rows), 120)
    for t in range(rounds):
        if time.monotonic() > deadline:
            break
        if best is not None and rng.random() < 0.58:
            v = best
        elif seeds and rng.random() < 0.50:
            v = rng.choice(seeds)
        else:
            v = random_logical(null_basis, stab_basis, checks, rng)
            if not v:
                continue

        # Multi-scale block perturbation: apply one to three linked stabilizer
        # row blocks, then certify-preserving local descent in the same coset.
        for _ in range(1 + (rng.random() < 0.45) + (rng.random() < 0.15)):
            scale = rng.choice(scales)
            if stab_rows:
                scale = min(scale, len(stab_rows))
            v = perturb_blocks(v, stab_rows, supports, neigh, rng, scale)
        consider(v)

        if t % 17 == 0:
            mix = 0
            for _ in range(rng.randint(1, 4)):
                mix ^= rng.choice(seeds)
            if verified(mix, checks, stab_basis):
                consider(mix)

    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    try:
        hx, nx = read_matrix(args.hx)
        hz, nz = read_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]

        xw = search_basis("x", hz, hx, n, args.seed)
        zw = search_basis("z", hx, hz, n, args.seed)
        choices = []
        if xw is not None:
            choices.append(("x", xw))
        if zw is not None:
            choices.append(("z", zw))
        if choices:
            basis, vec = min(choices, key=lambda kv: (kv[1].bit_count(), kv[0]))
            out = {
                "status": "completed",
                "basis": basis,
                "vector": int_to_list(vec, n),
                "upper_bound": int(vec.bit_count()),
            }
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
