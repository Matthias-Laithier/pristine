import json

import pytest

from pristine.audit.osv_json import parse_osv_json
from tests.audit.conftest import native_output
from tests.conftest import json_object


def test_absent_output_with_a_known_failure_reports_that_failure_once() -> None:
    report = parse_osv_json("", ("scanner provisioning unavailable",))
    assert report.problems == ("scanner provisioning unavailable",)
    assert report.verification_failed
    assert report.counts["advisory_records"] == 0
    assert report.counts["verification_failures"] == 1


@pytest.mark.parametrize(
    "output",
    ["", "null", "{}", '{"results": []}', native_output([]), '{"results": []} trailing'],
)
def test_absent_or_malformed_evidence_is_never_clean(output: str) -> None:
    report = parse_osv_json(output)
    assert report.verification_failed
    assert report.problems
    assert report.findings == ()


@pytest.mark.parametrize(
    "field,value", [("name", None), ("name", " "), ("name", "package\nname"), ("version", None), ("ecosystem", None)]
)
def test_malformed_identity_rows_are_incomplete(native_package: dict[str, object], field: str, value: object) -> None:
    metadata = json_object(native_package["package"])
    metadata[field] = value
    broken = {**native_package, "package": metadata}
    report = parse_osv_json(native_output([broken, native_package]))
    assert report.verification_failed
    assert report.counts["advisory_records"] == 4
    assert report.findings[0].package == "protobuf"


@pytest.mark.parametrize(
    "extension",
    [
        {"coverage": "partial"},
        {"experimental_config": {"licenses": {"summary": True, "allowlist": None}}},
        {"experimental_config": {"licenses": {"summary": 0, "allowlist": None}}},
    ],
    ids=["unknown-field", "enabled-analysis", "false-is-not-zero"],
)
def test_native_configuration_extensions_are_incomplete_but_retain_advisories(
    native_package: dict[str, object], extension: dict[str, object]
) -> None:
    report = parse_osv_json(native_output([native_package], **extension))
    assert report.verification_failed
    assert report.counts["advisory_records"] == 4


@pytest.mark.parametrize("groups", [None, [{"ids": []}], [{"ids": ["PYSEC-2026-1805"], "experimental_analysis": {}}]])
def test_invalid_or_analysis_extended_groups_preserve_advisories(
    native_package: dict[str, object], groups: object
) -> None:
    native_package["groups"] = groups
    report = parse_osv_json(native_output([native_package]))
    assert report.verification_failed
    assert report.counts["advisory_records"] == 4


@pytest.mark.parametrize("metadata", [{"aliases": None}, {"affected": {}}, {"ignored": True}])
def test_invalid_advisory_metadata_keeps_its_valid_identifier(
    native_package: dict[str, object], metadata: dict[str, object]
) -> None:
    native_package["vulnerabilities"] = [{"id": "PYSEC-2026-1805", **metadata}]
    native_package.pop("groups")
    report = parse_osv_json(native_output([native_package]))
    assert report.verification_failed
    assert report.counts["advisory_records"] == 1
    assert report.findings[0].advisory_id == "PYSEC-2026-1805"


def test_invalid_source_and_advisory_siblings_do_not_discard_valid_findings(native_package: dict[str, object]) -> None:
    native_package["vulnerabilities"] = [None, {"id": ""}, {"id": "PYSEC-2026-1805"}]
    native_package.pop("groups")
    source = {"source": {"path": "/fixtures/uv.lock", "type": "lockfile"}, "packages": [native_package]}
    report = parse_osv_json(json.dumps({"results": [None, source]}))
    assert report.verification_failed
    assert report.counts["advisory_records"] == 1
    assert report.findings[0].advisory_id == "PYSEC-2026-1805"


def test_native_groups_without_their_advisory_records_are_incomplete(native_package: dict[str, object]) -> None:
    native_package.pop("vulnerabilities")
    report = parse_osv_json(native_output([native_package]))
    assert report.verification_failed
    assert report.findings == ()
    assert report.problems == ("native groups refer to unreported advisories",)


def test_invalid_alias_siblings_do_not_drop_valid_aliases(native_package: dict[str, object]) -> None:
    native_package["vulnerabilities"] = [{"id": "PYSEC-2026-1805", "aliases": [None, "CVE-2026-0994", "\ud800"]}]
    native_package.pop("groups")
    report = parse_osv_json(native_output([native_package]))
    assert report.verification_failed
    assert report.findings[0].aliases == ("CVE-2026-0994",)


def test_unsupported_native_source_retains_its_advisories(native_package: dict[str, object]) -> None:
    source = {"source": {"path": "/fixtures/uv.lock", "type": "git"}, "packages": [native_package]}
    report = parse_osv_json(json.dumps({"results": [source]}))
    assert report.verification_failed
    assert report.counts["advisory_records"] == 4
    assert report.problems == ("unsupported native source type",)


@pytest.mark.parametrize(
    "fragment,problem",
    [
        ('"id": "PYSEC-2026-1805", "id": "PYSEC-2026-1805"', "native JSON has duplicate fields"),
        ('"id": "PYSEC-2026-1805", "database_specific": {"score": NaN}', "native JSON has a nonfinite number"),
    ],
    ids=["duplicate-key", "nonfinite-number"],
)
def test_json_guards_reject_otherwise_valid_native_records(vulnerable_output: str, fragment: str, problem: str) -> None:
    output = vulnerable_output.replace('"id": "PYSEC-2026-1805"', fragment, 1)
    report = parse_osv_json(output)
    assert report.verification_failed
    assert report.problems == (problem, "native output has no package evidence")
    assert report.findings == ()


def test_json_size_guard_accepts_exact_limit_and_rejects_one_more_character(clean_output: str) -> None:
    exact = clean_output + " " * (8 * 1024 * 1024 - len(clean_output))
    assert not parse_osv_json(exact).verification_failed
    report = parse_osv_json(exact + " ")
    assert report.problems == ("native JSON exceeds the size limit", "native output has no package evidence")
    assert report.findings == ()


@pytest.mark.parametrize("output", ['{"results": ' + "1" * 5000 + "}", "[" * 1100])
def test_unrepresentable_native_json_is_incomplete(output: str) -> None:
    assert parse_osv_json(output).problems == ("invalid native JSON", "native output has no package evidence")
