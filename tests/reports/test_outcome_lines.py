import pytest

from pristine.reports.outcome_lines import MalformedOutcomeLine, decoded_outcome


def test_decoded_outcome_rejects_a_non_string_severity() -> None:
    line = (
        '{"path": "invoice.py", "kind": "checked", "findings": '
        '[{"path": "invoice.py", "line": 3, "check_id": "STR-4", "severity": [], "message": "comment"}]}'
    )

    with pytest.raises(MalformedOutcomeLine):
        decoded_outcome(line)
