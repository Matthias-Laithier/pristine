import os
from pathlib import PurePosixPath

from pristine.checks.definitions import PathCheck
from pristine.files.path_roles import PYTEST_CONFTEST, is_test_file, is_test_folder
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import LANGUAGE_BY_SUFFIX

RULE_ID = "TST-4"
SOURCE_FOLDER = "src"
SOURCE_SIBLING_TEST_FOLDERS = frozenset({"test", "tests"})
HIDDEN_PREFIX = "."
SCRIPTS_FOLDER = "scripts"
PYTEST_ROOT_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", "tox.ini", ".git")
MOVE_HINT = "move it into the component's tests/ folder, mirroring the source layout"


def is_tooling_folder(name: str) -> bool:
    return name.startswith(HIDDEN_PREFIX) or name.lower() == SCRIPTS_FOLDER


def outermost_test_folder(folders: tuple[str, ...]) -> int | None:
    return next((index for index, name in enumerate(folders) if is_test_folder(name)), None)


def sits_in_source_tree(folders: tuple[str, ...], test_folder: int) -> bool:
    enclosing = [name.lower() for name in folders[:test_folder]]
    if SOURCE_FOLDER not in enclosing:
        return False
    is_source_sibling = enclosing[-1] == SOURCE_FOLDER and folders[test_folder].lower() in SOURCE_SIBLING_TEST_FOLDERS
    return not is_source_sibling


def is_pytest_root(path: PurePosixPath) -> bool:
    return any(os.path.exists(path.parent / marker) for marker in PYTEST_ROOT_MARKERS)


def placement_finding(path: str, severity: Severity, problem: str) -> Finding:
    return Finding(path, 1, RULE_ID, severity, f"{problem}; {MOVE_HINT}")


def test_file_finding(path: str, folders: tuple[str, ...]) -> Finding | None:
    test_folder = outermost_test_folder(folders)
    if test_folder is None:
        return placement_finding(path, Severity.ERROR, "test file sits beside source, outside any tests/ folder")
    if sits_in_source_tree(folders, test_folder):
        return placement_finding(path, Severity.WARNING, f"test folder '{folders[test_folder]}' sits inside src/")
    return None


def conftest_finding(path: str, folders: tuple[str, ...]) -> Finding | None:
    if outermost_test_folder(folders) is not None or is_pytest_root(PurePosixPath(path)):
        return None
    return placement_finding(path, Severity.WARNING, "conftest.py sits outside tests/ and is no pytest root conftest")


def location_finding(path: str) -> Finding | None:
    file_path = PurePosixPath(path)
    if file_path.suffix.lower() not in LANGUAGE_BY_SUFFIX:
        return None
    folders = file_path.parts[:-1]
    if any(is_tooling_folder(name) for name in folders):
        return None
    if file_path.name == PYTEST_CONFTEST:
        return conftest_finding(path, folders)
    if is_test_file(file_path):
        return test_file_finding(path, folders)
    return None


def check_test_location(paths: list[str]) -> list[Finding]:
    return [finding for path in paths if (finding := location_finding(path)) is not None]


CHECK = PathCheck(
    rule_id=RULE_ID,
    title="Tests Live in a Dedicated tests Folder",
    summary="Python, JavaScript/JSX and TypeScript/TSX test files outside a dedicated test folder such as tests/, test/, or spec/.",
    run=check_test_location,
)
