import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pristine.files.discovery import display_path, expand
from pristine.project.repository.makefile import Makefile, load_makefile
from pristine.project.repository.manifests import MANIFEST_READERS, Manifest
from pristine.project.repository.sources import SourceReader
from pristine.project.repository.tools import Ecosystem

MAKEFILE_NAMES = ("GNUmakefile", "makefile", "Makefile")
TEMPLATE_DIRECTORIES = frozenset({"template", "templates"})
CONTAINER_BUILD_FILE = re.compile(r"^(?:(?:Dockerfile|Containerfile)(?:\..+)?|.+\.[Dd]ockerfile)$")


@dataclass(frozen=True)
class Project:
    root: Path
    entries: frozenset[str]
    files: tuple[str, ...]
    makefile_path: str | None
    makefile: Makefile | None
    manifests: dict[Ecosystem, list[Manifest]]
    reader: SourceReader

    @property
    def file_names(self) -> frozenset[str]:
        return self.entries | {PurePosixPath(path).name for path in self.files}

    def shown(self, relative: str) -> str:
        return display_path(self.root / relative)

    def files_named(self, names: tuple[str, ...]) -> list[str]:
        return [path for path in self.files if PurePosixPath(path).name in names]

    def container_build_files(self) -> list[str]:
        return [path for path in self.files if CONTAINER_BUILD_FILE.match(PurePosixPath(path).name)]

    def root_manifest(self, ecosystem: Ecosystem) -> Manifest | None:
        filename, _ = MANIFEST_READERS[ecosystem]
        return next((manifest for manifest in self.manifests[ecosystem] if manifest.path == filename), None)


def project_files(root: Path) -> tuple[str, ...]:
    relative = (path.relative_to(root).as_posix() for path in expand(root))
    return tuple(sorted(path for path in relative if TEMPLATE_DIRECTORIES.isdisjoint(path.split("/"))))


def read_manifest(reader: SourceReader, ecosystem: Ecosystem, path: str) -> Manifest | None:
    _, parse = MANIFEST_READERS[ecosystem]
    text = reader.text(path)
    if text is None:
        return None
    try:
        return parse(path, text)
    except (ValueError, TypeError) as error:
        reader.reject(path, f"invalid {path}: {error}")
        return None


def manifest_paths(ecosystem: Ecosystem, entries: frozenset[str], files: tuple[str, ...]) -> list[str]:
    filename, _ = MANIFEST_READERS[ecosystem]
    nested = {path for path in files if PurePosixPath(path).name == filename}
    return sorted(nested | ({filename} & entries))


def read_manifests(reader: SourceReader, ecosystem: Ecosystem, paths: list[str]) -> list[Manifest]:
    manifests = (read_manifest(reader, ecosystem, path) for path in paths)
    return [manifest for manifest in manifests if manifest]


def load_project(directory: Path) -> Project:
    root = directory.resolve()
    reader = SourceReader(root)
    entries = frozenset(entry.name for entry in root.iterdir())
    files = project_files(root)
    makefile_path = next((name for name in MAKEFILE_NAMES if name in entries), None)
    makefile = load_makefile(reader, makefile_path) if makefile_path else None
    manifests = {
        ecosystem: read_manifests(reader, ecosystem, manifest_paths(ecosystem, entries, files))
        for ecosystem in MANIFEST_READERS
    }
    return Project(root, entries, files, makefile_path, makefile, manifests, reader)
