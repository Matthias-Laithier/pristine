import re

from pristine.syntax.parsing import ParsedFile

PYTHON = "python"
SCRIPT_METADATA = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s"
    r"(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def script_metadata_lines(parsed: ParsedFile) -> set[int]:
    if parsed.language != PYTHON:
        return set()

    text = parsed.text.replace("\r\n", "\n")
    exempt_lines: set[int] = set()
    comment_lines = {comment.line for comment in parsed.comments if not comment.is_documentation}
    line = 1
    position = 0
    while position < len(text):
        match = SCRIPT_METADATA.search(text, position)
        if match is None:
            return exempt_lines
        line += text.count("\n", position, match.start())
        block_newlines = text.count("\n", match.start(), match.end())
        exempt_lines |= script_metadata_block_lines(match, line, block_newlines, comment_lines)
        line += block_newlines
        position = match.end()
    return exempt_lines


def script_metadata_block_lines(
    match: re.Match[str], line: int, block_newlines: int, comment_lines: set[int]
) -> set[int]:
    if match.group("type") != "script":
        return set()
    metadata_lines = set(range(line, line + block_newlines + 1))
    if metadata_lines <= comment_lines:
        return metadata_lines
    return set()
