import json
from typing import NoReturn

import pytest

from pristine.cli.main import main
from pristine.services import osv_scanner
from tests.conftest import audit_recording, json_object, run_cli


@pytest.mark.parametrize("arguments", [("audit", "--help"), ("--version",)], ids=["audit-help", "version"])
def test_light_commands_never_call_native_lookup_provision_or_download(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], arguments: tuple[str, ...]
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("light command called a native boundary")

    for boundary in (
        "shutil.which",
        "pristine.services.native_tools.resolver.NativeToolResolver.resolve_tool",
        "pristine.services.native_tools.artifacts.download_artifact",
    ):
        monkeypatch.setattr(boundary, forbidden)
    with pytest.raises(SystemExit) as exit_info:
        main(list(arguments))
    assert exit_info.value.code == 0
    assert capsys.readouterr().err == ""


def test_audit_help_runs_without_parser_packages() -> None:
    exit_code, stdout, stderr = run_cli("audit", "--help")
    assert (exit_code, stderr) == (0, "")
    output = " ".join(stdout.split())
    assert "usage: pristine audit [-h] [--json] [--max N] PATH" in output
    assert "Before finishing, review your change against every review rule it touches." in output


@pytest.mark.parametrize(
    "arguments",
    [[], ["first.lock", "second.lock"], [".", "--max", "0"], [".", "--max", "invalid"]],
)
def test_audit_requires_one_path_and_positive_limit(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["audit", *arguments])
    assert exit_info.value.code == 2


@pytest.mark.parametrize("extracted_packages", [None, 0, 3])
def test_native_extraction_count_must_match_reported_evidence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    extracted_packages: int | None,
) -> None:
    result = osv_scanner.ScannerResult(
        audit_recording("vulnerable"), 1, None, "/fixtures/vulnerable/uv.lock", extracted_packages
    )
    monkeypatch.setattr(osv_scanner, "scan_lockfile", lambda _: result)
    assert main(["audit", "uv.lock", "--json", "--max", "1"]) == 3
    document = json_object(json.loads(capsys.readouterr().out))
    assert document["verification_status"] == "incomplete"
    assert document["problems"] == ["native extraction count contradicts its package evidence"]
    assert json_object(document["summary"])["advisory_records"] == 4
