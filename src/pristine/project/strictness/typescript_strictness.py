import posixpath

from pristine.project.commands.tool_arguments import checking, option, option_values
from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import array, table
from pristine.project.strictness.strictness import (
    Arguments,
    Probe,
    Shortfall,
    UnverifiedConfigError,
    passes_strict_flag,
    read_json_config,
)

TYPESCRIPT_CONFIG = "tsconfig.json"
LOCAL_PREFIXES = ("./", "../")
JSON_SUFFIX = ".json"
EXTENDS = "extends"
STRICT_OPTION = "strict"
TYPESCRIPT_FIX = 'set "strict": true in compilerOptions'


def local_extension(origin: str, name: str) -> str:
    if not name.startswith(LOCAL_PREFIXES):
        raise UnverifiedConfigError(origin, f"{origin} {EXTENDS} {name}, which is not a local file")
    return name


def located(project: Project, origin: str, name: str) -> str:
    target = posixpath.normpath(posixpath.join(posixpath.dirname(origin), name))
    candidates = (target, f"{target}{JSON_SUFFIX}", posixpath.join(target, TYPESCRIPT_CONFIG))
    found = next((candidate for candidate in candidates if project.reader.is_local_file(candidate)), None)
    if found is None:
        raise UnverifiedConfigError(origin, f"{origin} refers to {name}, which is not a file of the repository")
    return found


def extended_names(document: dict[str, object]) -> list[str]:
    extends = document.get(EXTENDS)
    names = [extends] if isinstance(extends, str) else array(document, EXTENDS)
    return [name for name in names if isinstance(name, str)]


def compiler_setting(project: Project, path: str, name: str, visited: frozenset[str]) -> bool | None:
    if path in visited:
        raise UnverifiedConfigError(path, f"the {EXTENDS} chain of {path} is circular")
    document = read_json_config(project, path)
    strict = table(document, "compilerOptions").get(name)
    if isinstance(strict, bool):
        return strict
    bases = (located(project, path, local_extension(path, name)) for name in reversed(extended_names(document)))
    settings = (compiler_setting(project, base, name, visited | {path}) for base in bases)
    return next((setting for setting in settings if setting is not None), None)


def checked_configs(project: Project) -> list[str]:
    document = read_json_config(project, TYPESCRIPT_CONFIG)
    paths = [reference.get("path") for reference in array(document, "references") if isinstance(reference, dict)]
    names = [path for path in paths if isinstance(path, str)]
    if document.get("files") != [] or "include" in document or not names:
        return [TYPESCRIPT_CONFIG]
    return [located(project, TYPESCRIPT_CONFIG, name) for name in names]


def typescript_shortfall(project: Project, calls: Arguments) -> Shortfall | None:
    if passes_strict_flag(calls) or TYPESCRIPT_CONFIG not in project.entries:
        return None
    lax = (
        path
        for path in checked_configs(project)
        if compiler_setting(project, path, STRICT_OPTION, frozenset()) is not True
    )
    return next((Shortfall(path, TYPESCRIPT_FIX) for path in lax), None)


TYPESCRIPT = Probe("TypeScript", typescript_shortfall)
TYPESCRIPT_PROBES = {"tsc": TYPESCRIPT, "vue-tsc": TYPESCRIPT, "tsgo": TYPESCRIPT}


def unused_typescript_shortfall(project: Project, calls: Arguments) -> Shortfall | None:
    required = ("noUnusedLocals", "noUnusedParameters")
    for arguments in calls:
        if not checking(arguments):
            continue
        paths, supplies_sources = unused_source_scope(project, arguments)
        enabled = [unused_option_enabled(project, paths, arguments, name) for name in required]
        complete = all(enabled)
        if complete and supplies_sources:
            raise UnverifiedConfigError(
                TYPESCRIPT_CONFIG,
                "explicit TypeScript source arguments require review of the complete project source scope",
            )
        if complete:
            return None
    return Shortfall(
        TYPESCRIPT_CONFIG,
        "enable noUnusedLocals and noUnusedParameters in the invoked TypeScript configuration or command; these are limited native unused-code checks",
    )


def unused_source_scope(project: Project, arguments: list[str]) -> tuple[list[str], bool]:
    if option("--project", "-p", "--build", "-b")(arguments):
        raise UnverifiedConfigError(
            TYPESCRIPT_CONFIG, "review the TypeScript unused-code checks for the explicit project or build graph"
        )
    paths = checked_configs(project) if TYPESCRIPT_CONFIG in project.entries else []
    if paths and paths != [TYPESCRIPT_CONFIG]:
        raise UnverifiedConfigError(
            TYPESCRIPT_CONFIG, "a TypeScript solution requires review of the invoked build graph"
        )
    supplies_sources = any(argument.endswith((".ts", ".tsx", ".mts", ".cts", ".js", ".jsx")) for argument in arguments)
    return ([] if supplies_sources else paths), supplies_sources


def unused_option_enabled(project: Project, paths: list[str], arguments: list[str], name: str) -> bool:
    if option(f"--{name}")(arguments):
        return "false" not in option_values(arguments, f"--{name}")
    return bool(paths) and all(compiler_setting(project, path, name, frozenset()) is True for path in paths)
