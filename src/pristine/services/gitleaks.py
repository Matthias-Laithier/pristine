import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pristine.services.native_tools.processes import run_process
from pristine.services.native_tools.resolver import NativeToolUnavailable, resolve_tool

GITLEAKS_TIMEOUT_SECONDS = 300
GITLEAKS_OUTPUT_LIMIT_IN_BYTES = 8 * 1024 * 1024
PROJECT_CONFIG_NAME = ".gitleaks.toml"
SCAN_OPTIONS = (
    "--follow-symlinks",
    "--no-banner",
    "--redact",
    "--report-format",
    "json",
    "--report-path",
    "-",
    "--exit-code",
    "0",
    "--log-level",
    "error",
)


class SecretScanFailed(Exception):
    pass


@dataclass(frozen=True)
class Leak:
    path: str
    line: int
    rule_id: str


def mirror_paths(paths: list[str], root: Path) -> dict[str, str]:
    links = {}
    for shown in paths:
        link = shown.lstrip("/")
        (root / link).parent.mkdir(parents=True, exist_ok=True)
        (root / link).symlink_to(Path(shown).absolute())
        links[link] = shown
    return links


def scan_command(gitleaks: str) -> list[str]:
    command = [gitleaks, "dir", ".", *SCAN_OPTIONS]
    project_config = Path.cwd() / PROJECT_CONFIG_NAME
    return [*command, "--config", str(project_config)] if project_config.is_file() else command


def run_gitleaks(root: Path) -> str:
    try:
        gitleaks = resolve_tool("gitleaks")
    except NativeToolUnavailable as error:
        raise SecretScanFailed(str(error)) from error
    result = run_process(
        scan_command(gitleaks),
        root,
        timeout_in_seconds=GITLEAKS_TIMEOUT_SECONDS,
        output_limit_in_bytes=GITLEAKS_OUTPUT_LIMIT_IN_BYTES,
    )
    if result.problem is not None:
        raise SecretScanFailed(result.problem.replace("native tool", "gitleaks"))
    if result.returncode != 0:
        raise SecretScanFailed(f"gitleaks exited with code {result.returncode}")
    if result.stderr.strip():
        raise SecretScanFailed("gitleaks reported errors or skipped inputs")
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SecretScanFailed("gitleaks printed a report that is not UTF-8") from error


def parsed_leak(entry: object, links: dict[str, str]) -> Leak:
    if not isinstance(entry, dict):
        raise SecretScanFailed("gitleaks reported a leak that is not an object")
    link, line, rule_id = entry.get("SymlinkFile"), entry.get("StartLine"), entry.get("RuleID")
    if (
        not isinstance(link, str)
        or link not in links
        or type(line) is not int
        or line < 0
        or not isinstance(rule_id, str)
    ):
        raise SecretScanFailed("gitleaks reported a leak without a known file, line, and rule")
    return Leak(links[link], line, rule_id)


def parsed_report(report: str, links: dict[str, str]) -> list[Leak]:
    try:
        entries = json.loads(report)
    except (ValueError, RecursionError) as error:
        raise SecretScanFailed("gitleaks printed a report that is not JSON") from error
    if not isinstance(entries, list):
        raise SecretScanFailed("gitleaks printed a report that is not a list of leaks")
    return [parsed_leak(entry, links) for entry in entries]


def scan_paths(paths: list[str]) -> list[Leak]:
    if not paths:
        return []
    try:
        with tempfile.TemporaryDirectory(prefix="pristine-gitleaks-") as directory:
            links = mirror_paths(paths, Path(directory))
            return parsed_report(run_gitleaks(Path(directory)), links)
    except OSError as error:
        raise SecretScanFailed(f"the files could not be prepared for gitleaks ({error})") from error
