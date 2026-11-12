import hashlib
import os
from collections.abc import Iterable

KEY_VERSION = "file-key-1"
MANIFEST = "pyproject.toml"
PACKAGE_MAIN = "__main__.py"
ABSENT = b"absent"

type Signature = tuple[int, int, int, int, int] | None


def digest_of(*fields: bytes | str) -> bytes:
    digest = hashlib.sha256()
    for field in fields:
        data = os.fsencode(field) if isinstance(field, str) else field
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.digest()


def signature_of(metadata: os.stat_result) -> Signature:
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns)


def current_signature(path: str) -> Signature:
    try:
        return signature_of(os.stat(path))
    except OSError:
        return None


class FileInputs:
    def __init__(self, cwd: str) -> None:
        self.cwd = cwd
        self.signatures: dict[str, Signature] = {}
        self.real_directories: dict[str, str] = {}
        self.contexts: dict[str, tuple[bytes, tuple[str, ...]]] = {}
        self.manifest_chains: dict[str, tuple[bytes, tuple[str, ...]]] = {}
        self.inputs_of: dict[str, tuple[str, ...]] = {}

    def read_digest(self, path: str) -> bytes:
        try:
            with open(path, "rb") as source:
                self.signatures[path] = signature_of(os.fstat(source.fileno()))
                return hashlib.file_digest(source, "sha256").digest()
        except OSError:
            self.signatures[path] = None
            return ABSENT

    def key(self, path: str) -> str | None:
        location = os.path.join(self.cwd, path)
        content = self.read_digest(location)
        if self.signatures[location] is None:
            return None
        resolved = self.resolved(location)
        context, inputs = self.context(os.path.dirname(resolved))
        self.inputs_of[path] = (location, *inputs)
        return digest_of(KEY_VERSION, self.cwd, path, resolved, content, context).hex()

    def exists(self, path: str) -> bool:
        return os.path.lexists(os.path.join(self.cwd, path))

    def changed_paths(self, paths: Iterable[str]) -> frozenset[str]:
        changed = {item for item, signature in self.signatures.items() if current_signature(item) != signature}
        return frozenset(path for path in paths if not changed.isdisjoint(self.inputs_of.get(path, (path,))))

    def resolved(self, location: str) -> str:
        directory, name = os.path.split(location)
        real = self.real_directories.get(directory)
        if real is None:
            real = self.real_directories[directory] = os.path.realpath(directory)
        candidate = os.path.join(real, name)
        return os.path.realpath(candidate) if os.path.islink(candidate) else candidate

    def context(self, directory: str) -> tuple[bytes, tuple[str, ...]]:
        context = self.contexts.get(directory)
        if context is None:
            package_main = os.path.join(directory, PACKAGE_MAIN)
            chain, manifests = self.manifest_chain(directory)
            context = digest_of(chain, self.read_digest(package_main)), (*manifests, package_main)
            self.contexts[directory] = context
        return context

    def manifest_chain(self, directory: str) -> tuple[bytes, tuple[str, ...]]:
        chain = self.manifest_chains.get(directory)
        if chain is None:
            manifest = os.path.join(directory, MANIFEST)
            parent = os.path.dirname(directory)
            outer, outer_manifests = (b"", ()) if parent == directory else self.manifest_chain(parent)
            chain = digest_of(self.read_digest(manifest), outer), (manifest, *outer_manifests)
            self.manifest_chains[directory] = chain
        return chain
