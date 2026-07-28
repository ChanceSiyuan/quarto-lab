"""One publishability policy for trusted local assets."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from .parser import css_loads_resource


TRUSTED_ASSET_SUFFIXES = frozenset(
    {
        ".gif",
        ".jpeg",
        ".jpg",
        ".pdf",
        ".png",
        ".svg",
        ".tif",
        ".tiff",
        ".webp",
    }
)


class TrustedAssetError(ValueError):
    """A stable validation failure for a local publish dependency."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _audit_svg(path: Path) -> None:
    source = path.read_bytes()
    lowered = source.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise TrustedAssetError("ASSET_UNSAFE", "unsafe SVG asset")
    try:
        root = ElementTree.fromstring(source)
    except ElementTree.ParseError as error:
        raise TrustedAssetError(
            "ASSET_UNSAFE",
            "unsafe SVG asset",
        ) from error

    forbidden_elements = {
        "embed",
        "foreignobject",
        "iframe",
        "object",
        "script",
    }
    for element in root.iter():
        tag = str(element.tag).rsplit("}", maxsplit=1)[-1].casefold()
        if tag in forbidden_elements:
            raise TrustedAssetError(
                "ASSET_UNSAFE",
                "unsafe SVG asset",
            )
        for raw_name, raw_value in element.attrib.items():
            name = str(raw_name).rsplit("}", maxsplit=1)[-1].casefold()
            value = str(raw_value).strip()
            if name.startswith("on"):
                raise TrustedAssetError(
                    "ASSET_UNSAFE",
                    "unsafe SVG asset",
                )
            if name == "href" and value and not value.startswith("#"):
                raise TrustedAssetError(
                    "ASSET_UNSAFE",
                    "unsafe SVG asset",
                )
            if name == "style" and css_loads_resource(value):
                raise TrustedAssetError(
                    "ASSET_UNSAFE",
                    "unsafe SVG asset",
                )
        if tag == "style" and css_loads_resource(
            "".join(element.itertext())
        ):
            raise TrustedAssetError(
                "ASSET_UNSAFE",
                "unsafe SVG asset",
            )


def audit_trusted_asset(path: Path) -> None:
    """Require a regular, allowlisted, passive publish dependency."""
    if not path.is_file():
        raise TrustedAssetError(
            "ASSET_NOT_FILE",
            "trusted asset is not a regular file",
        )
    suffix = path.suffix.casefold()
    if suffix not in TRUSTED_ASSET_SUFFIXES:
        raise TrustedAssetError(
            "ASSET_TYPE_FORBIDDEN",
            f"unsupported trusted asset type: {suffix or '<none>'}",
        )
    if suffix == ".svg":
        _audit_svg(path)
