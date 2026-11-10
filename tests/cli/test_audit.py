import json
from collections.abc import Callable
from pathlib import Path

import pytest

from pristine.cli.main import main
from pristine.services import osv_scanner
from tests.conftest import audit_recording, json_list, json_object, json_text

type NativeScanner = Callable[[str, int | None, str | None, str | None], list[Path]]


@pytest.fixture
def native_scanner(monkeypatch: pytest.MonkeyPatch) -> NativeScanner:
    def install(output: str, returncode: int | None, problem: str | None, target_path: str | None) -> list[Path]:
        calls: list[Path] = []
        packages = 2 if target_path == "/fixtures/vulnerable/uv.lock" else 1
        result = osv_scanner.ScannerResult(output, returncode, problem, target_path, packages)

        def scan(path: Path) -> osv_scanner.ScannerResult:
            calls.append(path)
            return result

        monkeypatch.setattr(osv_scanner, "scan_lockfile", scan)
        return calls

    return install


def native_output(sample: str) -> str:
    if sample in ("invalid-json", "empty", "unavailable"):
        return {"invalid-json": "{", "empty": '{"results": []}', "unavailable": ""}[sample]
    if sample == "duplicate":
        document = json_object(json.loads(native_output("clean")))
        sources = json_list(document["results"])
        duplicate = {**json_object(sources[0]), "packages": []}
        document["results"] = [*sources, duplicate]
        return json.dumps(document)
    return audit_recording(sample)


@pytest.mark.parametrize("limit", [None, 1])
def test_audit_json_keeps_native_findings_sources_and_uncapped_counts(
    native_scanner: NativeScanner, capsys: pytest.CaptureFixture[str], limit: int | None
) -> None:
    calls = native_scanner(native_output("vulnerable"), 1, None, "/fixtures/vulnerable/uv.lock")
    assert main(["audit", "uv.lock", "--json", *(["--max", str(limit)] if limit is not None else [])]) == 1
    document = json_object(json.loads(capsys.readouterr().out))
    assert calls == [Path("uv.lock")]
    assert document["sources"] == [
        {"path": "/fixtures/vulnerable/uv.lock", "source_type": "lockfile", "package_count": 2}
    ]
    findings = json_list(document["findings"])
    assert len(findings) == (4 if limit is None else 1)
    assert document["summary"] == {
        "advisory_records": 4,
        "packages": 2,
        "sources": 1,
        "verification_failures": 0,
        "omitted": 0 if limit is None else 3,
    }
    finding = json_object(findings[0])
    assert finding == {
        "source_path": "/fixtures/vulnerable/uv.lock",
        "source_type": "lockfile",
        "package": "protobuf",
        "version": "4.25.5",
        "ecosystem": "PyPI",
        "advisory_id": "PYSEC-2026-1805",
        "aliases": ["CVE-2026-0994", "GHSA-7gcm-g887-7qv7"],
        "fixed_versions": ["5.29.6", "6.33.5"],
    }


def test_audit_text_caps_only_findings_and_keeps_full_counts(
    native_scanner: NativeScanner, capsys: pytest.CaptureFixture[str]
) -> None:
    native_scanner(native_output("vulnerable"), 1, None, "/fixtures/vulnerable/uv.lock")
    assert main(["audit", "uv.lock", "--max", "1"]) == 1
    output = capsys.readouterr().out
    assert "... 3 findings omitted" in output
    assert "summary: 4 advisory records, 2 packages, 1 sources, 0 verification failures" in output
    assert output.count("    - ") == 1


@pytest.mark.parametrize("json_output", [False, True])
def test_audit_clean_evidence_still_limits_certainty_and_requires_rule_review(
    native_scanner: NativeScanner, capsys: pytest.CaptureFixture[str], *, json_output: bool
) -> None:
    native_scanner(native_output("clean"), 0, None, "/fixtures/clean/uv.lock")
    assert main(["audit", "uv.lock", *(["--json"] if json_output else [])]) == 0
    output = capsys.readouterr().out
    if json_output:
        document = json_object(json.loads(output))
        assert document["verification_status"] == "complete"
        assert document["findings"] == []
        assert document["summary"] == {
            "advisory_records": 0,
            "packages": 1,
            "sources": 1,
            "verification_failures": 0,
            "omitted": 0,
        }
        assert "no installed-dependency, package-origin, full-project, or exploitability assurance" in json_text(
            document["scope"]
        )
        assert "not upgrade recommendations" in json_text(document["scope"])
    else:
        assert "No known advisory matches; not proof of security." in output
    assert "review your change against every review rule it touches" in output


@pytest.mark.parametrize(
    "case",
    [
        ("unavailable", None, "scanner provisioning unavailable", None),
        ("vulnerable", 1, "scanner timed out", "/fixtures/vulnerable/uv.lock"),
        ("invalid-json", 0, None, "/fixtures/clean/uv.lock"),
        ("empty", 0, None, "/fixtures/clean/uv.lock"),
        ("vulnerable", 0, None, "/fixtures/vulnerable/uv.lock"),
        ("clean", 1, None, "/fixtures/clean/uv.lock"),
        ("clean", 0, None, "/fixtures/wrong/uv.lock"),
        ("clean", 0, None, None),
        ("duplicate", 0, None, "/fixtures/clean/uv.lock"),
    ],
)
def test_audit_gaps_and_exit_contradictions_are_incomplete_without_losing_findings(
    native_scanner: NativeScanner,
    capsys: pytest.CaptureFixture[str],
    case: tuple[str, int | None, str | None, str | None],
) -> None:
    sample, returncode, problem, target_path = case
    native_scanner(native_output(sample), returncode, problem, target_path)
    assert main(["audit", "uv.lock", "--max", "1", "--json"]) == 3
    output = capsys.readouterr().out
    document = json_object(json.loads(output))
    assert document["verification_status"] == "incomplete"
    assert json_list(document["problems"])
    assert json_object(document["summary"])["advisory_records"] == (4 if sample == "vulnerable" else 0)
    assert len(json_list(document["findings"])) == (1 if sample == "vulnerable" else 0)
    if sample == "duplicate":
        assert document["problems"] == ["native source evidence does not match the requested lockfile"]
    assert "review your change against every review rule it touches" in output


def test_audit_text_failure_retains_findings_without_claiming_a_clean_scan(
    native_scanner: NativeScanner, capsys: pytest.CaptureFixture[str]
) -> None:
    native_scanner(native_output("vulnerable"), 1, "scanner timed out", "/fixtures/vulnerable/uv.lock")
    assert main(["audit", "uv.lock", "--max", "1"]) == 3
    output = capsys.readouterr().out
    assert "verification: incomplete" in output
    assert "verify: scanner timed out" in output
    assert "summary: 4 advisory records" in output
    assert "No known advisory matches" not in output
