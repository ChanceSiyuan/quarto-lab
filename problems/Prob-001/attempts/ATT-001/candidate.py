#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from typing import Iterable, List, Optional, Sequence, Tuple


def _parse_token(tok: str) -> int:
    tok = tok.strip()
    if tok in ("0", "1"):
        return int(tok)
    try:
        return int(tok) & 1
    except ValueError:
        return 0


def load_matrix(path: str) -> Tuple[List[int], int]:
    """Load a binary matrix as integer row bitsets.

    Supported without optional dependencies: whitespace/comma text, MatrixMarket
    coordinate files, and simple JSON nested lists. If numpy is installed, .npy
    and .npz arrays are also accepted.
    """
    lower = path.lower()
    if lower.endswith(".npy") or lower.endswith(".npz"):
        try:
            import numpy as np  # type: ignore

            obj = np.load(path, allow_pickle=False)
            if hasattr(obj, "files"):
                key = obj.files[0]
                arr = obj[key]
            else:
                arr = obj
            arr = np.asarray(arr, dtype=np.uint8) & 1
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            rows = []
            for row in arr:
                bits = 0
                for j, val in enumerate(row.tolist()):
                    if val & 1:
                        bits |= 1 << j
                rows.append(bits)
            return rows, int(arr.shape[1])
        except Exception:
            pass

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    stripped = text.lstrip()
    if stripped.startswith("["):
        data = json.loads(text)
        if data and isinstance(data[0], (int, bool)):
            data = [data]
        n = max((len(row) for row in data), default=0)
        rows = []
        for row in data:
            bits = 0
            for j, val in enumerate(row):
                if int(val) & 1:
                    bits |= 1 << j
            rows.append(bits)
        return rows, n
    if stripped.startswith("{"):
        data = json.loads(text)
        if data.get("format") == "sparse_rows":
            n = int(data["num_cols"])
            rows = []
            for support in data["rows"]:
                bits = 0
                for column in support:
                    if not 0 <= int(column) < n:
                        raise ValueError("sparse row index is out of range")
                    bits ^= 1 << int(column)
                rows.append(bits)
            return rows, n
        for key in ("matrix", "data", "H", "hx", "hz"):
            if key in data:
                mat = data[key]
                if mat and isinstance(mat[0], (int, bool)):
                    mat = [mat]
                n = max((len(row) for row in mat), default=0)
                rows = []
                for row in mat:
                    bits = 0
                    for j, val in enumerate(row):
                        if int(val) & 1:
                            bits |= 1 << j
                    rows.append(bits)
                return rows, n

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines and lines[0].startswith("%%MatrixMarket"):
        body = [ln for ln in lines[1:] if not ln.startswith("%")]
        if not body:
            return [], 0
        m, n, _ = [int(x) for x in body[0].split()[:3]]
        rows = [0] * m
        for ln in body[1:]:
            parts = ln.split()
            if len(parts) >= 2:
                i = int(parts[0]) - 1
                j = int(parts[1]) - 1
                val = 1 if len(parts) == 2 else _parse_token(parts[2])
                if val & 1 and 0 <= i < m and 0 <= j < n:
                    rows[i] ^= 1 << j
        return rows, n

    numeric_lines = []
    for ln in lines:
        if ln.startswith("#") or ln.startswith("%"):
            continue
        parts = ln.replace(",", " ").split()
        if parts and all(part.lstrip("+-").isdigit() for part in parts):
            numeric_lines.append([int(part) for part in parts])
    if len(numeric_lines) >= 4 and len(numeric_lines[0]) >= 2 and len(numeric_lines[1]) >= 2:
        n, m = numeric_lines[0][0], numeric_lines[0][1]
        if n > 0 and m > 0 and len(numeric_lines) >= 4 + n:
            col_w = numeric_lines[2]
            row_w = numeric_lines[3]
            if len(col_w) >= n and len(row_w) >= m:
                rows = [0] * m
                ok = True
                for j in range(n):
                    entries = numeric_lines[4 + j]
                    for idx in entries[: col_w[j]]:
                        if idx == 0:
                            continue
                        if not (1 <= idx <= m):
                            ok = False
                            break
                        rows[idx - 1] ^= 1 << j
                    if not ok:
                        break
                if ok:
                    return rows, n

    parsed: List[List[int]] = []
    for ln in lines:
        if ln.startswith("#") or ln.startswith("%"):
            continue
        ln = ln.replace(",", " ").replace(";", " ")
        parts = ln.split()
        if len(parts) == 1 and parts[0] and set(parts[0]) <= {"0", "1"}:
            parsed.append([int(ch) for ch in parts[0]])
        elif parts:
            parsed.append([_parse_token(tok) for tok in parts])
    n = max((len(row) for row in parsed), default=0)
    rows = []
    for row in parsed:
        bits = 0
        for j, val in enumerate(row):
            if val & 1:
                bits |= 1 << j
        rows.append(bits)
    return rows, n


def rref(rows: Sequence[int], n: int) -> Tuple[List[int], List[int]]:
    work = [r for r in rows if r]
    out: List[int] = []
    pivots: List[int] = []
    i = 0
    for col in range(n):
        pivot = None
        mask = 1 << col
        for k in range(i, len(work)):
            if work[k] & mask:
                pivot = k
                break
        if pivot is None:
            continue
        work[i], work[pivot] = work[pivot], work[i]
        for k in range(len(work)):
            if k != i and (work[k] & mask):
                work[k] ^= work[i]
        out.append(work[i])
        pivots.append(col)
        i += 1
        if i == len(work):
            break
    order = sorted(range(len(out)), key=lambda t: pivots[t])
    return [out[t] for t in order], [pivots[t] for t in order]


def reduce_by_basis(v: int, basis: Sequence[int], pivots: Sequence[int]) -> int:
    x = v
    for row, col in zip(basis, pivots):
        if (x >> col) & 1:
            x ^= row
    return x


def in_rowspace(v: int, basis: Sequence[int], pivots: Sequence[int]) -> bool:
    return reduce_by_basis(v, basis, pivots) == 0


def nullspace_basis(rows: Sequence[int], n: int) -> List[int]:
    rbasis, pivots = rref(rows, n)
    pivot_set = set(pivots)
    out: List[int] = []
    for free in range(n):
        if free in pivot_set:
            continue
        v = 1 << free
        for row, col in reversed(list(zip(rbasis, pivots))):
            if (row >> free) & 1:
                v |= 1 << col
        out.append(v)
    return out


def mat_vec_zero(rows: Sequence[int], v: int) -> bool:
    return all(((row & v).bit_count() & 1) == 0 for row in rows)


def bits_to_list(v: int, n: int) -> List[int]:
    return [(v >> j) & 1 for j in range(n)]


def random_kernel_vector(ns: Sequence[int], rng: random.Random) -> int:
    v = 0
    if not ns:
        return 0
    p = rng.choice((0.08, 0.15, 0.25, 0.5))
    any_bit = False
    for b in ns:
        if rng.random() < p:
            v ^= b
            any_bit = True
    if not any_bit:
        v = rng.choice(ns)
    return v


def greedy_coset_descent(v: int, stabilizers: Sequence[int], rng: random.Random, passes: int) -> int:
    if not stabilizers:
        return v
    best = v
    current = v
    rows = [s for s in stabilizers if s]
    temp = 1.5
    for _ in range(passes):
        rng.shuffle(rows)
        improved = False
        for s in rows:
            cand = current ^ s
            dw = cand.bit_count() - current.bit_count()
            if dw < 0 or (dw == 0 and rng.random() < 0.2) or rng.random() < pow(2.718281828, -max(0, dw) / max(temp, 1e-6)):
                current = cand
                if 0 < current.bit_count() < best.bit_count():
                    best = current
                    improved = True
        temp *= 0.92
        if not improved and rng.random() < 0.35:
            current = best
    return best


def search_basis(
    label: str,
    checks: Sequence[int],
    stabilizers: Sequence[int],
    n: int,
    seed: int,
    budget: int,
) -> Optional[int]:
    rng = random.Random((seed << 8) ^ (17 if label == "x" else 83))
    stab_basis, stab_pivots = rref(stabilizers, n)
    ns = nullspace_basis(checks, n)
    if not ns:
        return None

    best: Optional[int] = None

    def accept(v: int) -> bool:
        return v != 0 and mat_vec_zero(checks, v) and not in_rowspace(v, stab_basis, stab_pivots)

    probes: Iterable[int] = list(ns[: min(len(ns), 256)])
    for v0 in probes:
        if accept(v0):
            v = greedy_coset_descent(v0, stabilizers, rng, max(2, min(24, budget // 200 + 2)))
            if accept(v) and (best is None or v.bit_count() < best.bit_count()):
                best = v

    for t in range(budget):
        v0 = random_kernel_vector(ns, rng)
        if not accept(v0):
            continue
        passes = 3 + (t % 7)
        v = greedy_coset_descent(v0, stabilizers, rng, passes)
        if accept(v) and (best is None or v.bit_count() < best.bit_count()):
            best = v
            if best.bit_count() <= 1:
                break

    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        hx, nx = load_matrix(args.hx)
        hz, nz = load_matrix(args.hz)
        n = max(nx, nz)
        os.makedirs(args.output_dir, exist_ok=True)

        budget = int(os.environ.get("CANDIDATE_BUDGET", "1200"))
        wx = search_basis("x", hz, hx, n, args.seed, budget)
        wz = search_basis("z", hx, hz, n, args.seed + 1000003, budget)

        choices = []
        if wx is not None:
            choices.append(("x", wx))
        if wz is not None:
            choices.append(("z", wz))

        if choices:
            basis, vec = min(choices, key=lambda item: (item[1].bit_count(), item[0]))
            result = {
                "status": "completed",
                "basis": basis,
                "vector": bits_to_list(vec, n),
                "upper_bound": int(vec.bit_count()),
            }
        else:
            result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}
    except Exception:
        result = {"status": "failed", "basis": "x", "vector": [], "upper_bound": None}

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
