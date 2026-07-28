#!/usr/bin/env python3
import argparse
import json
import os
import random


def _load_json_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if isinstance(obj, dict) and "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if isinstance(obj, dict) and "matrix" in obj:
        obj = obj["matrix"]

    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", obj.get("num_cols", 0)))
        if not n and data:
            n = max(len(r) for r in data)
        rows = []
        for r in data:
            bits = 0
            for j, x in enumerate(r):
                if int(x) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    if isinstance(obj, dict) and "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            bits = 0
            if isinstance(r, dict):
                r = r.get("cols", r.get("indices", []))
            for j in r:
                j = int(j)
                if j >= 0:
                    bits ^= 1 << j
                    if j + 1 > n:
                        n = j + 1
            rows.append(bits)
        return rows, n

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            bits = 0
            for j, x in enumerate(r):
                if int(x) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def _mask(n):
    return (1 << n) - 1 if n > 0 else 0


def _iter_bits(x):
    while x:
        lb = x & -x
        yield lb.bit_length() - 1
        x ^= lb


def _row_basis(rows):
    basis = {}
    for raw in rows:
        x = int(raw)
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    return basis


def _reduce(x, basis):
    x = int(x)
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            break
        x ^= b
    return x


def _in_rowspace(x, basis):
    return _reduce(x, basis) == 0


def _nullspace_basis(rows, n):
    basis = _row_basis(rows)
    pivots = set(basis)
    free_cols = [j for j in range(n) if j not in pivots]
    out = []
    for f in free_cols:
        v = 1 << f
        for p in sorted(pivots):
            if ((basis[p] & v).bit_count() & 1) != 0:
                v |= 1 << p
        out.append(v & _mask(n))
    return out


def _mat_vec_zero(rows, v):
    for r in rows:
        if ((r & v).bit_count() & 1) != 0:
            return False
    return True


def _to_vector(x, n):
    return [(x >> j) & 1 for j in range(n)]


def _logical_basis(kernel_rows, stabilizer_rows, n):
    stab_basis = _row_basis(stabilizer_rows)
    logicals = []
    combined = dict(stab_basis)
    for v in _nullspace_basis(kernel_rows, n):
        if v and _reduce(v, combined) != 0:
            logicals.append(v)
            combined = _row_basis(list(combined.values()) + [v])
    return logicals, stab_basis


def _column_degrees(rows, n):
    deg = [0] * n
    for r in rows:
        for j in _iter_bits(r):
            if j < n:
                deg[j] += 1
    return deg


def _row_neighbors(rows, n):
    by_col = [[] for _ in range(n)]
    for i, r in enumerate(rows):
        for j in _iter_bits(r):
            if j < n:
                by_col[j].append(i)
    neigh = [set() for _ in rows]
    for ids in by_col:
        if len(ids) > 1:
            limited = ids[:128]
            for i in limited:
                if len(neigh[i]) < 256:
                    neigh[i].update(k for k in limited if k != i)
    return [list(s) for s in neigh]


def _basis_random(logicals, rng):
    if not logicals:
        return 0
    v = 0
    for b in logicals:
        if rng.getrandbits(1):
            v ^= b
    if v == 0:
        v = rng.choice(logicals)
    return v


def _support_guided_seed(logicals, hot_touched, n, rng):
    v = _basis_random(logicals, rng)
    if not hot_touched or n == 0:
        return v
    for touched in hot_touched:
        if rng.random() < 0.35:
            if touched:
                v ^= rng.choice(touched)
    return v & _mask(n)


def _local_tabu_minimize(start, logical_basis_rows, stab_rows, rows_by_col, kernel_rows, stab_basis, n, rng, budget):
    if not stab_rows:
        return start
    row_w = [r.bit_count() for r in stab_rows]
    deg = _column_degrees(stab_rows, n)
    neigh = _row_neighbors(stab_rows, n)
    cur = start & _mask(n)
    best = cur
    best_w = cur.bit_count()
    tabu_until = {}
    last_flip = None
    tenure_base = 5 + int(len(stab_rows) ** 0.5)
    no_gain = 0

    for step in range(max(1, budget)):
        cur_w = cur.bit_count()
        active = cur
        candidates = set()
        while active and len(candidates) < 256:
            lb = active & -active
            j = lb.bit_length() - 1
            candidates.update(rows_by_col[j][: max(0, 256 - len(candidates))])
            active ^= lb
        if last_flip is not None:
            candidates.update(neigh[last_flip][:64])
        if not candidates:
            candidates.add(rng.randrange(len(stab_rows)))

        scored = []
        for i in candidates:
            r = stab_rows[i]
            overlap = (cur & r).bit_count()
            delta = row_w[i] - 2 * overlap
            graph_bias = sum(deg[j] for j in _iter_bits(cur & r))
            tabu = tabu_until.get(i, -1) > step
            if tabu and cur_w + delta >= best_w:
                continue
            jitter = rng.random() * 0.25
            scored.append((delta - 0.002 * graph_bias + jitter, delta, i))

        if scored:
            scored.sort(key=lambda x: x[0])
            improving = [x for x in scored[:24] if x[1] <= 0]
            pick_pool = improving if improving else scored[: min(12, len(scored))]
            _, delta, idx = rng.choice(pick_pool[: max(1, min(len(pick_pool), 4))])
        else:
            idx = rng.randrange(len(stab_rows))
            delta = row_w[idx] - 2 * (cur & stab_rows[idx]).bit_count()

        cur ^= stab_rows[idx]
        last_flip = idx
        tabu_until[idx] = step + tenure_base + rng.randrange(tenure_base + 1)

        cw = cur_w + delta
        if cw < best_w and cur and not _in_rowspace(cur, stab_basis) and _mat_vec_zero(kernel_rows, cur):
            best = cur
            best_w = cw
            no_gain = 0
        else:
            no_gain += 1

        if no_gain > 80:
            no_gain = 0
            cur = best
            for _ in range(1 + rng.randrange(4)):
                if stab_rows:
                    cur ^= rng.choice(stab_rows)
            if logical_basis_rows and rng.random() < 0.45:
                cur ^= rng.choice(logical_basis_rows)
                if _in_rowspace(cur, stab_basis):
                    cur ^= rng.choice(logical_basis_rows)

    return best


def _greedy_reduce(v, stab_rows):
    cur = v
    improved = True
    while improved:
        improved = False
        base_w = cur.bit_count()
        for r in sorted(stab_rows, key=lambda x: x.bit_count()):
            nv = cur ^ r
            if nv and nv.bit_count() < base_w:
                cur = nv
                improved = True
                break
    return cur


def _search_basis(name, kernel_rows, stabilizer_rows, n, rng, effort):
    logicals, stab_basis = _logical_basis(kernel_rows, stabilizer_rows, n)
    if not logicals:
        return None
    rows_by_col = [[] for _ in range(n)]
    for i, r in enumerate(stabilizer_rows):
        for j in _iter_bits(r):
            if j < n:
                rows_by_col[j].append(i)
    deg = _column_degrees(stabilizer_rows, n)
    hot = sorted(range(n), key=lambda j: deg[j], reverse=True)[: max(1, min(n, 16))]
    hot_touched = [[r for r in stabilizer_rows if (r >> j) & 1] for j in hot]

    seeds = []
    seeds.extend(logicals)
    for b in logicals:
        seeds.append(_greedy_reduce(b, stabilizer_rows))
    for _ in range(max(24, min(220, 3 * len(logicals) + effort // 4))):
        seeds.append(_support_guided_seed(logicals, hot_touched, n, rng))

    best = None
    best_w = n + 1
    per_seed_budget = max(20, min(420, effort // max(1, min(len(seeds), 80))))
    for s in seeds:
        if not s or _in_rowspace(s, stab_basis):
            continue
        v = _local_tabu_minimize(s, logicals, stabilizer_rows, rows_by_col, kernel_rows, stab_basis, n, rng, per_seed_budget)
        v = _greedy_reduce(v, stabilizer_rows)
        if v and v.bit_count() < best_w and _mat_vec_zero(kernel_rows, v) and not _in_rowspace(v, stab_basis):
            best = v
            best_w = v.bit_count()
    if best is None:
        for v in logicals:
            if v and _mat_vec_zero(kernel_rows, v) and not _in_rowspace(v, stab_basis):
                best = v
                best_w = v.bit_count()
                break
    if best is None:
        return None
    return {"basis": name, "vector": _to_vector(best, n), "upper_bound": int(best_w)}


def _validate_css_width(hx_n, hz_n):
    if hx_n and hz_n and hx_n != hz_n:
        raise ValueError("hx and hz have different column counts")
    return max(hx_n, hz_n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    try:
        hx, hx_n = _load_json_matrix(args.hx)
        hz, hz_n = _load_json_matrix(args.hz)
        n = _validate_css_width(hx_n, hz_n)
        hx = [r & _mask(n) for r in hx if r & _mask(n)]
        hz = [r & _mask(n) for r in hz if r & _mask(n)]
        os.makedirs(args.output_dir, exist_ok=True)

        effort = 3000 + 20 * n + 15 * (len(hx) + len(hz))
        zx = _search_basis("x", hz, hx, n, rng, effort)
        zz = _search_basis("z", hx, hz, n, rng, effort)
        choices = [c for c in (zx, zz) if c is not None]
        if choices:
            ans = min(choices, key=lambda c: (c["upper_bound"], 0 if c["basis"] == "x" else 1))
            status = {
                "status": "completed",
                "basis": ans["basis"],
                "vector": ans["vector"],
                "upper_bound": ans["upper_bound"],
            }
        else:
            status = {"status": "failed", "basis": None, "vector": None, "upper_bound": None}
    except Exception:
        status = {"status": "failed", "basis": None, "vector": None, "upper_bound": None}

    print(json.dumps(status, separators=(",", ":")))


if __name__ == "__main__":
    main()
