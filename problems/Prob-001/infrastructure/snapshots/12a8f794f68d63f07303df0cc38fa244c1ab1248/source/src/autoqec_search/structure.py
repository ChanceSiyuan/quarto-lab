from __future__ import annotations

from autoqec_search.load import SearchIntegrityError


DenseMatrix = list[list[int]]


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _dense_binary_matrix_data(payload: dict, label: str) -> DenseMatrix:
    required_keys = {"format", "n_rows", "n_cols", "data"}
    if not isinstance(payload, dict) or not required_keys.issubset(payload):
        raise SearchIntegrityError(f"invalid matrix payload: {label}")
    if payload["format"] != "dense_binary_matrix":
        raise SearchIntegrityError(f"unsupported matrix format: {label}")
    if not _is_plain_int(payload["n_rows"]) or not _is_plain_int(payload["n_cols"]):
        raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
    if payload["n_rows"] < 0 or payload["n_cols"] < 0:
        raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
    if not isinstance(payload["data"], list):
        raise SearchIntegrityError(f"invalid matrix data: {label}")
    if payload["n_rows"] != len(payload["data"]):
        raise SearchIntegrityError(f"matrix row count mismatch: {label}")

    rows: DenseMatrix = []
    for row in payload["data"]:
        if not isinstance(row, list):
            raise SearchIntegrityError(f"invalid matrix row: {label}")
        if len(row) != payload["n_cols"]:
            raise SearchIntegrityError(f"matrix column mismatch: {label}")
        if any(not _is_plain_int(bit) or bit not in (0, 1) for bit in row):
            raise SearchIntegrityError(f"matrix contains non-binary entries: {label}")
        rows.append([int(bit) for bit in row])
    return rows


def _sparse_rows_matrix_data(payload: dict, label: str) -> DenseMatrix:
    if payload.get("format") != "sparse_rows":
        raise SearchIntegrityError(f"unsupported matrix format: {label}")
    num_cols = payload.get("num_cols")
    if not _is_plain_int(num_cols) or num_cols <= 0:
        raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, list):
        raise SearchIntegrityError(f"invalid matrix data: {label}")
    rows: DenseMatrix = []
    for row_index, sparse_row in enumerate(rows_payload):
        if not isinstance(sparse_row, list):
            raise SearchIntegrityError(f"invalid matrix row: {label}")
        dense_row = [0] * int(num_cols)
        previous = -1
        for column in sparse_row:
            if not _is_plain_int(column):
                raise SearchIntegrityError(f"matrix contains non-binary entries: {label}")
            if column < 0 or column >= num_cols:
                raise SearchIntegrityError(f"matrix column mismatch: {label}")
            if column <= previous:
                raise SearchIntegrityError(
                    f"matrix row {row_index} columns must be strictly increasing: {label}"
                )
            dense_row[int(column)] = 1
            previous = int(column)
        rows.append(dense_row)
    return rows


def matrix_data(payload: dict, label: str) -> DenseMatrix:
    matrix_format = payload.get("format") if isinstance(payload, dict) else None
    if matrix_format == "dense_binary_matrix":
        return _dense_binary_matrix_data(payload, label)
    if matrix_format == "sparse_rows":
        return _sparse_rows_matrix_data(payload, label)
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid matrix payload: {label}")
    raise SearchIntegrityError(f"unsupported matrix format: {label}")


def _matrix_num_cols(payload: dict, rows: DenseMatrix, label: str) -> int:
    matrix_format = payload.get("format") if isinstance(payload, dict) else None
    if matrix_format == "dense_binary_matrix":
        num_cols = payload.get("n_cols")
    elif matrix_format == "sparse_rows":
        num_cols = payload.get("num_cols")
    else:
        raise SearchIntegrityError(f"unsupported matrix format: {label}")
    if not _is_plain_int(num_cols) or num_cols < 0:
        raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
    if rows and any(len(row) != int(num_cols) for row in rows):
        raise SearchIntegrityError(f"matrix column mismatch: {label}")
    return int(num_cols)


def _matrix_num_rows(payload: dict, rows: DenseMatrix, label: str) -> int:
    matrix_format = payload.get("format") if isinstance(payload, dict) else None
    if matrix_format == "dense_binary_matrix":
        num_rows = payload.get("n_rows")
        if not _is_plain_int(num_rows) or num_rows < 0:
            raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
        if int(num_rows) != len(rows):
            raise SearchIntegrityError(f"matrix row count mismatch: {label}")
        return int(num_rows)
    if matrix_format == "sparse_rows":
        return len(rows)
    raise SearchIntegrityError(f"unsupported matrix format: {label}")


def gf2_rank(matrix: DenseMatrix) -> int:
    rows = [row[:] for row in matrix if any(row)]
    if not rows:
        return 0

    rank = 0
    column_count = len(rows[0])
    for column in range(column_count):
        pivot_index = next(
            (index for index in range(rank, len(rows)) if rows[index][column] == 1),
            None,
        )
        if pivot_index is None:
            continue
        rows[rank], rows[pivot_index] = rows[pivot_index], rows[rank]
        for index in range(len(rows)):
            if index != rank and rows[index][column] == 1:
                rows[index] = [
                    left ^ right for left, right in zip(rows[index], rows[rank], strict=True)
                ]
        rank += 1
        if rank == len(rows):
            break
    return rank


def _validate_dense_rows(rows: DenseMatrix, *, num_cols: int, label: str) -> DenseMatrix:
    normalized: DenseMatrix = []
    for row in rows:
        if len(row) != num_cols:
            raise SearchIntegrityError(f"{label} row length mismatch")
        if any(not _is_plain_int(bit) or bit not in (0, 1) for bit in row):
            raise SearchIntegrityError(f"{label} contains non-binary entries")
        normalized.append([int(bit) for bit in row])
    return normalized


def _matrix_width_for_basis(
    kernel_rows: DenseMatrix,
    stabilizer_rows: DenseMatrix,
    preferred_vector: list[int],
) -> int:
    widths = [len(preferred_vector)]
    widths.extend(len(row) for row in kernel_rows)
    widths.extend(len(row) for row in stabilizer_rows)
    width = widths[0]
    if any(candidate != width for candidate in widths):
        raise SearchIntegrityError("logical observable basis width mismatch")
    return width


def gf2_nullspace(matrix: DenseMatrix, *, num_cols: int | None = None) -> DenseMatrix:
    if num_cols is None:
        if not matrix:
            raise SearchIntegrityError("num_cols is required for empty nullspace matrix")
        num_cols = len(matrix[0])
    if not _is_plain_int(num_cols) or num_cols < 0:
        raise SearchIntegrityError("num_cols must be a nonnegative integer")
    rows = _validate_dense_rows(matrix, num_cols=num_cols, label="nullspace matrix")
    rows = [row for row in rows if any(row)]
    pivot_columns: list[int] = []
    rank = 0
    for column in range(num_cols):
        pivot_index = next(
            (index for index in range(rank, len(rows)) if rows[index][column] == 1),
            None,
        )
        if pivot_index is None:
            continue
        rows[rank], rows[pivot_index] = rows[pivot_index], rows[rank]
        for index in range(len(rows)):
            if index != rank and rows[index][column] == 1:
                rows[index] = [
                    left ^ right
                    for left, right in zip(rows[index], rows[rank], strict=True)
                ]
        pivot_columns.append(column)
        rank += 1
        if rank == len(rows):
            break
    pivot_set = set(pivot_columns)
    basis: DenseMatrix = []
    for free_column in range(num_cols):
        if free_column in pivot_set:
            continue
        vector = [0] * num_cols
        vector[free_column] = 1
        for row_index, pivot_column in enumerate(pivot_columns):
            if rows[row_index][free_column] == 1:
                vector[pivot_column] = 1
        basis.append(vector)
    return basis


def complete_logical_observable_basis(
    *,
    kernel_rows: DenseMatrix,
    stabilizer_rows: DenseMatrix,
    preferred_vector: list[int],
) -> DenseMatrix:
    num_cols = _matrix_width_for_basis(kernel_rows, stabilizer_rows, preferred_vector)
    kernel = _validate_dense_rows(kernel_rows, num_cols=num_cols, label="kernel matrix")
    stabilizers = _validate_dense_rows(
        stabilizer_rows,
        num_cols=num_cols,
        label="stabilizer matrix",
    )
    preferred = _validate_witness_vector(preferred_vector)
    if preferred is None or len(preferred) != num_cols:
        raise SearchIntegrityError("preferred logical vector must be binary")
    logical_count = num_cols - gf2_rank(kernel) - gf2_rank(stabilizers)
    if logical_count <= 0:
        raise SearchIntegrityError("logical observable basis has no logical dimension")
    if not gf2_vector_in_kernel(kernel, preferred):
        raise SearchIntegrityError("preferred logical vector is not in kernel")
    if gf2_vector_in_row_space(stabilizers, preferred):
        raise SearchIntegrityError("preferred logical vector is in stabilizer row space")

    selected: DenseMatrix = [preferred]
    current_rank = gf2_rank([*stabilizers, *selected])
    for candidate in gf2_nullspace(kernel, num_cols=num_cols):
        if len(selected) == logical_count:
            break
        next_rank = gf2_rank([*stabilizers, *selected, candidate])
        if next_rank > current_rank:
            selected.append(candidate)
            current_rank = next_rank
    if len(selected) != logical_count:
        raise SearchIntegrityError(
            "could not complete logical observable basis to expected dimension"
        )
    return selected


def _fail(reason: str) -> dict[str, str]:
    return {"status": "fail", "reason": reason}


def _validate_witness_vector(value: object) -> list[int] | None:
    if not isinstance(value, list):
        return None
    if any(not _is_plain_int(bit) or bit not in (0, 1) for bit in value):
        return None
    return [int(bit) for bit in value]


def gf2_vector_in_row_space(rows: DenseMatrix, vector: list[int]) -> bool:
    return gf2_rank(rows) == gf2_rank([*rows, vector])


def gf2_vector_in_kernel(rows: DenseMatrix, vector: list[int]) -> bool:
    for row in rows:
        overlap = sum(
            left & right for left, right in zip(row, vector, strict=True)
        )
        if overlap % 2:
            return False
    return True


def verify_css_upper_bound_witness(
    hx_payload: dict, hz_payload: dict, witness_payload: dict
) -> dict:
    hx = matrix_data(hx_payload, "hx.json")
    hz = matrix_data(hz_payload, "hz.json")

    basis = witness_payload.get("basis") if isinstance(witness_payload, dict) else None
    if basis not in {"x", "z"}:
        return _fail("invalid_basis")

    vector = (
        _validate_witness_vector(witness_payload.get("vector"))
        if isinstance(witness_payload, dict)
        else None
    )
    if vector is None:
        return _fail("non_binary_vector")

    n_cols = _matrix_num_cols(hx_payload, hx, "hx.json")
    if n_cols != _matrix_num_cols(hz_payload, hz, "hz.json") or len(vector) != n_cols:
        return _fail("length_mismatch")

    kernel_rows = hz if basis == "x" else hx
    stabilizer_rows = hx if basis == "x" else hz
    if not gf2_vector_in_kernel(kernel_rows, vector):
        return _fail("not_in_kernel")
    if gf2_vector_in_row_space(stabilizer_rows, vector):
        return _fail("in_stabilizer_row_space")

    weight = sum(vector)
    return {
        "status": "pass",
        "basis": basis,
        "weight": weight,
        "distance_payload": {
            "status": "completed",
            "method": "css-upper-bound-witness",
            "bound_type": "upper",
            "upper_bound": weight,
            "basis": basis,
        },
    }


def commutation_failures(hx: DenseMatrix, hz: DenseMatrix) -> list[dict[str, int]]:
    failures: list[dict[str, int]] = []
    for hx_index, hx_row in enumerate(hx):
        for hz_index, hz_row in enumerate(hz):
            overlap = sum(left & right for left, right in zip(hx_row, hz_row, strict=True))
            if overlap % 2:
                failures.append({"hx_row": hx_index, "hz_row": hz_index})
    return failures


def summarize_css_structure(hx_payload: dict, hz_payload: dict) -> dict:
    hx = matrix_data(hx_payload, "hx.json")
    hz = matrix_data(hz_payload, "hz.json")
    hx_num_cols = _matrix_num_cols(hx_payload, hx, "hx.json")
    hz_num_cols = _matrix_num_cols(hz_payload, hz, "hz.json")
    if hx_num_cols != hz_num_cols:
        raise SearchIntegrityError("matrix column mismatch: hx.json vs hz.json")

    rank_hx = gf2_rank(hx)
    rank_hz = gf2_rank(hz)
    failures = commutation_failures(hx, hz)
    n = hx_num_cols
    summary = {
        "status": "completed" if not failures else "failed",
        "n": n,
        "k": n - rank_hx - rank_hz,
        "rank_hx": rank_hx,
        "rank_hz": rank_hz,
        "mx": _matrix_num_rows(hx_payload, hx, "hx.json"),
        "mz": _matrix_num_rows(hz_payload, hz, "hz.json"),
        "css_commute": not failures,
        "commutation_failures": failures,
    }
    return summary
