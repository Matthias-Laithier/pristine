lazy from tree_sitter import Node

CLASS_KINDS = frozenset({"class_declaration", "abstract_class_declaration", "class"})
FIELD_KINDS = frozenset({"public_field_definition", "field_definition"})
MEMBER_KINDS = FIELD_KINDS | {"method_definition"}


def eager_children(node: Node) -> list[Node] | None:
    if node.type in CLASS_KINDS:
        return [child for child in node.named_children if child.type in {"class_heritage", "class_body", "decorator"}]
    if node.type not in MEMBER_KINDS:
        return None
    name = node.child_by_field_name("name")
    children = [name] if name is not None and name.type == "computed_property_name" else []
    children.extend(child for child in node.named_children if child.type == "decorator")
    value = node.child_by_field_name("value")
    if node.type in FIELD_KINDS and any(child.type == "static" for child in node.children) and value is not None:
        children.append(value)
    return children
