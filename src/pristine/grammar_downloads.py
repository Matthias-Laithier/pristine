import sys
from pathlib import Path

from pristine.inspection import BINARY_SNIFF_BYTES, is_generated, skip_reason
from pristine.services.grammars import cached_languages, language_for

DOWNLOAD_NOTICE = "pristine: downloading the {language} grammar (first use)"


def file_head(path: Path) -> bytes | None:
    try:
        with path.open("rb") as file:
            return file.read(BINARY_SNIFF_BYTES)
    except OSError:
        return None


def uncached_language(shown_path: str, cached: frozenset[str]) -> str | None:
    path = Path(shown_path)
    language = language_for(path)
    if language is None or language in cached:
        return None
    head = file_head(path)
    if head is None or skip_reason(path, head) or is_generated(head.decode(errors="replace")):
        return None
    return language


def announce_grammar_downloads(paths: list[str]) -> None:
    cached = cached_languages()
    languages = {language for path in paths if (language := uncached_language(path, cached))}
    for language in sorted(languages):
        print(DOWNLOAD_NOTICE.format(language=language), file=sys.stderr)
