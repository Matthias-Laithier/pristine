from pathlib import Path

import pytest

from tests.report_types import JsonReport
from tests.services.outcome_cache.conftest import Scan, write

SETTINGS_READ = 'import os\n\n\ndef main():\n    return os.environ["API_KEY"]\n'
SCRIPTS_MANIFEST = '[project.scripts]\ntool = "pkg.cli:main"\n'
PACKAGE_MAIN = "from .cli import main\n\nmain()\n"
SAFE_1 = "SAFE-1"


def check_ids(report: JsonReport) -> list[str]:
    return [finding["check_id"] for finding in report["findings"]]


def test_unchanged_files_are_not_inspected_again(tmp_path: Path, scan: Scan) -> None:
    write(tmp_path, {"pkg/cli.py": SETTINGS_READ, "notes.md": "notes\n"})
    first, first_inspected = scan()
    second, second_inspected = scan()
    assert first_inspected == ["notes.md", "pkg/cli.py"]
    assert second_inspected == []
    assert second == first


def test_an_edited_file_is_inspected_again(tmp_path: Path, scan: Scan) -> None:
    write(tmp_path, {"pkg/cli.py": SETTINGS_READ, "pkg/other.py": "VALUE = 1\n"})
    scan()
    (tmp_path / "pkg/cli.py").write_text("VALUE = 2\n")
    report, inspected = scan()
    assert inspected == ["pkg/cli.py"]
    assert check_ids(report) == []


@pytest.mark.parametrize(
    ("manifest", "content"),
    [("pyproject.toml", SCRIPTS_MANIFEST), ("pkg/pyproject.toml", SCRIPTS_MANIFEST.replace("pkg.cli", "cli"))],
    ids=["ancestor", "same-directory"],
)
def test_a_manifest_naming_the_module_as_script_is_read_again(
    tmp_path: Path, scan: Scan, manifest: str, content: str
) -> None:
    write(tmp_path, {"pkg/cli.py": SETTINGS_READ})
    assert check_ids(scan()[0]) == [SAFE_1]
    write(tmp_path, {manifest: content})
    report, inspected = scan()
    assert "pkg/cli.py" in inspected
    assert check_ids(report) == []


def test_removing_a_manifest_reinstates_the_finding(tmp_path: Path, scan: Scan) -> None:
    write(tmp_path, {"pkg/cli.py": SETTINGS_READ, "pyproject.toml": SCRIPTS_MANIFEST})
    assert check_ids(scan()[0]) == []
    (tmp_path / "pyproject.toml").unlink()
    assert check_ids(scan()[0]) == [SAFE_1]


def test_a_package_main_importing_the_module_is_read_again(tmp_path: Path, scan: Scan) -> None:
    write(tmp_path, {"pkg/cli.py": SETTINGS_READ})
    assert check_ids(scan()[0]) == [SAFE_1]
    write(tmp_path, {"pkg/__main__.py": PACKAGE_MAIN})
    report, inspected = scan()
    assert "pkg/cli.py" in inspected
    assert check_ids(report) == []


def test_a_renamed_file_is_inspected_under_its_new_path(tmp_path: Path, scan: Scan) -> None:
    write(tmp_path, {"pkg/cli.py": SETTINGS_READ})
    scan()
    (tmp_path / "pkg/cli.py").rename(tmp_path / "pkg/run.py")
    report, inspected = scan()
    assert inspected == ["pkg/run.py"]
    assert [finding["path"] for finding in report["findings"]] == ["pkg/run.py"]


def test_the_same_file_seen_from_another_directory_is_inspected_again(
    tmp_path: Path, scan: Scan, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path, {"pkg/cli.py": SETTINGS_READ})
    scan()
    monkeypatch.chdir(tmp_path / "pkg")
    _, inspected = scan()
    assert inspected == ["cli.py"]
