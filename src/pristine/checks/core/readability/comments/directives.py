import re

from pristine.syntax.parsing import CommentText

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
CHECKED_JAVASCRIPT_SUFFIXES = (".js", ".mjs", ".cjs")
JSDOC_OPENING = "/**"
JSDOC_DECORATION = re.compile(r"^\s*(/\*\*|\*/|\*)?|\*/\s*$")
TYPE = r"\{.+\}"
NAME = r"\[?[\w$.]+(=[^\]]*)?\]?"
TYPE_TAG = re.compile(
    rf"@(type|satisfies)\s*{TYPE}"
    rf"|@(param|property)\s*{TYPE}\s*{NAME}"
    rf"|@returns?\s*{TYPE}"
    rf"|@typedef\s*({TYPE}\s*)?[\w$]+"
    rf"|@template\s+({TYPE}\s+)?[\w$]+(\s*,\s*[\w$]+)*"
)


def is_directive(comment: CommentText) -> bool:
    if comment.line == 1 and comment.text.startswith("#!"):
        return True
    body = COMMENT_MARKERS.sub("", comment.text, count=1)
    return any(pattern.match(body) for pattern in DIRECTIVE_PATTERNS)


def is_type_annotation(path: str, comment: CommentText) -> bool:
    if not path.endswith(CHECKED_JAVASCRIPT_SUFFIXES) or not comment.text.startswith(JSDOC_OPENING):
        return False
    lines = [JSDOC_DECORATION.sub("", line).strip() for line in comment.text.splitlines()]
    tags = [line for line in lines if line]
    return bool(tags) and all(TYPE_TAG.fullmatch(tag) for tag in tags)


def is_machine_read(path: str, comment: CommentText) -> bool:
    return is_directive(comment) or is_type_annotation(path, comment)
