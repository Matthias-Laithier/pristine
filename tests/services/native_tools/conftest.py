from pathlib import Path
from typing import Literal

import pytest

from pristine.services.native_tools.artifacts import ReleaseArtifact
from pristine.services.native_tools.processes import ProcessResult
from pristine.services.native_tools.resolver import NativeToolResolver, ToolRelease

FIXTURE_DIGEST = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
FIXTURE_URL = "https://github.com/google/osv-scanner/releases/download/v2.7.0/fixture"


class NativeBoundary:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.installed: str | None = None
        self.payload = b"abc"
        self.download_calls: list[str] = []
        self.commands: list[list[str]] = []
        self.version = ProcessResult(b"osv-scanner version: 2.7.0\n", b"", 0, None)
        self.download_error: OSError | None = None

    def find(self, name: str) -> str | None:
        assert name in {"osv-scanner", "gitleaks"}
        return self.installed

    def run(
        self, command: list[str], cwd: Path, *, timeout_in_seconds: float, output_limit_in_bytes: int
    ) -> ProcessResult:
        assert cwd == self.root.parent
        assert timeout_in_seconds == 5
        assert output_limit_in_bytes == 4096
        self.commands.append(command)
        return self.version

    def download(self, url: str) -> bytes:
        self.download_calls.append(url)
        if self.download_error is not None:
            raise self.download_error
        return self.payload

    def resolver(
        self, name: Literal["osv-scanner", "gitleaks"] = "osv-scanner", artifact: ReleaseArtifact | None = None
    ) -> NativeToolResolver:
        artifact = artifact or ReleaseArtifact("Darwin", "arm64", FIXTURE_URL, FIXTURE_DIGEST, FIXTURE_DIGEST)
        version = "2.7.0" if name == "osv-scanner" else "8.30.1"
        return NativeToolResolver(
            self.root,
            "Darwin",
            "arm64",
            releases=(ToolRelease(name, version, (artifact,)),),
            finder=self.find,
            process_runner=self.run,
            download=self.download,
        )


@pytest.fixture
def native_boundary(tmp_path: Path) -> NativeBoundary:
    return NativeBoundary(tmp_path / "private-cache")
