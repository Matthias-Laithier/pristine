import http.client
import io
import os
import runpy
import socket
import ssl
import sys
import urllib.request
from collections.abc import Callable
from contextlib import ExitStack
from functools import partial
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, Never, override
from unittest.mock import Mock, patch

if TYPE_CHECKING:
    import pytest

    from pristine.services.native_tools.processes import ProcessResult

STALL_IN_SECONDS = 3
ARTIFACT_LIMIT_IN_BYTES = 64 * 1024 * 1024


def _record(path: Path, *event: object) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(" ".join(map(str, event)) + "\n")


def _stall(path: Path, stage: str, *arguments: object, **options: object) -> Never:
    del arguments, options
    _record(path, stage, os.getpid())
    sleep(STALL_IN_SECONDS)
    raise (socket.gaierror if stage == "dns" else TimeoutError)("controlled offline stall")


class _RecordedIO(io.BytesIO):
    def __init__(self, payload: bytes, path: Path, name: str) -> None:
        super().__init__(payload)
        self.path = path
        self.response_name = name

    @override
    def read(self, size: int | None = -1) -> bytes:
        assert isinstance(size, int) and 0 < size <= 65536
        _record(self.path, "read", self.response_name, size)
        return super().read(size)

    read1 = read

    @override
    def close(self) -> None:
        if not self.closed:
            _record(self.path, "close", self.response_name)
        super().close()


class OfflineDownload:
    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, root: Path, scenario: str, process_runner: Callable[..., ProcessResult]
    ) -> None:
        self.events_path = root / "download-events"
        self.results: list[ProcessResult] = []
        self.scenario = scenario
        self.process_runner = process_runner
        monkeypatch.setattr("pristine.services.native_tools.artifacts.run_process", self.run)

    def events(self) -> list[str]:
        return self.events_path.read_text().splitlines()

    def run(
        self, command: list[str], cwd: Path, *, timeout_in_seconds: float, output_limit_in_bytes: int
    ) -> ProcessResult:
        assert command[1:3] == ["-I", "-S"]
        assert cwd == Path(command[3]).parent and cwd.is_absolute()
        assert output_limit_in_bytes == ARTIFACT_LIMIT_IN_BYTES
        result = self.process_runner(
            [*command[:3], str(Path(__file__).resolve()), str(self.events_path), self.scenario, *command[3:]],
            cwd,
            timeout_in_seconds=timeout_in_seconds,
            output_limit_in_bytes=output_limit_in_bytes,
        )
        self.results.append(result)
        return result


def _open_response(scenario: str, path: Path) -> _RecordedIO:
    location = {
        "redirect": "https://release-assets.githubusercontent.com/pinned",
        "untrusted_redirect": "https://untrusted.invalid/pinned",
    }.get(scenario)
    size_in_bytes = {"limit": ARTIFACT_LIMIT_IN_BYTES + 1, "exact_limit": ARTIFACT_LIMIT_IN_BYTES}.get(scenario)
    payload = b"abc" if size_in_bytes is None else b"x" * size_in_bytes
    status = "302 Found" if location is not None else {"http_error": "404 Not Found"}.get(scenario, "200 OK")
    headers = "" if location is None else "Location: " + location + "\r\n"
    recording = ("HTTP/1.1 " + status + "\r\n" + headers + "\r\n").encode() + payload
    return _RecordedIO(recording, path, "artifact" if location is None else "redirect")


def _configure_https(scenario: str, path: Path, socket_timeout_in_seconds: float, lifetime: ExitStack) -> None:
    if scenario == "dns":
        lifetime.enter_context(patch.object(socket, "getaddrinfo", partial(_stall, path, "dns")))
        return

    def connect(connection: http.client.HTTPSConnection) -> None:
        assert connection.host in {"github.com", "release-assets.githubusercontent.com"}
        assert connection.timeout == socket_timeout_in_seconds
        context: object = vars(connection)["_context"]
        assert isinstance(context, ssl.SSLContext)
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        _record(path, "connect", connection.host)
        if scenario == "tls":
            raise ssl.SSLError("sensitive TLS error")
        stream = _open_response(scenario if connection.host == "github.com" else "body", path)
        if scenario == "headers":
            lifetime.enter_context(patch.object(stream, "readline", partial(_stall, path, "headers")))
        recorded_socket = Mock(spec=socket.socket)
        recorded_socket.makefile.return_value = stream
        lifetime.enter_context(patch.object(connection, "sock", recorded_socket))

    lifetime.enter_context(patch.object(http.client.HTTPSConnection, "connect", connect))


def _child() -> None:
    events_path, scenario, helper, *arguments = sys.argv[1:]
    with ExitStack() as lifetime:
        lifetime.enter_context(patch.object(urllib.request, "getproxies", dict))
        _configure_https(scenario, Path(events_path), float(arguments[-1]), lifetime)
        sys.argv = [helper, *arguments]
        runpy.run_path(helper, run_name="__main__")


if __name__ == "__main__":
    _child()
