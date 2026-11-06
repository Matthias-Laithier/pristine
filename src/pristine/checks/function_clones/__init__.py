from collections import defaultdict
from pathlib import Path, PurePath

from pristine.checks.function_clones.blocks import repeated_blocks, text_blocks
from pristine.checks.function_clones.bodies import MINIMUM_STATEMENTS, FunctionBody, function_bodies
from pristine.checks.registry import PathCheck, register_path_check
from pristine.findings import Finding, Severity
from pristine.imports.repository import with_repository_files
from pristine.inspection import is_generated
from pristine.path_roles import is_test_path, is_vendored

RULE_ID = "CR-5"
PYTHON_SUFFIX = ".py"
MIGRATION_FOLDER_MARKER = "migration"
GENERATED_FOLDER_SUFFIX = "generated"
EXEMPT_FOLDER_NAMES = frozenset({"alembic", "template", "templates"})
EXTRACTION_ADVICE = "extract the shared behavior into one function or method that every caller uses"

type BlockKeys = dict[tuple[str, int], str]


def is_exempt_folder(name: str) -> bool:
    lowered = name.lower()
    is_marked = MIGRATION_FOLDER_MARKER in lowered or lowered.endswith(GENERATED_FOLDER_SUFFIX)
    return lowered in EXEMPT_FOLDER_NAMES or is_marked


def is_compared(path: str) -> bool:
    pure = PurePath(path)
    exempt = is_test_path(pure) or is_vendored(pure) or any(is_exempt_folder(name) for name in pure.parts[:-1])
    return pure.suffix == PYTHON_SUFFIX and not exempt


def read_source(path: str) -> str:
    try:
        text = Path(path).read_text(errors="replace")
    except OSError:
        return ""
    return "" if is_generated(text) else text


def repeated_block_keys(paths: list[str]) -> BlockKeys:
    blocks = [block for path in paths if is_compared(path) for block in text_blocks(path, read_source(path))]
    return {(block.path, block.line): block.key for block in repeated_blocks(blocks)}


def suspect_bodies(keys: BlockKeys) -> list[FunctionBody]:
    lines: dict[str, set[int]] = defaultdict(set)
    for path, line in keys:
        lines[path].add(line)
    return [body for path in sorted(lines) for body in function_bodies(path, read_source(path), lines[path])]


def clone_groups(paths: list[str]) -> list[list[FunctionBody]]:
    keys = repeated_block_keys(paths)
    groups: dict[tuple[str, str], list[FunctionBody]] = defaultdict(list)
    for body in suspect_bodies(keys):
        groups[keys[body.path, body.line], body.shape].append(body)
    return [sorted(group, key=lambda body: (body.path, body.line)) for group in groups.values() if len(group) > 1]


def location(body: FunctionBody) -> str:
    return f"{body.name} at {body.path}:{body.line}"


def clone_finding(group: list[FunctionBody], checked: set[str]) -> Finding | None:
    reported = next((body for body in group if body.path in checked), None)
    if reported is None:
        return None
    others = ", ".join(location(body) for body in group if body is not reported)
    message = f"function {reported.name} has the same body as {others}; {EXTRACTION_ADVICE}"
    return Finding(reported.path, reported.line, RULE_ID, Severity.WARNING, message)


def compared_paths(paths: list[str]) -> list[str]:
    return [path for path in with_repository_files(paths) if path.endswith(PYTHON_SUFFIX)]


def check_function_clones(paths: list[str]) -> list[Finding]:
    checked = set(paths)
    findings = (clone_finding(group, checked) for group in clone_groups(compared_paths(paths)))
    return [finding for finding in findings if finding is not None]


register_path_check(
    PathCheck(
        rule_id=RULE_ID,
        summary=(
            f"Python functions and methods whose bodies of at least {MINIMUM_STATEMENTS} statements are identical "
            "after parsing, identifiers included, across the repository. Test, generated, vendored, migration, and "
            "template files, overloads, abstract methods, and protocol stubs are exempt. Each group is reported once, "
            "on its first checked member."
        ),
        run=check_function_clones,
    )
)
