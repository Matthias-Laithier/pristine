from pathlib import Path

import pytest

from pristine.services.native_tools.processes import ProcessResult
from pristine.services.native_tools.resolver import NativeToolResolver, NativeToolUnavailable
from tests.services.native_tools.conftest import NativeBoundary


@pytest.mark.parametrize(
    "system,machine,asset_name",
    [
        ("Darwin", "arm64", "darwin_arm64"),
        ("Darwin", "x86_64", "darwin_amd64"),
        ("Linux", "aarch64", "linux_arm64"),
        ("Linux", "x86_64", "linux_amd64"),
    ],
)
def test_supported_catalog_selects_only_fixed_official_release_assets(
    tmp_path: Path, system: str, machine: str, asset_name: str
) -> None:
    url = "google/osv-scanner/releases/download/v2.7.0/osv-scanner_" + asset_name
    requested: list[str] = []

    def offline(download_url: str) -> bytes:
        requested.append(download_url)
        raise OSError("fixture offline")

    resolver = NativeToolResolver(tmp_path / "cache", system, machine, finder=lambda _name: None, download=offline)
    with pytest.raises(NativeToolUnavailable):
        resolver.resolve_tool("osv-scanner")
    assert requested == ["https://github.com/" + url]
    assert list((tmp_path / "cache").iterdir()) == []


@pytest.mark.parametrize("returncode,problem", [(1, None), (0, "native tool timed out")])
def test_failed_version_probe_cannot_accept_valid_looking_stdout(
    native_boundary: NativeBoundary, returncode: int | None, problem: str | None
) -> None:
    installed = native_boundary.root.parent / "installed"
    installed.write_bytes(b"installed fixture")
    native_boundary.installed = str(installed)
    native_boundary.version = ProcessResult(b"osv-scanner version: 2.7.0\n", b"", returncode, problem)
    assert Path(native_boundary.resolver().resolve_tool("osv-scanner")).read_bytes() == b"abc"
    assert len(native_boundary.download_calls) == 1
