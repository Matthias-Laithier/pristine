lazy from tree_sitter import Node

from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import node_text
from pristine.syntax.python_scopes import (
    assigned_values,
    enclosing_functions,
    module_root,
    named_parameters,
)

SIZE_KINDS = frozenset({"integer"})
SIZE_TYPE = "int"
SIZE_CLAMPS = frozenset({"min", "max"})
ANNOTATED_FORMS = frozenset({"Annotated", "typing.Annotated"})
TIMEOUT_ARGUMENTS = frozenset(
    {"timeout", "deadline", "connect_timeout", "read_timeout", "write_timeout", "pool_timeout"}
)


def passes_size(call: Node) -> bool:
    arguments = call.child_by_field_name("arguments")
    values = [] if arguments is None else arguments.named_children
    unwrapped = (
        value.child_by_field_name("value") or value
        for value in values
        if node_text(value.child_by_field_name("name")) not in TIMEOUT_ARGUMENTS
    )
    return any(is_size(value) for value in unwrapped)


def is_size(value: Node) -> bool:
    if value.type in SIZE_KINDS:
        return True
    if value.type == "call":
        return callee_of(value) in SIZE_CLAMPS and passes_size(value)
    if value.type != "identifier":
        return False
    name = node_text(value) or ""
    scopes = (named_parameters(function) for function in enclosing_functions(value))
    parameter = next((parameters[name] for parameters in scopes if name in parameters), None)
    if parameter is not None:
        return is_size_parameter(parameter)
    module_values = assigned_values(module_root(value), name)
    return bool(module_values) and all(module_value.type in SIZE_KINDS for module_value in module_values)


def is_size_parameter(parameter: Node) -> bool:
    default = parameter.child_by_field_name("value")
    return is_size_type(parameter.child_by_field_name("type")) or (default is not None and default.type in SIZE_KINDS)


def is_size_type(annotation: Node | None) -> bool:
    declared = None if annotation is None or not annotation.named_children else annotation.named_children[0]
    if declared is None or declared.type != "generic_type":
        return declared is not None and node_text(declared) == SIZE_TYPE
    holder = declared.named_children[0] if declared.named_children else None
    arguments = declared.named_children[-1].named_children if len(declared.named_children) > 1 else []
    is_annotated = holder is not None and node_text(holder) in ANNOTATED_FORMS
    return is_annotated and bool(arguments) and is_size_type(arguments[0])
