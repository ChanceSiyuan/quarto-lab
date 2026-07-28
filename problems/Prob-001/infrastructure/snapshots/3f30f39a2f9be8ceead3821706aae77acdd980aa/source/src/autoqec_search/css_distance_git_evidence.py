"""Exact, immutable Git evidence pins for CSS-distance campaign inputs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Callable

from autoqec_search.css_distance_container import CssDistanceInfrastructureError


GitReader = Callable[..., str]
_CONTROLLED_GIT_ENVIRONMENT = frozenset(
    {"GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"}
)
_OBJECT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_SYMBOLIC_REF = re.compile(r"refs/heads/[A-Za-z0-9._/-]+")
_MAX_GIT_INDIRECTION_BYTES = 4096


def sanitized_git_environment(
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return a Git environment without caller-controlled repository plumbing."""

    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("GIT_")
    }
    for name, value in (overrides or {}).items():
        if name.startswith("GIT_") and name not in _CONTROLLED_GIT_ENVIRONMENT:
            raise ValueError("unsupported controlled Git environment variable")
        environment[name] = value
    return environment


def run_git(root: Path, *args: str) -> str:
    """Run read-only Git plumbing against the repository selected by ``root``."""

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            env=sanitized_git_environment(),
            text=True,
        )
    except OSError:
        raise OSError("Git evidence is unavailable") from None
    if result.returncode != 0:
        raise OSError("Git evidence is unavailable")
    return result.stdout.strip()


@dataclass(frozen=True)
class EvidenceIdentity:
    device: int
    inode: int
    mode: int
    links: int
    size: int
    modified_ns: int
    changed_ns: int


@dataclass(frozen=True)
class DirectoryIdentity:
    device: int
    inode: int
    mode: int


@dataclass(frozen=True)
class WorktreeBindingPin:
    repository_root: Path
    worktree_root: Path
    common_dir: Path
    admin_dir: Path
    dot_git_path: Path
    dot_git_identity: EvidenceIdentity
    commondir_path: Path
    commondir_identity: EvidenceIdentity
    gitdir_path: Path
    gitdir_identity: EvidenceIdentity
    common_identity: DirectoryIdentity
    admin_identity: DirectoryIdentity
    listing: str
    root_record: tuple[str, str, str]
    worktree_record: tuple[str, str, str]
    branch: str
    head: str


@dataclass(frozen=True)
class EvidencePin:
    root: Path
    path: Path
    relative: str
    label: str
    maximum: int
    head: str
    symbolic_head: str
    object_format: str
    blob: str
    git_mode: str
    identity: EvidenceIdentity


@dataclass(frozen=True)
class CommittedTextEvidence:
    text: str
    pin: EvidencePin


def _identity(metadata: os.stat_result) -> EvidenceIdentity:
    return EvidenceIdentity(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=metadata.st_mode,
        links=metadata.st_nlink,
        size=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
        changed_ns=metadata.st_ctime_ns,
    )


def _read_bytes(path: Path, *, maximum: int) -> tuple[bytes, EvidenceIdentity]:
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > maximum
        ):
            raise ValueError("evidence file is unsafe")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity = _identity(before)
    if (
        len(payload) > maximum
        or len(payload) != before.st_size
        or _identity(after) != identity
        or _identity(os.lstat(path)) != identity
    ):
        raise ValueError("evidence changed during descriptor read")
    return payload, identity


def _directory_identity(path: Path) -> DirectoryIdentity:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("Git directory is unsafe")
    return DirectoryIdentity(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=metadata.st_mode,
    )


def _canonical_directory(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    resolved = absolute.resolve(strict=True)
    if resolved != absolute:
        raise ValueError("Git directory path is not canonical")
    _directory_identity(absolute)
    return absolute


def _absolute_git_path(cwd: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = cwd / path
    return Path(os.path.abspath(path))


def _parse_worktree_listing(
    listing: str,
) -> dict[Path, tuple[str, str, str]]:
    if not listing or "\0" in listing:
        raise ValueError("worktree listing is invalid")
    records: dict[Path, tuple[str, str, str]] = {}
    for block in listing.split("\n\n"):
        lines = tuple(block.splitlines())
        if (
            len(lines) != 3
            or not lines[0].startswith("worktree ")
            or not lines[1].startswith("HEAD ")
            or not lines[2].startswith("branch ")
        ):
            raise ValueError("worktree listing is invalid")
        path = Path(lines[0].removeprefix("worktree "))
        head = lines[1].removeprefix("HEAD ")
        branch = lines[2].removeprefix("branch ")
        if (
            not path.is_absolute()
            or _OBJECT_ID.fullmatch(head) is None
            or _SYMBOLIC_REF.fullmatch(branch) is None
            or path in records
        ):
            raise ValueError("worktree listing is invalid")
        records[path] = lines
    return records


def capture_linked_worktree_binding(
    repository_root: Path,
    worktree_root: Path,
    *,
    expected_branch: str,
    expected_head: str | None = None,
    listing: str | None = None,
    git_reader: GitReader = run_git,
) -> WorktreeBindingPin:
    """Pin one linked worktree to its canonical primary repository."""

    repository_root = _canonical_directory(repository_root)
    worktree_root = _canonical_directory(worktree_root)
    if _SYMBOLIC_REF.fullmatch(expected_branch) is None:
        raise ValueError("expected worktree branch is invalid")
    root_top = _canonical_directory(
        Path(git_reader(repository_root, "rev-parse", "--show-toplevel"))
    )
    if root_top != repository_root:
        raise ValueError("repository root is invalid")
    common_dir = _canonical_directory(
        _absolute_git_path(
            repository_root,
            git_reader(
                repository_root,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ),
        )
    )
    root_admin = _canonical_directory(
        Path(git_reader(repository_root, "rev-parse", "--absolute-git-dir"))
    )
    if common_dir != repository_root / ".git" or root_admin != common_dir:
        raise ValueError("repository common directory is invalid")

    dot_git_path = worktree_root / ".git"
    dot_git_payload, dot_git_identity = _read_bytes(
        dot_git_path,
        maximum=_MAX_GIT_INDIRECTION_BYTES,
    )
    try:
        dot_git_text = dot_git_payload.decode("utf-8")
    except UnicodeError as error:
        raise ValueError("linked worktree indirection is invalid") from error
    match = re.fullmatch(r"gitdir: ([^\0\r\n]+)\n", dot_git_text)
    if match is None:
        raise ValueError("linked worktree indirection is invalid")
    admin_value = Path(match.group(1))
    if not admin_value.is_absolute():
        raise ValueError("linked worktree indirection is invalid")
    admin_dir = _canonical_directory(admin_value)
    if admin_dir.parent != common_dir / "worktrees":
        raise ValueError("linked worktree admin directory is invalid")
    commondir_path = admin_dir / "commondir"
    commondir_payload, commondir_identity = _read_bytes(
        commondir_path,
        maximum=_MAX_GIT_INDIRECTION_BYTES,
    )
    gitdir_path = admin_dir / "gitdir"
    gitdir_payload, gitdir_identity = _read_bytes(
        gitdir_path,
        maximum=_MAX_GIT_INDIRECTION_BYTES,
    )
    if (
        commondir_payload != b"../..\n"
        or gitdir_payload != f"{dot_git_path}\n".encode("utf-8")
    ):
        raise ValueError("linked worktree admin indirection is invalid")

    actual_admin = _canonical_directory(
        Path(git_reader(worktree_root, "rev-parse", "--absolute-git-dir"))
    )
    actual_common = _canonical_directory(
        _absolute_git_path(
            worktree_root,
            git_reader(
                worktree_root,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ),
        )
    )
    actual_top = _canonical_directory(
        Path(git_reader(worktree_root, "rev-parse", "--show-toplevel"))
    )
    branch = git_reader(worktree_root, "symbolic-ref", "-q", "HEAD")
    head = git_reader(worktree_root, "rev-parse", "--verify", "HEAD^{commit}")
    if (
        actual_admin != admin_dir
        or actual_common != common_dir
        or actual_top != worktree_root
        or branch != expected_branch
        or _OBJECT_ID.fullmatch(head) is None
        or (expected_head is not None and head != expected_head)
    ):
        raise ValueError("linked worktree repository binding is invalid")

    captured_listing = listing
    if captured_listing is None:
        captured_listing = git_reader(
            repository_root,
            "worktree",
            "list",
            "--porcelain",
        )
    records = _parse_worktree_listing(captured_listing)
    root_record = records.get(repository_root)
    worktree_record = records.get(worktree_root)
    root_branch = git_reader(repository_root, "symbolic-ref", "-q", "HEAD")
    root_head = git_reader(
        repository_root,
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
    )
    if (
        root_record is None
        or worktree_record is None
        or root_record
        != (
            f"worktree {repository_root}",
            f"HEAD {root_head}",
            f"branch {root_branch}",
        )
        or worktree_record
        != (
            f"worktree {worktree_root}",
            f"HEAD {head}",
            f"branch {branch}",
        )
    ):
        raise ValueError("linked worktree topology binding is invalid")
    return WorktreeBindingPin(
        repository_root=repository_root,
        worktree_root=worktree_root,
        common_dir=common_dir,
        admin_dir=admin_dir,
        dot_git_path=dot_git_path,
        dot_git_identity=dot_git_identity,
        commondir_path=commondir_path,
        commondir_identity=commondir_identity,
        gitdir_path=gitdir_path,
        gitdir_identity=gitdir_identity,
        common_identity=_directory_identity(common_dir),
        admin_identity=_directory_identity(admin_dir),
        listing=captured_listing,
        root_record=root_record,
        worktree_record=worktree_record,
        branch=branch,
        head=head,
    )


def validate_worktree_binding_identity(pin: WorktreeBindingPin) -> None:
    """Validate retained local worktree indirection without Git subprocesses."""

    try:
        _, dot_git_identity = _read_bytes(
            pin.dot_git_path,
            maximum=_MAX_GIT_INDIRECTION_BYTES,
        )
        commondir_payload, commondir_identity = _read_bytes(
            pin.commondir_path,
            maximum=_MAX_GIT_INDIRECTION_BYTES,
        )
        gitdir_payload, gitdir_identity = _read_bytes(
            pin.gitdir_path,
            maximum=_MAX_GIT_INDIRECTION_BYTES,
        )
        if (
            dot_git_identity != pin.dot_git_identity
            or commondir_payload != b"../..\n"
            or commondir_identity != pin.commondir_identity
            or gitdir_payload != f"{pin.dot_git_path}\n".encode("utf-8")
            or gitdir_identity != pin.gitdir_identity
            or _directory_identity(pin.common_dir) != pin.common_identity
            or _directory_identity(pin.admin_dir) != pin.admin_identity
        ):
            raise ValueError("linked worktree identity drifted")
    except (OSError, ValueError):
        raise ValueError("linked worktree identity drifted") from None


def _nul_records(output: str) -> list[str]:
    if output == "":
        return []
    records = output.split("\0")
    if records.pop() != "" or any(record == "" for record in records):
        raise ValueError("Git evidence records are not canonical")
    return records


def _tree_entry(
    output: str,
    *,
    relative: str,
    object_format: str,
) -> tuple[str, str]:
    records = _nul_records(output)
    if len(records) != 1:
        raise ValueError("tree entry is not unique")
    metadata, separator, path = records[0].partition("\t")
    fields = metadata.split()
    object_id_length = 40 if object_format == "sha1" else 64
    if (
        separator != "\t"
        or path != relative
        or len(fields) != 3
        or fields[0] not in {"100644", "100755"}
        or fields[1] != "blob"
        or re.fullmatch(rf"[0-9a-f]{{{object_id_length}}}", fields[2]) is None
    ):
        raise ValueError("tree entry is not canonical")
    return fields[0], fields[2]


def _blob_id(payload: bytes, *, object_format: str) -> str:
    if object_format not in {"sha1", "sha256"}:
        raise ValueError("unsupported Git object format")
    digest = hashlib.new(object_format)
    digest.update(f"blob {len(payload)}\0".encode("ascii"))
    digest.update(payload)
    return digest.hexdigest()


def _symbolic_head(git_reader: GitReader, root: Path) -> str:
    reference = git_reader(root, "symbolic-ref", "-q", "HEAD")
    if re.fullmatch(r"refs/heads/[A-Za-z0-9._/-]+", reference) is None:
        raise ValueError("symbolic HEAD is invalid")
    return reference


def read_committed_text_evidence(
    root: Path,
    path: Path,
    *,
    label: str,
    maximum: int,
    git_reader: GitReader = run_git,
    missing_ok: bool = False,
) -> CommittedTextEvidence | None:
    """Read one canonical HEAD blob from an exact bounded local descriptor."""

    try:
        relative = path.relative_to(root).as_posix()
        head = git_reader(root, "rev-parse", "--verify", "HEAD^{commit}")
        symbolic_head = _symbolic_head(git_reader, root)
        object_format = git_reader(root, "rev-parse", "--show-object-format")
        object_id_length = 40 if object_format == "sha1" else 64
        if (
            object_format not in {"sha1", "sha256"}
            or re.fullmatch(rf"[0-9a-f]{{{object_id_length}}}", head) is None
        ):
            raise ValueError("repository identity is invalid")
        tree_output = git_reader(root, "ls-tree", "-z", head, "--", relative)
        tracked_output = git_reader(root, "ls-files", "-z", "--", relative)
        tracked = _nul_records(tracked_output)
        if tree_output == "" and missing_ok:
            if (
                git_reader(root, "rev-parse", "--verify", "HEAD^{commit}")
                != head
                or _symbolic_head(git_reader, root) != symbolic_head
                or git_reader(root, "ls-tree", "-z", head, "--", relative)
                != ""
                or git_reader(root, "ls-files", "-z", "--", relative) != ""
                or git_reader(root, "rev-parse", "--verify", "HEAD^{commit}")
                != head
                or _symbolic_head(git_reader, root) != symbolic_head
            ):
                raise ValueError("missing evidence changed during validation")
            return None
        if tracked != [relative]:
            raise ValueError("tracking output is not canonical")
        git_mode, blob = _tree_entry(
            tree_output,
            relative=relative,
            object_format=object_format,
        )
        payload, identity = _read_bytes(path, maximum=maximum)
        if (
            _blob_id(payload, object_format=object_format) != blob
            or bool(identity.mode & 0o111) != (git_mode == "100755")
        ):
            raise ValueError("working evidence differs from HEAD")
        if (
            git_reader(root, "rev-parse", "--verify", "HEAD^{commit}") != head
            or _symbolic_head(git_reader, root) != symbolic_head
            or git_reader(root, "ls-files", "-z", "--", relative)
            != tracked_output
            or git_reader(root, "ls-tree", "-z", head, "--", relative)
            != tree_output
            or _identity(os.lstat(path)) != identity
            or git_reader(root, "rev-parse", "--verify", "HEAD^{commit}")
            != head
            or _symbolic_head(git_reader, root) != symbolic_head
        ):
            raise ValueError("evidence changed during validation")
        return CommittedTextEvidence(
            text=payload.decode("utf-8"),
            pin=EvidencePin(
                root=root,
                path=path,
                relative=relative,
                label=label,
                maximum=maximum,
                head=head,
                symbolic_head=symbolic_head,
                object_format=object_format,
                blob=blob,
                git_mode=git_mode,
                identity=identity,
            ),
        )
    except (OSError, UnicodeError, ValueError, AssertionError):
        raise CssDistanceInfrastructureError(
            f"committed {label} evidence is invalid"
        ) from None


def validate_evidence_pin(
    pin: EvidencePin,
    *,
    git_reader: GitReader = run_git,
) -> None:
    """Fail closed if a retained evidence pin no longer names the same bytes."""

    try:
        payload, identity = _read_bytes(pin.path, maximum=pin.maximum)
        tracked = git_reader(
            pin.root,
            "ls-files",
            "-z",
            "--",
            pin.relative,
        )
        tree = git_reader(
            pin.root,
            "ls-tree",
            "-z",
            pin.head,
            "--",
            pin.relative,
        )
        mode, blob = _tree_entry(
            tree,
            relative=pin.relative,
            object_format=pin.object_format,
        )
        if (
            identity != pin.identity
            or git_reader(
                pin.root,
                "rev-parse",
                "--verify",
                "HEAD^{commit}",
            )
            != pin.head
            or _symbolic_head(git_reader, pin.root) != pin.symbolic_head
            or git_reader(pin.root, "rev-parse", "--show-object-format")
            != pin.object_format
            or _nul_records(tracked) != [pin.relative]
            or mode != pin.git_mode
            or blob != pin.blob
            or _blob_id(payload, object_format=pin.object_format) != pin.blob
            or git_reader(
                pin.root,
                "rev-parse",
                "--verify",
                "HEAD^{commit}",
            )
            != pin.head
            or _symbolic_head(git_reader, pin.root) != pin.symbolic_head
        ):
            raise ValueError("pinned evidence drifted")
    except (OSError, UnicodeError, ValueError, AssertionError):
        raise CssDistanceInfrastructureError(
            f"committed {pin.label} evidence drifted"
        ) from None


def validate_evidence_identity(pin: EvidencePin) -> None:
    """Check cheap local identity drift without rereading already-pinned bytes."""

    try:
        if _identity(os.lstat(pin.path)) != pin.identity:
            raise ValueError("pinned evidence identity drifted")
    except (OSError, ValueError):
        raise CssDistanceInfrastructureError(
            f"committed {pin.label} evidence drifted"
        ) from None
