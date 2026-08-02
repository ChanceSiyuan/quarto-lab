from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import pty
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import termios
import threading
import time
import tty
import unittest
from pathlib import Path
from typing import Any


NATIVE = Path(__file__).resolve().parents[1]
HELPER = Path(os.environ.get("REMOTE_HELPER", NATIVE / "build" / "qlab-remote"))
HELPER_VERSION = "1.0.0"
UUID_PATTERN = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def json_line(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode() + b"\n"


def activation_hello(
    mode: str,
    *,
    request_id: str = "hello-1",
    activation_id: str = "activation-1",
    candidate_root: str | None = None,
    expected_host: str | None = None,
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    if capabilities is None:
        capabilities = {
            "browse": ["browse", "codex-probe"],
            "repository-handshake": [],
            "setup-auth": ["codex-device-auth-pty"],
        }[mode]
    return {
        "kind": "hello",
        "phase": "activation",
        "requestId": request_id,
        "protocolVersion": 1,
        "helperVersion": HELPER_VERSION,
        "activationId": activation_id,
        "mode": mode,
        "candidateRoot": candidate_root,
        "expectedHostInstanceId": expected_host,
        "requestedCapabilities": capabilities,
    }


def activation_context(server: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocolVersion": server["protocolVersion"],
        "helperVersion": server["helperVersion"],
        "activationId": server["activationId"],
        "hostInstanceId": server["hostInstanceId"],
        "capabilities": server["capabilities"],
    }


def invoke(
    argv: list[str],
    frames: list[dict[str, Any]] | bytes,
    *,
    env: dict[str, str],
    timeout: float = 8,
) -> subprocess.CompletedProcess[bytes]:
    payload = frames if isinstance(frames, bytes) else b"".join(json_line(frame) for frame in frames)
    return subprocess.run(
        [str(HELPER), *argv],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=timeout,
        check=False,
    )


def decoded_lines(output: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in output.splitlines()]


def init_repository(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [shutil.which("git") or "git", "init", "-q", str(path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_executable(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


class RemoteHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir(mode=0o700)
        self.repo = self.root / "repository"
        init_repository(self.repo)
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["LC_ALL"] = "C.UTF-8"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def repository_handshake(
        self,
        repo: Path | None = None,
        *,
        env: dict[str, str] | None = None,
        activation_id: str = "activation-1",
        expected_host: str | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        selected = (repo or self.repo).resolve()
        return invoke(
            ["repository-handshake"],
            [activation_hello(
                "repository-handshake",
                activation_id=activation_id,
                candidate_root=str(selected),
                expected_host=expected_host,
                capabilities=[],
            )],
            env=env or self.env,
        )

    def successful_repository_identity(self) -> dict[str, Any]:
        completed = self.repository_handshake()
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
        lines = decoded_lines(completed.stdout)
        self.assertEqual(len(lines), 1)
        return lines[0]

    def fake_git_environment(
        self,
        private_path: bytes,
        common_directory: bytes | None = None,
    ) -> dict[str, str]:
        fake_bin = self.root / f"fake-git-{time.time_ns()}"
        fake_bin.mkdir()
        write_executable(
            fake_bin / "git",
            f"#!{sys.executable}\n"
            "import base64, os, sys\n"
            "name = 'QLAB_TEST_GIT_COMMON' if '--git-common-dir' in sys.argv else 'QLAB_TEST_GIT_PATH'\n"
            "sys.stdout.buffer.write(base64.b64decode(os.environ[name]))\n",
        )
        env = self.env.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["QLAB_TEST_GIT_PATH"] = base64.b64encode(private_path).decode()
        common = common_directory or f"{self.repo.resolve()}/.git\n".encode()
        env["QLAB_TEST_GIT_COMMON"] = base64.b64encode(common).decode()
        return env

    def fake_codex_environment(
        self,
        *,
        version_output: bytes | None,
        version_exit: int = 0,
        login_exit: int = 0,
        raw_output: bytes = b"",
        device_auth_sleep: float = 0,
    ) -> tuple[dict[str, str], Path]:
        fake_bin = self.root / f"fake-codex-{time.time_ns()}"
        fake_bin.mkdir()
        marker = fake_bin / "calls.jsonl"
        encoded_version = base64.b64encode(version_output or b"").decode()
        encoded_raw = base64.b64encode(raw_output).decode()
        write_executable(
            fake_bin / "codex",
            f"#!{sys.executable}\n"
            "import base64, json, os, sys\n"
            "with open(os.environ['QLAB_CODEX_MARKER'], 'a', encoding='utf-8') as stream:\n"
            "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1:] == ['--version']:\n"
            f"    os.write(1, base64.b64decode('{encoded_version}'))\n"
            f"    raise SystemExit({version_exit})\n"
            "if sys.argv[1:] == ['login', 'status']:\n"
            f"    raise SystemExit({login_exit})\n"
            "if sys.argv[1:] == ['app-server', '--stdio']:\n"
            "    if os.environ.get('QLAB_CODEX_CWD_MARKER'):\n"
            "        with open(os.environ['QLAB_CODEX_CWD_MARKER'], 'w', encoding='utf-8') as stream:\n"
            "            stream.write(os.getcwd())\n"
            f"    os.write(1, base64.b64decode('{encoded_raw}'))\n"
            "    raise SystemExit(0)\n"
            "if sys.argv[1:] == ['login', '--device-auth']:\n"
            f"    os.write(1, base64.b64decode('{encoded_raw}'))\n"
            f"    import time; time.sleep({device_auth_sleep!r})\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(91)\n",
        )
        env = self.env.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["QLAB_CODEX_MARKER"] = str(marker)
        return env, marker

    def start_setup_through_two_ptys(self, env: dict[str, str]) -> dict[str, Any]:
        outer_master, outer_slave = pty.openpty()
        inner_master, inner_slave = pty.openpty()
        tty.setraw(outer_slave, termios.TCSANOW)
        # Model OpenSSH transmitting the already-raw local tty modes before
        # starting the remote command; the helper independently reapplies them.
        tty.setraw(inner_slave, termios.TCSANOW)
        process = subprocess.Popen(
            [str(HELPER), "setup", "codex-device-auth"],
            stdin=inner_slave,
            stdout=inner_slave,
            stderr=subprocess.PIPE,
            env=env,
            close_fds=True,
        )
        os.close(inner_slave)
        stopped = threading.Event()

        def relay() -> None:
            routes = {outer_slave: inner_master, inner_master: outer_slave}
            while not stopped.is_set():
                try:
                    ready, _, _ = select.select(list(routes), [], [], 0.1)
                except (OSError, ValueError):
                    return
                for source in ready:
                    try:
                        chunk = os.read(source, 4096)
                    except OSError:
                        return
                    if not chunk:
                        return
                    destination = routes[source]
                    view = memoryview(chunk)
                    while view:
                        try:
                            written = os.write(destination, view)
                        except OSError:
                            return
                        view = view[written:]

        relay_thread = threading.Thread(target=relay)
        relay_thread.start()
        return {
            "outer_master": outer_master,
            "outer_slave": outer_slave,
            "inner_master": inner_master,
            "process": process,
            "stopped": stopped,
            "relay": relay_thread,
        }

    def read_pty_until(self, descriptor: int, needle: bytes, timeout: float = 5) -> bytes:
        received = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and needle not in received:
            ready, _, _ = select.select([descriptor], [], [], 0.1)
            if not ready:
                continue
            try:
                received.extend(os.read(descriptor, 4096))
            except OSError:
                break
        return bytes(received)

    def close_setup_relay(self, session: dict[str, Any]) -> None:
        session["stopped"].set()
        for key in ["outer_master", "outer_slave", "inner_master"]:
            try:
                os.close(session[key])
            except OSError:
                pass
        session["relay"].join(timeout=2)

    def test_concurrent_real_helpers_converge_on_private_host_and_repository_uuids(self) -> None:
        # Break caught: check-then-write races allow different processes to report different IDs.
        def resolve(index: int) -> dict[str, Any]:
            completed = self.repository_handshake(activation_id=f"activation-{index}")
            self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
            return decoded_lines(completed.stdout)[0]

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            identities = list(pool.map(resolve, range(24)))

        hosts = {identity["hostInstanceId"] for identity in identities}
        repositories = {identity["repositoryUuid"] for identity in identities}
        self.assertEqual(len(hosts), 1)
        self.assertEqual(len(repositories), 1)
        self.assertRegex(next(iter(hosts)), UUID_PATTERN)
        self.assertRegex(next(iter(repositories)), UUID_PATTERN)
        self.assertEqual({identity["canonicalRoot"] for identity in identities}, {str(self.repo.resolve())})

        state = self.home / ".qlab" / "state"
        private = self.repo / ".git" / "qlab"
        self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((state / "host-instance-id").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((private / "repository-id").stat().st_mode), 0o600)
        self.assertEqual((state / "host-instance-id").read_text().rstrip("\n"), next(iter(hosts)))
        self.assertEqual((private / "repository-id").read_text().rstrip("\n"), next(iter(repositories)))

    def test_loser_waits_for_a_concurrent_uuid_publisher_to_finish(self) -> None:
        # Break caught: an O_EXCL loser immediately reads the winner's still-empty file.
        qlab = self.repo / ".git" / "qlab"
        qlab.mkdir(mode=0o700)
        identity = qlab / "repository-id"
        descriptor = os.open(identity, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        winner = "11111111-1111-4111-8111-111111111111"

        def finish_publication() -> None:
            time.sleep(0.1)
            os.write(descriptor, f"{winner}\n".encode())
            os.fsync(descriptor)
            os.close(descriptor)

        publisher = threading.Thread(target=finish_publication)
        publisher.start()
        completed = self.repository_handshake()
        publisher.join(timeout=2)

        self.assertFalse(publisher.is_alive())
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
        self.assertEqual(decoded_lines(completed.stdout)[0]["repositoryUuid"], winner)

    def test_a_complete_invalid_uuid_is_not_retried_as_concurrent_publication(self) -> None:
        # Break caught: retrying every invalid file lets stable corrupt state become valid mid-handshake.
        # Seed the independent host identity first so its initial durable fsync cannot consume
        # the replacement delay and turn this into a scheduler race on slower filesystems.
        self.successful_repository_identity()
        qlab = self.repo / ".git" / "qlab"
        identity = qlab / "repository-id"
        identity.write_text("x" * 36 + "\n")
        identity.chmod(0o600)
        replacement = "22222222-2222-4222-8222-222222222222\n"

        def replace_invalid_state() -> None:
            time.sleep(0.1)
            identity.write_text(replacement)
            identity.chmod(0o600)

        replacer = threading.Thread(target=replace_invalid_state)
        replacer.start()
        completed = self.repository_handshake()
        replacer.join(timeout=2)

        self.assertEqual(completed.returncode, 78)
        self.assertEqual(completed.stdout, b"")

    def test_fifo_uuid_is_rejected_without_blocking(self) -> None:
        # Break caught: blocking O_RDONLY waits forever before fstat can reject a FIFO.
        qlab = self.repo / ".git" / "qlab"
        qlab.mkdir(mode=0o700)
        identity = qlab / "repository-id"
        os.mkfifo(identity, mode=0o600)
        hello = activation_hello(
            "repository-handshake",
            candidate_root=str(self.repo.resolve()),
            capabilities=[],
        )
        process = subprocess.Popen(
            [str(HELPER), "repository-handshake"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
        )
        try:
            stdout, stderr = process.communicate(json_line(hello), timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=2)
            self.fail("helper blocked while opening a FIFO UUID")

        self.assertEqual(process.returncode, 78, stderr.decode(errors="replace"))
        self.assertEqual(stdout, b"")

    def test_creation_forces_private_modes_even_under_a_restrictive_umask(self) -> None:
        # Break caught: validating mkdir's umask-filtered mode before fchmod
        # leaves an unusable identity tree or reports a false identity failure.
        hello = activation_hello(
            "repository-handshake",
            candidate_root=str(self.repo.resolve()),
            capabilities=[],
        )
        result = subprocess.run(
            [str(HELPER), "repository-handshake"],
            input=json_line(hello),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            timeout=8,
            check=False,
            preexec_fn=lambda: os.umask(0o777),
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(stat.S_IMODE((self.home / ".qlab" / "state").stat().st_mode), 0o700)
        self.assertEqual(
            stat.S_IMODE((self.repo / ".git" / "qlab" / "repository-id").stat().st_mode),
            0o600,
        )

    def test_a_fresh_copy_has_a_distinct_git_private_uuid_but_the_same_host_uuid(self) -> None:
        first = self.successful_repository_identity()
        copied = self.root / "copied"
        shutil.copytree(self.repo, copied, ignore=shutil.ignore_patterns(".git"))
        init_repository(copied)
        second = decoded_lines(self.repository_handshake(copied).stdout)[0]

        self.assertEqual(first["hostInstanceId"], second["hostInstanceId"])
        self.assertNotEqual(first["repositoryUuid"], second["repositoryUuid"])

    def test_accepts_absolute_and_relative_git_private_path_output_without_whitespace_trimming(self) -> None:
        relative = self.fake_git_environment(b".git/qlab/repository-id\n")
        first = self.repository_handshake(env=relative)
        self.assertEqual(first.returncode, 0, first.stderr.decode(errors="replace"))

        shutil.rmtree(self.repo / ".git" / "qlab")
        absolute_path = f"{self.repo.resolve()}/.git/qlab/repository-id\n".encode()
        absolute = self.fake_git_environment(absolute_path)
        second = self.repository_handshake(env=absolute)
        self.assertEqual(second.returncode, 0, second.stderr.decode(errors="replace"))

        for malformed in [
            b" .git/qlab/repository-id\n",
            b".git/qlab/repository-id \n",
            b".git/qlab/repository-id\r\n",
            b".git/qlab/repository-id\x00\n",
            b".git/qlab/repository-id\nextra\n",
            b"../outside/qlab/repository-id\n",
            f"{self.root}/outside/qlab/repository-id\n".encode(),
        ]:
            with self.subTest(git_path=malformed):
                result = self.repository_handshake(env=self.fake_git_environment(malformed))
                self.assertEqual(result.returncode, 78)
                self.assertEqual(result.stdout, b"")

    def test_descriptor_relative_identity_rejects_unsafe_private_parent_and_file(self) -> None:
        cases = ["parent-symlink", "parent-file", "parent-mode", "file-symlink", "file-mode", "file-invalid"]
        for case in cases:
            with self.subTest(case=case):
                repo = self.root / f"repo-{case}"
                init_repository(repo)
                qlab = repo / ".git" / "qlab"
                target = repo / ".git" / "elsewhere"
                if case == "parent-symlink":
                    target.mkdir()
                    qlab.symlink_to(target, target_is_directory=True)
                elif case == "parent-file":
                    qlab.write_text("not a directory")
                else:
                    qlab.mkdir(mode=0o700)
                    identity = qlab / "repository-id"
                    if case == "parent-mode":
                        qlab.chmod(0o755)
                    elif case == "file-symlink":
                        target.write_text("11111111-1111-4111-8111-111111111111\n")
                        identity.symlink_to(target)
                    elif case == "file-mode":
                        identity.write_text("11111111-1111-4111-8111-111111111111\n")
                        identity.chmod(0o644)
                    elif case == "file-invalid":
                        identity.write_text("not-a-uuid\n")
                        identity.chmod(0o600)
                result = self.repository_handshake(repo)
                self.assertEqual(result.returncode, 78)

    def test_existing_owner_readonly_repository_uuid_is_accepted_without_rewrite(self) -> None:
        # Break caught: repository reads are specified to reject group/other
        # access, not to rewrite or reject an otherwise private 0400 file.
        qlab = self.repo / ".git" / "qlab"
        qlab.mkdir(mode=0o700)
        identity = qlab / "repository-id"
        expected = "11111111-1111-4111-8111-111111111111"
        identity.write_text(f"{expected}\n")
        identity.chmod(0o400)

        result = self.repository_handshake()

        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(decoded_lines(result.stdout)[0]["repositoryUuid"], expected)
        self.assertEqual(stat.S_IMODE(identity.stat().st_mode), 0o400)

    def test_host_identity_rejects_invalid_content_and_permissive_objects_before_git(self) -> None:
        for case in ["state-mode", "file-mode", "file-invalid", "file-symlink"]:
            with self.subTest(case=case):
                home = self.root / f"home-{case}"
                state = home / ".qlab" / "state"
                state.mkdir(parents=True, mode=0o700)
                identity = state / "host-instance-id"
                if case == "state-mode":
                    state.chmod(0o755)
                elif case == "file-symlink":
                    target = home / "outside"
                    target.write_text("11111111-1111-4111-8111-111111111111\n")
                    identity.symlink_to(target)
                else:
                    identity.write_text(
                        "invalid\n" if case == "file-invalid"
                        else "11111111-1111-4111-8111-111111111111\n"
                    )
                    identity.chmod(0o644 if case == "file-mode" else 0o600)
                env = self.env.copy()
                env["HOME"] = str(home)
                result = self.repository_handshake(env=env)
                self.assertEqual(result.returncode, 78)

    def test_browse_dispatches_only_the_four_closed_activation_methods(self) -> None:
        (self.home / "research").mkdir()
        (self.home / "资料").mkdir()
        (self.home / "paper.pdf").write_text("not a directory")
        (self.home / "linked").symlink_to(self.home / "research", target_is_directory=True)

        process = subprocess.Popen(
            [str(HELPER), "browse"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
        )
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(json_line(activation_hello(
            "browse", capabilities=["browse", "codex-probe"],
        )))
        process.stdin.flush()
        server = json.loads(process.stdout.readline())
        context = activation_context(server)
        requests = [
            {**context, "kind": "request", "id": "home-1", "method": "browse.home", "params": {}},
            {**context, "kind": "request", "id": "list-1", "method": "browse.listDirectories", "params": {"path": str(self.home.resolve())}},
            {**context, "kind": "request", "id": "canonical-1", "method": "browse.canonicalize", "params": {"input": str((self.home / "research").resolve())}},
        ]
        for request in requests:
            process.stdin.write(json_line(request))
        process.stdin.close()
        responses = [json.loads(process.stdout.readline()) for _ in requests]
        process.wait(timeout=5)

        self.assertEqual(responses[0]["result"], {"path": str(self.home.resolve())})
        self.assertEqual(
            responses[1]["result"]["entries"],
            [
                {"name": ".qlab", "path": str((self.home / ".qlab").resolve()), "kind": "directory"},
                {"name": "research", "path": str((self.home / "research").resolve()), "kind": "directory"},
                {"name": "资料", "path": str((self.home / "资料").resolve()), "kind": "directory"},
            ],
        )
        self.assertEqual(responses[2]["result"], {"path": str((self.home / "research").resolve())})
        process.stdout.close()
        assert process.stderr is not None
        process.stderr.close()

    def test_invalid_rpc_frames_terminate_with_typed_errors_without_starting_codex(self) -> None:
        env, marker = self.fake_codex_environment(version_output=b"codex-cli 99.0.0\n")
        invalid = [
            ({"method": "process.run", "params": {}}, "METHOD_NOT_ALLOWED"),
            ({"method": "browse.home", "params": {"command": "id"}}, "INVALID_REQUEST"),
            ({"method": "browse.listDirectories", "params": {}}, "INVALID_REQUEST"),
            ({"method": "browse.canonicalize", "params": {"input": 7}}, "INVALID_REQUEST"),
        ]
        for index, (fields, code) in enumerate(invalid):
            hello = activation_hello("browse", activation_id=f"activation-{index}")
            seed = self.successful_browse_server(hello, env)
            request = {
                **activation_context(seed),
                "kind": "request",
                "id": f"bad-{index}",
                **fields,
            }
            result = invoke(["browse"], [hello, request], env=env)
            lines = decoded_lines(result.stdout)
            self.assertEqual(result.returncode, 78)
            self.assertEqual(lines[-1]["kind"], "protocol-error")
            self.assertEqual(lines[-1]["code"], code)
        self.assertFalse(marker.exists())

    def test_fixed_codex_probe_cannot_read_protocol_stdin(self) -> None:
        # Break caught: a fixed child inherits stdin and consumes the next JSONL request.
        fake_bin = self.root / "stdin-probe-bin"
        fake_bin.mkdir()
        started = fake_bin / "started"
        observed = fake_bin / "observed"
        write_executable(
            fake_bin / "codex",
            f"#!{sys.executable}\n"
            "import os, sys, time\n"
            "if sys.argv[1:] == ['--version']:\n"
            f"    open({str(started)!r}, 'w').close()\n"
            "    time.sleep(0.2)\n"
            "    data = os.read(0, 1)\n"
            f"    open({str(observed)!r}, 'wb').write(data)\n"
            "    os.write(1, b'codex-cli 99.0.0\\n')\n"
            "    raise SystemExit(0)\n"
            "if sys.argv[1:] == ['login', 'status']:\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(91)\n",
        )
        env = self.env.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
        process = subprocess.Popen(
            [str(HELPER), "browse"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(json_line(activation_hello(
            "browse", capabilities=["browse", "codex-probe"],
        )))
        process.stdin.flush()
        server = json.loads(process.stdout.readline())
        context = activation_context(server)
        probe = {
            **context, "kind": "request", "id": "probe-stdin",
            "method": "codex.probe", "params": {},
        }
        followup = {
            **context, "kind": "request", "id": "home-after-probe",
            "method": "browse.home", "params": {},
        }
        process.stdin.write(json_line(probe))
        process.stdin.flush()
        deadline = time.monotonic() + 2
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(started.exists(), "fake Codex version probe did not start")
        process.stdin.write(json_line(followup))
        process.stdin.close()
        responses = [json.loads(process.stdout.readline()), json.loads(process.stdout.readline())]
        process.wait(timeout=5)
        process.stdout.close()
        assert process.stderr is not None
        process.stderr.close()

        self.assertEqual(observed.read_bytes(), b"")
        self.assertEqual([response.get("id") for response in responses], ["probe-stdin", "home-after-probe"])
        self.assertEqual(process.returncode, 0)

    def test_activation_capabilities_are_exact_for_the_fixed_mode(self) -> None:
        cases = [
            ("browse", None, ["browse"]),
            ("repository-handshake", str(self.repo.resolve()), ["repository-identity"]),
        ]
        for index, (mode, candidate, capabilities) in enumerate(cases):
            with self.subTest(mode=mode):
                home = self.root / f"capability-home-{index}"
                home.mkdir(mode=0o700)
                env = self.env.copy()
                env["HOME"] = str(home)
                result = invoke(
                    [mode],
                    [activation_hello(
                        mode,
                        candidate_root=candidate,
                        capabilities=capabilities,
                    )],
                    env=env,
                )
                self.assertEqual(result.returncode, 78)
                self.assertEqual(result.stdout, b"")
                self.assertFalse((home / ".qlab").exists())

    def successful_browse_server(
        self, hello: dict[str, Any], env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        completed = invoke(["browse"], [hello], env=env or self.env)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
        return decoded_lines(completed.stdout)[0]

    def test_duplicate_activation_request_id_terminates_with_duplicate_id(self) -> None:
        hello = activation_hello("browse")
        server = self.successful_browse_server(hello)
        request = {
            **activation_context(server),
            "kind": "request",
            "id": "same-id",
            "method": "browse.home",
            "params": {},
        }
        result = invoke(["browse"], [hello, request, request], env=self.env)
        lines = decoded_lines(result.stdout)
        self.assertEqual(lines[-1]["kind"], "protocol-error")
        self.assertEqual(lines[-1]["code"], "DUPLICATE_ID")
        self.assertEqual(result.returncode, 78)

    def test_codex_probe_maps_missing_incompatible_unauthenticated_and_ready(self) -> None:
        cases = [
            (None, None, "missing"),
            (b"codex-cli 0.145.9\n", 0, "incompatible"),
            (b"codex-cli 0.146.0\n", 1, "unauthenticated"),
            (b"codex 99.0.0\n", 0, "ready"),
        ]
        for index, (version, login_exit, expected) in enumerate(cases):
            with self.subTest(state=expected):
                if version is None:
                    empty_bin = self.root / f"empty-bin-{index}"
                    empty_bin.mkdir()
                    env = self.env.copy()
                    env["PATH"] = str(empty_bin)
                else:
                    env, _marker = self.fake_codex_environment(
                        version_output=version,
                        login_exit=login_exit or 0,
                    )
                hello = activation_hello("browse", activation_id=f"probe-{index}")
                server = self.successful_browse_server(hello, env)
                request = {
                    **activation_context(server),
                    "kind": "request",
                    "id": f"probe-request-{index}",
                    "method": "codex.probe",
                    "params": {},
                }
                result = invoke(["browse"], [hello, request], env=env)
                response = decoded_lines(result.stdout)[1]
                self.assertEqual(response["result"]["state"], expected)
                if expected == "incompatible":
                    self.assertEqual(response["result"]["minimumVersion"], "0.146.0")

    def test_bound_agent_checks_every_identity_before_fixed_codex_exec(self) -> None:
        identity = self.successful_repository_identity()
        env, marker = self.fake_codex_environment(
            version_output=b"codex-cli 99.0.0\n",
            raw_output=b'{"from":"codex"}\n',
        )
        cwd_marker = self.root / "agent-cwd"
        env["QLAB_CODEX_CWD_MARKER"] = str(cwd_marker)
        hello = {
            "kind": "hello",
            "phase": "bound",
            "requestId": "bound-hello",
            "protocolVersion": 1,
            "helperVersion": HELPER_VERSION,
            "mode": "agent",
            "targetId": "target-a",
            "targetEpoch": 9,
            "canonicalRoot": identity["canonicalRoot"],
            "expectedHostInstanceId": identity["hostInstanceId"],
            "expectedRepositoryUuid": identity["repositoryUuid"],
            "expectedRepositoryId": "repository-a",
            "requestedCapabilities": ["codex-app-server"],
        }
        result = invoke(["agent"], [hello], env=env)
        lines = decoded_lines(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(lines[0]["kind"], "hello")
        self.assertEqual(lines[0]["repositoryId"], "repository-a")
        self.assertEqual(lines[1]["kind"], "stream-ready")
        self.assertEqual(lines[2], {"from": "codex"})
        self.assertEqual(json.loads(marker.read_text().splitlines()[-1]), ["app-server", "--stdio"])
        self.assertEqual(cwd_marker.read_text(), identity["canonicalRoot"])

        mutations = [
            {"canonicalRoot": str(self.root)},
            {"expectedHostInstanceId": "33333333-3333-4333-8333-333333333333"},
            {"expectedRepositoryUuid": "44444444-4444-4444-8444-444444444444"},
            {"mode": "repository"},
        ]
        before = marker.read_text()
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                rejected = invoke(["agent"], [{**hello, **mutation}], env=env)
                self.assertEqual(rejected.returncode, 78)
        self.assertEqual(marker.read_text(), before)

    def test_bound_agent_rejects_unsafe_epoch_and_capabilities_before_side_effects(self) -> None:
        env, marker = self.fake_codex_environment(version_output=b"codex-cli 99.0.0\n")
        cases = [
            {"targetEpoch": 9_007_199_254_740_992, "requestedCapabilities": ["codex-app-server"]},
            {"targetEpoch": 1, "requestedCapabilities": ["browse"]},
        ]
        for index, mutation in enumerate(cases):
            with self.subTest(mutation=mutation):
                home = self.root / f"bound-invalid-home-{index}"
                home.mkdir(mode=0o700)
                case_env = env.copy()
                case_env["HOME"] = str(home)
                hello = {
                    "kind": "hello",
                    "phase": "bound",
                    "requestId": "bound-invalid",
                    "protocolVersion": 1,
                    "helperVersion": HELPER_VERSION,
                    "mode": "agent",
                    "targetId": "target-a",
                    "canonicalRoot": str(self.repo.resolve()),
                    "expectedHostInstanceId": "33333333-3333-4333-8333-333333333333",
                    "expectedRepositoryUuid": "44444444-4444-4444-8444-444444444444",
                    "expectedRepositoryId": "repository-a",
                    **mutation,
                }
                result = invoke(["agent"], [hello], env=case_env)
                self.assertEqual(result.returncode, 78)
                self.assertEqual(result.stdout, b"")
                self.assertFalse((home / ".qlab").exists())
        self.assertFalse(marker.exists())

    @unittest.skipUnless(hasattr(os, "openpty"), "requires a POSIX PTY")
    def test_setup_auth_switches_real_nested_pty_from_machine_frames_to_raw_codex_bytes(self) -> None:
        # Break caught: either local or remote PTY echoes the hello or rewrites raw bytes.
        env, marker = self.fake_codex_environment(
            version_output=b"codex-cli 99.0.0\n",
            raw_output=b"codex-raw\nnext\xff",
        )
        session = self.start_setup_through_two_ptys(env)
        process = session["process"]
        hello = json_line(activation_hello(
            "setup-auth", capabilities=["codex-device-auth-pty"],
        ))
        try:
            for start in range(0, len(hello), 3):
                os.write(session["outer_master"], hello[start:start + 3])
            received = self.read_pty_until(
                session["outer_master"], b"codex-raw\nnext\xff",
            )
            outer_settings = termios.tcgetattr(session["outer_slave"])
            inner_settings = termios.tcgetattr(session["inner_master"])
            process.wait(timeout=5)

            self.assertNotIn(hello.rstrip(b"\n"), received)
            self.assertNotIn(b"\r\n", received)
            for settings in [outer_settings, inner_settings]:
                self.assertFalse(settings[3] & (termios.ECHO | termios.ICANON))
                self.assertFalse(settings[1] & termios.OPOST)
            first_lf = received.index(b"\n")
            second_lf = received.index(b"\n", first_lf + 1)
            first = json.loads(received[:first_lf])
            second = json.loads(received[first_lf + 1:second_lf])
            self.assertEqual(first["kind"], "hello")
            self.assertEqual(second["kind"], "setup-ready")
            self.assertEqual(received[second_lf + 1:], b"codex-raw\nnext\xff")
            self.assertEqual(
                json.loads(marker.read_text().splitlines()[-1]),
                ["login", "--device-auth"],
            )
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            assert process.stderr is not None
            process.stderr.close()
            self.close_setup_relay(session)

    @unittest.skipUnless(hasattr(os, "openpty"), "requires a POSIX PTY")
    def test_setup_auth_rejects_wrong_capabilities_before_identity_or_codex(self) -> None:
        home = self.root / "setup-capability-home"
        home.mkdir(mode=0o700)
        env, marker = self.fake_codex_environment(version_output=b"codex-cli 99.0.0\n")
        env["HOME"] = str(home)
        session = self.start_setup_through_two_ptys(env)
        process = session["process"]
        try:
            os.write(session["outer_master"], json_line(activation_hello(
                "setup-auth", capabilities=[],
            )))
            process.wait(timeout=2)
            self.assertEqual(process.returncode, 78)
            self.assertFalse((home / ".qlab").exists())
            self.assertFalse(marker.exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            assert process.stderr is not None
            process.stderr.close()
            self.close_setup_relay(session)

    @unittest.skipUnless(hasattr(os, "openpty"), "requires a POSIX PTY")
    def test_setup_auth_cancel_closes_kills_and_reaps_once(self) -> None:
        env, marker = self.fake_codex_environment(
            version_output=b"codex-cli 99.0.0\n",
            raw_output=b"codex-waiting",
            device_auth_sleep=30,
        )
        session = self.start_setup_through_two_ptys(env)
        process = session["process"]
        hello = json_line(activation_hello(
            "setup-auth", capabilities=["codex-device-auth-pty"],
        ))
        kill_count = 0
        reap_count = 0
        cancelled = False

        def cancel() -> None:
            nonlocal cancelled, kill_count, reap_count
            if cancelled:
                return
            cancelled = True
            self.close_setup_relay(session)
            if process.poll() is None:
                process.kill()
                kill_count += 1
            process.wait(timeout=2)
            reap_count += 1

        try:
            os.write(session["outer_master"], hello)
            received = self.read_pty_until(session["outer_master"], b"codex-waiting")
            self.assertIn(b'"kind":"setup-ready"', received)
            self.assertTrue(received.endswith(b"codex-waiting"))
            cancel()
            cancel()
            self.assertEqual(kill_count, 1)
            self.assertEqual(reap_count, 1)
            self.assertEqual(
                [json.loads(line) for line in marker.read_text().splitlines()],
                [["login", "--device-auth"]],
            )
        finally:
            if not cancelled:
                cancel()
            assert process.stderr is not None
            process.stderr.close()

    def test_malformed_or_overlong_first_frame_exits_without_identity_or_output(self) -> None:
        malformed = b'{"kind":"hello","phase":"activation","extra":true}\n'
        overlong = b"{" + b"x" * (8 * 1024 * 1024) + b"}\n"
        for payload in [malformed, overlong, b'{"kind":"hello"}']:
            with self.subTest(size=len(payload)):
                result = invoke(["browse"], payload, env=self.env)
                self.assertEqual(result.returncode, 78)
                self.assertEqual(result.stdout, b"")
                self.assertFalse((self.home / ".qlab").exists())


if __name__ == "__main__":
    unittest.main()
