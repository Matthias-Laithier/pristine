from collections.abc import Callable, Mapping

from pristine.project.commands.shell import positionals

type ArgumentsTest = Callable[[list[str]], bool]
KNIP_DEAD_TYPES = frozenset({"files", "exports", "types", "enumMembers", "namespaceMembers", "nsExports", "nsTypes"})
KNIP_DEFAULT_DEAD_TYPES = KNIP_DEAD_TYPES - {"nsExports", "nsTypes"}


def any_arguments(_: list[str]) -> bool:
    return True


def non_writing(arguments: list[str]) -> bool:
    return bool(arguments) and arguments[0] in {"-l", "-d"}


def subcommand(*names: str) -> ArgumentsTest:
    return lambda arguments: next(iter(positionals(arguments)), None) in names


def option(*names: str) -> ArgumentsTest:
    return lambda arguments: any(argument.partition("=")[0] in names for argument in arguments)


def without(*names: str) -> ArgumentsTest:
    return lambda arguments: not option(*names)(arguments)


def all_of(*tests: ArgumentsTest) -> ArgumentsTest:
    return lambda arguments: all(test(arguments) for test in tests)


def any_of(*tests: ArgumentsTest) -> ArgumentsTest:
    return lambda arguments: any(test(arguments) for test in tests)


def denies_warnings(arguments: list[str]) -> bool:
    return any(
        argument in {"-Dwarnings", "--deny=warnings"}
        or (argument in {"-D", "--deny"} and arguments[index + 1 : index + 2] == ["warnings"])
        for index, argument in enumerate(arguments)
    )


def option_values(arguments: list[str], *names: str) -> list[str]:
    return [
        value if separator else next(iter(arguments[index + 1 : index + 2]), "")
        for index, argument in enumerate(arguments)
        for name, separator, value in [argument.partition("=")]
        if name in names
    ]


def checking(arguments: list[str]) -> bool:
    return without("--help", "-help", "-h", "--version", "-V", "--fix", "--write", "--exit-zero")(arguments)


def knip_dead_code(arguments: list[str]) -> bool:
    return (
        checking(arguments)
        and (without("--dependencies", "--cycles")(arguments) or option("--files", "--exports")(arguments))
        and without("--no-exit-code", "--max-issues")(arguments)
        and bool(knip_issue_types(arguments, {}) & KNIP_DEAD_TYPES)
    )


def knip_issue_types(arguments: list[str], config: Mapping[str, object]) -> set[str]:
    included = option_values(arguments, "--include") or config.get("include")
    excluded = option_values(arguments, "--exclude") or config.get("exclude")
    enabled: set[str] = (
        set(",".join(value for value in included if isinstance(value, str)).split(","))
        if isinstance(included, list) and included
        else set(KNIP_DEFAULT_DEAD_TYPES)
    )
    if enabled <= {"nsExports", "nsTypes"}:
        enabled |= set(KNIP_DEFAULT_DEAD_TYPES)
    if option("--files", "--exports")(arguments):
        enabled = ({"files"} if option("--files")(arguments) else set[str]()) | (
            set(KNIP_DEAD_TYPES) - {"files"} if option("--exports")(arguments) else set[str]()
        )
    if isinstance(excluded, list):
        enabled -= set(",".join(value for value in excluded if isinstance(value, str)).split(","))
    return enabled


def pylint_dead_code(arguments: list[str]) -> bool:
    enabled = set(",".join(option_values(arguments, "--enable")).split(","))
    return (
        checking(arguments)
        and "unreachable" in enabled
        and without("--disable", "--errors-only", "-E", "--fail-under")(arguments)
    )


def audit_command(arguments: list[str]) -> bool:
    return (
        checking(arguments)
        and subcommand("audit")(arguments)
        and without("--offline")(arguments)
        and not ({"fix", "signatures"} & set(positionals(arguments)))
    )


def rust_dead_code(arguments: list[str]) -> bool:
    return (
        subcommand("clippy", "check", "test", "build")(arguments)
        and denies_warnings(arguments)
        and checking(arguments)
        and not any(argument.startswith(("-A", "--allow", "--cap-lints")) for argument in arguments)
    )


def source_arguments(arguments: list[str], value_options: frozenset[str]) -> list[str]:
    targets = []
    pending = iter(arguments)
    for argument in pending:
        if argument in value_options:
            next(pending, None)
        elif not argument.startswith("-"):
            targets.append(argument)
    return targets
