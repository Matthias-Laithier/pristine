import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "BS-3"
PYTHON_SOURCE = """import requests
import httpx
from subprocess import run
from urllib.request import urlopen
requests.get(url)
requests.get(url, timeout=3)
requests.get(url, timeout=None)
requests.post(url, **options)
run(["git", "status"], check=True)
urlopen(url, None)
urlopen(url, None, 5)
httpx.get(url)
session.get(url)
"""
SCRIPT_SOURCE = """import axios from "axios";
await fetch(url);
await fetch(url, { signal: AbortSignal.timeout(3000) });
await fetch(url, init);
await fetch("/api/orders");
await fetch(url, { credentials: "include" });
await axios.post(url, order);
await axios.post(url, order, { timeout: 3000 });
await axios({ url });
"""
GO_SOURCE = """package billing
import "net/http"
func fetchInvoices() {
	http.Get(invoicesURL)
	unbounded := &http.Client{}
	bounded := &http.Client{Timeout: invoiceTimeout}
	http.DefaultClient.Do(request)
}
"""
BROWSER_MARKERS = [
    '"use client";\n',
    'import { useEffect } from "react";\n',
    'import { ref } from "vue";\n',
    "const orderBadge = <span>{order.number}</span>;\n",
]


def test_python_calls_without_timeout_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"sync.py": PYTHON_SOURCE})
    assert rule_findings(report, RULE_ID) == [(5, "error"), (7, "error"), (9, "error"), (10, "error")]


def test_server_side_scripts_without_bound_are_warnings(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"scripts/sync.ts": SCRIPT_SOURCE})
    assert rule_findings(report, RULE_ID) == [(2, "warning"), (7, "warning"), (9, "warning")]


@pytest.mark.parametrize("marker", BROWSER_MARKERS)
def test_browser_code_is_exempt(run_pristine: RunPristine, marker: str) -> None:
    _, report = run_pristine({"orders.tsx": marker + SCRIPT_SOURCE})
    assert rule_findings(report, RULE_ID) == []


@pytest.mark.parametrize("path", ["src/components/orders.ts", "src/app/api/orders/route.ts", "orders.tsx"])
def test_server_code_is_reported_whatever_its_path(run_pristine: RunPristine, path: str) -> None:
    _, report = run_pristine({path: SCRIPT_SOURCE})
    assert rule_findings(report, RULE_ID) == [(2, "warning"), (7, "warning"), (9, "warning")]


def test_go_http_without_timeout(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing.go": GO_SOURCE})
    assert rule_findings(report, RULE_ID) == [(4, "error"), (5, "warning"), (7, "warning")]


def test_interactive_launch_on_the_terminal_is_exempt(run_pristine: RunPristine) -> None:
    source = (
        "import os\nimport subprocess\n"
        'subprocess.run([os.environ.get("EDITOR", "vi"), path], check=False)\n'
        'subprocess.run(["less", path])\n'
        'subprocess.run([os.environ["EDITOR"], path], capture_output=True)\n'
    )
    _, report = run_pristine({"editing.py": source})
    assert rule_findings(report, RULE_ID) == [(5, "error")]
