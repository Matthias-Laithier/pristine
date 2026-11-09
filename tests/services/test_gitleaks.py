import json
from pathlib import Path

import pytest

from pristine.services import gitleaks
from pristine.services.gitleaks import SecretScanFailed, scan_paths
from pristine.services.native_tools.processes import ProcessResult


@pytest.fixture
def secret_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    return ["settings.json"]


@pytest.mark.parametrize("field,value", [("StartLine", True), ("StartLine", -1), ("SymlinkFile", [])])
def test_invalid_native_leak_identity_is_not_a_verified_secret_scan(
    secret_paths: list[str], monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    leak = {"SymlinkFile": "settings.json", "StartLine": 1, "RuleID": "test_token", field: value}
    output = json.dumps([leak])
    monkeypatch.setattr(gitleaks, "run_gitleaks", lambda _: output)
    with pytest.raises(SecretScanFailed, match="known file, line, and rule"):
        scan_paths(secret_paths)


@pytest.mark.parametrize("output", ['[{"number": ' + "1" * 5000 + "}]", "[" * 1100])
def test_unrepresentable_native_json_is_a_scan_failure(
    secret_paths: list[str], monkeypatch: pytest.MonkeyPatch, output: str
) -> None:
    monkeypatch.setattr(gitleaks, "run_gitleaks", lambda _: output)
    with pytest.raises(SecretScanFailed, match="not JSON"):
        scan_paths(secret_paths)


@pytest.mark.parametrize(
    "result",
    [
        ProcessResult(b"[]", b"skipping symlink; private registry credential", 0, None),
        ProcessResult(b"[]", b"private registry credential", 3, None),
        ProcessResult(b"[]", b"private registry credential", -9, "native tool timed out"),
        ProcessResult(b"\xff", b"", 0, None),
    ],
)
def test_native_process_failure_or_invalid_encoding_never_becomes_clean(
    secret_paths: list[str], monkeypatch: pytest.MonkeyPatch, result: ProcessResult
) -> None:
    monkeypatch.setattr(gitleaks, "resolve_tool", lambda _: "/unused/gitleaks")
    monkeypatch.setattr(gitleaks, "run_process", lambda *_, **__: result)
    with pytest.raises(SecretScanFailed) as failure:
        scan_paths(secret_paths)
    assert "private registry credential" not in str(failure.value)
