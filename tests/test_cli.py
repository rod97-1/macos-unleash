import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from unleashlib.cli import main
from unleashlib.platforms import Platform, PlatformError
from helpers import FakeRunner


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "state"

    def call(self, args, runner=None):
        output = io.StringIO()
        with (
            patch(
                "unleashlib.cli.detect_platform",
                return_value=Platform("debian", "apt", "x86_64"),
            ),
            patch(
                "unleashlib.cli.Runner",
                return_value=runner
                or FakeRunner(available={"apt-get", "apt-cache", "dpkg-query"}),
            ),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(output),
        ):
            code = main(args)
        return code, output.getvalue()

    def test_help_does_not_detect_or_mutate(self):
        with (
            patch(
                "unleashlib.cli.detect_platform",
                side_effect=AssertionError("must not detect"),
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main([]), 0)

    def test_plan_has_commands_but_never_installs_or_creates_state(self):
        runner = FakeRunner(available={"apt-get", "apt-cache", "dpkg-query"})
        code, text = self.call(
            ["plan", "--tool", "git", "--state-dir", str(self.state)], runner
        )
        self.assertEqual(code, 0, text)
        self.assertIn("apt-get install", text)
        self.assertFalse(any("apt-get" in c for c in runner.calls))
        self.assertFalse(self.state.exists())

    def test_status_returns_failure_for_missing_selected_component(self):
        code, text = self.call(
            ["status", "--tool", "git", "--state-dir", str(self.state)]
        )
        self.assertEqual(code, 1, text)
        self.assertIn("missing", text)
        self.assertFalse(self.state.exists())

    def test_doctor_inspects_prerequisites_without_mutation(self):
        code, text = self.call(["doctor"])
        self.assertEqual(code, 0, text)
        self.assertIn("debian", text)
        code, text = self.call(["doctor"], FakeRunner())
        self.assertEqual(code, 1, text)
        self.assertIn("apt-get", text)

    def test_unsupported_platform_does_not_execute_commands(self):
        output = io.StringIO()
        with (
            patch(
                "unleashlib.cli.detect_platform",
                side_effect=PlatformError("Windows deferred"),
            ),
            patch("unleashlib.cli.Runner") as runner,
            contextlib.redirect_stderr(output),
        ):
            self.assertEqual(main(["apply"]), 2)
        runner.assert_not_called()

    def test_unknown_tool_is_rejected_without_command_execution(self):
        runner = FakeRunner(available={"apt-get", "apt-cache", "dpkg-query"})
        code, text = self.call(["apply", "--tool", "git;whoami"], runner)
        self.assertEqual(code, 2, text)
        self.assertFalse(runner.calls)

    def test_manual_tool_blocks_package_mutation(self):
        runner = FakeRunner(available={"apt-get", "apt-cache", "dpkg-query"})
        code, text = self.call(["apply", "--tool", "git", "--tool", "ollama"], runner)
        self.assertEqual(code, 2, text)
        self.assertIn("manual prerequisite", text)
        self.assertFalse(any("apt-get" in c for c in runner.calls))

    def test_explicit_apply_calls_installer_and_keeps_failure_code(self):
        responses = {
            ("apt-cache", "show", "git"): (0, "Package: git"),
            ("apt-get", "install", "-y", "--no-install-recommends", "git"): (
                42,
                "disk full",
            ),
        }
        runner = FakeRunner(
            responses, available={"apt-get", "apt-cache", "dpkg-query", "sudo"}
        )
        with patch("unleashlib.packages.os.geteuid", return_value=0):
            code, text = self.call(["apply", "--tool", "git"], runner)
        self.assertEqual(code, 42, text)
        self.assertIn("earlier", text)

    def test_no_packages_option_is_explicit_and_does_not_create_state(self):
        code, text = self.call(
            ["apply", "--no-packages", "--state-dir", str(self.state)]
        )
        self.assertEqual(code, 0, text)
        self.assertFalse(self.state.exists())

    def test_wrapper_rejects_linux_before_system_commands(self):
        with tempfile.TemporaryDirectory(prefix="unleash path ") as folder:
            wrapper = Path(folder) / "unleash-mac.sh"
            wrapper.write_text(Path("unleash-mac.sh").read_text())
            uname = Path(folder) / "uname"
            uname.write_text('#!/bin/sh\nprintf "Linux\\n"\n')
            uname.chmod(0o755)
            env = {**os.environ, "PATH": folder + os.pathsep + os.environ["PATH"]}
            result = subprocess.run(
                ["bash", str(wrapper), "plan"], capture_output=True, text=True, env=env
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("macOS", result.stderr)
            self.assertNotIn("system_profiler", result.stderr)

    def test_wrapper_delegates_from_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="unleash path ") as folder:
            wrapper = Path(folder) / "unleash-mac.sh"
            wrapper.write_text(Path("unleash-mac.sh").read_text())
            uname = Path(folder) / "uname"
            uname.write_text(
                '#!/bin/sh\ncase "$1" in -s) echo Darwin;; -m) echo arm64;; esac\n'
            )
            uname.chmod(0o755)
            (Path(folder) / "unleash.py").write_text("import sys; print(sys.argv[1])\n")
            env = {**os.environ, "PATH": folder + os.pathsep + os.environ["PATH"]}
            result = subprocess.run(
                ["bash", str(wrapper), "plan"], capture_output=True, text=True, env=env
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "plan")
