from pathlib import Path

import pytest

from pristine.services.osv_scanner import scan_lockfile
from tests.services.conftest import ScannerProgram, replay_scanner


@pytest.mark.parametrize("claimed_packages", [None, 0])
def test_missing_or_empty_extraction_ledger_is_incomplete(
    scanner_program: ScannerProgram, tmp_path: Path, claimed_packages: int | None
) -> None:
    lockfile = (tmp_path / "uv.lock").resolve()
    diagnostics = (
        ""
        if claimed_packages is None
        else (
            "Starting filesystem walk for root: /\n"
            f"Scanned {lockfile} file and found {claimed_packages} packages\n"
            "End status: 0 dirs visited, 1 inodes visited, 1 Extract calls, 1ms elapsed, 1ms wall time\n"
        )
    )
    result = scan_lockfile(scanner_program(replay_scanner(b'{"results": []}', diagnostics.encode())))
    assert result.problem is not None
