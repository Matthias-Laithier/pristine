import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from pristine.services import osv_scanner
from pristine.services.native_tools.resolver import NativeToolUnavailable

type ScannerProgram = Callable[[str], Path]


@pytest.fixture
def scanner_program(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ScannerProgram:
    lockfile = tmp_path / "uv.lock"
    lockfile.write_text("version = 1\n", encoding="utf-8")
    executable = tmp_path / "osv-scanner"

    def resolved_tool(name: str) -> str:
        assert name == "osv-scanner"
        if not executable.is_file():
            raise NativeToolUnavailable("osv-scanner provisioning is unavailable")
        return str(executable)

    monkeypatch.setattr(osv_scanner, "resolve_tool", resolved_tool)

    def prepare(program: str) -> Path:
        executable.write_text("#!" + sys.executable + "\n" + program, encoding="utf-8")
        executable.chmod(0o700)
        return lockfile

    return prepare


def scanner_diagnostics(lockfile: Path, packages: int = 1) -> str:
    return (
        "Starting filesystem walk for root: /\n"
        f"Scanned {lockfile.resolve()} file and found {packages} package{'s' if packages != 1 else ''}\n"
        "End status: 0 dirs visited, 1 inodes visited, 1 Extract calls, 576.458µs elapsed, 577µs wall time\n"
    )


def replay_scanner(stdout: bytes, stderr: bytes = b"", returncode: int = 0) -> str:
    return (
        "import sys\n"
        f"sys.stdout.buffer.write({stdout!r})\n"
        f"sys.stderr.buffer.write({stderr!r})\n"
        f"raise SystemExit({returncode!r})\n"
    )
