from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import isfinite, log10
import re
from typing import Any

from autoqec_search.decoder_parameters import (
    DecoderParameterError,
    decoder_parameters_suffix,
    normalize_decoder_parameters,
)
from autoqec_search.load import SearchIntegrityError


@dataclass(frozen=True)
class PlotPoint:
    p: float
    ler: float
    ci_low: float
    ci_high: float


@dataclass(frozen=True)
class DecoderSeries:
    decoder_id: str
    decoder_parameters: dict[str, Any]
    points: tuple[PlotPoint, ...]


WIDTH = 900
HEIGHT = 560
MARGIN_LEFT = 78
MARGIN_RIGHT = 34
MARGIN_TOP = 52
MARGIN_BOTTOM = 96
PLOT_WIDTH = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
PLOT_HEIGHT = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

SERIES_COLORS = (
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
    "#7f7f7f",
)
LOG_RATE_FLOOR = 1e-12
REQUIRED_MANIFEST_FIELDS = (
    "campaign_id",
    "run_id",
    "candidate_id",
    "task_id",
    "decoder_id",
    "status",
    "created_at",
    "tool_revisions",
    "points",
)
ALLOWED_MANIFEST_FIELDS = {
    *REQUIRED_MANIFEST_FIELDS,
    "decoder_parameters",
    "run_metadata",
}
REQUIRED_POINT_FIELDS = (
    "p",
    "rounds",
    "shots",
    "errors",
    "ler",
    "ci_low",
    "ci_high",
    "seconds",
)
ALLOWED_POINT_FIELDS = set(REQUIRED_POINT_FIELDS)
CREATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _svg_text(value: object) -> str:
    return escape(str(value), quote=True)


def _svg_attr(value: object) -> str:
    return escape(str(value), quote=True)


def _format_float(value: float) -> str:
    return format(value, ".12g")


def _format_coord(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _require_finite_number(record: dict[str, Any], key: str, decoder_id: str) -> float:
    value = record.get(key)
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise SearchIntegrityError(f"manifest {decoder_id} point has invalid {key}")
    return float(value)


def _require_nonempty_string(
    record: dict[str, Any], key: str, decoder_id: str
) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(f"manifest {decoder_id} has invalid {key}")
    return value


def _require_int_at_least(
    record: dict[str, Any],
    key: str,
    decoder_id: str,
    minimum: int,
) -> int:
    value = record.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise SearchIntegrityError(f"{key} must be an integer >= {minimum}")
    return value


def _require_number_at_least(
    record: dict[str, Any],
    key: str,
    decoder_id: str,
    minimum: float,
) -> float:
    value = _require_finite_number(record, key, decoder_id)
    if value < minimum:
        raise SearchIntegrityError(f"{key} must be a number >= {_format_float(minimum)}")
    return value


def _require_probability(record: dict[str, Any], key: str, decoder_id: str) -> float:
    numeric = _require_finite_number(record, key, decoder_id)
    if not 0 < numeric < 1:
        raise SearchIntegrityError(f"{key} must satisfy 0 < {key} < 1")
    return numeric


def _require_rate(record: dict[str, Any], key: str, decoder_id: str) -> float:
    numeric = _require_finite_number(record, key, decoder_id)
    if not 0 <= numeric <= 1:
        raise SearchIntegrityError(f"{key} must satisfy 0 <= {key} <= 1")
    return numeric


def _plot_rate(value: float) -> float:
    return max(value, LOG_RATE_FLOOR)


def _rate_domain(values: list[float]) -> tuple[float, float]:
    low, high = _domain(values)
    return low, min(high, 1.0)


def _read_point(record: Any, decoder_id: str) -> PlotPoint:
    if not isinstance(record, dict):
        raise SearchIntegrityError(f"manifest {decoder_id} point must be an object")
    extra_fields = sorted(set(record) - ALLOWED_POINT_FIELDS)
    if extra_fields:
        raise SearchIntegrityError(f"unexpected point field: {extra_fields[0]}")
    for key in REQUIRED_POINT_FIELDS:
        if key not in record:
            raise SearchIntegrityError(
                f"manifest {decoder_id} point missing point field: {key}"
            )
    _require_int_at_least(record, "rounds", decoder_id, 1)
    shots = _require_int_at_least(record, "shots", decoder_id, 1)
    errors = _require_int_at_least(record, "errors", decoder_id, 0)
    if errors > shots:
        raise SearchIntegrityError(f"manifest {decoder_id} point has errors > shots")
    _require_number_at_least(record, "seconds", decoder_id, 0)
    point = PlotPoint(
        p=_require_probability(record, "p", decoder_id),
        ler=_require_rate(record, "ler", decoder_id),
        ci_low=_require_rate(record, "ci_low", decoder_id),
        ci_high=_require_rate(record, "ci_high", decoder_id),
    )
    if point.ci_low > point.ci_high:
        raise SearchIntegrityError(f"manifest {decoder_id} has inverted CI interval")
    if not point.ci_low <= point.ler <= point.ci_high:
        raise SearchIntegrityError(f"manifest {decoder_id} has LER outside CI interval")
    return point


def _read_decoder_parameters(record: dict[str, Any], decoder_id: str) -> dict[str, Any]:
    try:
        return normalize_decoder_parameters(record.get("decoder_parameters", {}))
    except DecoderParameterError as exc:
        raise SearchIntegrityError(f"manifest {decoder_id} {exc}") from exc


def _read_series(
    manifests: list[dict],
    *,
    candidate_id: str,
    task_id: str,
) -> list[DecoderSeries]:
    if not manifests:
        raise SearchIntegrityError("plot requires at least one completed manifest")

    series: list[DecoderSeries] = []
    seen_decoders: set[str] = set()
    for manifest in manifests:
        if not isinstance(manifest, dict):
            raise SearchIntegrityError("plot manifest must be an object")
        extra_fields = sorted(set(manifest) - ALLOWED_MANIFEST_FIELDS)
        if extra_fields:
            raise SearchIntegrityError(f"unexpected manifest field: {extra_fields[0]}")
        for key in REQUIRED_MANIFEST_FIELDS:
            if key not in manifest:
                raise SearchIntegrityError(f"missing manifest field: {key}")
        decoder_id = manifest.get("decoder_id")
        if not isinstance(decoder_id, str) or not decoder_id:
            raise SearchIntegrityError("plot manifest has invalid decoder_id")
        if decoder_id in seen_decoders:
            raise SearchIntegrityError(f"duplicate decoder manifest: {decoder_id}")
        seen_decoders.add(decoder_id)
        for key in (
            "campaign_id",
            "run_id",
            "candidate_id",
            "task_id",
            "created_at",
        ):
            _require_nonempty_string(manifest, key, decoder_id)
        if not CREATED_AT_RE.fullmatch(manifest["created_at"]):
            raise SearchIntegrityError(f"manifest {decoder_id} has invalid created_at")
        tool_revisions = manifest.get("tool_revisions")
        if not isinstance(tool_revisions, dict) or not tool_revisions:
            raise SearchIntegrityError(
                f"manifest {decoder_id} has invalid tool_revisions"
            )
        for tool_name, revision in tool_revisions.items():
            if (
                not isinstance(tool_name, str)
                or not isinstance(revision, str)
                or not revision
            ):
                raise SearchIntegrityError(
                    f"manifest {decoder_id} has invalid tool_revisions"
                )
        if manifest.get("status") != "completed":
            raise SearchIntegrityError(f"manifest {decoder_id} is not completed")
        if manifest.get("candidate_id") != candidate_id:
            raise SearchIntegrityError(
                f"manifest {decoder_id} has unexpected candidate_id"
            )
        if manifest.get("task_id") != task_id:
            raise SearchIntegrityError(f"manifest {decoder_id} has unexpected task_id")
        points = manifest.get("points")
        if not isinstance(points, list):
            raise SearchIntegrityError(f"manifest {decoder_id} has invalid points")
        if not points:
            raise SearchIntegrityError(f"manifest {decoder_id} has no points")
        parsed_points = tuple(
            sorted(
                (_read_point(point, decoder_id) for point in points),
                key=lambda point: point.p,
            )
        )
        seen_p: set[float] = set()
        for point in parsed_points:
            if point.p in seen_p:
                raise SearchIntegrityError(
                    f"manifest {decoder_id} has duplicate p value: {point.p}"
                )
            seen_p.add(point.p)
        series.append(
            DecoderSeries(
                decoder_id=decoder_id,
                decoder_parameters=_read_decoder_parameters(manifest, decoder_id),
                points=parsed_points,
            )
        )
    return sorted(series, key=lambda item: item.decoder_id)


def _decoder_label(series: DecoderSeries) -> str:
    return f"{series.decoder_id}{decoder_parameters_suffix(series.decoder_parameters)}"


def _domain(values: list[float]) -> tuple[float, float]:
    low = min(values)
    high = max(values)
    if low == high:
        return low / 2, high * 2
    pad = 10 ** ((log10(high) - log10(low)) * 0.04)
    return low / pad, high * pad


def _scale_log(value: float, domain: tuple[float, float], start: float, end: float) -> float:
    low, high = domain
    if low == high:
        return (start + end) / 2
    position = (log10(value) - log10(low)) / (log10(high) - log10(low))
    return start + position * (end - start)


def _polyline_coords(
    points: tuple[PlotPoint, ...],
    x_domain: tuple[float, float],
    y_domain: tuple[float, float],
) -> str:
    coords = [
        (
            _format_coord(
                _scale_log(point.p, x_domain, MARGIN_LEFT, MARGIN_LEFT + PLOT_WIDTH)
            ),
            _format_coord(
                _scale_log(
                    _plot_rate(point.ler),
                    y_domain,
                    MARGIN_TOP + PLOT_HEIGHT,
                    MARGIN_TOP,
                )
            ),
        )
        for point in points
    ]
    return " ".join(f"{x},{y}" for x, y in coords)


def render_candidate_plot(
    candidate_id: str,
    distance: int | None,
    task_id: str,
    generated_at: str,
    manifests: list[dict],
) -> str:
    """Render a deterministic standalone SVG LER plot from completed manifests."""

    series = _read_series(manifests, candidate_id=candidate_id, task_id=task_id)
    all_points = [point for item in series for point in item.points]
    p_values = sorted({point.p for point in all_points})
    y_values = [
        _plot_rate(value)
        for point in all_points
        for value in (point.ci_low, point.ler, point.ci_high)
    ]
    x_domain = _domain(p_values)
    y_domain = _rate_domain(y_values)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Candidate logical error rate plot">',
        "<style>",
        ".plot-bg{fill:#ffffff}",
        ".axis{stroke:#20242a;stroke-width:1.2}",
        ".grid{stroke:#d9dee7;stroke-width:1;stroke-dasharray:3 4}",
        ".tick-label,.axis-label,.footer,.legend{font-family:Arial,sans-serif;fill:#20242a}",
        ".tick-label{font-size:11px}",
        ".axis-label{font-size:13px;font-weight:600}",
        ".footer{font-size:11px;fill:#4c5564}",
        ".legend{font-size:12px}",
        ".ci-interval{stroke-width:1.8;stroke-linecap:round;opacity:.85}",
        ".decoder-series{fill:none;stroke-width:2.4;stroke-linejoin:round;stroke-linecap:round}",
        ".point-marker{stroke:#ffffff;stroke-width:1.5}",
        "</style>",
        '<rect class="plot-bg" x="0" y="0" width="900" height="560"/>',
        f'<text class="axis-label" x="{MARGIN_LEFT}" y="28">Logical error rate vs physical error rate</text>',
    ]

    plot_bottom = MARGIN_TOP + PLOT_HEIGHT
    plot_right = MARGIN_LEFT + PLOT_WIDTH
    lines.extend(
        [
            f'<line class="axis" x1="{MARGIN_LEFT}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}"/>',
            f'<line class="axis" x1="{MARGIN_LEFT}" y1="{MARGIN_TOP}" x2="{MARGIN_LEFT}" y2="{plot_bottom}"/>',
        ]
    )

    for p in p_values:
        x = _format_coord(_scale_log(p, x_domain, MARGIN_LEFT, plot_right))
        label = _svg_text(_format_float(p))
        lines.extend(
            [
                f'<line class="grid" x1="{x}" y1="{MARGIN_TOP}" x2="{x}" y2="{plot_bottom}"/>',
                f'<line class="axis" x1="{x}" y1="{plot_bottom}" x2="{x}" y2="{plot_bottom + 5}"/>',
                f'<text class="tick-label" x="{x}" y="{plot_bottom + 20}" text-anchor="middle">p={label}</text>',
            ]
        )

    y_ticks = sorted(
        {y_domain[0], y_domain[1], *(_plot_rate(point.ler) for point in all_points)}
    )
    for value in y_ticks:
        y = _format_coord(_scale_log(value, y_domain, plot_bottom, MARGIN_TOP))
        label = _svg_text(_format_float(value))
        lines.extend(
            [
                f'<line class="grid" x1="{MARGIN_LEFT}" y1="{y}" x2="{plot_right}" y2="{y}"/>',
                f'<line class="axis" x1="{MARGIN_LEFT - 5}" y1="{y}" x2="{MARGIN_LEFT}" y2="{y}"/>',
                f'<text class="tick-label" x="{MARGIN_LEFT - 9}" y="{y}" text-anchor="end" dominant-baseline="middle">{label}</text>',
            ]
        )

    lines.extend(
        [
            f'<text class="axis-label" x="{(MARGIN_LEFT + plot_right) / 2:.1f}" y="{HEIGHT - 48}" text-anchor="middle">Physical error rate p (log scale)</text>',
            f'<text class="axis-label" transform="translate(22 {(MARGIN_TOP + plot_bottom) / 2:.1f}) rotate(-90)" text-anchor="middle">Logical error rate (log scale)</text>',
        ]
    )

    legend_x = MARGIN_LEFT + 12
    legend_y = MARGIN_TOP + 18
    for index, item in enumerate(series):
        color = SERIES_COLORS[index % len(SERIES_COLORS)]
        decoder_attr = _svg_attr(item.decoder_id)
        decoder_label = _decoder_label(item)
        coords = _polyline_coords(item.points, x_domain, y_domain)
        lines.append(
            f'<polyline class="decoder-series" data-decoder-id="{decoder_attr}" points="{coords}" stroke="{color}"/>'
        )
        for point in item.points:
            x = _format_coord(_scale_log(point.p, x_domain, MARGIN_LEFT, plot_right))
            y = _format_coord(
                _scale_log(_plot_rate(point.ler), y_domain, plot_bottom, MARGIN_TOP)
            )
            y_low = _format_coord(
                _scale_log(_plot_rate(point.ci_low), y_domain, plot_bottom, MARGIN_TOP)
            )
            y_high = _format_coord(
                _scale_log(_plot_rate(point.ci_high), y_domain, plot_bottom, MARGIN_TOP)
            )
            label = (
                f"{decoder_label}: p={_format_float(point.p)}, "
                f"LER={_format_float(point.ler)}, "
                f"CI=[{_format_float(point.ci_low)}, {_format_float(point.ci_high)}]"
            )
            lines.extend(
                [
                    f'<line class="ci-interval" data-decoder-id="{decoder_attr}" x1="{x}" y1="{y_low}" x2="{x}" y2="{y_high}" stroke="{color}"/>',
                    f'<circle class="point-marker" data-decoder-id="{decoder_attr}" cx="{x}" cy="{y}" r="4.4" fill="{color}"><title>{_svg_text(label)}</title></circle>',
                ]
            )
        legend_item_y = legend_y + index * 18
        lines.extend(
            [
                f'<line x1="{legend_x}" y1="{legend_item_y}" x2="{legend_x + 20}" y2="{legend_item_y}" stroke="{color}" stroke-width="2.4"/>',
                f'<circle cx="{legend_x + 10}" cy="{legend_item_y}" r="3.5" fill="{color}" stroke="#ffffff" stroke-width="1"/>',
                f'<text class="legend" x="{legend_x + 28}" y="{legend_item_y}" dominant-baseline="middle">{_svg_text(decoder_label)}</text>',
            ]
        )

    distance_text = str(distance) if distance is not None else "unavailable"
    footer = (
        f"candidate={candidate_id}, distance={distance_text}, "
        f"task={task_id}, generated={generated_at}"
    )
    lines.extend(
        [
            f'<text class="footer" x="{MARGIN_LEFT}" y="{HEIGHT - 18}">{_svg_text(footer)}</text>',
            "</svg>",
            "",
        ]
    )
    return "\n".join(lines)
