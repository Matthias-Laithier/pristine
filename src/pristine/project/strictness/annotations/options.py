from pristine.project.strictness.strictness import UnverifiedConfigError

UNIVERSAL_PATTERNS = frozenset({"*", "**", "**/*.py", "*.py"})


def option_values(arguments: list[str], name: str) -> list[str]:
    values = []
    for index, argument in enumerate(arguments):
        if argument.startswith(f"{name}="):
            values.append(argument.partition("=")[2])
        elif argument == name:
            values.append(following_value(arguments[index + 1 : index + 2], name))
    return values


def following_value(following: list[str], name: str) -> str:
    if not following or following[0].startswith("--"):
        raise UnverifiedConfigError("Makefile", f"{name} has no statically readable value")
    return following[0]


def codes(value: object) -> list[str]:
    if isinstance(value, str):
        return [code.strip() for code in value.split(",")]
    if isinstance(value, list):
        return [code for code in value if isinstance(code, str)]
    return []


def has_option(arguments: list[str], names: frozenset[str]) -> bool:
    return any(argument.partition("=")[0] in names for argument in arguments)


def code_overrides(arguments: list[str], names: tuple[str, ...]) -> dict[str, object]:
    return {name: codes(",".join(values)) for name in names if (values := option_values(arguments, f"--{name}"))}
