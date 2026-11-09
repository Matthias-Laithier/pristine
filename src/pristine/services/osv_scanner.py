import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pristine.services.native_tools.processes import ProcessResult, run_process
from pristine.services.native_tools.resolver import NativeToolUnavailable, resolve_tool

__all__ = ["ScannerResult", "scan_lockfile"]

SCAN_TIMEOUT_IN_SECONDS = 300
OUTPUT_LIMIT_IN_BYTES = 8 * 1024 * 1024
LOCKFILE_LIMIT_IN_BYTES = 8 * 1024 * 1024
PATH_LIMIT_IN_BYTES = 4096
EXPECTED_DIAGNOSTIC_LINES = 3
SCAN_OPTIONS = (
    "scan",
    "source",
    "--format=json",
    "--all-packages",
    "--all-vulns",
    "--no-ignore",
    "--no-resolve",
    "--no-call-analysis=all",
    "--x-no-default-plugins",
    "--x-plugins=python/uvlock",
    "--verbosity=info",
)
DURATION_PATTERN = r"(?:\d+(?:\.\d+)?(?:ns|µs|ms|s|m|h))+"
WALK_END_PATTERN = (
    r"End status: 0 dirs visited, 1 inodes visited, 1 Extract calls, "
    rf"{DURATION_PATTERN} elapsed, {DURATION_PATTERN} wall time"
)


@dataclass(frozen=True)
class ScannerResult:
    stdout: str
    stderr: str
    returncode: int | None
    problem: str | None
    target_path: str | None = None
    extracted_packages: int | None = None


class _ScanStopped(Exception):
    pass


def _validated_lockfile(path: Path) -> Path:
    if path.is_symlink():
        raise _ScanStopped("symlink audit paths are not supported")
    lockfile = path / "uv.lock" if path.is_dir() else path
    if lockfile.name != "uv.lock":
        raise _ScanStopped("only a root uv.lock file is supported")
    if lockfile.is_symlink():
        raise _ScanStopped("symlink uv.lock files are not supported")
    resolved = lockfile.resolve(strict=True)
    if len(os.fsencode(resolved)) > PATH_LIMIT_IN_BYTES or not str(resolved).isprintable():
        raise _ScanStopped("the lockfile path exceeds supported bounds")
    metadata = resolved.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise _ScanStopped("uv.lock must be a regular file")
    if metadata.st_size > LOCKFILE_LIMIT_IN_BYTES:
        raise _ScanStopped("uv.lock exceeds the scanner input limit")
    return resolved


def _scan_evidence(returncode: int | None, stderr: str, lockfile: Path) -> tuple[str | None, int | None]:
    if returncode not in (0, 1):
        return f"osv-scanner exited with code {returncode}", None
    lines = stderr.splitlines()
    extraction_pattern = r"Scanned " + re.escape(str(lockfile)) + r" file and found ([1-9][0-9]{0,8}) packages?"
    if len(lines) != EXPECTED_DIAGNOSTIC_LINES or lines[0] != "Starting filesystem walk for root: /":
        return "osv-scanner reported an incomplete or unrecognized scan diagnostic", None
    extraction = re.fullmatch(extraction_pattern, lines[1])
    if extraction is None or re.fullmatch(WALK_END_PATTERN, lines[2]) is None:
        return "osv-scanner reported an incomplete or unrecognized scan diagnostic", None
    return None, int(extraction[1])


def _scanner_result(result: ProcessResult, lockfile: Path) -> ScannerResult:
    problem = result.problem.replace("native tool", "osv-scanner") if result.problem is not None else None
    try:
        stdout, stderr = (stream.decode("utf-8") for stream in (result.stdout, result.stderr))
    except UnicodeDecodeError:
        stdout, stderr = (stream.decode("utf-8", errors="replace") for stream in (result.stdout, result.stderr))
        problem = problem or "osv-scanner output is not UTF-8"
    diagnostic_problem, package_count = _scan_evidence(result.returncode, stderr, lockfile)
    return ScannerResult(stdout, stderr, result.returncode, problem or diagnostic_problem, str(lockfile), package_count)


def scan_lockfile(path: Path) -> ScannerResult:
    try:
        if os.name != "posix":
            raise _ScanStopped("the native scanner boundary requires POSIX process control")
        lockfile = _validated_lockfile(path)
        executable = resolve_tool("osv-scanner")
        with tempfile.TemporaryDirectory(prefix="pristine-osv-") as directory:
            config = Path(directory) / "empty.toml"
            config.touch()
            command = [executable, *SCAN_OPTIONS, "--config", str(config), "--lockfile", ":" + str(lockfile)]
            result = run_process(
                command,
                Path(directory),
                timeout_in_seconds=SCAN_TIMEOUT_IN_SECONDS,
                output_limit_in_bytes=OUTPUT_LIMIT_IN_BYTES,
            )
            return _scanner_result(result, lockfile)
    except (_ScanStopped, NativeToolUnavailable) as error:
        return ScannerResult("", "", None, str(error))
    except OSError, ValueError:
        return ScannerResult("", "", None, "the scanner could not read uv.lock or prepare its input")
