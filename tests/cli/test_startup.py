import pytest

from tests.conftest import run_cli


@pytest.mark.parametrize(
    ("arguments", "expected_stdout", "expected_stderr"),
    [
        (("--version",), "pristine ", ""),
        (
            ("--help",),
            "usage: pristine [-h] [--version] {check,project,audit,guide,checks} ...\n",
            "",
        ),
        (("guide",), "# Pristine guide\n", ""),
        (("checks",), "STR-1 File Size (check): ", ""),
        (("checks", "--json"), '[\n  {\n    "check_id": "STR-1",', ""),
    ],
    ids=["version", "help", "guide", "checks", "checks-json"],
)
def test_light_commands_run_without_parser_packages(
    arguments: tuple[str, ...], expected_stdout: str, expected_stderr: str
) -> None:
    exit_code, stdout, stderr = run_cli(*arguments)
    assert exit_code == 0
    assert stderr == expected_stderr
    assert stdout.startswith(expected_stdout)
