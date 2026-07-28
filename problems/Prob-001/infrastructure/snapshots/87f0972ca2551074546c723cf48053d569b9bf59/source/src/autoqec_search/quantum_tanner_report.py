from __future__ import annotations

from collections import Counter
from html import escape as html_escape
import json
from pathlib import Path
import re
from typing import Any


DEFAULT_MAX_LOCAL_CODEWORDS = 1 << 20
DEFINITIONS_FILENAME = "construction-definitions.html"
QUANTUM_TANNER_FIXTURE_CATALOG = Path(
    "campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json"
)


def _binary_matrix(matrix: object) -> list[list[int]]:
    if not isinstance(matrix, list) or not matrix:
        raise ValueError("local parity-check matrix must be a nonempty matrix")
    if not isinstance(matrix[0], list) or not matrix[0]:
        raise ValueError("local parity-check matrix must have positive width")
    width = len(matrix[0])
    normalized: list[list[int]] = []
    for row in matrix:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError("local parity-check matrix rows must have equal width")
        if any(type(value) is not int or value not in {0, 1} for value in row):
            raise ValueError("local parity-check matrix entries must be binary")
        normalized.append(list(row))
    return normalized


def _rref_binary(matrix: list[list[int]]) -> tuple[list[list[int]], list[int]]:
    rows = [list(row) for row in matrix]
    width = len(rows[0])
    pivot_columns: list[int] = []
    pivot_row = 0
    for column in range(width):
        selected = next(
            (index for index in range(pivot_row, len(rows)) if rows[index][column]),
            None,
        )
        if selected is None:
            continue
        rows[pivot_row], rows[selected] = rows[selected], rows[pivot_row]
        for row_index, row in enumerate(rows):
            if row_index != pivot_row and row[column]:
                rows[row_index] = [
                    left ^ right for left, right in zip(row, rows[pivot_row])
                ]
        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == len(rows):
            break
    return rows[:pivot_row], pivot_columns


def _nullspace_basis(
    rref: list[list[int]], pivot_columns: list[int], width: int
) -> list[list[int]]:
    free_columns = [column for column in range(width) if column not in pivot_columns]
    basis: list[list[int]] = []
    for free_column in free_columns:
        vector = [0] * width
        vector[free_column] = 1
        for row_index, pivot_column in enumerate(pivot_columns):
            vector[pivot_column] = rref[row_index][free_column]
        basis.append(vector)
    return basis


def _weight_enumerator(
    basis: list[list[int]], *, max_codewords: int
) -> dict[int, int] | None:
    codeword_count = 1 << len(basis)
    if codeword_count > max_codewords:
        return None
    if not basis:
        return {}
    width = len(basis[0])
    counts: Counter[int] = Counter()
    for mask in range(1, codeword_count):
        vector = [0] * width
        for basis_index, basis_vector in enumerate(basis):
            if mask & (1 << basis_index):
                vector = [left ^ right for left, right in zip(vector, basis_vector)]
        counts[sum(vector)] += 1
    return dict(sorted(counts.items()))


def _local_code_name(
    *, n: int, k: int, d: int | None, weight_enumerator: dict[int, int] | None
) -> str:
    if (n, k, d, weight_enumerator) == (2, 1, 2, {2: 1}):
        return "Rep(2)"
    if (n, k, d, weight_enumerator) == (4, 2, 2, {2: 2, 4: 1}):
        return "Rep(2) direct sum Rep(2)"
    if (n, k, d, weight_enumerator) == (8, 4, 4, {4: 14, 8: 1}):
        return "Extended Hamming / RM(1,3)"
    return "Unnamed"


def describe_local_code(
    matrix: object,
    *,
    max_codewords: int = DEFAULT_MAX_LOCAL_CODEWORDS,
) -> dict[str, Any]:
    if type(max_codewords) is not int or max_codewords < 1:
        raise ValueError("max_codewords must be a positive integer")
    normalized = _binary_matrix(matrix)
    n = len(normalized[0])
    rref, pivot_columns = _rref_binary(normalized)
    k = n - len(pivot_columns)
    basis = _nullspace_basis(rref, pivot_columns, n)
    weight_enumerator = _weight_enumerator(basis, max_codewords=max_codewords)
    d = min(weight_enumerator) if weight_enumerator else None
    name = _local_code_name(
        n=n,
        k=k,
        d=d,
        weight_enumerator=weight_enumerator,
    )
    distance_text = str(d) if d is not None else "?"
    return {
        "d": d,
        "k": k,
        "label": f"{name} [{n},{k},{distance_text}]",
        "matrix": normalized,
        "n": n,
        "name": name,
        "weight_enumerator": weight_enumerator,
    }


def _catalog_entry(root: Path, candidate: dict[str, Any]) -> dict[str, Any] | None:
    provenance = candidate.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("kind") != "distance-ladder-fixture":
        return None
    candidate_id = candidate.get("candidate_id")
    catalog_path = root.resolve() / QUANTUM_TANNER_FIXTURE_CATALOG
    if not catalog_path.is_file():
        return None
    try:
        catalog = json.loads(catalog_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    entries = catalog.get("entries") if isinstance(catalog, dict) else None
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("candidate_id") != candidate_id:
            continue
        return entry
    return None


def _catalog_construction_spec_reference(
    root: Path, candidate: dict[str, Any]
) -> object:
    entry = _catalog_entry(root, candidate)
    if entry is None:
        return None
    provenance = entry.get("provenance")
    if isinstance(provenance, dict):
        return provenance.get("quantum_tanner_spec")
    return None


def _construction_spec_references(
    root: Path, candidate: dict[str, Any]
) -> list[object]:
    provenance = candidate.get("provenance")
    if isinstance(provenance, dict):
        proposal = provenance.get("proposal")
        if isinstance(proposal, dict) and proposal.get("qec_code_spec_path") is not None:
            return [proposal.get("qec_code_spec_path")]
    references: list[object] = []
    parameters = candidate.get("parameters")
    if isinstance(parameters, dict) and parameters.get("quantum_tanner_spec") is not None:
        references.append(parameters.get("quantum_tanner_spec"))
    catalog_reference = _catalog_construction_spec_reference(root, candidate)
    if catalog_reference is not None and catalog_reference not in references:
        references.append(catalog_reference)
    return references


def _safe_construction_path(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("candidate has no construction spec reference")
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or any(part == ".." for part in relative.parts):
        raise ValueError("construction spec reference must be a safe relative path")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("construction spec reference escapes repository root") from exc
    return resolved


def _required_mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"construction spec {label} must be an object")
    return value


def _required_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"construction spec {label} must be a nonempty string")
    return value


def _required_positive_int(value: object, *, label: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"construction spec {label} must be a positive integer")
    return value


def _generator_indices(value: object, *, label: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"construction spec {label} must be a nonempty list")
    if any(type(item) is not int or item < 0 for item in value):
        raise ValueError(f"construction spec {label} must contain nonnegative integers")
    return list(value)


def _css_dimensions_from_instance(path: Path) -> tuple[int, int] | None:
    instance_path = path.parent / "instance.json"
    if not instance_path.is_file():
        return None
    try:
        instance = json.loads(instance_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(instance, dict):
        return None
    n = instance.get("n")
    k = instance.get("k")
    if type(n) is int and n > 0 and type(k) is int and 0 <= k <= n:
        return n, k
    return None


def _css_dimensions_from_catalog(
    root: Path, candidate: dict[str, Any]
) -> tuple[int, int] | None:
    entry = _catalog_entry(root, candidate)
    if entry is None:
        return None
    n = entry.get("n")
    k = entry.get("k")
    if type(n) is int and n > 0 and type(k) is int and 0 <= k <= n:
        return n, k
    return None


def _parse_construction(
    root: Path,
    candidate: dict[str, Any],
    *,
    reference: object,
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid construction spec: {reference}") from exc
    spec = _required_mapping(payload, label="root")
    base_group = _required_mapping(spec.get("base_group"), label="base_group")
    local_codes = _required_mapping(spec.get("local_codes"), label="local_codes")
    if local_codes.get("field") != "GF(2)":
        raise ValueError("construction spec local_codes.field must be GF(2)")
    if local_codes.get("matrix_role") != "parity_check":
        raise ValueError(
            "construction spec local_codes.matrix_role must be parity_check"
        )
    group_name = _required_string(base_group.get("name"), label="base_group.name")
    group_order = _required_positive_int(
        base_group.get("order"), label="base_group.order"
    )
    element_order = _required_string(
        base_group.get("element_order"), label="base_group.element_order"
    )
    generators_a = _generator_indices(
        spec.get("a_generator_indices"), label="a_generator_indices"
    )
    generators_b = _generator_indices(
        spec.get("b_generator_indices"), label="b_generator_indices"
    )
    if any(index >= group_order for index in (*generators_a, *generators_b)):
        raise ValueError("construction spec generator index is outside base-group order")
    code_a = describe_local_code(local_codes.get("h_a"))
    code_b = describe_local_code(local_codes.get("h_b"))
    if code_a["n"] != len(generators_a) or code_b["n"] != len(generators_b):
        raise ValueError("construction spec local-code width must match generator count")
    dimensions = _css_dimensions_from_instance(path) or _css_dimensions_from_catalog(
        root, candidate
    )
    return {
        "available": True,
        "construction_mode": spec.get("construction_mode"),
        "css_k": dimensions[1] if dimensions is not None else None,
        "css_n": dimensions[0] if dimensions is not None else None,
        "element_order": element_order,
        "generator_indices_a": generators_a,
        "generator_indices_b": generators_b,
        "group_name": group_name,
        "group_order": group_order,
        "local_code_a": code_a,
        "local_code_b": code_b,
        "source_path": str(reference),
    }


def _unavailable_construction(reference: object, error: str) -> dict[str, Any]:
    return {
        "available": False,
        "error": error,
        "source_path": str(reference) if reference is not None else None,
    }


def _load_construction(root: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    references = _construction_spec_references(root, candidate)
    if not references:
        return _unavailable_construction(
            None, "candidate has no construction spec reference"
        )
    missing_errors: list[str] = []
    for reference in references:
        try:
            path = _safe_construction_path(root, reference)
        except ValueError as exc:
            return _unavailable_construction(reference, str(exc))
        if not path.is_file():
            missing_errors.append(f"missing construction spec: {reference}")
            continue
        try:
            return _parse_construction(
                root,
                candidate,
                reference=reference,
                path=path,
            )
        except (OSError, ValueError) as exc:
            return _unavailable_construction(reference, str(exc))
    return _unavailable_construction(references[-1], "; ".join(missing_errors))


def _frontier_candidate_ids(model: dict[str, Any]) -> set[str]:
    frontier = model.get("frontier")
    if not isinstance(frontier, list):
        return set()
    return {
        str(item["candidate_id"])
        for item in frontier
        if isinstance(item, dict) and isinstance(item.get("candidate_id"), str)
    }


def _point_by_candidate(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    points = model.get("points")
    if not isinstance(points, list):
        return {}
    selected: dict[str, dict[str, Any]] = {}
    for point in points:
        if not isinstance(point, dict) or not isinstance(point.get("candidate_id"), str):
            continue
        selected.setdefault(point["candidate_id"], point)
    return selected


def _finite_code_label(candidate_id: str, construction: dict[str, Any]) -> str:
    group_name = construction.get("group_name")
    if isinstance(group_name, str) and re.fullmatch(r"D_\d+", group_name):
        return group_name.replace("_", "")
    return candidate_id


def _local_code_label(construction: dict[str, Any]) -> str:
    if not construction.get("available"):
        return "Construction metadata unavailable"
    code_a = construction["local_code_a"]
    code_b = construction["local_code_b"]
    if code_a["matrix"] == code_b["matrix"]:
        return str(code_a["label"])
    return f"A: {code_a['label']}; B: {code_b['label']}"


def _screening_status(candidate: dict[str, Any]) -> str:
    screening = candidate.get("screening")
    if isinstance(screening, dict) and isinstance(
        screening.get("screening_status"), str
    ):
        return screening["screening_status"]
    status = candidate.get("status")
    return str(status) if isinstance(status, str) else "unknown"


def _upper_bound(candidate: dict[str, Any]) -> int | None:
    value = candidate.get("upper_bound")
    if type(value) is int and value > 0:
        return value
    screening = candidate.get("screening")
    if isinstance(screening, dict):
        value = screening.get("distance_upper_bound")
        if type(value) is int and value > 0:
            return value
    return None


def _candidate_row(
    root: Path,
    candidate: dict[str, Any],
    *,
    point: dict[str, Any] | None,
    frontier_ids: set[str],
    definition_index: int,
) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidate_id", ""))
    construction = _load_construction(root, candidate)
    n = candidate.get("n")
    k = candidate.get("k")
    if type(n) is not int and type(construction.get("css_n")) is int:
        n = construction["css_n"]
    if type(k) is not int and type(construction.get("css_k")) is int:
        k = construction["css_k"]
    rate = (
        float(k) / float(n)
        if type(n) is int and n > 0 and type(k) is int and k >= 0
        else None
    )
    if construction.get("available"):
        base_group_label = (
            f"{construction['group_name']} (order {construction['group_order']})"
        )
        generator_label = (
            f"A: {construction['generator_indices_a']}; "
            f"B: {construction['generator_indices_b']}"
        )
    else:
        base_group_label = "Construction metadata unavailable"
        generator_label = "Unavailable"
    return {
        "base_group_label": base_group_label,
        "candidate_id": candidate_id,
        "construction": construction,
        "css_label": f"[[{n},{k}]]" if type(n) is int and type(k) is int else "—",
        "definition_anchor": f"candidate-{definition_index}",
        "finite_code_label": _finite_code_label(candidate_id, construction),
        "frontier": candidate_id in frontier_ids,
        "generator_label": generator_label,
        "k": k,
        "ler": point.get("ler") if point is not None else None,
        "local_code_label": _local_code_label(construction),
        "n": n,
        "point": point,
        "rate": rate,
        "screening": candidate.get("screening"),
        "screening_status": _screening_status(candidate),
        "upper_bound": _upper_bound(candidate),
    }


def build_quantum_tanner_view_model(
    root: Path, model: dict[str, Any]
) -> dict[str, Any]:
    candidates = model.get("candidates")
    if not isinstance(candidates, list):
        candidates = []
    points = _point_by_candidate(model)
    frontier_ids = _frontier_candidate_ids(model)
    attempted_candidates = [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict)
        and (
            points.get(str(candidate.get("candidate_id", ""))) is not None
            or isinstance(candidate.get("screening"), dict)
            or candidate.get("status") not in {None, "placeholder"}
        )
    ]
    rows = [
        _candidate_row(
            root,
            candidate,
            point=points.get(str(candidate.get("candidate_id", ""))),
            frontier_ids=frontier_ids,
            definition_index=index,
        )
        for index, candidate in enumerate(attempted_candidates, start=1)
    ]
    return {
        "counts": {
            "processed": len(rows),
            "evaluated": sum(row["point"] is not None for row in rows),
            "skipped": sum(row["screening_status"] == "skipped" for row in rows),
            "frontier": sum(row["frontier"] for row in rows),
        },
        "provenance": model.get("provenance", {}),
        "rows": rows,
    }


def _display(value: object) -> str:
    return html_escape("" if value is None else str(value), quote=True)


def _format_percent(value: object, *, digits: int = 3) -> str:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return "—"
    return f"{100.0 * float(value):.{digits}f}%"


def _format_seconds(value: object) -> str:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return "—"
    return f"{float(value):.3f} s"


def _point_cells(point: dict[str, Any] | None) -> tuple[str, str, str, str]:
    if point is None:
        return "rsinter not run", "—", "—", "—"
    errors = point.get("errors")
    shots = point.get("shots")
    errors_shots = (
        f"{errors} / {shots}"
        if type(errors) is int and type(shots) is int
        else "—"
    )
    ci_low = point.get("ci_low")
    ci_high = point.get("ci_high")
    confidence_interval = (
        f"{_format_percent(ci_low)}–{_format_percent(ci_high)}"
        if isinstance(ci_low, int | float)
        and not isinstance(ci_low, bool)
        and isinstance(ci_high, int | float)
        and not isinstance(ci_high, bool)
        else "—"
    )
    return (
        errors_shots,
        _format_percent(point.get("ler")),
        confidence_interval,
        _format_seconds(point.get("seconds")),
    )


def _report_row_html(row: dict[str, Any]) -> str:
    errors_shots, ler, confidence_interval, seconds = _point_cells(row["point"])
    upper_bound = (
        f"≤ {row['upper_bound']}" if type(row.get("upper_bound")) is int else "—"
    )
    badge_class = (
        "admitted" if row["screening_status"] == "admitted" else "skipped"
    )
    definition_href = f"{DEFINITIONS_FILENAME}#{row['definition_anchor']}"
    return f"""
        <tr data-candidate-row="true">
          <td><strong>{_display(row['finite_code_label'])}</strong><span class="candidate-id">{_display(row['candidate_id'])}</span></td>
          <td><a href="{_display(definition_href)}">{_display(row['base_group_label'])}</a></td>
          <td class="compact code">{_display(row['generator_label'])}</td>
          <td><a href="{_display(definition_href)}">{_display(row['local_code_label'])}</a></td>
          <td class="code">{_display(row['css_label'])}</td>
          <td class="num">{_format_percent(row['rate'], digits=2)}</td>
          <td class="num">{_display(upper_bound)}</td>
          <td><span class="badge {badge_class}">{_display(row['screening_status'])}</span></td>
          <td class="num">{_display(errors_shots)}</td>
          <td class="num strong">{_display(ler)}</td>
          <td class="num">{_display(confidence_interval)}</td>
          <td class="num">{_display(seconds)}</td>
        </tr>"""


def _unique_point_values(rows: list[dict[str, Any]], key: str) -> list[Any]:
    values: list[Any] = []
    for row in rows:
        point = row.get("point")
        if not isinstance(point, dict):
            continue
        value = point.get(key)
        if value not in values:
            values.append(value)
    return values


def _configuration_html(view_model: dict[str, Any]) -> str:
    rows = view_model["rows"]
    provenance = view_model.get("provenance", {})
    if not isinstance(provenance, dict):
        provenance = {}
    p_values = _unique_point_values(rows, "p")
    rounds = _unique_point_values(rows, "rounds")
    decoders = _unique_point_values(rows, "decoder_id")
    shots = _unique_point_values(rows, "shots")

    def joined(values: list[Any]) -> str:
        return ", ".join(str(value) for value in values) if values else "unavailable"

    return f"""
    <div><span class="key">Physical error rate</span><span class="code">{_display(joined(p_values))}</span></div>
    <div><span class="key">Memory rounds</span><span>{_display(joined(rounds))}</span></div>
    <div><span class="key">Decoder</span><span class="code">{_display(joined(decoders))}</span></div>
    <div><span class="key">Shots per completed point</span><span>{_display(joined(shots))}</span></div>
    <div><span class="key">Seed</span><span class="code">{_display(provenance.get('seed', 'unavailable'))}</span></div>
    <div><span class="key">Construction</span><span class="code">lr_cayley_no_cover_v1</span></div>
    <div><span class="key">Distance evidence</span><span>random-window upper bound</span></div>
    <div><span class="key">Aggregation</span><span>any logical error per shot</span></div>"""


def _interpretation_items(view_model: dict[str, Any]) -> str:
    rows = view_model["rows"]
    items: list[str] = []
    for row in rows:
        if row["screening_status"] != "skipped":
            continue
        screening = row.get("screening")
        reason = screening.get("reason") if isinstance(screening, dict) else "unknown"
        items.append(
            f"<li>{_display(row['finite_code_label'])} did not run rsinter because "
            f"its screening status was <span class=\"code\">{_display(reason)}</span>.</li>"
        )
    zero_error_rows = [
        row
        for row in rows
        if isinstance(row.get("point"), dict) and row["point"].get("errors") == 0
    ]
    if zero_error_rows:
        labels = ", ".join(_display(row["finite_code_label"]) for row in zero_error_rows)
        items.append(
            f"<li>{labels} had zero observed errors, but the confidence interval "
            "still permits a nonzero logical error rate.</li>"
        )
    frontier_labels = [
        _display(row["finite_code_label"]) for row in rows if row.get("frontier")
    ]
    if frontier_labels:
        items.append(f"<li>The final frontier contains {', '.join(frontier_labels)}.</li>")
    return "".join(items) or "<li>No interpretation notes are available.</li>"


def render_quantum_tanner_report_html(
    view_model: dict[str, Any],
    *,
    ler_svg: str,
    report_json: str,
) -> str:
    provenance = view_model.get("provenance", {})
    if not isinstance(provenance, dict):
        provenance = {}
    counts = view_model["counts"]
    table_rows = "".join(_report_row_html(row) for row in view_model["rows"])
    ler_section = (
        f'<h2>Logical Error Rate Plot</h2><section class="panel plot">{ler_svg}</section>'
        if ler_svg
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quantum Tanner Benchmark Summary</title>
  <style>
    :root {{ color-scheme: light dark; --bg:#f6f7fb; --panel:#fff; --text:#19202a; --muted:#667085; --line:#e4e7ec; --accent:#3b5ccc; --good-bg:#e9f8ef; --good-text:#137a3d; --skip-bg:#fff4df; --skip-text:#9a5b00; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --bg:#11141a; --panel:#1a1f28; --text:#edf0f5; --muted:#aab2c0; --line:#303746; --accent:#91a7ff; --good-bg:#163624; --good-text:#8ce3ae; --skip-bg:#3c2c13; --skip-text:#ffc66d; }} }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ max-width:1480px; margin:0 auto; padding:40px 24px 64px; }}
    h1 {{ margin:0 0 6px; font-size:30px; letter-spacing:-.02em; }}
    h2 {{ margin:30px 0 12px; font-size:20px; }}
    .subtitle,.footnote {{ color:var(--muted); }}
    .subtitle {{ margin-bottom:24px; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
    .card,.panel {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; box-shadow:0 1px 2px rgba(16,24,40,.04); }}
    .card {{ padding:16px; }} .card .value {{ font-size:25px; font-weight:700; }} .card .label {{ color:var(--muted); }}
    .panel {{ overflow:hidden; }} .table-wrap {{ overflow-x:auto; }}
    table {{ width:100%; border-collapse:collapse; white-space:nowrap; }}
    th,td {{ padding:13px 14px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; }}
    th {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    tbody tr:last-child td {{ border-bottom:0; }}
    .master-table th:first-child,.master-table td:first-child {{ position:sticky; left:0; z-index:1; background:var(--panel); }}
    .master-table th:first-child {{ z-index:2; }}
    .num {{ font-variant-numeric:tabular-nums; }} .code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .candidate-id {{ display:block; margin-top:2px; color:var(--muted); font:11px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .compact {{ line-height:1.35; max-width:250px; white-space:normal; }}
    .badge {{ display:inline-block; border-radius:999px; padding:3px 9px; font-size:12px; font-weight:650; }}
    .admitted {{ background:var(--good-bg); color:var(--good-text); }} .skipped {{ background:var(--skip-bg); color:var(--skip-text); }}
    .strong {{ font-weight:700; color:var(--accent); }}
    a {{ color:var(--accent); text-decoration-thickness:1px; text-underline-offset:2px; }}
    .notes {{ padding:18px 22px; }} .notes ul {{ margin:8px 0; padding-left:20px; }}
    .config {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); }}
    .config div {{ padding:14px 16px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); }}
    .config div:nth-child(4n) {{ border-right:0; }} .config div:nth-last-child(-n+4) {{ border-bottom:0; }}
    .config span {{ display:block; }} .config .key {{ color:var(--muted); font-size:12px; }}
    .plot {{ padding:12px; }} .plot svg {{ display:block; width:100%; height:auto; background:var(--panel); }}
    pre {{ overflow:auto; max-height:360px; padding:14px; background:#111827; color:#f9fafb; font-size:12px; line-height:1.45; }}
    @media (max-width:850px) {{ .cards,.config {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .config div:nth-child(4n) {{ border-right:1px solid var(--line); }} .config div:nth-child(2n) {{ border-right:0; }} }}
  </style>
</head>
<body>
<main>
  <h1>Quantum Tanner Benchmark Summary</h1>
  <div class="subtitle">Run <span class="code">{_display(provenance.get('run_id'))}</span> · {_display(provenance.get('mode'))} · generated {_display(provenance.get('generated_at'))}</div>
  <section class="cards" aria-label="Run summary">
    <div class="card"><div class="value">{counts['processed']}</div><div class="label">Candidates processed</div></div>
    <div class="card"><div class="value">{counts['evaluated']}</div><div class="label">Evaluated by rsinter</div></div>
    <div class="card"><div class="value">{counts['skipped']}</div><div class="label">Skipped normally</div></div>
    <div class="card"><div class="value">{counts['frontier']}</div><div class="label">Frontier candidates</div></div>
  </section>

  <h2>Master Results Table <small style="color:var(--muted);font-weight:400">· one finite code per row</small></h2>
  <p class="footnote">Select a base group or local classical code to view its complete construction definition.</p>
  <section class="panel table-wrap">
    <table class="master-table">
      <thead><tr><th>Finite code / candidate</th><th>Base group</th><th>A / B generators</th><th>Local classical code</th><th>CSS parameters</th><th>Code rate</th><th>X upper bound</th><th>Screening</th><th>errors / shots</th><th>LER</th><th>95% CI</th><th>Decoding time</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>

  <h2>How to Read This Table</h2>
  <section class="panel notes"><ul>{_interpretation_items(view_model)}</ul></section>

  <h2>Benchmark Configuration</h2>
  <section class="panel config">{_configuration_html(view_model)}</section>

  {ler_section}

  <h2>Scientific Interpretation</h2>
  <section class="panel notes"><p>Each X upper bound is screening evidence from a randomized search, not an exact code distance. LER is the shot-level any-logical result from the recorded memory experiment.</p><p><a href="{DEFINITIONS_FILENAME}">View group presentations, generator indices, and parity-check matrices for all candidates →</a></p></section>

  <details><summary>Embedded report data</summary><script type="application/json" id="autoqec-report-data">{report_json}</script><pre>{html_escape(report_json)}</pre></details>
</main>
</body>
</html>
"""


def _matrix_text(matrix: list[list[int]]) -> str:
    return "\n".join("[" + " ".join(str(value) for value in row) + "]" for row in matrix)


def _enumerator_text(value: object) -> str:
    if not isinstance(value, dict):
        return "not enumerated"
    return "{" + ", ".join(f"{weight}: {count}" for weight, count in value.items()) + "}"


def _definition_section(row: dict[str, Any]) -> str:
    construction = row["construction"]
    if not construction.get("available"):
        return f"""
  <section class="candidate-definition" id="{_display(row['definition_anchor'])}">
    <h2>{_display(row['finite_code_label'])} · {_display(row['css_label'])}</h2>
    <div class="candidate-id">{_display(row['candidate_id'])}</div>
    <p class="warning">Construction metadata unavailable: {_display(construction.get('error'))}</p>
    <p>Recorded source: <code>{_display(construction.get('source_path'))}</code></p>
  </section>"""
    code_a = construction["local_code_a"]
    code_b = construction["local_code_b"]
    return f"""
  <section class="candidate-definition" id="{_display(row['definition_anchor'])}">
    <h2>{_display(row['finite_code_label'])} · {_display(row['css_label'])}</h2>
    <div class="candidate-id">{_display(row['candidate_id'])}</div>
    <div class="facts">
      <div class="key">Base group</div><div><code>{_display(construction['group_name'])}</code>, order {_display(construction['group_order'])}</div>
      <div class="key">Element indexing</div><div><code>{_display(construction['element_order'])}</code></div>
      <div class="key">Generator set A</div><div><code>{_display(construction['generator_indices_a'])}</code></div>
      <div class="key">Generator set B</div><div><code>{_display(construction['generator_indices_b'])}</code></div>
      <div class="key">Local code A</div><div>{_display(code_a['label'])}; weight enumerator <code>{_display(_enumerator_text(code_a['weight_enumerator']))}</code></div>
      <div class="key">Local code B</div><div>{_display(code_b['label'])}; weight enumerator <code>{_display(_enumerator_text(code_b['weight_enumerator']))}</code></div>
      <div class="key">Construction mode</div><div><code>{_display(construction.get('construction_mode'))}</code></div>
      <div class="key">Definition source</div><div><code>{_display(construction.get('source_path'))}</code></div>
    </div>
    <h3>H_A</h3><pre>{_display(_matrix_text(code_a['matrix']))}</pre>
    <h3>H_B</h3><pre>{_display(_matrix_text(code_b['matrix']))}</pre>
  </section>"""


def render_quantum_tanner_definitions_html(
    view_model: dict[str, Any],
    *,
    report_filename: str = "report.html",
) -> str:
    provenance = view_model.get("provenance", {})
    if not isinstance(provenance, dict):
        provenance = {}
    sections = "".join(_definition_section(row) for row in view_model["rows"])
    navigation = "".join(
        f'<a href="#{_display(row["definition_anchor"])}">{_display(row["finite_code_label"])}</a>'
        for row in view_model["rows"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quantum Tanner Candidate Construction Definitions</title>
  <style>
    :root {{ color-scheme:light dark; --bg:#f6f7fb; --panel:#fff; --text:#19202a; --muted:#667085; --line:#e4e7ec; --accent:#3b5ccc; --soft:#f1f3f9; --warn:#9a5b00; }}
    @media (prefers-color-scheme:dark) {{ :root {{ --bg:#11141a; --panel:#1a1f28; --text:#edf0f5; --muted:#aab2c0; --line:#303746; --accent:#91a7ff; --soft:#222936; --warn:#ffc66d; }} }}
    * {{ box-sizing:border-box; }} html {{ scroll-behavior:smooth; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ max-width:1000px; margin:0 auto; padding:40px 24px 72px; }}
    h1 {{ margin:0 0 6px; font-size:30px; }} h2 {{ margin:0 0 4px; font-size:22px; }} h3 {{ margin:18px 0 6px; }}
    a {{ color:var(--accent); text-decoration-thickness:1px; text-underline-offset:2px; }} .subtitle,.candidate-id {{ color:var(--muted); }}
    .intro,.candidate-definition {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; }}
    .intro {{ margin:24px 0; padding:18px 22px; }} .candidate-definition {{ margin-top:18px; padding:22px; scroll-margin-top:16px; }}
    .candidate-definition:target {{ outline:3px solid var(--accent); }}
    .candidate-id {{ font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .facts {{ display:grid; grid-template-columns:170px minmax(0,1fr); margin-top:14px; border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
    .facts div {{ padding:10px 12px; border-bottom:1px solid var(--line); }} .facts div:nth-last-child(-n+2) {{ border-bottom:0; }}
    .facts .key {{ color:var(--muted); background:var(--soft); font-size:13px; }}
    code,pre {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }} pre {{ margin:0; padding:14px 16px; overflow-x:auto; background:var(--soft); border:1px solid var(--line); border-radius:8px; line-height:1.5; }}
    nav {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:18px; }} nav a {{ padding:5px 10px; border:1px solid var(--line); border-radius:999px; text-decoration:none; }}
    .warning {{ color:var(--warn); font-weight:650; }}
    @media (max-width:620px) {{ .facts {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
<main>
  <h1>Quantum Tanner Candidate Construction Definitions</h1>
  <p class="subtitle">Run <code>{_display(provenance.get('run_id'))}</code> · traceable definitions generated with the main report</p>
  <p><a href="{_display(report_filename)}">← Return to the benchmark master table</a></p>
  <section class="intro"><strong>Candidate index</strong><nav aria-label="Candidate index">{navigation}</nav></section>
  {sections}
</main>
</body>
</html>
"""
