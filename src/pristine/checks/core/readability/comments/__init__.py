from pristine.checks.core.readability.comments.directives import is_machine_read
from pristine.checks.core.readability.comments.docstrings import machine_read_docstring_lines
from pristine.checks.core.readability.comments.script_metadata import script_metadata_lines
from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import CommentText, ParsedFile

RULE_ID = "CR-3"
PREVIEW_LENGTH = 60
DOC_TEXT_HINT = "allowed only on units a framework or published reference generator reads (CR-3 exceptions)"


def preview(text: str) -> str:
    return " ".join(text.split())[:PREVIEW_LENGTH]


def comment_finding(path: str, comment: CommentText) -> Finding:
    if comment.is_documentation:
        message = f"documentation text '{preview(comment.text)}' is {DOC_TEXT_HINT}"
    else:
        message = f"comment '{preview(comment.text)}'; make the code say it, then delete the comment"
    return Finding(path, comment.line, RULE_ID, Severity.ERROR, message)


def check_comments(parsed: ParsedFile) -> list[Finding]:
    docstring_lines = machine_read_docstring_lines(parsed)
    metadata_lines = script_metadata_lines(parsed)
    return [
        comment_finding(parsed.path, comment)
        for comment in parsed.comments
        if not is_machine_read(parsed.path, comment)
        and comment.line not in metadata_lines
        and not (comment.is_documentation and comment.line in docstring_lines)
    ]


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="No Comments Except Machine-Read Text",
    summary=(
        "Every comment, doc comment, and docstring. Shebangs and comments that start with a toolchain directive, "
        "such as noqa, type: ignore, eslint-disable, or //go:build, are allowed, and so are Python docstrings "
        "of functions under a framework decorator that publishes them, such as an MCP tool or a FastAPI route, "
        "module docstrings the module reads through __doc__, PEP 723 script metadata blocks, and JSDoc blocks "
        "of only type tags in JavaScript."
    ),
    run=check_comments,
)
