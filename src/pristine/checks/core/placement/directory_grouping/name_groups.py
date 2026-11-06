import re
from collections import Counter
from pathlib import PurePosixPath

WORD_BOUNDARY = re.compile(r"[_.\-\s()\[\]]+|(?<=[a-z0-9])(?=[A-Z])")
PLURAL_ENDING = "s"
MIN_PREFIX_LENGTH = 3
GENERIC_PREFIXES = frozenset(
    {"get", "list", "set", "update", "delete", "create", "post", "put", "patch", "use", "read", "write", "send"}
    | {"open", "show", "notify", "receive", "sync", "backfill", "migrate", "fetch", "load", "save", "build", "make"}
    | {"run", "handle", "has", "can", "add", "remove", "async", "with", "from", "base", "abstract", "generate"}
    | {"parse", "format", "validate", "check", "compute", "calculate", "render", "convert", "transform", "map"}
    | {"apply", "enable", "disable", "mark", "bump", "new", "custom", "default", "internal", "public", "private"}
    | {"test", "mock", "fake", "stub", "ask", "cancel", "approve", "restore", "register", "resolve", "start", "stop"}
    | {"init", "setup", "upload", "download", "export", "import", "process", "execute", "submit", "toggle"}
    | {"select", "edit", "reset", "clear", "refresh", "insert", "upsert", "find", "fix", "the", "all", "app", "main"}
)


def words(name: str) -> list[str]:
    return [word.lower() for word in WORD_BOUNDARY.split(name) if word]


def name_prefix(path: PurePosixPath) -> str:
    head = words(path.name)
    return head[0] if head else ""


def folder_themes(directory: PurePosixPath) -> set[str]:
    return {word for folder in directory.parts for word in words(folder)}


def is_group_prefix(prefix: str, themes: set[str]) -> bool:
    is_word = len(prefix) >= MIN_PREFIX_LENGTH and prefix.isalpha()
    forms = {prefix, prefix + PLURAL_ENDING, prefix.removesuffix(PLURAL_ENDING)}
    return is_word and forms.isdisjoint(GENERIC_PREFIXES) and forms.isdisjoint(themes)


def folded_plurals(counts: Counter[str]) -> Counter[str]:
    folded = Counter[str]()
    for prefix, count in counts.items():
        singular = prefix.removesuffix(PLURAL_ENDING)
        folded[singular if singular in counts else prefix] += count
    return folded


def prefix_groups(directory: PurePosixPath, files: list[PurePosixPath], minimum_size: int) -> dict[str, int]:
    themes = folder_themes(directory)
    counts = Counter(prefix for path in files if is_group_prefix(prefix := name_prefix(path), themes))
    return {prefix: count for prefix, count in folded_plurals(counts).most_common() if count >= minimum_size}
