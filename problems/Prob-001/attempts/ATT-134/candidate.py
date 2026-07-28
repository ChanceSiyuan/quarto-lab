#!/usr/bin/env python3
import argparse
import json
import os
import random
import time


def emit(status, basis=None, vector=None, upper_bound=None):
    print(json.dumps({
        "status": status,
        "basis": basis,
        "vector": vector,
        "upper_bound": upper_bound,
    }, separators=(",", ":")))


def load_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if "dense_binary_matrix" in obj:
        obj = obj["dense_binary_matrix"]
    if "sparse_rows" in obj:
        obj = obj["sparse_rows"]

    if "n_rows" in obj and "n_cols" in obj and "data" in obj:
        n = int(obj["n_cols"])
        rows = []
        for row in obj["data"]:
            if len(row) != n:
                raise ValueError("dense row has wrong length")
            bits = 0
            for i, v in enumerate(row):
                if v not in (0, 1, False, True):
                    raise ValueError("dense matrix entries must be binary")
                if int(v) & 1:
                    bits |= 1 << i
            rows.append(bits)
        if len(rows) != int(obj["n_rows"]):
            raise ValueError("dense matrix row count mismatch")
        return rows, n

    if "num_cols" in obj and "rows" in obj:
        n = int(obj["num_cols"])
        rows = []
        for row in obj["rows"]:
            last = -1
            bits = 0
            for c in row:
                c = int(c)
                if c <= last or c < 0 or c >= n:
                    raise ValueError("sparse rows must be strictly increasing valid indices")
                bits |= 1 << c
                last = c
            rows.append(bits)
        return rows, n

    raise ValueError("unsupported matrix JSON format")


def weight(x):
    return x.bit_count()


def to_list(x, n):
    return [(x >> i) & 1 for i in range(n)]


def dot_parity(a, b):
    return (a & b).bit_count() & 1


def in_kernel(v, checks):
    return all(dot_parity(v, r) == 0 for r in checks)


def rref_basis(rows):
    basis = {}
    for row in rows:
        x = row
        while x:
            p = (x & -x).bit_length() - 1
            if p in basis:
                x ^= basis[p]
            else:
                for q, b in list(basis.items()):
                    if (b >> p) & 1:
                        basis[q] = b ^ x
                basis[p] = x
                break
    return basis


def reduce_by_basis(x, basis):
    y = x
    while y:
        p = (y & -y).bit_length() - 1
        b = basis.get(p)
        if b is None:
            return y
        y ^= b
    return 0


def in_span(v, rows):
    return reduce_by_basis(v, rref_basis(rows)) == 0


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


def independent_logical_basis(kernel_basis, stabilizer_rows):
    span = rref_basis(stabilizer_rows)
    logicals = []
    for v in sorted(kernel_basis, key=weight):
        if reduce_by_basis(v, span) == 0:
            continue
        x = reduce_by_basis(v, span)
        while x:
            p = (x & -x).bit_length() - 1
            if p in span:
                x ^= span[p]
            else:
                for q, b in list(span.items()):
                    if (b >> p) & 1:
                        span[q] = b ^ x
                span[p] = x
                logicals.append(v)
                break
    return logicals


def greedy_reduce(v, stabilizers, rng, passes):
    cur = v
    cur_w = weight(cur)
    if not stabilizers:
        return cur

    order = list(stabilizers)
    for _ in range(passes):
        improved = False
        rng.shuffle(order)
        for row in order:
            nxt = cur ^ row
            nxt_w = weight(nxt)
            if nxt_w < cur_w or (nxt_w == cur_w and rng.randrange(16) == 0):
                cur, cur_w = nxt, nxt_w
                improved = True
        if not improved:
            break
    return cur


def mix_rows(rows, rng, count=None):
    if not rows:
        return 0
    if count is None:
        count = 1 + rng.randrange(len(rows))
    idxs = rng.sample(range(len(rows)), min(count, len(rows)))
    v = 0
    for i in idxs:
        v ^= rows[i]
    return v


def verified(v, checks, stabilizers):
    return v != 0 and in_kernel(v, checks) and not in_span(v, stabilizers)


def search_basis(name, checks, stabilizers, n, rng, deadline):
    k_basis = nullspace_basis(checks, n)
    l_basis = independent_logical_basis(k_basis, stabilizers)
    if not l_basis:
        return None

    candidates = list(l_basis)
    for v in l_basis:
        candidates.append(greedy_reduce(v, stabilizers, rng, 12))

    best = None
    best_w = n + 1
    attempts = 0
    max_attempts = max(400, 80 * (len(l_basis) + len(stabilizers) + 1))

    while attempts < max_attempts and time.monotonic() < deadline:
        attempts += 1
        if candidates and attempts <= len(candidates):
            v = candidates[attempts - 1]
        else:
            v = mix_rows(l_basis, rng)
            if stabilizers and rng.random() < 0.75:
                v ^= mix_rows(stabilizers, rng, rng.randrange(1, min(len(stabilizers), 12) + 1))

        v = greedy_reduce(v, stabilizers, rng, 20)
        if verified(v, checks, stabilizers):
            w = weight(v)
            if w < best_w:
                best, best_w = v, w
                if best_w <= 1:
                    break

    if best is None:
        for v in l_basis:
            if verified(v, checks, stabilizers):
                best = v
                best_w = weight(v)
                break
    if best is None:
        return None
    return (name, best, best_w)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        if nx != nz:
            raise ValueError("Hx and Hz have different column counts")
        os.makedirs(args.output_dir, exist_ok=True)

        rng = random.Random(args.seed)
        deadline = time.monotonic() + 25.0

        choices = [
            search_basis("x", hz, hx, nx, rng, deadline),
            search_basis("z", hx, hz, nx, rng, deadline),
        ]
        choices = [c for c in choices if c is not None]
        if not choices:
            emit("no_witness", None, [], None)
            return

        basis, vec, ub = min(choices, key=lambda item: (item[2], item[0]))
        checks = hz if basis == "x" else hx
        stabs = hx if basis == "x" else hz
        if not verified(vec, checks, stabs):
            emit("no_witness", None, [], None)
            return
        emit("completed", basis, to_list(vec, nx), ub)
    except Exception:
        emit("error", None, [], None)


if __name__ == "__main__":
    main()
