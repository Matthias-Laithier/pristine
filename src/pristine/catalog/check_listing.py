import json

from pristine.checks.registry import file_checks, path_checks
from pristine.project.inspection import CHECK_GROUPS

GROUP_ORDER = ("STR", "DEP", "SAFE", "TEST", "PROJ")


def check_order(entry: dict[str, str]) -> tuple[int, int]:
    prefix, _, number = entry["check_id"].partition("-")
    return GROUP_ORDER.index(prefix), int(number)


def check_entries() -> list[dict[str, str]]:
    entries = [
        {"check_id": check.check_id, "title": check.title, "checked_by": "check", "summary": check.summary}
        for check in [*file_checks(), *path_checks()]
    ]
    entries.extend(
        {"check_id": check_id, "title": title, "checked_by": "project", "summary": summary}
        for check_id, title, summary, _ in CHECK_GROUPS
    )
    return sorted(entries, key=check_order)


def render_checks_json() -> str:
    return json.dumps(check_entries(), indent=2)


def render_checks_text() -> str:
    entries = check_entries()
    return "\n".join(
        f"{entry['check_id']} {entry['title']} ({entry['checked_by']}): {entry['summary']}" for entry in entries
    )
