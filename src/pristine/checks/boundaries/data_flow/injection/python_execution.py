from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.boundaries.data_flow.injection.constructed import Injection
from pristine.checks.boundaries.data_flow.injection.python_values import is_trusted
from pristine.syntax.calls import calls_of
from pristine.syntax.parsing import node_text
from pristine.syntax.python_calls import import_bindings, keyword_values, positional_arguments, qualified_callee

SHELL_FUNCTIONS = frozenset(
    {"os.system", "os.popen", "subprocess.getoutput", "subprocess.getstatusoutput"}
    | {"asyncio.create_subprocess_shell"}
)
SUBPROCESS_PREFIX = "subprocess."
SHELL_KEYWORD = "shell"
EVALUATING_BUILTINS = frozenset({"eval", "exec"})
UNSAFE_DESERIALIZERS = frozenset({"pickle.load", "pickle.loads", "yaml.unsafe_load", "yaml.unsafe_load_all"})
LOADER_DESERIALIZERS = frozenset({"yaml.load", "yaml.load_all"})
LOADER_KEYWORD = "Loader"
UNSAFE_LOADERS = frozenset({"Loader", "FullLoader", "UnsafeLoader", "CLoader", "CFullLoader", "CUnsafeLoader"})
SHELL_FIX = "pass an argument list without a shell"
EVAL_FIX = "parse the value into data, such as with ast.literal_eval or json.loads"
DESERIALIZER_FIX = "load a data format such as JSON, or yaml.safe_load"


def runs_shell(qualified: str, arguments: list[Node]) -> bool:
    if qualified in SHELL_FUNCTIONS:
        return True
    shell = keyword_values(arguments).get(SHELL_KEYWORD)
    return qualified.startswith(SUBPROCESS_PREFIX) and shell is not None and node_text(shell) == "True"


def has_unsafe_loader(arguments: list[Node]) -> bool:
    positional = positional_arguments(arguments)
    loader = keyword_values(arguments).get(LOADER_KEYWORD) or (positional[1] if len(positional) > 1 else None)
    return loader is None or (node_text(loader) or "").rsplit(".", 1)[-1] in UNSAFE_LOADERS


def call_injection(callee: str, qualified: str, arguments: list[Node]) -> str | None:
    command = next(iter(positional_arguments(arguments)), None)
    is_dynamic = command is not None and not is_trusted(command)
    if is_dynamic and runs_shell(qualified, arguments):
        return f"'{callee}' runs a shell command built from non-literal values; {SHELL_FIX}"
    if is_dynamic and callee in EVALUATING_BUILTINS and not qualified:
        return f"'{callee}' evaluates a non-literal value as code; {EVAL_FIX}"
    if qualified in UNSAFE_DESERIALIZERS or (qualified in LOADER_DESERIALIZERS and has_unsafe_loader(arguments)):
        return f"'{callee}' can construct arbitrary objects from its input; {DESERIALIZER_FIX}"
    return None


def scan_execution(root: Node) -> Iterator[Injection]:
    bindings = import_bindings(root)
    for node, callee, arguments in calls_of(root, "call"):
        message = call_injection(callee, qualified_callee(callee, bindings) or "", arguments)
        if message is not None:
            yield Injection(node, message)
