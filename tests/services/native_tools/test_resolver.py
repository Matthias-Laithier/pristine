import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from pristine.services.native_tools.artifacts import ReleaseArtifact
from pristine.services.native_tools.processes import ProcessResult
from pristine.services.native_tools.resolver import NativeToolResolver, NativeToolUnavailable
from tests.services.native_tools.conftest import FIXTURE_DIGEST, FIXTURE_URL, NativeBoundary


def test_exact_installed_version_avoids_cache_and_network(native_boundary: NativeBoundary) -> None:
    installed = native_boundary.root.parent / "installed"
    installed.write_bytes(b"installed fixture")
    native_boundary.installed = str(installed)
    native_boundary.version = ProcessResult(b"osv-scanner version: 2.7.0\nother metadata\n", b"", 0, None)
    assert native_boundary.resolver().resolve_tool("osv-scanner") == str(installed.resolve())
    assert native_boundary.commands == [[str(installed.resolve()), "--version"]]
    assert native_boundary.download_calls == []
    assert not native_boundary.root.exists()


@pytest.mark.parametrize("version", [b"osv-scanner version: 2.6.0\n", b"2.7.0\n"])
def test_mismatched_installed_version_provisions_the_pin(native_boundary: NativeBoundary, version: bytes) -> None:
    installed = native_boundary.root.parent / "installed"
    installed.write_bytes(b"installed fixture")
    native_boundary.installed = str(installed)
    native_boundary.version = ProcessResult(version, b"", 0, None)
    assert Path(native_boundary.resolver().resolve_tool("osv-scanner")).read_bytes() == b"abc"
    assert native_boundary.download_calls == [FIXTURE_URL]


def test_absent_tool_provisions_once_and_reuses_verified_cache_offline(native_boundary: NativeBoundary) -> None:
    resolver = native_boundary.resolver()
    executable = Path(resolver.resolve_tool("osv-scanner"))
    native_boundary.download_error = OSError("network unavailable with sensitive diagnostic")
    assert resolver.resolve_tool("osv-scanner") == str(executable)
    assert executable.is_absolute()
    assert executable.read_bytes() == b"abc"
    assert executable.stat().st_mode & 0o777 == 0o700
    assert native_boundary.root.stat().st_mode & 0o777 == 0o700
    assert list(native_boundary.root.iterdir()) == [executable]
    assert native_boundary.download_calls == [FIXTURE_URL]


@pytest.mark.parametrize("path_alias", [False, True], ids=["absent-tool", "path-alias"])
def test_corrupt_cache_is_not_executed_or_replaced_even_through_a_path_alias(
    native_boundary: NativeBoundary, *, path_alias: bool
) -> None:
    native_boundary.root.mkdir(mode=0o700)
    cached = native_boundary.root / FIXTURE_DIGEST
    cached.write_bytes(b"ab")
    cached.chmod(0o700)
    if path_alias:
        installed = native_boundary.root.parent / "osv-scanner"
        installed.symlink_to(cached)
        native_boundary.installed = str(installed)
    with pytest.raises(NativeToolUnavailable, match="cache is corrupt"):
        native_boundary.resolver().resolve_tool("osv-scanner")
    assert cached.read_bytes() == b"ab"
    assert native_boundary.commands == []
    assert native_boundary.download_calls == []


@pytest.mark.parametrize("kind", ["entry-symlink", "directory-symlink", "public-directory", "public-file", "fifo"])
def test_unsafe_cache_is_refused_before_download(native_boundary: NativeBoundary, kind: str) -> None:
    root = native_boundary.root
    if kind == "directory-symlink":
        root.symlink_to(root.parent, target_is_directory=True)
    else:
        root.mkdir(mode=0o700)
        cached = root / FIXTURE_DIGEST
        if kind == "entry-symlink":
            cached.symlink_to(root.parent / "missing")
        elif kind == "fifo":
            os.mkfifo(cached, mode=0o700)
        else:
            cached.write_bytes(b"abc")
            cached.chmod(0o700 if kind == "public-directory" else 0o755)
            root.chmod(0o755 if kind == "public-directory" else 0o700)
    with pytest.raises(NativeToolUnavailable):
        native_boundary.resolver().resolve_tool("osv-scanner")
    assert native_boundary.download_calls == []
    assert native_boundary.commands == []


def test_foreign_owned_cache_is_refused(native_boundary: NativeBoundary, monkeypatch: pytest.MonkeyPatch) -> None:
    native_boundary.root.mkdir(mode=0o700)
    real_uid = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: real_uid + 1)
    with pytest.raises(NativeToolUnavailable, match="owned and private"):
        native_boundary.resolver().resolve_tool("osv-scanner")
    assert native_boundary.download_calls == []


@pytest.mark.parametrize("problem", ["offline", "wrong-hash"])
def test_failed_provision_leaves_no_executable_or_temporary(native_boundary: NativeBoundary, problem: str) -> None:
    if problem == "wrong-hash":
        native_boundary.payload = b"different"
    else:
        native_boundary.download_error = OSError("sensitive failure")
    with pytest.raises(NativeToolUnavailable) as failure:
        native_boundary.resolver().resolve_tool("osv-scanner")
    assert "sensitive" not in str(failure.value)
    assert list(native_boundary.root.iterdir()) == []


def test_concurrent_first_use_publishes_one_complete_executable(
    native_boundary: NativeBoundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    simultaneous_downloads = Barrier(2)

    def download(url: str) -> bytes:
        assert url == FIXTURE_URL
        simultaneous_downloads.wait(timeout=5)
        return b"abc"

    monkeypatch.setattr(native_boundary, "download", download)
    resolver = native_boundary.resolver()
    with ThreadPoolExecutor(max_workers=2) as callers:
        results = list(callers.map(resolver.resolve_tool, ("osv-scanner", "osv-scanner")))
    assert results == [str(native_boundary.root / FIXTURE_DIGEST)] * 2
    assert list(native_boundary.root.iterdir()) == [Path(results[0])]
    assert Path(results[0]).read_bytes() == b"abc"


@pytest.mark.parametrize("system,machine", [("Windows", "arm64"), ("Linux", "riscv64")])
def test_unsupported_platform_does_not_probe_or_download(
    native_boundary: NativeBoundary, system: str, machine: str
) -> None:
    def must_not_find(name: str) -> None:
        raise AssertionError(f"unsupported platform looked up {name}")

    resolver = NativeToolResolver(
        native_boundary.root,
        system,
        machine,
        finder=must_not_find,
        download=native_boundary.download,
    )
    with pytest.raises(NativeToolUnavailable, match="platform is unsupported"):
        resolver.resolve_tool("osv-scanner")
    assert native_boundary.commands == []
    assert native_boundary.download_calls == []


def test_invalid_executable_digest_cannot_escape_cache(native_boundary: NativeBoundary) -> None:
    artifact = ReleaseArtifact("Darwin", "arm64", FIXTURE_URL, "../outside")
    with pytest.raises(NativeToolUnavailable, match="pin is invalid"):
        native_boundary.resolver(artifact=artifact).resolve_tool("osv-scanner")
    assert not native_boundary.root.exists()
