lazy from tree_sitter import Node

from pristine.checks.core.values.global_mutation.scopes import (
    COMPARISON_KINDS,
    SCOPE_KINDS,
    names_in,
    operator_tokens,
    scope_of,
)
from pristine.checks.core.values.global_mutation.writes import REBIND_ACTION, Mutation
from pristine.syntax.nodes import ANONYMOUS_FUNCTION_KINDS, CALL_KINDS
from pristine.syntax.parsing import node_text
from pristine.syntax.python_scopes import own_nodes

LOOKUP_METHODS = frozenset({"get", "has"})
MEMBERSHIP_OPERATORS = frozenset({"in", "not in"})
PARAMETER_FIELDS = ("name", "pattern")
PARAMETER_HOLDERS = frozenset({"typed_parameter", "list_splat_pattern", "dictionary_splat_pattern"})
REGISTRATION_KINDS = frozenset({"identifier"})


def is_lookup(node: Node, name: str) -> bool:
    if node.type in CALL_KINDS:
        callee = node.child_by_field_name("function")
        receiver = None if callee is None else callee.child_by_field_name("object")
        method = (
            None
            if callee is None
            else callee.child_by_field_name("attribute") or callee.child_by_field_name("property")
        )
        return node_text(receiver) == name and node_text(method) in LOOKUP_METHODS
    if node.type in COMPARISON_KINDS:
        return bool(MEMBERSHIP_OPERATORS & operator_tokens(node)) and node_text(node.named_children[-1]) == name
    return False


def earlier_nodes(scope: Node, mutation: Mutation) -> list[Node]:
    return [node for node in own_nodes(scope, SCOPE_KINDS) if node.start_byte < mutation.node.start_byte]


def memoizes(scope: Node, mutation: Mutation) -> bool:
    return any(is_lookup(node, mutation.name) for node in earlier_nodes(scope, mutation))


def parameter_names(scope: Node) -> set[str]:
    holder = scope.child_by_field_name("parameters") or scope.child_by_field_name("parameter")
    if holder is None:
        return set()
    if holder.type == "identifier":
        return {node_text(holder) or ""}
    named = [child.child_by_field_name(field) for child in holder.named_children for field in PARAMETER_FIELDS]
    bare = [child for child in holder.named_children if child.type == "identifier"]
    wrapped = [child.named_children[0] for child in holder.named_children if child.type in PARAMETER_HOLDERS]
    return {
        node_text(node) or "" for node in [*named, *bare, *wrapped] if node is not None and node.type == "identifier"
    }


def returned_values(scope: Node) -> list[Node]:
    body = scope.child_by_field_name("body")
    if scope.type == "arrow_function" and body is not None and body.type != "statement_block":
        return [body]
    returns = [node for node in own_nodes(scope, SCOPE_KINDS) if node.type == "return_statement"]
    return [node.named_children[0] for node in returns if node.named_children]


def hands_back(value: Node, parameter: str, kinds: frozenset[str]) -> bool:
    if value.type == "identifier":
        return "identifier" in kinds and node_text(value) == parameter
    return value.type in kinds and parameter in names_in(value)


def stores_and_returns(scope: Node, mutation: Mutation, kinds: frozenset[str]) -> bool:
    stored = names_in(mutation.node) & parameter_names(scope)
    values = returned_values(scope)
    return any(hands_back(value, parameter, kinds) for parameter in stored for value in values)


def is_registration(mutation: Mutation) -> bool:
    scope = scope_of(mutation.node)
    return scope is not None and stores_and_returns(scope, mutation, REGISTRATION_KINDS)


def is_owned_write(mutation: Mutation, scope: Node) -> bool:
    return mutation.action != REBIND_ACTION and (
        memoizes(scope, mutation) or stores_and_returns(scope, mutation, ANONYMOUS_FUNCTION_KINDS)
    )


def owned_collections(mutations: list[Mutation]) -> set[str]:
    scoped = [(mutation, scope_of(mutation.node)) for mutation in mutations]
    return {mutation.name for mutation, scope in scoped if scope is not None and is_owned_write(mutation, scope)}
