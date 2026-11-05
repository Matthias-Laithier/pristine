import json
from pathlib import Path

import pytest

from pristine.checks.registry import file_checks, path_checks
from pristine.cli import main
from pristine.project.inspection import PROJECT_RULE_SUMMARIES

RULES_SOURCE = Path(__file__).parents[1] / "src" / "pristine" / "rules"


def listed_rules(capsys: pytest.CaptureFixture[str]) -> dict[str, str]:
    assert main(["rules", "--json"]) == 0
    return {entry["rule_id"]: entry["checked_by"] for entry in json.loads(capsys.readouterr().out)}


def test_guide_prints_the_hub_with_links_as_plain_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["guide"]) == 0
    output = capsys.readouterr().out
    hub_heading = (RULES_SOURCE / "README.md").read_text(encoding="utf-8").partition("\n")[0]
    assert output.startswith(hub_heading + "\n")
    assert "- CR-13 Nesting Depth\n" in output
    assert ".md)" not in output


def test_rule_prints_each_rule_matched_case_insensitively(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["rule", "cr-14", "CR-12"]) == 0
    output = capsys.readouterr().out
    assert output.startswith("# CR-14 Value Dispatch Through a Registry\n")
    assert "mechanism that CR-7 permits" in output
    assert ".md)" not in output
    assert "\n# CR-12 Function Size\n" in output


def test_unknown_rule_is_a_usage_error_listing_known_ids(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["rule", "CR-13", "CR-99"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "CR-99" in captured.err
    assert "CR-13" in captured.err


def test_rules_lists_checked_project_and_review_rules(capsys: pytest.CaptureFixture[str]) -> None:
    rules = listed_rules(capsys)
    assert (rules["CR-13"], rules["TL-1"], rules["CR-20"]) == ("check", "project", "review")
    assert len(rules) == len(list(RULES_SOURCE.glob("*-*-*.md")))


def test_every_checked_rule_has_a_rule_document(capsys: pytest.CaptureFixture[str]) -> None:
    registered = {check.rule_id for check in [*file_checks(), *path_checks()]} | PROJECT_RULE_SUMMARIES.keys()
    assert registered <= listed_rules(capsys).keys()
