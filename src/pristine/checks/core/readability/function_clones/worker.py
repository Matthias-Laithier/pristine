import hashlib
import json
import sys
from pathlib import Path

lazy from tree_sitter import Node

from pristine.checks.core.readability.function_clones.bodies import MINIMUM_STATEMENTS
from pristine.reports.findings import Finding, Severity
from pristine.reports.outcome_lines import encoded_outcome
from pristine.reports.outcomes import Checked, Outcome, Unchecked
from pristine.services.grammars import GrammarError, language_for
from pristine.syntax.nodes import FUNCTION_KINDS
from pristine.syntax.parsing import all_nodes, function_name, line_of, node_text, parse_file
from pristine.syntax.python_scopes import own_nodes

FUNCTIONS = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_expression",
        "arrow_function",
        "method_definition",
        "generator_function",
    }
)
STATEMENTS = frozenset({"lexical_declaration", "variable_declaration"})
IGNORED = frozenset({"comment", ";"})


def shape(node: Node) -> object:
    children = [shape(child) for child in node.children if child.type not in IGNORED]
    return [node.type, children] if children else [node.type, node_text(node)]


def candidate(path: str, function: Node) -> Finding | None:
    body = function.child_by_field_name("body")
    if body is None or body.type != "statement_block":
        return None
    nodes = list(own_nodes(body, FUNCTION_KINDS | {"class_declaration", "class"}))
    count = sum(node.type.endswith("_statement") or node.type in STATEMENTS for node in nodes)
    if count < MINIMUM_STATEMENTS:
        return None
    digest = hashlib.sha256(json.dumps(shape(body), ensure_ascii=False).encode()).hexdigest()
    payload = json.dumps({"name": function_name(function), "shape": digest})
    return Finding(path, line_of(function), "CR-5", Severity.WARNING, payload)


def inspect(path: str) -> Outcome:
    try:
        text = Path(path).read_text(errors="replace")
        language = language_for(Path(path))
        if language not in {"javascript", "typescript", "tsx"}:
            return Unchecked("clone extraction has no JS/TS grammar for this path")
        parsed = parse_file(path, text, language)
    except (OSError, GrammarError, RecursionError) as error:
        return Unchecked(f"clone extraction failed: {error}")
    if parsed.root.has_error:
        return Unchecked("clone extraction could not parse JS/TS without syntax recovery")
    records = (candidate(path, function) for function in all_nodes(parsed) if function.type in FUNCTIONS)
    return Checked([record for record in records if record is not None])


def main() -> None:
    for line in sys.stdin:
        path: object = json.loads(line)
        if not isinstance(path, str):
            raise TypeError("worker input must be a JSON string")
        sys.stdout.write(encoded_outcome(path, inspect(path)))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
