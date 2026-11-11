import pytest

from tests.conftest import RunPristine, rule_findings

CHECK_ID = "TEST-1"
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
    assert rule_findings(report, CHECK_ID) == [(16, "warning"), (17, "warning"), (18, "warning"), (19, "warning")]


def test_production_code_is_exempt(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing/retry.py": SOURCE})
    assert rule_findings(report, CHECK_ID) == []


def test_files_without_tests_are_exempt_unless_they_are_conftest(run_pristine: RunPristine) -> None:
    load_script = "def send_requests(client):\n    return client._session.post('/charge')\n"
    files = {"benchmark/load_test.py": load_script, "tests/conftest.py": load_script}
    _, report = run_pristine(files)
    assert {finding["path"] for finding in report["findings"] if finding["check_id"] == CHECK_ID} == {
        "tests/conftest.py"
    }


@pytest.mark.parametrize("extension", ["test.ts", "spec.tsx"])
def test_typescript_private_state_in_callbacks(run_pristine: RunPristine, extension: str) -> None:
    source = """import { test as check, vi as clock } from "vitest";
function helper() { return service._hidden; }
check("state", () => {
  expect(service._state).toBe("ready");
  service.client._session = null;
  expect(service._state._retries).toBe(2);
  fakeStore._state = 1;
  mock.client._session = null;
  this._state = 1;
  expect(Invoice._meta.table).toBe("invoice");
  clock.spyOn(service._client, "send");
  expect(service.__state__).toBe(1);
});
"""
    _, report = run_pristine({f"tests/orders.{extension}": source})
    assert rule_findings(report, CHECK_ID) == [(4, "warning"), (5, "warning"), (6, "warning")]


def test_typescript_private_state_requires_test_path_and_callback(run_pristine: RunPristine) -> None:
    source = """import {test as check} from "other";
check("state", () => service._state);
function helper() { return service._state; }
"""
    _, report = run_pristine({"tests/orders.test.ts": source, "orders.ts": 'test("state", () => service._state);'})
    assert rule_findings(report, CHECK_ID) == []
