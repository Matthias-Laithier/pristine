import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

GITLEAKS_TIMEOUT_SECONDS = 300
PROJECT_CONFIG_NAME = ".gitleaks.toml"
STDERR_EXCERPT_LENGTH = 200
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
    gitleaks = shutil.which("gitleaks")
    if gitleaks is None:
        raise SecretScanFailed("gitleaks is not installed or not on PATH")
    try:
        result = subprocess.run(
            scan_command(gitleaks),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=GITLEAKS_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise SecretScanFailed(f"gitleaks timed out after {GITLEAKS_TIMEOUT_SECONDS} seconds") from error
    except (OSError, subprocess.SubprocessError) as error:
        raise SecretScanFailed(f"gitleaks could not start ({error})") from error
    if result.returncode != 0:
        excerpt = result.stderr.strip()[-STDERR_EXCERPT_LENGTH:] or "no error output"
        raise SecretScanFailed(f"gitleaks exited with code {result.returncode}: {excerpt}")
    return result.stdout


def parsed_leak(entry: object, links: dict[str, str]) -> Leak:
    if not isinstance(entry, dict):
        raise SecretScanFailed("gitleaks reported a leak that is not an object")
    link, line, rule_id = entry.get("SymlinkFile"), entry.get("StartLine"), entry.get("RuleID")
    if link not in links or not isinstance(line, int) or not isinstance(rule_id, str):
        raise SecretScanFailed("gitleaks reported a leak without a known file, line, and rule")
    return Leak(links[link], line, rule_id)


def parsed_report(report: str, links: dict[str, str]) -> list[Leak]:
    try:
        entries = json.loads(report)
    except json.JSONDecodeError as error:
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
