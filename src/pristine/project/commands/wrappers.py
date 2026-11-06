from pristine.project.commands.wrapper_options import WRAPPERS, Wrapper

OPTION_PREFIX = "-"
VALUE_SEPARATOR = "="
RUN_COMMAND = "run"


def wrapper_option_arity(specification: Wrapper, argument: str) -> int | None:
    name = argument.partition(VALUE_SEPARATOR)[0]
    if name == RUN_COMMAND and specification.consumes_run:
        return 1
    if name in specification.flags:
        return 1
    if name in specification.options:
        return 2
    return None


def wrapper_option_argument_count(specification: Wrapper, argument: str) -> int | None:
    name = argument.partition(VALUE_SEPARATOR)[0]
    if VALUE_SEPARATOR in argument:
        return 1 if name in specification.options else None
    arity = wrapper_option_arity(specification, name)
    if arity is None and not argument.startswith(OPTION_PREFIX):
        return 0
    return arity


def wrapper_child(wrapper: str, arguments: list[str]) -> list[str] | None:
    specification = WRAPPERS[wrapper]
    index = 0
    while index < len(arguments):
        count = wrapper_option_argument_count(specification, arguments[index])
        if count == 0:
            return arguments[index:]
        if count is None or index + count > len(arguments):
            return None
        index += count
    return None
