import json
from dataclasses import dataclass
from typing import NoReturn

__all__ = [
    "MalformedNativeRecord",
    "PackageIdentity",
    "array",
    "decode_output",
    "fields",
    "fixed_versions",
    "object_record",
    "text",
    "texts",
]

MAX_JSON_CHARACTERS = 8 * 1024 * 1024


@dataclass(frozen=True)
class PackageIdentity:
    package: str
    version: str
    ecosystem: str


class MalformedNativeRecord(ValueError):
    pass


def decode_output(output: str) -> dict[str, object]:
    if len(output) > MAX_JSON_CHARACTERS:
        raise MalformedNativeRecord("native JSON exceeds the size limit")
    return object_record(
        json.loads(output, object_pairs_hook=_unique_fields, parse_constant=_invalid_number), "native output"
    )


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document = dict(pairs)
    if len(document) != len(pairs):
        raise MalformedNativeRecord("native JSON has duplicate fields")
    return document


def _invalid_number(_: str) -> NoReturn:
    raise MalformedNativeRecord("native JSON has a nonfinite number")


def object_record(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MalformedNativeRecord(f"{context} is not an object")
    return dict[str, object](value)


def array(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise MalformedNativeRecord(f"{context} is not an array")
    return list[object](value)


def text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        raise MalformedNativeRecord(f"{context} is not nonempty printable text")
    return value


def texts(value: object, context: str) -> tuple[str, ...]:
    return tuple(text(entry, context) for entry in array(value, context))


def fields(document: dict[str, object], allowed: tuple[str, ...], context: str) -> None:
    if document.keys() - set(allowed):
        raise MalformedNativeRecord(f"{context} has unsupported fields")


def fixed_versions(advisory: dict[str, object], package: PackageIdentity) -> tuple[str, ...]:
    releases: list[str] = []
    for value in array(advisory.get("affected", []), "advisory affected"):
        affected = object_record(value, "affected entry")
        identity = object_record(affected.get("package"), "affected package")
        name = text(identity.get("name"), "affected package name")
        ecosystem = text(identity.get("ecosystem"), "affected ecosystem")
        if name != package.package or ecosystem != package.ecosystem:
            continue
        releases.extend(_range_releases(affected))
    return tuple(dict.fromkeys(releases))


def _range_releases(affected: dict[str, object]) -> list[str]:
    releases: list[str] = []
    for value in array(affected.get("ranges", []), "affected ranges"):
        interval = object_record(value, "affected range")
        if text(interval.get("type"), "range type") not in ("SEMVER", "ECOSYSTEM", "GIT"):
            raise MalformedNativeRecord("unsupported affected range type")
        releases.extend(_event_releases(interval))
    return releases


def _event_releases(interval: dict[str, object]) -> list[str]:
    releases: list[str] = []
    for value in array(interval.get("events"), "range events"):
        event = object_record(value, "range event")
        fields(event, ("introduced", "fixed", "last_affected", "limit"), "range event")
        if len(event) != 1:
            raise MalformedNativeRecord("range event must have exactly one boundary")
        boundary = text(next(iter(event.values())), "range boundary")
        if "fixed" in event and interval["type"] != "GIT":
            releases.append(boundary)
    return releases
