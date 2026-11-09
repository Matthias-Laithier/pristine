import tomllib
from enum import StrEnum
from urllib.parse import urlsplit

from pristine.project.commands.shell import valid_options
from pristine.project.commands.tool_arguments import option, option_values
from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import table

CARGO_CONFIG = ".cargo/audit.toml"
CARGO_SECTIONS = frozenset({"database", "yanked", "advisories", "target", "output"})
CARGO_FLAGS = frozenset({"-n", "--no-fetch", "--no-yanked", "--stale", "-q", "--quiet", "--json"})
CARGO_VALUES = frozenset(
    {
        "-d",
        "--db",
        "-f",
        "--file",
        "-u",
        "--url",
        "-c",
        "--color",
        "-D",
        "--deny",
        "--ignore",
        "--target-arch",
        "--target-os",
        "--format",
    }
)


class AuditNetwork(StrEnum):
    NETWORK = "network"
    LOCAL = "local"
    UNVERIFIED = "unverified"


def cargo_settings(project: Project) -> dict[str, object] | None:
    if not project.reader.is_local_file(CARGO_CONFIG):
        return {}
    text = project.reader.text(CARGO_CONFIG)
    if text is None:
        return None
    try:
        config = dict[str, object](tomllib.loads(text))
    except ValueError as error:
        project.reader.reject(CARGO_CONFIG, f"Cargo audit configuration is invalid TOML ({error})")
        return None
    malformed = any(key in config and not isinstance(config[key], dict) for key in CARGO_SECTIONS)
    if malformed:
        project.reader.reject(CARGO_CONFIG, "Cargo audit configuration sections must be tables")
        return None
    return config


def cargo_network(project: Project, arguments: list[str]) -> AuditNetwork:
    if not arguments or arguments[0] != "audit" or not valid_options(arguments[1:], CARGO_FLAGS, CARGO_VALUES):
        return AuditNetwork.UNVERIFIED
    config = cargo_settings(project)
    if config is None:
        return AuditNetwork.UNVERIFIED
    database, yanked = table(config, "database"), table(config, "yanked")
    settings = (database.get("fetch", True), yanked.get("enabled", True), yanked.get("update_index", True))
    if any(not isinstance(value, bool) for value in settings):
        project.reader.reject(CARGO_CONFIG, "Cargo audit fetch and yanked settings must be booleans")
        return AuditNetwork.UNVERIFIED
    fetch = settings[0] and not option("--no-fetch", "-n")(arguments)
    update = settings[1] and settings[2] and not option("--no-yanked")(arguments)
    urls = option_values(arguments, "--url", "-u")
    url = urls[-1] if urls else database.get("url", "https://github.com/RustSec/advisory-db.git")
    if fetch:
        return AuditNetwork.NETWORK if update or (isinstance(url, str) and remote_url(url)) else AuditNetwork.UNVERIFIED
    paths = option_values(arguments, "--file", "-f")
    path = paths[-1] if paths else "Cargo.lock"
    return AuditNetwork.LOCAL if not update and project.reader.is_local_file(path) else AuditNetwork.UNVERIFIED


def network_audit(project: Project, name: str, arguments: list[str]) -> AuditNetwork:
    if name == "cargo":
        return cargo_network(project, arguments)
    if name == "govulncheck":
        databases = option_values(arguments, "-db", "--db")
        database = databases[-1] if databases else "https://vuln.go.dev"
        return AuditNetwork.NETWORK if remote_url(database) else AuditNetwork.UNVERIFIED
    return AuditNetwork.NETWORK


def remote_url(value: str) -> bool:
    try:
        return urlsplit(value).scheme in {"http", "https", "ssh"}
    except ValueError:
        return False
