#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time


def fail():
    print(json.dumps({"status": "failed", "basis": None, "vector": [], "upper_bound": None}, separators=(",", ":")))
    sys.exit(0)


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        data = obj
        n = max((len(r) for r in data), default=0)
        return [row_to_int(r, n) for r in data], n

    if not isinstance(obj, dict):
        raise ValueError("matrix JSON must be an object or list")

    fmt = obj.get("format") or obj.get("type")
    if fmt == "dense_binary_matrix" or ("data" in obj and "n_cols" in obj):
        n = int(obj.get("n_cols", 0))
        return [row_to_int(r, n) for r in obj.get("data", [])], n

    if fmt == "sparse_rows" or ("rows" in obj and ("num_cols" in obj or "n_cols" in obj)):
        n = int(obj.get("num_cols", obj.get("n_cols", 0)))
        rows = []
        for r in obj.get("rows", []):
            x = 0
            for c in r:
                c = int(c)
                if 0 <= c < n:
                    x ^= 1 << c
            rows.append(x)
        return rows, n

    # Tolerate common wrappers without depending on private formats.
    if "matrix" in obj:
        data = obj["matrix"]
        n = int(obj.get("n_cols", max((len(r) for r in data), default=0)))
        return [row_to_int(r, n) for r in data], n

    raise ValueError("unsupported matrix JSON")


def row_to_int(row, n):
    x = 0
    for i, v in enumerate(row[:n]):
        if int(v) & 1:
            x |= 1 << i
    return x


def int_to_bits(x, n):
    return [(x >> i) & 1 for i in range(n)]


def weight(x):
    return x.bit_count()


def rref(rows, n):
    a = [r for r in rows if r]
    rank = 0
    pivots = []
    for col in range(n):
        bit = 1 << col
        pivot = None
        for i in range(rank, len(a)):
            if a[i] & bit:
                pivot = i
                break
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        for i in range(len(a)):
            if i != rank and (a[i] & bit):
                a[i] ^= a[rank]
        pivots.append(col)
        rank += 1
        if rank == len(a):
            break
    return a[:rank], pivots


class RowSpace:
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
        if not x:
            return False
        p = x.bit_length() - 1
        self.basis[p] = x
        # Keep the representation reduced enough for stable membership checks.
        for q, b in list(self.basis.items()):
            if q != p and ((b >> p) & 1):
                self.basis[q] = b ^ x
        return True

    def rows(self):
        return list(self.basis.values())

    def rank(self):
        return len(self.basis)


def kernel_basis(check_rows, n):
    rr, pivots = rref(check_rows, n)
    pivot_set = set(pivots)
    out = []
    for f in range(n):
        if f in pivot_set:
            continue
        x = 1 << f
        for i, p in enumerate(pivots):
            if (rr[i] >> f) & 1:
                x |= 1 << p
        out.append(x)
    return out


def syndrome_zero(rows, x):
    return all(((r & x).bit_count() & 1) == 0 for r in rows)


def verified(x, check_rows, stab_space):
    return bool(x) and syndrome_zero(check_rows, x) and not stab_space.contains(x)


def logical_generators(check_rows, stab_rows, n):
    """Return kernel vectors whose cosets form a logical quotient basis."""
    kb = kernel_basis(check_rows, n)
    span = RowSpace(stab_rows)
    gens = []
    for v in sorted(kb, key=lambda z: (weight(z), z)):
        if span.add(v):
            # If adding changed the span beyond stabilizers, v was a new coset.
            # Recheck against the original stabilizer space to suppress pure stabilizers.
            if not RowSpace(stab_rows).contains(v):
                gens.append(v)
    return gens


def random_combo(rng, rows, force_one=True):
    if not rows:
        return 0
    x = 0
    used = False
    for r in rows:
        if rng.getrandbits(1):
            x ^= r
            used = True
    if force_one and not used:
        x = rows[rng.randrange(len(rows))]
    return x


def build_column_index(rows, n):
    cols = [[] for _ in range(n)]
    for i, r in enumerate(rows):
        x = r
        while x:
            lsb = x & -x
            c = lsb.bit_length() - 1
            if c < n:
                cols[c].append(i)
            x ^= lsb
    return cols


def greedy_coset_descent(x, stab_rows, rng, passes=8):
    if not x or not stab_rows:
        return x
    current = x
    rows = list(stab_rows)
    row_weights = [weight(r) for r in rows]
    for t in range(passes):
        improved = False
        order = list(range(len(rows)))
        if t:
            rng.shuffle(order)
        else:
            order.sort(key=lambda i: row_weights[i])
        for i in order:
            y = current ^ rows[i]
            if weight(y) < weight(current):
                current = y
                improved = True
        if not improved:
            break
    return current


def noisy_descent(x, stab_rows, rng, temperature, steps):
    current = x
    best = x
    if not stab_rows:
        return x
    for _ in range(steps):
        r = stab_rows[rng.randrange(len(stab_rows))]
        y = current ^ r
        dw = weight(y) - weight(current)
        if dw <= 0 or rng.random() < temperature ** max(1, dw):
            current = y
            if weight(current) < weight(best):
                best = current
    return best


def check_graph_mutation(x, logicals, stab_rows, check_rows, n, rng):
    # Kernel-safe perturbation: add another logical generator, then repair inside
    # the stabilizer coset using checks that touch the heaviest occupied columns.
    if logicals and rng.random() < 0.65:
        x ^= logicals[rng.randrange(len(logicals))]
    if not stab_rows:
        return x
    cols = build_column_index(stab_rows, n)
    occupied = [i for i in range(n) if (x >> i) & 1]
    rng.shuffle(occupied)
    for c in occupied[: min(16, len(occupied))]:
        choices = cols[c]
        if choices:
            y = x ^ stab_rows[rng.choice(choices)]
            if weight(y) <= weight(x) + rng.randrange(3):
                x = y
    return x


def support_peeling(x, stab_rows, n, rng):
    # Randomly target currently occupied qubits and add stabilizers covering them
    # when this removes more occupied support than it introduces.
    if not stab_rows:
        return x
    current = x
    col_rows = build_column_index(stab_rows, n)
    for _ in range(min(4 * max(1, weight(current)), 200)):
        occ = [i for i in range(n) if (current >> i) & 1]
        if not occ:
            break
        c = rng.choice(occ)
        best = None
        best_delta = 0
        for idx in rng.sample(col_rows[c], min(len(col_rows[c]), 8)) if col_rows[c] else []:
            r = stab_rows[idx]
            delta = weight(current ^ r) - weight(current)
            if delta < best_delta:
                best_delta = delta
                best = r
        if best is not None:
            current ^= best
    return current


def improve_basis(logicals, stab_rows, check_rows, n, rng, deadline):
    candidates = []
    for g in logicals:
        candidates.append(greedy_coset_descent(g, stab_rows, rng, passes=10))
    if not candidates:
        return None
    best = min(candidates, key=weight)
    attempts = 0
    base_steps = 20 + min(300, n * 2)
    while time.time() < deadline and attempts < 1600:
        attempts += 1
        mode = attempts % 5
        if mode == 0:
            x = random_combo(rng, logicals, True)
        elif mode == 1:
            x = rng.choice(candidates) ^ random_combo(rng, logicals, False)
            if not x:
                x = rng.choice(logicals)
        elif mode == 2:
            x = check_graph_mutation(rng.choice(candidates), logicals, stab_rows, check_rows, n, rng)
        elif mode == 3:
            x = support_peeling(random_combo(rng, logicals, True), stab_rows, n, rng)
        else:
            # Sparse-ish information-set style seed: combine a small random subset
            # of quotient generators, biased toward individually light ones.
            ordered = sorted(logicals, key=weight)
            cap = max(1, min(len(ordered), 1 + int(rng.expovariate(0.35))))
            x = 0
            for g in rng.sample(ordered[: max(cap, min(len(ordered), 12))], min(cap, len(ordered))):
                x ^= g
            if not x:
                x = ordered[0]

        if attempts % 7 == 0:
            temp = 0.45 + 0.45 * rng.random()
            x = noisy_descent(x, stab_rows, rng, temp, base_steps)
        x = greedy_coset_descent(x, stab_rows, rng, passes=6)
        if verified(x, check_rows, RowSpace(stab_rows)):
            candidates.append(x)
            if weight(x) < weight(best):
                best = x
    return best


def solve_side(name, check_rows, stab_rows, n, seed, deadline):
    rng = random.Random((seed ^ (0x9E3779B97F4A7C15 if name == "x" else 0xD1B54A32D192ED03)) & ((1 << 64) - 1))
    stab_space = RowSpace(stab_rows)
    gens = logical_generators(check_rows, stab_rows, n)
    verified_gens = []
    for g in gens:
        y = greedy_coset_descent(g, stab_rows, rng, passes=12)
        if verified(y, check_rows, stab_space):
            verified_gens.append(y)
    if not verified_gens:
        # Reliable fallback: scan the full kernel basis for the first non-stabilizer.
        for g in kernel_basis(check_rows, n):
            if verified(g, check_rows, stab_space):
                verified_gens.append(g)
                break
    if not verified_gens:
        return None
    best = improve_basis(verified_gens, stab_rows, check_rows, n, rng, deadline)
    if best is None:
        best = min(verified_gens, key=weight)
    if verified(best, check_rows, stab_space):
        return best
    return min((g for g in verified_gens if verified(g, check_rows, stab_space)), key=weight, default=None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hx", required=True)
    ap.add_argument("--hz", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        hx = [r & ((1 << n) - 1) for r in hx]
        hz = [r & ((1 << n) - 1) for r in hz]
        os.makedirs(args.output_dir, exist_ok=True)

        # Keep runtime bounded; the algebraic fallback happens before the loop.
        budget = 7.5 if n <= 256 else 11.0
        deadline = time.time() + budget

        # X logicals commute with Z checks and are not X stabilizers.
        x = solve_side("x", hz, hx, n, args.seed, deadline)
        # Z logicals commute with X checks and are not Z stabilizers.
        z = solve_side("z", hx, hz, n, args.seed + 0xA5A5A5A5, deadline)

        choices = []
        if x is not None:
            choices.append(("x", x))
        if z is not None:
            choices.append(("z", z))
        if not choices:
            fail()
        basis, vec = min(choices, key=lambda p: (weight(p[1]), 0 if p[0] == "x" else 1))

        # Final independent gate.
        if basis == "x":
            ok = verified(vec, hz, RowSpace(hx))
        else:
            ok = verified(vec, hx, RowSpace(hz))
        if not ok:
            fail()

        out = {
            "status": "completed",
            "basis": basis,
            "vector": int_to_bits(vec, n),
            "upper_bound": weight(vec),
        }
        print(json.dumps(out, separators=(",", ":")))
    except Exception:
        fail()


if __name__ == "__main__":
    main()
