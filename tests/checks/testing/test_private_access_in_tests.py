from tests.conftest import RunPristine, rule_findings

RULE_ID = "TST-1"
SOURCE = """import os
import sys
from collections import namedtuple


class InMemoryLedger:
    def __init__(self):
        self._entries = []

    def _record(self, entry):
        self._entries.append(entry)


def test_charge_stops_after_max_retries(gateway, mocker, monkeypatch):
    result = retry_charge(gateway, amount_in_cents=4200)
    assert result._attempt_count == 5
    result.gateway._session = None
    assert billing._parse_amount("42") == 42
    assert result._state._retries == 5
    ledger = InMemoryLedger()
    ledger._record("charge")
    assert ledger._entries == ["charge"]
    mocker.patch.object(result._client, "send")
    monkeypatch.setattr(result, "_client", None)
    mock_gateway._calls.clear()
    fake_clock._now = 0
    assert Invoice._meta.db_table == "invoices"
    assert result._asdict() == {}
    assert result.__dict__ == {}
    assert result.__class__ is Charge
    frame = sys._getframe()
    assert result._status_ == "failed"
    os._exit(0)
"""


def test_private_attribute_access_in_tests_is_a_warning(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/test_billing.py": SOURCE})
    assert rule_findings(report, RULE_ID) == [(16, "warning"), (17, "warning"), (18, "warning"), (19, "warning")]


def test_production_code_is_exempt(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing/retry.py": SOURCE})
    assert rule_findings(report, RULE_ID) == []


def test_files_without_tests_are_exempt_unless_they_are_conftest(run_pristine: RunPristine) -> None:
    load_script = "def send_requests(client):\n    return client._session.post('/charge')\n"
    files = {"benchmark/load_test.py": load_script, "tests/conftest.py": load_script}
    _, report = run_pristine(files)
    assert {finding["path"] for finding in report["findings"] if finding["rule_id"] == RULE_ID} == {"tests/conftest.py"}
