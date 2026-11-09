from pathlib import Path

from pristine.services.native_tools.resolver import NativeToolUnavailable


def gitleaks_without_leaks(root: Path) -> str:
    del root
    return "[]"


def unavailable_native_tool(_: str) -> str:
    raise NativeToolUnavailable("native tool provisioning is unavailable")
