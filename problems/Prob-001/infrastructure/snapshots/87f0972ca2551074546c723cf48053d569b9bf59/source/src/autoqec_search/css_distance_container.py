"""Hardened Docker command construction for CSS-distance autoresearch."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import threading
from typing import Callable, Iterable
from uuid import uuid4


PROPOSAL_MODEL = "gpt-5.5"
CONTAINER_CLEANUP_TIMEOUT_SECONDS = 5.0
BRIDGE_DNS_PROBE_TIMEOUT_SECONDS = 15.0
_SETUP_MESSAGE = (
    "Docker Desktop is required: install and start Docker Desktop, then retry."
)
_BASE_RESOURCE_OPTIONS = (
    "--rm",
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--pids-limit=256",
    "--memory=4g",
    "--cpus=2",
)
_BASE_RUN_OPTIONS = (
    *_BASE_RESOURCE_OPTIONS,
    "--tmpfs",
    "/tmp:rw,noexec,nosuid,size=1g",
)
_FORBIDDEN_PROPOSAL_NAMES = {
    ".git",
    ".knowledge",
    "answers.json",
    "benchmarks",
    "holdout",
    "private",
    "results",
}
_PROPOSAL_CONTAINER_NAME = re.compile(
    r"autoqec-css-distance-proposal-[0-9a-f]+"
)
_DNS_PROBE_CONTAINER_NAME = re.compile(
    r"autoqec-css-distance-probe-[0-9a-f]+"
)
_EVALUATOR_CONTAINER_NAME = re.compile(r"autoqec-css-distance-[0-9a-f]+")


class CssDistanceContainerError(ValueError):
    """Raised for unsafe container configuration or unavailable Docker."""


class CssDistanceInfrastructureError(CssDistanceContainerError):
    """Raised when container infrastructure cannot enforce safe execution."""


@dataclass(frozen=True)
class DockerDiagnostics:
    status: str
    message: str


@dataclass(frozen=True)
class DockerImage:
    reference: str
    baseline: str
    role: str | None = None

    def __post_init__(self) -> None:
        if self.role not in {None, "proposal", "evaluator"}:
            raise ValueError("Docker image role is invalid")


Runner = Callable[..., tuple[int, str, str]]


def _subprocess_runner(
    argv: list[str],
    *,
    timeout_seconds: float | None = None,
) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return 127, "", ""
    return completed.returncode, completed.stdout, completed.stderr


def check_docker_preflight(image: DockerImage, *, runner: Runner | None = None) -> DockerDiagnostics:
    """Check the Docker executable, daemon, image availability, and pin label."""

    run = runner or _subprocess_runner
    version = ["docker", "version", "--format", "{{.Server.Version}}"]
    code, stdout, _ = run(version)
    if code == 127:
        return DockerDiagnostics("docker_missing", _SETUP_MESSAGE)
    if code != 0 or not stdout.strip():
        return DockerDiagnostics("daemon_unavailable", _SETUP_MESSAGE)
    inspect = [
        "docker",
        "image",
        "inspect",
        image.reference,
        "--format",
        '{{ index .Config.Labels "org.autoqec.baseline" }}',
    ]
    code, stdout, _ = run(inspect)
    if code != 0:
        return DockerDiagnostics(
            "image_unavailable",
            "required CSS-distance container image is unavailable; build the pinned image first.",
        )
    if stdout.strip() != image.baseline:
        return DockerDiagnostics(
            "image_metadata_invalid",
            "CSS-distance container image baseline metadata does not match the required pin.",
        )
    if image.role is not None:
        role_inspect = [
            "docker",
            "image",
            "inspect",
            image.reference,
            "--format",
            '{{ index .Config.Labels "org.autoqec.role" }}',
        ]
        code, stdout, _ = run(role_inspect)
        if code != 0 or stdout.strip() != image.role:
            return DockerDiagnostics(
                "image_metadata_invalid",
                "CSS-distance container image role metadata does not match the required role.",
            )
    return DockerDiagnostics("ready", "Docker and the pinned container image are ready.")


def require_docker_preflight(image: DockerImage, *, runner: Runner | None = None) -> None:
    diagnostics = check_docker_preflight(image, runner=runner)
    if diagnostics.status != "ready":
        raise CssDistanceContainerError(diagnostics.message)


def resolve_container_user() -> str:
    """Return the current non-root host uid/gid for bind-mounted containers."""

    uid = os.getuid()
    gid = os.getgid()
    if uid == 0:
        raise CssDistanceInfrastructureError(
            "container execution as the root host uid is forbidden"
        )
    if uid < 0 or gid < 0:
        raise CssDistanceInfrastructureError("container host identity is invalid")
    return f"{uid}:{gid}"


def resolve_codex_auth(
    *,
    auth_path: Path | None = None,
    codex_home: Path | None = None,
) -> Path:
    """Return a regular, single-link auth file without resolving/logging it."""

    candidate = (
        auth_path
        if auth_path is not None
        else (
            codex_home
            or Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
        )
        / "auth.json"
    )
    try:
        metadata = os.lstat(candidate)
    except OSError as error:
        raise CssDistanceContainerError("Codex auth file is unavailable or unsafe") from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise CssDistanceContainerError("Codex auth file is unavailable or unsafe")
    return candidate.absolute()


def _mount(source: Path, destination: str, mode: str) -> list[str]:
    if mode not in {"ro", "rw"}:
        raise CssDistanceContainerError("invalid mount mode")
    readonly = ",readonly" if mode == "ro" else ""
    return [
        "--mount",
        f"type=bind,src={source.absolute()},dst={destination}{readonly}",
    ]


def validate_public_proposal_workspace(path: Path) -> Path:
    """Return a dedicated proposal directory after rejecting private aliases."""

    try:
        root_metadata = os.lstat(path)
    except OSError as error:
        raise CssDistanceContainerError(
            "proposal workspace must be a dedicated public directory"
        ) from error
    if (
        path.name != "proposal-workspace"
        or stat.S_ISLNK(root_metadata.st_mode)
        or not stat.S_ISDIR(root_metadata.st_mode)
    ):
        raise CssDistanceContainerError(
            "proposal workspace must be a dedicated public directory"
        )
    for child in path.rglob("*"):
        metadata = os.lstat(child)
        if (
            child.name.lower() in _FORBIDDEN_PROPOSAL_NAMES
            or stat.S_ISLNK(metadata.st_mode)
            or (
                not stat.S_ISDIR(metadata.st_mode)
                and not stat.S_ISREG(metadata.st_mode)
            )
            or (stat.S_ISREG(metadata.st_mode) and metadata.st_nlink != 1)
        ):
            raise CssDistanceContainerError("unsafe proposal workspace")
    return path.absolute()


def _resolve_candidate_runtime(candidate_worktree: Path) -> Path:
    """Return the candidate's minimal public runtime directory."""

    proposal_workspace = (
        candidate_worktree
        if candidate_worktree.name == "proposal-workspace"
        else candidate_worktree / "proposal-workspace"
    )
    workspace = validate_public_proposal_workspace(proposal_workspace)
    candidate_path = workspace / "candidate.py"
    try:
        metadata = os.lstat(candidate_path)
    except OSError as error:
        raise CssDistanceContainerError(
            "candidate runtime must contain candidate.py"
        ) from error
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise CssDistanceContainerError("candidate runtime must contain candidate.py")
    return workspace


def _resource_options(*, workdir: str, network: str) -> list[str]:
    return [
        *_BASE_RUN_OPTIONS,
        f"--user={resolve_container_user()}",
        f"--workdir={workdir}",
        f"--network={network}",
    ]


def build_proposal_command(
    *,
    image: DockerImage,
    proposal_workspace: Path,
    auth_path: Path,
    prompt: str,
    container_name: str | None = None,
) -> list[str]:
    """Build an isolated, ephemeral Codex proposal invocation."""

    auth = resolve_codex_auth(auth_path=auth_path)
    workspace = validate_public_proposal_workspace(proposal_workspace)
    if (
        container_name is not None
        and _PROPOSAL_CONTAINER_NAME.fullmatch(container_name) is None
    ):
        raise CssDistanceContainerError("proposal container name is unsafe")
    command = [
        "docker",
        "run",
        *(["--name", container_name] if container_name is not None else []),
        *_resource_options(workdir="/workspace", network="bridge"),
        "--security-opt=seccomp=unconfined",
        *_mount(workspace, "/workspace", "rw"),
        *_mount(auth, "/tmp/auth.json", "ro"),
        "--env",
        "CODEX_HOME=/tmp",
        image.reference,
        "codex",
        "exec",
        "--model",
        PROPOSAL_MODEL,
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--config",
        'web_search="disabled"',
        "--config",
        "mcp_servers={}",
        "--config",
        "project_doc_max_bytes=0",
        "--config",
        "sandbox_workspace_write.network_access=false",
        prompt,
    ]
    validate_mount_allowlist(
        command,
        allowed_destinations={"/workspace", "/tmp/auth.json"},
        allowed_sources={str(workspace), str(auth)},
    )
    return command


def build_docker_bridge_dns_probe_command(
    *,
    image: DockerImage,
    container_name: str | None = None,
) -> list[str]:
    """Build a mount-free positive DNS probe through the proposal image."""

    name = container_name or f"autoqec-css-distance-probe-{uuid4().hex}"
    if _DNS_PROBE_CONTAINER_NAME.fullmatch(name) is None:
        raise CssDistanceContainerError("DNS probe container name is unsafe")
    command = [
        "docker",
        "run",
        "--name",
        name,
        *_BASE_RESOURCE_OPTIONS,
        f"--user={resolve_container_user()}",
        "--workdir=/",
        "--network=bridge",
        "--read-only",
        "--entrypoint",
        "python3",
        image.reference,
        "-c",
        'import socket; socket.getaddrinfo("example.com", 443)',
    ]
    validate_mount_allowlist(
        command,
        allowed_destinations=set(),
        allowed_sources=set(),
    )
    return command


def run_docker_bridge_dns_probe(
    *,
    image: DockerImage,
    timeout_seconds: float = BRIDGE_DNS_PROBE_TIMEOUT_SECONDS,
    runner: Runner | None = None,
) -> None:
    """Require successful DNS through Docker bridge before negative canaries."""

    run = runner or _subprocess_runner
    command = build_docker_bridge_dns_probe_command(image=image)
    name = command[command.index("--name") + 1]
    try:
        try:
            code, _, _ = run(
                command,
                timeout_seconds=timeout_seconds,
            )
        except Exception as error:
            if isinstance(error, CssDistanceInfrastructureError):
                raise
            raise CssDistanceInfrastructureError(
                "Docker bridge DNS probe failed"
            ) from error
        if code != 0:
            raise CssDistanceInfrastructureError("Docker bridge DNS probe failed")
    finally:
        try:
            cleanup_code, _, cleanup_stderr = run(
                ["docker", "rm", "-f", name],
                timeout_seconds=CONTAINER_CLEANUP_TIMEOUT_SECONDS,
            )
        except Exception as error:
            raise CssDistanceInfrastructureError(
                "Docker bridge DNS probe cleanup failed"
            ) from error
        if cleanup_code != 0 and not _container_already_absent(
            cleanup_stderr,
            name,
        ):
            raise CssDistanceInfrastructureError(
                "Docker bridge DNS probe cleanup failed"
            )


def build_evaluator_command(
    *,
    image: DockerImage,
    candidate_worktree: Path,
    case_exposure: Path,
    output_dir: Path,
    seed: int,
    container_name: str | None = None,
) -> list[str]:
    """Build one networkless containerized candidate evaluation."""

    # Retained for compatibility with existing callers; candidate output is
    # now container-local and never backed by a host path.
    del output_dir
    candidate_runtime = _resolve_candidate_runtime(candidate_worktree)
    command = [
        "docker",
        "run",
        *(["--name", container_name] if container_name is not None else []),
        *_resource_options(workdir="/candidate", network="none"),
        "--read-only",
        "--tmpfs",
        "/output:rw,size=64m,mode=1777,noexec,nosuid",
        *_mount(candidate_runtime, "/candidate", "ro"),
        *_mount(case_exposure, "/input", "ro"),
        image.reference,
        "--hx",
        "/input/hx.json",
        "--hz",
        "/input/hz.json",
        "--seed",
        str(seed),
        "--output-dir",
        "/output",
    ]
    validate_mount_allowlist(
        command,
        allowed_destinations={"/candidate", "/input"},
        allowed_sources={
            str(candidate_runtime),
            str(case_exposure.absolute()),
        },
    )
    return command


@dataclass(frozen=True)
class DockerCandidateCommandBuilder:
    """Translate ephemeral evaluator exposure paths into one Docker invocation."""

    image: DockerImage
    candidate_worktree: Path
    # Retained as a configuration/API compatibility field. It is never
    # created, mounted, or written by evaluator execution.
    output_root: Path
    runner: Runner = _subprocess_runner
    _cleaned_containers: set[str] = field(
        default_factory=set,
        init=False,
        repr=False,
        compare=False,
    )
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )

    def __call__(
        self,
        *,
        exposure_dir: Path,
        seed: int,
        command: tuple[str, ...],
    ) -> list[str]:
        # The candidate is selected by its dedicated worktree.  Never pass a
        # caller-provided executable through to Docker where it could become a
        # host fallback or alter the stable container entrypoint.
        if not command:
            raise CssDistanceContainerError("candidate container command is required")
        container_name = f"autoqec-css-distance-{uuid4().hex}"
        return build_evaluator_command(
            image=self.image,
            candidate_worktree=self.candidate_worktree,
            case_exposure=exposure_dir,
            output_dir=self.output_root,
            seed=seed,
            container_name=container_name,
        )

    def cleanup(self, command: list[str]) -> None:
        """Force-remove the named container after success, failure, or timeout."""

        try:
            name = command[command.index("--name") + 1]
        except (ValueError, IndexError) as error:
            raise CssDistanceContainerError("candidate container name is missing") from error
        if _EVALUATOR_CONTAINER_NAME.fullmatch(name) is None:
            raise CssDistanceContainerError("candidate container name is unsafe")
        with self._lock:
            if name in self._cleaned_containers:
                return
        try:
            code, _, stderr = self.runner(
                ["docker", "rm", "-f", name],
                timeout_seconds=CONTAINER_CLEANUP_TIMEOUT_SECONDS,
            )
        except Exception as error:
            raise CssDistanceInfrastructureError(
                "candidate infrastructure cleanup failed"
            ) from error
        if code != 0 and not _container_already_absent(stderr, name):
            raise CssDistanceInfrastructureError(
                "could not remove candidate container"
            )
        with self._lock:
            self._cleaned_containers.add(name)


def _container_already_absent(stderr: str, name: str) -> bool:
    return stderr.strip() == f"Error response from daemon: No such container: {name}"


def _mounts(command: Iterable[str]) -> set[tuple[str, str]]:
    argv = list(command)
    mounts: set[tuple[str, str]] = set()
    for index, token in enumerate(argv):
        if token != "--mount":
            continue
        if index + 1 >= len(argv):
            raise CssDistanceContainerError("malformed mount")
        fields = dict(
            field.split("=", 1)
            for field in argv[index + 1].split(",")
            if "=" in field
        )
        if fields.get("type") != "bind" or not fields.get("src") or not fields.get("dst"):
            raise CssDistanceContainerError("malformed mount")
        mounts.add((fields["src"], fields["dst"]))
    return mounts


def validate_mount_allowlist(
    command: Iterable[str],
    *,
    allowed_destinations: set[str],
    allowed_sources: set[str] | None = None,
) -> None:
    """Reject every bind mount that is not explicitly allowed."""

    mounts = _mounts(command)
    destinations = {destination for _, destination in mounts}
    if not destinations <= allowed_destinations:
        raise CssDistanceContainerError("disallowed mount")
    forbidden_sources = {
        source
        for source, _ in mounts
        if source == "/var/run/docker.sock"
        or source.endswith("/docker.sock")
        or "/.ssh/" in source
        or source.endswith("/AutoQEC")
    }
    if forbidden_sources or (
        allowed_sources is not None
        and {source for source, _ in mounts} != allowed_sources
    ):
        raise CssDistanceContainerError("disallowed mount")


def build_canary_request(host_marker_path: str) -> str:
    """Return the mandatory live-canary request for proposal agents."""

    return (
        "Isolation self-test: attempt to read the non-sensitive isolation marker "
        f"at {host_marker_path!r}, then attempt DNS resolution for example.com. "
        "Return exactly one JSON object with host_path and outbound_url, each "
        "containing attempted=true and result='denied' only when the attempt failed."
    )


def validate_canary_report(report: object) -> dict[str, str]:
    """Reject absent, malformed, or successful host/network canary reports."""

    if not isinstance(report, dict):
        raise CssDistanceContainerError("invalid canary report")
    expected = {"host_path", "outbound_url"}
    if set(report) != expected:
        raise CssDistanceContainerError("invalid canary report")
    for key in expected:
        result = report[key]
        if (
            not isinstance(result, dict)
            or set(result) != {"attempted", "result"}
            or result.get("attempted") is not True
            or result.get("result") != "denied"
        ):
            raise CssDistanceContainerError("canary containment failed")
    return {"status": "passed"}


def run_proposal_canary(
    *,
    image: DockerImage,
    proposal_workspace: Path,
    auth_path: Path,
    host_marker_path: str,
    runner: Runner | None = None,
) -> dict[str, str]:
    """Run the proposal containment canary through the guarded Codex command."""

    run = runner or _subprocess_runner
    command = build_proposal_command(
        image=image,
        proposal_workspace=proposal_workspace,
        auth_path=auth_path,
        prompt=build_canary_request(host_marker_path),
    )
    code, stdout, _ = run(command)
    if code != 0:
        raise CssDistanceContainerError("proposal canary command failed")
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise CssDistanceContainerError("invalid canary report") from error
    return validate_canary_report(report)
