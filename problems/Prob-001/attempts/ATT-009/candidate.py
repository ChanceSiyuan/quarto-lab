#!/usr/bin/env python3
import argparse
import json
import random
import time


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        n = max((len(r) for r in obj), default=0)
        rows = []
        for r in obj:
            x = 0
            for i, b in enumerate(r):
                if b & 1:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]
    if "data" in obj:
        n = int(obj.get("n_cols", 0))
        rows = []
        for r in obj["data"]:
            x = 0
            for i, b in enumerate(r):
                if (b & 1) and i < n:
                    x |= 1 << i
            rows.append(x)
        return rows, n
    if "rows" in obj:
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj["rows"]:
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    x |= 1 << c
            rows.append(x)
        return rows, n
    raise ValueError("unsupported matrix JSON format")


def parity(x):
    return x.bit_count() & 1


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                basis[p] = x
                for q, y in list(basis.items()):
                    if q != p and ((y >> p) & 1):
                        basis[q] = y ^ x
                break
            x ^= b
    return basis


def reduce_by_basis(x, basis):
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            return x
        x ^= b
    return 0


def in_rowspace(x, basis):
    return reduce_by_basis(x, basis) == 0


def nullspace_basis(rows, n):
    rb = rref_basis(rows)
    pivots = set(rb)
    out = []
    for f in range(n):
        if f in pivots:
            continue
        v = 1 << f
        for p, row in rb.items():
            if (row >> f) & 1:
                v |= 1 << p
        out.append(v)
    return out


def kernel_ok(v, check_rows):
    return all(parity(v & r) == 0 for r in check_rows)


def verified(v, kernel_rows, stabilizer_basis):
    return v != 0 and kernel_ok(v, kernel_rows) and not in_rowspace(v, stabilizer_basis)


def to_bits(v, n):
    return [(v >> i) & 1 for i in range(n)]


def greedy_coset_reduce(v, stab_rows, rng, rounds=3, temp=0.0):
    if not stab_rows:
        return v
    rows = list(stab_rows)
    best = v
    best_w = v.bit_count()
    cur = v
    cur_w = best_w
    for r in range(rounds):
        rng.shuffle(rows)
        improved = False
        for s in rows:
            nw = (cur ^ s).bit_count()
            if nw < cur_w or (temp > 0.0 and rng.random() < temp / (1.0 + max(0, nw - cur_w))):
                cur ^= s
                cur_w = nw
                improved = True
                if cur_w < best_w:
                    best = cur
                    best_w = cur_w
        temp *= 0.55
        if not improved:
            break
    return best


def first_logical_from_kernel(kbasis, stabilizer_basis):
    for v in sorted(kbasis, key=lambda x: x.bit_count()):
        if v and not in_rowspace(v, stabilizer_basis):
            return v
    return 0


def choose_basis_pool(kbasis, rng, limit=384):
    if len(kbasis) <= limit:
        pool = list(kbasis)
    else:
        low = sorted(kbasis, key=lambda x: x.bit_count())[: limit * 2 // 3]
        rest = kbasis[:]
        rng.shuffle(rest)
        pool = low + rest[: limit - len(low)]
    pool.sort(key=lambda x: (x.bit_count(), rng.random()))
    return pool


def random_combo(pool, rng, max_terms):
    if not pool:
        return 0
    terms = 1 + rng.randrange(max(1, max_terms))
    v = 0
    # Bias toward low-weight nullspace directions but keep a random tail.
    for _ in range(terms):
        if rng.random() < 0.72:
            j = int((rng.random() ** 2.2) * len(pool))
        else:
            j = rng.randrange(len(pool))
        v ^= pool[j]
    return v


def search_side(name, kernel_rows, stabilizer_rows, n, rng, deadline):
    stabilizer_basis = rref_basis(stabilizer_rows)
    stab_independent = list(stabilizer_basis.values())
    stab_independent.sort(key=lambda x: x.bit_count())
    kbasis = nullspace_basis(kernel_rows, n)
    if not kbasis:
        return None

    fallback = first_logical_from_kernel(kbasis, stabilizer_basis)
    if not fallback:
        return None

    best = greedy_coset_reduce(fallback, stab_independent, rng, rounds=8, temp=0.0)
    if not verified(best, kernel_rows, stabilizer_basis):
        best = fallback
    best_w = best.bit_count()

    pool = choose_basis_pool(kbasis, rng)
    population = [best]
    for v in pool[: min(64, len(pool))]:
        if not in_rowspace(v, stabilizer_basis):
            vv = greedy_coset_reduce(v, stab_independent, rng, rounds=5, temp=0.0)
            if verified(vv, kernel_rows, stabilizer_basis):
                population.append(vv)
                if vv.bit_count() < best_w:
                    best, best_w = vv, vv.bit_count()
    population = sorted(set(population), key=lambda x: x.bit_count())[:48]
    if best_w <= 1:
        return {"basis": name, "vector": to_bits(best, n), "upper_bound": best_w}

    dim = len(pool)
    max_terms = min(18, max(2, int(dim ** 0.5) + 1))
    max_iters = min(12000, max(900, 2200 + 35 * dim))
    iter_count = 0
    while iter_count < max_iters and time.monotonic() < deadline:
        iter_count += 1
        phase = iter_count / 3500.0
        temp = max(0.01, 0.45 * (0.996 ** iter_count))

        if len(population) >= 2 and rng.random() < 0.58:
            a, b = rng.sample(population, 2)
            v = a ^ b
            # Reinject a few kernel-basis mutations so recombination does not
            # collapse into already explored stabilizer-adjusted cosets.
            flips = 1 + rng.randrange(1 + min(6, max_terms))
            for _ in range(flips):
                if rng.random() < max(0.18, 0.75 - phase):
                    v ^= pool[int((rng.random() ** 2.0) * len(pool))]
                else:
                    v ^= pool[rng.randrange(len(pool))]
        else:
            v = random_combo(pool, rng, max_terms)

        if not v or in_rowspace(v, stabilizer_basis):
            continue

        rounds = 2 + (iter_count % 5)
        vv = greedy_coset_reduce(v, stab_independent, rng, rounds=rounds, temp=temp)
        if not verified(vv, kernel_rows, stabilizer_basis):
            continue

        w = vv.bit_count()
        if w < best_w:
            best, best_w = vv, w

        population.append(vv)
        if len(population) > 80:
            population = sorted(set(population), key=lambda x: (x.bit_count(), rng.random()))[:48]

    if verified(best, kernel_rows, stabilizer_basis):
        return {"basis": name, "vector": to_bits(best, n), "upper_bound": best_w}
    if verified(fallback, kernel_rows, stabilizer_basis):
        return {"basis": name, "vector": to_bits(fallback, n), "upper_bound": fallback.bit_count()}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        deadline = time.monotonic() + 9.0
        # X logicals commute with Z checks and are nontrivial modulo X stabilizers;
        # Z logicals use the dual condition.
        order = ["x", "z"]
        rng.shuffle(order)
        results = []
        for side in order:
            remaining = max(0.75, deadline - time.monotonic())
            side_deadline = time.monotonic() + remaining / (2 if len(results) == 0 else 1)
            if side == "x":
                res = search_side("x", hz, hx, n, rng, side_deadline)
            else:
                res = search_side("z", hx, hz, n, rng, side_deadline)
            if res is not None:
                results.append(res)
        if not results:
            out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
        else:
            best = min(results, key=lambda r: r["upper_bound"])
            out = {
                "status": "completed",
                "basis": best["basis"],
                "vector": best["vector"],
                "upper_bound": best["upper_bound"],
            }
    except Exception:
        out = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
