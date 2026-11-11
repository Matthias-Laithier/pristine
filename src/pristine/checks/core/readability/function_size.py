lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Limit
from pristine.syntax.parsing import FunctionSpan, ParsedFile, line_of, node_text

RULE_ID = "CR-12"
FUNCTION_LINE_LIMIT = Limit(target=30, hard=50)
SINGLE_CLAUSE_KINDS = frozenset({"return_statement", "raise_statement", "expression_statement", "pass_statement"})


def is_single_clause(case: Node) -> bool:
    consequence = case.child_by_field_name("consequence")
    return (
        consequence is not None
        and consequence.named_child_count == 1
        and consequence.named_children[0].type in SINGLE_CLAUSE_KINDS
        and consequence.named_children[0].start_point.row == consequence.named_children[0].end_point.row
    )


def is_exhaustive_match_function(node: Node) -> bool:
    body = node.child_by_field_name("body")
    if body is None or body.named_child_count != 1 or body.named_children[0].type != "match_statement":
        return False
    match_body = body.named_children[0].child_by_field_name("body")
    cases = [] if match_body is None else match_body.named_children
    if not cases or any(case.type != "case_clause" or not is_single_clause(case) for case in cases):
        return False
    final_case = cases[-1]
    patterns = [child for child in final_case.named_children if child.type == "case_pattern"]
    if final_case.child_by_field_name("guard") is not None or len(patterns) != 1:
        return False
    pattern = patterns[0]
    if node_text(pattern) == "_":
        return True
    return (
        pattern.named_child_count == 1
        and pattern.named_children[0].type == "dotted_name"
        and pattern.named_children[0].named_child_count == 1
        and pattern.named_children[0].named_children[0].type == "identifier"
    )


def non_blank_line_count(lines: list[str], function: FunctionSpan) -> int:
    body = lines[function.start_line - 1 : function.end_line]
    return sum(1 for line in body if line.strip())


def check_function_size(parsed: ParsedFile) -> list[Finding]:
    lines = parsed.text.splitlines()
    exempt_lines = {
        line_of(node)
        for node in parsed.nodes
        if parsed.language == "python" and node.type == "function_definition" and is_exhaustive_match_function(node)
    }
    findings = []
    for function in parsed.functions:
        line_count = non_blank_line_count(lines, function)
        severity = FUNCTION_LINE_LIMIT.severity_for(line_count)
        if severity is None or function.start_line in exempt_lines:
            continue
        message = (
            f"function '{function.name}' has {line_count} non-blank lines "
            f"({FUNCTION_LINE_LIMIT.describe()}); extract named helpers along real jobs"
        )
        findings.append(Finding(parsed.path, function.start_line, RULE_ID, severity, message))
    return findings


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="Function Size",
    summary=(
        f"Function and method length, blank lines excluded ({FUNCTION_LINE_LIMIT.describe()}); "
        "exhaustive Python matches with one single-line clause per branch are exempt."
    ),
    run=check_function_size,
)
