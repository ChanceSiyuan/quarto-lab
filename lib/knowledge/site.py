"""Safely render the validated knowledge graph into the public Quarto site."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Protocol
from uuid import uuid4

from .quarto import QuartoProject, materialize_quarto_project
from .validate import KnowledgeValidationError, validate_knowledge


class ProcessRunner(Protocol):
    def run(
        self,
        command: str,
        args: tuple[str, ...],
        *,
        cwd: Path,
        shell: bool,
    ) -> None: ...


class AtomicDirectoryOps(Protocol):
    def rename(self, source: Path, destination: Path) -> None: ...

    def rm(self, path: Path) -> None: ...


class SubprocessRunner:
    def run(
        self,
        command: str,
        args: tuple[str, ...],
        *,
        cwd: Path,
        shell: bool,
    ) -> None:
        cache = cwd.parent / ".cache"
        cache.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["XDG_CACHE_HOME"] = str(cache)
        subprocess.run(
            [command, *args],
            cwd=cwd,
            check=True,
            env=environment,
            shell=shell,
        )


class LocalDirectoryOps:
    def rename(self, source: Path, destination: Path) -> None:
        source.rename(destination)

    def rm(self, path: Path) -> None:
        shutil.rmtree(path)


@contextmanager
def _materialized_project(
    *,
    repo_root: Path | str,
    workspace_prefix: str,
) -> Iterator[tuple[Path, QuartoProject]]:
    root = Path(repo_root).resolve()
    report = validate_knowledge(root)
    if not report.ok:
        raise KnowledgeValidationError(report.diagnostics)

    work_root = root / "work"
    work_root_was_created = not work_root.exists()
    work_root.mkdir(parents=True, exist_ok=True)
    workspace = Path(
        tempfile.mkdtemp(prefix=workspace_prefix, dir=work_root)
    )
    try:
        project = materialize_quarto_project(
            graph=report.graph,
            workspace=workspace,
        )
        yield root, project
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
        if work_root_was_created:
            try:
                work_root.rmdir()
            except OSError:
                pass


def _audit_rendered_site(output: Path) -> None:
    if output.is_symlink():
        raise RuntimeError("forbidden generated output: _site")

    forbidden_directories = {
        ".cache",
        ".jupyter_cache",
        ".knowledge",
        ".mypy_cache",
        ".pytest_cache",
        ".quarto",
        ".quarto_ipynb",
        "__pycache__",
        "_cache",
        "_freeze",
        "conference",
        "drafts",
        "literature",
        "work",
    }
    forbidden_suffixes = {
        ".bib",
        ".ipynb",
        ".lua",
        ".py",
        ".pyc",
        ".qmd",
        ".quarto_ipynb",
        ".sh",
        ".tex",
    }
    paths = sorted(
        output.rglob("*"),
        key=lambda path: (
            path.is_dir(),
            path.relative_to(output).as_posix(),
        ),
    )
    for path in paths:
        relative = path.relative_to(output)
        relative_text = relative.as_posix()
        if path.is_symlink():
            raise RuntimeError(
                f"forbidden generated output: {relative_text}"
            )
        parts = {part.casefold() for part in relative.parts}
        if parts.intersection(forbidden_directories) or (
            path.is_file() and path.suffix.casefold() in forbidden_suffixes
        ):
            raise RuntimeError(
                f"forbidden generated output: {relative_text}"
            )


def build_knowledge_site(
    *,
    repo_root: Path | str,
    quarto_bin: str = "quarto",
    runner: ProcessRunner | None = None,
    directory_ops: AtomicDirectoryOps | None = None,
) -> Path:
    ops = directory_ops or LocalDirectoryOps()
    with _materialized_project(
        repo_root=repo_root,
        workspace_prefix="knowledge-build-",
    ) as (root, project):
        project_dir = project.project_dir
        (runner or SubprocessRunner()).run(
            quarto_bin,
            ("render", ".", "--no-execute"),
            cwd=project_dir,
            shell=False,
        )
        rendered_site = project_dir / "_site"
        if not (rendered_site / "index.html").is_file():
            raise RuntimeError(
                "Quarto render did not produce _site/index.html"
            )
        _audit_rendered_site(rendered_site)

        output = root / "_site"
        backup = root / f".site-backup-{uuid4().hex}"
        had_previous_output = output.exists()
        if had_previous_output:
            ops.rename(output, backup)
        try:
            ops.rename(rendered_site, output)
        except BaseException:
            if output.exists():
                ops.rm(output)
            if had_previous_output and backup.exists():
                ops.rename(backup, output)
            raise
        if had_previous_output:
            ops.rm(backup)
        return output


def preview_knowledge_site(
    *,
    repo_root: Path | str,
    quarto_bin: str = "quarto",
    runner: ProcessRunner | None = None,
) -> None:
    with _materialized_project(
        repo_root=repo_root,
        workspace_prefix="knowledge-preview-",
    ) as (_, project):
        (runner or SubprocessRunner()).run(
            quarto_bin,
            ("preview", ".", "--no-browser", "--no-execute"),
            cwd=project.project_dir,
            shell=False,
        )
