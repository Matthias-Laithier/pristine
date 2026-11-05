import re
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from importlib.resources.abc import Traversable

__all__ = ["RuleDocument", "UnknownRule", "find_rule", "guide_text", "rule_documents"]

HUB_NAME = "README.md"
RULE_FILE_NAME = re.compile(r"[a-z]+-\d+-.+\.md")
RULE_HEADING = re.compile(r"# (?P<rule_id>[A-Z]+-(?P<number>\d+)) (?P<title>.+)")


@dataclass(frozen=True)
class RuleDocument:
    rule_id: str
    title: str
    text: str


class UnknownRule(LookupError):
    pass


def rules_directory() -> Traversable:
    return files("pristine") / "rules"


def guide_text() -> str:
    return (rules_directory() / HUB_NAME).read_text(encoding="utf-8")


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
    documents = [parse_rule(path.name, path.read_text(encoding="utf-8")) for path in paths]
    return tuple(sorted(documents, key=rule_order))


def find_rule(rule_id: str) -> RuleDocument:
    documents = {document.rule_id: document for document in rule_documents()}
    if rule_id.upper() not in documents:
        raise UnknownRule(rule_id)
    return documents[rule_id.upper()]
