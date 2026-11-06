import re
from pathlib import PurePath

VENDORED_DIRECTORIES = frozenset(
    {"node_modules", "bower_components", "vendor", "third_party", ".venv", "venv", "site-packages"}
)
CACHE_DIRECTORIES = frozenset({"__pycache__"})
TEST_FILE_NAME = re.compile(r"test_.+\.py|.+_test\.(py|go|rb|[cm]?[jt]sx?)|.+\.(test|spec)\.[cm]?[jt]sx?|.+_spec\.rb")
TEST_FOLDER = re.compile(r"(.+[-_.])?(tests?|e2e)|testing|specs?|__tests__")
JEST_TEST_FOLDER = "__tests__"
TEST_SUPPORT_FOLDERS = frozenset({"__mocks__", "testdata", "fixtures", "__fixtures__", "__snapshots__"})
PYTEST_CONFTEST = "conftest.py"


def is_vendored(path: PurePath) -> bool:
    return not VENDORED_DIRECTORIES.isdisjoint(path.parts[:-1])


def is_cache(path: PurePath) -> bool:
    return not CACHE_DIRECTORIES.isdisjoint(path.parts[:-1])


def is_test_folder(name: str) -> bool:
    return TEST_FOLDER.fullmatch(name.lower()) is not None


def holds_test_material(name: str) -> bool:
    return is_test_folder(name) or name.lower() in TEST_SUPPORT_FOLDERS


def is_test_file(path: PurePath) -> bool:
    return TEST_FILE_NAME.fullmatch(path.name) is not None or JEST_TEST_FOLDER in path.parts[:-1]


def is_test_path(path: PurePath) -> bool:
    in_test_material = any(holds_test_material(name) for name in path.parts[:-1])
    return in_test_material or is_test_file(path) or path.name == PYTEST_CONFTEST
