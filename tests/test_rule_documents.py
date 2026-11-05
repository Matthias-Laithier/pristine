import re
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]
RULES_DIRECTORY = REPOSITORY / "src" / "pristine" / "rules"
HUB = RULES_DIRECTORY / "README.md"
NON_RULE_DOCUMENTS = frozenset({"README.md", "STYLE.md"})
RULE_DOCUMENTS = sorted(RULES_DIRECTORY.glob("*.md"))
RULE_FILES = [path for path in RULE_DOCUMENTS if path.name not in NON_RULE_DOCUMENTS]
LINKED_DOCUMENTS = [*RULE_DOCUMENTS, REPOSITORY / "README.md", REPOSITORY / "AGENTS.md"]
CHAPTERS_HEADING = "## Chapters"
FENCED_BLOCK = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
EXTERNAL_TARGET = re.compile(r"^(?:[a-z]+:|#)")
RULE_HEADING = re.compile(r"# (?P<id>[A-Z]+-\d+) \S")
CHAPTER_ITEM = re.compile(r"^- (?P<id>[A-Z]+-\d+) \S", re.MULTILINE)


def relative_links(markdown: str) -> list[str]:
    prose = FENCED_BLOCK.sub("", markdown)
    targets = [target.split("#")[0] for target in MARKDOWN_LINK.findall(prose)]
    return [target for target in targets if target and not EXTERNAL_TARGET.match(target)]


def rule_id(path: Path) -> str:
    first_line = path.read_text().splitlines()[0]
    heading = RULE_HEADING.match(first_line)
    assert heading, f"{path.name} starts with {first_line!r}, expected '# <ID> <Title>'"
    return heading["id"]


@pytest.mark.parametrize("document", LINKED_DOCUMENTS, ids=lambda path: path.name)
def test_relative_links_resolve(document: Path) -> None:
    targets = relative_links(document.read_text())
    broken = [target for target in targets if not (document.parent / target).exists()]
    assert not broken, f"{document.name} links to missing files: {broken}"


def listed_rule_ids(hub: str) -> list[str]:
    chapters = hub.split(CHAPTERS_HEADING, 1)[1]
    return CHAPTER_ITEM.findall(chapters)


def test_hub_chapters_list_every_rule_file() -> None:
    listed = listed_rule_ids(HUB.read_text())
    assert len(listed) == len(set(listed)), "the hub lists a rule ID twice"
    assert set(listed) == {rule_id(path) for path in RULE_FILES}


def test_rule_files_start_with_a_unique_id_heading() -> None:
    identifiers = [rule_id(path) for path in RULE_FILES]
    mismatched = [
        path.name
        for path, identifier in zip(RULE_FILES, identifiers, strict=True)
        if not path.name.startswith(f"{identifier.lower()}-")
    ]
    assert not mismatched, f"file names disagree with their heading ID: {mismatched}"
    assert len(identifiers) == len(set(identifiers))
