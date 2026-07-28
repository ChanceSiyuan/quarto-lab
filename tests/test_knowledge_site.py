from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from lib.knowledge.site import (
    SubprocessRunner,
    build_knowledge_site,
    preview_knowledge_site,
)


ROOT = Path(__file__).resolve().parents[1]
VALID_FIXTURE = ROOT / "tests" / "fixtures" / "knowledge" / "valid"


class RejectingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], Path, bool]] = []

    def run(
        self,
        command: str,
        args: tuple[str, ...],
        *,
        cwd: Path,
        shell: bool,
    ) -> None:
        self.calls.append((command, args, cwd, shell))
        raise RuntimeError("fixture render failed")


class SuccessfulRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], Path, bool]] = []

    def run(
        self,
        command: str,
        args: tuple[str, ...],
        *,
        cwd: Path,
        shell: bool,
    ) -> None:
        self.calls.append((command, args, cwd, shell))
        rendered = cwd / "_site"
        (rendered / "theory" / "ising").mkdir(parents=True)
        (rendered / "index.html").write_bytes(b"verified-home")
        (rendered / "theory" / "ising" / "index.html").write_bytes(
            b"verified-topic"
        )


class LeakingRunner(SuccessfulRunner):
    def run(
        self,
        command: str,
        args: tuple[str, ...],
        *,
        cwd: Path,
        shell: bool,
    ) -> None:
        super().run(command, args, cwd=cwd, shell=shell)
        leak = cwd / "_site" / "drafts" / "secret.qmd"
        leak.parent.mkdir()
        leak.write_bytes(b"untrusted")


class OutputLeakingRunner(SuccessfulRunner):
    def __init__(self, leaked_path: str) -> None:
        super().__init__()
        self.leaked_path = leaked_path

    def run(
        self,
        command: str,
        args: tuple[str, ...],
        *,
        cwd: Path,
        shell: bool,
    ) -> None:
        super().run(command, args, cwd=cwd, shell=shell)
        leak = cwd / "_site" / self.leaked_path
        leak.parent.mkdir(parents=True, exist_ok=True)
        leak.write_bytes(b"generated-intermediate")


class SymlinkedOutputRunner(SuccessfulRunner):
    def run(
        self,
        command: str,
        args: tuple[str, ...],
        *,
        cwd: Path,
        shell: bool,
    ) -> None:
        self.calls.append((command, args, cwd, shell))
        rendered_target = cwd / "rendered-site-target"
        rendered_target.mkdir()
        (rendered_target / "index.html").write_bytes(b"unsafe-home")
        (cwd / "_site").symlink_to(rendered_target, target_is_directory=True)


class FailingFinalRenameOps:
    def __init__(self) -> None:
        self.rename_calls: list[tuple[Path, Path]] = []

    def rename(self, source: Path, destination: Path) -> None:
        self.rename_calls.append((source, destination))
        if source.parent.name == "project" and source.name == "_site":
            raise OSError("injected final rename failure")
        source.rename(destination)

    def rm(self, path: Path) -> None:
        shutil.rmtree(path)


class KnowledgeSiteBuildTest(unittest.TestCase):
    def test_failed_render_preserves_the_last_verified_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE, repo_root, dirs_exist_ok=True)
            output = repo_root / "_site"
            output.mkdir()
            sentinel = output / "sentinel.html"
            sentinel.write_bytes(b"last-known-good")
            runner = RejectingRunner()

            with self.assertRaisesRegex(RuntimeError, "fixture render failed"):
                build_knowledge_site(
                    repo_root=repo_root,
                    quarto_bin="fixture-quarto",
                    runner=runner,
                )

            self.assertEqual(sentinel.read_bytes(), b"last-known-good")
            self.assertEqual(len(runner.calls), 1)
            command, args, project_dir, shell = runner.calls[0]
            self.assertEqual(command, "fixture-quarto")
            self.assertEqual(args, ("render", ".", "--no-execute"))
            self.assertFalse(shell)
            self.assertTrue(project_dir.is_relative_to(repo_root / "work"))
            self.assertFalse((repo_root / "work").exists())

    def test_successful_render_atomically_replaces_the_old_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE, repo_root, dirs_exist_ok=True)
            output = repo_root / "_site"
            output.mkdir()
            (output / "sentinel.html").write_bytes(b"obsolete")
            runner = SuccessfulRunner()

            result = build_knowledge_site(
                repo_root=repo_root,
                quarto_bin="fixture-quarto",
                runner=runner,
            )

            self.assertEqual(result, output)
            self.assertFalse((output / "sentinel.html").exists())
            self.assertEqual(
                (output / "index.html").read_bytes(),
                b"verified-home",
            )
            self.assertEqual(
                (output / "theory" / "ising" / "index.html").read_bytes(),
                b"verified-topic",
            )
            self.assertFalse((repo_root / "work").exists())

    def test_forbidden_rendered_source_file_preserves_the_old_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE, repo_root, dirs_exist_ok=True)
            output = repo_root / "_site"
            output.mkdir()
            sentinel = output / "sentinel.html"
            sentinel.write_bytes(b"last-known-good")

            with self.assertRaisesRegex(
                RuntimeError,
                r"forbidden generated output: drafts/secret\.qmd",
            ):
                build_knowledge_site(
                    repo_root=repo_root,
                    quarto_bin="fixture-quarto",
                    runner=LeakingRunner(),
                )

            self.assertEqual(sentinel.read_bytes(), b"last-known-good")
            self.assertFalse((repo_root / "work").exists())

    def test_symlinked_rendered_site_root_preserves_the_old_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE, repo_root, dirs_exist_ok=True)
            output = repo_root / "_site"
            output.mkdir()
            sentinel = output / "sentinel.html"
            sentinel.write_bytes(b"last-known-good")

            with self.assertRaisesRegex(
                RuntimeError,
                "forbidden generated output:",
            ):
                build_knowledge_site(
                    repo_root=repo_root,
                    quarto_bin="fixture-quarto",
                    runner=SymlinkedOutputRunner(),
                )

            self.assertEqual(sentinel.read_bytes(), b"last-known-good")
            self.assertFalse((repo_root / "work").exists())

    def test_generated_caches_and_intermediates_preserve_the_old_site(self):
        leaked_paths = (
            "_freeze/chunk.json",
            ".quarto/session.json",
            ".cache/tool.db",
            ".pytest_cache/v/cache/nodeids",
            ".mypy_cache/3.11/helper.data.json",
            "_cache/chunk.html",
            "__pycache__/helper.cpython-311.pyc",
            "orphan.pyc",
            "notebook.quarto_ipynb",
            "filters/unsafe.lua",
        )
        for leaked_path in leaked_paths:
            with self.subTest(leaked_path=leaked_path):
                with tempfile.TemporaryDirectory() as temporary:
                    repo_root = Path(temporary)
                    shutil.copytree(
                        VALID_FIXTURE,
                        repo_root,
                        dirs_exist_ok=True,
                    )
                    output = repo_root / "_site"
                    output.mkdir()
                    sentinel = output / "sentinel.html"
                    sentinel.write_bytes(b"last-known-good")

                    with self.assertRaisesRegex(
                        RuntimeError,
                        "forbidden generated output:",
                    ):
                        build_knowledge_site(
                            repo_root=repo_root,
                            quarto_bin="fixture-quarto",
                            runner=OutputLeakingRunner(leaked_path),
                        )

                    self.assertEqual(
                        sentinel.read_bytes(),
                        b"last-known-good",
                    )
                    self.assertFalse((repo_root / "work").exists())

    def test_final_rename_failure_restores_the_old_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE, repo_root, dirs_exist_ok=True)
            output = repo_root / "_site"
            output.mkdir()
            sentinel = output / "sentinel.html"
            sentinel.write_bytes(b"last-known-good")
            directory_ops = FailingFinalRenameOps()

            with self.assertRaisesRegex(
                OSError,
                "injected final rename failure",
            ):
                build_knowledge_site(
                    repo_root=repo_root,
                    quarto_bin="fixture-quarto",
                    runner=SuccessfulRunner(),
                    directory_ops=directory_ops,
                )

            self.assertEqual(sentinel.read_bytes(), b"last-known-good")
            self.assertEqual(len(directory_ops.rename_calls), 3)
            self.assertEqual(
                list(repo_root.glob(".site-backup-*")),
                [],
            )
            self.assertFalse((repo_root / "work").exists())


class KnowledgeSitePreviewTest(unittest.TestCase):
    def test_preview_uses_the_same_safe_project_and_no_execute_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE, repo_root, dirs_exist_ok=True)
            output = repo_root / "_site"
            output.mkdir()
            sentinel = output / "sentinel.html"
            sentinel.write_bytes(b"last-known-good")
            runner = RejectingRunner()

            with self.assertRaisesRegex(RuntimeError, "fixture render failed"):
                preview_knowledge_site(
                    repo_root=repo_root,
                    quarto_bin="fixture-quarto",
                    runner=runner,
                )

            self.assertEqual(sentinel.read_bytes(), b"last-known-good")
            self.assertEqual(len(runner.calls), 1)
            command, args, project_dir, shell = runner.calls[0]
            self.assertEqual(command, "fixture-quarto")
            self.assertEqual(
                args,
                ("preview", ".", "--no-browser", "--no-execute"),
            )
            self.assertFalse(shell)
            self.assertTrue(project_dir.is_relative_to(repo_root / "work"))
            self.assertFalse((repo_root / "work").exists())


class SubprocessRunnerTest(unittest.TestCase):
    def test_quarto_cache_is_scoped_to_the_temporary_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            project_dir = Path(temporary) / "workspace" / "project"
            project_dir.mkdir(parents=True)

            with mock.patch("subprocess.run") as run:
                SubprocessRunner().run(
                    "quarto",
                    ("render", ".", "--no-execute"),
                    cwd=project_dir,
                    shell=False,
                )

            kwargs = run.call_args.kwargs
            self.assertEqual(
                kwargs["env"]["XDG_CACHE_HOME"],
                str(project_dir.parent / ".cache"),
            )
            self.assertTrue((project_dir.parent / ".cache").is_dir())
            self.assertFalse(kwargs["shell"])


if __name__ == "__main__":
    unittest.main()
