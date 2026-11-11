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
PYTHON_TYPES = (
    "from typing import Literal, TypeVar\nimport typing as t\nfrom pydantic import create_model\n\n\n"
    "def send(invoice):\n    return invoice\n\n\n"
    "Status = Literal['paid', 'open']\nInvoiceT = TypeVar('InvoiceT')\nMaybeId = int | None\n"
    "Lines = t.Sequence[str]\nAmount = float\nRefund = create_model('Refund', amount=(float, ...))\n"
)
PYTHON_CAPWORDS_VALUES = (
    "from metrics import Counter\n\n\ndef send(invoice):\n    return invoice\n\n\n"
    "DefaultCurrency = 'EUR'\nSentInvoices = Counter('sent')\nPermissions = READ | WRITE\n"
)
SCRIPT_CAPWORDS_VALUES = (
    "export function send(invoice) {\n  return invoice;\n}\nexport const InvoiceStatus = { paid: 'paid' };\n"
)
RUST_PLACEMENT = "const RETRY_COUNT: u32 = 3;\n\nfn send() {}\n\nstatic SMTP_PORT: u32 = 587;\n"
DEPENDENT_PLACEMENT = (
    "def send():\n    pass\ndef cancel():\n    pass\n"
    "HANDLERS = (send, cancel)\nDEFAULT = HANDLERS[0]\n"
    "def unrelated():\n    pass\nLATE = build_registry(send)\n"
)
INTERRUPTED_REGISTRY = (
    "def send():\n    pass\ndef unrelated():\n    pass\ndef cancel():\n    pass\nHANDLERS = (send, cancel)\n"
)
RELATED_DECLARATIONS = (
    "class Pattern:\n    pass\nclass Rule:\n    pattern: Pattern\n"
    "FIRST = Pattern('first')\nSECOND = Pattern('second')\nRULES = (Rule(FIRST), Rule(SECOND))\n"
    "def first():\n    return helper()\ndef helper():\n    return 0\n"
    "def second():\n    return first()\nCHECKS = (first, second)\n"
)


@pytest.mark.parametrize(
    ("file_name", "source", "expected"),
    [
        ("billing.py", PYTHON_PLACEMENT, [(10, "warning")]),
        ("billing.py", PYTHON_EXCEPTIONS, []),
        ("billing.py", PYTHON_TYPES, []),
        ("billing.py", PYTHON_CAPWORDS_VALUES, [(8, "warning"), (9, "warning"), (10, "warning")]),
        ("billing.ts", SCRIPT_PLACEMENT, [(4, "warning")]),
        ("billing.ts", SCRIPT_CAPWORDS_VALUES, [(4, "warning")]),
        ("billing.go", GO_PLACEMENT, [(10, "warning")]),
        ("billing.rs", RUST_PLACEMENT, [(5, "warning")]),
        ("billing.py", DEPENDENT_PLACEMENT, [(9, "warning")]),
        ("billing.py", INTERRUPTED_REGISTRY, [(7, "warning")]),
        ("billing.py", RELATED_DECLARATIONS, []),
        ("billing.ts", "function send() {}\nfunction cancel() {}\nconst DEFAULT = send();\n", [(3, "warning")]),
    ],
)
def test_global_defined_below_first_definition(
    run_pristine: RunPristine, file_name: str, source: str, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({file_name: source})
    assert rule_findings(report, "CR-6") == expected


@pytest.mark.parametrize(
    ("declaration", "expected"),
    [
        ("def unrelated(send):\n    return send\n", [(5, "warning")]),
        ("def unrelated():\n    send = 1\n    return send\n", [(6, "warning")]),
        ("def unrelated():\n    for send in (1,):\n        pass\n", [(6, "warning")]),
        ("def unrelated():\n    from billing import send\n    return send\n", [(6, "warning")]),
        ("def unrelated():\n    def send():\n        return 1\n    return send\n", [(7, "warning")]),
        ("def unrelated():\n    return invoice.send\n", [(5, "warning")]),
        ("def callback():\n    return send(1)\n", []),
        ("def callback(send=send):\n    return send(1)\n", []),
        ("class Callback:\n    send = None\n    def execute(self):\n        return send(1)\n", []),
        (
            "def callback():\n    def nested():\n        from billing import send\n        return send(1)\n    return send(1)\n",
            [],
        ),
        ("def unrelated():\n    return [send for send in (1,)]\n", [(5, "warning")]),
    ],
)
def test_only_module_references_connect_declarations(
    run_pristine: RunPristine, declaration: str, expected: list[tuple[int, str]]
) -> None:
    source = f"def send(invoice):\n    return invoice\n{declaration}HANDLERS = (send,)\n"
    _, report = run_pristine({"billing.py": source})
    assert rule_findings(report, "CR-6") == expected
