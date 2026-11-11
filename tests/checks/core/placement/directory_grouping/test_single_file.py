import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "CR-15"
CODE = "VALUE = 1\n"


def tree(folder: str, names: list[str]) -> dict[str, str]:
    return {f"{folder}/{name}": CODE for name in names}


def test_folder_holding_one_file_is_reported(run_pristine: RunPristine) -> None:
    files = tree("billing/src", ["ledger.py", "pricing.py"]) | {"billing/src/refunds/refund_policy.py": CODE}
    _, report = run_pristine(files)
    findings = [finding for finding in report["findings"] if finding["rule_id"] == RULE_ID]
    assert [(finding["path"], finding["line"]) for finding in findings] == [("billing/src/refunds/refund_policy.py", 1)]


@pytest.mark.parametrize(
    "lone_file",
    [
        "billing/src/refunds/__init__.py",
        "web/src/refunds/index.ts",
        "web/src/app/refunds/page.tsx",
        "web/src/app/api/refunds/route.ts",
        "billing/migrations/versions/0001_refunds.py",
        "billing/tests/refunds/test_refund_policy.py",
        "billing/src/services/refunds/stripe.py",
        "billing/src/templates/refunds/refund_policy.py",
        "billing/src/refunds/refunds.py",
    ],
)
def test_conventional_lone_file_is_not_reported(run_pristine: RunPristine, lone_file: str) -> None:
    _, report = run_pristine(tree("billing/src", ["ledger.py", "pricing.py"]) | {lone_file: CODE})
    assert rule_findings(report, RULE_ID) == []


def test_folder_with_a_second_entry_is_not_reported(run_pristine: RunPristine) -> None:
    files = {"billing/src/ledger.py": CODE, "billing/src/refunds/refund_policy.py": CODE}
    _, report = run_pristine(files | {"billing/src/refunds/README.md": "# Refunds\n"})
    assert rule_findings(report, RULE_ID) == []


def test_lone_file_among_feature_folders_is_not_reported(run_pristine: RunPristine) -> None:
    files = tree("billing/src/invoices", ["invoice.py", "invoice_total.py"]) | {"billing/src/refunds/policy.py": CODE}
    _, report = run_pristine(files)
    assert rule_findings(report, RULE_ID) == []


def test_lone_file_in_a_repeated_slot_is_not_reported(run_pristine: RunPristine) -> None:
    files = tree("billing/src/invoices", ["definition.py", "invoice.py"]) | {"billing/src/refunds/definition.py": CODE}
    _, report = run_pristine(files | tree("billing/src", ["ledger.py", "pricing.py"]))
    assert rule_findings(report, RULE_ID) == []
