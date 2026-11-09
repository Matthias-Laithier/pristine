import ssl

import pytest

from pristine.services.native_tools import artifacts
from pristine.services.native_tools.artifacts import NativeToolUnavailable, download_artifact
from tests.services.native_tools.conftest import FIXTURE_URL
from tests.services.native_tools.http_fakes import NativeResponse, install_https


def test_verified_tls_and_trusted_redirect_read_only_bounded_body(monkeypatch: pytest.MonkeyPatch) -> None:
    redirect = NativeResponse(b"ignored redirect body", "https://release-assets.githubusercontent.com/pinned")
    payload = NativeResponse(b"abc")
    requests: list[str] = []
    install_https(monkeypatch, [redirect, payload], requests)
    assert download_artifact(FIXTURE_URL) == b"abc"
    assert requests == ["github.com", "release-assets.githubusercontent.com"]
    assert redirect.read_sizes == []
    assert redirect.isclosed() and payload.isclosed()


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/pinned",
        "https://untrusted.invalid/pinned",
        "https://github.com.evil.invalid/pinned",
        "https://token@github.com/pinned",
    ],
)
def test_untrusted_download_origin_never_connects(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    requests: list[str] = []
    install_https(monkeypatch, [], requests)
    with pytest.raises(NativeToolUnavailable, match="not trusted"):
        download_artifact(url)
    assert requests == []


@pytest.mark.parametrize("url", ["http://github.com/pinned", "https://untrusted.invalid/pinned"])
def test_untrusted_redirect_is_closed_before_following(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    response = NativeResponse(b"never read this body", url)
    requests: list[str] = []
    install_https(monkeypatch, [response], requests)
    with pytest.raises(NativeToolUnavailable, match="not trusted"):
        download_artifact(FIXTURE_URL)
    assert requests == ["github.com"]
    assert response.isclosed()


def test_download_deadline_closes_the_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = NativeResponse(b"abc")
    requests: list[str] = []
    install_https(monkeypatch, [response], requests)
    clock = iter((0.0, 60.0))
    monkeypatch.setattr(artifacts, "monotonic", lambda: next(clock))
    with pytest.raises(NativeToolUnavailable, match="timed out"):
        download_artifact(FIXTURE_URL)
    assert response.isclosed()
    assert response.read_sizes == []


def test_download_rejects_limit_plus_one_and_closes_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = NativeResponse(b"x" * (64 * 1024 * 1024 + 1))
    requests: list[str] = []
    install_https(monkeypatch, [response], requests)
    with pytest.raises(NativeToolUnavailable, match="size limit"):
        download_artifact(FIXTURE_URL)
    assert response.isclosed()
    assert max(response.read_sizes) == 65536
    assert response.read_sizes[-1] == 1


def test_tls_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    install_https(monkeypatch, [], [], ssl.SSLError("sensitive TLS error"))
    with pytest.raises(NativeToolUnavailable, match="check HTTPS connectivity") as failure:
        download_artifact(FIXTURE_URL)
    assert "sensitive" not in str(failure.value)


def test_http_error_response_is_closed_without_reading_its_body(monkeypatch: pytest.MonkeyPatch) -> None:
    response = NativeResponse(b"unread error body")
    response.status = response.code = 404
    requests: list[str] = []
    install_https(monkeypatch, [response], requests)
    with pytest.raises(NativeToolUnavailable, match="check HTTPS connectivity"):
        download_artifact(FIXTURE_URL)
    assert response.isclosed()
    assert response.read_sizes == []
