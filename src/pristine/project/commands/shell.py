import re
import shlex
from collections.abc import Iterator

from pristine.project.commands.wrapper_options import WRAPPERS
from pristine.project.commands.wrappers import wrapper_child

OPERATOR_CHARACTERS = frozenset("();&|")
OPTION_PREFIX = "-"
PATH_SEPARATOR = "/"
VARIABLE_ASSIGNMENT = "="
MAKE_PROGRAMS = frozenset({"make", "gmake"})
MAKE_REDIRECTING_OPTIONS = ("-C", "--directory", "-f", "--file", "--makefile")
GUARD_PREFIX_ARGUMENTS = ("test", "-z")
GUARD_WORD_COUNT = len(GUARD_PREFIX_ARGUMENTS) + 1
GUARDED_COMMAND = re.compile(r"^\"?\$\$\((.+)\)\"?$")


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


def call_words(words: list[str]) -> list[tuple[str, list[str]]]:
    name = program_name(words[0])
    calls = [(name, words[1:])]
    if name in WRAPPERS:
        child = wrapper_child(name, words[1:])
        if child is not None:
            calls.append((program_name(child[0]), child[1:]))
    return calls


def program_name(word: str) -> str:
    return word.rsplit(PATH_SEPARATOR, 1)[-1]


def program_calls(command: str, programs: frozenset[str]) -> Iterator[tuple[str, list[str]]]:
    for words in command_segments(command):
        yield from ((name, arguments) for name, arguments in call_words(words) if name in programs)


def guarded_program_calls(command: str, programs: frozenset[str]) -> Iterator[tuple[str, list[str]]]:
    words = words_of(command)
    if len(words) != GUARD_WORD_COUNT or words[: len(GUARD_PREFIX_ARGUMENTS)] != list(GUARD_PREFIX_ARGUMENTS):
        return
    guard = GUARDED_COMMAND.match(words[2])
    if guard is None:
        return
    yield from program_calls(guard[1], programs)


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
