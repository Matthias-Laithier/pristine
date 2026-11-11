import re
from collections.abc import Callable
from dataclasses import dataclass, field

RECIPE_PREFIX = "\t"
RECIPE_FLAGS = "@-+ \t"
CONTINUATION = "\\"
COMMENT = "#"
ENDEF = "endef"
CONDITIONAL_DIRECTIVES = frozenset({"ifeq", "ifneq", "ifdef", "ifndef", "else", "endif"})
SPECIAL_TARGET_PREFIX = "."
PATTERN_NAME_MARKERS = ("$", "%")
ORDER_ONLY_SEPARATOR = "|"
INLINE_RECIPE_SEPARATOR = ";"
ASSIGNMENT = re.compile(r"^(?:(?:export|override|private)\s+)*([\w.\-/]+)\s*(:{1,3}=|\?=|\+=|!=|=)\s*(.*)$")
RULE = re.compile(r"^([^:=]+?)\s*::?(?!=)\s*(.*)$")
INCLUDE = re.compile(r"^-?s?include\s+(.+)$")
DEFINE = re.compile(r"^(?:(?:export|override|private)\s+)*define\b")

type Combine = Callable[[str | None, str], str]


def append_value(current: str | None, value: str) -> str:
    return value if current in (None, "") else f"{current} {value}".strip()


def keep_existing(current: str | None, value: str) -> str:
    return value if current is None else current


ASSIGNMENT_COMBINERS: dict[str, Combine] = {"+=": append_value, "?=": keep_existing}


def replace_value(_: str | None, value: str) -> str:
    return value


@dataclass
class Rule:
    path: str
    line: int
    prerequisites: list[str] = field(default_factory=list)
    recipe: list[str] = field(default_factory=list)
    ignored_error_commands: list[str] = field(default_factory=list)


@dataclass
class MakefileSyntax:
    path: str
    rules: dict[str, Rule] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)
    includes: list[str] = field(default_factory=list)
    current_rules: list[Rule] = field(default_factory=list)
    inside_define: bool = False
    special_targets: set[str] = field(default_factory=set)

    def read(self, line_number: int, line: str) -> None:
        if self.inside_define:
            self.inside_define = line.strip() != ENDEF
            return
        if line.startswith(RECIPE_PREFIX):
            self.add_recipe_line(line)
            return
        statement = line.split(COMMENT, 1)[0].strip()
        if not statement or statement.split()[0] in CONDITIONAL_DIRECTIVES:
            return
        self.current_rules = []
        self.read_statement(line_number, statement)

    def read_statement(self, line_number: int, statement: str) -> None:
        if DEFINE.match(statement):
            self.inside_define = True
        elif include := INCLUDE.match(statement):
            self.includes.extend(include[1].split())
        elif assignment := ASSIGNMENT.match(statement):
            self.assign(*assignment.groups())
        elif rule := RULE.match(statement):
            self.add_rule(line_number, rule[1].split(), rule[2])

    def assign(self, name: str, operator: str, value: str) -> None:
        combine = ASSIGNMENT_COMBINERS.get(operator, replace_value)
        self.variables[name] = combine(self.variables.get(name), value.strip())

    def add_rule(self, line_number: int, names: list[str], body: str) -> None:
        if ASSIGNMENT.match(body):
            return
        prerequisites, _, inline_recipe = body.partition(INLINE_RECIPE_SEPARATOR)
        normal_prerequisites = prerequisites.split(ORDER_ONLY_SEPARATOR)[0].split()
        self.special_targets.update(name for name in names if name.startswith(SPECIAL_TARGET_PREFIX))
        for name in filter(is_plain_target, names):
            rule = self.rules.setdefault(name, Rule(self.path, line_number))
            rule.prerequisites.extend(normal_prerequisites)
            self.current_rules.append(rule)
        if inline_recipe.strip():
            self.add_recipe_line(inline_recipe)

    def add_recipe_line(self, line: str) -> None:
        command = line.lstrip(RECIPE_FLAGS)
        ignores_errors = "-" in line[: len(line) - len(command)]
        for rule in self.current_rules:
            rule.recipe.append(command)
            if ignores_errors:
                rule.ignored_error_commands.append(command)


def is_plain_target(name: str) -> bool:
    return not name.startswith(SPECIAL_TARGET_PREFIX) and not any(marker in name for marker in PATTERN_NAME_MARKERS)


def logical_lines(text: str) -> list[tuple[int, str]]:
    joined: list[tuple[int, str]] = []
    start, parts = 0, []
    for number, raw in enumerate(text.splitlines(), start=1):
        start = start or number
        parts.append(raw.removesuffix(CONTINUATION))
        if not raw.endswith(CONTINUATION):
            joined.append((start, " ".join(parts)))
            start, parts = 0, []
    if parts:
        joined.append((start, " ".join(parts)))
    return joined


def parse_makefile(text: str, path: str) -> MakefileSyntax:
    syntax = MakefileSyntax(path)
    for line_number, line in logical_lines(text):
        syntax.read(line_number, line)
    return syntax
