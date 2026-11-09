from functools import cache
from pathlib import Path

lazy from tree_sitter import Parser
lazy from tree_sitter_language_pack import Error, detect_language_from_path, downloaded_languages, get_parser

SCRIPT_LANGUAGES = ("javascript", "typescript", "tsx")
RUBY = "ruby"
RUBY_FILE_NAMES = ("Gemfile", "Rakefile", "Guardfile", "Vagrantfile", "Podfile", "Fastfile", "Brewfile")
LANGUAGE_BY_FILE_NAME = {
    "Makefile": "make",
    "makefile": "make",
    "GNUmakefile": "make",
    "Dockerfile": "dockerfile",
} | dict.fromkeys(RUBY_FILE_NAMES, RUBY)
LANGUAGE_BY_SUFFIX = dict.fromkeys((".gemspec", ".podspec", ".ru"), RUBY)


class GrammarError(Exception):
    pass


def language_for(path: Path) -> str | None:
    named = LANGUAGE_BY_FILE_NAME.get(path.name) or LANGUAGE_BY_SUFFIX.get(path.suffix)
    return named or detect_language_from_path(str(path))


@cache
def parser_for(language: str) -> Parser:
    try:
        return get_parser(language)
    except Error as error:
        raise GrammarError(str(error)) from error


def cached_languages() -> frozenset[str]:
    return frozenset(downloaded_languages())
