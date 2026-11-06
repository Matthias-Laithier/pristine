import pytest

from tests.project.conftest import RunProject, rule_findings

GO_MOD = "module example.com/app\n\ngo 1.24\n"
GO_MAKEFILE = (
    'dev:\n\tgo run ./cmd/app\ncheck:\n\ttest -z "$$(gofmt -l .)"\n\tgo vet ./...\n\tgo test ./...\ncheck-all: check\n'
)
GO_FORMAT_RECIPE = 'test -z "$$(gofmt -l .)"'
GO_WITHOUT_TOOLS_MAKEFILE = "dev:\n\tgo run .\ncheck:\n\tgo run .\ncheck-all: check\n"
GOFMT_NOT_RUN = (
    "error",
    (
        "make check does not run the formatter in check mode, verifying formatting without rewriting files "
        "(configured: gofmt)"
    ),
    3,
)
CARGO_TOML = '[package]\nname = "app"\nrust-version = "1.84"\n'
RUST_MAKEFILE = (
    "dev:\n\tcargo run\n"
    "check:\n\tcargo fmt -- --check\n\tcargo clippy -- -D warnings\n\tcargo check\n"
    "check-all: check\n"
)


def test_go_gate_uses_native_tools(run_project: RunProject) -> None:
    exit_code, report = run_project({"go.mod": GO_MOD, "Makefile": GO_MAKEFILE})
    assert (exit_code, report["findings"]) == (0, [])


def test_go_formatter_guard_is_required(run_project: RunProject) -> None:
    files = {"go.mod": GO_MOD, "Makefile": GO_MAKEFILE.replace('test -z "$$(gofmt -l .)"\n', "gofmt -l .\n")}
    _, report = run_project(files)
    assert [message for _, message, _ in rule_findings(report, "TL-3")] == [
        (
            "make check does not run the formatter in check mode, verifying formatting without rewriting files "
            "(configured: gofmt)"
        )
    ]


@pytest.mark.parametrize(
    ("recipe", "finding"),
    [
        ("gofmt -l .", GOFMT_NOT_RUN),
        ("gofmt -w .", GOFMT_NOT_RUN),
        ('test -z "$$(gofumpt -w .)"', GOFMT_NOT_RUN),
        ('test -z "$$(gofumpt -d .)"', None),
    ],
)
def test_go_formatter_check_requires_a_non_writing_guard(
    run_project: RunProject, recipe: str, finding: tuple[str, str, int] | None
) -> None:
    files = {"go.mod": GO_MOD, "Makefile": GO_MAKEFILE.replace(GO_FORMAT_RECIPE, recipe)}
    _, report = run_project(files)
    assert rule_findings(report, "TL-3") == ([] if finding is None else [finding])


def test_go_project_without_tools(run_project: RunProject) -> None:
    _, report = run_project({"go.mod": GO_MOD, "Makefile": GO_WITHOUT_TOOLS_MAKEFILE})
    assert rule_findings(report, "TL-3") == [
        GOFMT_NOT_RUN,
        ("error", "make check does not run the linter (configured: go)", 3),
        ("error", "make check does not run the type checker (configured: go)", 3),
    ]


def test_rust_gate_uses_native_tools(run_project: RunProject) -> None:
    exit_code, report = run_project({"Cargo.toml": CARGO_TOML, "Makefile": RUST_MAKEFILE})
    assert (exit_code, report["findings"]) == (0, [])


def test_rust_project_without_lint_and_formatting(run_project: RunProject) -> None:
    _, report = run_project(
        {"Cargo.toml": CARGO_TOML, "Makefile": "dev:\n\tcargo run\ncheck:\n\tcargo check\ncheck-all: check\n"}
    )
    assert [message.split(";")[0] for _, message, _ in rule_findings(report, "TL-3")] == [
        "make check does not run the formatter in check mode, verifying formatting without rewriting files (configured: cargo)",
        "make check does not run the linter (configured: cargo)",
    ]


def test_rust_clippy_must_deny_warnings(run_project: RunProject) -> None:
    files = {
        "Cargo.toml": CARGO_TOML,
        "Makefile": RUST_MAKEFILE.replace("cargo clippy -- -D warnings", "cargo clippy -- -D style"),
    }
    _, report = run_project(files)
    assert [message for _, message, _ in rule_findings(report, "TL-3")] == [
        "make check does not run the linter (configured: cargo)"
    ]
