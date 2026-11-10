import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pristine.files.discovery import discover_files
from tests.conftest import RunPristine, run_git


def test_excluded_directories_are_left_out(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"vendor/library.py": "# vendored\n", "app.py": "value = 1\n"}, "--exclude", "vendor")
    assert report["summary"]["checked_files"] == 1
    assert report["findings"] == []


def test_vendored_directories_are_left_out(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"node_modules/lib/index.js": "// vendored\n", "app.py": "value = 1\n"})
    assert report["summary"]["checked_files"] == 1
    assert report["findings"] == []


def test_cache_directories_are_left_out(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"__pycache__/app.cpython-313.pyc": "compiled\n", "app.py": "value = 1\n"})
    assert report["skipped"] == []
    assert report["summary"]["checked_files"] == 1


def test_git_listed_files_keep_tracked_and_untracked_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_git(tmp_path, "init", "--quiet")
    monkeypatch.chdir(tmp_path)
    Path("tracked.py").write_text("tracked = 1\n")
    Path("untracked.py").write_text("untracked = 1\n")
    Path("ignored.py").write_text("ignored = 1\n")
    Path("node_modules/vendored.py").parent.mkdir(parents=True)
    Path("node_modules/vendored.py").write_text("vendored = 1\n")
    run_git(tmp_path, "add", "tracked.py")
    Path(".gitignore").write_text("ignored.py\n")
    assert discover_files([Path(".")], []) == [".gitignore", "tracked.py", "untracked.py"]


def test_walked_files_leave_out_vendored_and_cache_directories_without_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "no-git"))
    Path("app.py").write_text("value = 1\n")
    Path("node_modules/vendored.py").parent.mkdir(parents=True)
    Path("node_modules/vendored.py").write_text("vendored = 1\n")
    Path("vendor/vendored.py").parent.mkdir(parents=True)
    Path("vendor/vendored.py").write_text("vendored = 1\n")
    Path("__pycache__/compiled.py").parent.mkdir(parents=True)
    Path("__pycache__/compiled.py").write_text("compiled = 1\n")
    assert discover_files([Path(".")], []) == ["app.py"]


def test_explicit_duplicate_inputs_are_deduplicated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path("app.py").write_text("value = 1\n")
    assert discover_files([Path("app.py"), Path("app.py")], []) == ["app.py"]


def test_fallback_filters_descendants_but_not_explicit_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "no-git"))
    for name in (
        "src/app.py",
        "src/.hidden/ignored.py",
        "src/.hidden-file",
        "src/vendor/ignored.py",
        "src/__pycache__/ignored.py",
        "files/vendor",
        "files/node_modules",
        "files/__pycache__",
    ):
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content")

    assert discover_files([Path(".")], []) == ["files/__pycache__", "files/node_modules", "files/vendor", "src/app.py"]
    assert discover_files([Path("src/.hidden"), Path("src/vendor"), Path("src/__pycache__")], []) == [
        "src/.hidden/ignored.py",
        "src/__pycache__/ignored.py",
        "src/vendor/ignored.py",
    ]
    assert discover_files([Path("src/.hidden-file"), Path("src/vendor/ignored.py")], []) == [
        "src/.hidden-file",
        "src/vendor/ignored.py",
    ]


def test_fallback_symlink_files_and_explicit_directory_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "no-git"))
    Path("project").mkdir()
    Path("outside").mkdir()
    Path("outside/target.py").write_text("content")
    Path("outside/other.py").write_text("content")
    Path(".hidden.py").write_text("content")
    Path("project/file-link").symlink_to(Path("../outside/target.py"))
    Path("project/hidden-link").symlink_to(Path("../.hidden.py"))
    Path("project/broken-link").symlink_to(Path("../missing"))
    Path("project/directory-link").symlink_to(Path("../outside"), target_is_directory=True)

    assert discover_files([Path("project")], []) == [".hidden.py", "outside/target.py"]
    assert discover_files([Path("project/file-link")], []) == ["outside/target.py"]
    assert discover_files([Path("project/directory-link")], []) == ["outside/other.py", "outside/target.py"]
    assert discover_files([Path("project/broken-link")], []) == []


def test_fallback_does_not_scan_hidden_vendored_or_cache_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "no-git"))
    for name in ("src/app.py", "src/.hidden/ignored.py", "src/vendor/ignored.py", "src/__pycache__/ignored.py"):
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content")

    with patch("os.scandir", wraps=os.scandir) as scandir, patch("os.listdir", wraps=os.listdir) as listdir:
        assert discover_files([Path(".")], []) == ["src/app.py"]

    scanned = {
        Path(os.fsdecode((call.args[0] if call.args else call.kwargs.get("path")) or ".")).resolve()
        for call in scandir.call_args_list + listdir.call_args_list
    }
    excluded = [Path("src/.hidden").resolve(), Path("src/vendor").resolve(), Path("src/__pycache__").resolve()]
    assert scanned
    assert not any(path.is_relative_to(directory) for path in scanned for directory in excluded)
