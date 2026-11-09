import http.client
import ssl
import sys
import urllib.error
import urllib.request
from math import isfinite
from typing import IO, override

__all__ = ["ARTIFACT_LIMIT_IN_BYTES", "DOWNLOAD_FAILURE", "FAILURE_MESSAGES", "NativeToolUnavailable"]

ARTIFACT_LIMIT_IN_BYTES = 64 * 1024 * 1024
READ_CHUNK_IN_BYTES = 65536
TRUSTED_ORIGINS = ("https://github.com/", "https://release-assets.githubusercontent.com/")
DOWNLOAD_FAILURE = "native tool download failed; check HTTPS connectivity and retry"
_UNTRUSTED_URL = "native tool release URL is not trusted"
_INVALID_RESPONSE = "native tool release response is not HTTPS"
_SIZE_LIMIT = "native tool release exceeded the download size limit"
FAILURE_MESSAGES = (DOWNLOAD_FAILURE, _UNTRUSTED_URL, _INVALID_RESPONSE, _SIZE_LIMIT)


class NativeToolUnavailable(Exception):
    pass


def _trusted_url(url: str) -> None:
    if not url.startswith(TRUSTED_ORIGINS):
        raise NativeToolUnavailable(_UNTRUSTED_URL)


class _TrustedRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 2
    max_repeats = 1

    @override
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        fp.close()
        _trusted_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(url: str, socket_timeout_in_seconds: float) -> bytes:
    _trusted_url(url)
    opener = urllib.request.build_opener(
        _TrustedRedirects(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    try:
        with opener.open(url, timeout=socket_timeout_in_seconds) as response:
            return _download_body(response)
    except (OSError, urllib.error.URLError, http.client.HTTPException, ValueError) as error:
        if isinstance(error, urllib.error.HTTPError):
            error.close()
        raise NativeToolUnavailable(DOWNLOAD_FAILURE) from None


def _download_body(response: object) -> bytes:
    if not isinstance(response, http.client.HTTPResponse):
        raise NativeToolUnavailable(_INVALID_RESPONSE)
    payload = bytearray()
    while True:
        chunk = response.read1(min(READ_CHUNK_IN_BYTES, ARTIFACT_LIMIT_IN_BYTES - len(payload) + 1))
        if not chunk:
            return bytes(payload)
        payload.extend(chunk)
        if len(payload) > ARTIFACT_LIMIT_IN_BYTES:
            raise NativeToolUnavailable(_SIZE_LIMIT)


def _main() -> int:
    _, url, socket_timeout = sys.argv
    socket_timeout_in_seconds = float(socket_timeout)
    if not isfinite(socket_timeout_in_seconds) or socket_timeout_in_seconds <= 0:
        raise ValueError("native tool socket timeout must be positive")
    try:
        payload = _download(url, socket_timeout_in_seconds)
    except NativeToolUnavailable as error:
        sys.stderr.write(str(error))
        return 1
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
