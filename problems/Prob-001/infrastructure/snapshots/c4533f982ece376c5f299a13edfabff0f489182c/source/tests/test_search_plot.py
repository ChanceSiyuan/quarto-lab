from __future__ import annotations

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.plot import render_candidate_plot


def _point(
    *,
    p: float = 0.005,
    ler: float = 0.005,
    ci_low: float = 0.00214,
    ci_high: float = 0.01165,
) -> dict[str, object]:
    return {
        "p": p,
        "rounds": 3,
        "shots": 1000,
        "errors": 5,
        "ler": ler,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "seconds": 1.25,
    }


def _manifest(
    decoder_id: str,
    *,
    task_id: str = "rotated-memory-x-cdep-v1",
    points: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "candidate_id": "rotated-surface-d3",
        "task_id": task_id,
        "decoder_id": decoder_id,
        "status": "completed",
        "created_at": "2026-06-13T10:20:39Z",
        "tool_revisions": {"rsinter": "rsinter git main abc123"},
        "points": [_point()] if points is None else points,
    }


def test_render_candidate_plot_includes_series_ci_labels_and_footer() -> None:
    svg = render_candidate_plot(
        candidate_id="rotated-surface-d3",
        distance=3,
        task_id="rotated-memory-x-cdep-v1",
        generated_at="2026-06-13T10:20:39Z",
        manifests=[
            _manifest(
                "rmatching-default-v1",
                points=[
                    _point(p=0.005, ler=0.005, ci_low=0.00214, ci_high=0.01165),
                    _point(p=0.01, ler=0.018, ci_low=0.011, ci_high=0.029),
                ],
            ),
            _manifest(
                "rbposd-default-v1",
                points=[
                    _point(p=0.005, ler=0.006, ci_low=0.0028, ci_high=0.0128),
                    _point(p=0.01, ler=0.02, ci_low=0.0125, ci_high=0.031),
                ],
            ),
        ],
    )

    assert "<svg" in svg
    assert "rotated-surface-d3" in svg
    assert "distance=3" in svg
    assert "rotated-memory-x-cdep-v1" in svg
    assert "2026-06-13T10:20:39Z" in svg
    assert "rmatching-default-v1" in svg
    assert "rbposd-default-v1" in svg
    assert "p=0.005" in svg
    assert "p=0.01" in svg
    assert "ci-interval" in svg
    assert "point-marker" in svg
    assert "polyline" in svg
    assert svg.endswith("</svg>\n")


def test_render_candidate_plot_marks_unavailable_distance_in_footer() -> None:
    manifest = _manifest("rbposd-osd10-v1", task_id="bb-css-memory-x-cdep-v1")
    manifest["candidate_id"] = "bivariate-bicycle-code-m6-n6"

    svg = render_candidate_plot(
        candidate_id="bivariate-bicycle-code-m6-n6",
        distance=None,
        task_id="bb-css-memory-x-cdep-v1",
        generated_at="2026-06-13T10:20:39Z",
        manifests=[manifest],
    )

    assert "distance=unavailable" in svg


def test_render_candidate_plot_escapes_arbitrary_text_values() -> None:
    manifest = _manifest(
        'decoder <fast> & "quoted"',
        task_id='task <x> & "y"',
        points=[_point()],
    )
    manifest["candidate_id"] = 'candidate <one> & "two"'

    svg = render_candidate_plot(
        candidate_id='candidate <one> & "two"',
        distance=3,
        task_id='task <x> & "y"',
        generated_at='generated <now> & "later"',
        manifests=[manifest],
    )

    assert "candidate &lt;one&gt; &amp; &quot;two&quot;" in svg
    assert "task &lt;x&gt; &amp; &quot;y&quot;" in svg
    assert "generated &lt;now&gt; &amp; &quot;later&quot;" in svg
    assert "decoder &lt;fast&gt; &amp; &quot;quoted&quot;" in svg
    assert 'candidate <one> & "two"' not in svg
    assert 'decoder <fast> & "quoted"' not in svg


def test_render_candidate_plot_is_deterministic_by_decoder_and_p_order() -> None:
    decoder_b = _manifest(
        "decoder-b",
        points=[
            _point(p=0.02, ler=0.05, ci_low=0.03, ci_high=0.08),
            _point(p=0.005, ler=0.004, ci_low=0.0015, ci_high=0.009),
        ],
    )
    decoder_a = _manifest(
        "decoder-a",
        points=[
            _point(p=0.01, ler=0.012, ci_low=0.006, ci_high=0.021),
            _point(p=0.005, ler=0.003, ci_low=0.001, ci_high=0.007),
        ],
    )

    first = render_candidate_plot(
        candidate_id="rotated-surface-d3",
        distance=3,
        task_id="rotated-memory-x-cdep-v1",
        generated_at="2026-06-13T10:20:39Z",
        manifests=[decoder_b, decoder_a],
    )
    second = render_candidate_plot(
        candidate_id="rotated-surface-d3",
        distance=3,
        task_id="rotated-memory-x-cdep-v1",
        generated_at="2026-06-13T10:20:39Z",
        manifests=[decoder_a, decoder_b],
    )

    assert first == second
    assert first.index('data-decoder-id="decoder-a"') < first.index(
        'data-decoder-id="decoder-b"'
    )
    assert first.index("p=0.005") < first.index("p=0.01") < first.index("p=0.02")


def test_render_candidate_plot_allows_zero_ler_and_ci_for_log_coordinates() -> None:
    svg = render_candidate_plot(
        candidate_id="rotated-surface-d3",
        distance=3,
        task_id="rotated-memory-x-cdep-v1",
        generated_at="2026-06-13T10:20:39Z",
        manifests=[
            _manifest(
                "decoder-a",
                points=[
                    _point(p=0.005, ler=0.0, ci_low=0.0, ci_high=0.0038),
                    _point(p=0.01, ler=0.01, ci_low=0.004, ci_high=0.023),
                ],
            )
        ],
    )

    assert "decoder-a: p=0.005, LER=0, CI=[0, 0.0038]" in svg
    assert "ci-interval" in svg
    assert svg.endswith("</svg>\n")


def test_render_candidate_plot_rejects_manifest_identity_mismatch() -> None:
    manifest = _manifest("decoder-a")
    manifest["candidate_id"] = "other-candidate"

    with pytest.raises(SearchIntegrityError, match="unexpected candidate_id"):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[manifest],
        )


def test_render_candidate_plot_rejects_manifest_task_mismatch() -> None:
    manifest = _manifest("decoder-a")
    manifest["task_id"] = "other-task"

    with pytest.raises(SearchIntegrityError, match="unexpected task_id"):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[manifest],
        )


def test_render_candidate_plot_rejects_incomplete_completed_points() -> None:
    incomplete = {
        "p": 0.005,
        "ler": 0.005,
        "ci_low": 0.00214,
        "ci_high": 0.01165,
    }

    with pytest.raises(SearchIntegrityError, match="missing point field"):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[_manifest("decoder-a", points=[incomplete])],
        )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("rounds", 0, "rounds must be an integer >= 1"),
        ("shots", 0, "shots must be an integer >= 1"),
        ("errors", -1, "errors must be an integer >= 0"),
        ("seconds", -1, "seconds must be a number >= 0"),
    ],
)
def test_render_candidate_plot_rejects_invalid_completed_point_fields(
    field: str, value: object, match: str
) -> None:
    point = _point()
    point[field] = value

    with pytest.raises(SearchIntegrityError, match=match):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[_manifest("decoder-a", points=[point])],
        )


def test_render_candidate_plot_rejects_errors_exceeding_shots() -> None:
    point = _point()
    point["shots"] = 10
    point["errors"] = 11

    with pytest.raises(SearchIntegrityError, match="errors > shots"):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[_manifest("decoder-a", points=[point])],
        )


@pytest.mark.parametrize("field", ["campaign_id", "run_id", "created_at", "tool_revisions"])
def test_render_candidate_plot_rejects_missing_completed_manifest_fields(
    field: str,
) -> None:
    manifest = _manifest("decoder-a")
    del manifest[field]

    with pytest.raises(SearchIntegrityError, match=f"missing manifest field: {field}"):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[manifest],
        )


def test_render_candidate_plot_rejects_invalid_completed_manifest_timestamp() -> None:
    manifest = _manifest("decoder-a")
    manifest["created_at"] = "not-a-time"

    with pytest.raises(SearchIntegrityError, match="invalid created_at"):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[manifest],
        )


def test_render_candidate_plot_rejects_extra_completed_manifest_fields() -> None:
    manifest = _manifest("decoder-a")
    manifest["extra"] = "unexpected"

    with pytest.raises(SearchIntegrityError, match="unexpected manifest field: extra"):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[manifest],
        )


def test_render_candidate_plot_allows_decoder_parameters_manifest_field() -> None:
    manifest = _manifest("rbposd-osd10-v1")
    manifest["decoder_parameters"] = {
        "osd_order": 10,
        "early_stop": True,
        "bp_iters": 50,
    }

    svg = render_candidate_plot(
        candidate_id="rotated-surface-d3",
        distance=3,
        task_id="rotated-memory-x-cdep-v1",
        generated_at="2026-06-13T10:20:39Z",
        manifests=[manifest],
    )

    assert "rbposd-osd10-v1" in svg
    assert (
        "decoder_parameters={&quot;bp_iters&quot;: 50, "
        "&quot;early_stop&quot;: true, &quot;osd_order&quot;: 10}"
    ) in svg


def test_render_candidate_plot_keeps_empty_decoder_parameter_labels_clean() -> None:
    manifest = _manifest("rmatching-default-v1")
    manifest["decoder_parameters"] = {}

    svg = render_candidate_plot(
        candidate_id="rotated-surface-d3",
        distance=3,
        task_id="rotated-memory-x-cdep-v1",
        generated_at="2026-06-13T10:20:39Z",
        manifests=[manifest],
    )

    assert "rmatching-default-v1: p=0.005" in svg
    assert "rmatching-default-v1 decoder_parameters" not in svg
    assert "decoder_parameters={}" not in svg


def test_render_candidate_plot_rejects_extra_completed_point_fields() -> None:
    point = _point()
    point["extra"] = "unexpected"

    with pytest.raises(SearchIntegrityError, match="unexpected point field: extra"):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[_manifest("decoder-a", points=[point])],
        )


def test_render_candidate_plot_does_not_emit_rate_ticks_above_one() -> None:
    svg = render_candidate_plot(
        candidate_id="rotated-surface-d3",
        distance=3,
        task_id="rotated-memory-x-cdep-v1",
        generated_at="2026-06-13T10:20:39Z",
        manifests=[
            _manifest(
                "decoder-a",
                points=[_point(p=0.005, ler=1.0, ci_low=1.0, ci_high=1.0)],
            )
        ],
    )

    assert ">2<" not in svg
    assert ">1<" in svg


@pytest.mark.parametrize(
    ("manifests", "match"),
    [
        ([], "plot requires at least one completed manifest"),
        ([_manifest("decoder-a", points=[])], "manifest decoder-a has no points"),
    ],
)
def test_render_candidate_plot_rejects_empty_inputs(
    manifests: list[dict[str, object]], match: str
) -> None:
    with pytest.raises(SearchIntegrityError, match=match):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=manifests,
        )


def test_render_candidate_plot_rejects_duplicate_p_values_per_decoder() -> None:
    with pytest.raises(SearchIntegrityError, match="duplicate p value"):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[
                _manifest(
                    "decoder-a",
                    points=[
                        _point(p=0.005, ler=0.004, ci_low=0.001, ci_high=0.009),
                        _point(p=0.005, ler=0.005, ci_low=0.002, ci_high=0.011),
                    ],
                )
            ],
        )


@pytest.mark.parametrize(
    ("point", "match"),
    [
        (_point(p=0), "p must satisfy 0 < p < 1"),
        (_point(p=1), "p must satisfy 0 < p < 1"),
        (_point(p=1.2), "p must satisfy 0 < p < 1"),
        (_point(ler=-0.001), "ler must satisfy 0 <= ler <= 1"),
        (_point(ler=1.2, ci_high=1.2), "ler must satisfy 0 <= ler <= 1"),
        (_point(ci_low=-0.001), "ci_low must satisfy 0 <= ci_low <= 1"),
        (_point(ci_high=1.2), "ci_high must satisfy 0 <= ci_high <= 1"),
    ],
)
def test_render_candidate_plot_rejects_out_of_bounds_values(
    point: dict[str, object], match: str
) -> None:
    with pytest.raises(SearchIntegrityError, match=match):
        render_candidate_plot(
            candidate_id="rotated-surface-d3",
            distance=3,
            task_id="rotated-memory-x-cdep-v1",
            generated_at="2026-06-13T10:20:39Z",
            manifests=[_manifest("decoder-a", points=[point])],
        )
