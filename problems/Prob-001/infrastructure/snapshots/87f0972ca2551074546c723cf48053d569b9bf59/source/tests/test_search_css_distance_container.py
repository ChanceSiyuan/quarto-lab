from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

import pytest

from autoqec_search.css_distance_container import (
    CssDistanceContainerError,
    CssDistanceInfrastructureError,
    DockerCandidateCommandBuilder,
    DockerDiagnostics,
    DockerImage,
    build_docker_bridge_dns_probe_command,
    build_evaluator_command,
    build_proposal_command,
    check_docker_preflight,
    resolve_container_user,
    resolve_codex_auth,
    run_docker_bridge_dns_probe,
    run_proposal_canary,
    validate_canary_report,
    validate_mount_allowlist,
)
from autoqec_search.css_distance_eval import run_candidate_case


def _runner(responses: dict[tuple[str, ...], tuple[int, str, str]]):
    def run(argv: list[str]) -> tuple[int, str, str]:
        return responses.get(tuple(argv), (0, "", ""))

    return run


def test_missing_docker_returns_typed_macos_setup_diagnostic() -> None:
    diagnostics = check_docker_preflight(
        DockerImage("proposal:test", "baseline"),
        runner=_runner({("docker", "version", "--format", "{{.Server.Version}}"): (127, "", "")}),
    )

    assert diagnostics == DockerDiagnostics(
        status="docker_missing",
        message="Docker Desktop is required: install and start Docker Desktop, then retry.",
    )


def test_daemon_failure_returns_typed_macos_setup_diagnostic() -> None:
    diagnostics = check_docker_preflight(
        DockerImage("proposal:test", "baseline"),
        runner=_runner(
            {("docker", "version", "--format", "{{.Server.Version}}"): (1, "", "cannot connect")}
        ),
    )

    assert diagnostics.status == "daemon_unavailable"
    assert "start Docker Desktop" in diagnostics.message


def test_preflight_rejects_missing_image_or_baseline_label() -> None:
    image = DockerImage("proposal:test", "pinned-baseline")
    unavailable = check_docker_preflight(
        image,
        runner=_runner(
            {
                ("docker", "version", "--format", "{{.Server.Version}}"): (0, "27", ""),
                ("docker", "image", "inspect", "proposal:test", "--format", "{{ index .Config.Labels \"org.autoqec.baseline\" }}"): (1, "", ""),
            }
        ),
    )
    wrong_label = check_docker_preflight(
        image,
        runner=_runner(
            {
                ("docker", "version", "--format", "{{.Server.Version}}"): (0, "27", ""),
                ("docker", "image", "inspect", "proposal:test", "--format", "{{ index .Config.Labels \"org.autoqec.baseline\" }}"): (0, "other", ""),
            }
        ),
    )

    assert unavailable.status == "image_unavailable"
    assert wrong_label.status == "image_metadata_invalid"


@pytest.mark.parametrize("role_label", ["evaluator", ""])
def test_preflight_rejects_wrong_or_missing_image_role_label(
    role_label: str,
) -> None:
    image = DockerImage(
        "sha256:" + "1" * 64,
        "pinned-baseline",
        role="proposal",
    )
    baseline_inspect = (
        "docker",
        "image",
        "inspect",
        image.reference,
        "--format",
        '{{ index .Config.Labels "org.autoqec.baseline" }}',
    )
    role_inspect = (
        "docker",
        "image",
        "inspect",
        image.reference,
        "--format",
        '{{ index .Config.Labels "org.autoqec.role" }}',
    )

    diagnostics = check_docker_preflight(
        image,
        runner=_runner(
            {
                ("docker", "version", "--format", "{{.Server.Version}}"): (0, "27", ""),
                baseline_inspect: (0, "pinned-baseline", ""),
                role_inspect: (0, role_label, ""),
            }
        ),
    )

    assert diagnostics.status == "image_metadata_invalid"
    assert "role" in diagnostics.message


def test_proposal_command_mounts_only_public_workspace_and_redacted_auth(tmp_path: Path) -> None:
    worktree = tmp_path / "experiment"
    worktree.mkdir()
    proposal_workspace = worktree / "proposal-workspace"
    proposal_workspace.mkdir()
    auth = tmp_path / "deep" / "auth.json"
    auth.parent.mkdir()
    auth.write_text("{}")

    command = build_proposal_command(
        image=DockerImage("proposal:test", "baseline"),
        proposal_workspace=proposal_workspace,
        auth_path=auth,
        prompt="propose",
    )

    assert command[:4] == ["docker", "run", "--rm", "--cap-drop=ALL"]
    assert "--network=bridge" in command
    assert "--security-opt=no-new-privileges" in command
    assert "--security-opt=seccomp=unconfined" in command
    assert f"--user={os.getuid()}:{os.getgid()}" in command
    assert "--mount" in command
    mount_specs = [command[index + 1] for index, token in enumerate(command) if token == "--mount"]
    assert any(
        spec == f"type=bind,src={proposal_workspace},dst=/workspace"
        for spec in mount_specs
    )
    assert any(spec.endswith("dst=/tmp/auth.json,readonly") for spec in mount_specs)
    assert all(not spec.endswith((",rw", ",ro")) for spec in mount_specs)
    assert "CODEX_HOME=/tmp" in command
    assert str(auth) not in " ".join(command[command.index("proposal:test") + 1 :])
    assert "workspace-write" in command
    assert command[command.index("--model") + 1] == "gpt-5.5"
    assert 'web_search="disabled"' in command
    assert "mcp_servers={}" in command
    assert "sandbox_workspace_write.network_access=false" in command
    validate_mount_allowlist(command, allowed_destinations={"/workspace", "/tmp/auth.json"})


def test_container_user_is_numeric_host_identity_and_rejects_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autoqec_search.css_distance_container as container

    monkeypatch.setattr(container.os, "getuid", lambda: 501)
    monkeypatch.setattr(container.os, "getgid", lambda: 20)
    assert resolve_container_user() == "501:20"

    monkeypatch.setattr(container.os, "getuid", lambda: 0)
    with pytest.raises(CssDistanceInfrastructureError, match="root"):
        resolve_container_user()


def test_proposal_command_inserts_only_validated_container_name(tmp_path: Path) -> None:
    proposal_workspace = tmp_path / "proposal-workspace"
    proposal_workspace.mkdir()
    auth = tmp_path / "auth.json"
    auth.write_text("{}")

    command = build_proposal_command(
        image=DockerImage("proposal:test", "baseline"),
        proposal_workspace=proposal_workspace,
        auth_path=auth,
        prompt="propose",
        container_name="autoqec-css-distance-proposal-deadbeef",
    )

    assert command[:4] == [
        "docker",
        "run",
        "--name",
        "autoqec-css-distance-proposal-deadbeef",
    ]
    with pytest.raises(CssDistanceContainerError, match="container name"):
        build_proposal_command(
            image=DockerImage("proposal:test", "baseline"),
            proposal_workspace=proposal_workspace,
            auth_path=auth,
            prompt="propose",
            container_name="unsafe-name",
        )


def test_proposal_command_rejects_worktree_root_and_symlink_content(tmp_path: Path) -> None:
    worktree = tmp_path / "experiment"
    worktree.mkdir()
    auth = tmp_path / "auth.json"
    auth.write_text("{}")

    with pytest.raises(
        CssDistanceContainerError,
        match="proposal workspace must be a dedicated public directory",
    ):
        build_proposal_command(
            image=DockerImage("proposal:test", "baseline"),
            proposal_workspace=worktree,
            auth_path=auth,
            prompt="propose",
        )

    proposal_workspace = worktree / "proposal-workspace"
    proposal_workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, proposal_workspace / "linked")
    with pytest.raises(CssDistanceContainerError, match="unsafe proposal workspace"):
        build_proposal_command(
            image=DockerImage("proposal:test", "baseline"),
            proposal_workspace=proposal_workspace,
            auth_path=auth,
            prompt="propose",
        )


def test_proposal_command_rejects_private_marker_content(tmp_path: Path) -> None:
    proposal_workspace = tmp_path / "proposal-workspace"
    proposal_workspace.mkdir()
    (proposal_workspace / "answers.json").write_text("{}")
    auth = tmp_path / "auth.json"
    auth.write_text("{}")

    with pytest.raises(CssDistanceContainerError, match="unsafe proposal workspace"):
        build_proposal_command(
            image=DockerImage("proposal:test", "baseline"),
            proposal_workspace=proposal_workspace,
            auth_path=auth,
            prompt="propose",
        )


def test_mount_audit_rejects_private_socket_or_autqec_leakage() -> None:
    command = [
        "docker",
        "run",
        "--mount",
        "type=bind,src=/Users/me/AutoQEC,dst=/repo,ro",
        "image",
    ]

    with pytest.raises(CssDistanceContainerError, match="disallowed mount"):
        validate_mount_allowlist(command, allowed_destinations={"/workspace"})

    socket_command = [
        "docker",
        "run",
        "--mount",
        "type=bind,src=/var/run/docker.sock,dst=/workspace,rw",
        "image",
    ]
    with pytest.raises(CssDistanceContainerError, match="disallowed mount"):
        validate_mount_allowlist(
            socket_command,
            allowed_destinations={"/workspace"},
            allowed_sources={"/var/run/docker.sock"},
        )


def test_auth_rejects_symlink_hardlink_and_redacts_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    auth = tmp_path / "auth.json"
    auth.write_text("{}")
    linked = tmp_path / "linked.json"
    os.symlink(auth, linked)
    hardlinked = tmp_path / "hardlinked.json"
    os.link(auth, hardlinked)

    with pytest.raises(CssDistanceContainerError) as symlink_error:
        resolve_codex_auth(auth_path=linked)
    with pytest.raises(CssDistanceContainerError) as hardlink_error:
        resolve_codex_auth(auth_path=hardlinked)

    assert str(linked) not in str(symlink_error.value)
    assert str(hardlinked) not in str(hardlink_error.value)


def test_auth_resolves_default_codex_home_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    auth = codex_home / "auth.json"
    auth.write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert resolve_codex_auth() == auth.absolute()


def test_evaluator_command_is_networkless_readonly_and_exposes_only_case(tmp_path: Path) -> None:
    candidate = tmp_path / "proposal-workspace"
    exposure = tmp_path / "exposure"
    output = tmp_path / "output"
    for path in (candidate, exposure, output):
        path.mkdir()
    (candidate / "candidate.py").write_text("print('candidate')\n")

    command = build_evaluator_command(
        image=DockerImage("evaluator:test", "baseline"),
        candidate_worktree=candidate,
        case_exposure=exposure,
        output_dir=output,
        seed=17,
    )

    text = " ".join(command)
    assert "--network=none" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges" in command
    mount_specs = [command[index + 1] for index, token in enumerate(command) if token == "--mount"]
    assert any(spec.endswith("dst=/candidate,readonly") for spec in mount_specs)
    assert any(spec.endswith("dst=/input,readonly") for spec in mount_specs)
    assert not any("dst=/output" in spec for spec in mount_specs)
    assert set(
        command[index + 1]
        for index, token in enumerate(command)
        if token == "--tmpfs"
    ) >= {
        "/output:rw,size=64m,mode=1777,noexec,nosuid",
    }
    assert all(not spec.endswith((",rw", ",ro")) for spec in mount_specs)
    assert "--hx" in command and "/input/hx.json" in command
    assert "--hz" in command and "/input/hz.json" in command
    validate_mount_allowlist(command, allowed_destinations={"/candidate", "/input"})


def test_docker_bridge_dns_probe_uses_proposal_image_without_mounts() -> None:
    image = DockerImage("proposal:test", "baseline")

    command = build_docker_bridge_dns_probe_command(image=image)
    second = build_docker_bridge_dns_probe_command(image=image)

    assert command[:3] == ["docker", "run", "--name"]
    name = command[3]
    assert re.fullmatch(r"autoqec-css-distance-probe-[0-9a-f]+", name)
    assert second[3] != name
    assert "--network=bridge" in command
    assert image.reference in command
    assert "--mount" not in command
    assert "--tmpfs" not in command
    assert "--env" not in command
    assert "auth.json" not in " ".join(command)
    assert "--entrypoint" in command
    assert command[command.index("--entrypoint") + 1] == "python3"
    script = command[command.index("-c") + 1]
    assert 'socket.getaddrinfo("example.com", 443)' in script
    validate_mount_allowlist(
        command,
        allowed_destinations=set(),
        allowed_sources=set(),
    )

    with pytest.raises(CssDistanceContainerError, match="name.*unsafe"):
        build_docker_bridge_dns_probe_command(
            image=image,
            container_name="unsafe probe name",
        )


def test_docker_bridge_dns_probe_success_always_force_cleans_named_container() -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    run_docker_bridge_dns_probe(
        image=DockerImage("proposal:test", "baseline"),
        timeout_seconds=9.0,
        runner=lambda argv, **kwargs: (
            calls.append((argv, kwargs)) or (0, "", "")
        ),
    )

    assert calls[0][1] == {"timeout_seconds": 9.0}
    name = calls[0][0][calls[0][0].index("--name") + 1]
    assert calls[1] == (
        ["docker", "rm", "-f", name],
        {"timeout_seconds": 5.0},
    )


@pytest.mark.parametrize("probe_failure", ["nonzero", "timeout"])
def test_docker_bridge_dns_probe_failure_still_force_cleans(
    probe_failure: str,
) -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], **kwargs: object) -> tuple[int, str, str]:
        calls.append(argv)
        if argv[:2] == ["docker", "run"]:
            if probe_failure == "nonzero":
                return 1, "", "resolution failed"
            raise subprocess.TimeoutExpired(argv, kwargs["timeout_seconds"])
        return 0, "", ""

    with pytest.raises(CssDistanceInfrastructureError, match="DNS"):
        run_docker_bridge_dns_probe(
            image=DockerImage("proposal:test", "baseline"),
            timeout_seconds=9.0,
            runner=runner,
        )

    name = calls[0][calls[0].index("--name") + 1]
    assert calls[1] == ["docker", "rm", "-f", name]


def test_docker_bridge_dns_probe_cleanup_accepts_exact_already_absent() -> None:
    def runner(argv: list[str], **kwargs: object) -> tuple[int, str, str]:
        if argv[:2] == ["docker", "run"]:
            return 0, "", ""
        name = argv[-1]
        return 1, "", f"Error response from daemon: No such container: {name}\n"

    run_docker_bridge_dns_probe(
        image=DockerImage("proposal:test", "baseline"),
        timeout_seconds=9.0,
        runner=runner,
    )


@pytest.mark.parametrize("cleanup_failure", ["nonzero", "timeout", "error"])
def test_docker_bridge_dns_probe_cleanup_failure_is_infrastructure(
    cleanup_failure: str,
) -> None:
    def runner(argv: list[str], **kwargs: object) -> tuple[int, str, str]:
        if argv[:2] == ["docker", "run"]:
            return 0, "", ""
        if cleanup_failure == "nonzero":
            return 1, "", "daemon unavailable"
        if cleanup_failure == "timeout":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout_seconds"])
        raise OSError("docker transport unavailable")

    with pytest.raises(CssDistanceInfrastructureError, match="cleanup"):
        run_docker_bridge_dns_probe(
            image=DockerImage("proposal:test", "baseline"),
            timeout_seconds=9.0,
            runner=runner,
        )


def test_evaluator_mounts_only_validated_public_workspace_from_algorithm_root(
    tmp_path: Path,
) -> None:
    algorithm_root = tmp_path / "algorithm"
    proposal_workspace = algorithm_root / "proposal-workspace"
    proposal_workspace.mkdir(parents=True)
    (proposal_workspace / "candidate.py").write_text("print('candidate')\n")
    (algorithm_root / "private").mkdir()
    (algorithm_root / "private" / "answers.json").write_text("{}")
    (algorithm_root / "benchmarks").mkdir()
    exposure = tmp_path / "exposure"
    output = tmp_path / "output"
    exposure.mkdir()
    output.mkdir()

    for candidate_input in (algorithm_root, proposal_workspace):
        command = build_evaluator_command(
            image=DockerImage("evaluator:test", "baseline"),
            candidate_worktree=candidate_input,
            case_exposure=exposure,
            output_dir=output,
            seed=17,
        )
        candidate_mounts = [
            spec
            for index, token in enumerate(command)
            if token == "--mount"
            for spec in [command[index + 1]]
            if "dst=/candidate" in spec
        ]

        assert candidate_mounts == [
            f"type=bind,src={proposal_workspace.absolute()},dst=/candidate,readonly"
        ]
        assert str(algorithm_root / "private") not in " ".join(command)
        assert str(algorithm_root / "benchmarks") not in " ".join(command)


def test_evaluator_rejects_missing_or_unsafe_candidate_runtime(tmp_path: Path) -> None:
    proposal_workspace = tmp_path / "proposal-workspace"
    proposal_workspace.mkdir()
    exposure = tmp_path / "exposure"
    output = tmp_path / "output"
    exposure.mkdir()
    output.mkdir()

    with pytest.raises(CssDistanceContainerError, match="candidate.py"):
        build_evaluator_command(
            image=DockerImage("evaluator:test", "baseline"),
            candidate_worktree=proposal_workspace,
            case_exposure=exposure,
            output_dir=output,
            seed=17,
        )

    (proposal_workspace / "candidate.py").write_text("print('candidate')\n")
    (proposal_workspace / "private").mkdir()
    with pytest.raises(CssDistanceContainerError, match="unsafe proposal workspace"):
        build_evaluator_command(
            image=DockerImage("evaluator:test", "baseline"),
            candidate_worktree=proposal_workspace,
            case_exposure=exposure,
            output_dir=output,
            seed=17,
        )


def test_docker_candidate_builder_uses_no_host_output_and_force_cleans_container(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "proposal-workspace"
    exposure = tmp_path / "exposure"
    output = tmp_path / "output-must-not-exist"
    for path in (candidate, exposure):
        path.mkdir()
    (candidate / "candidate.py").write_text("print('candidate')\n")
    cleaned: list[tuple[list[str], dict[str, object]]] = []
    builder = DockerCandidateCommandBuilder(
        image=DockerImage("evaluator:test", "baseline"),
        candidate_worktree=candidate,
        output_root=output,
        runner=lambda argv, **kwargs: (
            cleaned.append((argv, kwargs)) or (0, "", "")
        ),
    )

    command = builder(
        exposure_dir=exposure,
        seed=17,
        command=("candidate-entrypoint",),
    )
    name = command[command.index("--name") + 1]
    assert name.startswith("autoqec-css-distance-")
    assert all(
        "dst=/output" not in command[index + 1]
        for index, token in enumerate(command)
        if token == "--mount"
    )
    assert "/output:rw,size=64m,mode=1777,noexec,nosuid" in command
    assert not output.exists()

    builder.cleanup(command)

    assert cleaned == [
        (["docker", "rm", "-f", name], {"timeout_seconds": 5.0})
    ]
    assert not output.exists()


def test_docker_candidate_cleanup_accepts_exact_already_absent_response(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "proposal-workspace"
    exposure = tmp_path / "exposure"
    candidate.mkdir()
    exposure.mkdir()
    (candidate / "candidate.py").write_text("print('candidate')\n")

    cleanup_calls: list[list[str]] = []

    def already_gone(
        argv: list[str], **kwargs: object
    ) -> tuple[int, str, str]:
        cleanup_calls.append(argv)
        assert kwargs == {"timeout_seconds": 5.0}
        name = argv[-1]
        return 1, "", f"Error response from daemon: No such container: {name}\n"

    builder = DockerCandidateCommandBuilder(
        image=DockerImage("evaluator:test", "baseline"),
        candidate_worktree=candidate,
        output_root=tmp_path / "output",
        runner=already_gone,
    )
    command = builder(
        exposure_dir=exposure,
        seed=91,
        command=("candidate-entrypoint",),
    )

    builder.cleanup(command)
    builder.cleanup(command)

    assert not (tmp_path / "output").exists()
    assert cleanup_calls == [["docker", "rm", "-f", command[command.index("--name") + 1]]]


def test_docker_candidate_cleanup_surfaces_remove_failure(tmp_path: Path) -> None:
    candidate = tmp_path / "proposal-workspace"
    candidate.mkdir()
    (candidate / "candidate.py").write_text("print('candidate')\n")
    exposure = tmp_path / "exposure"
    exposure.mkdir()
    builder = DockerCandidateCommandBuilder(
        image=DockerImage("evaluator:test", "baseline"),
        candidate_worktree=candidate,
        output_root=tmp_path / "output",
        runner=lambda argv, **kwargs: (1, "", "daemon error"),
    )
    command = builder(
        exposure_dir=exposure,
        seed=17,
        command=("candidate-entrypoint",),
    )

    with pytest.raises(CssDistanceInfrastructureError, match="remove candidate container"):
        builder.cleanup(command)
    assert not (tmp_path / "output").exists()


def test_docker_candidate_cleanup_timeout_is_bounded_without_host_output(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "proposal-workspace"
    exposure = tmp_path / "exposure"
    candidate.mkdir()
    exposure.mkdir()
    (candidate / "candidate.py").write_text("print('candidate')\n")

    def timeout(argv: list[str], **kwargs: object) -> tuple[int, str, str]:
        raise subprocess.TimeoutExpired(argv, kwargs["timeout_seconds"])

    builder = DockerCandidateCommandBuilder(
        image=DockerImage("evaluator:test", "baseline"),
        candidate_worktree=candidate,
        output_root=tmp_path / "output",
        runner=timeout,
    )
    command = builder(
        exposure_dir=exposure,
        seed=17,
        command=("candidate-entrypoint",),
    )
    with pytest.raises(CssDistanceInfrastructureError, match="cleanup"):
        builder.cleanup(command)

    assert not (tmp_path / "output").exists()


def test_canary_requires_both_denials_and_well_formed_report() -> None:
    request = json.loads(validate_canary_report.__module__ and '{"host_path":{"attempted":true,"result":"denied"},"outbound_url":{"attempted":true,"result":"denied"}}')
    canary_prompt = __import__(
        "autoqec_search.css_distance_container",
        fromlist=["build_canary_request"],
    ).build_canary_request("/host/isolation-marker")
    assert "non-sensitive isolation marker" in canary_prompt
    assert "example.com" in canary_prompt
    assert "canary.invalid" not in canary_prompt
    assert "secret" not in canary_prompt.lower()
    assert "fetch" not in canary_prompt.lower()
    assert validate_canary_report(request)["status"] == "passed"
    for invalid in (
        {},
        {"host_path": {"attempted": True, "result": "denied"}},
        {"host_path": {"attempted": True, "result": "success"}, "outbound_url": {"attempted": True, "result": "denied"}},
    ):
        with pytest.raises(CssDistanceContainerError, match="canary"):
            validate_canary_report(invalid)


def test_run_proposal_canary_invokes_guarded_codex_command(tmp_path: Path) -> None:
    worktree = tmp_path / "experiment"
    worktree.mkdir()
    proposal_workspace = worktree / "proposal-workspace"
    proposal_workspace.mkdir()
    auth = tmp_path / "auth.json"
    auth.write_text("{}")
    captured: dict[str, object] = {}

    def runner(argv: list[str]) -> tuple[int, str, str]:
        captured["argv"] = argv
        return (
            0,
            json.dumps(
                {
                    "host_path": {"attempted": True, "result": "denied"},
                    "outbound_url": {"attempted": True, "result": "denied"},
                }
            ),
            "",
        )

    result = run_proposal_canary(
        image=DockerImage("proposal:test", "baseline"),
        proposal_workspace=proposal_workspace,
        auth_path=auth,
        host_marker_path="/host/isolation-marker.txt",
        runner=runner,
    )

    assert result == {"status": "passed"}
    command = captured["argv"]
    assert command[:4] == ["docker", "run", "--rm", "--cap-drop=ALL"]
    assert "sandbox_workspace_write.network_access=false" in command
    assert "non-sensitive isolation marker" in command[-1]
    assert "/host/isolation-marker.txt" in command[-1]


def test_run_proposal_canary_rejects_non_json_or_successful_reports(tmp_path: Path) -> None:
    worktree = tmp_path / "experiment"
    worktree.mkdir()
    proposal_workspace = worktree / "proposal-workspace"
    proposal_workspace.mkdir()
    auth = tmp_path / "auth.json"
    auth.write_text("{}")

    with pytest.raises(CssDistanceContainerError, match="invalid canary report"):
        run_proposal_canary(
            image=DockerImage("proposal:test", "baseline"),
            proposal_workspace=proposal_workspace,
            auth_path=auth,
            host_marker_path="/host/isolation-marker.txt",
            runner=lambda argv: (0, "not json", ""),
        )

    with pytest.raises(CssDistanceContainerError, match="canary containment failed"):
        run_proposal_canary(
            image=DockerImage("proposal:test", "baseline"),
            proposal_workspace=proposal_workspace,
            auth_path=auth,
            host_marker_path="/host/isolation-marker.txt",
            runner=lambda argv: (
                0,
                json.dumps(
                    {
                        "host_path": {"attempted": True, "result": "success"},
                        "outbound_url": {"attempted": True, "result": "denied"},
                    }
                ),
                "",
            ),
        )


def test_secure_command_builder_receives_ephemeral_exposure_paths(tmp_path: Path) -> None:
    case = tmp_path / "case"
    case.mkdir()
    matrix = {"format": "dense_binary_matrix", "n_rows": 1, "n_cols": 4, "data": [[1, 1, 0, 0]]}
    (case / "hx.json").write_text(json.dumps(matrix))
    matrix["data"] = [[0, 0, 1, 1]]
    (case / "hz.json").write_text(json.dumps(matrix))
    captured: dict[str, object] = {}

    def transport(*, exposure_dir: Path, seed: int, command: tuple[str, ...]) -> list[str]:
        captured.update({"exposure_dir": exposure_dir, "seed": seed, "command": command})
        return [
            __import__("sys").executable,
            "-c",
            "import json; print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],'upper_bound':2}))",
        ]

    result = run_candidate_case(
        command=["candidate-entrypoint"],
        command_builder=transport,
        case={"case_id": "case-0001", "hx_path": case / "hx.json", "hz_path": case / "hz.json"},
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "completed"
    assert captured["seed"] == 7
    assert captured["command"] == ("candidate-entrypoint",)
    assert not Path(captured["exposure_dir"]).exists()


def test_container_assets_are_pinned_and_do_not_embed_secrets() -> None:
    root = Path(__file__).resolve().parents[1] / "containers" / "css-distance-autoresearch"
    proposal = (root / "proposal.Dockerfile").read_text()
    evaluator = (root / "evaluator.Dockerfile").read_text()
    requirements = (root / "requirements.txt").read_text()

    assert "CODEDISTANCE_COMMIT" in proposal
    assert "org.autoqec.baseline" in proposal
    assert "codex" in proposal.lower()
    assert "codex" not in evaluator.lower()
    assert "--no-install-recommends" in proposal
    assert "--no-install-recommends" in evaluator
    assert "build-essential" in proposal
    assert "build-essential" in evaluator
    assert "==" in requirements
