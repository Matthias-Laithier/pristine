import os
import signal
from pathlib import Path
from time import monotonic

import pytest

from pristine.services.native_tools import artifacts
from pristine.services.native_tools.artifacts import NativeToolUnavailable, download_artifact
from pristine.services.native_tools.processes import run_process
from tests.services.native_tools.conftest import FIXTURE_URL
from tests.services.native_tools.http_fakes import OfflineDownload

DOWNLOAD_DEADLINE_IN_SECONDS = 1
SCHEDULING_TOLERANCE_IN_SECONDS = 0.1
REAP_TOLERANCE_IN_SECONDS = 0.1


def test_verified_tls_and_trusted_redirect_read_only_bounded_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "sitecustomize.py").write_text("raise RuntimeError('audited startup ran')\n")
    (tmp_path / "http.py").write_text("raise RuntimeError('audited module ran')\n")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    boundary = OfflineDownload(monkeypatch, tmp_path, "redirect", run_process)
    assert download_artifact(FIXTURE_URL) == b"abc"
    assert boundary.results[0].stderr == b""
    events = boundary.events()
    assert [event for event in events if event.startswith("connect ")] == [
        "connect github.com",
        "connect release-assets.githubusercontent.com",
    ]
    assert not any(event.startswith("read redirect ") for event in events)
    assert {event for event in events if event.startswith("close ")} == {"close redirect", "close artifact"}


def test_untrusted_download_origin_never_connects(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boundary = OfflineDownload(monkeypatch, tmp_path, "body", run_process)
    with pytest.raises(NativeToolUnavailable, match="not trusted"):
        download_artifact("https://github.com.evil.invalid/pinned")
    assert not boundary.events_path.exists()


def test_untrusted_redirect_is_closed_before_following(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boundary = OfflineDownload(monkeypatch, tmp_path, "untrusted_redirect", run_process)
    with pytest.raises(NativeToolUnavailable, match="not trusted"):
        download_artifact(FIXTURE_URL)
    assert boundary.events() == ["connect github.com", "close redirect"]


@pytest.mark.parametrize("scenario", ["exact_limit", "limit"])
def test_download_size_boundary_is_bounded_and_closes_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scenario: str
) -> None:
    boundary = OfflineDownload(monkeypatch, tmp_path, scenario, run_process)
    if scenario == "exact_limit":
        assert download_artifact(FIXTURE_URL) == b"x" * (64 * 1024 * 1024)
    else:
        with pytest.raises(NativeToolUnavailable, match="size limit"):
            download_artifact(FIXTURE_URL)
    events = boundary.events()
    assert events[-1] == "close artifact"
    sizes = [int(event.split()[-1]) for event in events if event.startswith("read ")]
    assert 65536 in sizes and sizes[-1] == 1
    assert all(0 < size <= 65536 for size in sizes)


def test_tls_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boundary = OfflineDownload(monkeypatch, tmp_path, "tls", run_process)
    with pytest.raises(NativeToolUnavailable, match="check HTTPS connectivity") as failure:
        download_artifact(FIXTURE_URL)
    assert "sensitive" not in str(failure.value)
    assert boundary.events() == ["connect github.com"]


def test_http_error_response_is_closed_without_reading_its_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    boundary = OfflineDownload(monkeypatch, tmp_path, "http_error", run_process)
    with pytest.raises(NativeToolUnavailable, match="check HTTPS connectivity"):
        download_artifact(FIXTURE_URL)
    assert boundary.events() == ["connect github.com", "close artifact"]


@pytest.mark.parametrize("stage", ["dns", "headers"])
def test_whole_download_deadline_kills_and_reaps_entered_stall(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stage: str
) -> None:
    boundary = OfflineDownload(monkeypatch, tmp_path, stage, run_process)
    monkeypatch.setattr(artifacts, "DOWNLOAD_TIMEOUT_IN_SECONDS", DOWNLOAD_DEADLINE_IN_SECONDS)
    monkeypatch.setattr(artifacts, "SOCKET_TIMEOUT_IN_SECONDS", 0.01)
    started = monotonic()
    with pytest.raises(NativeToolUnavailable) as failure:
        download_artifact(FIXTURE_URL)
    elapsed_in_seconds = monotonic() - started
    event = next(event for event in boundary.events() if event.startswith(stage + " "))
    entered_stage, child_pid = event.split()
    assert entered_stage == stage
    pid = int(child_pid)
    assert pid != os.getpid()
    assert elapsed_in_seconds <= (
        DOWNLOAD_DEADLINE_IN_SECONDS + SCHEDULING_TOLERANCE_IN_SECONDS + REAP_TOLERANCE_IN_SECONDS
    )
    assert "timed out" in str(failure.value)
    assert boundary.results[0].returncode == -signal.SIGKILL
    with pytest.raises(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
