from pristine.audit.models import AuditReport, DependencyFinding, SourceEvidence
from pristine.cli.audit import render_text


def test_text_groups_sources_and_versions_without_merging_advisory_records() -> None:
    first = DependencyFinding("first/uv.lock", "lockfile", "protobuf", "1.0", "PyPI", "OSV-2026-1", (), ())
    second = DependencyFinding("second/uv.lock", "lockfile", "protobuf", "1.0", "PyPI", "OSV-2026-2", (), ("1.1",))
    changed = DependencyFinding("first/uv.lock", "lockfile", "protobuf", "2.0", "PyPI", "OSV-2026-3", (), ("2.1",))
    report = AuditReport(
        (first, second, changed, first),
        (SourceEvidence("first/uv.lock", "lockfile", 2), SourceEvidence("second/uv.lock", "lockfile", 1)),
        ("coverage incomplete",),
    )
    output = render_text(report, None)
    assert output.count("first/uv.lock") == output.count("second/uv.lock") == 1
    assert output.count("PyPI protobuf@1.0") == 2
    assert output.count("PyPI protobuf@2.0") == 1
    assert output.count("    - OSV-2026-1;") == 2
    assert "first/uv.lock (lockfile)\n  2 packages; 3 advisory records" in output
    assert "second/uv.lock (lockfile)\n  1 package; 1 advisory record" in output
    assert "    - OSV-2026-2; fixed releases: 1.1" in output
    assert "    - OSV-2026-3; fixed releases: 2.1" in output
    assert output.count("fixed releases: not reported") == 2
    assert "verify: coverage incomplete" in output
    assert "verification: incomplete" in output
    assert "summary: 4 advisory records, 3 packages, 2 sources, 1 verification failures" in output
    capped = render_text(report, 1)
    assert "second/uv.lock (lockfile)\n  1 package; 1 advisory record\n  PyPI protobuf@1.0; 1 advisory record" in capped
    assert "  PyPI protobuf@2.0; 1 advisory record" in capped
    assert capped.count("    - ") == 1


def test_text_limit_keeps_all_affected_packages_in_one_source() -> None:
    first = DependencyFinding("uv.lock", "lockfile", "protobuf", "1.0", "PyPI", "OSV-2026-1", (), ())
    second = DependencyFinding("uv.lock", "lockfile", "requests", "2.0", "PyPI", "OSV-2026-2", (), ("2.1",))
    report = AuditReport((first, second), (SourceEvidence("uv.lock", "lockfile", 2),), ())
    output = render_text(report, 1)
    assert "uv.lock (lockfile)\n  2 packages; 2 advisory records" in output
    assert "  PyPI requests@2.0; 1 advisory record\n... 1 findings omitted" in output
    assert "  PyPI protobuf@1.0; 1 advisory record\n    - OSV-2026-1;" in output
    assert "OSV-2026-2" not in output
    assert output.count("    - ") == 1
    assert "summary: 2 advisory records, 2 packages, 1 sources, 0 verification failures" in output
