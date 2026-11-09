import posixpath

from pristine.files.discovery import is_excluded
from pristine.project.repository.loading import Project
from pristine.project.strictness.annotations.options import has_option
from pristine.project.strictness.strictness import UnverifiedConfigError

PYTHON_SUFFIXES = (".py", ".pyi")
VALUE_OPTIONS = frozenset(
    {
        "--select",
        "--extend-select",
        "--ignore",
        "--extend-ignore",
        "--output-format",
        "--output-file",
        "-o",
        "--target-version",
        "--cache-dir",
        "--color",
        "--fixable",
        "--unfixable",
        "--extend-fixable",
        "--disable-error-code",
        "--enable-error-code",
        "--python-version",
        "--platform",
        "--python-executable",
        "--follow-imports",
        "--junit-xml",
        "--html-report",
        "--txt-report",
        "--linecount-report",
    }
)
SOURCE_OVERRIDES = frozenset({"-c", "--command", "-m", "--module", "-p", "--package", "--stdin-filename"})
SAFE_FLAGS = frozenset(
    {
        "--strict",
        "--isolated",
        "--no-cache",
        "-n",
        "--quiet",
        "-q",
        "--verbose",
        "-v",
        "--silent",
        "-s",
        "--preview",
        "--no-preview",
        "--no-fix",
        "--ignore-noqa",
        "--no-respect-gitignore",
        "--respect-gitignore",
        "--force-exclude",
        "--no-force-exclude",
        "--no-incremental",
        "--show-error-codes",
        "--pretty",
        "--no-pretty",
        "--show-column-numbers",
        "--show-error-context",
        "--show-traceback",
        "--disallow-untyped-defs",
        "--allow-untyped-defs",
        "--warn-unused-ignores",
        "--non-interactive",
    }
)


def target_paths(arguments: list[str]) -> list[str]:
    targets = []
    skip_value = False
    for argument in arguments:
        if skip_value:
            skip_value = False
            continue
        if not argument.startswith("-"):
            targets.append(argument)
            continue
        option, separator, _ = argument.partition("=")
        if option not in VALUE_OPTIONS and option not in SAFE_FLAGS:
            raise UnverifiedConfigError("Makefile", f"annotation source scope for {option} needs review")
        skip_value = option in VALUE_OPTIONS and not separator
    if skip_value:
        raise UnverifiedConfigError("Makefile", "annotation command ends with an option missing its value")
    return targets


def covers(target: str, source: str, project: Project) -> bool:
    absolute_root = str(project.root)
    target = target.removeprefix(absolute_root + "/") if target.startswith(absolute_root + "/") else target
    target = "." if target == absolute_root else posixpath.normpath(target)
    return target in {".", source} or source.startswith(target.rstrip("/") + "/")


def excluded_python_sources(sources: list[str], patterns: list[str]) -> bool:
    expanded = [candidate for pattern in patterns for candidate in (pattern, f"**/{pattern}")]
    return any(is_excluded(source, expanded) for source in sources)


def verify_source_scope(project: Project, arguments: list[str], *, ruff: bool) -> None:
    if "-" in arguments or has_option(arguments, SOURCE_OVERRIDES):
        raise UnverifiedConfigError(
            "Makefile", "annotation command checks stdin, inline code, or a module rather than repository paths"
        )
    sources = [path for path in project.files if path.endswith(PYTHON_SUFFIXES)]
    if not sources:
        return
    targets = target_paths(arguments[1:] if ruff else arguments)
    if ruff and not targets:
        targets = ["."]
    missing = [path for path in sources if not any(covers(target, path, project) for target in targets)]
    if missing:
        raise UnverifiedConfigError(
            "Makefile", "annotation command does not cover discovered Python source: " + ", ".join(missing)
        )
