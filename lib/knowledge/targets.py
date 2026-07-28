"""Classify link targets before applying context-specific trust rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import re


class TargetKind(str, Enum):
    EMPTY = "empty"
    EXTERNAL = "external"
    LOCAL = "local"
    ABSOLUTE = "absolute"
    BACKSLASH = "backslash"
    UNSUPPORTED_SCHEME = "unsupported-scheme"


@dataclass(frozen=True)
class LexicalTarget:
    raw: str
    path: str
    kind: TargetKind
    scheme: str | None = None


_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_SUPPORTED_EXTERNAL_SCHEMES = frozenset({"http", "https", "mailto"})


def classify_target(target: str) -> LexicalTarget:
    """Classify a raw Markdown target without touching the filesystem."""
    path = re.split(r"[?#]", target, maxsplit=1)[0]
    if not path:
        return LexicalTarget(raw=target, path=path, kind=TargetKind.EMPTY)
    if path.startswith(("/", "\\")) or _WINDOWS_ABSOLUTE.match(path):
        return LexicalTarget(raw=target, path=path, kind=TargetKind.ABSOLUTE)
    scheme_match = _SCHEME.match(path)
    if scheme_match is not None:
        scheme = scheme_match.group(1).casefold()
        kind = (
            TargetKind.EXTERNAL
            if scheme in _SUPPORTED_EXTERNAL_SCHEMES
            else TargetKind.UNSUPPORTED_SCHEME
        )
        return LexicalTarget(
            raw=target,
            path=path,
            kind=kind,
            scheme=scheme,
        )
    if "\\" in path:
        return LexicalTarget(raw=target, path=path, kind=TargetKind.BACKSLASH)
    return LexicalTarget(raw=target, path=path, kind=TargetKind.LOCAL)


def lexical_local_path(parent: Path, target: LexicalTarget) -> Path:
    """Return a normalized absolute path for an already-classified local target."""
    if target.kind is not TargetKind.LOCAL:
        raise ValueError(f"Expected a local target, received {target.kind.value}.")
    return Path(os.path.abspath(parent / target.path))
