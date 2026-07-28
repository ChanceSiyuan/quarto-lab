#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def row_weight(x):
    return int(x.bit_count())


def parse_matrix_arg(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
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
            rows.append(bits)
        if n <= 0 and rows:
            n = max(r.bit_length() for r in rows)
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


def add_rref_row(basis, row):
    x = row
    while x:
        p = x.bit_length() - 1
        y = basis.get(p)
        if y is None:
            for q, z in list(basis.items()):
                if (z >> p) & 1:
                    basis[q] = z ^ x
            basis[p] = x
            return True
        x ^= y
    return False


def make_rref(rows):
    basis = {}
    for r in rows:
        if r:
            add_rref_row(basis, r)
    return basis


def reduce_by_basis(row, basis):
    x = row
    while x:
        p = x.bit_length() - 1
        y = basis.get(p)
        if y is None:
            return x
        x ^= y
    return 0


def in_rowspace(row, basis):
    return reduce_by_basis(row, basis) == 0


def nullspace_basis(rows, n):
    rref = make_rref(rows)
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
    return all(((r & v).bit_count() & 1) == 0 for r in rows)


def verified(v, commute_rows, stabilizer_basis):
    return v != 0 and mat_vec_zero(commute_rows, v) and not in_rowspace(v, stabilizer_basis)


def vector_to_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def logical_seed_basis(commute_rows, stabilizer_rows, n):
    stab_basis = make_rref(stabilizer_rows)
    span = dict(stab_basis)
    seeds = []
    for v in nullspace_basis(commute_rows, n):
        if v and reduce_by_basis(v, span) != 0:
            seeds.append(v)
            add_rref_row(span, v)
    return seeds, stab_basis


def build_col_to_rows(rows, n):
    col_to_rows = [[] for _ in range(n)]
    for i, r in enumerate(rows):
        x = r
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            if j < n:
                col_to_rows[j].append(i)
            x ^= lsb
    return col_to_rows


def guided_candidates(v, col_to_rows, row_count, rng, cap):
    seen = set()
    cols = []
    x = v
    while x:
        lsb = x & -x
        cols.append(lsb.bit_length() - 1)
        x ^= lsb
    rng.shuffle(cols)
    for c in cols[: min(len(cols), 96)]:
        for ri in col_to_rows[c]:
            if ri not in seen:
                seen.add(ri)
                if len(seen) >= cap:
                    return list(seen)
    extra = min(max(8, cap // 5), row_count)
    for _ in range(extra):
        if row_count:
            seen.add(rng.randrange(row_count))
    return list(seen)


def greedy_sweep(v, stab_rows):
    improved = True
    while improved:
        improved = False
        base_w = row_weight(v)
        best_v = v
        best_w = base_w
        for r in stab_rows:
            u = v ^ r
            w = row_weight(u)
            if w < best_w:
                best_w = w
                best_v = u
        if best_w < base_w:
            v = best_v
            improved = True
    return v


def tabu_minimize(start, stab_rows, col_to_rows, rng, deadline):
    if not stab_rows:
        return start
    v = greedy_sweep(start, stab_rows)
    best = v
    best_w = row_weight(v)
    tabu_until = {}
    row_count = len(stab_rows)
    tenure_base = 7 + min(31, max(1, row_count.bit_length()))
    stagnant = 0
    it = 0
    while time.monotonic() < deadline:
        it += 1
        cur_w = row_weight(v)
        cap = 96 if cur_w < 256 else 160
        cand = guided_candidates(v, col_to_rows, row_count, rng, cap)
        if not cand:
            break
        chosen = None
        chosen_score = None
        for ri in cand:
            u = v ^ stab_rows[ri]
            w = row_weight(u)
            delta = w - cur_w
            tabu = tabu_until.get(ri, 0) > it
            if tabu and w >= best_w:
                continue
            score = delta + rng.random() * (0.20 + min(2.0, stagnant / 400.0))
            if chosen is None or score < chosen_score:
                chosen = ri
                chosen_score = score
        if chosen is None:
            chosen = rng.randrange(row_count)
        v ^= stab_rows[chosen]
        tabu_until[chosen] = it + tenure_base + rng.randrange(tenure_base)
        w = row_weight(v)
        if w < best_w:
            best = v
            best_w = w
            stagnant = 0
            v = greedy_sweep(v, stab_rows)
            if row_weight(v) < best_w:
                best = v
                best_w = row_weight(v)
        else:
            stagnant += 1
        if stagnant and stagnant % 250 == 0:
            # Diversify inside the same logical coset by taking a short random
            # stabilizer walk, then greedily descend again.
            for _ in range(1 + rng.randrange(4)):
                v ^= stab_rows[rng.randrange(row_count)]
            v = greedy_sweep(v, stab_rows)
    return best


def random_logical_combo(seeds, rng):
    v = 0
    for s in seeds:
        if rng.getrandbits(1):
            v ^= s
    if v == 0 and seeds:
        v = rng.choice(seeds)
    return v


def search_basis(name, commute_rows, stabilizer_rows, n, rng, deadline):
    started = time.monotonic()
    seeds, stab_basis = logical_seed_basis(commute_rows, stabilizer_rows, n)
    if not seeds:
        return None
    col_to_rows = build_col_to_rows(stabilizer_rows, n)
    best = None
    seed_order = list(seeds)
    seed_order.sort(key=row_weight)
    trials = 0
    last_improved = 0
    min_trials = min(40, max(8, 2 * len(seed_order)))
    while time.monotonic() < deadline:
        if trials < len(seed_order):
            v = seed_order[trials]
        else:
            v = random_logical_combo(seeds, rng)
            # Bias some trials toward sparse basis-derived combinations.
            if len(seeds) > 1 and rng.random() < 0.45:
                v = 0
                for s in rng.sample(seeds, rng.randrange(1, min(len(seeds), 4) + 1)):
                    v ^= s
        trials += 1
        if not verified(v, commute_rows, stab_basis):
            continue
        slice_seconds = min(0.22, 0.035 + 0.0006 * len(stabilizer_rows))
        slice_deadline = min(deadline, time.monotonic() + slice_seconds)
        u = tabu_minimize(v, stabilizer_rows, col_to_rows, rng, slice_deadline)
        if verified(u, commute_rows, stab_basis):
            if best is None or row_weight(u) < row_weight(best):
                best = u
                last_improved = trials
        if trials >= max(12, 4 * len(seeds)) and best is not None and len(stabilizer_rows) == 0:
            break
        if best is not None and row_weight(best) <= 1:
            break
        if (
            best is not None
            and trials >= min_trials
            and trials - last_improved >= max(6, min_trials // 2)
            and time.monotonic() - started >= 0.35
        ):
            break
    if best is None:
        for v in seed_order:
            if verified(v, commute_rows, stab_basis):
                best = v
                break
    if best is None:
        return None
    return {"basis": name, "vector": best, "upper_bound": row_weight(best)}


def solve(hx_rows, hz_rows, n, seed):
    rng = random.Random(seed)
    # Keep the entrypoint responsive under unknown harness limits while still
    # giving larger checks a little more search time.
    seconds = float(os.environ.get("CANDIDATE_TIME_SECONDS", "5.0"))
    deadline = time.monotonic() + max(1.0, seconds)
    mid = time.monotonic() + max(0.35, seconds * 0.48)
    zx = search_basis("x", hz_rows, hx_rows, n, rng, mid)
    zz = search_basis("z", hx_rows, hz_rows, n, rng, deadline)
    choices = [c for c in (zx, zz) if c is not None]
    if not choices:
        return {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    best = min(choices, key=lambda c: (c["upper_bound"], 0 if c["basis"] == "x" else 1))
    return {
        "status": "completed",
        "basis": best["basis"],
        "vector": vector_to_list(best["vector"], n),
        "upper_bound": best["upper_bound"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()
    try:
        hx_rows, nx = parse_matrix_arg(args.hx)
        hz_rows, nz = parse_matrix_arg(args.hz)
        n = max(nx, nz)
        mask = (1 << n) - 1 if n > 0 else 0
        hx_rows = [r & mask for r in hx_rows]
        hz_rows = [r & mask for r in hz_rows]
        result = solve(hx_rows, hz_rows, n, args.seed)
    except Exception:
        result = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
