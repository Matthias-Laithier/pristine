import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "CO-11"
REEXPORT = "from .delivery import send_invoice\n"
DECLARED_REEXPORT = 'from .delivery import send_invoice\n\n__all__ = ["send_invoice"]\n'
EXPLICIT_ALIAS_REEXPORT = "from .delivery import send_invoice as send_invoice\n"
ABSOLUTE_REEXPORT = "from invoices.delivery import send_invoice\n"
SUBMODULE_IMPORT = "from . import delivery\nfrom invoices import rendering\n"
USED_IMPORT = "from .delivery import register_handlers\n\nregister_handlers()\n"
THIRD_PARTY_IMPORT = "from pydantic import BaseModel\n"
EXPORT_LIST = (
    'from .delivery import _normalize_recipient, send_invoice\n\n__version__ = "1.0"\n\n\n'
    "def render_invoice(invoice):\n    return invoice\n\n\n"
    '__all__ = [\n    "send_invoice",\n    "render_invoice",\n    "__version__",\n'
    '    "archive_invoice",\n    "_normalize_recipient",\n]\n'
)
STAR_EXPORT_LIST = 'from .delivery import *\n\n__all__ = ["send_invoice"]\n'
INDEX = (
    'export * from "./delivery";\nexport * from "./types";\nexport * as rendering from "./rendering";\n'
    'export { sendInvoice } from "./sending";\nexport * from "@invoices/core";\n'
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (REEXPORT, [(1, "warning")]),
        (ABSOLUTE_REEXPORT, [(1, "warning")]),
        (DECLARED_REEXPORT, []),
        (EXPLICIT_ALIAS_REEXPORT, []),
        (SUBMODULE_IMPORT, []),
        (USED_IMPORT, []),
        (THIRD_PARTY_IMPORT, []),
        ("", []),
    ],
)
def test_package_reexports_need_an_export_list(
    run_pristine: RunPristine, source: str, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({"invoices/__init__.py": source})
    assert rule_findings(report, RULE_ID) == expected


def test_reexports_in_a_plain_module_or_a_test_package_are_allowed(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices/sending.py": REEXPORT, "tests/invoices/__init__.py": REEXPORT})
    assert rule_findings(report, RULE_ID) == []


def test_export_list_names_must_be_defined_and_public(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices/billing.py": EXPORT_LIST})
    assert rule_findings(report, RULE_ID) == [(14, "error"), (15, "warning")]


def test_star_import_makes_export_list_unverifiable(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices/billing.py": STAR_EXPORT_LIST})
    assert rule_findings(report, RULE_ID) == []


def test_index_must_not_reexport_a_whole_internal_module(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices/index.ts": INDEX, "invoices/billing.js": INDEX})
    assert rule_findings(report, RULE_ID) == [(1, "warning"), (2, "warning")]
