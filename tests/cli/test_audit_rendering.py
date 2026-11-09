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
    assert "verify: coverage incomplete" in output
    assert "verification: incomplete" in output
    assert "summary: 4 advisory records, 3 packages, 2 sources, 1 verification failures" in output


def test_text_limit_keeps_full_overviews_without_printing_hidden_advisories() -> None:
    finding = DependencyFinding("uv.lock", "lockfile", "protobuf", "1.0", "PyPI", "OSV-2026-1", (), ())
    report = AuditReport((finding, finding), (SourceEvidence("uv.lock", "lockfile", 1),), ())
    output = render_text(report, 1)
    assert output.count("uv.lock") == 2
    assert output.count("    - OSV-2026-1;") == 1
    assert "  1 package; 2 advisory records" in output
    assert "... 1 findings omitted" in output
    assert "fixed releases: not reported" in output
