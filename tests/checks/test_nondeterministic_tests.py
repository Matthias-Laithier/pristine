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


def test_seeds_patched_sleeps_and_production_code_are_exempt(run_pristine: RunPristine) -> None:
    files = {
        "tests/test_seeded.py": SEEDED,
        "tests/test_patched.py": PATCHED_SLEEP,
        "app/welcome.py": SOURCE,
    }
    _, report = run_pristine(files)
    assert rule_findings(report, RULE_ID) == []
