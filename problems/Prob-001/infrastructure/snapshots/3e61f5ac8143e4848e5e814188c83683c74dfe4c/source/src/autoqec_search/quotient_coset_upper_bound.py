from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import random
import time
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.structure import (
    verify_css_upper_bound_witness,
)


METHOD = "quotient-coset-upper-bound"
BOUND_TYPE = "upper"
MAX_TIMEOUT_SECONDS = 300.0
DEFAULT_MAX_NO_IMPROVEMENT = 2500


def _is_plain_int(value: object) -> bool:
    return type(value) is int


def _require_basis(value: object) -> str:
    if value not in {"x", "z", "both"}:
        raise SearchIntegrityError("basis must be one of: x, z, both")
    return str(value)


def _require_seed(value: object) -> int:
    if not _is_plain_int(value) or value < 0:
        raise SearchIntegrityError("seed must be a nonnegative integer")
    return int(value)


def _require_positive_int(value: object, label: str) -> int:
    if not _is_plain_int(value) or value <= 0:
        raise SearchIntegrityError(f"{label} must be a positive integer")
    return int(value)


def _require_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise SearchIntegrityError("timeout_seconds must be a positive number no greater than 300")
    timeout = float(value)
    if timeout <= 0 or timeout > MAX_TIMEOUT_SECONDS:
        raise SearchIntegrityError("timeout_seconds must be a positive number no greater than 300")
    return timeout


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise SearchIntegrityError("quotient-coset search timeout during preprocessing")


def _rows_to_ints(
    rows: list[list[int]],
    *,
    num_cols: int,
    label: str,
    deadline: float | None = None,
) -> list[int]:
    """Encode dense binary rows with column zero stored in the low bit."""
    if not _is_plain_int(num_cols) or num_cols < 0:
        raise SearchIntegrityError(f"invalid matrix dimensions: {label}")

    _check_deadline(deadline)
    encoded: list[int] = []
    for row in rows:
        _check_deadline(deadline)
        if not isinstance(row, list) or len(row) != num_cols:
            raise SearchIntegrityError(f"matrix column mismatch: {label}")
        value = 0
        for column, bit in enumerate(row):
            if column % 256 == 0:
                _check_deadline(deadline)
            if not _is_plain_int(bit) or bit not in {0, 1}:
                raise SearchIntegrityError(
                    f"matrix contains non-binary entries: {label}"
                )
            if bit:
                value |= 1 << column
        encoded.append(value)
    return encoded


def _matrix_rows_to_ints(
    payload: dict,
    label: str,
    *,
    deadline: float | None = None,
) -> tuple[list[int], int]:
    """Validate a supported matrix payload and encode rows with deadline polling."""

    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid matrix payload: {label}")
    matrix_format = payload.get("format")
    if matrix_format == "dense_binary_matrix":
        required_keys = {"format", "n_rows", "n_cols", "data"}
        if not required_keys.issubset(payload):
            raise SearchIntegrityError(f"invalid matrix payload: {label}")
        num_rows = payload["n_rows"]
        num_cols = payload["n_cols"]
        if not _is_plain_int(num_rows) or not _is_plain_int(num_cols):
            raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
        if num_rows < 0 or num_cols < 0:
            raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
        rows_payload = payload["data"]
        if not isinstance(rows_payload, list):
            raise SearchIntegrityError(f"invalid matrix data: {label}")
        if int(num_rows) != len(rows_payload):
            raise SearchIntegrityError(f"matrix row count mismatch: {label}")
        return (
            _rows_to_ints(
                rows_payload,
                num_cols=int(num_cols),
                label=label,
                deadline=deadline,
            ),
            int(num_cols),
        )
    if matrix_format == "sparse_rows":
        num_cols = payload.get("num_cols")
        if not _is_plain_int(num_cols) or num_cols <= 0:
            raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
        rows_payload = payload.get("rows")
        if not isinstance(rows_payload, list):
            raise SearchIntegrityError(f"invalid matrix data: {label}")
        encoded: list[int] = []
        for row_index, sparse_row in enumerate(rows_payload):
            _check_deadline(deadline)
            if not isinstance(sparse_row, list):
                raise SearchIntegrityError(f"invalid matrix row: {label}")
            previous = -1
            value = 0
            for entry_index, column in enumerate(sparse_row):
                if entry_index % 256 == 0:
                    _check_deadline(deadline)
                if not _is_plain_int(column):
                    raise SearchIntegrityError(
                        f"matrix contains non-binary entries: {label}"
                    )
                if column < 0 or column >= num_cols:
                    raise SearchIntegrityError(f"matrix column mismatch: {label}")
                if column <= previous:
                    raise SearchIntegrityError(
                        f"matrix row {row_index} columns must be strictly increasing: {label}"
                    )
                value |= 1 << int(column)
                previous = int(column)
            encoded.append(value)
        return encoded, int(num_cols)
    raise SearchIntegrityError(f"unsupported matrix format: {label}")


def _css_checks_commute(
    hx_rows: list[int],
    hz_rows: list[int],
    *,
    deadline: float | None = None,
) -> bool:
    """Return whether encoded CSS checks commute, polling the deadline by pair."""

    _check_deadline(deadline)
    for hx_row in hx_rows:
        _check_deadline(deadline)
        for hz_index, hz_row in enumerate(hz_rows):
            if hz_index % 256 == 0:
                _check_deadline(deadline)
            if (hx_row & hz_row).bit_count() % 2:
                return False
    return True


def _vector_to_list(vector: int, num_cols: int) -> list[int]:
    if not _is_plain_int(vector) or vector < 0:
        raise SearchIntegrityError("vector must be a nonnegative integer")
    if not _is_plain_int(num_cols) or num_cols < 0:
        raise SearchIntegrityError("num_cols must be a nonnegative integer")
    if vector.bit_length() > num_cols:
        raise SearchIntegrityError("vector exceeds matrix width")
    return [(vector >> column) & 1 for column in range(num_cols)]


def _syndrome_zero(rows: list[int], vector: int) -> bool:
    return all(((row & vector).bit_count() % 2) == 0 for row in rows)


@dataclass
class _RowSpace:
    """An incremental GF(2) row space, indexed by pivot bit."""

    rows: list[int] | None = None

    def __post_init__(self) -> None:
        self._basis: dict[int, int] = {}
        for row in self.rows or []:
            self.add(row)

    def reduce(self, value: int) -> int:
        while value:
            pivot = value.bit_length() - 1
            row = self._basis.get(pivot)
            if row is None:
                return value
            value ^= row
        return 0

    def contains(self, value: int) -> bool:
        return self.reduce(value) == 0

    def add(self, value: int) -> bool:
        reduced = self.reduce(value)
        if not reduced:
            return False
        self._basis[reduced.bit_length() - 1] = reduced
        return True


def _kernel_basis(
    rows: list[int],
    num_cols: int,
    *,
    deadline: float | None = None,
) -> list[int]:
    """Return a deterministic GF(2) basis of vectors orthogonal to *rows*."""
    if not _is_plain_int(num_cols) or num_cols < 0:
        raise SearchIntegrityError("num_cols must be a nonnegative integer")

    _check_deadline(deadline)
    echelon: dict[int, int] = {}
    for raw_row in rows:
        _check_deadline(deadline)
        if (
            not _is_plain_int(raw_row)
            or raw_row < 0
            or raw_row.bit_length() > num_cols
        ):
            raise SearchIntegrityError("kernel rows must fit the matrix width")
        value = raw_row
        while value:
            _check_deadline(deadline)
            pivot = (value & -value).bit_length() - 1
            existing = echelon.get(pivot)
            if existing is None:
                echelon[pivot] = value
                break
            value ^= existing

    pivots = set(echelon)
    result: list[int] = []
    for free_column in range(num_cols):
        _check_deadline(deadline)
        if free_column in pivots:
            continue
        vector = 1 << free_column
        for pivot in sorted(pivots, reverse=True):
            _check_deadline(deadline)
            row_without_pivot = echelon[pivot] & ~(1 << pivot)
            if (row_without_pivot & vector).bit_count() % 2:
                vector |= 1 << pivot
        result.append(vector)
    return result


def _random_combo(items: list[int], rng: random.Random, *, force_small: bool = True) -> int:
    if not items:
        return 0
    maximum = min(len(items), 8 if force_small else 64)
    draw = rng.random()
    if draw < 0.45:
        count = 1
    elif draw < 0.72:
        count = min(2, maximum)
    elif draw < 0.88:
        count = min(3, maximum)
    else:
        count = rng.randint(1, maximum)
    value = 0
    for item in rng.sample(items, count):
        value ^= item
    return value


def _build_logical_reps_with_rng(
    null_basis: list[int],
    stabilizer_rows: list[int],
    rng: random.Random,
    *,
    deadline: float | None = None,
) -> list[int]:
    _check_deadline(deadline)
    span = _RowSpace()
    for row in stabilizer_rows:
        _check_deadline(deadline)
        span.add(row)
    ordered = sorted(null_basis, key=int.bit_count)
    _check_deadline(deadline)
    if len(ordered) > 1:
        sample = ordered[: min(len(ordered), 256)]
        rng.shuffle(sample)
        ordered = sample + ordered

    representatives: list[int] = []
    for vector in ordered:
        _check_deadline(deadline)
        if vector and not span.contains(vector):
            representatives.append(vector)
            span.add(vector)
    return representatives


def _build_logical_reps(
    null_basis: list[int], stabilizer_rows: list[int], *, seed: int
) -> list[int]:
    """Choose an independent quotient basis using a reproducible random order."""
    return _build_logical_reps_with_rng(null_basis, stabilizer_rows, random.Random(seed))


def _greedy_reduce(
    vector: int,
    stabilizer_rows: list[int],
    *,
    seed: int,
    deadline_seconds: float,
    passes: int = 6,
) -> int:
    """Reduce a vector's stabilizer coset without changing its logical class."""
    if not vector or not stabilizer_rows:
        return vector
    if deadline_seconds <= 0:
        return vector

    deadline = time.monotonic() + deadline_seconds
    rng = random.Random(seed)
    rows = list(stabilizer_rows)
    best = vector
    best_weight = vector.bit_count()
    for pass_index in range(passes):
        if time.monotonic() >= deadline:
            break
        if pass_index:
            rng.shuffle(rows)
        changed = False
        for row in rows:
            candidate = best ^ row
            weight = candidate.bit_count()
            if weight < best_weight:
                best = candidate
                best_weight = weight
                changed = True
                if best_weight == 1:
                    return best
        if not changed:
            break
    return best


def _search_basis(
    basis: str,
    check_rows: list[int],
    stabilizer_rows: list[int],
    num_cols: int,
    *,
    seed: int,
    max_no_improvement: int,
    deadline: float,
) -> dict[str, Any] | None:
    rng_seed = (seed << 8) ^ (17 if basis == "x" else 43)
    rng = random.Random(rng_seed)
    stabilizer_space = _RowSpace()
    for row in stabilizer_rows:
        _check_deadline(deadline)
        stabilizer_space.add(row)
    null_basis = _kernel_basis(check_rows, num_cols, deadline=deadline)
    if not null_basis:
        return None
    representatives = _build_logical_reps_with_rng(
        null_basis,
        stabilizer_rows,
        rng,
        deadline=deadline,
    )
    if not representatives:
        return None

    low_null = sorted(null_basis, key=int.bit_count)[: min(len(null_basis), 512)]
    low_reps = sorted(representatives, key=int.bit_count)[: min(len(representatives), 256)]
    low_stabilizers = sorted((row for row in stabilizer_rows if row), key=int.bit_count)[
        : min(len(stabilizer_rows), 2048)
    ]
    best: int | None = None
    best_weight = num_cols + 1
    attempts = 0
    no_improvement = 0

    def consider(candidate: int, *, passes: int) -> bool:
        nonlocal attempts, best, best_weight, no_improvement
        attempts += 1
        remaining = deadline - time.monotonic()
        reduced = _greedy_reduce(
            candidate,
            low_stabilizers,
            seed=rng.randrange(1 << 63),
            deadline_seconds=max(remaining, 0.0),
            passes=passes,
        )
        if not reduced or stabilizer_space.contains(reduced) or not _syndrome_zero(check_rows, reduced):
            no_improvement += 1
            return False
        weight = reduced.bit_count()
        if weight < best_weight:
            best = reduced
            best_weight = weight
            no_improvement = 0
            return True
        no_improvement += 1
        return False

    seed_vectors = list(low_reps)
    seed_vectors.extend(
        _random_combo(low_reps, rng) for _ in range(min(64, 4 * len(low_reps) + 8))
    )
    for candidate in seed_vectors:
        if time.monotonic() >= deadline:
            break
        consider(candidate, passes=10)
        if best_weight <= 2:
            break

    while time.monotonic() < deadline and no_improvement < max_no_improvement:
        mode = rng.random()
        if mode < 0.70:
            candidate = _random_combo(low_reps, rng)
        elif mode < 0.90:
            candidate = _random_combo(representatives, rng)
        else:
            candidate = _random_combo(low_null, rng)
            if stabilizer_space.contains(candidate):
                candidate ^= rng.choice(low_reps)
        if low_stabilizers and rng.random() < 0.65:
            for _ in range(rng.randint(1, min(6, len(low_stabilizers)))):
                candidate ^= rng.choice(low_stabilizers)
        consider(candidate, passes=6)
        if best_weight <= 2:
            break

    if best is None:
        return None
    return {
        "basis": basis,
        "vector": best,
        "upper_bound": best_weight,
        "attempts": attempts,
    }


def find_quotient_coset_upper_bound(
    hx_payload: dict,
    hz_payload: dict,
    *,
    basis: str = "both",
    seed: int = 0,
    max_no_improvement: int = DEFAULT_MAX_NO_IMPROVEMENT,
    timeout_seconds: float = MAX_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Find and independently verify a CSS logical-operator upper bound."""
    requested_basis = _require_basis(basis)
    seed = _require_seed(seed)
    max_no_improvement = _require_positive_int(max_no_improvement, "max_no_improvement")
    timeout_seconds = _require_timeout(timeout_seconds)
    started = time.monotonic()
    deadline = started + timeout_seconds

    hx_rows, num_cols = _matrix_rows_to_ints(
        hx_payload,
        "hx.json",
        deadline=deadline,
    )
    hz_rows, hz_num_cols = _matrix_rows_to_ints(
        hz_payload,
        "hz.json",
        deadline=deadline,
    )
    if num_cols != hz_num_cols:
        raise SearchIntegrityError("matrix column mismatch: hx.json vs hz.json")
    if not _css_checks_commute(hx_rows, hz_rows, deadline=deadline):
        raise SearchIntegrityError("CSS checks do not commute")
    _check_deadline(deadline)

    searches: list[tuple[str, list[int], list[int]]] = []
    if requested_basis in {"x", "both"}:
        searches.append(("x", hz_rows, hx_rows))
    if requested_basis in {"z", "both"}:
        searches.append(("z", hx_rows, hz_rows))

    found: list[dict[str, Any]] = []
    basis_results: list[dict[str, Any]] = []
    for found_basis, check_rows, stabilizer_rows in searches:
        if time.monotonic() >= deadline:
            basis_results.append({"basis": found_basis, "status": "timeout", "attempts": 0})
            continue
        result = _search_basis(
            found_basis,
            check_rows,
            stabilizer_rows,
            num_cols,
            seed=seed,
            max_no_improvement=max_no_improvement,
            deadline=deadline,
        )
        if result is None:
            basis_results.append({"basis": found_basis, "status": "not_found", "attempts": 0})
        else:
            found.append(result)
            basis_results.append(
                {
                    "basis": found_basis,
                    "status": "completed",
                    "attempts": result["attempts"],
                    "upper_bound": result["upper_bound"],
                }
            )

    if not found and time.monotonic() >= deadline:
        raise SearchIntegrityError("quotient-coset search timeout")
    if not found:
        raise SearchIntegrityError("no quotient-coset upper-bound witness found")

    selected = min(found, key=lambda result: (result["upper_bound"], result["basis"]))
    found_basis = selected["basis"]
    found_vector = _vector_to_list(selected["vector"], num_cols)
    witness_payload = {"basis": found_basis, "vector": found_vector}
    verification = verify_css_upper_bound_witness(hx_payload, hz_payload, witness_payload)
    if verification.get("status") != "pass":
        reason = verification.get("reason", "invalid_upper_bound_witness")
        raise SearchIntegrityError(f"invalid_css_upper_bound_witness: {reason}")

    elapsed_seconds = time.monotonic() - started
    return {
        "status": "completed",
        "method": METHOD,
        "bound_type": BOUND_TYPE,
        "basis": found_basis,
        "vector": found_vector,
        "upper_bound": selected["upper_bound"],
        "witness_payload": witness_payload,
        "distance_payload": verification["distance_payload"],
        "verification": verification,
        "provenance": {
            "method": METHOD,
            "seed": seed,
            "basis_requested": requested_basis,
            "max_no_improvement": max_no_improvement,
            "timeout_seconds": timeout_seconds,
            "attempts": sum(result["attempts"] for result in basis_results),
            "elapsed_seconds": elapsed_seconds,
            "basis_results": basis_results,
        },
    }
