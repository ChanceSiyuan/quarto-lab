from __future__ import annotations

import csv
import io

import pytest

from autoqec_search.run_render import (
    ExperimentRow,
    FrontierItem,
    render_autoresearch_leaderboard,
    render_autoresearch_summary,
    render_experiment_log,
    render_frontier,
    render_run_summary_html,
)


def _rows() -> list[ExperimentRow]:
    return [
        ExperimentRow(
            candidate_id="rotated-surface-d3-example",
            ler=0.013,
            status="keep",
            description="entered frontier for distance 3",
        ),
        ExperimentRow(
            candidate_id="rotated-surface-d3-repeat",
            ler=0.02,
            status="discard",
            description="did not improve distance 3 frontier",
        ),
        ExperimentRow(
            candidate_id="rotated-surface-invalid-d1",
            ler=None,
            status="crash",
            description="no matching Zoo instance",
        ),
    ]


def _frontier() -> list[FrontierItem]:
    return [
        FrontierItem(
            candidate_id="rotated-surface-d3-example",
            distance=3,
            decoder_id="rmatching-default-v1",
            p=0.005,
            ler=0.013,
            manifest_path=(
                "candidates/rotated-surface-d3-example/evaluations/"
                "rotated-memory-x-cdep-v1/rmatching-default-v1/manifest.json"
            ),
        )
    ]


def test_render_experiment_log_uses_required_columns() -> None:
    text = render_experiment_log(_rows())

    assert text.splitlines()[0] == "candidate\tler\tstatus\tdescription"
    assert "rotated-surface-d3-example\t0.013\tkeep\tentered frontier for distance 3" in text
    assert "rotated-surface-invalid-d1\t\tcrash\tno matching Zoo instance" in text


def test_render_leaderboard_contains_only_keep_rows() -> None:
    text = render_autoresearch_leaderboard(_rows(), _frontier())
    rows = list(csv.reader(io.StringIO(text)))

    assert rows[0] == [
        "candidate_id",
        "distance",
        "distance_bound_type",
        "upper_bound",
        "decoder_id",
        "p",
        "ler",
        "status",
        "manifest_path",
    ]
    assert len(rows) == 2
    assert rows[1][0] == "rotated-surface-d3-example"
    assert rows[1][2] == "exact"
    assert rows[1][3] == ""
    assert rows[1][7] == "keep"


def test_render_frontier_returns_machine_readable_payload() -> None:
    payload = render_frontier(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        items=_frontier(),
    )

    assert payload["campaign_id"] == "rotated-surface-baseline"
    assert payload["run_id"] == "fixed-check"
    assert payload["items"][0]["distance"] == 3
    assert payload["items"][0]["candidate_id"] == "rotated-surface-d3-example"


def test_render_frontier_includes_upper_bound_metadata() -> None:
    payload = render_frontier(
        campaign_id="upper-bound-campaign",
        run_id="fixed-check",
        items=[
            FrontierItem(
                candidate_id="upper-bound-candidate",
                distance=7,
                decoder_id="predict-zero-v1",
                p=0.003,
                ler=0.01,
                manifest_path=(
                    "candidates/upper-bound-candidate/evaluations/"
                    "bb-css-memory-x-cdep-v1/predict-zero-v1/manifest.json"
                ),
                distance_bound_type="upper",
                upper_bound=7,
            )
        ],
    )

    assert payload["items"][0]["distance"] == 7
    assert payload["items"][0]["distance_bound_type"] == "upper"
    assert payload["items"][0]["upper_bound"] == 7


def test_render_summary_labels_upper_bound_frontier_entries() -> None:
    frontier = [
        FrontierItem(
            candidate_id="upper-bound-candidate",
            distance=7,
            decoder_id="predict-zero-v1",
            p=0.003,
            ler=0.01,
            manifest_path=(
                "candidates/upper-bound-candidate/evaluations/"
                "bb-css-memory-x-cdep-v1/predict-zero-v1/manifest.json"
            ),
            distance_bound_type="upper",
            upper_bound=7,
        )
    ]

    summary = render_autoresearch_summary(
        campaign_id="upper-bound-campaign",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=[],
        frontier=frontier,
    )
    html = render_run_summary_html(
        campaign_id="upper-bound-campaign",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=[],
        frontier=frontier,
    )

    assert "`upper\\-bound\\-candidate` upper_bound=7 predict\\-zero\\-v1" in summary
    assert "`upper-bound-candidate` d=7" not in summary
    assert "<th>Screening value</th><th>Bound type</th><th>Upper bound</th>" in html
    assert "<td>7</td><td>upper</td><td>7</td>" in html


def test_render_summary_and_html_escape_text() -> None:
    rows = [
        ExperimentRow(
            candidate_id='candidate <x> & "y"',
            ler=None,
            status="crash",
            description='failure <bad> & "quoted"',
        )
    ]

    summary = render_autoresearch_summary(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=rows,
        frontier=[],
    )
    html = render_run_summary_html(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=rows,
        frontier=[],
    )

    assert "# Autoresearch Run Summary" in summary
    assert "- crashes: `1`" in summary
    assert "<!doctype html>" in html
    assert "candidate &lt;x&gt; &amp; &quot;y&quot;" in html
    assert "failure &lt;bad&gt; &amp; &quot;quoted&quot;" in html
    assert 'candidate <x> & "y"' not in html


def test_render_html_does_not_link_unsafe_manifest_path() -> None:
    frontier = [
        FrontierItem(
            candidate_id="rotated-surface-d3-example",
            distance=3,
            decoder_id="rmatching-default-v1",
            p=0.005,
            ler=0.013,
            manifest_path="javascript:alert(1)",
        )
    ]

    html = render_run_summary_html(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=_rows(),
        frontier=frontier,
    )

    assert "href='javascript:alert(1)'" not in html
    assert 'href="javascript:alert(1)"' not in html
    assert "javascript:alert(1)" in html


def test_render_html_does_not_link_backslash_manifest_paths() -> None:
    traversal_path = r"..\secret/manifest.json"
    unc_path = r"\\server\share\manifest.json"
    frontier = [
        FrontierItem(
            candidate_id="rotated-surface-d3-example",
            distance=3,
            decoder_id="rmatching-default-v1",
            p=0.005,
            ler=0.013,
            manifest_path=traversal_path,
        ),
        FrontierItem(
            candidate_id="rotated-surface-d5-example",
            distance=5,
            decoder_id="rmatching-default-v1",
            p=0.005,
            ler=0.01,
            manifest_path=unc_path,
        ),
    ]

    html = render_run_summary_html(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=[
            ExperimentRow(
                candidate_id="rotated-surface-d3-example",
                ler=0.013,
                status="keep",
                description="entered frontier for distance 3",
            ),
            ExperimentRow(
                candidate_id="rotated-surface-d5-example",
                ler=0.01,
                status="keep",
                description="entered frontier for distance 5",
            ),
        ],
        frontier=frontier,
    )

    assert f"href='{traversal_path}'" not in html
    assert f'href="{traversal_path}"' not in html
    assert f"href='{unc_path}'" not in html
    assert f'href="{unc_path}"' not in html
    assert traversal_path in html
    assert unc_path in html


@pytest.mark.parametrize(
    "manifest_path",
    [
        "/abs/manifest.json",
        "../x/manifest.json",
        "safe/../x/manifest.json",
        "safe/\x1f/manifest.json",
        r"..\secret/manifest.json",
        "javascript:alert(1)",
        "%2e%2e/secret/manifest.json",
        "safe/%2e%2e/secret/manifest.json",
        " /abs/manifest.json",
        " //evil.example/a",
    ],
)
def test_render_html_does_not_link_invalid_manifest_paths(manifest_path: str) -> None:
    frontier = [
        FrontierItem(
            candidate_id="rotated-surface-d3-example",
            distance=3,
            decoder_id="rmatching-default-v1",
            p=0.005,
            ler=0.013,
            manifest_path=manifest_path,
        )
    ]

    html = render_run_summary_html(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=_rows(),
        frontier=frontier,
    )

    assert f"href='{manifest_path}'" not in html
    assert f'href="{manifest_path}"' not in html


def test_render_summary_keeps_injected_markdown_on_one_line() -> None:
    rows = [
        ExperimentRow(
            candidate_id="candidate `tick`\n# injected heading",
            ler=None,
            status="crash",
            description="failure line\n- injected bullet with `tick`",
        )
    ]

    summary = render_autoresearch_summary(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=rows,
        frontier=[],
    )

    assert "\n# injected heading" not in summary
    assert "\n- injected bullet" not in summary
    assert "\\`tick\\`" not in summary
    assert "candidate 'tick' \\# injected heading" in summary
    assert "failure line \\- injected bullet with 'tick'" in summary


def test_render_summary_neutralizes_active_markdown_and_html() -> None:
    rows = [
        ExperimentRow(
            candidate_id="candidate [x](javascript:alert(1)) <img src=x>",
            ler=None,
            status="crash",
            description=(
                "[x](javascript:alert(1)) "
                "![x](javascript:alert(1)) "
                "<img src=x onerror=alert(1)>"
            ),
        )
    ]

    summary = render_autoresearch_summary(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=rows,
        frontier=[],
    )

    assert "[x](javascript:alert(1))" not in summary
    assert "![x](javascript:alert(1))" not in summary
    assert "<img src=x onerror=alert(1)>" not in summary
    assert "<img src=x>" not in summary
    assert "\\[x\\]\\(javascript\\:alert\\(1\\)\\)" in summary
    assert "&lt;img src=x onerror=alert\\(1\\)&gt;" in summary


def test_render_summary_neutralizes_emphasis_strike_and_autolinks() -> None:
    rows = [
        ExperimentRow(
            candidate_id="candidate **bold** _italic_ ~~strike~~",
            ler=None,
            status="crash",
            description=(
                "**bold** _italic_ ~~strike~~ http://example.test "
                "{brace} # heading + plus - dash . dot | pipe > quote"
            ),
        )
    ]

    summary = render_autoresearch_summary(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=rows,
        frontier=[],
    )

    assert "**bold**" not in summary
    assert "_italic_" not in summary
    assert "~~strike~~" not in summary
    assert "http://example.test" not in summary
    assert "\\*\\*bold\\*\\*" in summary
    assert "\\_italic\\_" in summary
    assert "\\~\\~strike\\~\\~" in summary
    assert "http\\://example\\.test" in summary
    assert "\\{brace\\} \\# heading \\+ plus \\- dash \\. dot \\| pipe &gt; quote" in summary
