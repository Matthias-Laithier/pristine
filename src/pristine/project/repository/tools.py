from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from pristine.project.commands.shell import positionals

type ArgumentsTest = Callable[[list[str]], bool]


class Ecosystem(StrEnum):
    PYTHON = "Python"
    JAVASCRIPT = "JavaScript/TypeScript"


class Role(StrEnum):
    FORMATTER = "formatter"
    LINTER = "linter"
    TYPE_CHECKER = "type checker"


@dataclass(frozen=True)
class Tool:
    name: str
    ecosystem: Ecosystem
    checks: Mapping[Role, ArgumentsTest]
    config_files: tuple[str, ...] = ()
    packages: frozenset[str] = field(default_factory=frozenset)
    settings_keys: tuple[str, ...] = ()


def any_arguments(_: list[str]) -> bool:
    return True


def subcommand(*names: str) -> ArgumentsTest:
    return lambda arguments: next(iter(positionals(arguments)), None) in names


def option(*names: str) -> ArgumentsTest:
    return lambda arguments: any(argument in names for argument in arguments)


def without(*names: str) -> ArgumentsTest:
    return lambda arguments: not option(*names)(arguments)


def all_of(*tests: ArgumentsTest) -> ArgumentsTest:
    return lambda arguments: all(test(arguments) for test in tests)


def any_of(*tests: ArgumentsTest) -> ArgumentsTest:
    return lambda arguments: any(test(arguments) for test in tests)


def python_tool(name: str, checks: Mapping[Role, ArgumentsTest], config_files: tuple[str, ...] = ()) -> Tool:
    return Tool(name, Ecosystem.PYTHON, checks, config_files, frozenset({name}), (name,))


def javascript_tool(name: str, checks: Mapping[Role, ArgumentsTest], *config_files: str, package: str = "") -> Tool:
    return Tool(name, Ecosystem.JAVASCRIPT, checks, config_files, frozenset({package or name}))


TOOLS = (
    python_tool(
        "ruff",
        {Role.FORMATTER: all_of(subcommand("format"), option("--check")), Role.LINTER: subcommand("check")},
        ("ruff.toml", ".ruff.toml"),
    ),
    python_tool("black", {Role.FORMATTER: option("--check")}),
    python_tool("flake8", {Role.LINTER: any_arguments}, (".flake8",)),
    python_tool("pylint", {Role.LINTER: any_arguments}, (".pylintrc", "pylintrc")),
    python_tool("mypy", {Role.TYPE_CHECKER: any_arguments}, ("mypy.ini", ".mypy.ini")),
    python_tool("pyright", {Role.TYPE_CHECKER: any_arguments}, ("pyrightconfig.json",)),
    python_tool("basedpyright", {Role.TYPE_CHECKER: any_arguments}, ("pyrightconfig.json",)),
    python_tool("ty", {Role.TYPE_CHECKER: subcommand("check")}, ("ty.toml",)),
    python_tool("pyrefly", {Role.TYPE_CHECKER: subcommand("check")}, ("pyrefly.toml",)),
    Tool(
        "prettier",
        Ecosystem.JAVASCRIPT,
        {Role.FORMATTER: option("--check", "-c", "--list-different", "-l")},
        (".prettierrc*", "prettier.config.*"),
        frozenset({"prettier"}),
        ("prettier",),
    ),
    javascript_tool(
        "biome",
        {
            Role.FORMATTER: any_of(
                subcommand("check", "ci"), all_of(subcommand("format"), without("--write", "--fix"))
            ),
            Role.LINTER: subcommand("lint", "check", "ci"),
        },
        "biome.json",
        "biome.jsonc",
        package="@biomejs/biome",
    ),
    javascript_tool("dprint", {Role.FORMATTER: subcommand("check")}, "dprint.json*", ".dprint.json*"),
    javascript_tool("oxfmt", {Role.FORMATTER: option("--check")}, ".oxfmtrc*", "oxfmt.config.*"),
    Tool(
        "eslint",
        Ecosystem.JAVASCRIPT,
        {Role.LINTER: any_arguments},
        ("eslint.config.*", ".eslintrc*"),
        frozenset({"eslint"}),
        ("eslintConfig",),
    ),
    javascript_tool("oxlint", {Role.LINTER: any_arguments}, ".oxlintrc*", "oxlint.config.*"),
    Tool("tsc", Ecosystem.JAVASCRIPT, {Role.TYPE_CHECKER: any_arguments}, packages=frozenset({"typescript"})),
    javascript_tool("vue-tsc", {Role.TYPE_CHECKER: any_arguments}),
    javascript_tool("tsgo", {Role.TYPE_CHECKER: any_arguments}, package="@typescript/native-preview"),
)
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
