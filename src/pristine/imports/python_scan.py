import re
from collections.abc import Iterator

from pristine.imports.python_statements import WILDCARD, PythonImport

CONTINUED_LINE = r"[^\n;]*(?:\\\n[^\n;]*)*"
IMPORT_CANDIDATES = re.compile(
    r"(?=from|import|__import__)"
    r"(?:from\s+(?P<module>\.*[\w.]*)\s+import\s+(?P<names>\([^)]*\)|" + CONTINUED_LINE + ")"
    r"|import\s+(?P<modules>" + CONTINUED_LINE + ")"
    r"|(?:import_module|__import__)\s*\(\s*['\"](?P<dynamic>[\w.]+)['\"])"
)
LINE_COMMENT = re.compile(r"#[^\n]*")
NAME_SEPARATORS = "(),\\"
UNKNOWN_LINE = 0


def listed_names(listing: str) -> tuple[str, ...]:
    cleaned = LINE_COMMENT.sub("", listing)
    for separator in NAME_SEPARATORS:
        cleaned = cleaned.replace(separator, ",")
    entries = (entry.split() for entry in cleaned.split(","))
    return tuple(words[0] for words in entries if words and words[0] != WILDCARD)


def candidate_imports(text: str) -> Iterator[PythonImport]:
    for match in IMPORT_CANDIDATES.finditer(text):
        module = match.group("module")
        if module is not None:
            dotted = module.lstrip(".")
            yield PythonImport(UNKNOWN_LINE, len(module) - len(dotted), dotted, listed_names(match.group("names")))
            continue
        modules = match.group("modules")
        listed = listed_names(modules) if modules is not None else (match.group("dynamic"),)
        yield from (PythonImport(UNKNOWN_LINE, 0, name, ()) for name in listed)
