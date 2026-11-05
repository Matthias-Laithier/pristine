import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

RULES_DIRECTORY = Path(__file__).parent.parent / "src" / "pristine" / "rules"
RULE_DOCUMENT_PATTERN = "*-*.md"
TITLE_PATTERN = re.compile(r"^# (?P<rule_id>[A-Z]+-\d+) ")
SECTION_PATTERN = re.compile(r"^## (?P<kind>Bad|Good)(?::\s*(?P<variant>.+))?\s*$")
OTHER_SECTION_PATTERN = re.compile(r"^## ")
FILENAME_PATTERN = re.compile(r"^`(?P<name>[^`]+)`:\s*$")
FENCE_PATTERN = re.compile(r"^```(?P<language>\S*)\s*$")
TREE_INDENT = 4
GENERATED_STEM = "example"
TEST_FUNCTION_PATTERN = re.compile(r"^def test_", re.MULTILINE)
EXTENSIONS = {
    "python": ".py",
    "typescript": ".ts",
    "javascript": ".js",
    "toml": ".toml",
    "yaml": ".yaml",
}
MAKEFILE_LANGUAGE = "make"
MAKEFILE_NAME = "Makefile"
TREE_LANGUAGE = ""
SHARED_SECTION = (None, "")


class ExampleKind(StrEnum):
    BAD = "bad"
    GOOD = "good"


@dataclass(frozen=True)
class CodeBlock:
    language: str
    content: str
    filename: str | None


@dataclass(frozen=True)
class RuleExample:
    rule_id: str
    kind: ExampleKind
    variant: str
    files: dict[str, str]

    @property
    def example_id(self) -> str:
        suffix = f":{self.variant}" if self.variant else ""
        return f"{self.rule_id}-{self.kind}{suffix}"


def tree_paths(tree: str) -> list[str]:
    directories: list[str] = []
    files: list[str] = []
    for line in tree.splitlines():
        if not line.strip():
            continue
        depth = (len(line) - len(line.lstrip(" "))) // TREE_INDENT
        name = line.strip()
        del directories[depth:]
        if name.endswith("/"):
            directories.append(name.rstrip("/"))
        else:
            files.append("/".join([*directories, name]))
    return files


def _generated_name(block: CodeBlock, position: int) -> str:
    if block.language == MAKEFILE_LANGUAGE:
        return MAKEFILE_NAME
    stem = f"{GENERATED_STEM}_{position}"
    if block.language == "python" and TEST_FUNCTION_PATTERN.search(block.content):
        return f"tests/test_{stem}.py"
    return stem + EXTENSIONS[block.language]


def example_files(blocks: list[CodeBlock]) -> dict[str, str]:
    files: dict[str, str] = {}
    for position, block in enumerate(blocks, start=1):
        if block.language == TREE_LANGUAGE:
            files.update(dict.fromkeys(tree_paths(block.content), ""))
            continue
        files[block.filename or _generated_name(block, position)] = block.content
    return files


def _read_blocks(lines: list[str]) -> list[tuple[int, CodeBlock]]:
    blocks: list[tuple[int, CodeBlock]] = []
    end = -1
    for index, line in enumerate(lines):
        fence = FENCE_PATTERN.match(line) if index > end else None
        if fence:
            end = lines.index("```", index + 1)
            content = "\n".join(lines[index + 1 : end]) + "\n"
            blocks.append((index, CodeBlock(fence["language"], content, _filename_before(lines, index))))
    return blocks


def _filename_before(lines: list[str], fence_index: int) -> str | None:
    previous = fence_index - 1
    while previous >= 0 and not lines[previous].strip():
        previous -= 1
    match = FILENAME_PATTERN.match(lines[previous]) if previous >= 0 else None
    return match["name"] if match else None


def _section_at(lines: list[str], line_index: int) -> tuple[ExampleKind | None, str] | None:
    for heading in reversed(lines[:line_index]):
        section = SECTION_PATTERN.match(heading)
        if section:
            return ExampleKind(section["kind"].lower()), section["variant"] or ""
        if OTHER_SECTION_PATTERN.match(heading):
            return None
    return SHARED_SECTION


def parse_rule_document(text: str) -> list[RuleExample]:
    lines = text.splitlines()
    title = TITLE_PATTERN.match(lines[0])
    if title is None:
        raise ValueError(f"rule document without an ID title: {lines[0]!r}")
    shared: list[CodeBlock] = []
    sections: dict[tuple[ExampleKind, str], list[CodeBlock]] = {}
    for line_index, block in _read_blocks(lines):
        section = _section_at(lines, line_index)
        if section == SHARED_SECTION:
            shared.append(block)
        elif section is not None and section[0] is not None:
            sections.setdefault((section[0], section[1]), []).append(block)
    return [
        RuleExample(title["rule_id"], kind, variant, example_files([*shared, *blocks]))
        for (kind, variant), blocks in sections.items()
    ]


def rule_examples() -> list[RuleExample]:
    return [
        example
        for document in sorted(RULES_DIRECTORY.glob(RULE_DOCUMENT_PATTERN))
        for example in parse_rule_document(document.read_text())
    ]
