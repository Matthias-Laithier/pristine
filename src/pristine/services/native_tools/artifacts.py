import gzip
import hashlib
import http.client
import io
import os
import re
import secrets
import ssl
import stat
import tarfile
import urllib.error
import urllib.request
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import IO, override

__all__ = ["NativeToolUnavailable", "ReleaseArtifact", "cached_executable", "download_artifact"]

DOWNLOAD_TIMEOUT_IN_SECONDS = 60
SOCKET_TIMEOUT_IN_SECONDS = 10
ARTIFACT_LIMIT_IN_BYTES = 64 * 1024 * 1024
READ_CHUNK_IN_BYTES = 65536
TRUSTED_ORIGINS = ("https://github.com/", "https://release-assets.githubusercontent.com/")
PRIVATE_MODE = 0o700


@dataclass(frozen=True)
class ReleaseArtifact:
    system: str
    machine: str
    url: str
    download_sha256: str
    executable_sha256: str
    archive_member: str | None = None


class NativeToolUnavailable(Exception):
    pass


def _trusted_url(url: str) -> None:
    if not url.startswith(TRUSTED_ORIGINS):
        raise NativeToolUnavailable("native tool release URL is not trusted")


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


def download_artifact(url: str) -> bytes:
    _trusted_url(url)
    deadline = monotonic() + DOWNLOAD_TIMEOUT_IN_SECONDS
    opener = urllib.request.build_opener(
        _TrustedRedirects(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    try:
        with opener.open(url, timeout=SOCKET_TIMEOUT_IN_SECONDS) as response:
            return _download_body(response, deadline)
    except (OSError, urllib.error.URLError, http.client.HTTPException, ValueError) as error:
        if isinstance(error, urllib.error.HTTPError):
            error.close()
        raise NativeToolUnavailable("native tool download failed; check HTTPS connectivity and retry") from None


def _download_body(response: object, deadline: float) -> bytes:
    if not isinstance(response, http.client.HTTPResponse):
        raise NativeToolUnavailable("native tool release response is not HTTPS")
    payload = bytearray()
    while True:
        if monotonic() >= deadline:
            raise NativeToolUnavailable("native tool download timed out; retry with a working connection")
        chunk = response.read1(min(READ_CHUNK_IN_BYTES, ARTIFACT_LIMIT_IN_BYTES - len(payload) + 1))
        if not chunk:
            return bytes(payload)
        payload.extend(chunk)
        if len(payload) > ARTIFACT_LIMIT_IN_BYTES:
            raise NativeToolUnavailable("native tool release exceeded the download size limit")


def _executable_payload(artifact: ReleaseArtifact, payload: bytes) -> bytes:
    if len(payload) > ARTIFACT_LIMIT_IN_BYTES or hashlib.sha256(payload).hexdigest() != artifact.download_sha256:
        raise NativeToolUnavailable("native tool release checksum failed; retry from the official release")
    if artifact.archive_member is None:
        return payload
    with tarfile.open(fileobj=io.BytesIO(_expanded_archive(payload)), mode="r|") as archive:
        return _archive_executable(artifact, archive)


def _archive_executable(artifact: ReleaseArtifact, archive: tarfile.TarFile) -> bytes:
    allowed_names = {"LICENSE", "README.md", artifact.archive_member}
    executable = None
    for count, member in enumerate(archive, start=1):
        if count > len(allowed_names) or not member.isreg() or member.name not in allowed_names:
            raise NativeToolUnavailable("native tool release archive contains an unexpected member")
        if member.size > ARTIFACT_LIMIT_IN_BYTES or member.size < 0:
            raise NativeToolUnavailable("native tool release archive member exceeds the size limit")
        if member.name != artifact.archive_member:
            continue
        if executable is not None:
            raise NativeToolUnavailable("native tool release archive repeats its executable")
        stream = archive.extractfile(member)
        if stream is None:
            raise NativeToolUnavailable("native tool release executable could not be read")
        with stream:
            executable = stream.read(member.size)
    if executable is None:
        raise NativeToolUnavailable("native tool release archive has no executable")
    return executable


def _expanded_archive(payload: bytes) -> bytes:
    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as compressed:
        expanded = compressed.read(ARTIFACT_LIMIT_IN_BYTES + 1)
    if len(expanded) > ARTIFACT_LIMIT_IN_BYTES:
        raise NativeToolUnavailable("native tool release archive exceeds the expanded size limit")
    return expanded


def _owned_directory(descriptor: int, *, private: bool) -> None:
    metadata = os.fstat(descriptor)
    mode = stat.S_IMODE(metadata.st_mode)
    if metadata.st_uid != os.getuid() or mode & 0o022 or (private and mode != PRIVATE_MODE):
        raise NativeToolUnavailable("native tool cache must be owned and private; repair its permissions and retry")


@contextmanager
def _cache_directory(root: Path) -> Generator[int]:
    with ExitStack() as lifetime:
        parent = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        lifetime.callback(os.close, parent)
        _owned_directory(parent, private=False)
        with suppress(FileExistsError):
            os.mkdir(root.name, mode=PRIVATE_MODE, dir_fd=parent)
        descriptor = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        lifetime.callback(os.close, descriptor)
        _owned_directory(descriptor, private=True)
        yield descriptor


def _verified_cache(descriptor: int, digest: str) -> bool:
    try:
        executable = os.open(digest, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
    except FileNotFoundError:
        return False
    with os.fdopen(executable, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if metadata.st_mode != stat.S_IFREG | PRIVATE_MODE or metadata.st_uid != os.getuid():
            raise NativeToolUnavailable("native tool cache entry is unsafe; remove the private cache and retry")
        if hashlib.sha256(stream.read(ARTIFACT_LIMIT_IN_BYTES + 1)).hexdigest() != digest:
            raise NativeToolUnavailable("native tool cache is corrupt; remove the private cache and retry")
    return True


def _place_executable(descriptor: int, digest: str, payload: bytes) -> None:
    if not payload or hashlib.sha256(payload).hexdigest() != digest:
        raise NativeToolUnavailable("native tool executable checksum failed; retry from the official release")
    temporary_name = ".download-" + secrets.token_hex(16)
    temporary = os.open(
        temporary_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, PRIVATE_MODE, dir_fd=descriptor
    )
    try:
        with os.fdopen(temporary, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        with suppress(FileExistsError):
            os.link(temporary_name, digest, src_dir_fd=descriptor, dst_dir_fd=descriptor, follow_symlinks=False)
    finally:
        os.unlink(temporary_name, dir_fd=descriptor)


def cached_executable(artifact: ReleaseArtifact, root: Path, download: Callable[[str], bytes]) -> str:
    if re.fullmatch(r"[a-f0-9]{64}", artifact.executable_sha256) is None:
        raise NativeToolUnavailable("native tool executable pin is invalid")
    with _cache_directory(root) as descriptor:
        if _verified_cache(descriptor, artifact.executable_sha256):
            return str(root / artifact.executable_sha256)
        _place_executable(descriptor, artifact.executable_sha256, _executable_payload(artifact, download(artifact.url)))
        if not _verified_cache(descriptor, artifact.executable_sha256):
            raise NativeToolUnavailable("native tool cache changed concurrently; retry")
        return str(root / artifact.executable_sha256)
