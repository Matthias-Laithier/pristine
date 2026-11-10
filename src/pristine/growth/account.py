from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePath

from pristine.files.classification import LOCKFILE_NAMES, is_generated, skip_reason
from pristine.files.path_roles import is_test_path
from pristine.services import git

__all__ = ["Growth", "GrowthError", "growth_since"]


class Kind(StrEnum):
    CODE = "code"
    TESTS = "tests"
    OTHER = "other"
    GENERATED = "generated"


@dataclass(frozen=True)
class Growth:
    base: str
    added: dict[Kind, int]
    removed: dict[Kind, int]
    files_added: int
    files_removed: int


class GrowthError(Exception):
    pass


def kind_of(root: Path, name: str) -> Kind:
    path = root / name
    content = path.read_bytes() if path.is_file() else b""
    if PurePath(name).name in LOCKFILE_NAMES or is_generated(content.decode(errors="replace")):
        return Kind.GENERATED
    if skip_reason(path, content) is not None:
        return Kind.OTHER
    return Kind.TESTS if is_test_path(PurePath(name)) else Kind.CODE


def resolved_base(root: Path, base: str | None) -> str:
    if base is not None:
        return base
    branch = git.default_branch(root)
    merge_base = None if branch is None else git.git_output(root, "merge-base", "HEAD", branch)
    return "HEAD" if merge_base is None else merge_base.strip()


def untracked_lines(root: Path) -> list[tuple[str, int, int]]:
    names = git.untracked_files(root) or []
    files = [(name, root / name) for name in names if (root / name).is_file()]
    return [(name, len(path.read_bytes().splitlines()), 0) for name, path in files]


def growth_since(directory: Path, base: str | None) -> Growth:
    root = git.repository_root(directory.resolve())
    if root is None:
        raise GrowthError(f"not inside a git repository: {directory}")
    chosen = resolved_base(root, base)
    changes = git.line_changes(root, chosen)
    if changes is None:
        raise GrowthError(f"git cannot diff against '{chosen}'")
    untracked = untracked_lines(root)
    changes += untracked
    added = dict.fromkeys(Kind, 0)
    removed = dict.fromkeys(Kind, 0)
    for name, plus, minus in changes:
        kind = kind_of(root, name)
        added[kind] += plus
        removed[kind] += minus
    files_added = len(git.changed_names(root, chosen, "A")) + len(untracked)
    files_removed = len(git.changed_names(root, chosen, "D"))
    return Growth(chosen, added, removed, files_added, files_removed)
