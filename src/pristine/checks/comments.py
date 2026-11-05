import re

from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.findings import Finding, Severity
from pristine.parsing import CommentText, ParsedFile, all_nodes, line_of, node_text

RULE_ID = "CR-3"
PREVIEW_LENGTH = 60
COMMENT_MARKERS = re.compile(r"^\s*(#+|//+!?|/\*+!?|--+|;+|%+)?\s*")
DIRECTIVE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"noqa\b",
        r"type:\s",
        r"(pyright|mypy|ty|pyrefly|pylint|ruff|flake8|isort|rubocop|swiftlint|jshint|jscs|rustfmt)\s*:",
        r"fmt:\s*(off|on|skip)\b",
        r"pragma\b",
        r"(-\*-\s*)?(en)?coding[:=]",
        r"(eslint|stylelint|oxlint)-(disable|enable)",
        r"@ts-(ignore|expect-error|nocheck|check)\b",
        r"(prettier|biome|deno-lint|dprint)-ignore",
        r"(istanbul|c8|v8)\s+ignore\b",
        r"shellcheck\s+(disable|source|shell)=",
        r"go:\w",
        r"\+build\s",
        r"nolint\b",
        r"clang-format\s+(off|on)\b",
        r"frozen_string_literal:",
        r"<reference\s",
        r"@(jsx|jsxImportSource|vitest-environment|jest-environment)\b",
        r"SPDX-License-Identifier:",
    )
)

FRAMEWORK_DECORATOR_NAMES = frozenset(
    {
        "tool",
        "tool_plain",
        "function_tool",
        "resource",
        "prompt",
        "command",
        "group",
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "api_route",
    }
)

EXPLICIT_DESCRIPTION_KEYWORD = "description"

DOC_TEXT_HINT = "allowed only on units a framework or published reference generator reads (CR-3 exceptions)"


def is_machine_read(comment: CommentText) -> bool:
    if comment.line == 1 and comment.text.startswith("#!"):
        return True
    body = COMMENT_MARKERS.sub("", comment.text, count=1)
    return any(pattern.match(body) for pattern in DIRECTIVE_PATTERNS)


def decorator_name(expression: Node | None) -> str | None:
    if expression is not None and expression.type == "attribute":
        expression = expression.child_by_field_name("attribute")
    return node_text(expression)


def call_keywords(call: Node) -> set[str]:
    arguments = call.child_by_field_name("arguments")
    keywords = [] if arguments is None else arguments.named_children
    return {
        node_text(keyword.child_by_field_name("name")) or ""
        for keyword in keywords
        if keyword.type == "keyword_argument"
    }


def publishes_docstring(decorator: Node) -> bool:
    expression = decorator.named_children[0] if decorator.named_children else None
    if expression is None or expression.type != "call":
        return decorator_name(expression) in FRAMEWORK_DECORATOR_NAMES
    name = decorator_name(expression.child_by_field_name("function"))
    return name in FRAMEWORK_DECORATOR_NAMES and EXPLICIT_DESCRIPTION_KEYWORD not in call_keywords(expression)


def framework_docstring_line(decorated: Node) -> int | None:
    definition = decorated.child_by_field_name("definition")
    if definition is None or definition.type != "function_definition":
        return None
    body = definition.child_by_field_name("body")
    decorators = [child for child in decorated.named_children if child.type == "decorator"]
    if body is None or not body.named_children or not any(map(publishes_docstring, decorators)):
        return None
    return line_of(body.named_children[0])


def framework_docstring_lines(parsed: ParsedFile) -> set[int]:
    decorated = [node for node in all_nodes(parsed.root) if node.type == "decorated_definition"]
    return {line for line in map(framework_docstring_line, decorated) if line is not None}


def preview(text: str) -> str:
    return " ".join(text.split())[:PREVIEW_LENGTH]


def comment_finding(path: str, comment: CommentText) -> Finding:
    if comment.is_documentation:
        message = f"documentation text '{preview(comment.text)}' is {DOC_TEXT_HINT}"
    else:
        message = f"comment '{preview(comment.text)}'; make the code say it, then delete the comment"
    return Finding(path, comment.line, RULE_ID, Severity.ERROR, message)


def check_comments(parsed: ParsedFile) -> list[Finding]:
    framework_lines = framework_docstring_lines(parsed) if parsed.language == "python" else set()
    return [
        comment_finding(parsed.path, comment)
        for comment in parsed.comments
        if not is_machine_read(comment) and not (comment.is_documentation and comment.line in framework_lines)
    ]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Every comment, doc comment, and docstring. Shebangs and comments that start with a toolchain directive, "
            "such as noqa, type: ignore, eslint-disable, or //go:build, are allowed, and so are Python docstrings "
            "of functions under a framework decorator that publishes them, such as an MCP tool or a FastAPI route."
        ),
        run=check_comments,
    )
)
