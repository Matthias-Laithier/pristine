import hashlib
import os
from collections.abc import Iterable

from pristine.engine.read_digests import link_signature, read_digest, signature_of
from pristine.reports.outcomes import Checked, FileRead, Outcome, Signature

KEY_VERSION = "file-key-2"
ABSENT = b"absent"


def digest_of(*fields: bytes | str) -> bytes:
    digest = hashlib.sha256()
    for field in fields:
        data = os.fsencode(field) if isinstance(field, str) else field
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.digest()


class FileInputs:
    def __init__(self, cwd: str) -> None:
        self.cwd = cwd
        self.sources: dict[str, Signature | None] = {}
        self.reads: dict[str, Signature | None] = {}
        self.real_directories: dict[str, str] = {}
        self.digests: dict[tuple[str, bool], str] = {}
        self.inputs_of: dict[str, tuple[str, ...]] = {}

    def source_digest(self, path: str) -> bytes:
        try:
            with open(path, "rb") as source:
                self.sources[path] = signature_of(os.fstat(source.fileno()))
                return hashlib.file_digest(source, "sha256").digest()
        except OSError:
            self.sources[path] = None
            return ABSENT

    def key(self, path: str) -> str | None:
        location = os.path.join(self.cwd, path)
        content = self.source_digest(location)
        if self.sources[location] is None:
            return None
        self.inputs_of[path] = (location,)
        return digest_of(KEY_VERSION, self.cwd, path, self.resolved(location), content).hex()

    def current(self, path: str, read: FileRead) -> bool:
        digest = self.digests.get((path, read.listed))
        if digest is None:
            digest = self.digests[path, read.listed] = read_digest(path, listed=read.listed)
        return digest == read.digest

    def reusable(self, outcome: Outcome) -> bool:
        if not isinstance(outcome, Checked):
            return True
        return outcome.reads is not None and all(self.current(path, read) for path, read in outcome.reads.items())

    def observed(self, path: str, outcome: Outcome) -> bool:
        if not isinstance(outcome, Checked):
            return True
        if outcome.reads is None:
            return False
        self.inputs_of[path] = (*self.inputs_of.get(path, ()), *outcome.reads)
        for read_path, read in outcome.reads.items():
            self.reads.setdefault(read_path, read.signature)
        return True

    def exists(self, path: str) -> bool:
        return os.path.lexists(os.path.join(self.cwd, path))

    def changed(self) -> set[str]:
        sources = {path for path, signature in self.sources.items() if source_signature(path) != signature}
        return sources | {path for path, signature in self.reads.items() if link_signature(path) != signature}

    def changed_paths(self, paths: Iterable[str]) -> frozenset[str]:
        changed = self.changed()
        return frozenset(path for path in paths if not changed.isdisjoint(self.inputs_of.get(path, (path,))))

    def resolved(self, location: str) -> str:
        directory, name = os.path.split(location)
        real = self.real_directories.get(directory)
        if real is None:
            real = self.real_directories[directory] = os.path.realpath(directory)
        candidate = os.path.join(real, name)
        return os.path.realpath(candidate) if os.path.islink(candidate) else candidate


def source_signature(path: str) -> Signature | None:
    try:
        return signature_of(os.stat(path))
    except OSError:
        return None
