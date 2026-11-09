import platform
import shutil
import tarfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pristine.services.native_tools.artifacts import (
    NativeToolUnavailable,
    ReleaseArtifact,
    cached_executable,
    download_artifact,
)
from pristine.services.native_tools.processes import ProcessResult, run_process

__all__ = ["NativeToolResolver", "NativeToolUnavailable", "ToolRelease", "resolve_tool"]

VERSION_TIMEOUT_IN_SECONDS = 5
VERSION_OUTPUT_LIMIT_IN_BYTES = 4096
OSV_RELEASE_URL = "https://github.com/google/osv-scanner/releases/download/v2.7.0/"
GITLEAKS_RELEASE_URL = "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/"


@dataclass(frozen=True)
class ToolRelease:
    name: Literal["osv-scanner", "gitleaks"]
    version: str
    artifacts: tuple[ReleaseArtifact, ...]


_RELEASES = (
    ToolRelease(
        "osv-scanner",
        "2.7.0",
        (
            ReleaseArtifact(
                "Darwin",
                "x86_64",
                OSV_RELEASE_URL + "osv-scanner_darwin_amd64",
                "e82c5df7ab0a42dff29a1cd0660711447b56b4c0483ff66ad8634df10fd81a45",
                "e82c5df7ab0a42dff29a1cd0660711447b56b4c0483ff66ad8634df10fd81a45",
            ),
            ReleaseArtifact(
                "Darwin",
                "arm64",
                OSV_RELEASE_URL + "osv-scanner_darwin_arm64",
                "d4926ef8da134332543be276dff157e4c170f99ad91fc48e89448a8816bdf70b",
                "d4926ef8da134332543be276dff157e4c170f99ad91fc48e89448a8816bdf70b",
            ),
            ReleaseArtifact(
                "Linux",
                "x86_64",
                OSV_RELEASE_URL + "osv-scanner_linux_amd64",
                "160c6253e2922e9e0a6a9771c5c4c40a4b3c6090b34a3cdd5e80c96cc2e4218b",
                "160c6253e2922e9e0a6a9771c5c4c40a4b3c6090b34a3cdd5e80c96cc2e4218b",
            ),
            ReleaseArtifact(
                "Linux",
                "arm64",
                OSV_RELEASE_URL + "osv-scanner_linux_arm64",
                "4061ef4c021ed3c47f203b818f337e351336cc5cd67c0274fc36bd1dfc728dd7",
                "4061ef4c021ed3c47f203b818f337e351336cc5cd67c0274fc36bd1dfc728dd7",
            ),
        ),
    ),
    ToolRelease(
        "gitleaks",
        "8.30.1",
        (
            ReleaseArtifact(
                "Darwin",
                "arm64",
                GITLEAKS_RELEASE_URL + "gitleaks_8.30.1_darwin_arm64.tar.gz",
                "b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5",
                "ba52fb1bfabbcde42f032afad3d6e0b19dff8ed105229a16e7caa338bbc0e84f",
                "gitleaks",
            ),
            ReleaseArtifact(
                "Darwin",
                "x86_64",
                GITLEAKS_RELEASE_URL + "gitleaks_8.30.1_darwin_x64.tar.gz",
                "dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709",
                "cee01fea7173f1b779dff188e1c26ecbcb4027d394acc573b23aaf0be260e291",
                "gitleaks",
            ),
            ReleaseArtifact(
                "Linux",
                "arm64",
                GITLEAKS_RELEASE_URL + "gitleaks_8.30.1_linux_arm64.tar.gz",
                "e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080",
                "00e91bbe655bd7c47753e8cfe61cb76ea1a5d7e7702fe161ee40102b46b3823b",
                "gitleaks",
            ),
            ReleaseArtifact(
                "Linux",
                "x86_64",
                GITLEAKS_RELEASE_URL + "gitleaks_8.30.1_linux_x64.tar.gz",
                "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
                "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509",
                "gitleaks",
            ),
        ),
    ),
)


class _ProcessRunner(Protocol):
    def __call__(
        self,
        command: list[str],
        cwd: Path,
        *,
        timeout_in_seconds: float,
        output_limit_in_bytes: int,
    ) -> ProcessResult: ...


class NativeToolResolver:
    def __init__(  # noqa: PLR0913
        self,
        cache_directory: Path,
        system: str,
        machine: str,
        *,
        releases: tuple[ToolRelease, ...] = _RELEASES,
        finder: Callable[[str], str | None] = shutil.which,
        process_runner: _ProcessRunner = run_process,
        download: Callable[[str], bytes] = download_artifact,
    ) -> None:
        self._cache_directory = cache_directory.absolute()
        self._system = system
        self._machine = "arm64" if machine == "aarch64" else machine
        self._releases = releases
        self._finder = finder
        self._process_runner = process_runner
        self._download = download

    def resolve_tool(self, name: Literal["osv-scanner", "gitleaks"]) -> str:
        release = next((release for release in self._releases if release.name == name), None)
        if release is None:
            raise NativeToolUnavailable("native tool is not supported")
        artifact = next(
            (
                artifact
                for artifact in release.artifacts
                if (artifact.system, artifact.machine) == (self._system, self._machine)
            ),
            None,
        )
        if artifact is None:
            raise NativeToolUnavailable("native tool platform is unsupported; use macOS or Linux on arm64 or x86_64")
        try:
            installed = self._compatible_installed(release)
            return installed or cached_executable(artifact, self._cache_directory, self._download)
        except OSError, tarfile.TarError, EOFError, ValueError:
            raise NativeToolUnavailable(
                "native tool lookup or cache failed; repair PATH or remove private cache and retry"
            ) from None

    def _compatible_installed(self, release: ToolRelease) -> str | None:
        installed = self._finder(release.name)
        if installed is None:
            return None
        try:
            executable = Path(installed).resolve(strict=True)
        except OSError, RuntimeError:
            return None
        if executable.is_relative_to(self._cache_directory.resolve()):
            return None
        argument = "--version" if release.name == "osv-scanner" else "version"
        result = self._process_runner(
            [str(executable), argument],
            self._cache_directory.parent,
            timeout_in_seconds=VERSION_TIMEOUT_IN_SECONDS,
            output_limit_in_bytes=VERSION_OUTPUT_LIMIT_IN_BYTES,
        )
        expected = "osv-scanner version: " + release.version if release.name == "osv-scanner" else release.version
        first_line = result.stdout.partition(b"\n")[0].rstrip(b"\r")
        if result.problem is None and result.returncode == 0 and first_line == expected.encode():
            return str(executable)
        return None


def resolve_tool(name: Literal["osv-scanner", "gitleaks"]) -> str:
    try:
        home = Path.home()
    except RuntimeError as error:
        raise NativeToolUnavailable("native tool home directory is unavailable") from error
    if not home.is_absolute():
        raise NativeToolUnavailable("native tools require an absolute home directory")
    return NativeToolResolver(
        home / ".pristine-native-tools",
        platform.system(),
        platform.machine(),
    ).resolve_tool(name)
