#!/usr/bin/env python3
import argparse
import json
import random
import time


def fail():
    print(json.dumps({"status": "failed", "basis": "x", "vector": [], "upper_bound": None}, separators=(",", ":")))


def row_from_bits(bits):
    x = 0
    for i, b in enumerate(bits):
        if b & 1:
            x |= 1 << i
    return x


def row_from_indices(indices):
    x = 0
    for i in indices:
        if i >= 0:
            x |= 1 << int(i)
    return x


def parse_matrix_object(obj):
    if isinstance(obj, list):
        if not obj:
            return [], 0
        if all(isinstance(r, list) for r in obj):
            n = max((len(r) for r in obj), default=0)
            return [row_from_bits(r) for r in obj], n
        raise ValueError("unsupported list matrix")

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or row list")

    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    elif "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    elif "matrix" in obj and isinstance(obj["matrix"], (dict, list)):
        return parse_matrix_object(obj["matrix"])

    if "data" in obj:
        n = int(obj.get("n_cols", obj.get("num_cols", obj.get("cols", 0))))
        data = obj["data"]
        if data and all(isinstance(r, list) for r in data):
            if n == 0:
                n = max((len(r) for r in data), default=0)
            return [row_from_bits(r) for r in data], n
        if n <= 0:
            raise ValueError("dense matrix missing n_cols")
        rows = []
        for off in range(0, len(data), n):
            rows.append(row_from_bits(data[off : off + n]))
        return rows, n

    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", obj.get("cols", 0))))
        rows_obj = obj["rows"]
        if all(isinstance(r, list) and all(isinstance(v, int) for v in r) for r in rows_obj):
            if n == 0:
                n = 1 + max((i for r in rows_obj for i in r), default=-1)
            return [row_from_indices(r) for r in rows_obj], n
        raise ValueError("unsupported sparse rows")

    raise ValueError("unrecognized matrix format")


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        return parse_matrix_object(json.load(f))


class Reducer:
    def __init__(self, rows=()):
        self.basis = {}
        for r in rows:
            self.add(r)

    def reduce(self, x):
        while x:
            p = x.bit_length() - 1
            b = self.basis.get(p)
            if b is None:
                return x
            x ^= b
        return 0

    def contains(self, x):
        return self.reduce(x) == 0

    def add(self, x):
        x = self.reduce(x)
        if x == 0:
            return False
        p = x.bit_length() - 1
        for q, r in list(self.basis.items()):
            if (r >> p) & 1:
                self.basis[q] = r ^ x
        self.basis[p] = x
        return True

    def rows(self):
        return list(self.basis.values())


def kernel_basis(check_rows, n):
    red = Reducer(r for r in check_rows if r)
    pivots = set(red.basis)
    free = [i for i in range(n) if i not in pivots]
    out = []
    for f in free:
        v = 1 << f
        for p, r in red.basis.items():
            if (r >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def in_kernel(v, checks):
    for r in checks:
        if ((v & r).bit_count() & 1) != 0:
            return False
    return True


def verified(v, checks, stabilizer_reducer):
    return v != 0 and in_kernel(v, checks) and not stabilizer_reducer.contains(v)


def bits_list(v, n):
    return [(v >> i) & 1 for i in range(n)]


def logical_generators(checks, stabs, n):
    stab_red = Reducer(stabs)
    span = Reducer(stabs)
    gens = []
    for k in kernel_basis(checks, n):
        if k and not span.contains(k):
            if verified(k, checks, stab_red):
                gens.append(k)
            span.add(k)
    return gens, stab_red


def stabilizers_preserving_kernel(stabs, checks):
    return [r for r in stabs if r and in_kernel(r, checks)]


def greedy_descent(v, rows, rng, passes=4):
    if not rows:
        return v
    cur = v
    cur_w = cur.bit_count()
    order = list(range(len(rows)))
    for _ in range(passes):
        improved = False
        rng.shuffle(order)
        for i in order:
            nv = cur ^ rows[i]
            nw = nv.bit_count()
            if nw < cur_w:
                cur, cur_w = nv, nw
                improved = True
        if not improved:
            break
    return cur


def make_blocks(rows, rng):
    if not rows:
        return []
    idx = list(range(len(rows)))
    rng.shuffle(idx)
    m = len(idx)
    sizes = sorted(set([1, 2, 3, 5, 8, max(1, int(m ** 0.5)), max(1, m // 8), max(1, m // 4)]))
    blocks = []
    for size in sizes:
        if size > m:
            continue
        for off in range(0, m, size):
            block = idx[off : off + size]
            if block:
                blocks.append(block)
    rng.shuffle(blocks)
    return blocks


def perturb_from_block(v, block, rows, rng):
    x = v
    chosen = False
    for i in block:
        if rng.random() < 0.5:
            x ^= rows[i]
            chosen = True
    if not chosen and block:
        x ^= rows[rng.choice(block)]
    return x


def random_logical_combo(gens, rng):
    if not gens:
        return 0
    x = 0
    # Bias toward small combinations while occasionally mixing many generators.
    if rng.random() < 0.75:
        take = 1 + int(rng.expovariate(0.8))
        take = min(take, len(gens))
        for i in rng.sample(range(len(gens)), take):
            x ^= gens[i]
    else:
        for g in gens:
            if rng.random() < 0.5:
                x ^= g
        if x == 0:
            x = rng.choice(gens)
    return x


def search_basis(name, checks, stabs, n, seed, deadline):
    rng = random.Random((seed << 8) ^ (17 if name == "x" else 53))
    gens, stab_red = logical_generators(checks, stabs, n)
    if not gens:
        return None

    descent_rows = stabilizers_preserving_kernel(stabs, checks)
    descent_rows.sort(key=lambda r: (r.bit_count(), r))
    blocks = make_blocks(descent_rows, rng)

    candidates = []
    for g in gens:
        candidates.append(g)
        if time.monotonic() > deadline:
            break
    rounds = 60 + 8 * min(200, len(gens)) + 2 * min(400, len(descent_rows))
    rounds = max(rounds, 180)

    best = None
    best_w = n + 1

    def consider(v):
        nonlocal best, best_w
        if verified(v, checks, stab_red):
            w = v.bit_count()
            if w < best_w:
                best, best_w = v, w

    for v in candidates:
        consider(greedy_descent(v, descent_rows, rng))

    r = 0
    while r < rounds and time.monotonic() < deadline:
        base = random_logical_combo(gens, rng)
        if base == 0:
            r += 1
            continue
        v = greedy_descent(base, descent_rows, rng, passes=3)
        consider(v)

        # Multi-scale perturbation: move within the same logical coset by
        # toggling stabilizer-row blocks, then certify after local descent.
        if blocks and time.monotonic() < deadline:
            reps = 1 + (r % 3)
            for _ in range(reps):
                b = blocks[rng.randrange(len(blocks))]
                v2 = perturb_from_block(v, b, descent_rows, rng)
                v2 = greedy_descent(v2, descent_rows, rng, passes=3)
                consider(v2)
                if time.monotonic() >= deadline:
                    break

        # A larger shake, useful when the row basis has many redundant checks.
        if descent_rows and (r % 7 == 0):
            v3 = v
            shakes = 1 + rng.randrange(min(12, len(descent_rows)))
            for _ in range(shakes):
                v3 ^= rng.choice(descent_rows)
            consider(greedy_descent(v3, descent_rows, rng, passes=4))
        r += 1

    if best is None:
        for g in gens:
            if verified(g, checks, stab_red):
                best = g
                best_w = g.bit_count()
                break
    if best is None:
        return None
    return {"basis": name, "vector": best, "upper_bound": best_w}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        mask = (1 << n) - 1 if n > 0 else 0
        hx = [r & mask for r in hx]
        hz = [r & mask for r in hz]

        deadline = time.monotonic() + 8.0
        # X logicals commute with Z checks modulo X stabilizers; Z logicals
        # commute with X checks modulo Z stabilizers.
        results = []
        rx = search_basis("x", hz, hx, n, args.seed, deadline)
        if rx is not None:
            results.append(rx)
        rz = search_basis("z", hx, hz, n, args.seed, deadline)
        if rz is not None:
            results.append(rz)

        if not results:
            fail()
            return
        best = min(results, key=lambda d: (d["upper_bound"], 0 if d["basis"] == "x" else 1))
        out = {
            "status": "completed",
            "basis": best["basis"],
            "vector": bits_list(best["vector"], n),
            "upper_bound": int(best["upper_bound"]),
        }
        print(json.dumps(out, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
