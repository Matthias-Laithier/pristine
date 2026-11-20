import re

from pristine.reports.findings import Finding
from pristine.syntax.nodes import CommentText, ParsedFile

PRAGMA = re.compile(r"\bpristine\s*:\s*ignore\b", re.IGNORECASE)
NEXT_LINE = 1


def comment_starts_line(comment: CommentText, lines: list[str]) -> bool:
    if comment.line > len(lines):
        return False
    first_line = comment.text.splitlines()[0].lstrip()
    return lines[comment.line - 1].lstrip().startswith(first_line)


def pragma_lines(comment: CommentText, lines: list[str]) -> set[int]:
    suppressed: set[int] = set()
    for match in PRAGMA.finditer(comment.text):
        line = comment.line + comment.text.count("\n", 0, match.start())
        suppressed.add(line)
        if comment_starts_line(comment, lines):
            suppressed.add(line + NEXT_LINE)
    return suppressed


def suppressed_lines(parsed: ParsedFile) -> set[int]:
    candidates = [
        comment for comment in parsed.comments if not comment.is_documentation and PRAGMA.search(comment.text)
    ]
    if not candidates:
        return set()
    lines = parsed.text.splitlines()
    suppressed: set[int] = set()
    for comment in candidates:
        suppressed |= pragma_lines(comment, lines)
    return suppressed


def apply_suppressions(parsed: ParsedFile, findings: list[Finding]) -> list[Finding]:
    suppressed = suppressed_lines(parsed)
    if not suppressed:
        return findings
    return [finding for finding in findings if finding.line not in suppressed]
