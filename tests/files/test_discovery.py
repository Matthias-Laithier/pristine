from tests.conftest import RunPristine


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
