import re
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from importlib.resources.abc import Traversable

__all__ = ["RuleDocument", "UnknownRule", "guide_text", "rule_documents", "select_rules"]

HUB_NAME = "README.md"
RULE_FILE_NAME = re.compile(r"[a-z]+-\d+-.+\.md")
RULE_HEADING = re.compile(r"# (?P<rule_id>[A-Z]+-(?P<number>\d+)) (?P<title>.+)")
ALL_RULES = "ALL"
RULE_LINK = re.compile(r"\[(?P<label>[^\]]+)\]\([^):\s]+\.md(?:#[^)\s]*)?\)")


@dataclass(frozen=True)
class RuleDocument:
    rule_id: str
    title: str
    text: str

    @property
    def statement(self) -> str:
        paragraph = self.text.partition("\n")[2].strip().partition("\n\n")[0]
        return " ".join(paragraph.splitlines())


class UnknownRule(LookupError):
    pass


def rules_directory() -> Traversable:
    return files("pristine") / "rules"


def read_without_links(document: Traversable) -> str:
    return RULE_LINK.sub(r"\g<label>", document.read_text(encoding="utf-8"))


def guide_text() -> str:
    return read_without_links(rules_directory() / HUB_NAME)


def parse_rule(name: str, text: str) -> RuleDocument:
    heading = RULE_HEADING.fullmatch(text.partition("\n")[0])
    if heading is None:
        raise ValueError(f"rule document {name} does not start with a '# <ID> <Title>' heading")
    return RuleDocument(heading["rule_id"], heading["title"], text)


def rule_order(document: RuleDocument) -> tuple[str, int]:
    prefix, _, number = document.rule_id.partition("-")
    return prefix, int(number)


@cache
def rule_documents() -> tuple[RuleDocument, ...]:
    paths = [path for path in rules_directory().iterdir() if RULE_FILE_NAME.fullmatch(path.name)]
    documents = [parse_rule(path.name, read_without_links(path)) for path in paths]
    return tuple(sorted(documents, key=rule_order))


def chapter_of(document: RuleDocument) -> str:
    return document.rule_id.partition("-")[0]


def select_rules(selector: str) -> list[RuleDocument]:
    wanted = selector.upper()
    selected = [
        document for document in rule_documents() if wanted in (ALL_RULES, document.rule_id, chapter_of(document))
    ]
    if not selected:
        raise UnknownRule(selector)
    return selected
