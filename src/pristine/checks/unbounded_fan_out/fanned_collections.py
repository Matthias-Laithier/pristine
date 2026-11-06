import re
from collections.abc import Iterator

from tree_sitter import Node

from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import all_nodes, node_text
from pristine.syntax.syntax_kinds import FUNCTION_KINDS

TRANSPARENT_WRAPPERS = frozenset({"enumerate", "sorted", "reversed", "list", "tuple", "set"})
LOOP_CLAUSE_KINDS = frozenset({"for_statement", "for_in_clause"})
NAME_SEGMENT = re.compile(r"\w+")
NAMED_COLLECTION = re.compile(r"[A-Za-z_][\w.]*(\.(items|keys|values)\(\))?")
MAPPING_VIEWS = frozenset({"items", "keys", "values"})
BOUNDED_SEGMENT = re.compile(r"[A-Z]\w*|\w*(batch|chunk|wave|window|page|limit|capped)\w*|range")
BOUNDED_SOURCE = re.compile(r"batch|chunk|page|limit|\[:", re.IGNORECASE)
DATA_NOUNS = (
    "ids|records|rows|items|documents|docs|files|messages|emails|users|urls|links|entries|objects|blobs"
    "|events|requests|jobs|runs|members|customers|accounts|orders|invoices|summaries|credentials|images"
    "|paths|queries|prompts|samples|cases|questions|comments|notifications|conversations|tickets|repos|repositories"
    "|workspaces|organizations|projects|datasets|payloads|uploads|attachments|contacts|hits"
)
DATA_COLLECTION = re.compile(rf"(\w+_)?({DATA_NOUNS})(_list)?", re.IGNORECASE)


def collection_of(iterable: Node) -> Node:
    if iterable.type != "call" or callee_of(iterable) not in TRANSPARENT_WRAPPERS:
        return iterable
    arguments = iterable.child_by_field_name("arguments")
    inner = None if arguments is None or not arguments.named_children else arguments.named_children[0]
    return iterable if inner is None else collection_of(inner)


def loop_iterables(loop: Node) -> list[Node]:
    if loop.type == "call":
        arguments = loop.child_by_field_name("arguments")
        return [] if arguments is None else arguments.named_children[1:]
    clauses = [loop] if loop.type == "for_statement" else loop.named_children
    found = (clause.child_by_field_name("right") for clause in clauses if clause.type in LOOP_CLAUSE_KINDS)
    return [collection_of(iterable) for iterable in found if iterable is not None]


def loop_variables(loop: Node) -> set[str]:
    clauses = [loop] if loop.type == "for_statement" else loop.named_children
    targets = (clause.child_by_field_name("left") for clause in clauses if clause.type in LOOP_CLAUSE_KINDS)
    return {node_text(name) or "" for target in targets if target is not None for name in identifiers(target)}


def identifiers(node: Node) -> Iterator[Node]:
    return (child for child in all_nodes(node) if child.type == "identifier")


def has_bounded_source(loop: Node) -> bool:
    scope = loop.parent
    while scope is not None and scope.type not in FUNCTION_KINDS:
        scope = scope.parent
    return scope is not None and BOUNDED_SOURCE.search(node_text(scope) or "") is not None


def is_unbounded_data(iterable: Node, loop: Node) -> bool:
    text = node_text(iterable) or ""
    segments = NAME_SEGMENT.findall(text)
    if NAMED_COLLECTION.fullmatch(text) is None:
        return False
    if any(BOUNDED_SEGMENT.fullmatch(segment) for segment in segments):
        return False
    named = [segment for segment in segments if segment not in MAPPING_VIEWS] or segments
    return DATA_COLLECTION.fullmatch(named[-1]) is not None and not has_bounded_source(loop)


def unbounded_collection(loop: Node) -> Node | None:
    return next((iterable for iterable in loop_iterables(loop) if is_unbounded_data(iterable, loop)), None)
