import base64
import gzip
import hashlib
import io
import json
import os
import tarfile
from dataclasses import replace
from pathlib import Path

import pytest

from pristine.services.native_tools.artifacts import ReleaseArtifact
from pristine.services.native_tools.resolver import NativeToolUnavailable
from tests.services.native_tools.conftest import FIXTURE_DIGEST, FIXTURE_URL, NativeBoundary

FIXTURE_PATH = Path(__file__).resolve().parents[3] / "assets" / "native_tools" / "archive.json"


def test_reviewed_archive_extracts_only_the_pinned_regular_executable(native_boundary: NativeBoundary) -> None:
    fixture = json.loads(FIXTURE_PATH.read_text())
    payload = base64.b64decode(fixture["base64"])
    artifact = ReleaseArtifact("Darwin", "arm64", FIXTURE_URL, fixture["sha256"], FIXTURE_DIGEST, "gitleaks")
    native_boundary.payload = payload
    executable = Path(native_boundary.resolver("gitleaks", artifact).resolve_tool("gitleaks"))
    assert executable.read_bytes() == b"abc"
    assert list(native_boundary.root.iterdir()) == [executable]
    assert not (native_boundary.root / "LICENSE").exists()
    assert not (native_boundary.root / "README.md").exists()


def archive_payload(members: tuple[tarfile.TarInfo, ...]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for member in members:
            archive.addfile(member, io.BytesIO(b"abc") if member.size else None)
    return gzip.compress(buffer.getvalue(), mtime=0)


def regular_member(name: str = "gitleaks") -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.size = 3
    return member


@pytest.mark.parametrize("name", ["../outside", "/untrusted/outside", "nested/gitleaks", "./gitleaks"])
def test_archive_path_members_are_never_written(native_boundary: NativeBoundary, name: str) -> None:
    payload = archive_payload((regular_member(name),))
    native_boundary.payload = payload
    artifact = ReleaseArtifact(
        "Darwin", "arm64", FIXTURE_URL, hashlib.sha256(payload).hexdigest(), FIXTURE_DIGEST, "gitleaks"
    )
    with pytest.raises(NativeToolUnavailable, match="unexpected member"):
        native_boundary.resolver("gitleaks", artifact).resolve_tool("gitleaks")
    assert list(native_boundary.root.iterdir()) == []


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE])
def test_archive_special_members_are_refused(native_boundary: NativeBoundary, kind: bytes) -> None:
    member = tarfile.TarInfo("gitleaks")
    member.type = kind
    member.linkname = "../outside"
    payload = archive_payload((member,))
    native_boundary.payload = payload
    artifact = ReleaseArtifact(
        "Darwin", "arm64", FIXTURE_URL, hashlib.sha256(payload).hexdigest(), FIXTURE_DIGEST, "gitleaks"
    )
    with pytest.raises(NativeToolUnavailable, match="unexpected member"):
        native_boundary.resolver("gitleaks", artifact).resolve_tool("gitleaks")
    assert list(native_boundary.root.iterdir()) == []


@pytest.mark.parametrize(
    "members,reason",
    [
        ((regular_member(), regular_member()), "repeats"),
        ((regular_member("README.md"),), "no executable"),
        ((regular_member(),) + (regular_member("LICENSE"),) * 3, "unexpected member"),
    ],
)
def test_archive_duplicate_missing_and_member_limit_failures(
    native_boundary: NativeBoundary, members: tuple[tarfile.TarInfo, ...], reason: str
) -> None:
    payload = archive_payload(members)
    native_boundary.payload = payload
    artifact = ReleaseArtifact(
        "Darwin", "arm64", FIXTURE_URL, hashlib.sha256(payload).hexdigest(), FIXTURE_DIGEST, "gitleaks"
    )
    with pytest.raises(NativeToolUnavailable, match=reason):
        native_boundary.resolver("gitleaks", artifact).resolve_tool("gitleaks")
    assert list(native_boundary.root.iterdir()) == []


@pytest.mark.parametrize("expanded_size", [64 * 1024 * 1024, 64 * 1024 * 1024 + 1])
def test_expanded_archive_size_limit_is_bounded(native_boundary: NativeBoundary, expanded_size: int) -> None:
    payload = gzip.compress(b"\0" * expanded_size, mtime=0)
    native_boundary.payload = payload
    artifact = ReleaseArtifact(
        "Darwin", "arm64", FIXTURE_URL, hashlib.sha256(payload).hexdigest(), FIXTURE_DIGEST, "gitleaks"
    )
    reason = "no executable" if expanded_size == 64 * 1024 * 1024 else "expanded size limit"
    with pytest.raises(NativeToolUnavailable, match=reason):
        native_boundary.resolver("gitleaks", artifact).resolve_tool("gitleaks")
    assert list(native_boundary.root.iterdir()) == []


def test_declared_oversized_member_is_rejected_before_read(native_boundary: NativeBoundary) -> None:
    member = regular_member()
    member.size = 64 * 1024 * 1024 + 1
    payload = gzip.compress(member.tobuf(format=tarfile.USTAR_FORMAT) + b"\0" * 1024, mtime=0)
    native_boundary.payload = payload
    artifact = ReleaseArtifact(
        "Darwin", "arm64", FIXTURE_URL, hashlib.sha256(payload).hexdigest(), FIXTURE_DIGEST, "gitleaks"
    )
    with pytest.raises(NativeToolUnavailable, match="member exceeds"):
        native_boundary.resolver("gitleaks", artifact).resolve_tool("gitleaks")
    assert list(native_boundary.root.iterdir()) == []


def test_extracted_executable_pin_is_checked_independently(native_boundary: NativeBoundary) -> None:
    fixture = json.loads(FIXTURE_PATH.read_text())
    native_boundary.payload = base64.b64decode(fixture["base64"])
    artifact = ReleaseArtifact("Darwin", "arm64", FIXTURE_URL, fixture["sha256"], FIXTURE_DIGEST, "gitleaks")
    wrong_executable = replace(artifact, executable_sha256="0" * 64)
    with pytest.raises(NativeToolUnavailable, match="executable checksum failed"):
        native_boundary.resolver("gitleaks", wrong_executable).resolve_tool("gitleaks")
    assert list(native_boundary.root.iterdir()) == []


def test_disk_failure_cleans_the_unpublished_temporary(
    native_boundary: NativeBoundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_sync(descriptor: int) -> None:
        del descriptor
        raise OSError("disk full with sensitive path")

    monkeypatch.setattr(os, "fsync", fail_sync)
    with pytest.raises(NativeToolUnavailable) as failure:
        native_boundary.resolver().resolve_tool("osv-scanner")
    assert "sensitive" not in str(failure.value)
    assert list(native_boundary.root.iterdir()) == []
