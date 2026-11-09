"""Execute argument arrays and preserve underlying failures."""

import shlex
import shutil
import subprocess


class CommandError(RuntimeError):
    def __init__(self, argv, code, detail=""):
        self.code = code if 0 < code < 256 else 1
        super().__init__(
            f"Command failed ({self.code}): {shlex.join(argv)}"
            + (f"\n{detail.strip()}" if detail.strip() else "")
        )


class Runner:
    def which(self, name):
        return shutil.which(name)

    def run(self, argv, check=True, live=False):
        try:
            result = subprocess.run(
                argv, text=True, capture_output=not live, check=False
            )
        except OSError as exc:
            raise CommandError(argv, 127, str(exc)) from exc
        if check and result.returncode:
            code = (
                result.returncode if result.returncode > 0 else 128 - result.returncode
            )
            raise CommandError(argv, code, result.stderr or result.stdout or "")
        return subprocess.CompletedProcess(
            argv, result.returncode, result.stdout or "", result.stderr or ""
        )
