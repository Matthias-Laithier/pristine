from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from itertools import chain

lazy from tree_sitter import Node, Tree

type SyntaxNode = Node
type SyntaxTree = Tree

IF_KINDS = frozenset({"if_statement"})

ELSE_CONTAINERS = frozenset({"else_clause", "else"})

CONTROL_KINDS = frozenset(
    {
        "for_statement",
        "for_in_statement",
        "while_statement",
        "do_statement",
        "try_statement",
        "with_statement",
        "match_statement",
        "switch_statement",
    }
)

ANONYMOUS_FUNCTION_KINDS = frozenset(
    {
        "lambda",
        "arrow_function",
        "function_expression",
    }
)

COMPREHENSION_KINDS = frozenset(
    {"list_comprehension", "set_comprehension", "dictionary_comprehension", "generator_expression"}
)

LEVEL_KINDS = IF_KINDS | CONTROL_KINDS | ANONYMOUS_FUNCTION_KINDS | COMPREHENSION_KINDS

NAMED_FUNCTION_KINDS = frozenset(
    {
        "function_definition",
        "function_declaration",
        "generator_function_declaration",
        "method_definition",
    }
)

FUNCTION_KINDS = NAMED_FUNCTION_KINDS | ANONYMOUS_FUNCTION_KINDS

NESTED_SCOPE_KINDS = FUNCTION_KINDS | {"class_definition"}

ASYNC_KINDS = frozenset({"function_definition", "for_statement", "with_statement"})

CALL_KINDS = frozenset({"call", "call_expression"})

COMMENT_KINDS = frozenset({"comment", "line_comment", "block_comment"})

DOCUMENTATION_PREFIXES = ("///", "//!", "/**", "/*!")

DOCSTRING_CONTAINERS = frozenset({"module", "block"})

DOCSTRING_LANGUAGES = frozenset({"python"})

NAME_BINDING_KINDS = frozenset(
    {
        "variable_declarator",
        "assignment",
        "assignment_expression",
        "pair",
        "public_field_definition",
        "field_definition",
    }
)


@dataclass(frozen=True)
class FunctionSpan:
    name: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class CommentText:
    line: int
    text: str
    is_documentation: bool


@dataclass(frozen=True)
class ParsedFile:
    path: str
    language: str
    text: str
    tree: SyntaxTree
    nodes: tuple[SyntaxNode, ...]
    functions: list[FunctionSpan]
    comments: list[CommentText]
    derived: dict[object, object] = field(default_factory=dict, init=False, repr=False, compare=False)

    @property
    def root(self) -> Node:
        return self.tree.root_node

    @cached_property
    def positions_by_type(self) -> dict[str, list[int]]:
        positions: dict[str, list[int]] = {}
        for position, node in enumerate(self.nodes):
            positions.setdefault(node.type, []).append(position)
        return positions

    def nodes_of(self, *kinds: str) -> list[SyntaxNode]:
        groups = [self.positions_by_type[kind] for kind in set(kinds) if kind in self.positions_by_type]
        positions = groups[0] if len(groups) == 1 else sorted(chain.from_iterable(groups))
        return [self.nodes[position] for position in positions]

    def shared[T](self, kind: type[T], compute: Callable[[ParsedFile], T]) -> T:
        found = self.derived.get(compute)
        if isinstance(found, kind):
            return found
        value = compute(self)
        self.derived[compute] = value
        return value
