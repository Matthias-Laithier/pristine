import os

import pytest

from pristine.services.native_tools.resolver import NativeToolUnavailable
from tests.services.native_tools.conftest import NativeBoundary


def test_disk_failure_cleans_the_unpublished_temporary(
    native_boundary: NativeBoundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_sync(descriptor: int) -> None:
        del descriptor
        raise OSError("disk full with sensitive path")

    monkeypatch.setattr(os, "fsync", fail_sync)
    with pytest.raises(NativeToolUnavailable) as failure:
        native_boundary.resolver().resolve_tool("osv-scanner")
    assert "sensitive" not in str(failure.value)
    assert list(native_boundary.root.iterdir()) == []
