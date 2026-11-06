import posixpath

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


def strict_setting(project: Project, path: str, visited: frozenset[str]) -> bool | None:
    if path in visited:
        raise UnverifiedConfigError(path, f"the {EXTENDS} chain of {path} is circular")
    document = read_json_config(project, path)
    strict = table(document, "compilerOptions").get(STRICT_OPTION)
    if isinstance(strict, bool):
        return strict
    bases = (located(project, path, local_extension(path, name)) for name in reversed(extended_names(document)))
    settings = (strict_setting(project, base, visited | {path}) for base in bases)
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
    lax = (path for path in checked_configs(project) if strict_setting(project, path, frozenset()) is not True)
    return next((Shortfall(path, TYPESCRIPT_FIX) for path in lax), None)


TYPESCRIPT = Probe("TypeScript", typescript_shortfall)
TYPESCRIPT_PROBES = {"tsc": TYPESCRIPT, "vue-tsc": TYPESCRIPT, "tsgo": TYPESCRIPT}
