from pathlib import Path

import pytest

from pristine.services.native_tools import resolver
from pristine.services.native_tools.resolver import NativeToolUnavailable, resolve_tool


class ResolvedTool:
    def resolve_tool(self, name: str) -> str:
        return "/unused/" + name


def test_relative_home_never_places_cache_in_the_working_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: Path("relative-home"))
    monkeypatch.setattr(resolver, "NativeToolResolver", lambda *_args: ResolvedTool())
    with pytest.raises(NativeToolUnavailable):
        resolve_tool("osv-scanner")


def test_unavailable_home_is_an_owned_provisioning_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable_home() -> Path:
        raise RuntimeError("home directory is unavailable")

    monkeypatch.setattr(Path, "home", unavailable_home)
    with pytest.raises(NativeToolUnavailable):
        resolve_tool("osv-scanner")
