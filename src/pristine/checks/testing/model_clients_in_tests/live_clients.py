from dataclasses import dataclass


@dataclass(frozen=True)
class LiveClient:
    line: int
    key: str | None


def is_within(module: str, packages: tuple[str, ...], separator: str) -> bool:
    return any(module == package or module.startswith(package + separator) for package in packages)


def key_label(key: str | None) -> str:
    return "an API key" if key is None else f"the {key} key"


def all_environment_reads(reads: list[tuple[bool, str | None]]) -> tuple[bool, str | None]:
    is_read = bool(reads) and all(is_environment for is_environment, _ in reads)
    return is_read, next((key for _, key in reads if key is not None), None)
