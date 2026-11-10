import json
from pathlib import Path

import pytest

from pristine.catalog.rule_documents import rule_documents
from pristine.catalog.rule_listing import PROJECT_RULE_SUMMARIES
from pristine.checks.registry import file_checks, path_checks
from pristine.cli.main import main

RULES_SOURCE = Path(__file__).parents[2] / "src" / "pristine" / "rules"


def listed_rules(capsys: pytest.CaptureFixture[str]) -> dict[str, dict[str, str]]:
    assert main(["rules", "--json"]) == 0
    return {entry["rule_id"]: entry for entry in json.loads(capsys.readouterr().out)}


def test_guide_prints_the_hub_with_links_as_plain_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["guide"]) == 0
    output = capsys.readouterr().out
    hub_heading = (RULES_SOURCE / "README.md").read_text(encoding="utf-8").partition("\n")[0]
    assert output.startswith(hub_heading + "\n")
    assert "- CR-13 Nesting Depth\n" in output
    assert ".md)" not in output


def test_guide_index_states_review_rules_and_summarizes_checked_ones(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["guide"]) == 0
    index = capsys.readouterr().out.partition("\n## Rule index\n")[2]
    statement = (RULES_SOURCE / "cr-20-minimize-the-resulting-codebase.md").read_text(encoding="utf-8").splitlines()[2]
    summary = next(check.summary for check in file_checks() if check.rule_id == "CR-13")
    assert f"\n- CR-20 Minimize the Resulting Codebase (review): {statement}\n" in index
    assert f"\n- CR-13 Nesting Depth (check): {summary}\n" in index


@pytest.mark.parametrize("command", ["guide", "rules"])
def test_rule_guidance_requires_targeted_reading_and_review(capsys: pytest.CaptureFixture[str], command: str) -> None:
    assert main([command]) == 0
    output = capsys.readouterr().out.lower()
    assert "pristine rule <id>" in output
    assert "review rule" in output


def test_rule_prints_each_rule_matched_case_insensitively(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["rule", "cr-14", "CR-12"]) == 0
    output = capsys.readouterr().out
    assert output.startswith("# CR-14 Value Dispatch Through a Registry\n")
    assert "registry form that CR-7 and CR-23 require" in output
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
    checked_by = (rules["CR-13"]["checked_by"], rules["TL-1"]["checked_by"], rules["CR-20"]["checked_by"])
    assert checked_by == ("check", "project", "review")
    assert rules["CR-13"]["statement"].startswith("2 levels of nesting is the target, 3 is the hard limit")
    assert len(rules) == len(list(RULES_SOURCE.glob("*-*-*.md")))


def test_every_checked_rule_has_a_rule_document(capsys: pytest.CaptureFixture[str]) -> None:
    registered = {check.rule_id for check in [*file_checks(), *path_checks()]} | PROJECT_RULE_SUMMARIES.keys()
    assert registered <= listed_rules(capsys).keys()


def test_rule_prints_a_chapter_and_all_rules(capsys: pytest.CaptureFixture[str]) -> None:
    main(["rule", "tl"])
    chapter = [line for line in capsys.readouterr().out.splitlines() if line.startswith("# ")]
    main(["rule", "all"])
    every_rule = [line for line in capsys.readouterr().out.splitlines() if line.startswith("# ")]
    assert [heading.split()[1] for heading in chapter] == ["TL-1", "TL-2", "TL-3", "TL-4"]
    assert len(every_rule) == len(rule_documents())
