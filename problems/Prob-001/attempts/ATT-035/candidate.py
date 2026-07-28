#!/usr/bin/env python3
import argparse
import json
import os
import random
from collections import deque


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        n = int(obj["n_cols"])
        data = obj["data"]
        if not data:
            return [], n
        if all(isinstance(r, list) for r in data):
            rows = []
            for r in data:
                x = 0
                for j, b in enumerate(r[:n]):
                    if b & 1:
                        x ^= 1 << j
                rows.append(x)
            return rows, n
        rows = []
        for i in range(0, len(data), n):
            x = 0
            for j, b in enumerate(data[i:i + n]):
                if b & 1:
                    x ^= 1 << j
            rows.append(x)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for j in r:
                if 0 <= int(j) < n:
                    x ^= 1 << int(j)
            rows.append(x)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def weight(x):
    return x.bit_count()


def rows_rank(rows):
    basis = {}
    for x in rows:
        y = x
        while y:
            p = y.bit_length() - 1
            if p in basis:
                y ^= basis[p]
            else:
                basis[p] = y
                break
    return len(basis)


def row_basis(rows):
    basis = {}
    for x in rows:
        y = x
        while y:
            p = y.bit_length() - 1
            if p in basis:
                y ^= basis[p]
            else:
                basis[p] = y
                break
    return basis


def in_rowspace(x, basis):
    y = x
    while y:
        p = y.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        y ^= b
    return True


def rref_with_pivots(rows, n):
    rows = [r for r in rows if r]
    r = 0
    pivots = []
    for c in range(n):
        mask = 1 << c
        pivot = None
        for i in range(r, len(rows)):
            if rows[i] & mask:
                pivot = i
                break
        if pivot is None:
            continue
        rows[r], rows[pivot] = rows[pivot], rows[r]
        for i in range(len(rows)):
            if i != r and (rows[i] & mask):
                rows[i] ^= rows[r]
        pivots.append(c)
        r += 1
        if r == len(rows):
            break
    return rows[:r], pivots


def nullspace_basis(rows, n):
    rref, pivots = rref_with_pivots(rows, n)
    pivot_set = set(pivots)
    basis = []
    for f in range(n):
        if f in pivot_set:
            continue
        x = 1 << f
        for row, p in zip(rref, pivots):
            if row & (1 << f):
                x ^= 1 << p
        basis.append(x)
    return basis


def syndrome(v, checks):
    s = 0
    for i, r in enumerate(checks):
        if weight(v & r) & 1:
            s ^= 1 << i
    return s


def verify(v, kernel_checks, stabilizers, stab_basis):
    return v != 0 and syndrome(v, kernel_checks) == 0 and not in_rowspace(v, stab_basis)


def bit_positions(x):
    while x:
        lsb = x & -x
        yield lsb.bit_length() - 1
        x ^= lsb


def build_sparse_guides(checks, n):
    q_checks = [[] for _ in range(n)]
    check_qubits = []
    for i, r in enumerate(checks):
        qs = list(bit_positions(r))
        check_qubits.append(qs)
        for q in qs:
            q_checks[q].append(i)
    deg = [len(q_checks[q]) for q in range(n)]
    neighbors = [set() for _ in range(n)]
    for qs in check_qubits:
        if len(qs) <= 80:
            for a in qs:
                neighbors[a].update(q for q in qs if q != a)
    return q_checks, check_qubits, deg, [list(s) for s in neighbors]


def xor_reduce_by_stabilizers(v, stabilizers, rng, rounds=5):
    rows = [r for r in stabilizers if r]
    if not rows:
        return v
    rows.sort(key=weight)
    best = v
    improved = True
    passes = 0
    while improved and passes < rounds:
        improved = False
        passes += 1
        ordered = rows[:]
        if passes > 1:
            rng.shuffle(ordered)
        for r in ordered:
            y = best ^ r
            if weight(y) < weight(best):
                best = y
                improved = True
    return best


def repair_candidate(v, checks, q_checks, check_qubits, deg, rng, max_steps):
    s = syndrome(v, checks)
    if s == 0:
        return v
    for _ in range(max_steps):
        unsat = list(bit_positions(s))
        if not unsat:
            return v
        touched = set()
        for c in rng.sample(unsat, min(len(unsat), 12)):
            touched.update(check_qubits[c])
        if not touched:
            return v
        cur_bad = weight(s)
        best_delta = None
        best_qs = []
        for q in touched:
            ns = s
            for c in q_checks[q]:
                ns ^= 1 << c
            bad = weight(ns)
            delta = (bad - cur_bad, 1 if (v >> q) & 1 else 0, deg[q], rng.random())
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_qs = [q]
            elif delta[:3] == best_delta[:3]:
                best_qs.append(q)
        q = rng.choice(best_qs)
        v ^= 1 << q
        for c in q_checks[q]:
            s ^= 1 << c
        if s == 0:
            return v
    return v


def grow_cluster_candidate(n, checks, q_checks, check_qubits, deg, neighbors, rng):
    active = 0
    if n == 0:
        return 0
    nonisolated = [q for q in range(n) if deg[q] > 0]
    if nonisolated and rng.random() < 0.85:
        seed = min(rng.sample(nonisolated, min(len(nonisolated), 16)),
                   key=lambda q: (deg[q], rng.random()))
    else:
        seed = rng.randrange(n)
    active ^= 1 << seed
    frontier = deque([seed])
    seen = {seed}
    target = rng.randint(1, max(1, min(n, 4 + int(n ** 0.5))))
    while frontier and weight(active) < target:
        q = frontier.popleft()
        cand = neighbors[q]
        if not cand and q_checks[q]:
            c = rng.choice(q_checks[q])
            cand = check_qubits[c]
        ordered = sorted(cand, key=lambda u: (deg[u], rng.random()))
        for u in ordered[: rng.randint(1, min(4, max(1, len(ordered))))]:
            if u in seen:
                continue
            seen.add(u)
            frontier.append(u)
            if rng.random() < 0.75:
                active ^= 1 << u
            if weight(active) >= target:
                break
    return active


def logical_from_nullspace(null_basis, stab_basis, rng, tries):
    if not null_basis:
        return 0
    ordered = sorted(null_basis, key=weight)
    for v in ordered:
        if v and not in_rowspace(v, stab_basis):
            return v
    best = 0
    best_w = 10**18
    m = len(null_basis)
    for _ in range(tries):
        v = 0
        # Heavy-tailed subset sizes cover both single-basis and mixed-coset witnesses.
        k = 1 + int(rng.paretovariate(1.35)) % max(1, min(m, 32))
        for i in rng.sample(range(m), min(k, m)):
            v ^= null_basis[i]
        if v and not in_rowspace(v, stab_basis) and weight(v) < best_w:
            best = v
            best_w = weight(v)
    if best:
        return best

    # Deterministic quotient escape: add nullspace generators until leaving the
    # stabilizer row-space. Positive-k CSS inputs must eventually do this.
    v = 0
    for b in ordered:
        v ^= b
        if v and not in_rowspace(v, stab_basis):
            return v
    return 0


def search_basis(label, kernel_checks, stabilizers, n, seed):
    rng = random.Random(seed)
    stab_basis = row_basis(stabilizers)
    q_checks, check_qubits, deg, neighbors = build_sparse_guides(kernel_checks, n)
    null_basis = None
    best = 0
    best_w = 10**18

    def consider(v):
        nonlocal best, best_w
        if not v:
            return
        v = xor_reduce_by_stabilizers(v, stabilizers, rng)
        if verify(v, kernel_checks, stabilizers, stab_basis):
            w = weight(v)
            if w < best_w:
                best = v
                best_w = w

    # Sparse connected-cluster growth followed by syndrome repair.
    budget = 220 + min(900, 8 * max(1, n))
    repair_steps = 30 + min(260, 3 * max(1, len(kernel_checks)))
    for _ in range(budget):
        v = grow_cluster_candidate(n, kernel_checks, q_checks, check_qubits, deg, neighbors, rng)
        v = repair_candidate(v, kernel_checks, q_checks, check_qubits, deg, rng, repair_steps)
        consider(v)

    # Nullspace-derived seeds make the search reliable and provide a fallback.
    null_basis = nullspace_basis(kernel_checks, n)
    for v in sorted(null_basis, key=weight)[: min(len(null_basis), 80)]:
        consider(v)
    for _ in range(260 + min(740, 4 * max(1, n))):
        v = logical_from_nullspace(null_basis, stab_basis, rng, 1)
        consider(v)
        if null_basis:
            for b in rng.sample(null_basis, min(len(null_basis), rng.randint(1, 4))):
                v ^= b
            consider(v)

    if not best:
        v = logical_from_nullspace(null_basis, stab_basis, rng, 600)
        consider(v)

    return {"basis": label, "vector_int": best, "upper_bound": best_w if best else None}


def int_to_vec(x, n):
    return [(x >> i) & 1 for i in range(n)]


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

        # X logicals commute with Z checks and are quotiented by X stabilizers.
        xres = search_basis("x", hz, hx, n, (args.seed << 1) ^ 0x58C0DE)
        # Z logicals commute with X checks and are quotiented by Z stabilizers.
        zres = search_basis("z", hx, hz, n, (args.seed << 1) ^ 0xA91CE)
        choices = [r for r in (xres, zres) if r["vector_int"]]
        if choices:
            best = min(choices, key=lambda r: (r["upper_bound"], 0 if r["basis"] == "x" else 1))
            out = {
                "status": "completed",
                "basis": best["basis"],
                "vector": int_to_vec(best["vector_int"], n),
                "upper_bound": int(best["upper_bound"]),
            }
        else:
            out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    except Exception:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
