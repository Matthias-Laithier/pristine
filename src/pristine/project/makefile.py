import re
from dataclasses import dataclass

from pristine.project.makefile_syntax import Rule, parse_makefile
from pristine.project.shell import invoked_make_targets
from pristine.project.sources import SourceReader

DEFAULT_VARIABLES = {"MAKE": "make"}
VARIABLE_REFERENCE = re.compile(r"\$[({]([\w.\-]+)[)}]")
EXPANSION_DEPTH_LIMIT = 10
FAST_GATE = "check"
COMPLETE_GATE = "check-all"
INCLUDE_PATTERN_MARKERS = ("$", "*", "?", "[")


@dataclass(frozen=True)
class Makefile:
    path: str
    rules: dict[str, Rule]
    variables: dict[str, str]

    def expand(self, text: str) -> str:
        for _ in range(EXPANSION_DEPTH_LIMIT):
            expanded = VARIABLE_REFERENCE.sub(lambda match: self.variables.get(match[1], match[0]), text)
            if expanded == text:
                return expanded
            text = expanded
        return text


@dataclass(frozen=True)
class Reach:
    targets: frozenset[str]
    commands: tuple[str, ...]


def reach(makefile: Makefile, target: str) -> Reach:
    reached: set[str] = set()
    commands: list[str] = []
    pending = [target]
    while pending:
        name = pending.pop()
        if name in reached or name not in makefile.rules:
            continue
        reached.add(name)
        rule = makefile.rules[name]
        recipe = [makefile.expand(line) for line in rule.recipe]
        commands.extend(recipe)
        pending.extend(makefile.expand(" ".join(rule.prerequisites)).split())
        pending.extend(invoked for command in recipe for invoked in invoked_make_targets(command))
    return Reach(frozenset(reached), tuple(commands))


def merge_rules(rules: dict[str, Rule], additions: dict[str, Rule]) -> None:
    for name, addition in additions.items():
        existing = rules.setdefault(name, addition)
        if existing is not addition:
            existing.prerequisites.extend(addition.prerequisites)
            existing.recipe.extend(addition.recipe)


def is_followable_include(reader: SourceReader, name: str) -> bool:
    return not any(marker in name for marker in INCLUDE_PATTERN_MARKERS) and reader.is_local_file(name)


def load_makefile(reader: SourceReader, path: str) -> Makefile | None:
    rules: dict[str, Rule] = {}
    variables = dict(DEFAULT_VARIABLES)
    pending, visited = [path], set()
    while pending:
        current = pending.pop(0)
        text = None if current in visited else reader.text(current)
        visited.add(current)
        if text is None:
            continue
        syntax = parse_makefile(text, current)
        merge_rules(rules, syntax.rules)
        variables.update(syntax.variables)
        pending.extend(name for name in syntax.includes if is_followable_include(reader, name))
    return Makefile(path, rules, variables) if path in reader.checked else None
