import pytest

from tests.conftest import RunPristine, rule_findings

CHECK_ID = "SAFE-1"
READ_IN_FUNCTION = """import os


def payment_term_days():
    return int(os.environ["PAYMENT_TERM_DAYS"])
"""
SERVER_ENTRY = """import os


def main():
    serve(port=int(os.environ["PORT"]))
"""
SCRIPTS_MANIFEST = """[project]
name = "billing"

[project.scripts]
billing-server = "billing.server:main"
"""
INVOKE_TASKS = """import os

from invoke import task


@task
def deploy(context):
    context.run(f"deploy --region {os.environ['BILLING_REGION']}")
"""


def test_invoke_tasks_module_is_exempt(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"deployment.py": INVOKE_TASKS})
    assert rule_findings(report, CHECK_ID) == []


@pytest.mark.parametrize("path", ["billing/config.py", "billing/main.py", "billing/tasks.py", "scripts/backfill.py"])
def test_read_in_a_module_named_like_a_root_is_reported(run_pristine: RunPristine, path: str) -> None:
    _, report = run_pristine({path: READ_IN_FUNCTION})
    assert rule_findings(report, CHECK_ID) == [(5, "warning")]


def test_entry_function_named_by_the_manifest_is_exempt(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"pyproject.toml": SCRIPTS_MANIFEST, "src/billing/server.py": SERVER_ENTRY})
    assert rule_findings(report, CHECK_ID) == []


def test_module_that_the_package_main_imports_is_exempt(run_pristine: RunPristine) -> None:
    package_main = "from .server import main\n\nmain()\n"
    _, report = run_pristine({"billing/__main__.py": package_main, "billing/server.py": SERVER_ENTRY})
    assert rule_findings(report, CHECK_ID) == []


def test_function_named_main_without_a_manifest_entry_is_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"src/billing/server.py": SERVER_ENTRY})
    assert rule_findings(report, CHECK_ID) == [(5, "warning")]
