import json
from collections.abc import Callable
from pathlib import Path

import pytest

from pristine.cli.main import main
from pristine.services import osv_scanner
from tests.conftest import json_list, json_object, json_text

NATIVE_FIXTURES = Path(__file__).parents[2] / "assets" / "audit"

type NativeScanner = Callable[[str, int | None, str | None, str | None], list[Path]]


@pytest.fixture
def native_scanner(monkeypatch: pytest.MonkeyPatch) -> NativeScanner:
    def install(output: str, returncode: int | None, problem: str | None, target_path: str | None) -> list[Path]:
        calls: list[Path] = []
        packages = 2 if target_path == "/fixtures/vulnerable/uv.lock" else 1
        result = osv_scanner.ScannerResult(
            output, "private native diagnostic", returncode, problem, target_path, packages
        )

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
        document["results"] = [*sources, *sources]
        return json.dumps(document)
    return (NATIVE_FIXTURES / f"{sample}.json").read_text(encoding="utf-8")


def test_audit_exposes_native_findings_and_source_evidence(
    native_scanner: NativeScanner, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = native_scanner(native_output("vulnerable"), 1, None, "/fixtures/vulnerable/uv.lock")
    assert main(["audit", "uv.lock", "--json"]) == 1
    document = json_object(json.loads(capsys.readouterr().out))
    assert calls == [Path("uv.lock")]
    assert document["sources"] == [
        {"path": "/fixtures/vulnerable/uv.lock", "source_type": "lockfile", "package_count": 2}
    ]
    findings = [json_object(value) for value in json_list(document["findings"])]
    by_id = {json_text(finding["advisory_id"]): finding for finding in findings}
    assert set(by_id) == {"PYSEC-2026-1805", "PYSEC-2026-1806", "GHSA-7gcm-g887-7qv7", "GHSA-8qvm-5x2c-j2w7"}
    finding = by_id["GHSA-8qvm-5x2c-j2w7"]
    assert set(json_list(finding.pop("aliases"))) == {"CVE-2025-4565", "PYSEC-2026-1806"}
    assert finding == {
        "source_path": "/fixtures/vulnerable/uv.lock",
        "source_type": "lockfile",
        "package": "protobuf",
        "version": "4.25.5",
        "ecosystem": "PyPI",
        "advisory_id": "GHSA-8qvm-5x2c-j2w7",
        "fixed_versions": ["4.25.8", "5.29.5", "6.31.1"],
    }


@pytest.mark.parametrize("json_output", [False, True])
def test_audit_caps_only_findings_and_keeps_full_counts(
    native_scanner: NativeScanner, capsys: pytest.CaptureFixture[str], json_output: bool
) -> None:
    native_scanner(native_output("vulnerable"), 1, None, "/fixtures/vulnerable/uv.lock")
    assert main(["audit", "uv.lock", "--max", "1", *(["--json"] if json_output else [])]) == 1
    output = capsys.readouterr().out
    if json_output:
        document = json_object(json.loads(output))
        assert len(json_list(document["findings"])) == 1
        assert document["summary"] == {
            "advisory_records": 4,
            "packages": 2,
            "sources": 1,
            "verification_failures": 0,
            "omitted": 3,
        }
    else:
        assert "... 3 findings omitted" in output
        assert "summary: 4 advisory records, 2 packages, 1 sources, 0 verification failures" in output
        assert "/fixtures/vulnerable/uv.lock (lockfile)\n  2 packages; 4 advisory records" in output
        assert "  PyPI protobuf@4.25.5\n    - PYSEC-2026-1805;" in output
        assert output.count("/fixtures/vulnerable/uv.lock") == 1
        assert output.count("protobuf@4.25.5") == 1
        assert output.count("not upgrade recommendations") == 1
        assert "fixed releases: 5.29.6, 6.33.5" in output


@pytest.mark.parametrize("json_output", [False, True])
def test_audit_clean_evidence_still_limits_certainty_and_requires_rule_review(
    native_scanner: NativeScanner, capsys: pytest.CaptureFixture[str], json_output: bool
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
    assert "read every rule in full with 'pristine rule all' before coding" in output
    assert "review your change against every rule, including checked rules" in output
    assert "A clean report does not establish full rule compliance." in output


@pytest.mark.parametrize("json_output", [False, True])
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
    json_output: bool,
) -> None:
    sample, returncode, problem, target_path = case
    native_scanner(native_output(sample), returncode, problem, target_path)
    assert main(["audit", "uv.lock", "--max", "1", *(["--json"] if json_output else [])]) == 3
    output = capsys.readouterr().out
    if json_output:
        document = json_object(json.loads(output))
        assert document["verification_status"] == "incomplete"
        assert json_list(document["problems"])
        assert json_object(document["summary"])["advisory_records"] == (4 if sample == "vulnerable" else 0)
        assert len(json_list(document["findings"])) == (1 if sample == "vulnerable" else 0)
    else:
        assert "verification: incomplete" in output
        assert "No known advisory matches" not in output
        assert "verify: " in output
        if sample == "vulnerable":
            assert "summary: 4 advisory records" in output
    assert "private native diagnostic" not in output
    assert "review your change against every rule, including checked rules" in output


def test_audit_marks_absent_fixed_versions_as_not_reported(
    native_scanner: NativeScanner, capsys: pytest.CaptureFixture[str]
) -> None:
    document = json_object(json.loads(native_output("vulnerable")))
    source = json_object(json_list(document["results"])[0])
    packages = json_list(source["packages"])
    package = json_object(packages[1])
    package["vulnerabilities"] = [
        {**json_object(value), "affected": []} for value in json_list(package["vulnerabilities"])
    ]
    source["packages"] = [packages[0], package]
    document["results"] = [source]
    native_scanner(json.dumps(document), 1, None, "/fixtures/vulnerable/uv.lock")
    assert main(["audit", "uv.lock"]) == 1
    assert capsys.readouterr().out.count("fixed releases: not reported") == 4
