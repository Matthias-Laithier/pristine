import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize("body", ["return send;", "const send = 1; return send;"])
def test_local_names_do_not_connect_module_declarations(run_pristine: RunPristine, body: str) -> None:
    source = f"""function send(invoice) {{ return invoice; }}
function unrelated(send) {{ {body} }}
const HANDLERS = {{send}};
"""
    _, report = run_pristine({"handlers.ts": source})
    assert rule_findings(report, "CR-6") == [(3, "warning")]


def test_related_callback_registry_stays_together(run_pristine: RunPristine) -> None:
    source = """function send(invoice) { return invoice; }
function send_reminder(invoice) { return send(invoice); }
const HANDLERS = {send, send_reminder};
"""
    _, report = run_pristine({"handlers.ts": source})
    assert not rule_findings(report, "CR-6")
