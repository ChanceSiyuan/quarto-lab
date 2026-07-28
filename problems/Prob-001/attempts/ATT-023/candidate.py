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
        data = obj.get("data") or []
        n = int(obj.get("n_cols", 0))
        rows = []
        for row in data:
            x = 0
            if n == 0:
                n = len(row)
            for j, v in enumerate(row):
                if int(v) & 1:
                    x |= 1 << j
            rows.append(x)
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
                    if jj + 1 > n:
                        n = jj + 1
            rows.append(x)
        return rows, n

    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for row in obj:
            x = 0
            for j, v in enumerate(row):
                if int(v) & 1:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def rref_basis(rows):
    basis = {}
    for value in rows:
        x = int(value)
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                break
            x ^= b
    # Make membership reduction deterministic and close to reduced echelon form.
    for p in sorted(basis):
        for q in sorted(basis):
            if q != p and ((basis[q] >> p) & 1):
                basis[q] ^= basis[p]
    return basis


def reduce_by_basis(x, basis):
    y = int(x)
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            break
        y ^= b
    return y


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def kernel_basis(rows, n):
    basis = rref_basis(rows)
    pivots = set(basis)
    out = []
    for free in range(n):
        if free in pivots:
            continue
        v = 1 << free
        for p, row in basis.items():
            if (row >> free) & 1:
                v |= 1 << p
        out.append(v)
    if n == 0 and not rows:
        out.append(0)
    return out


def orthogonal_to_all(v, rows):
    for r in rows:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def verify(v, syndrome_rows, stabilizer_basis, n):
    if v <= 0:
        return False
    if v >> n:
        return False
    if not orthogonal_to_all(v, syndrome_rows):
        return False
    if in_rowspace(v, stabilizer_basis):
        return False
    return True


def vector_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def support_rows(v, rows, q_to_rows, rng, limit):
    seen = set()
    qs = [i for i in range(v.bit_length()) if (v >> i) & 1]
    rng.shuffle(qs)
    for q in qs[: max(1, min(len(qs), 96))]:
        for ri in q_to_rows[q]:
            seen.add(ri)
    if len(seen) < limit:
        extra = list(range(len(rows)))
        rng.shuffle(extra)
        for ri in extra[: limit - len(seen)]:
            seen.add(ri)
    cand = list(seen)
    rng.shuffle(cand)
    return cand[:limit]


def greedy_reduce(v, stab_rows, q_to_rows, rng, deadline, tabu_len=11):
    if not stab_rows:
        return v
    cur = v
    best = v
    best_w = v.bit_count()
    tabu = {}
    step = 0
    stagnant = 0
    max_steps = 2200 + 25 * len(stab_rows)
    while step < max_steps and time.monotonic() < deadline:
        step += 1
        cw = cur.bit_count()
        candidate_rows = support_rows(cur, stab_rows, q_to_rows, rng, 160)
        scored = []
        for ri in candidate_rows:
            if tabu.get(ri, -1) > step:
                continue
            row = stab_rows[ri]
            nw = (cur ^ row).bit_count()
            # Overlap with the current support is the check-graph guidance:
            # rows touching more active qubits get explored first.
            overlap = (cur & row).bit_count()
            scored.append((nw - cw, -overlap, rng.random(), ri, nw))
        if not scored:
            break
        scored.sort()
        improving = [s for s in scored[:24] if s[0] <= 0]
        if improving:
            chosen = rng.choice(improving[: min(8, len(improving))])
        else:
            # Tabu diversification: occasionally accept a small uphill move
            # from a high-overlap stabilizer row to escape local minima.
            window = scored[: min(18, len(scored))]
            if stagnant < 30 and rng.random() > 0.22:
                stagnant += 1
                continue
            chosen = rng.choice(window)
            stagnant = 0
        ri = chosen[3]
        cur ^= stab_rows[ri]
        tabu[ri] = step + tabu_len + rng.randrange(0, 7)
        w = cur.bit_count()
        if 0 < w < best_w:
            best = cur
            best_w = w
            stagnant = 0
        else:
            stagnant += 1
        if stagnant > 140:
            cur = best
            touched = support_rows(cur, stab_rows, q_to_rows, rng, 30)
            for ri in touched[: rng.randrange(1, min(6, len(touched)) + 1)]:
                cur ^= stab_rows[ri]
                tabu[ri] = step + tabu_len
            stagnant = 0
    return best


def build_q_to_rows(rows, n):
    q_to_rows = [[] for _ in range(n)]
    for ri, row in enumerate(rows):
        x = row
        while x:
            lsb = x & -x
            q = lsb.bit_length() - 1
            if q < n:
                q_to_rows[q].append(ri)
            x ^= lsb
    return q_to_rows


def logical_seeds(syndrome_rows, stabilizer_rows, n, rng, max_seeds=96):
    stab_basis = rref_basis(stabilizer_rows)
    kb = kernel_basis(syndrome_rows, n)
    seeds = []
    for v in sorted(kb, key=lambda z: z.bit_count()):
        if v and not in_rowspace(v, stab_basis):
            seeds.append(v)
            if len(seeds) >= max_seeds // 3:
                break
    logical_pool = [v for v in kb if v and not in_rowspace(v, stab_basis)]
    if not logical_pool:
        # If individual nullspace basis vectors are unlucky after reduction
        # choices, random combinations still expose the positive-k quotient.
        pool = [v for v in kb if v]
        for _ in range(4 * max_seeds):
            x = 0
            for v in pool:
                if rng.random() < 0.35:
                    x ^= v
            if x and not in_rowspace(x, stab_basis):
                logical_pool.append(x)
                seeds.append(x)
                break
    for _ in range(max_seeds):
        if not logical_pool:
            break
        x = 0
        count = 1 + rng.randrange(1, min(8, len(logical_pool)) + 1)
        for v in rng.sample(logical_pool, min(count, len(logical_pool))):
            x ^= v
        if x and not in_rowspace(x, stab_basis):
            seeds.append(x)
    # Stable de-duplication.
    seen = set()
    uniq = []
    for v in seeds:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def search_basis(name, syndrome_rows, stabilizer_rows, n, seed, seconds):
    rng = random.Random((seed << 8) ^ (17 if name == "x" else 53))
    stab_basis = rref_basis(stabilizer_rows)
    seeds = logical_seeds(syndrome_rows, stabilizer_rows, n, rng)
    if not seeds:
        return None
    q_to_rows = build_q_to_rows(stabilizer_rows, n)
    deadline = time.monotonic() + seconds
    best = None
    best_w = n + 1
    for s in seeds:
        if time.monotonic() >= deadline:
            break
        if verify(s, syndrome_rows, stab_basis, n) and s.bit_count() < best_w:
            best = s
            best_w = s.bit_count()
        v = greedy_reduce(s, stabilizer_rows, q_to_rows, rng, deadline)
        if verify(v, syndrome_rows, stab_basis, n) and v.bit_count() < best_w:
            best = v
            best_w = v.bit_count()
    if best is not None:
        return best
    # Reliable fallback: return the first verified basis-derived logical.
    for s in seeds:
        if verify(s, syndrome_rows, stab_basis, n):
            return s
    return None


def solve(hx, hz, n, seed):
    # For X logicals use ker(Hz) / row(Hx); for Z use ker(Hx) / row(Hz).
    time_budget = 28.0
    vx = search_basis("x", hz, hx, n, seed, time_budget * 0.48)
    vz = search_basis("z", hx, hz, n, seed, time_budget * 0.48)
    choices = []
    if vx is not None:
        choices.append(("x", vx))
    if vz is not None:
        choices.append(("z", vz))
    if not choices:
        return None
    choices.sort(key=lambda item: (item[1].bit_count(), 0 if item[0] == "x" else 1))
    return choices[0]


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
        os.makedirs(args.output_dir, exist_ok=True)
        result = solve(hx, hz, n, int(args.seed))
        if result is None:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
        else:
            basis, v = result
            # Final independent certification gate.
            if basis == "x":
                ok = verify(v, hz, rref_basis(hx), n)
            else:
                ok = verify(v, hx, rref_basis(hz), n)
            if ok:
                out = {
                    "status": "completed",
                    "basis": basis,
                    "vector": vector_list(v, n),
                    "upper_bound": int(v.bit_count()),
                }
            else:
                out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
