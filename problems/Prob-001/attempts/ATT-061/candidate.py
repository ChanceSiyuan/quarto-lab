#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time


def _unwrap_matrix(obj):
    if isinstance(obj, dict):
        for key in ("dense_binary_matrix", "sparse_rows", "matrix"):
            if key in obj and isinstance(obj[key], (dict, list)):
                inner = obj[key]
                if isinstance(inner, dict):
                    merged = dict(inner)
                    for nk in ("n_cols", "num_cols"):
                        if nk in obj and nk not in merged:
                            merged[nk] = obj[nk]
                    return merged
                return inner
    return obj


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = _unwrap_matrix(json.load(f))

    rows = []
    n = 0
    if isinstance(obj, list):
        for row in obj:
            if not isinstance(row, list):
                raise ValueError("matrix rows must be lists")
            n = max(n, len(row))
        for row in obj:
            m = 0
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    m |= 1 << i
            rows.append(m)
        return rows, n

    if not isinstance(obj, dict):
        raise ValueError("unsupported matrix JSON")

    n = int(obj.get("n_cols", obj.get("num_cols", 0)) or 0)
    if "data" in obj:
        for row in obj["data"]:
            n = max(n, len(row))
            m = 0
            for i, bit in enumerate(row):
                if int(bit) & 1:
                    m |= 1 << i
            rows.append(m)
        return rows, n

    sparse = obj.get("rows")
    if sparse is None:
        raise ValueError("matrix JSON needs data or rows")
    for row in sparse:
        m = 0
        for j in row:
            j = int(j)
            if j < 0:
                raise ValueError("negative column index")
            m ^= 1 << j
            n = max(n, j + 1)
        rows.append(m)
    return rows, n


def bit_count(x):
    return x.bit_count()


def rref_basis(rows, n=None):
    basis = {}
    for row in rows:
        x = int(row)
        while x:
            p = x.bit_length() - 1
            b = basis.get(p)
            if b is None:
                for q, y in list(basis.items()):
                    if (y >> p) & 1:
                        basis[q] = y ^ x
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


def in_span(x, basis):
    return reduce_by_basis(x, basis) == 0


def kernel_basis(check_rows, n):
    rb = rref_basis(check_rows, n)
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


def syndrome_zero(v, check_rows):
    for row in check_rows:
        if bit_count(row & v) & 1:
            return False
    return True


def verified(v, check_rows, stab_basis):
    return v != 0 and syndrome_zero(v, check_rows) and not in_span(v, stab_basis)


def insert_basis_vec(basis, row):
    x = int(row)
    while x:
        p = x.bit_length() - 1
        b = basis.get(p)
        if b is None:
            for q, y in list(basis.items()):
                if (y >> p) & 1:
                    basis[q] = y ^ x
            basis[p] = x
            return True
        x ^= b
    return False


def greedy_reduce(v, stab_rows, rng=None, rounds=2):
    best = v
    best_w = bit_count(best)
    rows = [r for r in stab_rows if r]
    rows.sort(key=bit_count)
    for _ in range(rounds):
        changed = False
        seq = rows
        if rng is not None and len(rows) > 1:
            seq = rows[:]
            rng.shuffle(seq)
        for r in seq:
            cand = best ^ r
            w = bit_count(cand)
            if w < best_w:
                best, best_w = cand, w
                changed = True
        if not changed:
            break
    return best


def build_logical_basis(check_rows, stab_rows, n, rng):
    stab_basis = rref_basis(stab_rows, n)
    span = dict(stab_basis)
    reps = []
    for v in kernel_basis(check_rows, n):
        if reduce_by_basis(v, span) != 0:
            v = greedy_reduce(v, stab_rows, rng=None, rounds=4)
            if verified(v, check_rows, stab_basis):
                reps.append(v)
                insert_basis_vec(span, v)
    return reps, stab_basis


def xor_reps(mask, reps):
    v = 0
    i = 0
    while mask:
        if mask & 1:
            v ^= reps[i]
        mask >>= 1
        i += 1
    return v


def make_individual(mask, reps, stab_rows, check_rows, stab_basis, rng, n_stab_flips=0):
    v = xor_reps(mask, reps)
    if stab_rows and n_stab_flips:
        for _ in range(n_stab_flips):
            v ^= rng.choice(stab_rows)
    v = greedy_reduce(v, stab_rows, rng=rng, rounds=3)
    if not verified(v, check_rows, stab_basis):
        v = greedy_reduce(xor_reps(mask, reps), stab_rows, rng=None, rounds=5)
    return (bit_count(v), mask, v)


def random_nonzero_mask(rng, ldim):
    if ldim <= 62:
        return rng.randrange(1, 1 << ldim)
    m = 0
    for i in range(ldim):
        if rng.random() < 0.18:
            m |= 1 << i
    if m == 0:
        m = 1 << rng.randrange(ldim)
    return m


def crossover_mask(a, b, ldim, rng):
    if ldim <= 1:
        return a or b or 1
    child = 0
    if rng.random() < 0.55:
        cut1 = rng.randrange(ldim)
        cut2 = rng.randrange(cut1, ldim)
        mid = ((1 << (cut2 - cut1 + 1)) - 1) << cut1
        full = (1 << ldim) - 1 if ldim <= 4096 else None
        child = (a & mid) | (b & (~mid if full is None else (full ^ mid)))
    else:
        for i in range(ldim):
            if ((a >> i) & 1 and rng.random() < 0.5) or ((b >> i) & 1 and rng.random() < 0.5):
                child ^= 1 << i
    if child == 0:
        child = a ^ b
    if child == 0:
        child = 1 << rng.randrange(ldim)
    return child


def mutate_mask(mask, ldim, rng):
    flips = 1
    if rng.random() < 0.35:
        flips += 1
    if rng.random() < 0.12:
        flips += rng.randrange(1, min(4, ldim) + 1)
    for _ in range(flips):
        mask ^= 1 << rng.randrange(ldim)
    if mask == 0:
        mask = 1 << rng.randrange(ldim)
    return mask


def search_basis(name, check_rows, stab_rows, n, seed):
    rng = random.Random(seed)
    reps, stab_basis = build_logical_basis(check_rows, stab_rows, n, rng)
    if not reps:
        return None

    ldim = len(reps)
    pop_size = min(96, max(18, 3 * ldim + 12))
    pop = []

    for i, rep in enumerate(reps):
        mask = 1 << i
        pop.append(make_individual(mask, reps, stab_rows, check_rows, stab_basis, rng))

    for _ in range(pop_size - len(pop)):
        mask = random_nonzero_mask(rng, ldim)
        flips = rng.randrange(0, min(5, len(stab_rows)) + 1) if stab_rows else 0
        pop.append(make_individual(mask, reps, stab_rows, check_rows, stab_basis, rng, flips))

    pop = [p for p in pop if verified(p[2], check_rows, stab_basis)]
    pop.sort(key=lambda t: t[0])
    best = pop[0]
    start = time.monotonic()
    iterations = min(2200, max(350, 90 * ldim))

    for gen in range(iterations):
        if time.monotonic() - start > 18.0:
            break
        elite = pop[: max(4, pop_size // 5)]
        children = elite[:]
        while len(children) < pop_size:
            p1 = rng.choice(pop[: max(6, len(pop) // 2)])
            p2 = rng.choice(pop[: max(6, len(pop) // 2)])
            mask = crossover_mask(p1[1], p2[1], ldim, rng)
            if rng.random() < 0.72:
                mask = mutate_mask(mask, ldim, rng)
            flips = 0
            if stab_rows and rng.random() < 0.55:
                flips = 1 + rng.randrange(min(7, len(stab_rows)))
            child = make_individual(mask, reps, stab_rows, check_rows, stab_basis, rng, flips)
            if verified(child[2], check_rows, stab_basis):
                children.append(child)
        children.sort(key=lambda t: (t[0], rng.random()))
        pop = children[:pop_size]
        if pop[0][0] < best[0]:
            best = pop[0]
        if best[0] <= 1:
            break
        if gen % 37 == 0 and len(stab_rows) > 1:
            # Immigrants keep the population from collapsing into one logical coset.
            for _ in range(max(2, pop_size // 12)):
                mask = random_nonzero_mask(rng, ldim)
                pop[-1 - _] = make_individual(mask, reps, stab_rows, check_rows, stab_basis, rng, 3)
            pop.sort(key=lambda t: t[0])

    if not verified(best[2], check_rows, stab_basis):
        return None
    return {"basis": name, "weight": best[0], "vector_int": best[2]}


def int_to_list(v, n):
    return [int((v >> i) & 1) for i in range(n)]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args(argv)

    hx, nx = load_matrix(args.hx)
    hz, nz = load_matrix(args.hz)
    n = max(nx, nz)
    hx = [r & ((1 << n) - 1) for r in hx]
    hz = [r & ((1 << n) - 1) for r in hz]

    candidates = []
    xres = search_basis("x", hz, hx, n, args.seed ^ 0x58A5)
    if xres is not None:
        candidates.append(xres)
    zres = search_basis("z", hx, hz, n, args.seed ^ 0xA75A)
    if zres is not None:
        candidates.append(zres)

    if candidates:
        best = min(candidates, key=lambda d: (d["weight"], 0 if d["basis"] == "x" else 1))
        out = {
            "status": "completed",
            "basis": best["basis"],
            "vector": int_to_list(best["vector_int"], n),
            "upper_bound": int(best["weight"]),
        }
    else:
        out = {"status": "failed", "basis": None, "vector": [], "upper_bound": None}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
