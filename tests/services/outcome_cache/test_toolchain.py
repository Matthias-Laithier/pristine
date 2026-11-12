from pathlib import Path

import pytest

from pristine.services.grammars import grammar_library_directory, parser_for
from pristine.services.outcome_cache import toolchain
from pristine.services.outcome_cache.toolchain import ToolchainUnavailable, fingerprint_of

RUNTIME = b"3.15.0 cpython-315 UTF-8 1"


def installed(root: Path) -> tuple[dict[str, Path], Path]:
    packages = {name: root / name for name in toolchain.PACKAGES}
    for directory in packages.values():
        (directory / "nested").mkdir(parents=True)
        (directory / "__init__.py").write_text("VERSION = 1\n")
        (directory / "nested" / "module.py").write_text("VALUE = 1\n")
    grammars = root / "grammars"
    grammars.mkdir()
    for language in ("python", "typescript", "tsx", "javascript", "rust"):
        (grammars / f"libtree_sitter_{language}.dylib").write_bytes(language.encode())
    return packages, grammars


@pytest.mark.parametrize(
    "changed",
    [
        "pristine/nested/module.py",
        "tree_sitter/__init__.py",
        "tree_sitter_language_pack/nested/module.py",
        "grammars/libtree_sitter_python.dylib",
        "grammars/libtree_sitter_tsx.dylib",
    ],
)
def test_editing_any_source_or_used_grammar_changes_the_fingerprint(tmp_path: Path, changed: str) -> None:
    packages, grammars = installed(tmp_path)
    before = fingerprint_of(packages, grammars, RUNTIME)
    (tmp_path / changed).write_bytes(b"edited")
    assert fingerprint_of(packages, grammars, RUNTIME) != before


@pytest.mark.parametrize("added", ["pristine/nested/new.py", "tree_sitter/native.so", "grammars/tree_sitter_python.so"])
def test_adding_a_source_or_grammar_file_changes_the_fingerprint(tmp_path: Path, added: str) -> None:
    packages, grammars = installed(tmp_path)
    before = fingerprint_of(packages, grammars, RUNTIME)
    (tmp_path / added).write_bytes(b"new")
    assert fingerprint_of(packages, grammars, RUNTIME) != before


def test_a_renamed_source_file_changes_the_fingerprint(tmp_path: Path) -> None:
    packages, grammars = installed(tmp_path)
    before = fingerprint_of(packages, grammars, RUNTIME)
    (tmp_path / "pristine/nested/module.py").rename(tmp_path / "pristine/nested/other.py")
    assert fingerprint_of(packages, grammars, RUNTIME) != before


def test_the_runtime_and_grammar_location_are_part_of_the_fingerprint(tmp_path: Path) -> None:
    packages, grammars = installed(tmp_path)
    before = fingerprint_of(packages, grammars, RUNTIME)
    moved = tmp_path / "other-grammars"
    grammars.rename(moved)
    assert fingerprint_of(packages, grammars, b"3.15.1 cpython-315 UTF-8 1") != before
    assert fingerprint_of(packages, moved, RUNTIME) != before


def test_bytecode_and_unused_grammars_leave_the_fingerprint_unchanged(tmp_path: Path) -> None:
    packages, grammars = installed(tmp_path)
    before = fingerprint_of(packages, grammars, RUNTIME)
    (tmp_path / "pristine/__pycache__").mkdir()
    (tmp_path / "pristine/__pycache__/module.cpython-315.pyc").write_bytes(b"bytecode")
    (grammars / "libtree_sitter_rust.dylib").write_bytes(b"edited")
    assert fingerprint_of(packages, grammars, RUNTIME) == before


def test_an_unreadable_source_makes_the_toolchain_unavailable(tmp_path: Path) -> None:
    packages, grammars = installed(tmp_path)
    (tmp_path / "pristine/broken.py").symlink_to(tmp_path / "missing.py")
    with pytest.raises(ToolchainUnavailable):
        fingerprint_of(packages, grammars, RUNTIME)


def test_the_installed_toolchain_covers_the_loaded_grammars() -> None:
    parser_for("python")
    libraries = {path.name.split(".", 1)[0] for path in toolchain.grammar_libraries(grammar_library_directory())}
    assert "libtree_sitter_python" in libraries or "tree_sitter_python" in libraries
