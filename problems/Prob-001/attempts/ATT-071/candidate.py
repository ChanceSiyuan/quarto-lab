#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def load_matrix(arg):
    if os.path.exists(arg):
        with open(arg, "r", encoding="utf-8") as f:
            obj = json.load(f)
    else:
        obj = json.loads(arg)

    if isinstance(obj, list):
        data = obj
        n_cols = max((len(r) for r in data), default=0)
        return dense_to_rows(data, n_cols), n_cols

    fmt = obj.get("format") or obj.get("type")
    if fmt == "dense_binary_matrix" or "data" in obj:
        data = obj.get("data", [])
        n_cols = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        return dense_to_rows(data, n_cols), n_cols

    if fmt == "sparse_rows" or "rows" in obj:
        rows = obj.get("rows", [])
        n_cols = int(obj.get("num_cols", obj.get("n_cols", 0)))
        out = []
        for row in rows:
            mask = 0
            for c in row:
                c = int(c)
                if 0 <= c < n_cols:
                    mask ^= 1 << c
            out.append(mask)
        return out, n_cols

    raise ValueError("unsupported matrix JSON format")


def dense_to_rows(data, n_cols):
    out = []
    for row in data:
        mask = 0
        for i, bit in enumerate(row[:n_cols]):
            if int(bit) & 1:
                mask |= 1 << i
        out.append(mask)
    return out


def build_rref(rows):
    basis = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                for q, old in list(basis.items()):
                    if (old >> p) & 1:
                        basis[q] = old ^ x
                basis[p] = x
                break
            x ^= b
    return basis


def reduce_by_basis(x, basis):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(v, basis):
    return reduce_by_basis(v, basis) == 0


def kernel_basis(check_rows, n_cols):
    rref = build_rref(check_rows)
    pivots = set(rref)
    free_cols = [c for c in range(n_cols) if c not in pivots]
    basis = []
    for f in free_cols:
        v = 1 << f
        for p, row in rref.items():
            if (row >> f) & 1:
                v |= 1 << p
        basis.append(v)
    return basis


def syndrome_zero(v, checks):
    for row in checks:
        if ((v & row).bit_count() & 1) != 0:
            return False
    return True


def verified(v, kernel_checks, stabilizer_basis, n_cols):
    if v <= 0 or (v >> n_cols) != 0:
        return False
    return syndrome_zero(v, kernel_checks) and not in_rowspace(v, stabilizer_basis)


def vector_bits(v, n_cols):
    return [(v >> i) & 1 for i in range(n_cols)]


def rows_by_column(rows, n_cols):
    cols = [[] for _ in range(n_cols)]
    for ri, row in enumerate(rows):
        x = row
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c < n_cols:
                cols[c].append(ri)
            x ^= lsb
    return cols


def random_kernel_combo(rng, kbasis, stabilizer_basis, n_cols, bias=0.12):
    if not kbasis:
        return 0
    v = 0
    p = max(1.0 / max(1, len(kbasis)), min(0.5, bias))
    for b in kbasis:
        if rng.random() < p:
            v ^= b
    if v == 0:
        v = rng.choice(kbasis)
    if in_rowspace(v, stabilizer_basis):
        order = list(range(len(kbasis)))
        rng.shuffle(order)
        for i in order:
            w = v ^ kbasis[i]
            if w and not in_rowspace(w, stabilizer_basis):
                return w & ((1 << n_cols) - 1)
    return v & ((1 << n_cols) - 1)


def quotient_seeds(kbasis, stabilizer_basis, limit):
    seeds = []
    for v in sorted(kbasis, key=lambda x: x.bit_count()):
        if v and not in_rowspace(v, stabilizer_basis):
            seeds.append(v)
            if len(seeds) >= limit:
                break
    return seeds


def sample_support_columns(rng, v, n_cols, limit):
    cols = []
    x = v
    while x and len(cols) < limit:
        lsb = x & -x
        cols.append(lsb.bit_length() - 1)
        x ^= lsb
    if len(cols) > 1:
        rng.shuffle(cols)
    while len(cols) < limit and n_cols:
        cols.append(rng.randrange(n_cols))
    return cols[:limit]


def candidate_rows_from_graph(rng, v, stab_rows, col_rows, n_cols, row_count, tabu, step):
    cand = set()
    support_limit = 20 if v.bit_count() > 20 else max(4, v.bit_count() + 2)
    for c in sample_support_columns(rng, v, n_cols, support_limit):
        rows = col_rows[c]
        if len(rows) <= 10:
            cand.update(rows)
        else:
            for ri in rng.sample(rows, 10):
                cand.add(ri)

    # One-hop Tanner expansion from a few touched checks gives the search a
    # check-graph bias without enumerating a full connected cluster.
    frontier = list(cand)
    rng.shuffle(frontier)
    for ri in frontier[:8]:
        row = stab_rows[ri]
        bits = []
        x = row
        while x and len(bits) < 8:
            lsb = x & -x
            bits.append(lsb.bit_length() - 1)
            x ^= lsb
        for c in bits:
            if col_rows[c]:
                cand.add(rng.choice(col_rows[c]))

    random_budget = 8 if row_count > 80 else 4
    for _ in range(random_budget):
        if row_count:
            cand.add(rng.randrange(row_count))

    if not cand and row_count:
        cand.add(rng.randrange(row_count))
    return [ri for ri in cand if tabu.get(ri, -1) <= step or rng.random() < 0.05]


def tabu_coset_search(start, kernel_checks, stab_rows, stabilizer_basis, n_cols, rng, time_limit):
    if not stab_rows:
        return start if verified(start, kernel_checks, stabilizer_basis, n_cols) else 0

    col_rows = rows_by_column(stab_rows, n_cols)
    row_weights = [r.bit_count() for r in stab_rows]
    row_count = len(stab_rows)
    v = start
    best = v
    best_w = v.bit_count()
    tabu = {}
    use_count = [0] * row_count
    no_improve = 0
    max_steps = min(70000, max(3000, 140 * (n_cols + row_count)))
    deadline = time.time() + time_limit

    for step in range(max_steps):
        if time.time() >= deadline:
            break
        cand = candidate_rows_from_graph(rng, v, stab_rows, col_rows, n_cols, row_count, tabu, step)
        best_ri = None
        best_score = None
        best_delta = 10**9
        cur_w = v.bit_count()

        for ri in cand:
            row = stab_rows[ri]
            overlap = (v & row).bit_count()
            delta = row_weights[ri] - 2 * overlap
            aspiration = cur_w + delta < best_w
            if tabu.get(ri, -1) > step and not aspiration:
                continue
            score = delta + 0.035 * use_count[ri] + rng.random() * 0.02
            if best_score is None or score < best_score:
                best_score = score
                best_delta = delta
                best_ri = ri

        if best_ri is None:
            continue

        improving = best_delta < 0
        diversify = no_improve > 30 and (step % 7 == 0 or rng.random() < 0.08)
        aspirational = cur_w + best_delta < best_w
        if improving or diversify or aspirational:
            v ^= stab_rows[best_ri]
            use_count[best_ri] += 1
            tenure = 9 + rng.randrange(13) + min(30, no_improve // 8)
            tabu[best_ri] = step + tenure
            w = v.bit_count()
            if w < best_w and verified(v, kernel_checks, stabilizer_basis, n_cols):
                best = v
                best_w = w
                no_improve = 0
            else:
                no_improve += 1
        else:
            no_improve += 1

        if no_improve > 220:
            # Diversify in the stabilizer coset by applying a short random
            # check-graph walk, then resume descent from the shaken vector.
            for _ in range(1 + rng.randrange(5)):
                ri = rng.randrange(row_count)
                v ^= stab_rows[ri]
                use_count[ri] += 1
            no_improve = 40

    return best if verified(best, kernel_checks, stabilizer_basis, n_cols) else 0


def solve_basis(label, kernel_checks, stabilizer_rows, n_cols, rng, total_time):
    stabilizer_basis = build_rref(stabilizer_rows)
    kbasis = kernel_basis(kernel_checks, n_cols)
    seeds = quotient_seeds(kbasis, stabilizer_basis, 16)

    attempts = max(24, min(96, 12 + n_cols // 2))
    trial_budget = attempts * 12
    trials = 0
    while len(seeds) < attempts and trials < trial_budget:
        trials += 1
        v = random_kernel_combo(rng, kbasis, stabilizer_basis, n_cols, bias=rng.uniform(0.04, 0.35))
        if verified(v, kernel_checks, stabilizer_basis, n_cols):
            seeds.append(v)

    if not seeds:
        return None

    best = min(seeds, key=lambda x: x.bit_count())
    deadline = time.time() + total_time
    for i, seed in enumerate(seeds):
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        slice_time = max(0.015, min(0.20, remaining / max(1, len(seeds) - i)))
        found = tabu_coset_search(seed, kernel_checks, stabilizer_rows, stabilizer_basis, n_cols, rng, slice_time)
        if found and found.bit_count() < best.bit_count():
            best = found

    if verified(best, kernel_checks, stabilizer_basis, n_cols):
        return {"basis": label, "vector": vector_bits(best, n_cols), "upper_bound": int(best.bit_count())}
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n_cols = max(nx, nz)
        mask = (1 << n_cols) - 1 if n_cols else 0
        hx = [r & mask for r in hx]
        hz = [r & mask for r in hz]
        rng = random.Random(args.seed)

        # Try both CSS logical types. The local search is randomized, but the
        # final selection is purely by verified witness weight.
        order = [("z", hx, hz), ("x", hz, hx)]
        if rng.random() < 0.5:
            order.reverse()

        results = []
        for label, kernel_checks, stabilizers in order:
            res = solve_basis(label, kernel_checks, stabilizers, n_cols, rng, total_time=1.75)
            if res is not None:
                results.append(res)

        if results:
            res = min(results, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "z" else 1))
            out = {
                "status": "completed",
                "basis": res["basis"],
                "vector": res["vector"],
                "upper_bound": res["upper_bound"],
            }
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}

    sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
