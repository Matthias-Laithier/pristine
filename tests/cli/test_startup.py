import pytest

from tests.conftest import run_cli


@pytest.mark.parametrize(
    ("arguments", "expected_stdout", "expected_stderr"),
    [
        (("--version",), "pristine ", ""),
        (
            ("--help",),
            "usage: pristine [-h] [--version]\n                {check,project,audit,growth,guide,rule,rules} ...\n",
            "",
        ),
        (("rule", "CR-20"), "# CR-20 Minimize the Resulting Codebase\n", ""),
        (("guide",), "# Coding rules\n", ""),
        (("rules",), "BS-1 Validate Untrusted Input at the Boundary (check): ", ""),
        (("rules", "--json"), '[\n  {\n    "rule_id": "BS-1",', ""),
    ],
    ids=["version", "help", "rule", "guide", "rules", "rules-json"],
)
def test_light_commands_run_without_parser_packages(
    arguments: tuple[str, ...], expected_stdout: str, expected_stderr: str
) -> None:
    exit_code, stdout, stderr = run_cli(*arguments)
    assert exit_code == 0
    assert stderr == expected_stderr
    assert stdout.startswith(expected_stdout)
