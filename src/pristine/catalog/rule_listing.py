import json

from pristine.catalog.rule_documents import RuleDocument, guide_text, rule_documents
from pristine.checks.registry import file_checks, path_checks

PROJECT_RULE_SUMMARIES = {
    "TL-1": "A root Makefile with dev, check, and check-all, a build target when the project ships artifacts, and no component Makefiles.",
    "TL-2": "check-all runs check.",
    "TL-3": (
        "A formatter, a linter, and a type checker are configured and run by make check, the formatter in check mode "
        "and the type checker in strict mode."
    ),
    "TL-4": (
        "A deployable project commits its lockfile, Makefile installs never rewrite the lockfile, "
        "and the Python and Node.js runtime versions are pinned."
    ),
}

REVIEW = "review"
RULES_NEXT_STEP = (
    "next: read a rule with 'pristine rule <ID>'. Rules marked (review) have no automated check, and a checked "
    "rule is often checked only in part: review your code against every relevant rule yourself."
)
INDEX_HEADING = (
    "## Rule index\n"
    "Each entry gives a rule ID, its title, how it is checked, and its statement. Read the full rule with "
    "`pristine rule <ID>`."
)


def check_summaries() -> dict[str, tuple[str, str]]:
    checked = {check.rule_id: ("check", check.summary) for check in [*file_checks(), *path_checks()]}
    projected = {rule_id: ("project", summary) for rule_id, summary in PROJECT_RULE_SUMMARIES.items()}
    return checked | projected


def rule_entry(document: RuleDocument, summaries: dict[str, tuple[str, str]]) -> dict[str, str | None]:
    checked_by, summary = summaries.get(document.rule_id, (REVIEW, None))
    return {
        "rule_id": document.rule_id,
        "title": document.title,
        "checked_by": checked_by,
        "summary": summary,
        "statement": document.statement,
    }


def rule_entries() -> list[dict[str, str | None]]:
    summaries = check_summaries()
    return [rule_entry(document, summaries) for document in rule_documents()]


def render_rules_json() -> str:
    return json.dumps(rule_entries(), indent=2)


def render_rule_line(entry: dict[str, str | None]) -> str:
    line = f"{entry['rule_id']} {entry['title']} ({entry['checked_by']})"
    return line if entry["summary"] is None else f"{line}: {entry['summary']}"


def render_rules_text() -> str:
    return "\n".join(map(render_rule_line, rule_entries())) + "\n" + RULES_NEXT_STEP


def render_index_entry(entry: dict[str, str | None]) -> str:
    return f"- {entry['rule_id']} {entry['title']} ({entry['checked_by']}): {entry['statement']}"


def render_guide() -> str:
    index = "\n".join(map(render_index_entry, rule_entries()))
    return f"{guide_text().rstrip()}\n\n{INDEX_HEADING}\n{index}\n"
