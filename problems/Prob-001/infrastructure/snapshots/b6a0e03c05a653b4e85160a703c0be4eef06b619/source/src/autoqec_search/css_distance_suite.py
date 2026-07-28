"""Validation contracts for blinded CSS-distance paper suites."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
from typing import Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from autoqec_search.load import SearchIntegrityError
from autoqec_search.structure import (
    gf2_rank,
    matrix_data,
    verify_css_upper_bound_witness,
)


FAMILY_COUNTS = {
    "development": {
        "geometric": 8,
        "bivariate-bicycle": 6,
        "apm-kasai": 4,
        "quantum-tanner": 6,
    },
    "final": {
        "geometric": 4,
        "bivariate-bicycle": 3,
        "apm-kasai": 2,
        "quantum-tanner": 3,
    },
}
GEOMETRIC_KIND_COUNTS = {
    "development": {"surface": 4, "toric": 4},
    "final": {"surface": 2, "toric": 2},
}
TIME_LIMIT_SECONDS = 300
MINIMUM_SEEDS = 20

_SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "schemas"


@dataclass(frozen=True)
class ValidatedSuiteCase:
    record: dict
    hx_payload: dict
    hz_payload: dict


def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_rowspace_fingerprint(rows: Iterable[Iterable[int]]) -> str:
    dense_rows = _validate_dense_rows(rows)
    rref_rows = _rref_rows(dense_rows)
    return sha256_bytes(canonical_json_bytes(rref_rows))


def load_and_validate_source_pool(
    *,
    root: Path,
    path: Path,
) -> tuple[ValidatedSuiteCase, ...]:
    pool = _load_json_at(root, path, label="source pool")
    _validate_schema("css-distance-source-pool.schema.json", pool, "source pool")

    records = pool.get("cases")
    if not isinstance(records, list):
        raise SearchIntegrityError("source pool schema violation")

    seen_ids: set[str] = set()
    seen_constructions: set[str] = set()
    seen_rowspaces: set[tuple[str, str]] = set()
    cases: list[ValidatedSuiteCase] = []
    for record in records:
        case = _validate_source_record(root, record)
        case_id = case.record["case_id"]
        if case_id in seen_ids:
            raise SearchIntegrityError("duplicate source case id")
        seen_ids.add(case_id)

        construction_key = sha256_bytes(
            canonical_json_bytes(case.record["construction"])
        )
        if construction_key in seen_constructions:
            raise SearchIntegrityError("duplicate construction record")
        seen_constructions.add(construction_key)

        rowspace_key = (
            case.record["hx_rowspace_sha256"],
            case.record["hz_rowspace_sha256"],
        )
        if rowspace_key in seen_rowspaces:
            raise SearchIntegrityError("duplicate row-space fingerprints")
        seen_rowspaces.add(rowspace_key)
        cases.append(case)

    return tuple(sorted(cases, key=lambda case: case.record["case_id"]))


def validate_split_manifest(
    *,
    root: Path,
    payload: dict,
    source_cases: Iterable[ValidatedSuiteCase],
) -> dict:
    _ = root
    _validate_schema(
        "css-distance-split-manifest.schema.json",
        payload,
        "split manifest",
    )
    split = payload.get("split")
    if split not in FAMILY_COUNTS:
        raise SearchIntegrityError("split manifest schema violation")
    manifest_cases = payload.get("cases")
    if not isinstance(manifest_cases, list):
        raise SearchIntegrityError("split manifest schema violation")

    expected_total = sum(FAMILY_COUNTS[split].values())
    if len(manifest_cases) != expected_total:
        raise SearchIntegrityError("split case count mismatch")

    source_by_id = {case.record["case_id"]: case for case in source_cases}
    opaque_ids: set[str] = set()
    selected_ids: set[str] = set()
    selected: list[ValidatedSuiteCase] = []
    for entry in manifest_cases:
        opaque_id = entry["case_id"]
        source_id = entry["source_case_id"]
        if opaque_id in opaque_ids or source_id in selected_ids:
            raise SearchIntegrityError("duplicate split manifest entry")
        opaque_ids.add(opaque_id)
        selected_ids.add(source_id)
        try:
            selected.append(source_by_id[source_id])
        except KeyError as error:
            raise SearchIntegrityError("split manifest references unknown source case") from error

    family_counts = Counter(case.record["family"] for case in selected)
    if dict(family_counts) != FAMILY_COUNTS[split]:
        raise SearchIntegrityError("split family counts mismatch")

    geometric_kind_counts = Counter(
        case.record["construction_kind"]
        for case in selected
        if case.record["family"] == "geometric"
    )
    if dict(geometric_kind_counts) != GEOMETRIC_KIND_COUNTS[split]:
        raise SearchIntegrityError("split geometric-kind counts mismatch")

    reference_counts = Counter(case.record["reference"]["bound_type"] for case in selected)
    if reference_counts["exact"] < expected_total // 2:
        raise SearchIntegrityError("split exact-reference coverage is insufficient")
    if reference_counts["upper"] < expected_total // 4:
        raise SearchIntegrityError("split upper-reference coverage is insufficient")

    size_bands = Counter(_size_band(int(case.record["n"])) for case in selected)
    if set(size_bands) != {"small", "medium", "large"}:
        raise SearchIntegrityError("split size-band coverage is insufficient")

    return {
        "status": "pass",
        "split": split,
        "case_count": len(selected),
        "family_counts": dict(FAMILY_COUNTS[split]),
        "geometric_kind_counts": dict(GEOMETRIC_KIND_COUNTS[split]),
        "reference_counts": {
            "exact": reference_counts["exact"],
            "upper": reference_counts["upper"],
        },
        "size_bands": {
            "large": size_bands["large"],
            "medium": size_bands["medium"],
            "small": size_bands["small"],
        },
    }


def prepare_blind_suite(
    *,
    root: Path,
    source_pool_path: Path,
    work_root: Path,
    commitment_path: Path,
    created_at: str,
    secret: bytes | None = None,
    salt: bytes | None = None,
) -> dict:
    secret = _secret_bytes(secret, label="selection secret")
    salt = _secret_bytes(salt, label="commitment salt")
    _reject_private_root_inside_worktree(root=root, work_root=work_root)

    source_cases = load_and_validate_source_pool(root=root, path=source_pool_path)
    selected = _select_blind_cases(source_cases, secret)
    private_root = work_root / "private" / "css-distance-paper-suite"
    if private_root.exists():
        raise SearchIntegrityError("private suite already exists")

    _mkdir_private(private_root)
    _write_private_bytes(private_root / "selection-secret.bin", secret)
    _write_private_bytes(private_root / "salt.bin", salt)

    source_pool_payload = {
        "schema_version": 1,
        "created_at": created_at,
        "cases": [copy_case.record for copy_case in source_cases],
    }
    _write_private_json(private_root / "source_pool.json", source_pool_payload)

    manifests = {}
    for split, cases in selected.items():
        split_root = private_root / split
        _mkdir_private(split_root)
        manifest = _materialize_split(
            root=root,
            split_root=split_root,
            split=split,
            cases=cases,
            created_at=created_at,
        )
        manifests[split] = manifest

    source_commit = _git_head_or_zero(root)
    commitment = {
        "schema_version": 1,
        "selection_policy_version": 1,
        "created_at": created_at,
        "source_commit": source_commit,
        "counts": {"development": 24, "final": 12},
        "family_counts": FAMILY_COUNTS,
        "geometric_kind_counts": GEOMETRIC_KIND_COUNTS,
        "source_pool_sha256": sha256_bytes(canonical_json_bytes(source_pool_payload)),
        "development_manifest_commitment": _salted_hash(
            salt,
            canonical_json_bytes(manifests["development"]),
        ),
        "final_manifest_commitment": _salted_hash(
            salt,
            canonical_json_bytes(manifests["final"]),
        ),
        "selection_secret_commitment": _salted_hash(salt, secret),
    }
    _validate_schema(
        "css-distance-suite-commitment.schema.json",
        commitment,
        "suite commitment",
    )
    commitment_path.parent.mkdir(parents=True, exist_ok=True)
    commitment_path.write_text(json.dumps(commitment, sort_keys=True, indent=2) + "\n")
    return commitment


def verify_suite_commitment(*, private_root: Path, commitment: dict) -> dict:
    _validate_schema(
        "css-distance-suite-commitment.schema.json",
        commitment,
        "suite commitment",
    )
    salt = (private_root / "salt.bin").read_bytes()
    secret = (private_root / "selection-secret.bin").read_bytes()
    source_pool = _load_json_file(private_root / "source_pool.json", label="source pool")
    development = _load_json_file(
        private_root / "development" / "manifest.json",
        label="development manifest",
    )
    final = _load_json_file(
        private_root / "final" / "manifest.json",
        label="final manifest",
    )

    expected = {
        "source_pool_sha256": sha256_bytes(canonical_json_bytes(source_pool)),
        "development_manifest_commitment": _salted_hash(
            salt,
            canonical_json_bytes(development),
        ),
        "final_manifest_commitment": _salted_hash(salt, canonical_json_bytes(final)),
        "selection_secret_commitment": _salted_hash(salt, secret),
    }
    for key, value in expected.items():
        if commitment[key] != value:
            raise SearchIntegrityError("suite commitment mismatch")

    _verify_private_matrix_hashes(private_root, development)
    _verify_private_matrix_hashes(private_root, final)
    return {
        "status": "pass",
        "development": len(development["cases"]),
        "final": len(final["cases"]),
    }


def _select_blind_cases(
    source_cases: tuple[ValidatedSuiteCase, ...],
    secret: bytes,
) -> dict[str, list[ValidatedSuiteCase]]:
    remaining = list(source_cases)
    selected: dict[str, list[ValidatedSuiteCase]] = {}
    for split in ("development", "final"):
        split_cases = _select_split_cases(remaining, split=split, secret=secret)
        selected[split] = split_cases
        selected_ids = {case.record["case_id"] for case in split_cases}
        remaining = [
            case for case in remaining if case.record["case_id"] not in selected_ids
        ]
    return selected


def _select_split_cases(
    available: list[ValidatedSuiteCase],
    *,
    split: str,
    secret: bytes,
) -> list[ValidatedSuiteCase]:
    selected: list[ValidatedSuiteCase] = []
    for construction_kind, count in GEOMETRIC_KIND_COUNTS[split].items():
        candidates = [
            case
            for case in available
            if case.record["family"] == "geometric"
            and case.record["construction_kind"] == construction_kind
        ]
        selected.extend(
            _balanced_take(
                candidates,
                count=count,
                secret=secret,
                label=f"{split}:geometric:{construction_kind}",
            )
        )

    for family, count in FAMILY_COUNTS[split].items():
        if family == "geometric":
            continue
        candidates = [case for case in available if case.record["family"] == family]
        selected.extend(
            _balanced_take(
                candidates,
                count=count,
                secret=secret,
                label=f"{split}:{family}",
            )
        )
    selected = _rebalance_reference_coverage(
        available=available,
        selected=selected,
        split=split,
        secret=secret,
    )

    manifest = {
        "schema_version": 1,
        "split": split,
        "created_at": "2026-07-21T00:00:00Z",
        "cases": [
            {"case_id": f"{split}-{index:03d}", "source_case_id": case.record["case_id"]}
            for index, case in enumerate(selected)
        ],
    }
    try:
        validate_split_manifest(
            root=Path("/private/css-distance-paper-suite"),
            payload=manifest,
            source_cases=tuple(selected),
        )
    except SearchIntegrityError as error:
        raise SearchIntegrityError("insufficient eligible cases for split coverage") from error
    return selected


def _rebalance_reference_coverage(
    *,
    available: list[ValidatedSuiteCase],
    selected: list[ValidatedSuiteCase],
    split: str,
    secret: bytes,
) -> list[ValidatedSuiteCase]:
    expected_total = sum(FAMILY_COUNTS[split].values())
    minimum_exact = expected_total // 2
    minimum_upper = expected_total // 4
    selected = list(selected)
    while _reference_count(selected, "exact") < minimum_exact:
        replacement = _find_reference_swap(
            available=available,
            selected=selected,
            from_bound="upper",
            to_bound="exact",
            secret=secret,
            label=f"{split}:exact-rebalance",
        )
        if replacement is None or _reference_count(selected, "upper") - 1 < minimum_upper:
            raise SearchIntegrityError("insufficient eligible cases for split coverage")
        old_case, new_case = replacement
        selected[selected.index(old_case)] = new_case

    while _reference_count(selected, "upper") < minimum_upper:
        replacement = _find_reference_swap(
            available=available,
            selected=selected,
            from_bound="exact",
            to_bound="upper",
            secret=secret,
            label=f"{split}:upper-rebalance",
        )
        if replacement is None or _reference_count(selected, "exact") - 1 < minimum_exact:
            raise SearchIntegrityError("insufficient eligible cases for split coverage")
        old_case, new_case = replacement
        selected[selected.index(old_case)] = new_case

    return sorted(
        selected,
        key=lambda case: _selection_score(secret, f"{split}:final-order", case),
    )


def _find_reference_swap(
    *,
    available: list[ValidatedSuiteCase],
    selected: list[ValidatedSuiteCase],
    from_bound: str,
    to_bound: str,
    secret: bytes,
    label: str,
) -> tuple[ValidatedSuiteCase, ValidatedSuiteCase] | None:
    selected_ids = {case.record["case_id"] for case in selected}
    selected_by_stratum: dict[tuple[str, str], list[ValidatedSuiteCase]] = {}
    for case in selected:
        if case.record["reference"]["bound_type"] != from_bound:
            continue
        selected_by_stratum.setdefault(_selection_stratum(case), []).append(case)

    swaps: list[tuple[bytes, ValidatedSuiteCase, ValidatedSuiteCase]] = []
    for stratum, removable in selected_by_stratum.items():
        additions = [
            case
            for case in available
            if case.record["case_id"] not in selected_ids
            and _selection_stratum(case) == stratum
            and case.record["reference"]["bound_type"] == to_bound
        ]
        for old_case in removable:
            for new_case in additions:
                swaps.append(
                    (
                        _swap_score(secret, label, old_case, new_case),
                        old_case,
                        new_case,
                    )
                )
    if not swaps:
        return None
    _score, old_case, new_case = min(swaps, key=lambda item: item[0])
    return old_case, new_case


def _selection_stratum(case: ValidatedSuiteCase) -> tuple[str, str]:
    family = case.record["family"]
    if family == "geometric":
        return family, case.record["construction_kind"]
    return family, family


def _reference_count(cases: list[ValidatedSuiteCase], bound_type: str) -> int:
    return sum(1 for case in cases if case.record["reference"]["bound_type"] == bound_type)


def _swap_score(
    secret: bytes,
    label: str,
    old_case: ValidatedSuiteCase,
    new_case: ValidatedSuiteCase,
) -> bytes:
    return hashlib.sha256(
        secret
        + b"\x00"
        + label.encode()
        + b"\x00"
        + old_case.record["case_id"].encode()
        + b"\x00"
        + new_case.record["case_id"].encode()
    ).digest()


def _balanced_take(
    candidates: list[ValidatedSuiteCase],
    *,
    count: int,
    secret: bytes,
    label: str,
) -> list[ValidatedSuiteCase]:
    if len(candidates) < count:
        raise SearchIntegrityError("insufficient eligible cases for split stratum")
    selected = _take_across_size_bands(
        candidates,
        count=count,
        secret=secret,
        label=label,
    )
    return sorted(selected, key=lambda case: _selection_score(secret, label, case))


def _take_across_size_bands(
    candidates: list[ValidatedSuiteCase],
    *,
    count: int,
    secret: bytes,
    label: str,
) -> list[ValidatedSuiteCase]:
    if count == 0:
        return []
    buckets: dict[str, list[ValidatedSuiteCase]] = {}
    for case in candidates:
        key = _size_band(int(case.record["n"]))
        buckets.setdefault(key, []).append(case)
    for key, bucket in buckets.items():
        bucket.sort(key=lambda case: _selection_score(secret, f"{label}:{key}", case))

    bucket_order = sorted(
        buckets,
        key=lambda key: _selection_score(secret, f"{label}:bucket", buckets[key][0]),
    )
    selected: list[ValidatedSuiteCase] = []
    while len(selected) < count:
        progressed = False
        for key in bucket_order:
            if not buckets[key]:
                continue
            selected.append(buckets[key].pop(0))
            progressed = True
            if len(selected) == count:
                break
        if not progressed:
            break
    if len(selected) != count:
        raise SearchIntegrityError("insufficient eligible cases for split stratum")
    return selected


def _selection_score(secret: bytes, label: str, case: ValidatedSuiteCase) -> bytes:
    return hashlib.sha256(
        secret
        + b"\x00"
        + label.encode()
        + b"\x00"
        + case.record["case_id"].encode()
    ).digest()


def _materialize_split(
    *,
    root: Path,
    split_root: Path,
    split: str,
    cases: list[ValidatedSuiteCase],
    created_at: str,
) -> dict:
    manifest_cases: list[dict] = []
    for index, case in enumerate(cases):
        opaque_id = f"{split}-{index:03d}"
        case_root = split_root / opaque_id
        _mkdir_private(case_root)
        _copy_private_file(
            _join_under(root, Path(case.record["hx_path"]), label="matrix path"),
            case_root / "hx.json",
        )
        _copy_private_file(
            _join_under(root, Path(case.record["hz_path"]), label="matrix path"),
            case_root / "hz.json",
        )
        manifest_cases.append(
            {
                "case_id": opaque_id,
                "source_case_id": case.record["case_id"],
                "family": case.record["family"],
                "construction_kind": case.record["construction_kind"],
                "construction": case.record["construction"],
                "n": case.record["n"],
                "k": case.record["k"],
                "reference": case.record["reference"],
                "hx_path": f"{opaque_id}/hx.json",
                "hz_path": f"{opaque_id}/hz.json",
                "hx_sha256": case.record["hx_sha256"],
                "hz_sha256": case.record["hz_sha256"],
                "hx_rowspace_sha256": case.record["hx_rowspace_sha256"],
                "hz_rowspace_sha256": case.record["hz_rowspace_sha256"],
            }
        )
    manifest = {
        "schema_version": 1,
        "split": split,
        "created_at": created_at,
        "cases": manifest_cases,
    }
    _write_private_json(split_root / "manifest.json", manifest)
    return manifest


def _verify_private_matrix_hashes(private_root: Path, manifest: dict) -> None:
    split = manifest.get("split")
    if split not in {"development", "final"}:
        raise SearchIntegrityError("invalid private split manifest")
    for case in manifest.get("cases", []):
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or "/" in case_id or ".." in Path(case_id).parts:
            raise SearchIntegrityError("invalid private split manifest")
        hx_path = private_root / split / case_id / "hx.json"
        hz_path = private_root / split / case_id / "hz.json"
        if _sha256_file(hx_path) != case.get("hx_sha256"):
            raise SearchIntegrityError("matrix hash mismatch")
        if _sha256_file(hz_path) != case.get("hz_sha256"):
            raise SearchIntegrityError("matrix hash mismatch")


def _secret_bytes(value: bytes | None, *, label: str) -> bytes:
    if value is None:
        return secrets.token_bytes(32)
    if not isinstance(value, bytes) or len(value) != 32:
        raise SearchIntegrityError(f"invalid {label}")
    return value


def _salted_hash(salt: bytes, data: bytes) -> str:
    return sha256_bytes(salt + data)


def _mkdir_private(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    path.chmod(0o700)


def _write_private_json(path: Path, payload: dict) -> None:
    _write_private_bytes(
        path,
        json.dumps(payload, sort_keys=True, indent=2).encode() + b"\n",
    )


def _write_private_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    path.chmod(0o600)


def _copy_private_file(source: Path, destination: Path) -> None:
    _write_private_bytes(destination, source.read_bytes())


def _reject_private_root_inside_worktree(*, root: Path, work_root: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "worktree", "list", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return
    if result.returncode != 0:
        return
    target = work_root.resolve()
    for line in result.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        worktree = Path(line.removeprefix("worktree ")).resolve()
        if target == worktree or worktree in target.parents:
            raise SearchIntegrityError("private suite root must be outside Git worktrees")


def _git_head_or_zero(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "0" * 40
    head = result.stdout.strip()
    if result.returncode != 0 or len(head) != 40:
        return "0" * 40
    return head


def _validate_source_record(root: Path, record: dict) -> ValidatedSuiteCase:
    case_id = record.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise SearchIntegrityError("source pool schema violation")

    hx_path = _safe_relative_path(record.get("hx_path"), label="matrix path")
    hz_path = _safe_relative_path(record.get("hz_path"), label="matrix path")
    hx_file = _join_under(root, hx_path, label="matrix path")
    hz_file = _join_under(root, hz_path, label="matrix path")
    hx_payload = _load_json_file(hx_file, label="matrix JSON")
    hz_payload = _load_json_file(hz_file, label="matrix JSON")

    if _sha256_file(hx_file) != record["hx_sha256"]:
        raise SearchIntegrityError("matrix hash mismatch")
    if _sha256_file(hz_file) != record["hz_sha256"]:
        raise SearchIntegrityError("matrix hash mismatch")

    hx_rows = matrix_data(hx_payload, "hx.json")
    hz_rows = matrix_data(hz_payload, "hz.json")
    n = _matrix_num_cols(hx_payload, hx_rows, label="hx.json")
    if n != _matrix_num_cols(hz_payload, hz_rows, label="hz.json"):
        raise SearchIntegrityError("matrix column mismatch")
    if n != record["n"]:
        raise SearchIntegrityError("n mismatch")

    if canonical_rowspace_fingerprint(hx_rows) != record["hx_rowspace_sha256"]:
        raise SearchIntegrityError("row-space hash mismatch")
    if canonical_rowspace_fingerprint(hz_rows) != record["hz_rowspace_sha256"]:
        raise SearchIntegrityError("row-space hash mismatch")

    if not _css_checks_commute(hx_rows, hz_rows):
        raise SearchIntegrityError("CSS checks do not commute")

    derived_k = n - gf2_rank(hx_rows) - gf2_rank(hz_rows)
    if derived_k != record["k"]:
        raise SearchIntegrityError("k mismatch")

    reference = record["reference"]
    if reference["bound_type"] == "upper":
        witness = reference.get("witness")
        verification = verify_css_upper_bound_witness(hx_payload, hz_payload, witness)
        if (
            verification.get("status") != "pass"
            or verification.get("weight") != reference["value"]
        ):
            raise SearchIntegrityError("invalid upper witness")

    return ValidatedSuiteCase(
        record=record,
        hx_payload=hx_payload,
        hz_payload=hz_payload,
    )


def _validate_schema(schema_name: str, payload: dict, label: str) -> None:
    schema = _load_json_file(_SCHEMA_ROOT / schema_name, label="schema")
    validator = Draft202012Validator(schema)
    try:
        validator.validate(payload)
    except ValidationError as error:
        raise SearchIntegrityError(f"{label} schema violation") from error


def _load_json_at(root: Path, relative: Path, *, label: str) -> dict:
    return _load_json_file(_join_under(root, relative, label=label), label=label)


def _load_json_file(path: Path, *, label: str) -> dict:
    try:
        with path.open() as handle:
            payload = json.load(handle)
    except OSError as error:
        raise SearchIntegrityError(f"missing {label}") from error
    except json.JSONDecodeError as error:
        raise SearchIntegrityError(f"invalid {label}") from error
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid {label}")
    return payload


def _join_under(root: Path, relative: Path, *, label: str) -> Path:
    safe = _safe_relative_path(str(relative), label=label)
    root_resolved = root.resolve()
    joined = (root_resolved / safe).resolve()
    if joined != root_resolved and root_resolved not in joined.parents:
        raise SearchIntegrityError(f"unsafe {label}")
    return joined


def _safe_relative_path(value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(f"unsafe {label}")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise SearchIntegrityError(f"unsafe {label}")
    return path


def _sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _validate_dense_rows(rows: Iterable[Iterable[int]]) -> list[list[int]]:
    dense: list[list[int]] = []
    width: int | None = None
    for row in rows:
        normalized: list[int] = []
        for bit in row:
            if type(bit) is not int or bit not in (0, 1):
                raise SearchIntegrityError("row-space fingerprint requires binary rows")
            normalized.append(int(bit))
        if width is None:
            width = len(normalized)
        elif len(normalized) != width:
            raise SearchIntegrityError("row-space fingerprint row width mismatch")
        dense.append(normalized)
    return dense


def _rref_rows(rows: list[list[int]]) -> list[list[int]]:
    if not rows:
        return []
    work = [row[:] for row in rows if any(row)]
    if not work:
        return []

    rank = 0
    width = len(work[0])
    for column in range(width):
        pivot = next(
            (index for index in range(rank, len(work)) if work[index][column] == 1),
            None,
        )
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        for index in range(len(work)):
            if index != rank and work[index][column] == 1:
                work[index] = [
                    left ^ right for left, right in zip(work[index], work[rank], strict=True)
                ]
        rank += 1
        if rank == len(work):
            break

    nonzero = [row for row in work if any(row)]
    return sorted(nonzero, key=_pivot_column)


def _pivot_column(row: list[int]) -> int:
    return next(index for index, bit in enumerate(row) if bit)


def _matrix_num_cols(payload: dict, rows: list[list[int]], *, label: str) -> int:
    matrix_format = payload.get("format")
    if matrix_format == "dense_binary_matrix":
        num_cols = payload.get("n_cols")
    elif matrix_format == "sparse_rows":
        num_cols = payload.get("num_cols")
    else:
        raise SearchIntegrityError(f"unsupported matrix format: {label}")
    if type(num_cols) is not int or num_cols < 0:
        raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
    if any(len(row) != num_cols for row in rows):
        raise SearchIntegrityError(f"matrix column mismatch: {label}")
    return int(num_cols)


def _css_checks_commute(hx_rows: list[list[int]], hz_rows: list[list[int]]) -> bool:
    return all(
        sum(left & right for left, right in zip(hx_row, hz_row, strict=True)) % 2 == 0
        for hx_row in hx_rows
        for hz_row in hz_rows
    )


def _size_band(n: int) -> str:
    if n <= 128:
        return "small"
    if n <= 512:
        return "medium"
    return "large"
