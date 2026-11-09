import os
from collections.abc import Callable
from pathlib import Path

import pytest

from pristine.services import osv_scanner
from pristine.services.native_tools import processes
from pristine.services.osv_scanner import scan_lockfile
from tests.services.conftest import ScannerProgram, replay_scanner


def _recording(name: str) -> str:
    return (Path(__file__).parents[2] / "assets" / "audit" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "recording,returncode,package_count", [("clean.json", 0, "1 package"), ("vulnerable.json", 1, "2 packages")]
)
def test_native_invocation_preserves_recorded_json_and_target(
    scanner_program: ScannerProgram, tmp_path: Path, recording: str, returncode: int, package_count: str
) -> None:
    payload = _recording(recording)
    lockfile = (tmp_path / "uv.lock").resolve()
    diagnostics = (
        "Starting filesystem walk for root: /\n"
        f"Scanned {lockfile} file and found {package_count}\n"
        "End status: 0 dirs visited, 1 inodes visited, 1 Extract calls, 576.458µs elapsed, 577µs wall time\n"
    )
    program = (
        "import sys\nfrom pathlib import Path\narguments = sys.argv[1:]\n"
        "assert arguments[:-4] == ['scan', 'source', '--format=json', '--all-packages', '--all-vulns', "
        "'--no-ignore', '--no-resolve', '--no-call-analysis=all', '--x-no-default-plugins', "
        "'--x-plugins=python/uvlock', '--verbosity=info']\n"
        "assert arguments[-4] == '--config'\nassert arguments[-2] == '--lockfile'\n"
        f"assert arguments[-1] == {(':' + str(lockfile))!r}\n"
        "assert Path(arguments[-3]).read_bytes() == b''\n"
        "assert Path(arguments[-3]).parent.resolve() == Path.cwd()\n"
        + replay_scanner(payload.encode(), diagnostics.encode(), returncode)
    )
    scanner_program(program)
    result = scan_lockfile(tmp_path)
    assert (result.stdout, result.stderr, result.returncode, result.problem) == (payload, diagnostics, returncode, None)
    assert result.target_path == str(lockfile)
    assert {path.name for path in tmp_path.iterdir()} == {"uv.lock", "osv-scanner"}


@pytest.mark.parametrize(
    "diagnostic",
    [
        "Filtered 1 local/unscannable package/s from the scan.",
        "Filtered 1 ignored package/s from the scan.",
        "Skipping package: short commit hash",
        "Error during extraction: initial query timed out",
        "Warning: database is unavailable",
        "A new status message",
        "Scanned /other/uv.lock file and found 1 package",
    ],
)
def test_gaps_and_unknown_diagnostics_preserve_findings_but_fail(
    scanner_program: ScannerProgram, diagnostic: str
) -> None:
    payload = _recording("vulnerable.json")
    result = scan_lockfile(scanner_program(replay_scanner(payload.encode(), diagnostic.encode(), 1)))
    assert result.stdout == payload
    assert result.stderr == diagnostic
    assert result.returncode == 1
    assert result.problem == "osv-scanner reported an incomplete or unrecognized scan diagnostic"


@pytest.mark.parametrize("returncode", [127, 128, 129, 130])
def test_native_failure_exits_are_not_clean(scanner_program: ScannerProgram, returncode: int) -> None:
    result = scan_lockfile(scanner_program(replay_scanner(b"", b"No package sources found", returncode)))
    assert result.returncode == returncode
    assert result.problem == f"osv-scanner exited with code {returncode}"


@pytest.mark.parametrize("size,overflow", [(32, False), (33, True)])
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_output_is_bounded_at_the_exact_limit(
    scanner_program: ScannerProgram, monkeypatch: pytest.MonkeyPatch, size: int, overflow: bool, stream: str
) -> None:
    monkeypatch.setattr(osv_scanner, "OUTPUT_LIMIT_IN_BYTES", 32)
    payload = b"a" * size
    program = replay_scanner(payload if stream == "stdout" else b"", payload if stream == "stderr" else b"")
    result = scan_lockfile(scanner_program(program))
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 32
    if overflow:
        assert result.problem == "osv-scanner exceeded the output limit"
    else:
        assert getattr(result, stream) == payload.decode()
        assert result.returncode == 0


def test_the_output_limit_covers_both_streams_together(
    scanner_program: ScannerProgram, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(osv_scanner, "OUTPUT_LIMIT_IN_BYTES", 32)
    result = scan_lockfile(scanner_program(replay_scanner(b"a" * 16, b"b" * 17)))
    assert result.problem == "osv-scanner exceeded the output limit"


def test_timeout_kills_and_reaps_the_scanner(scanner_program: ScannerProgram, monkeypatch: pytest.MonkeyPatch) -> None:
    readings = iter((0.0, 300.0))
    monkeypatch.setattr(processes, "monotonic", lambda: next(readings))
    result = scan_lockfile(scanner_program("import signal\nsignal.pause()\n"))
    assert result.problem == "osv-scanner timed out"
    assert result.returncode == -9


def test_invalid_utf8_is_not_clean(scanner_program: ScannerProgram) -> None:
    result = scan_lockfile(scanner_program(replay_scanner(b"\xff")))
    assert result.stdout == "\ufffd"
    assert result.returncode == 0
    assert result.problem == "osv-scanner output is not UTF-8"


def test_missing_and_unlaunchable_scanner_fail(scanner_program: ScannerProgram, tmp_path: Path) -> None:
    lockfile = scanner_program(replay_scanner(b""))
    executable = tmp_path / "osv-scanner"
    executable.unlink()
    assert scan_lockfile(lockfile).problem == "osv-scanner provisioning is unavailable"
    executable.write_text("#!/nonexistent/pristine-scanner\n", encoding="utf-8")
    executable.chmod(0o700)
    result = scan_lockfile(lockfile)
    assert result.returncode is None
    assert result.problem == "osv-scanner could not start"


def _symlink_input(lockfile: Path) -> Path:
    original = lockfile.with_suffix(".original")
    lockfile.rename(original)
    lockfile.symlink_to(original)
    return lockfile


def _oversized_input(lockfile: Path) -> Path:
    with lockfile.open("wb") as stream:
        stream.truncate(8 * 1024 * 1024 + 1)
    return lockfile


def _fifo_input(lockfile: Path) -> Path:
    lockfile.unlink()
    os.mkfifo(lockfile)
    return lockfile


@pytest.mark.parametrize(
    "prepare",
    [
        lambda path: path.parent / "missing" / "uv.lock",
        lambda path: path.with_name("pyproject.toml"),
        _symlink_input,
        _oversized_input,
        _fifo_input,
        lambda path: path.parent / "line\nbreak" / "uv.lock",
    ],
)
def test_unsupported_inputs_never_launch(scanner_program: ScannerProgram, prepare: Callable[[Path], Path]) -> None:
    lockfile = scanner_program("raise RuntimeError('must not launch')\n")
    result = scan_lockfile(prepare(lockfile))
    assert result.problem is not None
    assert result.returncode is None


def test_unsupported_platform_fails_before_launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(os, "name", "nt")
        result = scan_lockfile(tmp_path)
    assert result.problem == "the native scanner boundary requires POSIX process control"
    assert result.returncode is None
