import posixpath
import re
from collections.abc import Iterator

from pristine.imports.registry import ImportEdge, SourceFile, reads_imports
from pristine.syntax.match_groups import group_text

SCRIPT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
INDEX_MODULE = "index"
TEMPLATE_INTERPOLATION = "${"
RELATIVE_SPECIFIER = re.compile(r"\.\.?(/|$)")
COMPILED_TO_SOURCE_SUFFIXES = {".js": (".ts", ".tsx"), ".jsx": (".tsx",), ".mjs": (".mts",), ".cjs": (".cts",)}
MEMBER_ACCESS_CHARACTERS = frozenset("_$.")
SPECIFIER = r"(?P<{name}_quote>['\"`])(?P<{name}>[^'\"`\n]+)(?P={name}_quote)"
SCRIPT_TOKENS = re.compile(
    "|".join(
        [
            r"//[^\n]*",
            r"/\*.*?\*/",
            r"(?:import|export|require)(?:"
            + r"\s+[\w$*{}\s,]*?\bfrom\s*"
            + SPECIFIER.format(name="clause")
            + r"|\s*"
            + SPECIFIER.format(name="bare")
            + r"|\s*\(\s*"
            + SPECIFIER.format(name="call")
            + r"\s*[,)])",
            r"'(?:\\.|[^'\\\n])*'",
            r"\"(?:\\.|[^\"\\\n])*\"",
            r"`(?:\\.|[^`\\])*`",
        ]
    ),
    re.DOTALL,
)


def is_member_access(text: str, position: int) -> bool:
    previous = text[position - 1 : position]
    return previous.isalnum() or previous in MEMBER_ACCESS_CHARACTERS


def module_specifier(token: re.Match[str]) -> str | None:
    specifier = group_text(token, "clause") or group_text(token, "bare") or group_text(token, "call")
    if specifier is None or TEMPLATE_INTERPOLATION in specifier or is_member_access(token.string, token.start()):
        return None
    return specifier if RELATIVE_SPECIFIER.match(specifier) else None


def relative_specifiers(text: str) -> Iterator[tuple[str, int]]:
    line = 1
    previous_start = 0
    for token in SCRIPT_TOKENS.finditer(text):
        line += text.count("\n", previous_start, token.start())
        previous_start = token.start()
        specifier = module_specifier(token)
        if specifier is not None:
            yield specifier, line


def candidate_paths(target: str) -> Iterator[str]:
    yield target
    yield from (f"{target}{suffix}" for suffix in SCRIPT_SUFFIXES)
    yield from (posixpath.join(target, f"{INDEX_MODULE}{suffix}") for suffix in SCRIPT_SUFFIXES)
    stem, suffix = posixpath.splitext(target)
    yield from (f"{stem}{source_suffix}" for source_suffix in COMPILED_TO_SOURCE_SUFFIXES.get(suffix, ()))


def resolve_specifier(importer: str, specifier: str, known_paths: set[str]) -> str | None:
    target = posixpath.normpath(posixpath.join(posixpath.dirname(importer), specifier))
    return next((path for path in candidate_paths(target) if path in known_paths), None)


@reads_imports(*SCRIPT_SUFFIXES)
def read_script_edges(files: list[SourceFile]) -> list[ImportEdge]:
    known_paths = {file.path for file in files}
    edges = []
    for file in files:
        resolved = [
            (resolve_specifier(file.path, specifier, known_paths), line)
            for specifier, line in relative_specifiers(file.text)
        ]
        edges.extend(ImportEdge(file.path, target, line) for target, line in resolved if target is not None)
    return edges
