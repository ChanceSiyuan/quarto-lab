#!/usr/bin/env python3
import argparse
import json
import random
import sys
from collections import deque


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        rows = []
        for r in data:
            x = 0
            for j, v in enumerate(r):
                if v:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "data" in obj:
        data = obj["data"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        rows = []
        for r in data:
            x = 0
            for j, v in enumerate(r):
                if v:
                    x |= 1 << j
            rows.append(x)
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for j in r:
                jj = int(j)
                if jj >= 0:
                    x |= 1 << jj
                    if jj + 1 > n:
                        n = jj + 1
            rows.append(x)
        return rows, n

    raise ValueError("matrix JSON must use dense_binary_matrix/data or sparse_rows/rows")


def parity(x):
    return x.bit_count() & 1


def add_basis(basis, row):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            basis[p] = x
            return True
        x ^= b
    return False


def make_basis(rows):
    basis = {}
    for r in rows:
        if r:
            add_basis(basis, r)
    return basis


def in_rowspace(row, basis):
    x = row
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return False
        x ^= b
    return True


def rref_with_transform(rows, n, order=None):
    mat = [r for r in rows]
    m = len(mat)
    trans = [1 << i for i in range(m)]
    pivots = []
    r = 0
    if order is None:
        order = range(n)
    for c in order:
        pivot = -1
        for i in range(r, m):
            if (mat[i] >> c) & 1:
                pivot = i
                break
        if pivot < 0:
            continue
        if pivot != r:
            mat[r], mat[pivot] = mat[pivot], mat[r]
            trans[r], trans[pivot] = trans[pivot], trans[r]
        for i in range(m):
            if i != r and ((mat[i] >> c) & 1):
                mat[i] ^= mat[r]
                trans[i] ^= trans[r]
        pivots.append(c)
        r += 1
        if r == m:
            break
    return mat[:r], trans[:r], pivots


def nullspace_basis(rref_rows, pivots, n):
    pivot_set = set(pivots)
    out = []
    for f in range(n):
        if f in pivot_set:
            continue
        v = 1 << f
        for row, p in zip(rref_rows, pivots):
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def syndrome(rows, v):
    s = 0
    for i, r in enumerate(rows):
        if parity(r & v):
            s |= 1 << i
    return s


def solve_image_preimage(syn, rref_trans, pivots):
    x = 0
    for t, p in zip(rref_trans, pivots):
        if parity(t & syn):
            x |= 1 << p
    return x


def vector_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def tanner(rows, n):
    check_to_vars = []
    var_to_checks = [[] for _ in range(n)]
    for i, r in enumerate(rows):
        vs = []
        x = r
        while x:
            lsb = x & -x
            j = lsb.bit_length() - 1
            vs.append(j)
            var_to_checks[j].append(i)
            x ^= lsb
        check_to_vars.append(vs)
    return check_to_vars, var_to_checks


def random_cycle_seed(rng, check_to_vars, var_to_checks, n):
    active = [i for i, cs in enumerate(var_to_checks) if cs]
    if not active:
        return 1 << rng.randrange(n) if n else 0
    start = rng.choice(active)
    path = [start]
    seen = {start: 0}
    cur = start
    max_len = rng.randint(6, 28)
    for step in range(max_len):
        checks = var_to_checks[cur]
        if not checks:
            break
        c = rng.choice(checks)
        vs = check_to_vars[c]
        if len(vs) <= 1:
            break
        nxt = rng.choice(vs)
        for _ in range(4):
            if nxt != cur:
                break
            nxt = rng.choice(vs)
        if nxt in seen and step + 1 - seen[nxt] >= 2:
            cyc = path[seen[nxt]:]
            v = 0
            for q in cyc:
                v ^= 1 << q
            return v
        path.append(nxt)
        seen[nxt] = len(path) - 1
        cur = nxt
    v = 0
    for q in path:
        if rng.random() < 0.75:
            v ^= 1 << q
    return v


def trapping_seed(rng, rows, check_to_vars, var_to_checks, n):
    nonisolated = [i for i, cs in enumerate(var_to_checks) if cs]
    if not nonisolated:
        return 1 << rng.randrange(n) if n else 0
    start = rng.choice(nonisolated)
    support = {start}
    target = rng.randint(3, min(max(4, n), 18))
    syn = syndrome(rows, 1 << start)
    for _ in range(target * 3):
        if len(support) >= target:
            break
        unsat = [i for i in range(len(rows)) if (syn >> i) & 1]
        if not unsat:
            break
        c = min(rng.sample(unsat, min(len(unsat), 5)), key=lambda z: len(check_to_vars[z]) or 10**9)
        choices = [q for q in check_to_vars[c] if q not in support]
        if not choices:
            break
        q = min(rng.sample(choices, min(len(choices), 8)),
                key=lambda z: sum((syn >> cc) & 1 for cc in var_to_checks[z]))
        support.add(q)
        for cc in var_to_checks[q]:
            syn ^= 1 << cc
    v = 0
    for q in support:
        v |= 1 << q
    return v


def connected_seed(rng, check_to_vars, var_to_checks, n):
    starts = [i for i, cs in enumerate(var_to_checks) if cs]
    if not starts:
        return 1 << rng.randrange(n) if n else 0
    q0 = rng.choice(starts)
    target = rng.randint(2, min(max(2, n), 24))
    support = {q0}
    frontier = deque([q0])
    while frontier and len(support) < target:
        q = frontier.popleft()
        checks = list(var_to_checks[q])
        rng.shuffle(checks)
        for c in checks[:4]:
            vs = list(check_to_vars[c])
            rng.shuffle(vs)
            for nb in vs[:6]:
                if nb not in support and rng.random() < 0.55:
                    support.add(nb)
                    frontier.append(nb)
                    if len(support) >= target:
                        break
            if len(support) >= target:
                break
    v = 0
    for q in support:
        v |= 1 << q
    return v


def minimize_by_stabilizers(v, stab_rows, stab_basis, rng, rounds=5):
    if not v:
        return v
    rows = [r for r in stab_rows if r]
    best = v
    improved = True
    passes = 0
    while improved and passes < rounds:
        improved = False
        passes += 1
        order = rows[:]
        rng.shuffle(order)
        order.sort(key=lambda r: (best ^ r).bit_count() - best.bit_count())
        for r in order:
            w = best ^ r
            if w and w.bit_count() < best.bit_count() and not in_rowspace(w, stab_basis):
                best = w
                improved = True
    return best


def verify(v, check_rows, stab_basis):
    return bool(v) and syndrome(check_rows, v) == 0 and not in_rowspace(v, stab_basis)


def search_basis(name, check_rows, stab_rows, n, seed):
    rng = random.Random((seed << 8) ^ (0x58 if name == "x" else 0x7a))
    stab_basis = make_basis(stab_rows)
    rref_rows, rref_trans, pivots = rref_with_transform(check_rows, n)
    ns = nullspace_basis(rref_rows, pivots, n)
    check_to_vars, var_to_checks = tanner(check_rows, n)
    col_degrees = [len(var_to_checks[i]) for i in range(n)]
    repair_solvers = [(rref_trans, pivots)]
    if n:
        low_degree = list(range(n))
        low_degree.sort(key=lambda j: (col_degrees[j], j))
        high_degree = list(range(n))
        high_degree.sort(key=lambda j: (-col_degrees[j], j))
        for order in (low_degree, high_degree):
            rr, rt, pp = rref_with_transform(check_rows, n, order)
            repair_solvers.append((rt, pp))
        for _ in range(2):
            order = list(range(n))
            rng.shuffle(order)
            rr, rt, pp = rref_with_transform(check_rows, n, order)
            repair_solvers.append((rt, pp))
    best = None

    def consider(raw):
        nonlocal best
        raw &= (1 << n) - 1 if n else 0
        if not raw:
            return
        syn = syndrome(check_rows, raw)
        for rt, pp in repair_solvers:
            repaired = raw ^ solve_image_preimage(syn, rt, pp)
            if not repaired:
                continue
            cand = minimize_by_stabilizers(repaired, stab_rows, stab_basis, rng)
            if verify(cand, check_rows, stab_basis):
                if best is None or cand.bit_count() < best.bit_count():
                    best = cand

    # Fast basis-derived witnesses and randomized quotient combinations.
    outside = []
    for b in sorted(ns, key=lambda z: z.bit_count()):
        if not in_rowspace(b, stab_basis):
            outside.append(b)
            consider(b)
            if len(outside) >= 48:
                break
    for _ in range(min(180, 20 + 5 * len(outside))):
        if not outside:
            break
        v = 0
        for b in rng.sample(outside, rng.randint(1, min(len(outside), 8))):
            v ^= b
        consider(v)

    trials = 900 if n <= 256 else 520 if n <= 1200 else 260
    for t in range(trials):
        mode = t % 3
        if mode == 0:
            raw = random_cycle_seed(rng, check_to_vars, var_to_checks, n)
        elif mode == 1:
            raw = trapping_seed(rng, check_rows, check_to_vars, var_to_checks, n)
        else:
            raw = connected_seed(rng, check_to_vars, var_to_checks, n)
        consider(raw)

        # Occasionally mix a repaired graph seed with a quotient direction.
        if outside and t % 11 == 0:
            raw ^= rng.choice(outside)
            if rng.random() < 0.35 and len(outside) > 1:
                raw ^= rng.choice(outside)
            consider(raw)

    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1) for r in hx]
    hz = [r & ((1 << n) - 1) for r in hz]

    results = []
    xw = search_basis("x", hz, hx, n, args.seed)
    if xw is not None:
        results.append(("x", xw))
    zw = search_basis("z", hx, hz, n, args.seed)
    if zw is not None:
        results.append(("z", zw))

    if results:
        basis, vec = min(results, key=lambda bv: (bv[1].bit_count(), 0 if bv[0] == "x" else 1))
        out = {
            "status": "completed",
            "basis": basis,
            "vector": vector_list(vec, n),
            "upper_bound": int(vec.bit_count()),
        }
    else:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))
        sys.exit(0)
