lazy from tree_sitter import Node

from pristine.checks.boundaries.execution.unbounded_fan_out.limiters import Limiters, acquires_limiter, last_segment
from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import node_text
from pristine.syntax.python_calls import qualified_callee
from pristine.syntax.python_scopes import CLASS_KIND, ancestors, defined_function, enclosing_functions, module_root

POOLED_CALLS = frozenset({"asyncio.to_thread"})
TASK_WRAPPERS = frozenset({"asyncio.create_task", "asyncio.ensure_future"})
SPAWN_METHODS = frozenset({"create_task", "start_soon"})
RECEIVER_SEPARATOR = "."


def fanned_call(element: Node, limiters: Limiters) -> Node:
    callee = callee_of(element)
    is_wrapper = qualified_callee(callee, limiters.bindings) in TASK_WRAPPERS
    is_spawn = callee.rsplit(RECEIVER_SEPARATOR, 1)[-1] in SPAWN_METHODS
    arguments = element.child_by_field_name("arguments")
    inner = None if arguments is None or not arguments.named_children else arguments.named_children[0]
    return fanned_call(inner, limiters) if (is_wrapper or is_spawn) and inner is not None else element


def coroutine_definition(reference: Node, site: Node) -> Node | None:
    name = node_text(reference) or ""
    if reference.type == "attribute":
        holder = next((scope for scope in ancestors(site) if scope.type == CLASS_KIND), None)
        name = last_segment(reference) if holder is not None else ""
        scopes = [] if holder is None else [holder]
    else:
        scopes = [*enclosing_functions(site), module_root(site)]
    definitions = (defined_function(scope, name) for scope in scopes)
    return next((definition for definition in definitions if definition is not None), None)


def is_bounded_work(element: Node, limiters: Limiters) -> bool:
    call = fanned_call(element, limiters)
    if call.type != "call":
        definition = coroutine_definition(call, element)
        return definition is not None and acquires_limiter(definition, None, limiters)
    if qualified_callee(callee_of(call), limiters.bindings) in POOLED_CALLS:
        return True
    function = call.child_by_field_name("function")
    definition = None if function is None else coroutine_definition(function, element)
    return definition is not None and acquires_limiter(definition, call, limiters)
