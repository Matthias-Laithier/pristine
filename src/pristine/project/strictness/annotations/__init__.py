from pristine.project.automation import CHECK_ID, fast_gate
from pristine.project.commands.shell import program_calls, words_of
from pristine.project.repository.loading import Project
from pristine.project.repository.tools import Ecosystem
from pristine.project.strictness.annotations.mypy import mypy_annotations
from pristine.project.strictness.annotations.ruff import ruff_annotations
from pristine.project.strictness.strictness import UnverifiedConfigError
from pristine.reports.findings import Finding, FindingKind, Severity

PROBES = {"mypy": mypy_annotations, "ruff": ruff_annotations}
NAMES = frozenset(PROBES)
FIX = "run strict mypy or Ruff with ANN001/002/003/201/202/204/205/206 in make check, without annotation suppressions"
FIRST_LINE = 1
UNSUPPORTED_SHELL_WORDS = frozenset({"|", "||", ";", "&", "cd"})
UNSUPPORTED_MAKE_TARGETS = frozenset({".IGNORE", ".ONESHELL"})


def verify_shell_context(command: str) -> None:
    words = words_of(command)
    if command.lstrip().startswith("-") or UNSUPPORTED_SHELL_WORDS.intersection(words):
        raise UnverifiedConfigError("Makefile", "annotation command shell context may bypass enforcement")
    if any("$" in word or "=" in word and not word.startswith("--") for word in words):
        raise UnverifiedConfigError("Makefile", "annotation command uses dynamic values or environment overrides")
    if any(word.partition("=")[0] in {"--directory", "-C"} for word in words):
        raise UnverifiedConfigError("Makefile", "annotation command changes its working directory")


def python_annotations(project: Project) -> list[Finding]:
    manifest = project.root_manifest(Ecosystem.PYTHON)
    gate = fast_gate(project)
    if manifest is None or gate is None:
        return []
    shortfalls = []
    unverifiable = []
    commands = [
        command for command in gate.commands if list(eligible_calls(command)) or NAMES.intersection(words_of(command))
    ]
    for command in commands:
        try:
            shortfall = command_shortfall(project, command)
        except UnverifiedConfigError as error:
            unverifiable.append(error)
            continue
        if shortfall is None:
            return []
        shortfalls.append(shortfall)
    if unverifiable:
        return [verification_finding(project, unverifiable[0])]
    detail = "; ".join(dict.fromkeys(shortfalls)) or "no annotation-enforcing invocation"
    message = f"make check does not enforce explicit Python annotations: {detail}; {FIX}"
    return [Finding(project.shown(gate.rule.path), gate.rule.line, CHECK_ID, Severity.ERROR, message)]


def eligible_calls(command: str) -> list[tuple[str, list[str]]]:
    return [
        (name, arguments)
        for name, arguments in program_calls(command, NAMES)
        if name != "ruff" or arguments[:1] == ["check"]
    ]


def command_shortfall(project: Project, command: str) -> str | None:
    verify_shell_context(command)
    verify_ignored_recipe(project, command)
    shortfalls = [PROBES[name](project, arguments) for name, arguments in eligible_calls(command)]
    return (
        None
        if None in shortfalls
        else "; ".join(shortfall for shortfall in shortfalls if shortfall is not None)
        or "no annotation-enforcing invocation"
    )


def verification_finding(project: Project, error: UnverifiedConfigError) -> Finding:
    message = f"cannot verify that make check enforces explicit Python annotations: {error.reason}; {FIX}"
    return Finding(project.shown(error.path), FIRST_LINE, CHECK_ID, Severity.WARNING, message, FindingKind.VERIFICATION)


def verify_ignored_recipe(project: Project, command: str) -> None:
    makefile = project.makefile
    if makefile is not None and (
        UNSUPPORTED_MAKE_TARGETS.intersection(makefile.special_targets) or "SHELL" in makefile.variables
    ):
        raise UnverifiedConfigError(makefile.path, "Makefile shell or error-handling directives need review")
    ignored = (
        []
        if makefile is None
        else [makefile.expand(recipe) for rule in makefile.rules.values() for recipe in rule.ignored_error_commands]
    )
    if command in ignored:
        raise UnverifiedConfigError("Makefile", "annotation recipe ignores errors with the '-' prefix")


__all__ = ("python_annotations",)
