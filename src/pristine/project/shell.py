import shlex
from collections.abc import Iterator

OPERATOR_CHARACTERS = frozenset("();&|")
OPTION_PREFIX = "-"
PATH_SEPARATOR = "/"
VARIABLE_ASSIGNMENT = "="
MAKE_PROGRAMS = frozenset({"make", "gmake"})
MAKE_REDIRECTING_OPTIONS = ("-C", "--directory", "-f", "--file", "--makefile")


def words_of(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def is_operator(word: str) -> bool:
    return bool(word) and set(word) <= OPERATOR_CHARACTERS


def command_segments(command: str) -> list[list[str]]:
    segments: list[list[str]] = [[]]
    for word in words_of(command):
        if is_operator(word):
            segments.append([])
        else:
            segments[-1].append(word)
    return [segment for segment in segments if segment]


def program_name(word: str) -> str:
    return word.rsplit(PATH_SEPARATOR, 1)[-1]


def program_calls(command: str, programs: frozenset[str]) -> Iterator[tuple[str, list[str]]]:
    for words in command_segments(command):
        yield from (
            (program_name(word), words[index + 1 :])
            for index, word in enumerate(words)
            if program_name(word) in programs
        )


def positionals(arguments: list[str]) -> list[str]:
    return [argument for argument in arguments if not argument.startswith(OPTION_PREFIX)]


def invoked_make_targets(command: str) -> list[str]:
    return [
        argument
        for _, arguments in program_calls(command, MAKE_PROGRAMS)
        if not any(option.startswith(MAKE_REDIRECTING_OPTIONS) for option in arguments)
        for argument in positionals(arguments)
        if VARIABLE_ASSIGNMENT not in argument
    ]
