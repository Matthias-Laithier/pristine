import configparser
from dataclasses import dataclass

from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import table
from pristine.project.repository.tools import Ecosystem
from pristine.project.strictness.strictness import (
    Arguments,
    Probe,
    Shortfall,
    StrictnessCheck,
    UnverifiedConfigError,
    passes_strict_flag,
    read_json_config,
)

MYPY = "mypy"
MYPY_INI_FILES = ("mypy.ini", ".mypy.ini")
SETUP_CFG = "setup.cfg"
STRICT_OPTION = "strict"
MYPY_FIX = "set strict = true in its configuration or pass --strict in make check"
PYRIGHT_CONFIG = "pyrightconfig.json"
MODE_KEY = "typeCheckingMode"
STRICT_MODE = "strict"
PYRIGHT_FIX = f'set {MODE_KEY} to "{STRICT_MODE}"'


@dataclass(frozen=True)
class PyrightFlavor:
    sections: tuple[str, ...]
    strict_modes: frozenset[str]
    default_is_strict: bool


def ini_strict(project: Project, path: str) -> bool | None:
    text = project.reader.text(path)
    if text is None:
        raise UnverifiedConfigError(path, f"{path} is unreadable")
    parser = configparser.ConfigParser()
    try:
        parser.read_string(text)
        return parser.getboolean(MYPY, STRICT_OPTION, fallback=False) if parser.has_section(MYPY) else None
    except (configparser.Error, ValueError) as error:
        raise UnverifiedConfigError(path, f"{path} cannot be parsed ({error})") from error


def mypy_configuration(project: Project) -> tuple[str, bool]:
    ini_file = next((name for name in MYPY_INI_FILES if name in project.entries), None)
    if ini_file:
        return ini_file, bool(ini_strict(project, ini_file))
    manifest = project.root_manifest(Ecosystem.PYTHON)
    if manifest and MYPY in manifest.settings:
        return manifest.path, table(manifest.settings, MYPY).get(STRICT_OPTION) is True
    setup_strict = ini_strict(project, SETUP_CFG) if SETUP_CFG in project.entries else None
    if setup_strict is not None:
        return SETUP_CFG, setup_strict
    return manifest.path if manifest else SETUP_CFG, False


def mypy_shortfall(project: Project, calls: Arguments) -> Shortfall | None:
    if passes_strict_flag(calls):
        return None
    path, strict = mypy_configuration(project)
    return None if strict else Shortfall(path, MYPY_FIX)


def pyright_mode(project: Project, flavor: PyrightFlavor) -> tuple[str, object]:
    if PYRIGHT_CONFIG in project.entries:
        return PYRIGHT_CONFIG, read_json_config(project, PYRIGHT_CONFIG).get(MODE_KEY)
    manifest = project.root_manifest(Ecosystem.PYTHON)
    settings = manifest.settings if manifest else {}
    section = next((table(settings, name) for name in flavor.sections if name in settings), {})
    return manifest.path if manifest else PYRIGHT_CONFIG, section.get(MODE_KEY)


def pyright_check(flavor: PyrightFlavor) -> StrictnessCheck:
    def check(project: Project, _: Arguments) -> Shortfall | None:
        path, mode = pyright_mode(project, flavor)
        strict = mode in flavor.strict_modes if mode is not None else flavor.default_is_strict
        return None if strict else Shortfall(path, PYRIGHT_FIX)

    return check


PYRIGHT = PyrightFlavor(("pyright",), frozenset({STRICT_MODE}), default_is_strict=False)
BASEDPYRIGHT = PyrightFlavor(
    ("basedpyright", "pyright"), frozenset({STRICT_MODE, "recommended", "all"}), default_is_strict=True
)
PYTHON_PROBES = {
    MYPY: Probe(MYPY, mypy_shortfall),
    "pyright": Probe("pyright", pyright_check(PYRIGHT)),
    "basedpyright": Probe("basedpyright", pyright_check(BASEDPYRIGHT)),
}
