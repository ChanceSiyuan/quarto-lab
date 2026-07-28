from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


VALIDATOR_VERSION = "quantum-tanner-proposal-validator-v1"


class QuantumTannerProposalValidationError(ValueError):
    kind = "QuantumTannerProposalValidationError"

    def __init__(self, message: str):
        super().__init__(f"{self.kind}: {message}")
        self.message = message


class GroupOrderLimitExceeded(QuantumTannerProposalValidationError):
    kind = "GroupOrderLimitExceeded"


class InvalidGroupTable(QuantumTannerProposalValidationError):
    kind = "InvalidGroupTable"


class NonSymmetricGeneratorSet(QuantumTannerProposalValidationError):
    kind = "NonSymmetricGeneratorSet"


class NonBipartiteCayleyGraph(QuantumTannerProposalValidationError):
    kind = "NonBipartiteCayleyGraph"


class KnownToricTemplateDuplicate(QuantumTannerProposalValidationError):
    kind = "KnownToricTemplateDuplicate"


class InvalidLocalCodeMatrix(QuantumTannerProposalValidationError):
    kind = "InvalidLocalCodeMatrix"


class LocalCodeWidthMismatch(QuantumTannerProposalValidationError):
    kind = "LocalCodeWidthMismatch"


class DegenerateQuantumTannerFace(QuantumTannerProposalValidationError):
    kind = "DegenerateQuantumTannerFace"


@dataclass(frozen=True)
class QuantumTannerProposalSummary:
    proposal_id: str
    group_order: int
    a_generator_count: int
    b_generator_count: int
    h_a_dimensions: tuple[int, int]
    h_b_dimensions: tuple[int, int]
    validator_version: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["h_a_dimensions"] = list(self.h_a_dimensions)
        payload["h_b_dimensions"] = list(self.h_b_dimensions)
        return payload


def validate_quantum_tanner_proposal_file(
    path: Path,
    *,
    max_group_order: int = 32,
) -> QuantumTannerProposalSummary:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise InvalidGroupTable("proposal payload must be a JSON object")
    return validate_quantum_tanner_proposal(payload, max_group_order=max_group_order)


def validate_quantum_tanner_proposal(
    payload: dict[str, Any],
    *,
    max_group_order: int = 32,
) -> QuantumTannerProposalSummary:
    table = _validate_group_table(payload, max_group_order=max_group_order)
    _validate_associativity(table)
    group = payload["base_group"]
    identity = int(group["identity"])
    inverses = _inverse_map(table, identity)
    a_generators = _validate_generator_set(
        payload,
        key="a_generator_indices",
        order=len(table),
        inverses=inverses,
    )
    b_generators = _validate_generator_set(
        payload,
        key="b_generator_indices",
        order=len(table),
        inverses=inverses,
    )
    h_a = _validate_binary_matrix(payload, key="h_a")
    h_b = _validate_binary_matrix(payload, key="h_b")
    if len(h_a[0]) != len(a_generators):
        raise LocalCodeWidthMismatch(
            f"h_a width {len(h_a[0])} does not match |A| {len(a_generators)}"
        )
    if len(h_b[0]) != len(b_generators):
        raise LocalCodeWidthMismatch(
            f"h_b width {len(h_b[0])} does not match |B| {len(b_generators)}"
        )
    _validate_non_degenerate_faces(table, a_generators, b_generators)
    _validate_bipartite_cayley_graph(table, a_generators, b_generators)
    if _is_known_toric_template_duplicate(
        payload=payload,
        a_generators=a_generators,
        b_generators=b_generators,
        h_a=h_a,
        h_b=h_b,
    ):
        raise KnownToricTemplateDuplicate(
            "proposal matches the committed Zm x Zm toric Tanner template"
        )
    canonical = {
        "proposal_id": payload["proposal_id"],
        "schema_version": payload["schema_version"],
        "construction_mode": payload["construction_mode"],
        "base_group": {
            "name": group["name"],
            "element_order": group["element_order"],
            "order": len(table),
            "identity": identity,
            "multiplication_table": table,
        },
        "a_generator_indices": list(a_generators),
        "b_generator_indices": list(b_generators),
        "local_codes": {
            "matrix_role": payload["local_codes"]["matrix_role"],
            "field": payload["local_codes"]["field"],
            "h_a": [list(row) for row in h_a],
            "h_b": [list(row) for row in h_b],
        },
    }
    return QuantumTannerProposalSummary(
        proposal_id=str(payload["proposal_id"]),
        group_order=len(table),
        a_generator_count=len(a_generators),
        b_generator_count=len(b_generators),
        h_a_dimensions=(len(h_a), len(h_a[0])),
        h_b_dimensions=(len(h_b), len(h_b[0])),
        validator_version=VALIDATOR_VERSION,
        fingerprint=_fingerprint(canonical),
    )


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _fingerprint(canonical_payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(canonical_payload).encode("utf-8")).hexdigest()


def _is_known_toric_template_duplicate(
    *,
    payload: dict[str, Any],
    a_generators: tuple[int, ...],
    b_generators: tuple[int, ...],
    h_a: tuple[tuple[int, ...], ...],
    h_b: tuple[tuple[int, ...], ...],
) -> bool:
    group = payload["base_group"]
    order = int(group["order"])
    root = int(order**0.5)
    if root * root != order or root < 2:
        return False
    if group.get("identity") != 0:
        return False
    a_generator_set = set(a_generators)
    b_generator_set = set(b_generators)
    x_generator_set = {root, root * (root - 1)}
    y_generator_set = {1, root - 1}
    if not (
        (a_generator_set == x_generator_set and b_generator_set == y_generator_set)
        or (a_generator_set == y_generator_set and b_generator_set == x_generator_set)
    ):
        return False
    if h_a != ((1, 1),) or h_b != ((1, 1),):
        return False
    table = group["multiplication_table"]
    for left in range(order):
        lx, ly = divmod(left, root)
        for right in range(order):
            rx, ry = divmod(right, root)
            expected = root * ((lx + rx) % root) + ((ly + ry) % root)
            if table[left][right] != expected:
                return False
    return True


def _inverse_map(table: list[list[int]], identity: int) -> dict[int, int]:
    inverses: dict[int, int] = {}
    for element in range(len(table)):
        for candidate in range(len(table)):
            if table[element][candidate] == identity and table[candidate][element] == identity:
                inverses[element] = candidate
                break
        if element not in inverses:
            raise InvalidGroupTable(f"element {element} does not have a two-sided inverse")
    return inverses


def _validate_generator_set(
    payload: dict[str, Any],
    *,
    key: str,
    order: int,
    inverses: dict[int, int],
) -> tuple[int, ...]:
    raw = payload.get(key)
    if not isinstance(raw, list) or not raw:
        raise NonSymmetricGeneratorSet(f"{key} must be a nonempty list")
    seen: set[int] = set()
    generators: list[int] = []
    for index, value in enumerate(raw):
        if type(value) is not int or value < 0 or value >= order:
            raise NonSymmetricGeneratorSet(f"{key}[{index}] is out of range")
        if value in seen:
            raise NonSymmetricGeneratorSet(f"{key} contains duplicate generator {value}")
        seen.add(value)
        generators.append(value)
    missing = sorted(inverses[value] for value in generators if inverses[value] not in seen)
    if missing:
        raise NonSymmetricGeneratorSet(
            f"{key} is not closed under inverses: missing {missing}"
        )
    return tuple(generators)


def _validate_bipartite_cayley_graph(
    table: list[list[int]],
    a_generators: tuple[int, ...],
    b_generators: tuple[int, ...],
) -> None:
    colors: list[int | None] = [None] * len(table)
    for start in range(len(table)):
        if colors[start] is not None:
            continue
        colors[start] = 0
        queue = [start]
        cursor = 0
        while cursor < len(queue):
            vertex = queue[cursor]
            cursor += 1
            color = colors[vertex]
            assert color is not None
            neighbors = [table[generator][vertex] for generator in a_generators]
            neighbors.extend(table[vertex][generator] for generator in b_generators)
            for neighbor in neighbors:
                neighbor_color = colors[neighbor]
                if neighbor_color == color:
                    raise NonBipartiteCayleyGraph(
                        "combined left-right Cayley graph is not bipartite: "
                        f"adjacent vertices {vertex} and {neighbor} have the same color"
                    )
                if neighbor_color is None:
                    colors[neighbor] = color ^ 1
                    queue.append(neighbor)


def _validate_binary_matrix(payload: dict[str, Any], *, key: str) -> tuple[tuple[int, ...], ...]:
    local_codes = payload.get("local_codes")
    if not isinstance(local_codes, dict):
        raise InvalidLocalCodeMatrix("local_codes must be an object")
    matrix = local_codes.get(key)
    if not isinstance(matrix, list) or not matrix:
        raise InvalidLocalCodeMatrix(f"{key} must be a nonempty matrix")
    width: int | None = None
    rows: list[tuple[int, ...]] = []
    for row_index, row in enumerate(matrix):
        if not isinstance(row, list) or not row:
            raise InvalidLocalCodeMatrix(f"{key} row {row_index} must be nonempty")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise InvalidLocalCodeMatrix(f"{key} rows must have equal width")
        normalized_row: list[int] = []
        for column_index, value in enumerate(row):
            if type(value) is not int or value not in (0, 1):
                raise InvalidLocalCodeMatrix(
                    f"{key}[{row_index}][{column_index}] must be 0 or 1"
                )
            normalized_row.append(int(value))
        rows.append(tuple(normalized_row))
    return tuple(rows)


def _validate_group_table(
    payload: dict[str, Any],
    *,
    max_group_order: int,
) -> list[list[int]]:
    group = payload.get("base_group")
    if not isinstance(group, dict):
        raise InvalidGroupTable("base_group must be an object")
    order = group.get("order")
    identity = group.get("identity")
    table = group.get("multiplication_table")
    if type(order) is not int or order <= 0:
        raise InvalidGroupTable("base_group.order must be a positive integer")
    if order > max_group_order:
        raise GroupOrderLimitExceeded(
            f"group order {order} exceeds max_group_order {max_group_order}"
        )
    if type(identity) is not int or identity < 0 or identity >= order:
        raise InvalidGroupTable("base_group.identity must be in range")
    if not isinstance(table, list) or len(table) != order:
        raise InvalidGroupTable("multiplication_table must have order rows")
    normalized: list[list[int]] = []
    for row_index, row in enumerate(table):
        if not isinstance(row, list) or len(row) != order:
            raise InvalidGroupTable(
                f"multiplication_table row {row_index} must have width {order}"
            )
        normalized_row: list[int] = []
        for column_index, value in enumerate(row):
            if type(value) is not int or value < 0 or value >= order:
                raise InvalidGroupTable(
                    f"multiplication_table[{row_index}][{column_index}] is out of range"
                )
            normalized_row.append(value)
        normalized.append(normalized_row)
    for element in range(order):
        if normalized[identity][element] != element or normalized[element][identity] != element:
            raise InvalidGroupTable("identity laws failed")
        has_left_inverse = any(
            normalized[candidate][element] == identity for candidate in range(order)
        )
        has_right_inverse = any(
            normalized[element][candidate] == identity for candidate in range(order)
        )
        if not has_left_inverse or not has_right_inverse:
            raise InvalidGroupTable(f"element {element} does not have two-sided inverses")
    return normalized


def _validate_associativity(table: list[list[int]]) -> None:
    order = len(table)
    for left in range(order):
        for middle in range(order):
            left_middle = table[left][middle]
            for right in range(order):
                if table[left_middle][right] != table[left][table[middle][right]]:
                    raise InvalidGroupTable(
                        f"associativity failed at ({left}, {middle}, {right})"
                    )


def _validate_non_degenerate_faces(
    table: list[list[int]],
    a_generators: tuple[int, ...],
    b_generators: tuple[int, ...],
) -> None:
    order = len(table)
    for root in range(order):
        for a_generator in a_generators:
            for b_generator in b_generators:
                a_root = table[a_generator][root]
                root_b = table[root][b_generator]
                a_root_b = table[a_root][b_generator]
                vertices = sorted((root, a_root, root_b, a_root_b))
                if any(left == right for left, right in zip(vertices, vertices[1:])):
                    raise DegenerateQuantumTannerFace(
                        "degenerate quantum Tanner face at "
                        f"root {root} with a={a_generator}, b={b_generator}: "
                        f"vertices {vertices}"
                    )
