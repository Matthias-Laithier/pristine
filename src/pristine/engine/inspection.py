from pathlib import Path

from pristine.checks.registry import file_checks
from pristine.files.classification import is_generated, is_minified, skip_reason
from pristine.reports.outcomes import Checked, Outcome, Skipped, Unchecked, Unsupported
from pristine.services.grammars import GrammarError, language_for
from pristine.syntax.parsing import parse_file


def run_checks(shown_path: str, text: str, language: str) -> Outcome:
    try:
        parsed = parse_file(shown_path, text, language)
    except GrammarError as error:
        return Unchecked(f"could not parse as {language}: {error}")
    if parsed.root.has_error:
        return Unchecked(f"could not parse as {language}: the parser recovered from a syntax error")
    return Checked([finding for check in file_checks() for finding in check.run(parsed)])


def inspect_file(shown_path: str) -> Outcome:
    path = Path(shown_path)
    try:
        content = path.read_bytes()
    except OSError as error:
        return Unchecked(f"could not read the file: {error.strerror}")
    reason = skip_reason(path, content)
    if reason is not None:
        return Skipped(reason)
    language = language_for(path)
    if language is None:
        return Unsupported("no grammar for this file type")
    text = content.decode(errors="replace")
    if is_generated(text) or is_minified(path, text):
        return Skipped("generated file")
    return run_checks(shown_path, text, language)
