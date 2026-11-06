import shlex
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

MINIMUM_REQUIREMENT_WORD_COUNT = 2
DIRECTIVE_KINDS = frozenset({"require", "replace"})
ARROW = "=>"
EXACT_REPLACEMENT_WORD_COUNT = 4
REMOTE_REPLACEMENT_WORD_COUNT = 4
WILDCARD_REPLACEMENT_WORD_COUNT = 3
EXACT_REMOTE_REPLACEMENT_WORD_COUNT = 5
WILDCARD_ARROW_INDEX = 1
EXACT_ARROW_INDEX = 2
SUPPORTED_ARROW_INDEXES = frozenset({WILDCARD_ARROW_INDEX, EXACT_ARROW_INDEX})


@dataclass(frozen=True)
class GoDirective:
    kind: str
    words: tuple[str, ...]


def go_words(text: str) -> list[str]:
    lexer = shlex.shlex(text.split("//", 1)[0], posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


@dataclass(frozen=True)
class ParsedGoReplacement:
    old_name: str
    old_version: str | None
    replacement: str


def block_directive(words: list[str], kind: str) -> GoDirective | None:
    return GoDirective(kind, tuple(words)) if len(words) > 1 else None


def standalone_directive(words: list[str]) -> GoDirective | None:
    return GoDirective(words[0], tuple(words[1:])) if len(words) > MINIMUM_REQUIREMENT_WORD_COUNT else None


def parse_go_mod(text: str) -> tuple[frozenset[str], bool, bool | None]:
    block: str | None = None
    requirements: dict[str, str] = {}
    replaces: list[tuple[str, ...]] = []
    pins_runtime = False
    for line in text.splitlines():
        words = go_words(line)
        if not words:
            continue
        directive, block = inline_directive(words, block)
        if directive is not None:
            store_directive(requirements, replaces, directive)
        pins_runtime = pins_runtime or pins_go_runtime(words, block)
    return frozenset(requirements), pins_runtime, needs_go_sum(requirements, replaces)


def inline_directive(words: list[str], block: str | None) -> tuple[GoDirective | None, str | None]:
    if block is not None:
        if words[0] == ")":
            return None, None
        return block_directive(words, block), block
    if words[0] == "go" and len(words) > 1:
        return None, None
    if words[0] not in DIRECTIVE_KINDS:
        return None, None
    if words[-1] == "(":
        return None, words[0]
    return standalone_directive(words), None


def pins_go_runtime(words: list[str], block: str | None) -> bool:
    return block is None and words[0] == "go" and len(words) > 1


def store_directive(
    requirements: dict[str, str],
    replaces: list[tuple[str, ...]],
    directive: GoDirective,
) -> None:
    if directive.kind == "replace":
        replaces.append(directive.words)
    elif len(directive.words) >= MINIMUM_REQUIREMENT_WORD_COUNT:
        requirements[directive.words[0]] = directive.words[1]


def is_local_go_path(path: str) -> bool:
    return path in {".", ".."} or path.startswith(("./", "../", "/"))


def selected_go_replacements(
    requirements: Mapping[str, str],
    replaces: Iterable[tuple[str, ...]],
) -> dict[str, str] | None:
    parsed = [parse_go_replacement(replace) for replace in replaces]
    if any(replacement is None for replacement in parsed):
        return None
    exact_replacements = {
        replacement.old_name: replacement.replacement
        for replacement in parsed
        if replacement is not None
        and replacement.old_version is not None
        and requirements.get(replacement.old_name) == replacement.old_version
    }
    return {
        replacement.old_name: exact_replacements.get(replacement.old_name, replacement.replacement)
        for replacement in parsed
        if replacement is not None
        and (replacement.old_version is None or requirements.get(replacement.old_name) == replacement.old_version)
    }


def parse_go_replacement(replace: tuple[str, ...]) -> ParsedGoReplacement | None:
    try:
        arrow = replace.index(ARROW)
    except ValueError:
        return None
    if arrow not in SUPPORTED_ARROW_INDEXES:
        return None
    wildcard = arrow == WILDCARD_ARROW_INDEX
    if wildcard:
        if len(replace) not in {WILDCARD_REPLACEMENT_WORD_COUNT, REMOTE_REPLACEMENT_WORD_COUNT}:
            return None
        replacement_index = -1 if len(replace) == WILDCARD_REPLACEMENT_WORD_COUNT else -2
        replacement = replace[replacement_index]
        return (
            ParsedGoReplacement(replace[0], None, replacement)
            if is_local_go_path(replacement) == (len(replace) == WILDCARD_REPLACEMENT_WORD_COUNT)
            else None
        )
    if len(replace) not in {EXACT_REPLACEMENT_WORD_COUNT, EXACT_REMOTE_REPLACEMENT_WORD_COUNT}:
        return None
    replacement_index = -2 if len(replace) == EXACT_REMOTE_REPLACEMENT_WORD_COUNT else -1
    replacement = replace[replacement_index]
    return (
        ParsedGoReplacement(replace[0], replace[1], replacement)
        if is_local_go_path(replacement) == (len(replace) == EXACT_REPLACEMENT_WORD_COUNT)
        else None
    )


def needs_go_sum(requirements: Mapping[str, str], replaces: Iterable[tuple[str, ...]]) -> bool | None:
    replacements = selected_go_replacements(requirements, replaces)
    if replacements is None:
        return None
    return any(not is_local_go_path(replacements.get(module, module)) for module in requirements)
