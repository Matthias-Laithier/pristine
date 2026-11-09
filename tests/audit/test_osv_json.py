from pristine.audit.models import SourceEvidence
from pristine.audit.osv_json import parse_osv_json
from tests.audit.conftest import native_output
from tests.conftest import json_list, json_object


def test_recorded_native_advisories_keep_ids_aliases_and_contextual_fixed_releases(vulnerable_output: str) -> None:
    report = parse_osv_json(vulnerable_output)
    assert not report.verification_failed
    assert report.problems == ()
    assert report.sources == (SourceEvidence("/fixtures/vulnerable/uv.lock", "lockfile", 2),)
    assert report.counts == {"advisory_records": 4, "packages": 2, "sources": 1, "verification_failures": 0}
    assert [(finding.package, finding.version, finding.ecosystem) for finding in report.findings] == [
        ("protobuf", "4.25.5", "PyPI"),
        ("protobuf", "4.25.5", "PyPI"),
        ("protobuf", "4.25.5", "PyPI"),
        ("protobuf", "4.25.5", "PyPI"),
    ]
    assert [(finding.advisory_id, finding.aliases, finding.fixed_versions) for finding in report.findings] == [
        ("PYSEC-2026-1805", ("CVE-2026-0994", "GHSA-7gcm-g887-7qv7"), ("5.29.6", "6.33.5")),
        ("PYSEC-2026-1806", ("CVE-2025-4565", "GHSA-8qvm-5x2c-j2w7"), ("4.25.8", "5.29.5", "6.31.1")),
        ("GHSA-7gcm-g887-7qv7", ("CVE-2026-0994", "PYSEC-2026-1805"), ("6.33.5", "5.29.6")),
        ("GHSA-8qvm-5x2c-j2w7", ("CVE-2025-4565", "PYSEC-2026-1806"), ("4.25.8", "5.29.5", "6.31.1")),
    ]


def test_recorded_clean_result_requires_native_package_evidence(clean_output: str) -> None:
    report = parse_osv_json(clean_output)
    assert not report.verification_failed
    assert report.findings == ()
    assert report.problems == ()
    assert report.sources == (SourceEvidence("/fixtures/clean/uv.lock", "lockfile", 1),)
    assert report.counts == {"advisory_records": 0, "packages": 1, "sources": 1, "verification_failures": 0}


def test_scanner_failure_retains_valid_native_advisories(vulnerable_output: str) -> None:
    report = parse_osv_json(vulnerable_output, ("scanner timed out",))
    assert report.verification_failed
    assert report.problems == ("scanner timed out",)
    assert report.counts == {"advisory_records": 4, "packages": 2, "sources": 1, "verification_failures": 1}
    assert report.findings[0].advisory_id == "PYSEC-2026-1805"


def test_aliases_from_native_groups_do_not_merge_advisory_records(native_package: dict[str, object]) -> None:
    native_package["vulnerabilities"] = [{"id": "PYSEC-2026-1805"}, {"id": "GHSA-7gcm-g887-7qv7"}]
    native_package["groups"] = [json_list(native_package["groups"])[0]]
    report = parse_osv_json(native_output([native_package]))
    assert report.problems == ()
    assert report.counts["advisory_records"] == 2
    assert [(finding.advisory_id, finding.aliases) for finding in report.findings] == [
        ("PYSEC-2026-1805", ("GHSA-7gcm-g887-7qv7", "CVE-2026-0994")),
        ("GHSA-7gcm-g887-7qv7", ("PYSEC-2026-1805", "CVE-2026-0994")),
    ]


def test_record_occurrences_keep_source_version_and_ecosystem_boundaries(native_package: dict[str, object]) -> None:
    native_package["vulnerabilities"] = [{"id": "PYSEC-2026-1805"}]
    native_package.pop("groups")
    metadata = json_object(native_package["package"])
    other_package = {**native_package, "package": {**metadata, "version": "5.0.0", "ecosystem": "npm"}}
    document = json_object(json.loads(native_output([native_package, native_package])))
    document["results"] = [
        *json_list(document["results"]),
        {
            "source": {"path": "/fixtures/other/uv.lock", "type": "lockfile"},
            "packages": [other_package],
        },
    ]
    report = parse_osv_json(json.dumps(document))
    assert report.verification_failed
    assert report.problems == ("unsupported native package ecosystem",)
    assert [(finding.source_path, finding.version, finding.ecosystem) for finding in report.findings] == [
        ("/fixtures/vulnerable/uv.lock", "4.25.5", "PyPI"),
        ("/fixtures/vulnerable/uv.lock", "4.25.5", "PyPI"),
        ("/fixtures/other/uv.lock", "5.0.0", "npm"),
    ]


def test_fixed_releases_match_exact_native_package_and_ignore_git_commits(native_package: dict[str, object]) -> None:
    identity = {"name": "protobuf", "ecosystem": "PyPI"}
    interval = {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "4.25.8"}]}
    native_package["vulnerabilities"] = [
        {
            "id": "PYSEC-2026-1806",
            "affected": [
                {"package": {"name": "other-package", "ecosystem": "PyPI"}, "ranges": [interval]},
                {"package": {"name": "protobuf", "ecosystem": "npm"}, "ranges": [interval]},
                {
                    "package": identity,
                    "ranges": [{"type": "GIT", "events": [{"introduced": "0"}, {"fixed": "abc123"}]}],
                },
                {"package": identity, "ranges": [interval, interval]},
            ],
        }
    ]
    native_package.pop("groups")
    report = parse_osv_json(native_output([native_package]))
    assert report.problems == ()
    assert report.findings[0].fixed_versions == ("4.25.8",)


import json
