#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from autoqec_zoo.kb_migration import migrate_repo


def main() -> int:
    repo_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO_ROOT
    report = migrate_repo(repo_root)
    print(f"Imported: {', '.join(report.imported_titles) or '(none)'}")
    print(f"Skipped: {', '.join(report.skipped_titles) or '(none)'}")
    print(f"Appended bibliography keys: {', '.join(report.appended_bib_keys) or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
