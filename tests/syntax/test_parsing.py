from pristine.syntax.calls import calls_of
from pristine.syntax.parsing import all_nodes, parse_file


def test_native_lazy_imports_parse_without_rewriting_literals() -> None:
    source = (
        "lazy import json as data\n"
        "lazy from pathlib import Path as InputPath\n"
        'literal = """lazy import os\n'
        'lazy from os import path"""\n'
    )
    parsed = parse_file("orders.py", source, "python")
    statements = [
        node for node in parsed.root.named_children if node.type in {"import_statement", "import_from_statement"}
    ]
    literal = next(node for node in parsed.root.named_children if node.type == "assignment")
    assert parsed.root.has_error is False
    assert [(node.type, node.start_point) for node in statements] == [
        ("import_statement", (0, 5)),
        ("import_from_statement", (1, 5)),
    ]
    assert parsed.comments == []
    assert literal.text == b'literal = """lazy import os\nlazy from os import path"""'
    assert parsed.text == source


def test_traversal_helpers_accept_parsed_files_and_subtrees() -> None:
    parsed = parse_file("orders.py", "def send_order(order):\n    return print(order)\n", "python")
    expected_nodes = [
        "module",
        "function_definition",
        "identifier",
        "parameters",
        "identifier",
        "block",
        "return_statement",
        "call",
        "identifier",
        "argument_list",
        "identifier",
    ]
    assert [node.type for node in parsed.nodes] == expected_nodes
    assert [node.type for node in all_nodes(parsed)] == expected_nodes
    assert [node.type for node in all_nodes(parsed.nodes[1])] == expected_nodes[1:]
    assert [
        (node.type, callee, [argument.type for argument in arguments])
        for node, callee, arguments in calls_of(parsed, "call")
    ] == [("call", "print", ["identifier"])]
