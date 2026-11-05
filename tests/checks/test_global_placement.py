import pytest

from tests.conftest import RunPristine, rule_findings

PYTHON_PLACEMENT = "import os\n\nRETRY_COUNT = 3\n\n\ndef send(invoice):\n    return invoice\n\n\nSMTP_PORT = 587\n"
PYTHON_EXCEPTIONS = (
    "from typing import TypeAlias\n\n\nclass Handler:\n    pass\n\n\n"
    "HANDLERS = build_registry(Handler)\nDEFAULT_HANDLER = HANDLERS['default']\n__all__ = ['Handler']\n"
    "InvoiceId: TypeAlias = str\nPayload = dict[str, str]\n\n"
    "if __name__ == '__main__':\n    exit_code = 0\n"
)
SCRIPT_PLACEMENT = (
    "const RETRY_COUNT = 3;\nexport const sendInvoice = (invoice) => invoice;\n"
    "const DEFAULT_INVOICE = sendInvoice({});\nexport const SMTP_PORT = 587;\n"
)
GO_PLACEMENT = (
    "package billing\n\nconst retryCount = 3\n\ntype Sender struct{}\n\nfunc send() {}\n\n"
    "var _ = Sender{}\nvar smtpPort = 587\n"
)
RUST_PLACEMENT = "const RETRY_COUNT: u32 = 3;\n\nfn send() {}\n\nstatic SMTP_PORT: u32 = 587;\n"


@pytest.mark.parametrize(
    ("file_name", "source", "expected"),
    [
        ("billing.py", PYTHON_PLACEMENT, [(10, "warning")]),
        ("billing.py", PYTHON_EXCEPTIONS, []),
        ("billing.ts", SCRIPT_PLACEMENT, [(4, "warning")]),
        ("billing.go", GO_PLACEMENT, [(10, "warning")]),
        ("billing.rs", RUST_PLACEMENT, [(5, "warning")]),
    ],
)
def test_global_defined_below_first_definition(
    run_pristine: RunPristine, file_name: str, source: str, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({file_name: source})
    assert rule_findings(report, "CR-6") == expected
