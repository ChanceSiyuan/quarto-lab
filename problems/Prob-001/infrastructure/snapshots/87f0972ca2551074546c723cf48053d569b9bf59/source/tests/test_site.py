from __future__ import annotations

import shutil
from pathlib import Path

from autoqec_zoo.build import build_zoo


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_writes_static_site_artifacts(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-27")

    html = (work_root / "views" / "site" / "index.html").read_text()
    js = (work_root / "views" / "site" / "assets" / "app.js").read_text()
    css = (work_root / "views" / "site" / "assets" / "styles.css").read_text()

    assert (work_root / "views" / "site" / "index.html").exists()
    assert (work_root / "views" / "site" / "assets" / "app.js").exists()
    assert (work_root / "views" / "site" / "assets" / "styles.css").exists()
    assert '<script id="app-state" type="application/json">' in html
    assert "Canonical Facts" in html
    assert "Paper-Specific Evidence" in html
    assert "renderCodeList" in js
    assert "code.instance_count" in js
    assert ".layout" in css


def test_build_site_state_exposes_instance_count(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-28")

    html = (work_root / "views" / "site" / "index.html").read_text()
    js = (work_root / "views" / "site" / "assets" / "app.js").read_text()
    assert '"instance_count": 6' in html
    assert '"id": "rotated-surface-code-d3"' in html
    assert '"id": "rotated-surface-d3-example"' in html
    assert '"id": "rotated-surface-d5-example"' in html
    assert '"id": "rotated-surface-d7-example"' in html
    assert "renderInstances" in js
