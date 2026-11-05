import re


def group_text(match: re.Match[str], group: str | int) -> str | None:
    value = match.group(group)
    return value if isinstance(value, str) else None
