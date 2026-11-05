from functools import cache
from pathlib import Path

from tree_sitter import Parser
from tree_sitter_language_pack import Error, detect_language_from_path, downloaded_languages, get_parser

SCRIPT_LANGUAGES = ("javascript", "typescript", "tsx")
LANGUAGE_BY_FILE_NAME = {"Makefile": "make", "makefile": "make", "GNUmakefile": "make", "Dockerfile": "dockerfile"}

GrammarError = Error


def language_for(path: Path) -> str | None:
    return LANGUAGE_BY_FILE_NAME.get(path.name) or detect_language_from_path(str(path))


@cache
def parser_for(language: str) -> Parser:
    return get_parser(language)


def cached_languages() -> frozenset[str]:
    return frozenset(downloaded_languages())
