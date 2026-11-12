import os
from pathlib import Path

from pristine.files.path_roles import RESULT_CACHE_DIRECTORY
from pristine.services.git import repository_root
from pristine.services.outcome_cache.files import STORE_PREFIX, prepared_store, user_secret
from pristine.services.outcome_cache.inputs import FileInputs, digest_of
from pristine.services.outcome_cache.store import OutcomeCache
from pristine.services.outcome_cache.toolchain import ToolchainUnavailable, toolchain_fingerprint

__all__ = ["CacheLocations", "OutcomeCache", "cache_locations", "open_outcome_cache"]

USER_KEY_DIRECTORY = (".cache", "pristine")

type CacheLocations = tuple[Path, Path]


def cache_locations(paths: list[Path], configured: str | None) -> CacheLocations | None:
    if configured is not None and configured != "":
        return Path(configured), Path(configured)
    try:
        key_directory = Path.home().joinpath(*USER_KEY_DIRECTORY)
        common = Path(os.path.commonpath([os.path.abspath(path) for path in paths]))
    except RuntimeError, ValueError:
        return None
    directory = common if common.is_dir() else common.parent
    return (repository_root(directory) or directory) / RESULT_CACHE_DIRECTORY, key_directory


def open_outcome_cache(locations: CacheLocations, command: tuple[str, ...]) -> OutcomeCache | None:
    root, key_directory = locations
    cwd = os.getcwd()
    try:
        store = f"{STORE_PREFIX}{digest_of(toolchain_fingerprint(), cwd, *command).hex()}"
        secret = user_secret(key_directory)
        location = prepared_store(root, store)
    except OSError, ToolchainUnavailable:
        return None
    return OutcomeCache(location, FileInputs(cwd), secret)
