import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass

PARAMETERS = r"\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)"
DEFINITION = re.compile(
    r"^(?P<indent>[ \t]*)(?:async[ \t]+)?def[ \t]+\w+[ \t]*(?:\[[^\]\n]*\])?[ \t]*" + PARAMETERS + r"[^:]*:[^\n]*\n"
    r"(?P<body>(?:(?P=indent)[ \t]+[^\n]*\n|[ \t]*\n)*)",
    re.MULTILINE,
)
DOCSTRING = re.compile(r"\s*[rRuU]?(?:\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|\"[^\"\n]*\"|'[^'\n]*')")
COMMENT_OR_STRING_PREFIX = re.compile(r"#[^\n]*|\b[rRbBuUfF]{1,2}(?=['\"])")
LAYOUT_CHARACTERS = str.maketrans("", "", " \t\n\r\f\v(),'\"\\")
CODE_LINE = re.compile(r"^[ \t]*[^\s#]", re.MULTILINE)
MINIMUM_CODE_LINES = 3


@dataclass(frozen=True)
class TextBlock:
    path: str
    line: int
    key: str


def without_docstring(body: str) -> str:
    docstring = DOCSTRING.match(body)
    return body if docstring is None else body[docstring.end() :]


def layout_free(body: str) -> str:
    return COMMENT_OR_STRING_PREFIX.sub("", body).translate(LAYOUT_CHARACTERS)


def text_blocks(path: str, text: str) -> Iterator[TextBlock]:
    line, position = 1, 0
    for definition in DEFINITION.finditer(text):
        line += text.count("\n", position, definition.start())
        position = definition.start()
        body = without_docstring(definition.group("body"))
        if len(CODE_LINE.findall(body)) >= MINIMUM_CODE_LINES:
            yield TextBlock(path, line, layout_free(body))


def repeated_blocks(blocks: list[TextBlock]) -> list[TextBlock]:
    counts = Counter(block.key for block in blocks)
    return [block for block in blocks if counts[block.key] > 1]
