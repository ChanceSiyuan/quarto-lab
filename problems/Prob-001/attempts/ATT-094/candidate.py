#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time


def parse_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        n_cols = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for j, bit in enumerate(r):
                if bit & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n_cols
    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or row list")
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        data = obj["data"]
        n_cols = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for j, bit in enumerate(r):
                if bit & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n_cols
    if "rows" in obj:
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for j in r:
                jj = int(j)
                if jj >= 0:
                    x |= 1 << jj
            rows.append(x)
        if n_cols == 0:
            n_cols = max((x.bit_length() for x in rows), default=0)
        return rows, n_cols
    raise ValueError("unknown matrix JSON format")


def mask_n(n):
    return (1 << n) - 1 if n > 0 else 0


def clean_rows(rows, n):
    m = mask_n(n)
    return [int(r) & m for r in rows if (int(r) & m) != 0]


def echelon_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def reduce_with_basis(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return y
        y ^= b
    return 0


def in_span(x, basis):
    return reduce_with_basis(x, basis) == 0


def add_to_basis(row, basis):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def rref_basis(rows):
    basis = echelon_basis(rows)
    for p in sorted(list(basis.keys())):
        bit = 1 << p
        for q in list(basis.keys()):
            if q != p and (basis[q] & bit):
                basis[q] ^= basis[p]
    return basis


def nullspace_basis(rows, n):
    rref = rref_basis(rows)
    pivots = set(rref.keys())
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


def mat_vec_zero(rows, v):
    for r in rows:
        if ((r & v).bit_count() & 1) != 0:
            return False
    return True


def verified(v, check_rows, stab_basis):
    return v != 0 and mat_vec_zero(check_rows, v) and not in_span(v, stab_basis)


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def quotient_logicals(check_rows, stab_rows, n):
    ns = nullspace_basis(check_rows, n)
    span = echelon_basis(stab_rows)
    out = []
    for v in sorted(ns, key=lambda z: (z.bit_count(), z)):
        if not in_span(v, span):
            out.append(v)
            add_to_basis(v, span)
    return out


def greedy_descent(v, moves, rng, passes):
    cur = v
    cur_w = cur.bit_count()
    if not moves:
        return cur
    for _ in range(passes):
        improved = False
        order = moves[:]
        rng.shuffle(order)
        best = None
        best_w = cur_w
        for r, _rw in order:
            nw = (cur ^ r).bit_count()
            if nw < best_w:
                best = r
                best_w = nw
                if cur_w - nw >= 3 and rng.random() < 0.65:
                    break
        if best is not None:
            cur ^= best
            cur_w = best_w
            improved = True
        if not improved:
            break
    return cur


def stabilizer_walk(start, moves, check_rows, stab_basis, rng, budget):
    cur = start
    best = start
    cur_w = cur.bit_count()
    best_w = cur_w
    temp = max(1.0, cur_w / 3.0)
    tabu = {}
    if not moves:
        return best
    for step in range(max(1, budget)):
        if step % 29 == 0:
            cur = greedy_descent(cur, moves, rng, 5)
            cur_w = cur.bit_count()
            if cur_w < best_w and verified(cur, check_rows, stab_basis):
                best = cur
                best_w = cur_w
        sample_size = min(len(moves), 12 + (step % 17))
        cand = rng.sample(moves, sample_size) if sample_size < len(moves) else moves
        chosen = None
        chosen_score = None
        for r, rw in cand:
            if tabu.get(r, -1) > step:
                continue
            overlap = (cur & r).bit_count()
            delta = rw - 2 * overlap
            noise = rng.random() * temp
            score = delta + noise
            if chosen is None or score < chosen_score:
                chosen = (r, delta)
                chosen_score = score
        if chosen is None:
            continue
        r, delta = chosen
        accept = delta <= 0 or rng.random() < (temp / (temp + delta + 1.0))
        if accept:
            cur ^= r
            cur_w += delta
            tabu[r] = step + 3 + rng.randrange(7)
            if cur_w < best_w and verified(cur, check_rows, stab_basis):
                best = cur
                best_w = cur_w
        temp *= 0.997
        if temp < 0.08:
            temp = 0.08
    return greedy_descent(best, moves, rng, 10)


def random_logical_seed(logicals, rng):
    v = 0
    if not logicals:
        return 0
    order = logicals[:]
    rng.shuffle(order)
    p = rng.uniform(0.18, 0.55)
    for g in order:
        if rng.random() < p:
            v ^= g
    if v == 0:
        v = rng.choice(logicals)
    return v


def search_basis(name, check_rows, stab_rows, n, rng, seconds):
    stab_basis = echelon_basis(stab_rows)
    logicals = quotient_logicals(check_rows, stab_rows, n)
    if not logicals:
        return None
    moves = []
    for r in stab_rows:
        if r and mat_vec_zero(check_rows, r):
            moves.append((r, r.bit_count()))
    moves.sort(key=lambda x: x[1])
    deadline = time.monotonic() + seconds
    best = None
    for v in logicals:
        if verified(v, check_rows, stab_basis):
            w = greedy_descent(v, moves, rng, 16)
            if verified(w, check_rows, stab_basis):
                if best is None or w.bit_count() < best.bit_count():
                    best = w
    if best is None:
        for v in logicals:
            if verified(v, check_rows, stab_basis):
                best = v
                break
    reps = 0
    while time.monotonic() < deadline and reps < 240:
        reps += 1
        seed = random_logical_seed(logicals, rng)
        if best is not None and rng.random() < 0.35:
            seed ^= best
            if seed == 0:
                seed = random_logical_seed(logicals, rng)
        if not verified(seed, check_rows, stab_basis):
            continue
        local_budget = 120 + 5 * min(len(moves), 80) + rng.randrange(80)
        w = stabilizer_walk(seed, moves, check_rows, stab_basis, rng, local_budget)
        if verified(w, check_rows, stab_basis):
            if best is None or w.bit_count() < best.bit_count():
                best = w
    if best is None:
        return None
    return {"basis": name, "vector": best, "weight": best.bit_count()}


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()
    try:
        hx, nx = parse_matrix(args.hx)
        hz, nz = parse_matrix(args.hz)
        n = max(nx, nz)
        hx = clean_rows(hx, n)
        hz = clean_rows(hz, n)
        rng = random.Random(args.seed)
        # X logicals commute with Z checks and are compared modulo X stabilizers;
        # Z logicals commute with X checks and are compared modulo Z stabilizers.
        choices = []
        bx = search_basis("x", hz, hx, n, rng, 3.8)
        if bx is not None:
            choices.append(bx)
        bz = search_basis("z", hx, hz, n, rng, 3.8)
        if bz is not None:
            choices.append(bz)
        if choices:
            choices.sort(key=lambda d: (d["weight"], 0 if d["basis"] == "x" else 1))
            ans = choices[0]
            out = {
                "status": "completed",
                "basis": ans["basis"],
                "vector": vector_to_list(ans["vector"], n),
                "upper_bound": int(ans["weight"]),
            }
        else:
            out = {"status": "failed", "basis": "x", "vector": [0] * n, "upper_bound": 0}
    except Exception:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": 0}
    sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
