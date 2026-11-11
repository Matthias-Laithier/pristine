import pytest

from tests.conftest import RunPristine, rule_findings

CHECK_ID = "STR-11"
FLAGGED = {
    "built getattr": ("jobs.py", 'handler = getattr(handlers, f"on_{kind}")\n', "warning"),
    "concatenated import": (
        "jobs.py",
        'import importlib\nmodule = importlib.import_module("jobs." + kind)\n',
        "warning",
    ),
    "wildcard": ("jobs.py", "from billing.handlers import *\n", "error"),
    "template import": ("jobs.ts", "const steps = await import(`./steps/${kind}`);\n", "warning"),
    "re-export": ("jobs.ts", 'export { loadInvoice } from "./invoices";\n', "warning"),
}
KEPT = {
    "literal getattr": ("jobs.py", 'handler = getattr(handlers, "on_invoice")\n'),
    "variable getattr": ("jobs.py", "value = getattr(record, field_name)\n"),
    "json import": ("jobs.ts", "const messages = await import(`./messages/${locale}.json`);\n"),
    "entry point": ("index.ts", 'export { loadInvoice } from "./invoices";\n'),
}


@pytest.mark.parametrize(("name", "source", "severity"), FLAGGED.values(), ids=FLAGGED.keys())
def test_unsearchable_names_are_flagged(run_pristine: RunPristine, name: str, source: str, severity: str) -> None:
    _, report = run_pristine({name: source})
    assert [found_severity for _, found_severity in rule_findings(report, CHECK_ID)] == [severity]


@pytest.mark.parametrize(("name", "source"), KEPT.values(), ids=KEPT.keys())
def test_searchable_names_pass(run_pristine: RunPristine, name: str, source: str) -> None:
    _, report = run_pristine({name: source})
    assert rule_findings(report, CHECK_ID) == []
