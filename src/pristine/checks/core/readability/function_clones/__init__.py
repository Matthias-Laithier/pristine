from collections import defaultdict
from pathlib import Path, PurePath

from pristine.checks.core.readability.function_clones.blocks import repeated_blocks, text_blocks
from pristine.checks.core.readability.function_clones.bodies import MINIMUM_STATEMENTS, FunctionBody, function_bodies
from pristine.checks.core.readability.function_clones.scripts import SCRIPT_SUFFIXES, ScriptBody, script_groups
from pristine.checks.definitions import PathCheck
from pristine.files.classification import is_generated
from pristine.files.path_roles import is_test_path, is_vendored
from pristine.imports.repository import with_repository_files
from pristine.reports.findings import Finding, Severity

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
    return pure.suffix in {PYTHON_SUFFIX, *SCRIPT_SUFFIXES} and not exempt


def read_source(path: str) -> str:
    try:
        text = Path(path).read_text(errors="replace")
    except OSError:
        return ""
    return "" if is_generated(text) else text


def repeated_block_keys(paths: list[str]) -> BlockKeys:
    blocks = [
        block
        for path in paths
        if path.endswith(PYTHON_SUFFIX) and is_compared(path)
        for block in text_blocks(path, read_source(path))
    ]
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


def location(body: FunctionBody | ScriptBody) -> str:
    return f"{body.name} at {body.path}:{body.line}"


def clone_finding(group: list[FunctionBody] | list[ScriptBody], checked: set[str]) -> Finding | None:
    reported = next((body for body in group if body.path in checked), None)
    if reported is None:
        return None
    others = ", ".join(location(body) for body in group if body is not reported)
    message = f"function {reported.name} has the same body as {others}; {EXTRACTION_ADVICE}"
    return Finding(reported.path, reported.line, RULE_ID, Severity.WARNING, message)


def compared_paths(paths: list[str]) -> list[str]:
    return [path for path in with_repository_files(paths) if is_compared(path)]


def check_function_clones(paths: list[str]) -> list[Finding]:
    checked = set(paths)
    compared = compared_paths(paths)
    scripts = [path for path in compared if PurePath(path).suffix in SCRIPT_SUFFIXES and read_source(path)]
    groups, failures = script_groups(scripts)
    findings = (clone_finding(group, checked) for group in [*clone_groups(compared), *groups])
    return [finding for finding in findings if finding is not None] + failures


CHECK = PathCheck(
    rule_id=RULE_ID,
    title="Identical Function Bodies",
    summary=(
        f"Python functions and methods whose bodies of at least {MINIMUM_STATEMENTS} statements are identical "
        "after parsing, identifiers included, across the repository. Test, generated, vendored, migration, and "
        "template files, overloads, abstract methods, and protocol stubs are exempt. Each group is reported once, "
        "on its first checked member. JS/TS functions, methods, and block-bodied arrows use exact syntax trees, "
        "including identifiers and literal spelling, with comments and optional semicolons ignored, at the same threshold."
    ),
    run=check_function_clones,
)
