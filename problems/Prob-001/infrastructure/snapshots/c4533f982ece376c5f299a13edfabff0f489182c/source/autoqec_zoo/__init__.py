from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

SRC_PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "src" / "autoqec_zoo"

if SRC_PACKAGE_ROOT.is_dir():
    src_package_path = str(SRC_PACKAGE_ROOT)
    if src_package_path not in __path__:
        __path__.append(src_package_path)
