import http.client
import io
import ssl
from typing import override

import pytest


class NativeResponse(http.client.HTTPResponse):
    def __init__(self, payload: bytes, location: str | None = None) -> None:
        self.stream = io.BytesIO(payload)
        self.status = 200 if location is None else 302
        self.code = self.status
        self.reason = "OK" if location is None else "Found"
        self.headers = http.client.HTTPMessage()
        if location is not None:
            self.headers["Location"] = location
        self.read_sizes: list[int] = []

    @override
    def read1(self, n: int = -1) -> bytes:
        assert 0 < n <= 65536
        self.read_sizes.append(n)
        return self.read(n)

    @override
    def read(self, amt: int | None = None) -> bytes:
        if self.stream.closed:
            return b""
        assert amt is not None
        return self.stream.read(amt)

    @override
    def close(self) -> None:
        self.stream.close()

    @override
    def isclosed(self) -> bool:
        return self.stream.closed


class NativeConnection:
    def __init__(self, response: NativeResponse) -> None:
        self.response = response
        self.sock = None

    def set_debuglevel(self, level: int) -> None:
        assert level == 0

    def request(
        self, method: str, path: str, body: bytes | None, headers: dict[str, str], *, encode_chunked: bool
    ) -> None:
        assert method == "GET"
        assert path.startswith("/")
        assert body is None
        assert headers["Connection"] == "close"
        assert not encode_chunked

    def getresponse(self) -> NativeResponse:
        return self.response

    def close(self) -> None:
        self.response.close()


def install_https(
    monkeypatch: pytest.MonkeyPatch, responses: list[NativeResponse], requests: list[str], error: OSError | None = None
) -> None:
    def connect(host: str, **options: object) -> NativeConnection:
        assert host in {"github.com", "release-assets.githubusercontent.com"}
        assert options["timeout"] == 10
        context = options["context"]
        assert isinstance(context, ssl.SSLContext)
        assert context.check_hostname
        assert context.verify_mode == ssl.CERT_REQUIRED
        requests.append(host)
        if error is not None:
            raise error
        return NativeConnection(responses.pop(0))

    monkeypatch.setattr(connect, "debuglevel", 0, raising=False)
    monkeypatch.setattr(http.client, "HTTPSConnection", connect)
