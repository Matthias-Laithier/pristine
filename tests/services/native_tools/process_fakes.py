import os
import signal
import subprocess
from pathlib import Path
from typing import BinaryIO

import pytest


def output_pipe(payload: bytes) -> BinaryIO:
    reader, writer = os.pipe()
    try:
        os.write(writer, payload)
    finally:
        os.close(writer)
    return os.fdopen(reader, "rb")


class NativeProcess:
    def __init__(self, stdout: bytes = b"abc", stderr: bytes = b"de") -> None:
        self.stdout = output_pipe(stdout)
        self.stderr = output_pipe(stderr)
        self.returncode: int | None = None
        self.pid = 424242
        self.events: list[str] = []
        self.reap_failure = False

    def wait(self, timeout: float) -> int:
        assert timeout == 5
        self.events.append("reap")
        if self.reap_failure:
            raise subprocess.TimeoutExpired("native fixture", timeout)
        self.returncode = 0
        return 0

    def kill_group(self, process_group: int, requested_signal: int) -> None:
        assert process_group == self.pid
        assert requested_signal == signal.SIGKILL
        assert self.returncode is None
        self.events.append("kill")

    def wait_without_reaping(self, idtype: int, pid: int, options: int) -> os.waitid_result:
        assert idtype == os.P_PID
        assert pid == self.pid
        assert options == os.WEXITED | os.WNOWAIT | os.WNOHANG
        self.events.append("observe-exit")
        return os.waitid_result((self.pid, 0, signal.SIGCHLD, 0, os.CLD_EXITED))

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def start(command: list[str], **options: object) -> NativeProcess:
            assert command == ["/native/tool", "--version"]
            cwd = options["cwd"]
            assert isinstance(cwd, Path)
            assert cwd.is_absolute()
            assert options["stdin"] == subprocess.DEVNULL
            assert options["stdout"] == options["stderr"] == subprocess.PIPE
            assert options["start_new_session"]
            return self

        monkeypatch.setattr(subprocess, "Popen", start)
        monkeypatch.setattr(os, "killpg", self.kill_group)
        monkeypatch.setattr(os, "waitid", self.wait_without_reaping)
