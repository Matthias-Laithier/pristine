from functools import cache
from pathlib import Path

lazy from tree_sitter import Parser
lazy from tree_sitter_language_pack import Error, downloaded_languages, get_parser

SCRIPT_LANGUAGES = ("javascript", "typescript", "tsx")
LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}
SUPPORTED_LANGUAGES = frozenset(LANGUAGE_BY_SUFFIX.values())


class GrammarError(Exception):
    pass


def language_for(path: Path) -> str | None:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower())


@cache
def parser_for(language: str) -> Parser:
    if language not in SUPPORTED_LANGUAGES:
        raise GrammarError(f"unsupported source language: {language}")
    try:
        return get_parser(language)
    except Error as error:
        raise GrammarError(str(error)) from error


def cached_languages() -> frozenset[str]:
    return frozenset(downloaded_languages()) & SUPPORTED_LANGUAGES
