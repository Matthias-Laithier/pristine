import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "BS-1"
SCATTERED_READS = """import os
from os import environ, getenv


def payment_term_days():
    return int(os.environ.get("PAYMENT_TERM_DAYS", "30"))


def billing_region():
    return os.environ["BILLING_REGION"] or getenv("FALLBACK_REGION")


def invoice_bucket():
    return environ.get("INVOICE_BUCKET")
"""
READ_IN_FUNCTION = """import os


def payment_term_days():
    return int(os.environ["PAYMENT_TERM_DAYS"])
"""
UNREPORTED_READS = """import os

INVOICE_BUCKET = os.environ["INVOICE_BUCKET"]


def child_environment(names):
    return {name: os.environ[name] for name in names}


def subprocess_path(tool_directory):
    return f"{tool_directory}{os.pathsep}{os.environ.get('PATH', '')}"


def enable_billing_debug():
    os.environ["BILLING_DEBUG"] = "1"
    del os.environ["BILLING_TRACE"]


def main():
    serve(port=int(os.environ["PORT"]))
"""
SETTINGS_MODULE = """import os

from pydantic_settings import BaseSettings


class BillingSettings(BaseSettings):
    payment_term_days: int


def legacy_region():
    return os.environ["BILLING_REGION"]
"""


def test_reads_inside_functions_are_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing.py": SCATTERED_READS})
    assert rule_findings(report, RULE_ID) == [(6, "warning"), (10, "warning"), (14, "warning")]


def test_module_level_writes_dynamic_process_and_startup_reads_are_not_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing.py": UNREPORTED_READS})
    assert rule_findings(report, RULE_ID) == []


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("settings_loader.py", SETTINGS_MODULE),
        ("billing/config.py", READ_IN_FUNCTION),
        ("billing/main.py", READ_IN_FUNCTION),
        ("billing/cli.py", READ_IN_FUNCTION),
        ("billing/tasks.py", READ_IN_FUNCTION),
        ("tests/test_billing.py", READ_IN_FUNCTION),
        ("scripts/backfill_invoices.py", READ_IN_FUNCTION),
        ("backfill_invoices.py", f"#!/usr/bin/env python3\n{READ_IN_FUNCTION}"),
        ("backfill_invoices.py", f"{READ_IN_FUNCTION}\n\nif __name__ == '__main__':\n    payment_term_days()\n"),
    ],
)
def test_settings_modules_entrypoints_tests_and_scripts_are_exempt(
    run_pristine: RunPristine, path: str, source: str
) -> None:
    _, report = run_pristine({path: source})
    assert rule_findings(report, RULE_ID) == []


def test_read_in_an_application_module_is_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing/reminders.py": READ_IN_FUNCTION})
    assert rule_findings(report, RULE_ID) == [(5, "warning")]
