from collections import defaultdict
from pathlib import PurePosixPath

from pristine.files.classification import is_generated
from pristine.files.path_roles import is_test_path, is_vendored
from pristine.reports.findings import Finding, Severity

RULE_ID = "CR-15"
HEADER_BYTES = 8192
CODE_SUFFIXES = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte"}
    | {".go", ".rs", ".java", ".kt", ".scala", ".rb", ".php", ".swift", ".cs", ".c", ".cc", ".cpp", ".h", ".hpp"}
)
TYPE_DECLARATION_SUFFIX = ".d.ts"
STORY_MARKER = ".stories."
GENERATED_FOLDER_MARKERS = ("generated", "__generated__")
GENERATED_FOLDER_NAMES = frozenset({"gen", "codegen", "dist", "build", "out", "esm", "cjs"})
SAMPLE_FOLDER_NAMES = frozenset({"template", "templates", "example", "examples", "stories", "storybook", "docs", "doc"})
MIGRATION_FOLDER_MARKER = "migration"
MIGRATION_FOLDER_NAMES = frozenset({"alembic", "migrate"})
PLACED_FOLDER_NAMES = GENERATED_FOLDER_NAMES | MIGRATION_FOLDER_NAMES

type Directories = dict[PurePosixPath, list[PurePosixPath]]


def is_code(path: PurePosixPath) -> bool:
    is_companion = path.name.endswith(TYPE_DECLARATION_SUFFIX) or STORY_MARKER in path.name
    return path.suffix.lower() in CODE_SUFFIXES and not is_companion


def is_placed_folder(name: str) -> bool:
    lowered = name.lower()
    is_marked = lowered.endswith(GENERATED_FOLDER_MARKERS) or MIGRATION_FOLDER_MARKER in lowered
    return lowered in PLACED_FOLDER_NAMES or lowered.startswith(".") or is_marked


def is_counted_code(path: PurePosixPath) -> bool:
    exempt = is_test_path(path) or is_vendored(path) or any(is_placed_folder(name) for name in path.parts[:-1])
    return is_code(path) and not exempt


def is_grouped_code(path: PurePosixPath) -> bool:
    is_sample = not SAMPLE_FOLDER_NAMES.isdisjoint(name.lower() for name in path.parts[:-1])
    return is_counted_code(path) and not is_sample


def code_files_by_directory(paths: list[str]) -> Directories:
    directories: Directories = defaultdict(list)
    for path in map(PurePosixPath, paths):
        if is_counted_code(path):
            directories[path.parent].append(path)
    return directories


def grouped_directories(directories: Directories) -> Directories:
    grouped = {directory: [path for path in files if is_grouped_code(path)] for directory, files in directories.items()}
    return {directory: files for directory, files in grouped.items() if files}


def directory_finding(files: list[PurePosixPath], message: str, severity: Severity = Severity.WARNING) -> Finding:
    return Finding(str(min(files)), 1, RULE_ID, severity, message)


def read_header(path: PurePosixPath) -> str:
    try:
        with open(path, "rb") as source:
            return source.read(HEADER_BYTES).decode(errors="replace")
    except OSError:
        return ""


def holds_generated_code(files: list[PurePosixPath]) -> bool:
    return any(is_generated(read_header(path)) for path in files)
