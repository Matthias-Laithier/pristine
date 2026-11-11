import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "TST-6"
SOURCE = """import random
import time


def test_welcome_email_is_sent(smtp_server):
    register_user(email="marc@example.com")
    time.sleep(2)
    assert random.choice(["marc", "lea"]) in smtp_server.recipients
    time.sleep(0)


def test_welcome_email_is_retried(smtp_server):
    for _ in range(3):
        time.sleep(0.1)


def wait_until_sent(smtp_server, timeout):
    deadline = time.time() + timeout
    while not smtp_server.sent and time.time() < deadline:
        time.sleep(0.05)


def slow_send(message):
    time.sleep(0.1)
"""
SEEDED = """import random

random.seed(7)


def test_shuffled_invoices_are_sorted():
    assert sort_invoices(random.sample(INVOICES, 3)) == sorted(INVOICES)
"""
PATCHED_SLEEP = """import time


def test_retry_backs_off(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    time.sleep(5)
"""
UNIMPORTED = """def test_welcome_email_is_sent(smtp_server):
    time.sleep(2)


def test_timer_is_a_parameter(time):
    time.sleep(2)
"""
MIXED_IMPLICIT_MODULES = """def test_welcome_email_is_sent(time):
    time.sleep(2)
    assert random.choice(["marc", "lea"]) == "marc"


def test_shipping_method_is_random():
    assert random.choice(["standard", "express"]) in {"standard", "express"}
"""
UNSHADOWED_TIME = """def test_retry_backs_off():
    time.sleep(2)
"""


def test_reads_of_the_outside_world_are_warnings(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/test_welcome.py": SOURCE})
    assert rule_findings(report, RULE_ID) == [(7, "warning"), (8, "warning")]


def test_files_without_tests_are_exempt_unless_they_are_conftest(run_pristine: RunPristine) -> None:
    load_script = "import random\n\n\ndef send_requests():\n    return random.random()\n"
    files = {"benchmark/load_test.py": load_script, "tests/conftest.py": SOURCE}
    _, report = run_pristine(files)
    assert {finding["path"] for finding in report["findings"] if finding["rule_id"] == RULE_ID} == {"tests/conftest.py"}


def test_unimported_time_module_is_resolved_unless_shadowed(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/test_welcome.py": UNIMPORTED})
    assert rule_findings(report, RULE_ID) == []


def test_implicit_modules_are_resolved_per_file(run_pristine: RunPristine) -> None:
    files = {"tests/test_mixed.py": MIXED_IMPLICIT_MODULES, "tests/test_retry.py": UNSHADOWED_TIME}
    _, report = run_pristine(files, "--jobs", "1")
    findings = [(finding["path"], finding["line"], finding["severity"]) for finding in report["findings"]]
    assert findings == [
        ("tests/test_mixed.py", 3, "warning"),
        ("tests/test_mixed.py", 7, "warning"),
        ("tests/test_retry.py", 2, "warning"),
    ]


def test_seeds_patched_sleeps_and_production_code_are_exempt(run_pristine: RunPristine) -> None:
    files = {
        "tests/test_seeded.py": SEEDED,
        "tests/test_patched.py": PATCHED_SLEEP,
        "app/welcome.py": SOURCE,
    }
    _, report = run_pristine(files)
    assert rule_findings(report, RULE_ID) == []


@pytest.mark.parametrize("extension", ["test.ts", "spec.tsx"])
def test_typescript_random_and_real_timer_calls(run_pristine: RunPristine, extension: str) -> None:
    source = """import {it as check, vi as clock} from "vitest";
function helper() { setTimeout(done, 10); }
check("real", async () => {
  const value = Math.random();
  await new Promise(resolve => setTimeout(resolve, 20));
  clock.useFakeTimers();
  setTimeout(done, 20);
  Math.random();
  clock.useRealTimers();
  setTimeout(done, 20);
});
check("other", () => setTimeout(done, 20));
"""
    _, report = run_pristine({f"tests/orders.{extension}": source})
    assert rule_findings(report, RULE_ID) == [
        (4, "warning"),
        (5, "warning"),
        (8, "warning"),
        (10, "warning"),
        (12, "warning"),
    ]


def test_typescript_timer_hooks_are_suite_scoped(run_pristine: RunPristine) -> None:
    source = """import {describe, test, beforeEach, vi} from "vitest";
describe("fake", () => {
  beforeEach(() => vi.useFakeTimers());
  test("fake", () => setTimeout(done, 2));
  test("restored", () => { vi.useRealTimers(); setTimeout(done, 2); });
});
describe("real", () => {
  test("real", () => setTimeout(done, 2));
});
test("top", () => setTimeout(done, 2));
"""
    _, report = run_pristine({"tests/orders.test.ts": source})
    assert rule_findings(report, RULE_ID) == [(5, "warning"), (8, "warning"), (10, "warning")]


def test_typescript_shadowed_or_conditional_fakes_do_not_exempt(run_pristine: RunPristine) -> None:
    source = """import {test, vi} from "vitest";
test("shadow", (vi) => { vi.useFakeTimers(); setTimeout(done, 2); });
test("conditional", () => { if (ready) vi.useFakeTimers(); setTimeout(done, 2); });
test("nested", () => { const helper = () => vi.useFakeTimers(); setTimeout(done, 2); });
test("globals", (Math, setTimeout) => { Math.random(); setTimeout(done, 2); });
function helper(test) { test("custom", () => Math.random()); }
"""
    _, report = run_pristine({"tests/orders.test.ts": source, "orders.ts": 'test("x", () => Math.random());'})
    assert rule_findings(report, RULE_ID) == [(2, "warning"), (3, "warning"), (4, "warning")]


def test_typescript_unproven_timer_setup_is_not_owned(run_pristine: RunPristine) -> None:
    source = """import {test, beforeEach, vi} from "@jest/globals";
import {jest as clock} from "@jest/globals";
beforeEach(() => { ready && clock.useFakeTimers(); });
test("logical", () => setTimeout(done, 2));
test("deferred", () => { helper(() => clock.useFakeTimers()); setTimeout(done, 2); });
test("late", () => { setTimeout(done, 2); clock.useFakeTimers(); });
test("real", () => { clock.useFakeTimers(); if (ready) clock.useRealTimers(); setTimeout(done, 2); });
test("replaced", () => { clock = custom; clock.useFakeTimers(); setTimeout(done, 2); });
"""
    _, report = run_pristine({"tests/orders.test.ts": source})
    assert rule_findings(report, RULE_ID) == [
        (4, "warning"),
        (5, "warning"),
        (6, "warning"),
        (7, "warning"),
        (8, "warning"),
    ]
