lazy from tree_sitter import Node

from pristine.syntax.parsing import ParsedFile, node_text, unwrapped

SCRIPT_LANGUAGES = frozenset({"javascript", "typescript", "tsx"})
CLASS_KINDS = frozenset({"class_declaration", "abstract_class_declaration"})


def module_classes(parsed: ParsedFile) -> dict[str, Node]:
    definitions = map(unwrapped, parsed.root.named_children)
    return {node_text(node.child_by_field_name("name")) or "": node for node in definitions if node.type in CLASS_KINDS}


def heritage(node: Node) -> Node | None:
    return next((child for child in node.named_children if child.type == "class_heritage"), None)


def base_name(node: Node) -> str | None:
    holder = heritage(node)
    if holder is None:
        return None
    clauses = [child for child in holder.named_children if child.type in {"extends_clause", "identifier"}]
    if len(clauses) != 1:
        return None
    clause = clauses[0]
    value = clause.child_by_field_name("value")
    if clause.type == "extends_clause" and value is not None and value.type == "identifier":
        return node_text(value)
    if clause.type == "identifier":
        return node_text(clause)
    return None


def members(node: Node) -> list[Node]:
    body = node.child_by_field_name("body")
    return [] if body is None else [child for child in body.named_children if child.type != "comment"]


def statements(method: Node) -> list[Node]:
    body = method.child_by_field_name("body")
    return [] if body is None else [child for child in body.named_children if child.type != "comment"]


def plain_header(node: Node) -> bool:
    return (
        node.type == "class_declaration"
        and heritage(node) is None
        and node.child_by_field_name("type_parameters") is None
        and not any(child.type == "decorator" for child in node.named_children)
        and not (node.parent is not None and any(child.type == "decorator" for child in node.parent.named_children))
    )


def ordinary_method(node: Node) -> bool:
    name = node.child_by_field_name("name")
    excluded = {"static", "get", "set", "decorator", "accessibility_modifier", "abstract"}
    return (
        node.type == "method_definition"
        and name is not None
        and name.type == "property_identifier"
        and node_text(name) != "constructor"
        and not any(child.type in excluded for child in node.children)
    )
