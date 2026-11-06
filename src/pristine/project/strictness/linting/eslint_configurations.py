import json
from fnmatch import fnmatchcase

from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import Manifest, table
from pristine.project.strictness.strictness import UnverifiedConfigError

SUPPORTED_CONFIG = ".eslintrc.json"
PACKAGE_CONFIG = "package.json"
PACKAGE_CONFIG_KEY = "eslintConfig"
FLAT_CONFIG_PATTERN = "eslint.config.*"
UNSUPPORTED_CONFIG_MODE = "uses a configuration mode pristine does not statically support"
UNSUPPORTED_CONFIG_LOCATION = "uses a configuration location pristine does not statically support"


def read_config(project: Project, path: str) -> dict[str, object]:
    text = project.reader.text(path)
    if text is None:
        raise UnverifiedConfigError(path, f"{path} is unreadable")
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise UnverifiedConfigError(path, f"{path} is not valid JSON ({error})") from error
    if not isinstance(document, dict):
        raise UnverifiedConfigError(path, f"the top level of {path} is not a JSON object")
    return dict[str, object](document)


def config_path(project: Project) -> str:
    return SUPPORTED_CONFIG if SUPPORTED_CONFIG in project.entries else PACKAGE_CONFIG


def package_config(manifest: Manifest | None) -> dict[str, object]:
    if manifest is None:
        raise UnverifiedConfigError(PACKAGE_CONFIG, f"{PACKAGE_CONFIG} is unreadable")
    return dict[str, object](table(manifest.settings, PACKAGE_CONFIG_KEY))


def unsupported_config(project: Project, manifests: list[Manifest]) -> tuple[str, str] | None:
    flat_config_path = next((entry for entry in project.entries if fnmatchcase(entry, FLAT_CONFIG_PATTERN)), None)
    if flat_config_path is not None:
        return flat_config_path, UNSUPPORTED_CONFIG_MODE
    if SUPPORTED_CONFIG in project.entries:
        return None
    root_config_path = next((entry for entry in sorted(project.entries) if fnmatchcase(entry, ".eslintrc*")), None)
    if root_config_path is not None:
        return root_config_path, UNSUPPORTED_CONFIG_MODE
    nested_manifest = next(
        (
            manifest
            for manifest in manifests
            if manifest.path != PACKAGE_CONFIG and PACKAGE_CONFIG_KEY in manifest.settings
        ),
        None,
    )
    if nested_manifest is not None:
        return nested_manifest.path, UNSUPPORTED_CONFIG_LOCATION
    return None
