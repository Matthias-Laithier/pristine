from pathlib import Path

import pytest

from pristine.services.osv_scanner import scan_lockfile
from tests.conftest import audit_recording
from tests.services.conftest import ScannerProgram, replay_scanner, scanner_diagnostics


@pytest.mark.parametrize(
    "before,after",
    [
        ("Scanned {path} file and found 2 packages", "Extraction ledger unavailable"),
        ("Scanned {path}", "Scanned /other/uv.lock"),
        ("0 dirs visited, 1 inodes visited", "1 dirs visited, 2 inodes visited"),
        ("End status:", "Warning: database is unavailable\nEnd status:"),
        ("End status:", "Filtered 1 ignored package/s from the scan.\nEnd status:"),
    ],
    ids=["missing-ledger", "wrong-path", "invalid-walk", "valid-ledger-warning", "valid-ledger-filter"],
)
def test_native_diagnostic_gaps_retain_findings_but_fail_verification(
    scanner_program: ScannerProgram, tmp_path: Path, before: str, after: str
) -> None:
    lockfile = (tmp_path / "uv.lock").resolve()
    diagnostics = scanner_diagnostics(lockfile, 2).replace(before.format(path=lockfile), after, 1)
    payload = audit_recording("vulnerable")
    result = scan_lockfile(scanner_program(replay_scanner(payload.encode(), diagnostics.encode(), 1)))
    assert result.stdout == payload
    assert result.returncode == 1
    assert result.extracted_packages is None
    assert result.problem == "osv-scanner reported an incomplete or unrecognized scan diagnostic"


def test_zero_package_extraction_is_not_verified_clean(scanner_program: ScannerProgram, tmp_path: Path) -> None:
    diagnostics = scanner_diagnostics(tmp_path / "uv.lock", 0)
    result = scan_lockfile(scanner_program(replay_scanner(b'{"results": []}', diagnostics.encode())))
    assert result.returncode == 0
    assert result.problem == "osv-scanner reported an incomplete or unrecognized scan diagnostic"
    assert result.extracted_packages is None
