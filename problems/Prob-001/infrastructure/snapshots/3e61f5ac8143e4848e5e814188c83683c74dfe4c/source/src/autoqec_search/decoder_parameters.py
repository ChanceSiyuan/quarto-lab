from __future__ import annotations

import json
from math import isfinite
from typing import Any


class DecoderParameterError(ValueError):
    """Raised when decoder parameter metadata is not a stable JSON object."""


def _is_scalar_parameter(value: Any) -> bool:
    return (
        value is None
        or isinstance(value, str)
        or isinstance(value, bool)
        or (isinstance(value, int) and not isinstance(value, bool))
        or (isinstance(value, float) and isfinite(value))
    )


def normalize_decoder_parameters(parameters: Any) -> dict[str, Any]:
    if parameters is None:
        return {}
    if not isinstance(parameters, dict):
        raise DecoderParameterError("decoder_parameters must be an object")

    normalized: dict[str, Any] = {}
    for key, value in parameters.items():
        if not isinstance(key, str) or not key:
            raise DecoderParameterError(
                "decoder parameter keys must be non-empty strings"
            )
        if not _is_scalar_parameter(value):
            raise DecoderParameterError(f"decoder parameter {key} must be a scalar")
        normalized[key] = value
    return {key: normalized[key] for key in sorted(normalized)}


def canonical_decoder_parameters(
    parameters: Any,
    *,
    impl_key: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_decoder_parameters(parameters)
    if impl_key == "rbposd" and "max_bp_iterations" in normalized:
        if "bp_iters" in normalized:
            raise DecoderParameterError(
                "rbposd parameters must not set both bp_iters and max_bp_iterations"
            )
        normalized["bp_iters"] = normalized.pop("max_bp_iterations")
    return {key: normalized[key] for key in sorted(normalized)}


def canonical_decoder_config(decoder: dict[str, Any]) -> dict[str, Any]:
    impl_key = decoder.get("impl_key")
    if impl_key is not None and not isinstance(impl_key, str):
        raise DecoderParameterError("decoder impl_key must be a string")
    canonical = dict(decoder)
    canonical["parameters"] = canonical_decoder_parameters(
        decoder.get("parameters", {}),
        impl_key=impl_key,
    )
    return canonical


def decoder_parameters_json(parameters: Any) -> str:
    return json.dumps(
        normalize_decoder_parameters(parameters),
        allow_nan=False,
        sort_keys=True,
    )


def decoder_parameters_suffix(parameters: Any) -> str:
    parameters_json = decoder_parameters_json(parameters)
    if parameters_json == "{}":
        return ""
    return f" decoder_parameters={parameters_json}"
