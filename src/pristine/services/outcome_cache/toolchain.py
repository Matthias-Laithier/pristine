import hashlib
import locale
import os
import sys
from functools import cache
from importlib.util import find_spec
from pathlib import Path

from pristine.services.grammars import SUPPORTED_LANGUAGES, grammar_library_directory

FINGERPRINT_VERSION = "toolchain-1"
PACKAGES = ("pristine", "tree_sitter", "tree_sitter_language_pack")
BYTECODE_DIRECTORY = "__pycache__"
GRAMMAR_LIBRARY_STEMS = frozenset(
    stem for language in SUPPORTED_LANGUAGES for stem in (f"libtree_sitter_{language}", f"tree_sitter_{language}")
)


class ToolchainUnavailable(Exception):
    pass


def package_directory(name: str) -> Path:
    spec = find_spec(name)
    locations = None if spec is None else spec.submodule_search_locations
    if locations is None or len(locations) == 0:
        raise ToolchainUnavailable(f"package {name} has no source directory")
    return Path(next(iter(locations)))


def package_files(directory: Path) -> list[Path]:
    files = []
    for base, directories, names in directory.walk():
        directories[:] = sorted(name for name in directories if name != BYTECODE_DIRECTORY)
        files.extend(base / name for name in sorted(names))
    return files


def grammar_libraries(directory: Path) -> list[Path]:
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    return [directory / name for name in names if name.split(".", 1)[0] in GRAMMAR_LIBRARY_STEMS]


def file_digest(path: Path) -> bytes:
    try:
        with path.open("rb") as source:
            return hashlib.file_digest(source, "sha256").digest()
    except OSError as error:
        raise ToolchainUnavailable(f"could not read {path}: {error.strerror}") from error


def labelled(label: str, content: bytes) -> bytes:
    name = os.fsencode(label)
    return len(name).to_bytes(8, "big") + name + content


def runtime_identity() -> bytes:
    runtime = (sys.version, sys.implementation.cache_tag, locale.getencoding(), sys.flags.utf8_mode)
    return repr(runtime).encode()


def fingerprint_of(packages: dict[str, Path], grammars: Path, runtime: bytes) -> str:
    digest = hashlib.sha256(labelled(FINGERPRINT_VERSION, runtime))
    for package, root in packages.items():
        for path in package_files(root):
            digest.update(labelled(f"{package}/{path.relative_to(root).as_posix()}", file_digest(path)))
    digest.update(labelled("grammars", os.fsencode(grammars)))
    for path in grammar_libraries(grammars):
        digest.update(labelled(f"grammar/{path.name}", file_digest(path)))
    return digest.hexdigest()


@cache
def toolchain_fingerprint() -> str:
    packages = {package: package_directory(package) for package in PACKAGES}
    return fingerprint_of(packages, grammar_library_directory(), runtime_identity())
