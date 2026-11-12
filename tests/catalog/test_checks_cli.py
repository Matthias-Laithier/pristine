import json

import pytest

from pristine.checks.registry import file_checks, path_checks
from pristine.cli.main import main

RETIRED_IDS = frozenset({"SAFE-2"})


def test_catalog_lists_every_executable_check(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["checks", "--json"]) == 0
    entries = json.loads(capsys.readouterr().out)
    ids = [entry["check_id"] for entry in entries]
    registered = {check.check_id for check in [*file_checks(), *path_checks()]}
    assert len(ids) == len(set(ids)) == 39
    assert set(ids) == registered | {"PROJ-1", "PROJ-2", "PROJ-3", "PROJ-4"}
    assert all(entry["title"] and entry["summary"] for entry in entries)
    assert all(entry["checked_by"] in {"check", "project"} for entry in entries)
    assert not any("statement" in entry for entry in entries)
    assert main(["checks"]) == 0
    text = capsys.readouterr().out
    assert len(text.splitlines()) == len(entries)
    assert "STR-1 File Size (check):" in text
    expected = [
        f"{group}-{number}"
        for group, count in (("STR", 11), ("DEP", 5), ("SAFE", 15), ("TEST", 5), ("PROJ", 4))
        for number in range(1, count + 1)
        if f"{group}-{number}" not in RETIRED_IDS
    ]
    assert ids == expected
    assert all("rule_id" not in entry for entry in entries)


def test_guide_is_short_and_contains_caller_first_design(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["guide"]) == 0
    text = capsys.readouterr().out
    assert text.startswith("# Pristine guide\n")
    assert len([line for line in text.splitlines() if line.startswith("- ")]) == 7
    assert len(text.split()) < 200
    assert "operation the caller needs" in text
    assert "pristine rule" not in text


@pytest.mark.parametrize("command", ["rule", "rules", "growth"])
def test_removed_commands_are_usage_errors(command: str) -> None:
    with pytest.raises(SystemExit) as result:
        main([command])
    assert result.value.code == 2
