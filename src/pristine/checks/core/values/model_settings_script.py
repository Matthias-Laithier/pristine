import re
from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.core.values.model_settings_bindings import (
    ModelBindings,
    literal_value,
    model_bindings,
    model_client,
    unwrapped,
)
from pristine.syntax.parsing import ParsedFile, node_text

SAMPLING_DEFAULTS = {"temperature": 0.0, "top_p": 1.0, "topP": 1.0}
MODEL_NAME = re.compile(
    r"gpt|claude|mistral|gemini|llama|codestral|devstral|ministral|magistral|pixtral|voxtral", re.IGNORECASE
)


def options(call: Node) -> dict[str, Node]:
    arguments = call.child_by_field_name("arguments")
    first = None if arguments is None or not arguments.named_children else unwrapped(arguments.named_children[0])
    pairs = {
        (node_text(entry.child_by_field_name("key")) or "").strip("\"'"): value
        for entry in ([] if first is None or first.type != "object" else first.named_children)
        if entry.type == "pair" and (value := entry.child_by_field_name("value")) is not None
    }
    pairs.update(
        (node_text(entry) or "", entry)
        for entry in ([] if first is None or first.type != "object" else first.named_children)
        if entry.type == "shorthand_property_identifier"
    )
    return pairs


def is_literal_model(value: Node, *, is_client: bool) -> bool:
    text = (node_text(value) or "").strip("\"'`")
    literal = value.type == "string" or (
        value.type == "template_string"
        and not any(child.type == "template_substitution" for child in value.named_children)
    )
    return literal and bool(text) and (is_client or MODEL_NAME.search(text) is not None or "/" in text)


def tuned_number(value: Node, neutral: float) -> bool:
    if value.type not in {"number", "unary_expression"}:
        return False
    try:
        return float((node_text(value) or "").replace("_", "")) != neutral
    except ValueError:
        return False


def call_settings(call: Node, bindings: ModelBindings) -> Iterator[tuple[str, Node]]:
    values = options(call)
    is_client = model_client(call, bindings)
    model = values.get("model")
    names_model = model is not None and is_literal_model(literal_value(model, bindings), is_client=is_client)
    if names_model:
        yield "model", model
    for name, neutral in SAMPLING_DEFAULTS.items():
        value = values.get(name)
        if (is_client or names_model) and value is not None and tuned_number(literal_value(value, bindings), neutral):
            yield name, value


def hardcoded_settings(parsed: ParsedFile) -> Iterator[tuple[str, Node]]:
    bindings = model_bindings(parsed)
    for call in parsed.nodes_of("call_expression"):
        yield from call_settings(call, bindings)
