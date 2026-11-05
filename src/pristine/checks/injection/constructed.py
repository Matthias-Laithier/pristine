import re
from dataclasses import dataclass

from tree_sitter import Node

SQL_START = re.compile(r"\s*(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|DROP|ALTER)\b", re.IGNORECASE)
CONSTANT_NAME = re.compile(r"_*[A-Z][A-Z0-9_]*")
PLACEHOLDER_NAME = re.compile(r"placeholder", re.IGNORECASE)
ESCAPING_CALL = re.compile(r"(?<!un)(quote|escape)|saniti[sz]e|^(int|float|len|Number)$", re.IGNORECASE)
REQUEST_ATTRIBUTES = frozenset({"GET", "POST", "META", "FILES", "COOKIES", "REQUEST"})


@dataclass(frozen=True)
class Injection:
    node: Node
    message: str


def is_constant_reference(text: str) -> bool:
    segments = [segment for segment in text.split(".") if segment not in REQUEST_ATTRIBUTES]
    return any(CONSTANT_NAME.fullmatch(segment) for segment in segments)


def is_escaping_callee(text: str) -> bool:
    return ESCAPING_CALL.search(text.rsplit(".", 1)[-1]) is not None


def is_placeholder_name(text: str) -> bool:
    return PLACEHOLDER_NAME.search(text) is not None


def starts_with_sql(text: str) -> bool:
    return SQL_START.match(text) is not None
