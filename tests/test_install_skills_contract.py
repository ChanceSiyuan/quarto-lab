from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _github_source(source: str) -> tuple[str, str]:
    parts = source.split("/")
    if len(parts) < 3:
        raise AssertionError(f"expected owner/repository/path source, got {source!r}")
    return f"https://github.com/{parts[0]}/{parts[1]}.git", "/".join(parts[2:])


class SkillPinContractTest(unittest.TestCase):
    def test_installer_remains_an_executable_command(self):
        self.assertNotEqual(
            (ROOT / "scripts" / "install_skills.sh").stat().st_mode & 0o111,
            0,
        )

    def test_every_remote_skill_has_an_explicit_lock_matching_revision(self):
        with (ROOT / "Ion.toml").open("rb") as handle:
            manifest = tomllib.load(handle)
        with (ROOT / "Ion.lock").open("rb") as handle:
            lock = tomllib.load(handle)

        locked = {entry["name"]: entry for entry in lock["skill"]}
        remote = {
            name: entry
            for name, entry in manifest["skills"].items()
            if isinstance(entry, dict) and entry.get("type") != "local"
        }

        self.assertEqual(len(remote), 9)
        for name, entry in remote.items():
            expected_source, expected_path = _github_source(entry["source"])
            self.assertRegex(entry.get("rev", ""), r"^[0-9a-f]{40}$", name)
            self.assertEqual(locked[name]["source"], expected_source, name)
            self.assertEqual(locked[name]["path"], expected_path, name)
            self.assertEqual(locked[name]["commit"], entry["rev"], name)

    def test_every_manifest_skill_has_a_lock_entry(self):
        with (ROOT / "Ion.toml").open("rb") as handle:
            manifest = tomllib.load(handle)
        with (ROOT / "Ion.lock").open("rb") as handle:
            lock = tomllib.load(handle)

        self.assertEqual(
            set(manifest["skills"]),
            {entry["name"] for entry in lock["skill"]},
        )


class SkillInstallTransactionTest(unittest.TestCase):
    def _project(self, manifest: str, lock: str, fake_ion: str) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="skills-install-contract-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)

        (root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts" / "install_skills.sh", root / "scripts")
        (root / "Ion.toml").write_text(
            textwrap.dedent(manifest).lstrip(),
            encoding="utf-8",
        )
        (root / "Ion.lock").write_text(
            textwrap.dedent(lock).lstrip(),
            encoding="utf-8",
        )
        (root / "skills" / "fixture").mkdir(parents=True)
        (root / "skills" / "fixture" / "SKILL.md").write_text(
            "---\nname: fixture\ndescription: Test fixture.\n---\n\nFixture.\n",
            encoding="utf-8",
        )

        for consumer in (".agents", ".claude"):
            sentinel = root / consumer / "skills" / "sentinel" / "KEEP"
            sentinel.parent.mkdir(parents=True)
            sentinel.write_text(f"{consumer} must survive\n", encoding="utf-8")

        ion = root / "fake-bin" / "ion"
        ion.parent.mkdir(parents=True)
        ion.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            + textwrap.dedent(fake_ion).lstrip(),
            encoding="utf-8",
        )
        ion.chmod(0o755)
        return root

    def _run(
        self,
        root: Path,
        extra_environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PATH"] = (
            f"{root / 'fake-bin'}:{ROOT / '.venv' / 'bin'}:{environment['PATH']}"
        )
        environment["ION_ADD_MARKER"] = str(root / "ion-add-called")
        environment.update(extra_environment or {})
        return subprocess.run(
            ["bash", "scripts/install_skills.sh"],
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )

    def _assert_consumers_unchanged(self, root: Path) -> None:
        self.assertEqual(
            (root / ".agents" / "skills" / "sentinel" / "KEEP").read_text(
                encoding="utf-8"
            ),
            ".agents must survive\n",
        )
        self.assertEqual(
            (root / ".claude" / "skills" / "sentinel" / "KEEP").read_text(
                encoding="utf-8"
            ),
            ".claude must survive\n",
        )

    def test_pin_mismatch_fails_before_install_or_consumer_changes(self):
        root = self._project(
            manifest="""
                [skills]
                fixture = { source = "Acme/example/skills/fixture", rev = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }

                [options.targets]
                claude = ".claude/skills"
            """,
            lock="""
                [[skill]]
                name = "fixture"
                source = "https://github.com/Acme/example.git"
                kind = "git"
                path = "skills/fixture"
                commit = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
                checksum = "sha256:fixture"
            """,
            fake_ion="""
                touch "$ION_ADD_MARKER"
                exit 9
            """,
        )

        completed = self._run(root)

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("rev differs from its Ion.lock commit", completed.stderr)
        self.assertFalse((root / "ion-add-called").exists())
        self._assert_consumers_unchanged(root)

    def test_failed_staged_install_preserves_both_consumers(self):
        root = self._project(
            manifest="""
                [skills]
                fixture = { type = "local", path = "skills/fixture" }

                [options.targets]
                claude = ".claude/skills"
            """,
            lock="""
                [[skill]]
                name = "fixture"
                source = ""
                kind = "local"
                checksum = "sha256:fixture"
            """,
            fake_ion="""
                touch "$ION_ADD_MARKER"
                mkdir -p .agents/skills/partial .claude/skills/partial
                echo partial > .agents/skills/partial/INCOMPLETE
                echo partial > .claude/skills/partial/INCOMPLETE
                echo '{"success":false,"error":"fixture install failure"}'
                exit 9
            """,
        )

        completed = self._run(root)

        self.assertEqual(completed.returncode, 9)
        self.assertTrue((root / "ion-add-called").exists())
        self.assertFalse((root / ".agents" / "skills" / "partial").exists())
        self.assertFalse((root / ".claude" / "skills" / "partial").exists())
        self._assert_consumers_unchanged(root)

    def test_staged_lock_pin_change_is_rejected_before_consumer_changes(self):
        root = self._project(
            manifest="""
                [skills]
                fixture = { source = "Acme/example/skills/fixture", rev = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }

                [options.targets]
                claude = ".claude/skills"
            """,
            lock="""
                [[skill]]
                name = "fixture"
                source = "https://github.com/Acme/example.git"
                kind = "git"
                path = "skills/fixture"
                commit = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                checksum = "sha256:fixture"
            """,
            fake_ion="""
                touch "$ION_ADD_MARKER"
                mkdir -p .agents/skills .claude/skills
                ln -s ../../skills/fixture .agents/skills/fixture
                ln -s ../../.agents/skills/fixture .claude/skills/fixture
                sed -i \
                  s/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/ \
                  Ion.lock
                sed -i \
                  s/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/ \
                  Ion.toml
                echo '{"success":true,"data":{"installed":[{"name":"fixture"}]}}'
            """,
        )
        original_lock = (root / "Ion.lock").read_bytes()

        completed = self._run(root)

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("post-install pin verification failed", completed.stderr)
        self.assertTrue((root / "ion-add-called").exists())
        self.assertEqual((root / "Ion.lock").read_bytes(), original_lock)
        self._assert_consumers_unchanged(root)

    def test_staged_skill_must_be_a_directory_with_skill_file(self):
        root = self._project(
            manifest="""
                [skills]
                fixture = { type = "local", path = "skills/fixture" }

                [options.targets]
                claude = ".claude/skills"
            """,
            lock="""
                [[skill]]
                name = "fixture"
                source = ""
                kind = "local"
                checksum = "sha256:fixture"
            """,
            fake_ion="""
                mkdir -p .agents/skills .claude/skills
                echo not-a-skill > .agents/skills/fixture
                echo not-a-skill > .claude/skills/fixture
                echo '{"success":true,"data":{"installed":[{"name":"fixture"}]}}'
            """,
        )

        completed = self._run(root)

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("staged skill is not a directory", completed.stderr)
        self._assert_consumers_unchanged(root)

    def test_staged_skill_tree_rejects_nested_symlinks(self):
        root = self._project(
            manifest="""
                [skills]
                fixture = { type = "local", path = "skills/fixture" }

                [options.targets]
                claude = ".claude/skills"
            """,
            lock="""
                [[skill]]
                name = "fixture"
                source = ""
                kind = "local"
                checksum = "sha256:fixture"
            """,
            fake_ion="""
                mkdir -p .agents/skills/fixture .claude/skills
                cp skills/fixture/SKILL.md .agents/skills/fixture/SKILL.md
                ln -s /tmp/outside .agents/skills/fixture/escape
                ln -s ../../.agents/skills/fixture .claude/skills/fixture
                echo '{"success":true,"data":{"installed":[{"name":"fixture"}]}}'
            """,
        )

        completed = self._run(root)

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("staged skill tree contains a symlink", completed.stderr)
        self._assert_consumers_unchanged(root)

    def test_staged_skill_tree_rejects_special_files(self):
        root = self._project(
            manifest="""
                [skills]
                fixture = { type = "local", path = "skills/fixture" }

                [options.targets]
                claude = ".claude/skills"
            """,
            lock="""
                [[skill]]
                name = "fixture"
                source = ""
                kind = "local"
                checksum = "sha256:fixture"
            """,
            fake_ion="""
                mkdir -p .agents/skills/fixture .claude/skills
                cp skills/fixture/SKILL.md .agents/skills/fixture/SKILL.md
                mkfifo .agents/skills/fixture/stream
                ln -s ../../.agents/skills/fixture .claude/skills/fixture
                echo '{"success":true,"data":{"installed":[{"name":"fixture"}]}}'
            """,
        )

        completed = self._run(root)

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("staged skill tree contains a special file", completed.stderr)
        self._assert_consumers_unchanged(root)

    def test_consumer_parent_must_be_a_real_repository_directory(self):
        manifest = """
            [skills]
            fixture = { type = "local", path = "skills/fixture" }

            [options.targets]
            claude = ".claude/skills"
        """
        lock = """
            [[skill]]
            name = "fixture"
            source = ""
            kind = "local"
            checksum = "sha256:fixture"
        """
        fake_ion = """
            mkdir -p .agents/skills .claude/skills
            ln -s ../../skills/fixture .agents/skills/fixture
            ln -s ../../.agents/skills/fixture .claude/skills/fixture
            echo '{"success":true,"data":{"installed":[{"name":"fixture"}]}}'
        """

        for consumer in (".agents", ".claude"):
            with self.subTest(consumer=consumer):
                root = self._project(manifest, lock, fake_ion)
                outside = root / f"outside-{consumer.removeprefix('.')}"
                shutil.move(root / consumer, outside)
                (root / consumer).symlink_to(outside, target_is_directory=True)

                completed = self._run(root)

                self.assertNotEqual(completed.returncode, 0)
                self.assertIn(
                    "consumer parent must be a real repository directory",
                    completed.stderr,
                )
                self.assertTrue((root / consumer).is_symlink())
                self._assert_consumers_unchanged(root)

    def test_signal_during_each_swap_step_restores_consumers_and_lock(self):
        manifest = """
            [skills]
            fixture = { type = "local", path = "skills/fixture" }

            [options.targets]
            claude = ".claude/skills"
        """
        lock = """
            [[skill]]
            name = "fixture"
            source = ""
            kind = "local"
            checksum = "sha256:fixture"
        """
        fake_ion = """
            mkdir -p .agents/skills .claude/skills
            ln -s ../../skills/fixture .agents/skills/fixture
            ln -s ../../.agents/skills/fixture .claude/skills/fixture
            printf '\\n# staged-by-ion\\n' >> Ion.lock
            echo '{"success":true,"data":{"installed":[{"name":"fixture"}]}}'
        """
        failure_points = (
            "/previous-agents",
            "/previous-claude",
            "/.agents/skills",
            "/.claude/skills",
            "/Ion.lock",
        )

        for failure_point in failure_points:
            with self.subTest(failure_point=failure_point):
                root = self._project(manifest, lock, fake_ion)
                original_lock = (root / "Ion.lock").read_bytes()
                fake_mv = root / "fake-bin" / "mv"
                fake_mv.write_text(
                    textwrap.dedent(
                        """\
                        #!/usr/bin/env bash
                        set -euo pipefail
                        /bin/mv "$@"
                        destination="${!#}"
                        if [[ "$destination" == *"$FAIL_AFTER_MOVE_SUFFIX" ]] &&
                           [[ ! -e "$MV_SIGNAL_MARKER" ]]; then
                          touch "$MV_SIGNAL_MARKER"
                          kill -TERM "$PPID"
                        fi
                        """
                    ),
                    encoding="utf-8",
                )
                fake_mv.chmod(0o755)

                completed = self._run(
                    root,
                    {
                        "FAIL_AFTER_MOVE_SUFFIX": failure_point,
                        "MV_SIGNAL_MARKER": str(root / "mv-signal-sent"),
                    },
                )

                self.assertNotEqual(completed.returncode, 0)
                self.assertTrue((root / "mv-signal-sent").exists())
                self.assertEqual((root / "Ion.lock").read_bytes(), original_lock)
                self._assert_consumers_unchanged(root)
                self.assertFalse((root / ".agents" / "skills" / "fixture").exists())
                self.assertFalse((root / ".claude" / "skills" / "fixture").exists())
                self.assertFalse((root / "work" / "skills-install.lock").exists())

    def test_success_on_fresh_machine_without_consumer_directories(self):
        root = self._project(
            manifest="""
                [skills]
                fixture = { type = "local", path = "skills/fixture" }

                [options.targets]
                claude = ".claude/skills"
            """,
            lock="""
                [[skill]]
                name = "fixture"
                source = ""
                kind = "local"
                checksum = "sha256:fixture"
            """,
            fake_ion="""
                mkdir -p .agents/skills .claude/skills
                ln -s ../../skills/fixture .agents/skills/fixture
                ln -s ../../.agents/skills/fixture .claude/skills/fixture
                echo '{"success":true,"data":{"installed":[{"name":"fixture"}]}}'
            """,
        )
        shutil.rmtree(root / ".agents")
        shutil.rmtree(root / ".claude")

        completed = self._run(root)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        for consumer in (".agents", ".claude"):
            fixture = root / consumer / "skills" / "fixture"
            self.assertTrue(fixture.is_dir())
            self.assertFalse(fixture.is_symlink())
            self.assertTrue((fixture / "SKILL.md").is_file())

    def test_success_replaces_both_consumers_with_real_copies_and_lock(self):
        root = self._project(
            manifest="""
                [skills]
                fixture = { type = "local", path = "skills/fixture" }

                [options.targets]
                claude = ".claude/skills"
            """,
            lock="""
                [[skill]]
                name = "fixture"
                source = ""
                kind = "local"
                checksum = "sha256:fixture"
            """,
            fake_ion="""
                touch "$ION_ADD_MARKER"
                mkdir -p .agents/skills .claude/skills
                ln -s ../../skills/fixture .agents/skills/fixture
                ln -s ../../.agents/skills/fixture .claude/skills/fixture
                printf '\\n# staged-by-ion\\n' >> Ion.lock
                echo '{"success":true,"data":{"installed":[{"name":"fixture"}],"skipped":[]}}'
            """,
        )

        completed = self._run(root)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        for consumer in (".agents", ".claude"):
            skills = root / consumer / "skills"
            fixture = skills / "fixture"
            self.assertTrue(skills.is_dir())
            self.assertFalse(skills.is_symlink())
            self.assertEqual([entry.name for entry in skills.iterdir()], ["fixture"])
            self.assertTrue(fixture.is_dir())
            self.assertFalse(fixture.is_symlink())
            self.assertEqual(
                (fixture / "SKILL.md").read_bytes(),
                (root / "skills" / "fixture" / "SKILL.md").read_bytes(),
            )
        self.assertIn(
            "# staged-by-ion",
            (root / "Ion.lock").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
