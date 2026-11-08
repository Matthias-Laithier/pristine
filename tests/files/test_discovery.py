from pathlib import Path

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
