import json
import re

from pristine.match_groups import group_text

BYTE_ORDER_MARK = "\ufeff"
JSON_STRING = r'("(?:[^"\\\n]|\\.)*")'
STRING_OR_COMMENT = re.compile(JSON_STRING + r"|//[^\n]*|/\*.*?\*/", re.DOTALL)
STRING_OR_TRAILING_COMMA = re.compile(JSON_STRING + r"|,(?=\s*[}\]])")


def comment_as_space(match: re.Match[str]) -> str:
    return group_text(match, 1) or " "


def string_or_nothing(match: re.Match[str]) -> str:
    return group_text(match, 1) or ""


def parse_jsonc(text: str) -> object:
    without_comments = STRING_OR_COMMENT.sub(comment_as_space, text.removeprefix(BYTE_ORDER_MARK))
    return json.loads(STRING_OR_TRAILING_COMMA.sub(string_or_nothing, without_comments))
