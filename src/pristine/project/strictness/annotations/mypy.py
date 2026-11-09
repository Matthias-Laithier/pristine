import configparser
import re

from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import table
from pristine.project.repository.tools import Ecosystem
from pristine.project.strictness.annotations.options import code_overrides, codes, has_option
from pristine.project.strictness.annotations.scope import verify_source_scope
from pristine.project.strictness.python_strictness import mypy_configuration
from pristine.project.strictness.strictness import UnverifiedConfigError

ERROR_CODE = "no-untyped-def"
UNSUPPORTED = frozenset({"--config-file", "--exclude", "--exclude-gitignore", "--shadow-file"})
NON_GATING = frozenset({"--help", "-h", "--version", "-V"})
ERROR_CODE_PATTERN = re.compile(r"[a-z]+(?:-[a-z]+)*")


def ini_settings(project: Project, path: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    text = project.reader.text(path)
    if text is None:
        raise UnverifiedConfigError(path, f"{path} is unreadable")
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error as error:
        raise UnverifiedConfigError(path, f"{path} cannot be parsed ({error})") from error
    settings = dict[str, object](parser["mypy"]) if parser.has_section("mypy") else {}
    overrides = [dict[str, object](parser[name]) for name in parser.sections() if name.startswith("mypy-")]
    return settings, overrides


def configuration(project: Project) -> tuple[str, dict[str, object], list[dict[str, object]]]:
    path, _ = mypy_configuration(project)
    if path.endswith(".toml"):
        return toml_configuration(project, path)
    settings, overrides = ini_settings(project, path)
    return path, settings, overrides


def toml_configuration(project: Project, path: str) -> tuple[str, dict[str, object], list[dict[str, object]]]:
    manifest = project.root_manifest(Ecosystem.PYTHON)
    settings = table(manifest.settings, "mypy") if manifest else {}
    overrides = settings.get("overrides", [])
    if not isinstance(overrides, list) or any(not isinstance(override, dict) for override in overrides):
        raise UnverifiedConfigError(path, "mypy module overrides cannot be parsed")
    return path, settings, [dict[str, object](override) for override in overrides if isinstance(override, dict)]


def boolean(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return configparser.ConfigParser.BOOLEAN_STATES.get(value.lower())
    return None


def disabled(settings: dict[str, object]) -> bool:
    ignored = codes(settings.get("disable_error_code"))
    enabled = codes(settings.get("enable_error_code"))
    return (
        boolean(settings.get("disallow_untyped_defs")) is False
        or boolean(settings.get("ignore_errors")) is True
        or ERROR_CODE in set(ignored) - set(enabled)
        or settings.get("follow_imports") == "skip"
    )


def mypy_annotations(project: Project, arguments: list[str]) -> str | None:
    if has_option(arguments, NON_GATING):
        return "mypy is invoked without checking definitions"
    if has_option(arguments, UNSUPPORTED):
        raise UnverifiedConfigError("Makefile", "mypy configuration or source overrides need review")
    verify_source_scope(project, arguments, ruff=False)
    path, settings, overrides = configuration(project)
    error_codes = codes(settings.get("disable_error_code")) + codes(settings.get("enable_error_code"))
    if any(ERROR_CODE_PATTERN.fullmatch(code) is None for code in error_codes):
        raise UnverifiedConfigError(path, "mypy error-code settings are not statically readable error codes")
    if any(disabled(override) for override in overrides):
        raise UnverifiedConfigError(path, "mypy module overrides disable annotation enforcement")
    if settings.get("exclude") or boolean(settings.get("exclude_gitignore")) is True:
        raise UnverifiedConfigError(path, "mypy file exclusions need review")
    effective = dict(settings)
    if "--strict" in arguments:
        effective["disallow_untyped_defs"] = True
    if "--disallow-untyped-defs" in arguments:
        effective["disallow_untyped_defs"] = True
    if "--allow-untyped-defs" in arguments:
        effective["disallow_untyped_defs"] = False
    overrides_by_code = code_overrides(arguments, ("disable-error-code", "enable-error-code"))
    for name, value in overrides_by_code.items():
        key = name.replace("-", "_")
        effective[key] = codes(settings.get(key)) + codes(value)
    strict = "--strict" in arguments or boolean(settings.get("strict")) is True
    if disabled(effective) or not (strict or boolean(effective.get("disallow_untyped_defs")) is True):
        return "mypy does not enforce untyped definitions (no-untyped-def)"
    return None
