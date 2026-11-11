import json

from pristine.checks.registry import file_checks, path_checks
from pristine.project.inspection import CHECK_GROUPS


def check_order(entry: dict[str, str]) -> tuple[str, int]:
    prefix, _, number = entry["rule_id"].partition("-")
    return prefix, int(number)


def check_entries() -> list[dict[str, str]]:
    entries = [
        {"rule_id": check.rule_id, "title": check.title, "checked_by": "check", "summary": check.summary}
        for check in [*file_checks(), *path_checks()]
    ]
    entries.extend(
        {"rule_id": rule_id, "title": title, "checked_by": "project", "summary": summary}
        for rule_id, title, summary, _ in CHECK_GROUPS
    )
    return sorted(entries, key=check_order)


def render_checks_json() -> str:
    return json.dumps(check_entries(), indent=2)


def render_checks_text() -> str:
    entries = check_entries()
    return "\n".join(
        f"{entry['rule_id']} {entry['title']} ({entry['checked_by']}): {entry['summary']}" for entry in entries
    )
