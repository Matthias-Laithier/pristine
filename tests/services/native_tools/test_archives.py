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

from pristine.services.native_tools import artifacts
from pristine.services.native_tools.artifacts import ReleaseArtifact
from pristine.services.native_tools.resolver import NativeToolUnavailable
from tests.services.native_tools.conftest import FIXTURE_DIGEST, FIXTURE_URL, NativeBoundary

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "native_tools" / "archive.json"


def test_reviewed_archive_extracts_only_the_pinned_regular_executable(native_boundary: NativeBoundary) -> None:
    fixture = json.loads(FIXTURE_PATH.read_text())
    payload = base64.b64decode(fixture["base64"])
    artifact = ReleaseArtifact("Darwin", "arm64", FIXTURE_URL, fixture["sha256"], FIXTURE_DIGEST, "gitleaks")
    native_boundary.payload = payload
    executable = Path(native_boundary.resolver("gitleaks", artifact).resolve_tool("gitleaks"))
    assert executable.read_bytes() == b"abc"
    assert list(native_boundary.root.iterdir()) == [executable]


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


def assert_archive_refused(native_boundary: NativeBoundary, payload: bytes, reason: str) -> None:
    native_boundary.payload = payload
    artifact = ReleaseArtifact(
        "Darwin", "arm64", FIXTURE_URL, hashlib.sha256(payload).hexdigest(), FIXTURE_DIGEST, "gitleaks"
    )
    with pytest.raises(NativeToolUnavailable, match=reason):
        native_boundary.resolver("gitleaks", artifact).resolve_tool("gitleaks")
    assert list(native_boundary.root.iterdir()) == []


def test_archive_path_member_is_never_written(native_boundary: NativeBoundary) -> None:
    assert_archive_refused(native_boundary, archive_payload((regular_member("../outside"),)), "unexpected member")


def test_archive_link_in_place_of_executable_is_refused(native_boundary: NativeBoundary) -> None:
    member = tarfile.TarInfo("gitleaks")
    member.type = tarfile.SYMTYPE
    member.linkname = "../outside"
    assert_archive_refused(native_boundary, archive_payload((member,)), "unexpected member")


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
    assert_archive_refused(native_boundary, archive_payload(members), reason)


@pytest.mark.parametrize("expanded_size,reason", [(2048, "no executable"), (2049, "expanded size limit")])
def test_expanded_archive_size_limit_is_bounded(
    native_boundary: NativeBoundary, monkeypatch: pytest.MonkeyPatch, expanded_size: int, reason: str
) -> None:
    monkeypatch.setattr(artifacts, "ARTIFACT_LIMIT_IN_BYTES", 2048)
    assert_archive_refused(native_boundary, gzip.compress(b"\0" * expanded_size, mtime=0), reason)


def test_declared_oversized_member_is_rejected_before_read(native_boundary: NativeBoundary) -> None:
    member = regular_member()
    member.size = 64 * 1024 * 1024 + 1
    payload = gzip.compress(member.tobuf(format=tarfile.USTAR_FORMAT) + b"\0" * 1024, mtime=0)
    assert_archive_refused(native_boundary, payload, "member exceeds")


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
