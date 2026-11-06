from collections.abc import Callable, Iterator

from tree_sitter import Node

from pristine.checks.injection.constructed import is_constant_reference, is_escaping_callee, is_placeholder_name
from pristine.registration import registering
from pristine.syntax.parsing import node_text
from pristine.syntax.python_strings import interpolations
from pristine.syntax.syntax_kinds import COMPREHENSION_KINDS

LITERAL_KINDS = frozenset({"integer", "float", "true", "false", "none"})
COLLECTION_KINDS = frozenset({"list", "tuple", "set", "parenthesized_expression"})
LOOP_KIND = "for_statement"
LOOP_CLAUSE_KIND = "for_in_clause"
JOIN_METHOD = "join"
ARGUMENT_LIST_KIND = "argument_list"
REPEAT_OPERATOR = "*"

_TRUST_RULES: dict[str, Callable[[Node], bool]] = {}


def is_trusted(node: Node | None) -> bool:
    rule = None if node is None else _TRUST_RULES.get(node.type)
    return node is not None and (node.type in LITERAL_KINDS or (rule is not None and rule(node)))


@registering(_TRUST_RULES, "string", "concatenated_string")
def is_literal_text(node: Node) -> bool:
    return all(map(is_trusted, interpolations(node)))


@registering(_TRUST_RULES, *COLLECTION_KINDS)
def is_literal_collection(node: Node) -> bool:
    return all(map(is_trusted, node.named_children))


@registering(_TRUST_RULES, *COMPREHENSION_KINDS)
def is_literal_comprehension(node: Node) -> bool:
    return is_trusted(node.child_by_field_name("body"))


@registering(_TRUST_RULES, "subscript")
def is_constant_lookup(node: Node) -> bool:
    return is_trusted(node.child_by_field_name("value"))


@registering(_TRUST_RULES, "attribute")
def is_constant_attribute(node: Node) -> bool:
    return is_constant_reference(node_text(node) or "")


@registering(_TRUST_RULES, "identifier")
def is_constant_name(node: Node) -> bool:
    name = node_text(node) or ""
    sources = (loop.child_by_field_name("right") for loop in enclosing_loops(node) if loop_variable(loop) == name)
    outside_sources = (source for source in sources if source is not None and not encloses(source, node))
    return is_constant_reference(name) or is_placeholder_name(name) or any(map(is_trusted, outside_sources))


def encloses(outer: Node, inner: Node) -> bool:
    return outer.start_byte <= inner.start_byte and inner.end_byte <= outer.end_byte


@registering(_TRUST_RULES, "binary_operator")
def is_repeated_literal(node: Node) -> bool:
    operands = [node.child_by_field_name("left"), node.child_by_field_name("right")]
    is_repetition = node_text(node.child_by_field_name("operator")) == REPEAT_OPERATOR
    return is_repetition and any(
        operand is not None and operand.type == "list" and is_trusted(operand) for operand in operands
    )


@registering(_TRUST_RULES, "call")
def is_escaping_or_literal_join(node: Node) -> bool:
    function = node.child_by_field_name("function")
    arguments = node.child_by_field_name("arguments")
    if function is None or arguments is None:
        return False
    is_join = function.type == "attribute" and node_text(function.child_by_field_name("attribute")) == JOIN_METHOD
    values = arguments.named_children if arguments.type == ARGUMENT_LIST_KIND else [arguments]
    is_literal_join = is_join and is_trusted(function.child_by_field_name("object")) and all(map(is_trusted, values))
    return is_escaping_callee(node_text(function) or "") or is_literal_join


def loop_variable(loop: Node) -> str | None:
    return node_text(loop.child_by_field_name("left"))


def enclosing_loops(node: Node) -> Iterator[Node]:
    ancestor = node.parent
    while ancestor is not None:
        if ancestor.type == LOOP_KIND:
            yield ancestor
        clauses = ancestor.named_children if ancestor.type in COMPREHENSION_KINDS else []
        yield from (clause for clause in clauses if clause.type == LOOP_CLAUSE_KIND)
        ancestor = ancestor.parent
