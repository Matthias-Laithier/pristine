from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from pristine.project.commands.tool_arguments import (
    ArgumentsTest,
    all_of,
    any_arguments,
    any_of,
    audit_command,
    checking,
    denies_warnings,
    knip_dead_code,
    non_writing,
    option,
    pylint_dead_code,
    rust_dead_code,
    subcommand,
    without,
)


class Ecosystem(StrEnum):
    PYTHON = "Python"
    JAVASCRIPT = "JavaScript/TypeScript"
    GO = "Go"
    RUST = "Rust"


class Role(StrEnum):
    FORMATTER = "formatter"
    LINTER = "linter"
    TYPE_CHECKER = "type checker"
    DEAD_CODE = "dead-code checker"
    VULNERABILITY_AUDIT = "dependency vulnerability audit"


@dataclass(frozen=True)
class Tool:
    name: str
    ecosystem: Ecosystem
    checks: Mapping[Role, ArgumentsTest]
    config_files: tuple[str, ...] = ()
    packages: frozenset[str] = field(default_factory=frozenset)
    settings_keys: tuple[str, ...] = ()


def native_tool(name: str, ecosystem: Ecosystem, checks: Mapping[Role, ArgumentsTest], *config_files: str) -> Tool:
    return Tool(name, ecosystem, checks, config_files)


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
    python_tool("pylint", {Role.LINTER: any_arguments, Role.DEAD_CODE: pylint_dead_code}, (".pylintrc", "pylintrc")),
    python_tool("vulture", {Role.DEAD_CODE: checking}),
    python_tool("pip-audit", {Role.VULNERABILITY_AUDIT: all_of(checking, without("--dry-run", "-d"))}),
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
    javascript_tool("knip", {Role.DEAD_CODE: knip_dead_code}, "knip.*", ".knip.*"),
    *(
        native_tool(name, Ecosystem.JAVASCRIPT, {Role.VULNERABILITY_AUDIT: audit_command})
        for name in ("npm", "pnpm", "bun")
    ),
    native_tool("gofmt", Ecosystem.GO, {Role.FORMATTER: non_writing}, "go.mod"),
    native_tool("gofumpt", Ecosystem.GO, {Role.FORMATTER: non_writing}),
    native_tool(
        "go",
        Ecosystem.GO,
        {
            Role.LINTER: subcommand("vet"),
            Role.TYPE_CHECKER: subcommand("test", "build"),
            Role.DEAD_CODE: all_of(subcommand("test", "build"), option("./..."), checking),
        },
        "go.mod",
    ),
    native_tool("golangci-lint", Ecosystem.GO, {Role.LINTER: any_arguments}, ".golangci.yml", ".golangci.yaml"),
    native_tool("staticcheck", Ecosystem.GO, {Role.LINTER: any_arguments}, "staticcheck.conf"),
    native_tool("govulncheck", Ecosystem.GO, {Role.VULNERABILITY_AUDIT: all_of(checking, without("-mode", "--mode"))}),
    native_tool(
        "cargo",
        Ecosystem.RUST,
        {
            Role.FORMATTER: all_of(subcommand("fmt"), option("--check")),
            Role.LINTER: all_of(subcommand("clippy"), denies_warnings),
            Role.TYPE_CHECKER: subcommand("check", "test", "build"),
            Role.DEAD_CODE: rust_dead_code,
            Role.VULNERABILITY_AUDIT: audit_command,
        },
        "Cargo.toml",
    ),
)
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
