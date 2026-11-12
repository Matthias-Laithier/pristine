from collections.abc import Callable, Iterable, Mapping

from pristine.reports.findings import Finding
lazy from pristine.syntax.parsing import ParsedFile

type FileRun = Callable[[ParsedFile], list[Finding]]
type Condition = Callable[[ParsedFile], bool]


def requiring(condition: Condition, run: FileRun) -> FileRun:
    def gated(parsed: ParsedFile) -> list[Finding]:
        return run(parsed) if condition(parsed) else []

    return gated


def mentions_any(tokens_by_language: Mapping[str, Iterable[str]]) -> Condition:
    required = {language: tuple(tokens) for language, tokens in tokens_by_language.items()}

    def mentions(parsed: ParsedFile) -> bool:
        tokens = required.get(parsed.language)
        return tokens is None or any(token in parsed.text for token in tokens)

    return mentions


def heads(names: Iterable[str], separator: str = ".") -> tuple[str, ...]:
    return tuple(dict.fromkeys(name.split(separator)[0] for name in names))
