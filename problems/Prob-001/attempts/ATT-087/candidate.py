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
        data = obj
        n = max((len(r) for r in data), default=0)
        return [row_to_int(r) for r in data], n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        rows = [row_to_int(r) for r in obj.get("data", [])]
        if n == 0:
            n = max((r.bit_length() for r in rows), default=0)
        return rows, n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            x = 0
            for c in r:
                c = int(c)
                if c >= 0:
                    x ^= 1 << c
            rows.append(x)
        if n == 0:
            n = max((r.bit_length() for r in rows), default=0)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def row_to_int(row):
    x = 0
    for i, b in enumerate(row):
        if int(b) & 1:
            x |= 1 << i
    return x


def int_to_bits(x, n):
    return [(x >> i) & 1 for i in range(n)]


def make_reducer(rows):
    basis = {}
    for v in rows:
        x = v
        while x:
            p = x.bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                basis[p] = x
                break
    return basis


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            break
        y ^= b
    return y


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def kernel_basis(check_rows, n):
    rows = [r & ((1 << n) - 1) for r in check_rows if r]
    pivot_rows = {}
    for r in rows:
        x = r
        while x:
            p = x.bit_length() - 1
            if p in pivot_rows:
                x ^= pivot_rows[p]
            else:
                pivot_rows[p] = x
                break
    pivots = sorted(pivot_rows.keys())
    pivot_set = set(pivots)
    out = []
    for f in range(n):
        if f in pivot_set:
            continue
        v = 1 << f
        for p in pivots:
            if ((pivot_rows[p] & v).bit_count() & 1) != 0:
                v |= 1 << p
        out.append(v)
    return out


def dot_parity_rows(v, rows):
    for r in rows:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def verified(v, basis_name, hx, hz, rx, rz, n):
    if v <= 0 or v.bit_length() > n:
        return False
    if basis_name == "x":
        return dot_parity_rows(v, hz) and not in_rowspace(v, rx)
    return dot_parity_rows(v, hx) and not in_rowspace(v, rz)


def low_weight_logical_basis(check_rows, stab_rows, stab_reducer, n):
    kb = kernel_basis(check_rows, n)
    logicals = []
    log_reducer = dict(stab_reducer)
    for v in sorted(kb, key=lambda z: z.bit_count()):
        if not in_rowspace(v, log_reducer):
            logicals.append(v)
            x = v
            while x:
                p = x.bit_length() - 1
                if p in log_reducer:
                    x ^= log_reducer[p]
                else:
                    log_reducer[p] = x
                    break
    return logicals


def greedy_stabilizer_reduce(v, stab_rows, rng, deadline):
    cur = v
    improved = True
    passes = 0
    order = list(range(len(stab_rows)))
    while improved and time.monotonic() < deadline and passes < 10:
        passes += 1
        improved = False
        rng.shuffle(order)
        for i in order:
            r = stab_rows[i]
            nxt = cur ^ r
            if nxt and nxt.bit_count() < cur.bit_count():
                cur = nxt
                improved = True
    return cur


def build_row_adjacency(stab_rows, n, max_edges=250000):
    adj = [[] for _ in range(n)]
    edges = 0
    for i, r in enumerate(stab_rows):
        x = r
        while x:
            lsb = x & -x
            q = lsb.bit_length() - 1
            if q < n:
                adj[q].append(i)
                edges += 1
            x ^= lsb
            if edges > max_edges:
                return None
    return adj


def tabu_coset_search(seed_v, stab_rows, n, rng, deadline, row_adj):
    if not stab_rows:
        return seed_v
    cur = seed_v
    best = seed_v
    best_w = best.bit_count()
    m = len(stab_rows)
    tabu = {}
    tenure_base = max(5, min(41, int(m ** 0.5) + 7))
    iter_no = 0
    stagnation = 0
    all_idx = list(range(m))
    row_weights = [r.bit_count() for r in stab_rows]
    random_cap = 96
    max_iter = max(40, min(1600, 14 * m + 120))
    while time.monotonic() < deadline and iter_no < max_iter:
        iter_no += 1
        candidates = set()
        if row_adj is not None:
            support = []
            x = cur
            while x and len(support) < 180:
                lsb = x & -x
                support.append(lsb.bit_length() - 1)
                x ^= lsb
            if len(support) > 56:
                support = rng.sample(support, 56)
            for q in support:
                for i in row_adj[q]:
                    candidates.add(i)
                    if len(candidates) >= 384:
                        break
                if len(candidates) >= 384:
                    break
        if len(candidates) < random_cap:
            candidates.update(rng.sample(all_idx, min(m, random_cap)))

        choice = None
        choice_key = None
        cand_list = list(candidates)
        rng.shuffle(cand_list)
        for i in cand_list[: max(random_cap, min(len(cand_list), 320))]:
            r = stab_rows[i]
            overlap = (cur & r).bit_count()
            delta = row_weights[i] - 2 * overlap
            is_tabu = tabu.get(i, 0) > iter_no
            aspirates = cur.bit_count() + delta < best_w
            if is_tabu and not aspirates:
                continue
            key = (delta, -overlap, rng.random())
            if choice_key is None or key < choice_key:
                choice = i
                choice_key = key

        if choice is None:
            choice = rng.randrange(m)
        cur ^= stab_rows[choice]
        if cur == 0:
            cur ^= stab_rows[choice]
        tabu[choice] = iter_no + tenure_base + rng.randrange(tenure_base)

        w = cur.bit_count()
        if w < best_w:
            best = cur
            best_w = w
            stagnation = 0
            cur = greedy_stabilizer_reduce(cur, stab_rows, rng, min(deadline, time.monotonic() + 0.025))
            if cur.bit_count() < best_w:
                best = cur
                best_w = cur.bit_count()
        else:
            stagnation += 1

        if stagnation > 80:
            stagnation = 0
            cur = best
            flips = 1 + rng.randrange(min(5, max(2, m)))
            for _ in range(flips):
                cur ^= stab_rows[rng.randrange(m)]
            if cur == 0:
                cur = best
    return best


def build_seeds(logicals, stab_rows, rng, deadline):
    seeds = list(logicals)
    if not logicals:
        return seeds
    by_weight = sorted(logicals, key=lambda x: x.bit_count())
    seeds.extend(by_weight[: min(16, len(by_weight))])
    limit = min(64, max(8, 4 * len(by_weight)))
    while len(seeds) < limit and time.monotonic() < deadline:
        v = 0
        count = 1 + rng.randrange(min(5, len(by_weight)))
        for b in rng.sample(by_weight, count):
            v ^= b
        if v:
            seeds.append(v)
    if stab_rows:
        for v in by_weight[: min(8, len(by_weight))]:
            cur = v
            for _ in range(3):
                cur ^= rng.choice(stab_rows)
            if cur:
                seeds.append(cur)
    return seeds


def search_basis(name, hx, hz, rx, rz, n, rng, deadline):
    if name == "x":
        check_rows, stab_rows, stab_reducer = hz, hx, rx
    else:
        check_rows, stab_rows, stab_reducer = hx, hz, rz
    logicals = low_weight_logical_basis(check_rows, stab_rows, stab_reducer, n)
    if not logicals:
        return None
    best = min(logicals, key=lambda x: x.bit_count())
    row_adj = build_row_adjacency(stab_rows, n)
    seeds = build_seeds(logicals, stab_rows, rng, min(deadline, time.monotonic() + 0.25))
    rng.shuffle(seeds)
    for s in seeds:
        if time.monotonic() >= deadline:
            break
        s = greedy_stabilizer_reduce(s, stab_rows, rng, min(deadline, time.monotonic() + 0.04))
        rem = max(0.02, min(0.18, deadline - time.monotonic()))
        cand = tabu_coset_search(s, stab_rows, n, rng, min(deadline, time.monotonic() + rem), row_adj)
        cand = greedy_stabilizer_reduce(cand, stab_rows, rng, min(deadline, time.monotonic() + 0.03))
        if cand and cand.bit_count() < best.bit_count():
            best = cand
    return best


def choose_witness(hx, hz, n, seed):
    rng = random.Random(seed)
    rx = make_reducer(hx)
    rz = make_reducer(hz)
    deadline = time.monotonic() + float(os.environ.get("CANDIDATE_TIME_SEC", "24"))
    options = []
    order = ["x", "z"] if rng.randrange(2) == 0 else ["z", "x"]
    for name in order:
        per_deadline = min(deadline, time.monotonic() + 11.5)
        cand = search_basis(name, hx, hz, rx, rz, n, rng, per_deadline)
        if cand is not None and verified(cand, name, hx, hz, rx, rz, n):
            options.append((cand.bit_count(), name, cand))
    if options:
        _, name, cand = min(options, key=lambda t: t[0])
        return name, cand

    for name in ("x", "z"):
        if name == "x":
            logs = low_weight_logical_basis(hz, hx, rx, n)
        else:
            logs = low_weight_logical_basis(hx, hz, rz, n)
        for cand in sorted(logs, key=lambda x: x.bit_count()):
            if verified(cand, name, hx, hz, rx, rz, n):
                return name, cand
    return None, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        mask = (1 << n) - 1 if n > 0 else 0
        hx = [r & mask for r in hx]
        hz = [r & mask for r in hz]
        name, vec = choose_witness(hx, hz, n, args.seed)
        if name is not None:
            out = {
                "status": "completed",
                "basis": name,
                "vector": int_to_bits(vec, n),
                "upper_bound": int(vec.bit_count()),
            }
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
